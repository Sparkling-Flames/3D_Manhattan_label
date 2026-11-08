"""Render the supplied 66-config archive without rescoring or editing the paper."""
from pathlib import Path
import io
import json
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.lines import Line2D
from matplotlib.backends.backend_pdf import PdfPages

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('C:/Users/ASUS/Downloads/B8L2_3DIoU_8组几何对照_数据与代码.zip')
OUT = ROOT / 'docs/thesis_main/论文写作工作资料/受控几何验证图_20261107'
BLUE, ORANGE, GRAY = '#267788', '#c16a32', '#7b858c'
SETTINGS = [
 ('C1', 'Uniform ceiling-height shifts', 'Relative height increase', ['Uniform rise'], .2),
 ('C2', 'Opposite height shifts with unchanged mean', 'Relative height amplitude', ['Balanced tilt'], .2),
 ('C3', 'Equal vertex-mean height, different profiles', 'Single-corner relative height increase', ['One raised corner', 'Uniform rise with equal vertex mean'], .4),
 ('C4', 'Identical geometry with different vertex counts', 'Number of annotated vertices', ['Same geometry'], 12),
 ('C5', 'Equal overlap under shear and translation', 'Matched parameter s', ['Shear: x\' = x + s z', 'Translation: x\' = x + s m'], .3),
 ('C6', 'Equal displacement of near and far walls', 'Outward wall displacement (m)', ['Near wall (0.8 m from camera)', 'Far wall (7.2 m from camera)'], .8),
 ('C7', 'Omission of a narrow alcove', 'Omitted alcove depth (m)', ['Square approximation'], .6),
 ('C8', 'Non-orthogonal reference: scope diagnostic', 'Reference shear parameter', ['Exact reference copy', 'Orthogonal approximation'], .3),
]


def project(g):
    f = np.array(g['floor_xz_m']); h = np.array(g['wall_heights_m'])
    floor = np.column_stack((.82*f[:, 0]+.60*f[:, 1], .35*f[:, 0]-.48*f[:, 1]))
    return floor, floor+np.column_stack((np.zeros(len(h)), h))


def draw_geometry(ax, g, three_d, limits):
    r, c = g['reference'], g['candidate']
    if three_d:
        rb, rt = project(r); cb, ct = project(c)
        ax.add_patch(Polygon(cb, facecolor='#eef2f3', edgecolor=GRAY, lw=.6))
        # A non-planar four-corner top has no uniquely defined interior surface.
        if np.ptp(c['wall_heights_m']) == 0 or g['case'] in ['C2', 'C4']:
            ax.add_patch(Polygon(ct, facecolor=BLUE, alpha=.12, edgecolor='none'))
        ax.plot(*np.vstack([rt, rt[0]]).T, color=GRAY, ls='--', lw=.8)
        if len(rt) == len(ct) and np.allclose(rb, cb):
            for i in range(len(ct)):
                if ct[i, 1] < rt[i, 1]-1e-8:
                    ax.plot(*np.vstack([ct[i], rt[i]]).T, color=GRAY, ls='--', lw=.8)
        for lo, hi in zip(cb, ct):
            ax.plot(*np.vstack([lo, hi]).T, color=BLUE, lw=.8)
        ax.plot(*np.vstack([ct, ct[0]]).T, color=BLUE, lw=1.1)
        ax.scatter(*ct.T, s=10, color=BLUE, zorder=5)
        ax.set_axis_off()
    else:
        r = np.array(r['floor_xz_m']); c = np.array(c['floor_xz_m'])
        ax.fill(*c.T, color=BLUE, alpha=.10)
        ax.plot(*np.vstack([r, r[0]]).T, color=GRAY, ls='--', lw=1.1)
        ax.plot(*np.vstack([c, c[0]]).T, color=BLUE, lw=1.1)
        ax.scatter([0], [0], marker='+', color='#333333', s=24, zorder=5)
        ax.set_xlabel('x (m)'); ax.set_ylabel('z (m)')
        ax.grid(alpha=.15, lw=.4)
        ax.spines[['top','right']].set_visible(False)
    ax.set_xlim(limits[0]); ax.set_ylim(limits[1]); ax.set_aspect('equal')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SOURCE) as z:
        frame = pd.read_csv(io.BytesIO(z.read('q_iou_eight_cases/results_all.csv')))
        geoms = json.loads(z.read('q_iou_eight_cases/geometries.json'))
    lookup = {(g['case'], g['variant'], g['amount']): g for g in geoms}
    assert len(frame) == len(lookup) == 66
    assert not frame.duplicated(['case','variant','amount']).any()
    for row in frame.itertuples():
        g = lookup[(row.case, row.variant, row.amount)]
        assert len(g['candidate']['floor_xz_m']) == row.candidate_nodes
        assert np.isfinite([row.Q, row.prism_iou100]).all()
        assert np.isclose(np.mean(g['candidate']['wall_heights_m']), row.candidate_mean_corner_height_m)
    c4 = frame[frame.case == 'C4']
    assert np.ptp(c4.Q) < 1e-8 and c4.candidate_nodes.tolist() == [4, 5, 8, 16]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'axes.titlesize':9,
                         'axes.labelsize':8,'xtick.labelsize':7,'ytick.labelsize':7,'pdf.fonttype':42})
    with PdfPages(OUT/'controlled_geometry.pdf') as book:
        for cid, title, xlabel, labels, amount in SETTINGS:
            sub = frame[frame.case == cid]; variants = sub.variant.unique()
            fig = plt.figure(figsize=(7.2, 8.0 if cid == 'C5' else 6.3))
            fig.suptitle(f'{cid}  {title}', fontsize=12, y=.985)
            top = fig.add_gridspec(1,2,left=.09,right=.97,bottom=.61 if cid=='C5' else .56,top=.87,wspace=.25)
            selected = []
            if len(variants) == 2:
                selected = [(v, amount, labels[i]) for i,v in enumerate(variants)]
            else:
                low = 0 if cid != 'C7' else .1
                selected = [(variants[0], low, 'Reference' if cid in ['C1','C2'] else ('4 vertices' if cid=='C4' else 'Alcove depth: 0.1 m')),
                            (variants[0], amount, '16 vertices' if cid=='C4' else (f'Alcove depth: {amount} m' if cid=='C7' else f'Height amplitude: {amount:.0%}'))]
            gs = [lookup[(cid,v,a)] for v,a,_ in selected]
            coords = []
            for g in gs:
                for typ in ['reference','candidate']:
                    coords.extend(project(g[typ]) if cid in ['C1','C2','C3','C4'] else [np.array(g[typ]['floor_xz_m'])])
            pts=np.vstack(coords); low=pts.min(axis=0); high=pts.max(axis=0); pad=.10*(high-low)
            limits=((low[0]-pad[0],high[0]+pad[0]),(low[1]-pad[1],high[1]+pad[1]))
            for i, ((v,a,label),g) in enumerate(zip(selected,gs)):
                ax=fig.add_subplot(top[0,i]); draw_geometry(ax,g,cid in ['C1','C2','C3','C4'],limits)
                row=sub[(sub.variant==v)&(sub.amount==a)].iloc[0]
                ax.set_title(f'({chr(97+i)}) {label}',pad=5)
                fig.text(.305 if i==0 else .755, .55 if cid=='C5' else .49,
                        f'Q {row.Q:.2f}   |   Prism IoU {row.prism_iou100:.2f}',ha='center',fontsize=8)
            fig.legend(handles=[Line2D([],[],color=GRAY,ls='--',label='Reference geometry'),
                                Line2D([],[],color=BLUE,label='Candidate geometry')],
                       loc='upper center',bbox_to_anchor=(.5,.955),ncol=2,frameon=False)
            bottom=fig.add_gridspec(1,len(variants),left=.09,right=.97,bottom=.35 if cid=='C5' else .19,top=.46 if cid=='C5' else .425,wspace=.28)
            for i,v in enumerate(variants):
                t=sub[sub.variant==v].sort_values('amount'); ax=fig.add_subplot(bottom[0,i])
                x=t.candidate_nodes if cid=='C4' else t.amount
                ax.plot(x,t.Q,'o-',c=BLUE,lw=1.2,ms=3,label='Q')
                ax.plot(x,t.prism_iou100,'s--',c=ORANGE,lw=1.2,ms=3,label='Vertex-mean prism IoU × 100')
                if cid=='C2':
                    ax.plot(x,t.actual_planar_volume_iou100,'^:',c='#57934d',lw=1.2,ms=3,label='Actual planar-volume IoU × 100')
                if cid=='C4':
                    ax.plot(x,t.weighted_prism_iou100,':',c='#57934d',lw=1.5,label='Perimeter-mean prism IoU × 100')
                ax.set(xlabel=xlabel,ylabel='Index value',ylim=(0,104))
                if cid=='C7':
                    ax.set_ylim(95,100.3)
                    ax.set_ylabel('Index value (95–100 detail)')
                ax.set_title(f'({chr(99+i)}) {labels[i]}',pad=6)
                ax.spines[['top','right']].set_visible(False); ax.grid(alpha=.16,lw=.4)
                if cid=='C4': ax.set_xticks([4,5,8,16])
                if i==0: handles,names=ax.get_legend_handles_labels()
            fig.legend(handles,names,loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,frameon=False,fontsize=7)
            if cid=='C5':
                detail=fig.add_gridspec(1,2,left=.09,right=.97,bottom=.16,top=.255,wspace=.28)
                for i,(col,lab) in enumerate([('Sb_deg','Boundary error (deg)'),('Ddir_deg','Direction residual (deg)')]):
                    ax=fig.add_subplot(detail[0,i])
                    for j,v in enumerate(variants):
                        t=sub[sub.variant==v]; ax.plot(t.amount,t[col],['o-','s--'][j],ms=2,lw=1,c=[BLUE,ORANGE][j],label=['Shear','Translation'][j])
                    ax.set(xlabel='Matched parameter s',ylabel=lab); ax.spines[['top','right']].set_visible(False)
                    ax.legend(frameon=False,fontsize=6,loc='upper left'); ax.grid(alpha=.15)
            fig.text(.5,.018,'Dots show all supplied configurations; lines connect observations. Q and IoU are distinct indices.',ha='center',fontsize=6.5,color='#56616b')
            for ext in ['pdf','svg','png']: fig.savefig(OUT/f'{cid}.{ext}',dpi=220)
            book.savefig(fig); plt.close(fig)
    html='<!doctype html><meta charset="utf-8"><title>受控几何验证图</title><style>body{max-width:1100px;margin:30px auto;font:17px sans-serif;color:#243746}img{width:100%;border:1px solid #ddd;margin:12px 0}a{color:#267788}</style><h1>八组受控几何验证图</h1><p>使用提供包内66个配置；未修改论文正文。虚线为参考，蓝色为候选；曲线包含全部预设扰动。</p><a href="controlled_geometry.pdf">下载8页PDF</a>'
    for cid,title,*_ in SETTINGS: html+=f'<h2>{cid} {title}</h2><a href="{cid}.pdf">矢量PDF</a> · <a href="{cid}.svg">SVG</a><img src="{cid}.png">'
    (OUT/'index.html').write_text(html,encoding='utf-8')
    (OUT/'CHECKS.json').write_text(json.dumps({'source':str(SOURCE),'configurations':66,'geometry_score_key_matches':66,'C4_Q_range':float(np.ptp(c4.Q)),'paper_modified':False},indent=2),encoding='utf-8')
    print('Eight figures generated; 66 geometry/score identities checked.')


if __name__=='__main__': main()
