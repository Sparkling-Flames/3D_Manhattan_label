"""Readable, source-separated comparison of every completed Manual45 panel.

This summarizes a finite, fully enumerated conditional member space. It does
not turn mixture variance into exchange effects or estimated labor savings.
"""
from pathlib import Path
import gzip, hashlib, json, os
import numpy as np
import pandas as pd

W=Path(__file__).resolve().parents[2]
C=W/'composition'; R=C/'primary_manual45'; O=C/'primary_mixture_results'
O.mkdir(exist_ok=True)

def save(p,d):
    data=d.to_csv(index=False).encode('utf-8-sig')
    if p.suffix=='.gz': data=gzip.compress(data,compresslevel=6,mtime=0)
    t=p.with_name(p.name+'.writing')
    with t.open('wb') as f: f.write(data);f.flush();os.fsync(f.fileno())
    t.replace(p)

def md(d):
    return '\n'.join(['| '+' | '.join(d.columns)+' |',
        '| '+' | '.join(['---']*len(d.columns))+' |']+
        ['| '+' | '.join(map(str,r))+' |' for r in d.itertuples(index=False,name=None)])

receipt=json.loads((R/'COMPLETE.json').read_text())
methods=receipt['methods']; assert len(methods)==45
summary=pd.read_csv(R/'ALL_METHOD_COMPARISON.csv',low_memory=False)
overall=summary[summary.summary_axis.eq('all')].copy()
key_metrics=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges',
    'fusion_redundancy_n','geometry_area_h2','height_mean_h','failure',
    'recorded_time_total_seconds']
save(O/'ALL45_ALL_METRICS_BOTH_SUPPORTS.csv',overall)
save(O/'ALL45_COMMON_SUPPORT_KEY_METRICS.csv',overall[
    overall.support.eq('shared_known')&overall.metric.isin(key_metrics)])
save(O/'BY_SIZE_DIFFICULTY_AND_SOURCE.csv.gz',summary[
    summary.summary_axis.isin(['n','difficulty','source_domain','geometric_challenge'])])

matrices={}
for support in ['method_known','shared_known']:
    d=overall[overall.support.eq(support)&overall.metric.isin(key_metrics)].copy()
    d['metric_with_source']=d.metric.where(d.time_source.eq('not_time'),
        d.metric+'__'+d.time_source)
    mat=d.pivot(index='method',columns='metric_with_source',values='between_share').reset_index()
    save(O/f'ALL45_{support.upper()}_METRIC_MATRIX.csv',mat)
    matrices[support]=mat

# The exact parent mappings were independently derived from the frozen labels.
# Ward cuts on one family tree are genuinely nested, as are V3 coarse/fine.
hpath=W/'analysis/global_parent_links/METHOD_HIERARCHY_ALL_LOBO.csv'
hierarchy=pd.read_csv(hpath)
relevant=hierarchy[hierarchy.child_method.isin(methods)&hierarchy.parent_method.isin(methods)]
assert relevant.nested.all()
save(O/'EXACT_FOLD_HIERARCHY.csv',relevant)
pairs=relevant[['child_method','parent_method']].drop_duplicates()
increments=[]
shared=overall[overall.support.eq('shared_known')].copy()
for child,parent in pairs.itertuples(index=False,name=None):
    a=shared[shared.method.eq(child)];b=shared[shared.method.eq(parent)]
    z=a.merge(b,on=['metric','time_source','condition','support'],suffixes=('_child','_parent'))
    assert (z.valid_team_links_child==z.valid_team_links_parent).all()
    for r in z.itertuples():
        increments.append(dict(child_method=child,parent_method=parent,metric=r.metric,
            time_source=r.time_source,panels=r.panels_child,images=r.images_child,
            buildings=r.buildings_child,valid_team_links=r.valid_team_links_child,
            parent_between_share=r.between_share_parent,child_between_share=r.between_share_child,
            between_share_increment=r.between_share_child-r.between_share_parent,
            parent_within_variance=r.within_variance_parent,child_within_variance=r.within_variance_child,
            within_variance_reduction=r.within_variance_parent-r.within_variance_child,
            interpretation='Nested-partition descriptive increment on identical member sets; fixed-parent ABC is separately evaluated'))
save(O/'NESTED_FINE_INCREMENT_SAME_TEAMS.csv',pd.DataFrame(increments))

# A compact complete image/building comparison, kept separate from all events.
# Means of panel variances -> target -> image -> building, never averaging eta.
image_frames=[];building_frames=[];cover=[]
for method in methods:
    base=R/'by_method'/method
    p=pd.read_csv(base/'PANEL_VARIANCE.csv.gz',low_memory=False)
    fields=['total_variance','within_variance','between_variance']
    g=['method','condition','support','metric','time_source']
    p=p.dropna(subset=['total_variance'])
    target=p.groupby(g+['building','image','pool_id'],dropna=False)[fields].mean().reset_index()
    im=target.groupby(g+['building','image'],dropna=False)[fields].mean().reset_index()
    im['between_share']=(im.between_variance/im.total_variance).where(im.total_variance.gt(1e-12))
    im['within_sd_proxy']=np.sqrt(im.within_variance)
    counts=p.groupby(g+['building','image'],dropna=False).agg(
        panels=('panel_id','nunique'),valid_team_links=('valid_teams','sum')).reset_index()
    im=im.merge(counts,on=g+['building','image'],validate='one_to_one')
    image_frames.append(im)
    bu=im.groupby(g+['building'],dropna=False)[fields].mean().reset_index()
    bu['between_share']=(bu.between_variance/bu.total_variance).where(bu.total_variance.gt(1e-12))
    bc=im.groupby(g+['building'],dropna=False).agg(images=('image','nunique'),
        panels=('panels','sum'),valid_team_links=('valid_team_links','sum')).reset_index()
    building_frames.append(bu.merge(bc,on=g+['building'],validate='one_to_one'))
    cov=pd.read_csv(base/'PANEL_COVERAGE.csv.gz')
    for support,col in [('method_known','known_teams'),('shared_known','shared_known_teams')]:
        v=cov[cov[col].gt(0)]
        cover.append(dict(method=method,support=support,panels=len(v),images=v.image.nunique(),
            buildings=v.building.nunique(),team_links=int(v[col].sum()),
            unclassified_links=int(cov.teams.sum()-v[col].sum())))
save(O/'BY_IMAGE_ALL_METHODS.csv.gz',pd.concat(image_frames,ignore_index=True))
save(O/'BY_BUILDING_ALL_METHODS.csv.gz',pd.concat(building_frames,ignore_index=True))
save(O/'METHOD_KNOWN_AND_COMMON_COVERAGE.csv',pd.DataFrame(cover))

pre=json.loads((C/'primary_panel_inputs/INPUT_PREPARATION.json').read_text())
common=pd.DataFrame(cover);common=common[common.support.eq('shared_known')]
assert common[['panels','images','buildings','team_links']].nunique().max()==1
c=common.iloc[0]
selected=['DSTRUCT_K3','DSTRUCT_K4','OPPSTRUCT_K3','OPPSTRUCT_K4','OPPSTRUCT_K5',
    'DJOINT_K3','MSDGEOM_SCOPE_K4','RFUSE_GEOM_K3','RFUSE_GEOMQ_K3',
    'TARGET_DSTRUCT_K3','TARGET_RFUSE_GEOM_K3','V3_BEHAVIOR_COARSE',
    'V3_BEHAVIOR_FINE','V3_JOINT_QT_COARSE','V3_JOINT_QT_FINE','Q_MEDIAN2']
columns=['method','B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','failure']
tab=matrices['shared_known'].set_index('method').loc[selected].reset_index()[columns]
for col in columns[1:]:tab[col]=tab[col].map(lambda v:'未知' if pd.isna(v) else f'{100*v:.2f}%')
tab.columns=['方法','Q','D10','转折数','底面积','高度','失败']
report=f'''# v2.1 Manual：45套分类的完整有限配比比较

固定源提交 `a476461d7ede8db95da43de4139e612c05e618bc`。这是本轮冻结楼外标签下的重新汇总：先建类并保存名单，再给既有精确团队分配完整类别人数向量。输入为真人v2.1。

## 1. 已实际完成的空间

主目标 {pre['panels']} 个面板、{pre['images']} 张图、{pre['buildings']} 栋楼，213,444个面板—团队关联、213,442个唯一端点。每个面板固定共同背景D及12名可变成员，完整枚举12选6的924个集合；n覆盖12、14、16、18、19、20、23、24、25、27、28、29。完整类别向量包括固定D与选择的6人。这个有限成员空间全部完成，不等于每张图全部30余人中所有可能团队。

40,655个端点使用已经完成的v2.1现行参考重评分，172,787个输入和参考未改变的端点直接复用。本批没有新增融合或评分，现行目标不合法队伍为0，缺少受影响分项为0。原始精确成员、面板D/变量池、来源及可评分分母都保留。

45法共同有标签支持是 {c.panels} 面板、{c.images} 图、{c.buildings} 楼、{c.team_links:,} 个关联。每法自身可分类范围另列，不能把共同域缩小误说成退出资格。时间只在同来源且全队记录可用时求和，单位秒，来源标签在每张汇总表中保留。

## 2. 分类与完整配比的实际区分

下表是相同团队上**构成间方差/总方差**。先按面板分解，再按目标、图片、建筑等权汇总方差后相除。这说明类别人数向量描述了多少输出差异，不是Q提升比例、节时比例，也不直接代替匹配ABC。

{md(tab)}

全部45法及所有质量分项保存在 `ALL45_ALL_METRICS_BOTH_SUPPORTS.csv`。方便查阅的宽矩阵分别为 `ALL45_SHARED_KNOWN_METRIC_MATRIX.csv` 与 `ALL45_METHOD_KNOWN_METRIC_MATRIX.csv`，时间列含原来源名称。方法采用应将这里的真实配比解释力与严格同背景、同n/m的换人结果共同判断；不能只取一个最高方差比例。

**本节的采用判断：保留V3联合粗类用于整体配比的质量—时间解释，保留结构分类用于可见标法与局部构成解释。** V3联合粗类在这套共同有限面板上解释Q方差18.28%、记录时间方差59.44%；其细层在当前共同成员支持上没有增量。OPPSTRUCT K3的Q与转折解释分别14.89%和23.01%，高于DSTRUCT K3的12.44%和19.65%；DSTRUCT K3对高度解释30.55%，反而高于OPPSTRUCT K3的23.56%。因此没有必要将所有用途强行归为一套分类。跨条件MSDGEOM_SCOPE K4对Q解释17.87%，是有竞争力的补充，不因为它不是结构主线就丢弃。

这些比较都是在已有v2.1材料上重新形成标签后的内部评价。楼外建类与方法选型是两层：标签未使用目标楼历史，但本轮用这些实际输出比较方法并选用途，不宣称全新外部盲测。

## 3. 粗细增量和具体成员

这些同族K切分来自相同Ward树，逐折映射已核实为嵌套；V3粗/细也有对应关系。`EXACT_FOLD_HIERARCHY.csv` 保存实际映射；`NESTED_FINE_INCREMENT_SAME_TEAMS.csv` 是同一批具体团队上真实细分的增量。它与“固定A/B/C父类人数向量后更换细类”的实验分别报告。细分得到更高样本内方差解释并不自动表示每个细类都有可互换成员，仍需看每格团队数、实际波动、绝对幅度和固定父类事件。

`by_method/<method>/CONFIGURATION_COUNTS.csv.gz` 保存每一个可行配比及该格所有成员集合的覆盖、单例格、失败、源背景人数向量。`CONFIGURATION_DISTRIBUTIONS.csv.gz` 保存全分项均值、5/25/50/75/95分位、极值、标准差和IQR。只有一队的格不估计成员波动；失败团队不被质量可评分分母隐藏。

## 4. 难度、团队规模与成员域

`BY_SIZE_DIFFICULTY_AND_SOURCE.csv.gz` 同时保留不同n、官方难度、可计算结构条件、all_formal/new_only成员域的结果。规模间图片和背景支持可能不同，分层描述不能直接改写为同一批人的人数因果曲线。逐图及逐楼全分项在 `BY_IMAGE_ALL_METHODS.csv.gz` 和 `BY_BUILDING_ALL_METHODS.csv.gz`；比较方法可以直接对齐同图支持，分析具体构成时可返回完整配比和精确成员。

其它31个已准入目标的结果独立保存在阶段03A，不复制主目标难度或把不同空间人员合队。Semi另有105个自身标签面板，单独报告；没有混入这里的Manual。

## 5. 文件和复算

- `../primary_panel_inputs/`：现行端点标量、面板、精确成员和已存v2.1重评分来源。
- `../primary_manual45/by_method/`：45法完整结果，按方法逐个保存；所有引用均为已完成文件。
- `../../classification/MAIN45_LABELS_ALL_LOBO.csv.gz`：实际ALL及楼外标签，描述与评价分别使用。
- `../primary_compact_links/`：无损紧凑关联，0为未知；方法整数码经码本展开回原完整人数向量。
- `../code/prepare_current_panel_endpoints.py`、`aggregate_frozen_panels.py`、`build_primary_mixture_note.py`、`compact_vector_links.py`：实际运行代码。

本节回答“完整配比及配比内成员波动”。推荐方法、方向、n/m及机制由本轮全局严格ABC和局部案例共同确定，避免将同一结果重复充当不同实验。
'''
(O/'README.md').write_text(report,encoding='utf-8')
done=dict(methods=45,panels=pre['panels'],team_links=pre['team_links'],
    unique_endpoints=pre['unique_endpoints'],common_panels=int(c.panels),
    common_images=int(c.images),common_buildings=int(c.buildings),common_links=int(c.team_links),
    nested_family_relations=len(pairs),source='frozen v2.1 endpoints; no new fusion',
    hierarchy_sha256=hashlib.sha256(hpath.read_bytes()).hexdigest())
(O/'COMPLETE.json').write_text(json.dumps(done,ensure_ascii=False,indent=2))
print(json.dumps(done,ensure_ascii=False),flush=True)
