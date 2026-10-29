"""Package-facing summaries for the completed other-target finite panels.
These are descriptive mixture results, distinct from strict ABC inference.
"""
from pathlib import Path
import json,re,gzip,os
import numpy as np
import pandas as pd

W=Path(__file__).resolve().parents[2]
C=W/'composition'; O=C/'stage03A_other_targets';O.mkdir(exist_ok=True)
def save(path,d):
 data=d.to_csv(index=False).encode('utf-8-sig')
 if str(path).endswith('.gz'):data=gzip.compress(data,mtime=0)
 tmp=path.with_name(path.name+'.writing')
 with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 tmp.replace(path)
summary=pd.read_csv(C/'other_targets_manual45/ALL_METHOD_COMPARISON.csv')
a=summary[summary.summary_axis.eq('all')&summary.summary_value.eq('all')&summary.support.eq('shared_known')].copy()
key=a[a.metric.isin(['B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','failure','recorded_time_total_seconds'])]
save(O/'ALL45_COMMON_SUPPORT_KEY_METRICS.csv',key)
methods=set(a.method);increments=[]
for method in sorted(methods):
 m=re.match(r'^(.*)_K([3-9])$',method)
 parent=f'{m[1]}_K{int(m[2])-1}' if m else method[:-5]+'_COARSE' if method.endswith('_FINE') else ''
 if parent not in methods:continue
 child=a[a.method.eq(method)];base=a[a.method.eq(parent)]
 x=child.merge(base,on=['metric','time_source','condition','support'],suffixes=('_child','_parent'))
 for r in x.itertuples():
  increments.append(dict(child_method=method,parent_method=parent,metric=r.metric,time_source=r.time_source,
    panels_child=r.panels_child,panels_parent=r.panels_parent,images_child=r.images_child,images_parent=r.images_parent,
    teams_child=r.valid_team_links_child,teams_parent=r.valid_team_links_parent,
    between_share_child=r.between_share_child,between_share_parent=r.between_share_parent,
    between_share_delta=r.between_share_child-r.between_share_parent,
    within_variance_child=r.within_variance_child,within_variance_parent=r.within_variance_parent,
    within_variance_delta=r.within_variance_child-r.within_variance_parent,
    interpretation='Descriptive partition increment on identical shared teams, not held-out prediction gain'))
save(O/'HIERARCHY_INCREMENT_COMMON_SUPPORT.csv',pd.DataFrame(increments))
requests=pd.read_csv(C/'other_targets_design/TEAM_REQUESTS.csv.gz');panels=pd.read_csv(C/'other_targets_design/PANELS_USED.csv')
end=pd.read_csv(C/'other_targets_endpoints/ENDPOINT_SCALARS.csv.gz',low_memory=False)
roles=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',low_memory=False)
case_specs=[('structure_composition','manual','DSTRUCT_K3','rPc6DW4iMge-06',5),
 ('within_composition_risk','manual','DSTRUCT_K3','wc2JMjhGNzB-26',6),
 ('same_coarse_different_members','manual','DSTRUCT_K3','e9zR4mvMWw7-17',3),
 ('fine_partition_small_absolute_effect','semi','V3_BEHAVIOR_FINE','uNb9QFRL6hY-68',3)]
config=[];dist=[];teams=[];case_rows=[]
for cid,condition,method,image,n in case_specs:
 base=C/('other_targets_manual45' if condition=='manual' else 'other_targets_semi4')/'by_method'/method
 cd=pd.read_csv(base/'CONFIGURATION_COUNTS.csv.gz');dd=pd.read_csv(base/'CONFIGURATION_DISTRIBUTIONS.csv.gz')
 support='shared_known' if condition=='manual' else 'method_known'
 cc=cd[cd.image.eq(image)&cd.n.eq(n)&cd.support.eq(support)].copy();dd=dd[dd.image.eq(image)&dd.n.eq(n)&dd.support.eq(support)].copy()
 assert cc.panel_id.nunique()==1
 pid=cc.panel_id.iloc[0]; pool=cc.pool_id.iloc[0];building=cc.building.iloc[0]
 vv=pd.read_csv(base/'TEAM_CLASS_VECTORS.csv.gz');vv=vv[vv.panel_id.eq(pid)&vv['shared_known' if condition=='manual' else 'known']].copy()
 vv=vv.merge(requests[['team_key','member_workers']],on='team_key',validate='one_to_one')
 vv=vv.merge(end[['team_key','B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','complete_evaluable','recorded_time_total_seconds']],on='team_key',validate='one_to_one')
 rr=roles[roles.method.eq(method)&roles.heldout_building.eq(building)] if condition=='manual' else pd.DataFrame()
 rolemap=dict(zip(rr.class_id,rr.semantic_training_role)) if len(rr) else {}
 for frame in [cc,dd,vv]:frame.insert(0,'case_id',cid)
 cc['fold_role_definitions_json']=json.dumps(rolemap,ensure_ascii=False,sort_keys=True)
 config.append(cc);dist.append(dd);teams.append(vv)
 q=dd[dd.metric.eq('B8L2')];case_rows.append(dict(case_id=cid,condition=condition,method=method,image=image,pool_id=pool,panel_id=pid,n=n,
  configurations=len(cc),teams=int(cc.teams.sum()),scorable=int(cc.scorable_teams.sum()),failed=int(cc.failed_teams.sum()),
  minimum_q=float(q.minimum.min()),maximum_q=float(q.maximum.max()),range_of_configuration_means=float(q['mean'].max()-q['mean'].min()),
  singleton_configurations=int((cc.teams==1).sum()),selection='deliberate explanatory examples after full finite comparison; not independent method selection'))
save(O/'REPRESENTATIVE_ALL_CONFIGURATIONS.csv',pd.concat(config,ignore_index=True));save(O/'REPRESENTATIVE_CONFIGURATION_DISTRIBUTIONS.csv.gz',pd.concat(dist,ignore_index=True));save(O/'REPRESENTATIVE_EXACT_TEAMS.csv.gz',pd.concat(teams,ignore_index=True));save(O/'REPRESENTATIVE_CASES.csv',pd.DataFrame(case_rows))
counts=end.groupby('condition').agg(unique_teams=('team_key','size'),scorable_Q=('B8L2','count'),scorable_D10=('D10','count'),complete=('complete_evaluable','sum'),known_comparable_time=('recorded_time_total_seconds','count')).reset_index();counts['not_complete']=counts.unique_teams-counts.complete;save(O/'UNIQUE_ENDPOINT_COVERAGE.csv',counts)
columns=['method','B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h']
key['matrix_metric']=key['metric'].where(key.time_source.eq('not_time'),key['metric']+'__'+key.time_source)
pivot=key.pivot(index='method',columns='matrix_metric',values='between_share').reset_index()
save(O/'ALL45_COMMON_SUPPORT_METRIC_MATRIX.csv',pivot)
selected=['DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3','OPPSTRUCT_K5','DJOINT_K3','MSDGEOM_SCOPE_K4','RFUSE_GEOM_K2','RFUSE_GEOMQ_K3','TARGET_RFUSE_GEOM_K3','V3_JOINT_QT_COARSE']
tab=pivot[pivot.method.isin(selected)][columns].copy()
for c in columns[1:]:tab[c]=tab[c].map(lambda x:f'{100*x:.2f}%')
def markdown(df):
 return '\n'.join(['| '+' | '.join(map(str,df.columns))+' |','| '+' | '.join(['---']*len(df.columns))+' |']+['| '+' | '.join(map(str,row))+' |' for row in df.itertuples(index=False,name=None)])
report='''# 阶段03A：其它已准入目标的完整有限配比结果

固定源提交 `a476461d7ede8db95da43de4139e612c05e618bc`，真人 **v2.1**。本批已实际完成，原目标主域45法比较仍独立继续；这里不抢先宣布主分类优胜。

## 1. 实际计算与覆盖

31 个其它合法目标池、69 个固定人数面板、8,940 支唯一团队：2,459 支复用现行缓存，6,481 支新增冻结融合。Manual 是30池、8,935队；Semi是1池、5队，两者分别评价。

- 21个 N≤10 小池枚举全部 n=3…N 的成员集合，共1,086队。
- 3个 N=11 池，各枚举11选5的462队。
- 7个 N≥12 池，在结果未知时由固定哈希选12人，完整枚举12选6的924队；不称为全人员池穷尽。
- 所有池 n≥3 的全成员空间是219,284队；本批覆盖8,940队，尚未请求210,344队。具体每池范围见 `other_targets_design/POOL_CAPACITY_PLAN.csv`。

Manual 8,935队中7,391队可完整评分，1,544队失败/不完整；来源可比的完整记录时间1,871队。Semi5队全部可评分，记录时间未知。时间未知不记零；Q分布按可评团队计算，失败同时在全部尝试分母上报告。

## 2. 同一批团队上，分类确实有不同用途

以下全部使用45法共同已知团队支持：66个人数面板、30个目标池、28张图、9栋楼；7,933团队关联，其中Q可评6,515队、失败/不完整1,418队。先在面板内分解方差，再按目标池→图片→建筑等权。百分数是**构成间方差／总方差**，没有当作升质百分比、预测改善或节时比例。

'''+markdown(tab.rename(columns={'method':'方法','B8L2':'Q','D10':'D10','fusion_turn_n':'转折数','geometry_area_h2':'底面积','height_mean_h':'高度'}))+'''

完整45法和全部质量/几何/时间分项见 `ALL45_COMMON_SUPPORT_KEY_METRICS.csv` 及 `../other_targets_manual45/ALL_METHOD_COMPARISON.csv`。每法自身已知支持也完整保留；不是因为共同支持较少就丢掉其它有效团队。

这批新增目标上，旧V3联合工作分类保留了较强的描述作用；新的OPPSTRUCT K3并没有在每个指标上超过旧DSTRUCT K3。细分类常能解释更多样本内变异，但是否值得采用还要看绝对差异、实际成员替代空间和严格ABC结果。V3联合及V3结构的粗/细层在这批目标上的结果完全相同，没有额外层级收益；全部同族增量见 `HIERARCHY_INCREMENT_COMMON_SUPPORT.csv`。

## 3. 四个完整配置例子

例子是从已经完成的有限比较中按解释用途选择，所有配比格和精确成员均保留，不只展示最高分。

- **rPc-06 其它目标，DSTRUCT K3，n5：**21队、6配比全枚举。C3在该楼外折是较多转折角色；仅1个C3席位的构成均Q44.73，2席位两种构成均Q65.02和54.87，3席位三种构成均Q86.10、86.06和93.84。构成间Q方差占84.76%。不同C1/C2背景依然造成明显差别；其中2种配比只有唯一成员队，不能估计该格的换人成员波动。
- **wc2-26 其它目标，DSTRUCT K3，n6：**固定12人面板内924队、8配比，450队失败、474队可评分。构成间Q方差仅4.19%；几格内部Q约20—77，说明该条件仍主要由具体成员决定，不能只按三类配额组织。
- **e9z-17 其它目标，DSTRUCT K3，n3：**4队都为C3:3，Q仍为50.17—93.60。该图可研究同构成内成员差异，没有跨构成证据；这不是对其它图多数规律的否定。
- **新增Semi uNb-68，n3：**自身结构粗类四队都是S1:3，Q仅相差0.7337，6个转折一致。细类把这两档分开，构成间方差占比100%，绝对差仍很小；n4只有全员唯一队，成员波动不可估。自身联合QT只有两人历史足够，不能为n≥3团队补类。

上述全部格见 `REPRESENTATIVE_ALL_CONFIGURATIONS.csv`；每格全指标分布与精确队伍分别见 `REPRESENTATIVE_CONFIGURATION_DISTRIBUTIONS.csv.gz`、`REPRESENTATIVE_EXACT_TEAMS.csv.gz`。这些是配比比较，不冒充共同D的严格ABC因果对照。

## 4. 小池怎样接续

6个 N4 Manual池对所有4个三人队做72个有向直接AC事件（36个无向团队对），独立保存于 `../small_pool_direct_ac/`。新增Semi N4池以其自身4套标签做12个有向AC（6个无向对），在 `../small_pool_semi_direct_ac/`。这些没有同类B对照，不混入严格ABC。5个 N3 Manual池只有n≥3唯一全员队，不能估计大块替换。

其它目标继续沿用已确认的空间归属；没有将它们与原主目标人员合队。未知正式难度保持未分级，可计算的转折、自遮挡、短边条件另列于目标条件表，不复制同图另一个空间的难度。

## 5. 可接续文件

- `../other_targets_design/`：固定面板、全部成员请求及理论未覆盖量。
- `../other_targets_endpoints/ENDPOINT_SCALARS.csv.gz`：8,940个去重端点标量；同目录 `pools/*/part_*.jsonl.gz` 是完整几何、来源和票数基础字段。
- `../other_targets_manual45/by_method/<method>/`：每法完整类别向量、配置计数、逐配置分布、面板方差、覆盖及已完成凭证。
- `../other_targets_semi4/`：Semi自身分类的独立结果。
- `../../classification/MAIN45_LABELS_ALL_LOBO.csv.gz`、`SEMI_BASE_LABELS_ALL_LOBO.csv.gz`：实际楼外标签，属于阶段02。
- `../code/aggregate_frozen_panels.py`：实际运行的配比聚合。旧团队原答和质量未因新标签修改。

所有 `.writing` 临时残留不属交付；完成表已实际解压读取。本批不替代后续主目标广筛、严格ABC和成员/背景扩展。
'''
(O/'README.md').write_text(report,encoding='utf-8')
manifest=[dict(path=str(p.relative_to(W)),bytes=p.stat().st_size) for root in [C/'other_targets_design',C/'other_targets_endpoints',C/'other_targets_manual45',C/'other_targets_semi4',C/'small_pool_direct_ac',C/'small_pool_semi_direct_ac',O] for p in root.rglob('*') if p.is_file() and not p.name.endswith(('.writing','.tmp','.log','.pyc'))]
(O/'DELIVERY_FILE_INDEX.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print(json.dumps({'stage':'03A','files':len(manifest),'case_configurations':sum(len(v) for v in config),'case_team_rows':sum(len(v) for v in teams)}),flush=True)
