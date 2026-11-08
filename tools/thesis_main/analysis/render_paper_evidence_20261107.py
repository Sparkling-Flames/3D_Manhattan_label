"""Recompose paper figures from archived annotations and summary tables; no rescoring."""
from pathlib import Path
import importlib.util
import gzip
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from PIL import Image
from render_manuscript_3d import geometry, wire

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / 'docs/thesis_main/论文提纲_LaTeX_20261028'
OUT = PAPER / 'figures'
SUPPORT = ROOT / 'docs/thesis_main/论文写作工作资料'
EX = ROOT / 'research/workers/current_class_interpretation_20261104/examples'
MIX = ROOT / 'research/workers/mixture_patterns_and_c13_half_20261104/mixtures'
SIZE = ROOT / 'research/workers/image_response_v21_20261101/HOHONET_v21_image_response_20261101/stage07_summary'
ROOM = ROOT / 'research/fusion/manual_order_impact_20261104/same_room'
COLORS = ['#b36d37', '#437b97', '#26847b']
NAMES = ['C1: More simplifying', 'C2: Typical expression', 'C3: More turn-retaining']
METHOD = 'TARGET_DSTRUCT_K3'
AUDIT = {}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                     'axes.titlesize': 8.5, 'axes.labelsize': 8,
                     'xtick.labelsize': 7.5, 'ytick.labelsize': 7.5,
                     'pdf.fonttype': 42, 'axes.linewidth': .6})
spec = importlib.util.spec_from_file_location('example_renderer', EX / 'render_examples.py')
example_renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(example_renderer)
DATA = json.loads((EX / 'EXAMPLE_DATA.json').read_text(encoding='utf-8'))
CLASS_EASY_IMAGE = 'wc2JMjhGNzB-40'
replacement = json.loads((SUPPORT / '整体图表重排_20261108/easy_replacement.json').read_text(encoding='utf-8'))
DATA['images'].extend(replacement['images'])
DATA['slots'].extend(replacement['slots'])
DATA['objects'].update(replacement['objects'])
DATA['references'].update(replacement['references'])
IDS = pd.read_csv(PAPER / 'annotator_id_mapping.csv').set_index('source_worker_id')['paper_annotator_id'].to_dict()


def save(fig, name):
    extensions = ['pdf', 'png'] + (['svg'] if (OUT / f'{name}.svg').exists() else [])
    for ext in extensions:
        fig.savefig(OUT / f'{name}.{ext}', dpi=260, bbox_inches='tight', pad_inches=.06)
    plt.close(fig)


def clean(ax):
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(length=2, pad=2)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#9aa5af', alpha=.18, lw=.4)


def height_control():
    """Project archived geometry, including the missing reference verticals."""
    from matplotlib.patches import Polygon
    cases = json.loads((ROOT / 'outputs/visit16/assets/height.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1))
    def project(points):
        p = np.asarray(points)
        return np.column_stack((.82*p[:, 0]+.60*p[:, 2],
                                .35*p[:, 0]-.48*p[:, 2]+p[:, 1]))
    for ax, key, title, color in zip(axes,
            ['square:perfect:0:0.0', 'square:tilt_x:1:0.2'],
            ['(a) Uniform height', '(b) Opposite sides ±20%'],
            ['#427984', '#c52720']):
        case = cases[key]
        b = np.array(case['annotation_geometry']['bottom3d'])
        t = np.array(case['annotation_geometry']['top3d'])
        r = np.array(case['reference_geometry']['top3d'])
        assert np.allclose(t[:, [0, 2]], r[:, [0, 2]])
        assert np.isclose(t[:, 1].mean(), r[:, 1].mean())
        assert np.allclose(b, case['reference_geometry']['bottom3d'])
        bp, tp, rp = project(b), project(t), project(r)
        ax.add_patch(Polygon(bp, facecolor='#f0f2f3', edgecolor='#657079', lw=.75))
        ax.add_patch(Polygon(tp, facecolor=color, alpha=.12, edgecolor='none'))
        if key != 'square:perfect:0:0.0':
            ring = rp[[0, 1, 2, 3, 0]]
            ax.plot(*ring.T, color='#727c84', lw=.85, ls=(0, (3, 2)))
            for i in np.flatnonzero(t[:, 1] < r[:, 1]):
                # Only the exposed extension is dashed; the actual wall stays solid.
                ax.plot(*np.vstack([tp[i], rp[i]]).T, color='#727c84',
                        lw=.85, ls=(0, (3, 2)))
        for i in range(4):
            ax.plot(*np.vstack([bp[i], tp[i]]).T, color=color, lw=.95)
        ax.plot(*tp[[0, 1, 2, 3, 0]].T, color=color, lw=1.2)
        ax.scatter(*project([[0, 0, 0]])[0], s=9, color='#333333', zorder=5)
        ax.set(xlim=(-3.1, 3.1), ylim=(-3, 4), aspect='equal')
        ax.set_axis_off()
        ax.set_title(title, fontsize=9, pad=2)
        q = case['candidate_components']['main']['score']
        ax.text(.5, -.01, f"IoU 1.00   Hm 0   Hc {0 if key == 'square:perfect:0:0.0' else .1633:.4f}   Q {q:.2f}",
                transform=ax.transAxes, ha='center', fontsize=9)
    fig.subplots_adjust(wspace=.14)
    save(fig, 'height_control')


def chosen(image, cls):
    rows = [s for s in DATA['slots'] if s['image'] == image and s['method'] == METHOD
            and s['class_id'] == cls and s['image_group'] == 'primary']
    # The second geometric candidate retains 8 turns/3 short edges with less extreme labor.
    if image == 'jtcxE69GiFV-26' and cls == 'C3':
        return next(s for s in rows if s['object_id'] == 'v2:new:103127')
    return min(rows, key=lambda s: s['selection_rank'])


def panorama(ax, photo, points=None, color='#00d1e5'):
    ax.imshow(photo, extent=[0, 1024, 512, 0])
    if points is not None:
        for seg in example_renderer.boundary_segments(points):
            a = np.asarray(seg['xy'])
            ax.plot(*a.T, color=color, lw=1)
        p = np.asarray(points)
        for a, b in zip(p[::2], p[1::2]):
            ax.plot(*np.array([a, b]).T, color=color, lw=.7)
        ax.scatter(*p.T, s=7, c=color, edgecolors='#23333b', linewidths=.3, zorder=4)
    ax.set(xlim=(0, 1024), ylim=(512, 0))
    ax.axis('off')


def study_design():
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.set(xlim=(0, 12), ylim=(-1.15, 7)); ax.axis('off')
    def box(x,y,w,h,label):
        ax.add_patch(Rectangle((x,y),w,h,facecolor='#f4f7f8',edgecolor='#40535f',lw=.7))
        ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=7.3)
    def arrow(a,b):
        ax.annotate('',xy=b,xytext=a,arrowprops={'arrowstyle':'-|>','lw':.8,'color':'#40535f'})
    box(4.1,6.05,3.8,.72,'Independent annotation records\nManual / Semi · image · target')
    box(.2,4.5,3.3,.82,'Individual analysis\nstructure · quality · labor')
    box(4.35,4.5,3.3,.82,'Offline team recombination\nreuse independent responses')
    box(8.65,4.5,3.1,.82,'History and activity records\nprofiles / selection · labor')
    arrow((5,6.05),(1.85,5.32));arrow((6,6.05),(6,5.32));arrow((7,6.05),(10.2,5.32))
    for x,label in [(0.15,'Group size\n256 random orders'),(2.9,'Matched replacement\nshared retained members'),(5.65,'Composition and mixtures\nfixed or varying size')]:
        box(x,2.7,2.55,.82,label);arrow((5.95,4.5),(x+1.27,3.52))
    ax.text(1.42,2.38,'1  2  3  |  4  5  6  |  …  10',ha='center',fontsize=6.5)
    ax.text(1.42,2.08,'nested prefixes: 3 / 6 / 10',ha='center',fontsize=6.5)
    box(3.05,.5,3.0,.85,'Consensus construction\nlayout + output state')
    box(7.35,.5,3.0,.85,'Quality assessment\nQ and geometric components')
    arrow((2.65,2.7),(3.25,1.35))
    for x in [4.17,6.92]: arrow((x,2.65),(4.55,1.35))
    arrow((6.05,.92),(7.35,.92))
    ax.text(8.85,2.02,'Assigned target reference',ha='center',fontsize=7)
    arrow((8.85,1.88),(8.85,1.35))
    box(9.05,2.7,2.75,.82,'Selection / stopping\nand recorded labor')
    arrow((10.2,4.5),(10.4,3.52))
    box(.25,-.83,5.45,.66,'Method validation: geometry · reviews · baselines')
    box(6.25,-.83,5.45,.66,'Empirical study: people · teams · task conditions')
    fig.subplots_adjust(left=.01,right=.99,bottom=.03,top=.97)
    save(fig, 'study_design')


def geometry_consensus():
    fig, axes = plt.subplots(1, 2, figsize=(3.45, 3.6))
    chains = [ ['Layout + reference', 'Five geometric\nmeasurements', 'Scaled losses', 'Quality Q'],
               ['Independent\ncorner pairs', 'Correspondence', 'Person support\nand position', 'Source-ring order', 'Layout + status'] ]
    for ax, labels, title in zip(axes, chains, ['(a) Quality', '(b) Consensus']):
        ax.set(xlim=(0,1), ylim=(0,6)); ax.axis('off'); ax.set_title(title, fontsize=9)
        for i, label in enumerate(labels):
            y=5-i
            ax.add_patch(Rectangle((.03,y-.55),.94,.65,facecolor='#f5f8f8',edgecolor='#40535f',lw=.7))
            ax.text(.5,y-.22,label,ha='center',va='center',fontsize=8)
            if i<len(labels)-1: ax.annotate('',xy=(.5,y-.9),xytext=(.5,y-.55),arrowprops={'arrowstyle':'-|>','lw':.7})
    fig.subplots_adjust(left=.02,right=.98,top=.91,bottom=.09,wspace=.17)
    fig.text(.5,.02,'Support threshold: at least half the team',ha='center',fontsize=8)
    save(fig,'geometry_consensus')


def class_annotations():
    fig = plt.figure(figsize=(7.2, 6.4))
    selected = []
    for row, (image, difficulty) in enumerate([(CLASS_EASY_IMAGE, 'Easy'), ('jtcxE69GiFV-26', 'Difficult')]):
        im = next(x for x in DATA['images'] if x['image_code'] == image)
        photo = Image.open(EX / im['path'])
        ref = DATA['references'][im['reference_key']]
        bottom = .55 if row == 0 else .06
        fig.text(.01, bottom+.40, f'({"a" if row == 0 else "b"}) {difficulty} image · {image}', fontsize=9, weight='bold')
        for col in range(3):
            s = chosen(image, f'C{col+1}'); o = DATA['objects'][s['object_id']]; selected.append(s)
            x = col/3
            ax = fig.add_axes([x+.012, bottom+.205, .31, .17])
            panorama(ax, photo, o['points_1024x512'])
            ax.set_title(NAMES[col], color=COLORS[col], pad=2, fontsize=8)
            ax = fig.add_axes([x+.035, bottom+.005, .16, .185])
            for obj, color, ls in [(ref, '#7f8b94', '--'), (o, COLORS[col], '-')]:
                xy = np.asarray(obj['traits']['floor_xz_h']); closed = np.vstack([xy, xy[0]])
                ax.plot(*closed.T, color=color, ls=ls, lw=1)
            for edge in o['traits']['short_edge_start_nodes_1based']:
                ax.plot(*closed[edge-1:edge+1].T, color='#c18b00', lw=2)
            ax.scatter(*xy.T, s=6, c=COLORS[col], zorder=4)
            ax.scatter([0], [0], marker='+', c='#30373b', s=17, lw=.8)
            x0, x1, y0, y1 = im['floor_bounds']
            ax.set(xlim=(x0, x1), ylim=(y0, y1), xlabel='$x/h$', ylabel='$z/h$')
            ax.set_aspect('equal'); clean(ax); ax.tick_params(labelsize=6.7)
            short_label = 'short wall' if s['short_turn_edges'] == 1 else 'short walls'
            text = (f"{IDS[s['worker_id']]}\n{s['turn_n']:.0f} turns\n{s['short_turn_edges']:.0f} {short_label}\n"
                    f"Q {s['B8L2']:.1f}\nT {s['source_active_time_seconds']:.0f} s")
            fig.text(x+.215, bottom+.12, text, va='center', fontsize=7.6, linespacing=1.5)
    fig.legend(handles=[Line2D([], [], color='#437b97', label='Original BEV'),
                        Line2D([], [], color='#7f8b94', ls='--', label='Reference'),
                        Line2D([], [], color='#c18b00', lw=2, label='Short wall'),
                        Line2D([], [], color='#30373b', marker='+', ls='', label='Camera')],
               loc='lower center', ncol=4, frameon=False, fontsize=8, bbox_to_anchor=(.5, -.045))
    save(fig, 'class_annotations')
    AUDIT['class_annotations'] = [{k: s[k] for k in ['image','class_id','worker_id','object_id','selection_rank','B8L2','turn_n','short_turn_edges']} for s in selected]


def mixture_effects():
    d = pd.read_csv(MIX / 'DSTRUCT_SEVEN_COALITIONS_COMMON_Q.csv')
    q = d.pivot(index='image', columns='classes', values='B8L2')
    order = ['C1','C2','C3','C1|C2','C1|C3','C2|C3','C1|C2|C3']
    assert q.shape == (154, 7) and q.notna().all().all()
    means = q[order].mean()
    assert np.allclose(means.values, [75.37,84.83,92.29,84.14,90.21,88.52,87.98], atol=.011)
    fig, axs = plt.subplots(2, 1, figsize=(3.45, 5.0))
    fig.subplots_adjust(left=.28, right=.98, top=.94, bottom=.15, hspace=.55)
    ax = axs[0]; ys = np.arange(7)
    ax.scatter(means, ys, c=COLORS+['#596b77']*4, s=25, zorder=3)
    for y, v in enumerate(means): ax.text(v+.7, y, f'{v:.2f}', va='center', fontsize=7.5)
    ax.set(yticks=ys, yticklabels=[x.replace('|',' + ') for x in order], xlabel='Mean Q across images', xlim=(71, 99))
    ax.invert_yaxis(); ax.set_title('(a) Whole-class combinations', loc='left'); clean(ax)
    ax = axs[1]; effects = []
    for k, (mix, pure) in enumerate([('C1|C2','C1'),('C1|C2','C2'),('C1|C3','C1'),('C1|C3','C3'),('C2|C3','C2'),('C2|C3','C3')]):
        vals = (q[mix]-q[pure]).sort_values().values; effects.append(vals)
        y = np.full(len(vals), k) + np.linspace(-.15,.15,len(vals))
        ax.scatter(vals, y, s=5, color=COLORS[int(pure[-1])-1], alpha=.36, edgecolors='none')
        ax.scatter([vals.mean()], [k], s=28, marker='D', color='#172d39', zorder=4)
    ax.axvline(0, color='#52636c', lw=.7)
    ax.set(yticks=range(6), yticklabels=['C1+C2 − C1','C1+C2 − C2','C1+C3 − C1','C1+C3 − C3','C2+C3 − C2','C2+C3 − C3'], xlabel='Within-image ΔQ (mixture − pure)')
    ax.invert_yaxis(); ax.set_title('(b) Effects relative to each pure group', loc='left'); clean(ax)
    fig.text(.5,.015,'154 common images · team size varies\nAll available members of selected classes',ha='center',fontsize=8)
    save(fig,'profile_mixtures')
    AUDIT['profile_mixtures'] = {'images':len(q),'means':means.to_dict(),'paired_effect_means':[float(v.mean()) for v in effects]}


def member_distributions():
    d = pd.read_csv(MIX / 'SAME_CONFIGURATION_MEMBER_DISTRIBUTIONS.csv.gz')
    d = d[(d.method==METHOD)&(d.n==12)].copy()
    counts = d.class_counts.str.extract(r'C1:(\d+)\|C2:(\d+)\|C3:(\d+)').astype(int)
    d[['c1','c2','c3']] = counts
    assert ((d.c1+d.c2+d.c3)==12).all()
    candidates = []
    for (panel,c1), a in d.groupby(['panel_id','c1']):
        if len(a)>=4 and (a.valid_teams>=5).all():
            candidates.append((panel,c1,a.official_difficulty.iloc[0],a.within_p05_p95_width.mean()))
    picked = []
    for diff in ['简单','困难']:
        rows = sorted([r for r in candidates if r[2]==diff],key=lambda r:(r[3],r[0],r[1]))
        assert rows
        picked.append(rows[len(rows)//2])
    fig, axs=plt.subplots(2,1,figsize=(3.45,4.8), sharey=True)
    fig.subplots_adjust(left=.18,right=.97,bottom=.18,top=.94,hspace=.62)
    records=[]
    for ax, (panel,c1,diff,width), title in zip(axs,picked,['(a) Easy image','(b) Difficult image']):
        a=d[(d.panel_id==panel)&(d.c1==c1)].sort_values('c3'); xx=np.arange(len(a))
        ax.vlines(xx,a.p05,a.p95,color='#90b5c4',lw=5,alpha=.65)
        ax.plot(xx,a['mean'], 'o-', c='#245e79',ms=4,lw=1)
        for x,r in zip(xx,a.itertuples()):ax.text(x, 4, str(r.valid_teams), ha='center',fontsize=7,color='#57636b')
        ax.set(xticks=xx,xticklabels=[f'{r.c1}/{r.c2}/{r.c3}' for r in a.itertuples()],ylim=(0,110),xlabel='Composition: C1 / C2 / C3 counts')
        ax.set_title(title,loc='left');clean(ax)
        records+=a.to_dict('records')
    axs[0].set_ylabel('Team Q (12 annotators)')
    fig.text(.5,.045,'● Composition mean · bars: 5th–95th percentiles\nBottom numbers: scorable teams',ha='center',fontsize=7.5)
    save(fig,'composition_members')
    AUDIT['composition_members']={'selection':'median mean within-composition interval width among eligible chains, separately by difficulty','rows':records}


def image_changes():
    mem=pd.read_csv(SIZE/'manual/FIXED_PANEL_MEMBERS.csv')
    pools=mem[mem.panel=='ordinary_manual_main__capacity_ge30'].pool_id
    d=pd.read_csv(SIZE/'manual/PER_IMAGE_MARGINAL_CHANGES.csv.gz')
    d=d[d.pool_id.isin(pools)&(d.window=='fixed_20_to_30')&(d.metric=='B8L2_mean')].copy()
    assert len(d)==171 and d.image.nunique()==171
    fig,ax=plt.subplots(figsize=(3.45,2.8));fig.subplots_adjust(left=.19,right=.97,bottom=.19,top=.89)
    ax.axhspan(-2,2,color='#e8eef0',zorder=0);ax.axhline(0,color='#566a75',lw=.7)
    summaries={}
    for k,diff in enumerate(['Easy','Medium','Hard']):
        vals=d[d.difficulty_en==diff].delta.sort_values().values
        ax.scatter(k+np.linspace(-.22,.22,len(vals)),vals,s=9,c=COLORS[k],alpha=.65,edgecolors='none')
        ax.scatter([k],[vals.mean()],s=30,marker='D',color='#152d38',zorder=3)
        summaries[diff]={'n':len(vals),'mean':float(vals.mean()),'positive':int((vals>0).sum()),'negative':int((vals<0).sum())}
    ax.set(xticks=range(3),xticklabels=[f'{x}\n(n={summaries[x]["n"]})' for x in summaries],ylabel='Image-mean ΔQ (30 − 20 annotators)')
    ax.set_title('Individual-image changes on the fixed panel',loc='left');clean(ax)
    save(fig,'group_size_image_changes');AUDIT['group_size_image_changes']=summaries


def doorway_results():
    d=pd.read_csv(SIZE/'doorway/SCREENING_FIXED_PANEL_SUMMARY.csv')
    d=d[d.panel=='before_after_shared14']
    fig,axs=plt.subplots(2,1,figsize=(3.45,4.45));fig.subplots_adjust(left=.18,right=.98,bottom=.10,top=.94,hspace=.60)
    for ax,metric,factor,title,ylabel in zip(axs,['B8L2_mean','complete_evaluable_rate'],[1,100],
            ['(c) Conditional mean quality','(d) Complete-and-evaluable outputs'],['Change in mean Q','Rate change (percentage points)']):
        a=d[d.metric==metric].sort_values('k');assert len(a)==12 and a.valid_images.eq(17).all()
        ax.plot(a.k,a.mean_image_equal*factor,'o-',c='#256e7c',ms=3,lw=1)
        ax.axhline(0,color='#66757e',lw=.6);ax.set(xticks=[3,6,10,14],xlabel='Annotators per team',ylabel=ylabel)
        ax.set_title(title,loc='left');clean(ax)
    save(fig,'doorway_screening')
    AUDIT['doorway_screening']={'support':'before_after_shared14, fixed 17 images','quality_estimand':'difference of image-level marginal conditional means, not paired paths','k10':d[d.k==10][['metric','mean_image_equal']].to_dict('records')}


def doorway_absolute_curves():
    data = ROOT / 'research/data/doorway_review_20261030/screen439_results_20261031'
    d = pd.read_csv(data / 'AGGREGATE_COMMON_SUPPORT.csv')
    d = d[(d.k >= 3) & (d.k <= 14)].sort_values('k')
    assert len(d) == 12 and (d.capacity_images == 17).all() and (d.quality_images == 17).all()
    a = pd.read_csv(data / 'NATURAL_CURVES.csv')
    a = a[(a.image == '7y3sRwLe3Va-18') & (a.metric == 'B8L2') & a.family.isin(['space1','space2','whole_compatible'])]
    assert a.groupby('family').pool_n.first().to_dict() == {'space1':9,'space2':4,'whole_compatible':15}
    fig, axes = plt.subplots(2,2,figsize=(7.2,5.3),constrained_layout=True)
    for ax in axes.flat: clean(ax)
    for name,col in [('Before screening','#b36d37'),('After screening','#26847b')]:
        key = 'before' if name.startswith('Before') else 'after'
        axes[0,0].plot(d.k,d[key+'_q'],marker='o',ms=2.7,color=col,label=name)
        axes[0,1].plot(d.k,100*d[key+'_complete'],marker='o',ms=2.7,color=col,label=name)
    for fam,label,col in [('space1','Space 1 (N=9)','#437b97'),('space2','Space 2 (N=4)','#b36d37'),('whole_compatible','Whole (N=15)','#26847b')]:
        b=a[(a.family==fam)&(a.k>=3)].sort_values('k')
        for j,key in [(0,'mean'),(1,'complete_rate')]:
            axes[1,j].plot(b.k,b[key]*(100 if j else 1),marker='o',ms=2.7,color=col,label=label)
    for ax,t in zip(axes.flat,['(a) Quality: 17 doorway images','(b) Complete and evaluable: 17 images','(c) Quality: panorama 7y3sRwLe3Va-18','(d) Complete and evaluable: same panorama']):
        ax.set_title(t,loc='left',fontsize=8);ax.set_xlabel('Annotators per team')
    axes[0,0].set_ylabel('Mean Q');axes[1,0].set_ylabel('Mean Q')
    axes[0,1].set_ylabel('Complete and evaluable (%)');axes[1,1].set_ylabel('Complete and evaluable (%)')
    axes[0,0].set_xticks([3,6,10,14]);axes[0,1].set_xticks([3,6,10,14]);axes[1,0].set_xticks([3,6,9,12,15]);axes[1,1].set_xticks([3,6,9,12,15])
    axes[0,0].legend(fontsize=7,frameon=False);axes[1,0].legend(fontsize=6.7,frameon=False)
    save(fig,'doorway_absolute_curves')


def doorway_supplement_figures():
    from matplotlib.backends.backend_pdf import PdfPages
    data = ROOT / 'research/data/doorway_review_20261030/screen439_results_20261031'
    d = pd.read_csv(data / 'AGGREGATE_COMMON_SUPPORT.csv').sort_values('k')
    fig, axes = plt.subplots(1,2,figsize=(10,3.7),constrained_layout=True)
    for ax in axes: clean(ax); ax.axvline(14.5,color='#777777',ls='--',lw=.8);ax.set_xlabel('Annotators per team')
    for key,label,col in [('before','Before screening','#b36d37'),('after','After screening','#26847b')]:
        axes[0].plot(d.k,d[key+'_q'],color=col,label=label)
        axes[1].plot(d.k,100*d[key+'_complete'],color=col,label=label)
    axes[0].set_ylabel('Image-equal mean Q'); axes[1].set_ylabel('Complete and evaluable (%)')
    for ax in axes:
        other=ax.twinx();other.step(d.k,d.capacity_images,where='mid',color='#777777',alpha=.65,ls=':');other.set_ylabel('Supported images');other.set_ylim(0,18)
    axes[0].legend(frameon=False,fontsize=8);fig.suptitle('Figure S1. Doorway screening: changing image support',fontsize=10)
    fig.savefig(OUT/'doorway_full_range.pdf',bbox_inches='tight');plt.close(fig)
    x = d[(d.k >= 3) & (d.k <= 14)]
    fig, axes = plt.subplots(1,2,figsize=(8,3.1),constrained_layout=True)
    for ax in axes: clean(ax); ax.axhline(0,color='#777777',lw=.6);ax.set_xlabel('Annotators per team');ax.set_xticks([3,6,10,14])
    axes[0].plot(x.k,x.after_q-x.before_q,marker='o',ms=3,color='#26847b');axes[0].set_ylabel('Change in image-equal mean Q');axes[0].set_title('(a) Conditional quality',loc='left')
    axes[1].plot(x.k,100*(x.after_complete-x.before_complete),marker='o',ms=3,color='#26847b');axes[1].set_ylabel('Change in rate (percentage points)');axes[1].set_title('(b) Complete and evaluable',loc='left')
    fig.savefig(OUT/'doorway_screening_supp.pdf',bbox_inches='tight');plt.close(fig)
    rows=pd.read_csv(data/'NATURAL_CURVES.csv');rows=rows[rows.metric=='B8L2']
    families=[('overall_before','Before screening','#b36d37'),('overall_after','After screening','#26847b'),('space1','Space 1','#437b97'),('space2','Space 2','#d29128'),('whole_compatible','Whole compatible','#7561a6')]
    with PdfPages(OUT/'doorway_individual_curves.pdf') as pdf:
        for n,image in enumerate(sorted(rows.image.unique()),start=3):
            fig,axes=plt.subplots(2,2,figsize=(10,6.1),constrained_layout=True)
            for ax in axes.flat:clean(ax);ax.set_xlabel('Annotators per team')
            sub=rows[rows.image==image]
            for fam,label,col in families:
                a=sub[(sub.family==fam)&(sub.k>=3)].sort_values('k')
                if a.empty:continue
                k=0 if fam.startswith('overall') else 1
                label=f"{label} (N={int(a.pool_n.iloc[0])})"
                axes[k,0].plot(a.k,a['mean'],color=col,marker='o',ms=2,label=label)
                axes[k,1].plot(a.k,100*a.complete_rate,color=col,marker='o',ms=2,label=label)
            for i,name in enumerate(['Screening / common reference','Target-compatible pools']):
                axes[i,0].set_title(name+' — quality',fontsize=9);axes[i,1].set_title(name+' — output',fontsize=9)
                axes[i,0].set_ylabel('Mean Q');axes[i,1].set_ylabel('Complete and evaluable (%)')
                for ax in axes[i]:
                    ax.set_ylim((0,105));h,l=ax.get_legend_handles_labels()
                    if h:ax.legend(fontsize=7,frameon=False)
            fig.suptitle(f'Figure S{n}. {image}',fontsize=10);pdf.savefig(fig);plt.close(fig)


def individual_difficulty_rank():
    p=ROOT/'research/data/releases/v2.1/personnel_descriptive/difficulty_preferences.csv'
    d=pd.read_csv(p).dropna(subset=['B8L2_hard_rank','B8L2_nonhard_rank'])
    assert len(d)==59
    a=d[d.worker_id=='W002'].iloc[0]
    assert int(a.hard_n)==15 and int(a.nonhard_n)==43
    fig,ax=plt.subplots(figsize=(3.45,2.5),constrained_layout=True)
    ax.scatter(d.B8L2_nonhard_rank,d.B8L2_hard_rank,s=13,c='#7897a6',alpha=.6)
    ax.plot([0,1],[0,1],ls='--',color='#777777',lw=.7)
    ax.scatter([a.B8L2_nonhard_rank],[a.B8L2_hard_rank],s=32,c='#b36d37',zorder=4)
    ax.annotate('A2: 43 / 15 images',(a.B8L2_nonhard_rank,a.B8L2_hard_rank),xytext=(-65,-20),textcoords='offset points',fontsize=7,arrowprops={'arrowstyle':'-','lw':.5})
    ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean relative rank: non-difficult',ylabel='Mean relative rank: difficult')
    ax.set_title('Relative quality across image conditions',loc='left',fontsize=8);clean(ax)
    save(fig,'individual_difficulty_rank')


def matching_evidence():
    path=ROOT/'research/workers/personnel_v21_reselection_20261029/stage06_cases/traces_semantic/ae9bc0bdaf9a5f2119cea910.json.gz'
    with gzip.open(path,'rt',encoding='utf-8') as f:t=json.load(f)
    state=t['arms']['B']['full_state']; records={r['id']:r for r in t['pool']['records']}
    turn_colors=['#00b6d0','#d8a000']
    selected=[a for a in state['assignments'] if a['worker'] in ['W006','W106','W108']]
    assert len(selected)==3
    fig=plt.figure(figsize=(7.2,2.15))
    gs=fig.add_gridspec(1,4,width_ratios=[1,1,1,1.55],left=.05,right=.99,bottom=.22,top=.82,wspace=.4)
    allxy=[geometry(records[a['id']]['points'])[0,:,:2] for a in state['assignments']]
    pts=np.concatenate(allxy);low=pts.min(0)-.1;high=pts.max(0)+.1
    for k,a in enumerate(selected):
        ax=fig.add_subplot(gs[k]);xy=geometry(records[a['id']]['points'])[0,:,:2];closed=np.vstack([xy,xy[0]])
        ax.plot(*closed.T,c='#6e8792',lw=1)
        for p,feature in zip(xy,a['feature_ids']):
            if feature in ['node_004','node_005']:
                j=['node_004','node_005'].index(feature);ax.scatter(*p,c=[turn_colors[j]],s=27,zorder=4,marker=['o','^'][j])
        ax.set(xlim=(low[0],high[0]),ylim=(low[1],high[1]),xlabel='$x/h$');ax.set_aspect('equal');clean(ax)
        if k==0:ax.set_ylabel('$z/h$')
        ax.set_title(f'Original {IDS[a["worker"]]}',loc='left')
    ax=fig.add_subplot(gs[3]);arr=np.array([[f in a['feature_ids'] for f in ['node_004','node_005']] for a in state['assignments']])
    assert arr.sum(0).tolist()==[4,2] and state['minimum_support']==5
    for i,a in enumerate(state['assignments']):
        for j in range(2):
            ax.scatter(j,i,s=21,marker=['o','^'][j],facecolors=turn_colors[j] if arr[i,j] else 'white',edgecolors=turn_colors[j],lw=.7)
    ax.set(xticks=[0,1],xticklabels=['Turn A: 4 votes','Turn B: 2 votes'],yticks=range(10),
           yticklabels=[IDS[a['worker']] for a in state['assignments']],ylim=(9.7,-.8),xlim=(-.6,1.6))
    ax.set_title('All 10 people in Team 1',loc='left');ax.spines[:].set_visible(False);ax.tick_params(length=0,labelsize=7)
    fig.text(.36,.015,'Same colors denote matched identities; filled symbols indicate support. Threshold: ≥5 people.',ha='center',fontsize=7.7)
    save(fig,'bathroom_matching')
    AUDIT['bathroom_matching']={'trace':str(path.relative_to(ROOT)),'arm':'B','shown_originals':[a['id'] for a in selected],'votes':arr.sum(0).tolist()}


def same_room():
    d=pd.read_csv(ROOM/'PAIR_EFFECTS_BY_VERSION.csv.gz')
    d=d[(d.method_updated==METHOD)&(d.n==10)&(d.updated_direction=='C2→C3')&(d.version=='assisted_expanded_support')].copy()
    assert len(d)==19 and ((d.CB_a>0)&(d.CB_b>0)).sum()==18 and ((d.CB_a+d.CB_b)>0).all()
    cached={}
    for path in [ROOM/'RECOVERED_AUTOMATIC_ENDPOINTS.jsonl.gz', ROOM.parent/'endpoints/ENDPOINTS.jsonl.gz']:
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for r in map(json.loads,f):
                cached[r['team_key']]=r
    events=pd.read_csv(ROOM/'ASSISTED_CURRENT_EVENTS.csv.gz',low_memory=False)
    events=events[(events.method_updated==METHOD)&(events.n==10)&(events.updated_direction=='C2→C3')&events.B8L2_common6]
    candidates=[]
    for _,e in events.iterrows():
        if not all(e[f'team_key_{a}_{s}'] in cached for a in ['B','C'] for s in ['a','b']):
            continue
        if not all('B8L2' in cached[e[f'team_key_{a}_{s}']] for a in ['B','C'] for s in ['a','b']):
            continue
        good=True
        for side in ['a','b']:
            b,c=[cached[e[f'team_key_{a}_{side}']] for a in ['B','C']]
            good &= (b['reference_id']==c['reference_id']==e['reference_id_'+side])
            good &= np.isclose(c['B8L2']-b['B8L2'],e['B8L2_CB_'+side])
            good &= e['B8L2_CB_'+side]>0
        if good:candidates.append(e)
    assert candidates
    candidates=sorted(candidates,key=lambda e:(e.B8L2_CB_a+e.B8L2_CB_b,e.event_id))
    ev=candidates[len(candidates)//2]
    selected=d[d.pair_key==ev.pair_key].iloc[0]
    # Source geometries, reference identities and adopted scores must refer to the same endpoints.
    for side in ['a','b']:
        b,c=[cached[ev[f'team_key_{a}_{side}']] for a in ['B','C']]
        assert np.isclose(c['B8L2']-b['B8L2'],ev['B8L2_CB_'+side])
    D=set(ev.D_members.split('|'));Y=set(ev.Y_members.split('|'));Z=set(ev.Z_members.split('|'))
    assert len(D)==len(Y)==len(Z)==5 and not (D&Y or D&Z or Y&Z)
    photos=[]
    for side in ['a','b']:
        paths=list((ROOT/'data/mp3d_layout').glob(f'*/img/{ev["image_id_"+side]}.png'))
        assert paths, ev['image_id_'+side]
        photos.append(Image.open(paths[0]))
    fig=plt.figure(figsize=(7.2,4.0))
    for y,photo,side in zip([.62,.19],photos,['a','b']):
        ax=fig.add_axes([0,y,.31,.29]);panorama(ax,photo)
        ax.set_title(f'View {side.upper()} · {ev["image_"+side]}',loc='left',pad=2)
        ax=fig.add_axes([.36,y,.16,.29])
        for arm,color in [('B',COLORS[1]),('C',COLORS[2])]:
            key=ev[f'team_key_{arm}_{side}']
            xy=np.asarray(cached[key]['geometry']['footprint']);closed=np.vstack([xy,xy[0]])
            ax.plot(*closed.T,color=color,lw=1.1,ls='--' if arm=='B' else '-')
        ax.set_aspect('equal');clean(ax);ax.set(xlabel='$x/h$',ylabel='$z/h$');ax.tick_params(labelsize=7)
        ax.set_title(f'B → C: ΔQ {ev["B8L2_CB_"+side]:+.1f}',loc='left',fontsize=7.5)
    ax=fig.add_axes([.63,.30,.35,.57]);clean(ax)
    ax.axhline(0,c='#6a7880',lw=.7);ax.axvline(0,c='#6a7880',lw=.7)
    ax.scatter(d.CB_a,d.CB_b,s=24,c='#367b91',alpha=.8)
    ax.scatter([selected.CB_a],[selected.CB_b],s=65,facecolors='none',edgecolors='#b36d37',lw=1.3)
    ax.set(xlabel='View A: mean ΔQ (C − B)',ylabel='View B: mean ΔQ (C − B)')
    ax.set_title('19 pairs: mean replacement effects',loc='left')
    fig.text(.81,.15,'18/19 positive in both views',ha='center',fontsize=7.6)
    fig.legend(handles=[Line2D([],[],color=COLORS[1],ls='--',label='B = D + Y'),Line2D([],[],color=COLORS[2],label='C = D + Z')],
               loc='lower left',bbox_to_anchor=(.02,.035),ncol=2,frameon=False,fontsize=8)
    fig.text(.5,.005,'D: 5 retained people. Y / Z: 5 exchanged people. Each person supplied a separate original at each view.',ha='center',fontsize=8)
    save(fig,'same_room_transfer')
    AUDIT['same_room_transfer']={'selected_pair':selected.pair_key,'selected_event':ev.event_id,'selection':'median mean effect among positive-in-both-view events with all four adopted B/C endpoint geometries and matching reference/score identities','candidate_events':len(candidates),'case_effects':[ev.B8L2_CB_a,ev.B8L2_CB_b],'pairs':d[['pair_key','CB_a','CB_b']].to_dict('records'),'support':'318/322 six-endpoint-scoreable events; assisted expanded support'}


def fireplace_compact():
    base=SUPPORT/'Dot交付审查_20261106/Paper_Figures_4_5_6_10_CURRENT_ONLY_20261106/02_Figure6_latest'
    src=json.loads((base/'inputs/fig6_geometry_inputs.json').read_text(encoding='utf-8'))
    floors=[geometry(c['points'])[0,:,:2] for c in src['cases']]
    pts=np.concatenate(floors);low=pts.min(0)-.15;high=pts.max(0)+.15
    fig=plt.figure(figsize=(7.2,4.1))
    ax=fig.add_axes([0,.52,.35,.40]);panorama(ax,Image.open(base/'inputs'/src['image']))
    ax.set_title('(a) Complete panorama',loc='left',pad=3)
    ax=fig.add_axes([0,.05,.35,.43]);ax.imshow(Image.open(base/'output/verified_gt_views/GT_main.png'));ax.axis('off')
    ax.set_title('(b) GT-based context scene',loc='left',pad=0)
    for k,(x,label,color) in enumerate([(.405,'A29 · 4 corners','#168c87'),(.72,'A59 · 8 corners','#df732f')],1):
        fig.text(x+.12,.95,f'({"c" if k==1 else "d"}) {label}',ha='center',fontsize=8.5)
        ax=fig.add_axes([x,.56,.255,.33]);ref=np.vstack([floors[0],floors[0][0]]);xy=np.vstack([floors[k],floors[k][0]])
        ax.plot(*ref.T,c='#68737c',ls='--',lw=.9);ax.plot(*xy.T,c=color,lw=1.2)
        ax.scatter([0],[0],marker='+',s=16,c='#424d54')
        ax.set(xlim=(low[0],high[0]),ylim=(low[1],high[1]),xlabel='$x/h$',ylabel='$z/h$');ax.set_aspect('equal');clean(ax)
        ax=fig.add_axes([x-.035,.055,.31,.40]);ax.imshow(Image.open(base/f'output/renders/Fig6_{src["cases"][k]["label"]}_complete_walls.png'));ax.axis('off')
    fig.legend(handles=[Line2D([],[],c='#68737c',ls='--',label='GT in BEV'),Line2D([],[],c='#168c87',label='A29 original'),Line2D([],[],c='#df732f',label='A59 original')],loc='lower center',ncol=3,frameon=False,fontsize=8,bbox_to_anchor=(.5,-.02))
    save(fig,'individual_fireplace')
    AUDIT['individual_fireplace']={'source':str(base.relative_to(ROOT)),'change':'recomposition of original full panorama, unchanged accepted Blender renders and original-coordinate BEVs','model_geometry_changed':False}


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    funcs=[height_control,study_design,geometry_consensus,class_annotations,mixture_effects,member_distributions,image_changes,doorway_results,matching_evidence,same_room,fireplace_compact]
    for f in funcs:
        f();print(f.__name__+' OK',flush=True)
    (SUPPORT/'新增图表来源核对_20261107.json').write_text(json.dumps(AUDIT,ensure_ascii=False,indent=2),encoding='utf-8')
