"""Export publication figures and target review cards from accepted saved tables.

No fitting, fusion, reference changes, or adoption of difficulty labels.
"""
from pathlib import Path
import html
import gzip
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
REL = ROOT / 'research/data/releases/v2.1'
SRC = ROOT / 'research/workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030'
QT = SRC.parent / 'common_support/v21_q_qt_common_support_20261030/results'
OUT = REL / 'paper_evidence_20261030'
INDEX = []
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42})


def read(path):
    return pd.read_csv(path, low_memory=False)


def one(frame):
    assert len(frame) == 1, f'Expected one row, got {len(frame)}'
    return frame.iloc[0]


def save(fig, name, title, caption, sources, selection, data):
    fig.suptitle(title, fontsize=13)
    fig.canvas.draw()
    texts = [t.get_text() for t in fig.findobj(matplotlib.text.Text)]
    assert not any('\u4e00' <= c <= '\u9fff' for t in texts for c in t), name
    for ext in ('png', 'svg', 'pdf'):
        fig.savefig(OUT / f'{name}.{ext}', dpi=300, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    data.to_csv(OUT / f'{name}_DATA.csv', index=False)
    INDEX.append(dict(figure=name, title=title, caption=caption,
                      source_tables=';'.join(str(p.relative_to(ROOT)).replace('\\', '/') for p in sources),
                      selection=selection, data=f'{name}_DATA.csv'))


def figures():
    hp = SRC / 'stage01_half_team/IMAGES_METRIC_SPECIFIC_SUPPORT.csv.gz'
    half = read(hp); h = half[half.n.eq(14)]
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.5), layout='constrained')
    for d, label, marker in [('简单', 'Easy', 'o'), ('中等', 'Moderate', 's'), ('困难', 'Difficult', '^')]:
        z = h[h.difficulty.eq(d)].dropna(subset=['B8L2__within', 'B8L2__cross_symmetric'])
        ax[0].scatter(z.B8L2__within, z.B8L2__cross_symmetric, marker=marker, label=f'{label}: {len(z)} images', s=28)
    lim = h[['B8L2__within', 'B8L2__cross_symmetric']].max().max() * 1.06
    ax[0].plot([0, lim], [0, lim], 'k--', lw=1)
    ax[0].set(xlabel='Within-class change |B - A| (Q points)', ylabel='Symmetric between-class change (Q points)', title='(a) Change magnitude: 62/83 above equality')
    ax[0].legend(fontsize=8)
    q = h.CB.dropna().sort_values()
    ax[1].bar(np.arange(len(q)), q, color='#287b8e', edgecolor='black', linewidth=.2)
    ax[1].axhline(0, color='black', lw=.7)
    ax[1].set(xlabel='Images ranked by C - B (83 images)', ylabel='Quality difference C - B (Q points)', title='(b) Quality direction: 76/83 positive')
    assert len(q) == 83 and (q > 0).sum() == 76
    save(fig, 'F01_half_team', 'Quality changes under within-class and between-class replacement\nof half the team',
         'Ordinary Manual, TARGET_DSTRUCT K3 working labels, n=14 and m=7. A is the original team, B the within-class replacement, and C the between-class replacement. Symmetric magnitude=(|C-A|+|C-B|)/2. Saved background, block, pool and image aggregation is retained. GA/GS use 185 jointly scoreable ABC events; C-B uses 187 BC events, both covering 83 of 85 registered images. Missing scores are excluded, never replaced by zero.', [hp], 'n=14; metric-specific nonmissing support', h)

    p = SRC / 'stage01_half_team/MATCHED_BACKGROUND_CONTEXT_SUMMARY.csv'; d = read(p)
    z = d[d.scope.eq('D14_subset_D20') & d.metric.isin(['gap_A', 'gap_sym', 'CB'])]
    assert len(z) == 3
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4), layout='constrained')
    for ax, metric, label in zip(axes, ['gap_A', 'gap_sym', 'CB'], ['GA: direct excess magnitude', 'GS: symmetric excess magnitude', 'C - B: quality direction']):
        r = one(z[z.metric.eq(metric)])
        ax.plot([14, 20], [r.mean14, r.mean20], 'o-', color='#287b8e'); ax.axhline(0, color='black', lw=.7)
        ax.set(xticks=[14, 20], xlabel='Team size n (m = 7 fixed)', ylabel='Quality contrast (Q points)', title=f'{label}\n{int(r.valid_images)} common images')
    save(fig, 'F02_background', 'Quality contrasts at two team sizes\nwith a fixed seven-member replacement block',
         'TARGET K3 working labels. Exact X/Y/Z blocks are fixed and the 14-person background is nested in the 20-person background. Saved paired-context weights are used. There are 56 registered links across 45 images; metric-specific valid support is shown. Team size, background, voting threshold and replacement fraction change together.', [p], 'nested background D; gap_A, gap_sym, CB; source paired weights', z)

    p = SRC / 'stage01_half_team/DIFFICULTY_METRIC_SUMMARY.csv'; d = read(p)
    metrics = ['B8L2__delta_CB', 'fusion_turn_n__delta_CB', 'ref_node_recall_5__delta_CB']
    z = d[d.n.eq(14) & d.metric.isin(metrics)]
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.4), layout='constrained')
    for ax, metric, ylabel in zip(axes, metrics, ['Quality difference C - B (Q points)', 'Turn-count difference C - B (turns)', 'Reference-node recall difference C - B']):
        rows = [one(z[z.metric.eq(metric) & z.difficulty.eq(dif)]) for dif in ['简单', '中等', '困难']]
        ax.bar(range(3), [r['mean'] for r in rows], color=['#387b9b', '#b18c40', '#8b526b'], edgecolor='black', hatch='/')
        ax.axhline(0, color='black', lw=.7); ax.set(xticks=range(3), xticklabels=[f'{label}\nn={int(r.valid_images)}' for label,r in zip(['Easy','Moderate','Difficult'],rows)], ylabel=ylabel, xlabel='Image difficulty')
    save(fig, 'F03_difficulty', 'Structural and quality changes under half-team replacement\nacross image difficulty levels',
         'TARGET K3, 14/7. Bars are image-equal means from saved metric-specific summaries, not confidence intervals. Among nine scoreable difficult images, turns increase in 9/9 and Q in 7/9; structural retention and quality are distinct outcomes. Reference-node recall uses the source 5-degree matching definition.', [p], 'n=14; three difficulty levels; metric-specific support', z)

    p = SRC / 'stage02_same_room/abc/PAIR_METRICS.csv.gz'; d = read(p)
    z = d[d.final_method.eq('TARGET_DSTRUCT_K3') & d.analysis_scope.eq('ordinary_comparable') & d.condition.eq('manual') & d.metric.eq('B8L2') & d.role_direction.eq('2→3') & d.n.isin([10,14]) & (d.m*2).eq(d.n)]
    # The table contains several aggregation levels; only exact n/m direction rows belong here.
    z = z[z.level.eq('direction_nm')]
    assert not z.duplicated(['n','pair_key']).any(), z.level.unique()
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), layout='constrained')
    for row,n in enumerate([10,14]):
        s=z[z.n.eq(n)]; assert len(s)==(19 if n==10 else 2)
        for col, metric in enumerate(['GS','CB']):
            ax=axes[row,col]; ax.scatter(s[metric+'_a'], s[metric+'_b'], marker='o' if n==10 else '^', s=45, color='#287b8e')
            ax.axhline(0,color='black',lw=.7);ax.axvline(0,color='black',lw=.7)
            low=min(0,s[[metric+'_a',metric+'_b']].min().min());high=s[[metric+'_a',metric+'_b']].max().max();pad=(high-low)*.08
            ax.set_xlim(low-pad,high+pad);ax.set_ylim(low-pad,high+pad)
            ax.set(xlabel=f'View 1 {metric} (Q points)',ylabel=f'View 2 {metric} (Q points)',title=f'n={n}, m={n//2}: {len(s)} room-view pairs')
    save(fig,'F04_same_room_replacement','Cross-view consistency of quality changes\nunder half-team replacement within the same room',
         'Ordinary comparable Manual, TARGET K3 working direction 2 to 3. Each point is a physical pair of room views. GS denotes symmetric excess between-class magnitude; CB denotes C-B. The 10/5 subset has 268 physical events, 237 with all six endpoints scoreable, across 19 pairs and 7 buildings. The 14/7 subset has 10 events, 6 jointly scoreable, only 2 pairs and one fixed incoming seven-person block.',[p],'TARGET K3; ordinary comparable; Manual; B8L2; direction 2→3; n/m=10/5 or14/7',z)

    p=SRC/'stage02_same_room/prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv'; pp=SRC/'stage02_same_room/prediction/PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv'
    d=read(p); e=read(pp); scope='ordinary_no_relation_oos_pending'
    z=d[d.metric.eq('B8L2') & d.scenario.eq('v21_all') & d.scope.eq(scope) & d.method.isin(['source_mean','external_image_mean'])]
    zz=e[e.metric.eq('B8L2') & e.scenario.eq('v21_all') & e.scope.eq(scope) & e.budget.eq('single_direct') & e.stage.eq('single') & e.method.isin(['external_abs','public_source','public_external'])]
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,data,methods,labels,title in [(axes[0],z,['external_image_mean','source_mean'],['Outside-building\nimage mean','Same-room\nsource mean'],'(a) Image-mean prediction: 128 pairs'),(axes[1],zz,['external_abs','public_source','public_external'],['Personal\nhistory','Public\nsource mean','Public mean +\npersonal history'],'(b) Individual prediction: 1,793 answers')]:
        vals=[one(data[data.method.eq(m)]).mae for m in methods]
        ax.bar(range(len(vals)),vals,color='#387b9b',edgecolor='black',hatch='/');ax.set(xticks=range(len(vals)),xticklabels=labels,ylabel='Mean absolute error (Q points)',xlabel='Available prediction information',title=title)
        for i,v in enumerate(vals):ax.text(i,v+.15,f'{v:.3f}',ha='center')
        ax.set_ylim(0,max(vals)*1.2)
    save(fig,'F05_same_room_prediction','Prediction errors for annotation quality\nusing same-room and annotator-history information',
         'Current ordinary no-relation-pending scope: 65 images and 13 buildings. Image predictions use 128 direct pairs; individual predictions use the same 1,793 target answers (5,198 prediction rows). Panels have different prediction targets and should not be ranked against each other. Source-level image weighting is retained.',[p,pp],'v21_all; B8L2; ordinary_no_relation_oos_pending; person budget single_direct, stage single',pd.concat([z.assign(prediction_target='image'),zz.assign(prediction_target='individual')],ignore_index=True))

    files=[SRC/'stage03_speed_difficulty'/f for f in ['V21_FIXED_V2_SAME_PEOPLE_SUMMARY.csv','CURRENT_SAME_PEOPLE_SUMMARY.csv','CURRENT_ON_V2_FINE_PAIR_SAME_PEOPLE_SUMMARY.csv']]
    selected=[]
    for i,p in enumerate(files):
        d=read(p);method='V3_JOINT_QT_COARSE' if i==0 else 'TARGET_DSTRUCT_K3'
        selected.append(d[d.method.eq(method)&d.condition.eq('manual')&d.origin.eq('new')&d.metric.isin(['turn_n','short_turn_edges'])].assign(support=['Frozen v2 pairs','Current pairs','Exact support overlap'][i]))
    z=pd.concat(selected);assert sorted(z.valid_pair_rows.unique())==[52,63,105]
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,metric,label in zip(axes,['turn_n','short_turn_edges'],['Turn-count advantage (turns)','Short-edge advantage (edges)']):
        s=z[z.metric.eq(metric)];ax.bar(range(3),s['mean'],color='#387b9b',edgecolor='black',hatch='/');ax.axhline(0,color='black',lw=.7)
        ax.set(xticks=range(3),xticklabels=[f'{r.support}\nn={r.valid_pair_rows}' for r in s.itertuples()],ylabel=f'Hard-minus-easy change in\nslow-minus-fast {label.lower()}',xlabel='Matched people-pair support')
    save(fig,'F06_speed_difficulty','Changes in structural-expression differences between slower and faster\nannotators across difficulty levels',
         'Bars use the saved same-people-pair means of (slow-fast on difficult images) minus (slow-fast on easy images). Frozen v2 pairs are rescored on v2.1; current TARGET K3 and the exact old/current support overlap are separate designs. Matching uses outside-building history, not target-image Q. The overlap is not a replacement for the full current support.',files,'Manual; origin=new; frozen V3 versus current TARGET K3; turn_n/short_turn_edges',z)

    p=REL/'NATURAL_CONCLUSION_COMPARISON_INDEPENDENT_20261029.csv';d=read(p)
    z=d[d.version_support.eq('v21_combined')&d.group.eq('ordinary_N30')&d.interval.isin(['3_to_6','20_to_30'])].set_index('interval').loc[['3_to_6','20_to_30']].reset_index()
    fig,axes=plt.subplots(1,4,figsize=(13,4.3),layout='constrained')
    for ax,metric,label,scale in zip(axes,['Q_mean_delta','Q_p10_delta','Q_sd_ddof1_delta','actual_consensus_failure_rate_delta'],['Mean Q change\n(Q points)','P10 change\n(Q points)','SD change\n(Q points)','Fusion-failure rate change\n(percentage points)'],[1,1,1,100]):
        ax.bar(range(2),z[metric]*scale,color='#387b9b',edgecolor='black',hatch='/');ax.axhline(0,color='black',lw=.7);ax.set(xticks=range(2),xticklabels=['3 to 6','20 to 30'],xlabel='Team-size interval (people)',ylabel=label)
    save(fig,'F07_natural_size','Consensus quality and variability across team-size intervals\nunder natural annotation arrival',
         'Fixed 171 ordinary Manual images with at least 30 eligible annotators. Each bar is an image-equal change in a per-image statistic under natural random orderings. Mean, P10 and SD are conditional on scoreability; actual fusion failures are separately measured. These are interval contrasts, not a complete arrival curve or an optimized-team experiment.',[p],'v21_combined; ordinary_N30; 3_to_6 and20_to_30',z)

    p=QT/'COMMON_SUPPORT_SUMMARY.csv';d=read(p);z=d[d.panel.eq('all_sizes_3_to_13') & d.metric.isin(['delta_q','labor_ratio','loss_gt5'])]
    fig,axes=plt.subplots(1,3,figsize=(12,4.3),layout='constrained')
    for ax,metric,label,baseline in zip(axes,['delta_q','labor_ratio','loss_gt5'],['Q/T minus Q-only\n(Q points)','Recorded labor ratio\n(Q/T divided by Q-only)','Probability of Q loss > 5 points'],[0,1,0]):
        s=z[z.metric.eq(metric)].sort_values('n');assert len(s)==7
        ax.errorbar(s.n,s.value,yerr=np.array([s.value-s.boot_lo,s.boot_hi-s.value]),fmt='o-',capsize=3,color='#287b8e');ax.axhline(baseline,color='black',lw=.7);ax.set(xticks=s.n,xlabel='Selected team size n (people)',ylabel=label)
    save(fig,'F08_qt_selection','Quality and recorded labor of Q/T-selected teams relative to Q-only teams\non fixed candidate support',
         '126 common source-target contexts, 46 images, 9 buildings, fixed across n=3,4,5,6,7,9,13. Points and 95% empirical building-resampling intervals are copied from the accepted saved summaries (20,000 replicates), Contexts are equally weighted within target images, then images within buildings, then buildings. Labor ratios are aggregated on the log scale and exponentiated; they are not ratios of summed labor. Metric-specific scoreability is retained. At n=5, delta Q=0.218 and labor ratio=0.813. Q/T teams can be non-nested across sizes. This is not natural arrival.',[p],'panel=all_sizes_3_to_13; delta_q/labor_ratio/loss_gt5; saved value and bootstrap limits',z)


def review_cards():
    source = REL / 'difficulty_records.json'
    records = json.loads(source.read_text(encoding='utf8'))['records']
    by_image = {r['image']: r for r in records}
    pools = read(REL / 'admitted_space_extension/difficulty_evidence/POOL_EVIDENCE.csv')
    rows = []
    for r in pools.to_dict('records'):
        current = by_image[r['image']]
        grade = current['current_class']
        assert grade in {'简单', '中等', '困难'}, (r['image'], grade)
        rows.append(dict(image=r['image'], pool_id=r['pool_id'], target_id=r['target_id'], image_difficulty=grade,
                         source='difficulty_records.json', rule='用户明确：每图一个难度；不同目标分别评分', downstream_status='图片等级已沿用；受影响下游补算见image_difficulty_20261030'))
    mapping = pd.DataFrame(rows)
    assert len(mapping) == 31 and mapping.image.nunique() == 28
    assert mapping.groupby('image').image_difficulty.nunique().eq(1).all()
    mapping.to_csv(OUT / 'IMAGE_DIFFICULTY_MAPPING.csv', index=False, encoding='utf-8-sig')
    table = mapping[['image','image_difficulty']].drop_duplicates().to_html(index=False)
    (OUT / 'TARGET_REVIEW.html').write_text('<!doctype html><meta charset="utf-8"><title>图片难度已确认</title><style>body{font:18px sans-serif;max-width:1000px;margin:30px auto}td,th{padding:8px}</style><h1>已撤销重复的空间级难度审查</h1><p>按你的研究口径，每张图片只有一个难度。31池对应28张图片，均已找到现行难度，直接沿用；不需要重新提交任何判断。空间与参考仍分别评分。</p><p>wc2-26和uNb-88均已为困难，之前要求再评三个目标不必要。下表来自当前difficulty_records.json。受影响下游现已补算，详见 ../admitted_space_extension/image_difficulty_20261030/README.md；原图表保留冻结标签身份。</p>'+table, encoding='utf8')
    return dict(images=28, pools=31, missing_image_grades=0, repeated_target_review_withdrawn=True, downstream_recomputed=False)


def cases_and_tables():
    sys.path.insert(0,str(SRC/'scripts'))
    from render_half_figures import project_line
    base=SRC/'stage01_half_team'
    anchors=read(base/'CASE_ANCHOR_SELECTION.csv').set_index('image')
    events=read(base/'EVENTS_METRIC_SPECIFIC_SUPPORT.csv.gz').set_index('event_id')
    choices=['S9hNv5qa7GM-09','jh4fc5c5qoQ-04','B6ByNegPMKs-11','VFuaQ6m2Qom-04','pa4otMbVnkk-42','S9hNv5qa7GM-12']
    for k,im in enumerate(choices,1):
        eid=anchors.loc[im,'anchor_event'];e=events.loc[eid]
        poolpath=base/'case_inputs'/f'{e.pool_id}.json.gz'
        with gzip.open(poolpath,'rt',encoding='utf8') as f:pool=json.load(f)
        fig,axes=plt.subplots(1,2,figsize=(12,5.2),gridspec_kw={'width_ratios':[2,1]},layout='constrained')
        axes[0].imshow(Image.open(base/'originals'/f'{im}.png'),extent=(0,1024,512,0))
        for line in project_line(pool['reference']['points_1024x512']):axes[0].plot(line[:,0],line[:,1],color='black',lw=1.5)
        ref=np.asarray(pool['reference']['floor_xz_h']);closed=np.vstack([ref,ref[0]])
        axes[1].plot(*closed.T,color='black',lw=1.7,label='Reference')
        traces=[];sources=[base/'CASE_ANCHOR_SELECTION.csv',poolpath]
        for arm,color,style in zip('ABC',['#267caa','#a17630','#b74764'],['-','--',':']):
            p=base/'trace_endpoints'/f'{e[arm+"_team_key"]}.json.gz';sources.append(p)
            with gzip.open(p,'rt',encoding='utf8') as f:t=json.load(f)
            traces.append(dict(image=im,event_id=eid,arm=arm,team_key=e[arm+'_team_key'],Q=t['B8L2'],nodes=t['nodes'],status=t['score_status']))
            geom=t.get('geometry') or {}
            label=f'{arm}: Q={t["B8L2"]:.2f}' if t['B8L2'] is not None else f'{arm}: {t["score_status"]}'
            if t['score_status']=='complete_conditional':
                for line in project_line(geom['points']):axes[0].plot(line[:,0],line[:,1],color=color,ls=style,lw=1.2)
                floor=np.asarray(geom['footprint']);closed=np.vstack([floor,floor[0]])
                axes[1].plot(*closed.T,color=color,ls=style,marker='o',ms=3,label=label)
            else:
                centers=[g['center'] for g in t['full_state']['identity_groups'] if g['selected'] and g['center']]
                floor=[]
                for pair in centers:
                    pt=pair[1];az=pt[0]/1024*2*np.pi;radius=-1/np.tan((.5-pt[1]/512)*np.pi)
                    floor.append([-np.sin(az)*radius,np.cos(az)*radius]);axes[0].plot(*np.asarray(pair).T,'x',color=color)
                if floor:axes[1].plot(*np.asarray(floor).T,'x',color=color,label=label)
        axes[0].set(xlim=(0,1024),ylim=(512,0),xlabel='Panorama x (pixels)',ylabel='Panorama y (pixels)')
        axes[1].set_aspect('equal',adjustable='datalim');axes[1].set(xlabel='x / camera height',ylabel='z / camera height');axes[1].legend(fontsize=8)
        save(fig,f'S{k:02d}_case_{im}',f'Consensus geometry under half-team replacement\nfor {im} using TARGET K3 working labels',
             f'One saved 14/7 anchor event ({eid}). A: original team; B: within-class replacement; C: between-class replacement. Coordinates are normalized by camera height. Missing rings are represented only by selected nodes; connecting edges are never invented. This is an explanatory case, not an independent effect estimate. Image-level effects use all saved events, not only this anchor.',sources,'Original six explanatory anchors after complete 36-image diagnosis; source geometry unchanged',pd.DataFrame(traces))
    p=base/'DIFFICULTY_METRIC_SUMMARY.csv';d=read(p)
    z=d[d.n.eq(14)&d.metric.isin(['B8L2__delta_CB','D10__delta_CB','IoU3D100__delta_CB','fusion_turn_n__delta_CB','ref_node_recall_5__delta_CB','geometry_area_h2__delta_CB','height_mean_h__delta_CB'])].copy()
    z['difficulty']=z.difficulty.map({'简单':'Easy','中等':'Moderate','困难':'Difficult'})
    assert z.difficulty.notna().all()
    z.to_csv(OUT/'TABLE_S1_difficulty.csv',index=False)
    display=z[['difficulty','metric','valid_images','valid_buildings','mean','median','positive_images','negative_images','zero_images']].copy()
    display['metric']=display.metric.map({'B8L2__delta_CB':'Quality Q (points)','D10__delta_CB':'D10 score (points)','IoU3D100__delta_CB':'3D IoU (0-100 scale)','fusion_turn_n__delta_CB':'Turn count','ref_node_recall_5__delta_CB':'Reference-node recall (5 degrees)','geometry_area_h2__delta_CB':'Floor area / camera height squared','height_mean_h__delta_CB':'Mean height / camera height'})
    assert display.metric.notna().all()
    display.columns=['Difficulty','Outcome: C minus B','Valid images','Buildings','Mean','Median','Positive images','Negative images','Zero images']
    table='<h1>Structural and quality differences across image difficulty levels</h1><p>TARGET K3 working labels, 14/7, C minus B. Means are image-equal; valid support is metric-specific. Recalls are fractions. D10 retains its source definition.</p>'+display.to_html(index=False,float_format=lambda v:f'{v:.4f}')
    (OUT/'TABLES.html').write_text('<!doctype html><meta charset="utf-8"><title>v2.1 supplementary tables</title><style>body{font:16px sans-serif;margin:30px}td,th{padding:8px;text-align:left}table{border-collapse:collapse}</style>'+table,encoding='utf8')


def audit():
    modules = [
        ('质量与参考','quality_inventory.csv','quality_inventory.json','已更新','原主目标8154；其它231另列；原答不变'),
        ('原答与范围差异','descriptive_statistics/cohort_condition_summary.csv','descriptive_statistics/CHECKS.json','已更新','范围与同范围内结构分别解释'),
        ('人员画像与可靠性','personnel_descriptive/profiles.csv','personnel_descriptive/reliability.csv','已更新并合法复用','Q历史更新；scope及Semi任务裁决复用，不当新分类'),
        ('难度与几何机会','difficulty_computable_comparison/COMPARISONS.csv','difficulty_computable_comparison/CHECKS.json','已更新','三档与连续几何；31池目标级采用另列'),
        ('分类与成员敏感性','final_classification_downstream/README.md','final_classification_downstream/TARGET_MAIN_EVENTS.csv.gz','工作结果已接续','最终选型未定；类别改变须按依赖更新'),
        ('有限配比与格内分布','simulated_population_evidence/README.md','simulated_population_evidence/INTEGRATION_CHECKS.json','已接续','有限面板全集不等于全库所有可能团队'),
        ('半队与机制','full_chain_downstream_20261030/README.md','../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage01_half_team/MAIN_CHECKED_SUMMARY.csv','已接续并复核','197事件；36图诊断；墙体语义局部待人工'),
        ('背景与扩大替换','simulated_population_evidence/exchange','../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage01_half_team/MATCHED_BACKGROUND_CONTEXT_SUMMARY.csv','已接续','固定A、固定XYZ与嵌套D分别解释'),
        ('自然人数与失败','natural_results/NATURAL_CURVES.csv.gz','NATURAL_CONCLUSION_COMPARISON_INDEPENDENT_20261029.csv','已更新','固定支持均值低尾波动失败分别保留'),
        ('旧角色进入策略','current_policy_results/README.md','current_policy_results','已更新','原图和新增26图分开；不是新分类大池策略'),
        ('融合方法与评分敏感性','fusion_common_panel/COMMON_SCENE_SUMMARY_OLD_V21.csv','d10_formation_sensitivity/ABC_COMMON_PHYSICAL_SUMMARY.csv','固定设计更新','算法不变可复用几何；评分与形成链分开'),
        ('同房配比与ABC','same_room_oppjoint_fixed_panels/README.md','../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage02_same_room/abc/PAIR_METRICS.csv.gz','已接续并复核','旧队合法子集与重新选队不同；10/5和14/7分开'),
        ('同房预测','full_chain_downstream_20261030/README.md','../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage02_same_room/prediction/DIRECT_MEAN_SUMMARY_BY_SCOPE.csv','已接续并复核','公共均值、个人稳定水平、残差分开'),
        ('快慢与难度','full_chain_downstream_20261030/README.md','../../../workers/personnel_full_chain_v21_20261030/HOHONET_v21_full_chain_20261030/stage03_speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv','已接续并复核','63/105/52对分别报告，完整当前支持弱效应'),
        ('同用途','room_type_similarity/COMPARISON_OLD_NEW_SUPPORT.csv','room_type_similarity/INDEPENDENT_CHECKS.json','当前分析已更新，历史复现局部未闭合','52条旧内折预测；稳定Q增益不再采用'),
        ('选队停止与成本','full_chain_downstream_20261030/README.md','../../../workers/personnel_full_chain_v21_20261030/common_support/v21_q_qt_common_support_20261030/results/COMMON_SUPPORT_SUMMARY.csv','已接续并复核','已有历史与冷启动分开，2.115为项目劳动比'),
        ('其它合法空间31池','admitted_space_extension/README.md','admitted_space_extension/image_difficulty_20261030/INPUT_CHECKS.json','图片等级已沿用，受影响下游已补算','31池30目标28图；无需重复评级；分类候选未定'),
        ('OOS与门洞','../../../difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/oos_statistics_20261024/README.md','NATURAL_CONCLUSION_COMPARISON_INDEPENDENT_20261029.csv','既有证据复用；新双版本待用户','门洞分空间双版本与GT讨论不提前认定完成'),
    ]
    rows=[]
    for module,entry,evidence,status,boundary in modules:
        paths=[(REL/p).resolve() for p in [entry,evidence]]
        assert all(p.exists() for p in paths), paths
        rows.append(dict(module=module,status=status,entry=str(paths[0].relative_to(ROOT)).replace('\\','/'),evidence=str(paths[1].relative_to(ROOT)).replace('\\','/'),boundary=boundary,
                         verification='本轮来源/支持定向检查；既有计算核验见对应CHECKS及local_review；非全量重放'))
    pd.DataFrame(rows).to_csv(OUT/'COMPLETENESS.csv',index=False,encoding='utf-8-sig')
    cross=read(SRC/'stage06_synthesis/V2_TO_V21_CROSSWALK.csv').fillna('')
    checks=[]
    for row in cross.to_dict('records'):
        for column in ['当前证据源表_交付根目录相对路径','原结论来源_交付根目录相对路径','保留成果源表_冻结仓库相对路径']:
            for part in row[column].split(';'):
                if not part.strip():continue
                base=ROOT if column.startswith('保留') else SRC
                path=base/part.strip()
                checks.append(dict(item=row['条目ID'],question=row['研究问题'],source_field=column,source=part,exists=path.exists()))
    pd.DataFrame(checks).to_csv(OUT/'CROSSWALK_SOURCE_CHECKS.csv',index=False,encoding='utf-8-sig')
    return dict(modules=len(rows),crosswalk_items=len(cross),references=len(checks),unresolved_references=[r for r in checks if not r['exists']])


def main():
    INDEX.clear()
    OUT.mkdir(exist_ok=True)
    completeness=audit()
    figures()
    cases_and_tables()
    # The imported source case renderer changes rcParams; keep it after publication export.
    review=review_cards()
    pd.DataFrame(INDEX).to_csv(OUT/'FIGURE_INDEX.csv',index=False)
    parts=['<!doctype html><meta charset="utf-8"><title>v2.1 publication figures</title><style>body{font:16px sans-serif;max-width:1300px;margin:30px auto}img{width:100%}section{margin-bottom:50px}p{line-height:1.5}</style><h1>v2.1 publication figures</h1>']
    for item in INDEX:
        name=item['figure'];parts.append(f'<section><h2>{name}: {item["title"].replace(chr(10)," ")}</h2><img src="{name}.png"><p>{item["caption"]}</p><p><a href="{name}.pdf">PDF</a> · <a href="{name}.svg">SVG</a> · <a href="{name}_DATA.csv">Data</a></p></section>')
    (OUT/'FIGURES.html').write_text(''.join(parts),encoding='utf8')
    checks=dict(completeness=completeness,figures=len(INDEX),formats=['PDF','SVG','300 dpi PNG'],figure_text_english=True,source_filters_asserted=True,review=review,new_fusion=0,classification_finalized=False,visual_review='pending')
    (OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(checks,ensure_ascii=False))


if __name__=='__main__':
    main()
