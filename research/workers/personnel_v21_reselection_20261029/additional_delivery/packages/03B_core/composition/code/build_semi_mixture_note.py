from pathlib import Path
import json,os,gzip
import numpy as np,pandas as pd
W=Path(__file__).resolve().parents[2]; O=W/'composition/semi_mixture_results';O.mkdir(exist_ok=True)
def save(p,d):
 data=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':data=gzip.compress(data,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 t.replace(p)
def md(d):return '\n'.join(['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']+['| '+' | '.join(map(str,r))+' |' for r in d.itertuples(index=False,name=None)])
d=pd.read_csv(W/'composition/primary_semi4/ALL_METHOD_COMPARISON.csv');a=d[d.summary_axis.eq('all')&d.support.eq('shared_known')]
key=a[a.metric.isin(['B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','failure','recorded_time_total_seconds'])].copy();save(O/'COMMON_SUPPORT_ALL_METRICS.csv',a);save(O/'COMMON_SUPPORT_KEY_METRICS.csv',key)
keep=d[d.summary_axis.isin(['n','difficulty','source_domain'])&d.support.eq('shared_known')];save(O/'BY_SIZE_DIFFICULTY_AND_SOURCE.csv.gz',keep)
piv=key.pivot(index='method',columns='metric',values='between_share').reset_index();save(O/'COMMON_SUPPORT_METRIC_MATRIX.csv',piv)
rows=[]
for family in ['V3_BEHAVIOR','V3_JOINT_QT']:
 c=a[a.method.eq(family+'_COARSE')];f=a[a.method.eq(family+'_FINE')];x=f.merge(c,on=['metric','time_source'],suffixes=('_fine','_coarse'))
 for r in x.itertuples():rows.append(dict(family=family,metric=r.metric,time_source=r.time_source,coarse_share=r.between_share_coarse,fine_share=r.between_share_fine,share_increment=r.between_share_fine-r.between_share_coarse,coarse_within=r.within_variance_coarse,fine_within=r.within_variance_fine,valid_teams_fine=r.valid_team_links_fine,valid_teams_coarse=r.valid_team_links_coarse,images=r.images_fine,buildings=r.buildings_fine))
save(O/'FINE_INCREMENT_SAME_TEAMS.csv',pd.DataFrame(rows))
l=pd.read_csv(W/'classification/SEMI_BASE_LABELS_ALL_LOBO.csv.gz',low_memory=False);allcenters=[]
for (m,b,c),g in l[l.known].groupby(['method','heldout_building','class_id']):
 r=dict(method=m,heldout_building=b,class_id=c,people=len(g),members='|'.join(sorted(g.worker_id)))
 for field in ['turn_history','short_history','redundancy_history','area_history','height_history','complex_turn_history','q_history','q_downside','t_history','n_images','n_buildings']:
  if field in g:r[field]=g[field].mean()
 allcenters.append(r)
centers=pd.DataFrame(allcenters);save(O/'OWN_SEMI_CLASS_CENTERS_ALL_LOBO.csv.gz',centers)
allview=centers[centers.heldout_building.eq('ALL')];save(O/'OWN_SEMI_CLASS_MEMBERS_ALL.csv',allview)
pretty=piv[['method','B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','failure','recorded_time_total_seconds']].copy()
for c in pretty.columns[1:]:pretty[c]=pretty[c].map(lambda v:f'{100*v:.2f}%')
pretty.columns=['Semi自身方法','Q','D10','转折','底面积','高度','失败','记录时间']
text='''# v2.1 Semi自身分类：完整有限配比用途

固定提交 `a476461d7ede8db95da43de4139e612c05e618bc`。本节只使用Semi人员历史形成的现行V3结构/联合Q/T标签，效果也仅来自Semi终点；没有把Manual标签或终点混入主比较。

## 已完成范围

105个既有完整12选6条件面板，22张图、12栋楼，97,020团队关联、97,016唯一端点。26,795个端点复用已经完成的v2.1重评分，70,221个参考未变的端点直接复用；本批0次新融合、0次新评分，缺少现行参考分项为0。

自身结构两层可用56,364团队关联；自身联合两层可用31,808。四法共同支持为42面板、12图、9楼、31,808团队关联，Q可评29,797；时间在来源一致的28面板、12图、9楼、25,872团队关联中可用。缺失历史与未知时间均不补零。

## 比例与成员变化的用途

下面是同一批团队中，类别人数向量所解释的构成间方差比例。按面板→目标→图片→建筑等权；不是升质百分比或节时百分比。

'''+md(pretty)+'''

**采用判断：保留Semi自身联合粗类作为质量—时间构成的工作分类。** 它对记录时间差异的解释最明确，也同时描述部分Q、底面积、高度和失败差异。结构粗类主要描述少量几何差异；其细类对转折与底面积有较清楚增量。联合细类的平均Q和时间增量较小，但失败构成的解释增量较大，可以作为风险解释的补充层。

这些是实际配比和同配比成员波动的结果；不能把60.77%时间构成间方差改写为节省60.77%劳动时间。现成v2的定向换人结果保持原阶段身份，新的Semi方向采用需要与相应折的精确替换事件关联。

## 角色与人员

ALL描述名单和中心见 `OWN_SEMI_CLASS_MEMBERS_ALL.csv`；逐折中心与名单在 `OWN_SEMI_CLASS_CENTERS_ALL_LOBO.csv.gz`。例如联合粗类ALL的K2（9人）与K3（10人）历史Q同伴残差分别约+1.99和+2.68，但来源内log时间中心分别+1.016和−0.612，是“相近历史Q、速度角色不同”的实际人群。K1（23人）历史Q较低；K4（12人）历史Q较高。这里只用于解释ALL名册，跨建筑事件不能直接拼接K编号。

全体成员、质量低尾、结构/尺度中心和缺失原因与原始标签相连；未修改不等于盲信，没有精确初始化的人员不虚构编辑轨迹。

## 其它合法目标

新增Semi只有uNb-68的另一个合法目标，4人池。n3枚举4队，n4只有唯一全员队。自身结构粗类n3四队同构成，Q范围仅0.7337；细类解释了两档差异，但绝对量很小。联合QT只有两人历史足够，无法构成n≥3有类团队。它的结果独立保存在 `../other_targets_semi4/`，不借用主目标难度，不混入上述22图主域比较。

## 完整文件

- `../primary_semi_inputs/`：v2.1现行端点标量、精确队伍与面板关联、重评分来源。
- `../primary_semi4/by_method/<method>/`：完整每配比分布、失败数、成员组合数、团队类别向量和逐面板方差。
- `COMMON_SUPPORT_ALL_METRICS.csv`：四法所有可用分项同支持比较。
- `BY_SIZE_DIFFICULTY_AND_SOURCE.csv.gz`：规模、难度与来源域分层。
- `FINE_INCREMENT_SAME_TEAMS.csv`：粗细类同团队增量，保留负向/零差异。
- `../code/prepare_current_panel_endpoints.py`、`../code/aggregate_frozen_panels.py`：实际重汇总代码。
'''
(O/'README.md').write_text(text,encoding='utf-8')
print(json.dumps({'methods':len(piv),'key_rows':len(key),'centers_all_lobo':len(centers),'complete':True}))
