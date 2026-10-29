"""Complete cached configuration examples for the selected OPPJOINT K4 method.
No new teams, fusion, scores, or labels. Selection rules are saved explicitly.
"""
from pathlib import Path
import gzip,os,json
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
W=Path(__file__).resolve().parents[1];C=W/'composition';O=C/'OPPJOINT_K4_complete_configuration_cases';O.mkdir(exist_ok=True)
def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
base=C/'primary_manual45/by_method/OPPJOINT_K4'
v=pd.read_csv(base/'PANEL_VARIANCE.csv.gz');eligible=v[v.support.eq('shared_known')&v.metric.eq('B8L2')&v.n.ge(20)&v.teams.eq(924)&v.valid_teams.eq(924)&v.configurations.ge(3)].copy()
rules=[('all_panel_median','between_variance',eligible,.5,'All 95 complete n>=20 panels: nearest median between-configuration Q variance'),
 ('material_variation_median','between_share',eligible[eligible.between_variance.ge(1)],.5,'Among panels with between-configuration Q variance >=1: nearest median share'),
 ('weak_separation','between_share',eligible[eligible.total_variance.ge(1)],.1,'Non-flat panels with total Q variance >=1: nearest 10th-percentile share')]
chosen=[]
for cid,col,domain,q,why in rules:
 target=domain[col].quantile(q);r=domain.loc[(domain[col]-target).abs().idxmin()].to_dict()
 r.update(case_id=cid,selection_rule=why,selection_field=col,selection_target=target,eligible_panels=len(domain),post_comparison_example=True);chosen.append(r)
chosen=pd.DataFrame(chosen);save(O/'CASE_SELECTION.csv',chosen)
save(O/'ALL_ELIGIBLE_PANELS_FOR_SELECTION.csv',eligible)
panels=pd.read_csv(C/'primary_panel_inputs/PANELS_USED.csv');panels=panels[panels.panel_id.isin(chosen.panel_id)]
save(O/'SELECTED_PANELS_EXACT_BACKGROUNDS.csv',panels)
roles=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz');roles=roles[roles.method.eq('OPPJOINT_K4')&roles.heldout_building.isin(panels.building)]
save(O/'LOBO_ROLE_DEFINITIONS_AND_MEMBERS.csv',roles)
mapping={(r.heldout_building,r.class_id):int(r.q_rank_asc) for r in roles.itertuples()}
def qvector(building,counts):
 q={mapping[(building,k)]:int(n) for k,n in (s.split(':') for s in counts.split('|'))}
 return '|'.join(f'q{i}:{q.get(i,0)}' for i in range(1,5))
counts=pd.read_csv(base/'CONFIGURATION_COUNTS.csv.gz');counts=counts[counts.panel_id.isin(panels.panel_id)&counts.support.eq('shared_known')].copy()
dist=pd.read_csv(base/'CONFIGURATION_DISTRIBUTIONS.csv.gz');dist=dist[dist.panel_id.isin(panels.panel_id)&dist.support.eq('shared_known')].copy()
case_map=chosen.set_index('panel_id').case_id.to_dict()
for d in [counts,dist]:
 d.insert(0,'case_id',d.panel_id.map(case_map));d['q_rank_counts']=[qvector(b,c) for b,c in zip(d.building,d.class_counts)]
save(O/'ALL_CONFIGURATIONS_COUNTS.csv',counts);save(O/'ALL_CONFIGURATIONS_ALL_METRIC_DISTRIBUTIONS.csv.gz',dist)
q=dist[dist.metric.eq('B8L2')].copy();q=q.merge(counts[['panel_id','class_counts','failed_teams','member_census_complete','background_class_counts','variable_class_capacity']],on=['panel_id','class_counts'],validate='one_to_one')
q=q.rename(columns={'mean':'Q_mean','p05':'Q_p05','p25':'Q_p25','median':'Q_median','p75':'Q_p75','p95':'Q_p95','sd':'Q_within_sd','minimum':'Q_min','maximum':'Q_max'})
save(O/'ALL_CONFIGURATIONS_Q_READABLE.csv',q[['case_id','image','n','q_rank_counts','class_counts','background_class_counts','variable_class_capacity','teams','valid_teams','failed_teams','Q_mean','Q_p05','Q_p25','Q_median','Q_p75','Q_p95','Q_min','Q_max','Q_within_sd','member_census_complete']])
links=pd.read_csv(base/'TEAM_CLASS_VECTORS.csv.gz');links=links[links.panel_id.isin(panels.panel_id)&links.shared_known].copy()
members=pd.read_csv(C/'primary_panel_inputs/TEAM_MEMBERS.csv.gz')
endpoint_columns=['team_key','B8L2','D10','fusion_turn_n','geometry_area_h2','height_mean_h','recorded_time_total_seconds','time_source_kinds','complete_evaluable']
end=pd.read_csv(C/'primary_panel_inputs/ENDPOINT_SCALARS.csv.gz',usecols=endpoint_columns,low_memory=False)
links=links.merge(members[['team_key','member_workers']],on='team_key',validate='many_to_one').merge(end,on='team_key',validate='many_to_one')
links.insert(0,'case_id',links.panel_id.map(case_map));save(O/'ALL_EXACT_TEAMS_AND_ENDPOINTS.csv.gz',links)
stats=[]
for r in chosen.itertuples():
 z=q[q.case_id.eq(r.case_id)];stats.append(dict(case_id=r.case_id,image=r.image,n=r.n,configurations=len(z),teams=int(z.teams.sum()),
  min_configuration_Q_mean=z.Q_mean.min(),max_configuration_Q_mean=z.Q_mean.max(),between_share=r.between_share,
  minimum_Q=z.Q_min.min(),maximum_Q=z.Q_max.max(),minimum_p05=z.Q_p05.min(),maximum_within_sd=z.Q_within_sd.max()))
save(O/'CASE_OVERVIEW.csv',pd.DataFrame(stats))
fig,axes=plt.subplots(3,1,figsize=(12,11.8))
titles={'all_panel_median':'Median panel in the full eligible set','material_variation_median':'Median share among panels with material Q variation','weak_separation':'Weak composition separation, large member variation'}
for ax,r in zip(axes,chosen.itertuples()):
 z=q[q.case_id.eq(r.case_id)].sort_values('q_rank_counts');x=np.arange(len(z))
 ax.vlines(x,z.Q_min,z.Q_max,color='#cbd5e1',linewidth=2,label='min-max')
 ax.vlines(x,z.Q_p05,z.Q_p95,color='#3b82f6',linewidth=5,label='p05-p95')
 ax.scatter(x,z.Q_mean,color='#be123c',s=30,zorder=4,label='mean')
 labels=['/'.join(a.split(':')[1] for a in s.split('|')) for s in z.q_rank_counts]
 ax.set_xticks(x,labels,fontsize=8,rotation=35,ha='right');ax.set_ylabel('Frozen Q (B8L2)')
 ax.set_title(f'{titles[r.case_id]}: {r.image}, n={r.n}, between share={100*r.between_share:.1f}%',loc='left',fontsize=11)
 ax.grid(axis='y',color='#e2e8f0');ax.spines[['top','right']].set_visible(False)
 for i,rr in enumerate(z.itertuples()):ax.annotate(str(int(rr.teams)),(i,rr.Q_max),xytext=(0,4),textcoords='offset points',ha='center',fontsize=7)
 ax.margins(y=.2);ax.set_xlabel('Full-team q1 / q2 / q3 / q4 counts (class ranks formed outside the building)',fontsize=9)
axes[0].legend(loc='lower left',ncol=3,fontsize=8)
fig.suptitle('OPPJOINT K4: every feasible configuration in three exact member panels',fontsize=14,weight='bold')
fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(O/'ALL_CONFIGURATION_Q_DISTRIBUTIONS.png',dpi=170);fig.savefig(O/'ALL_CONFIGURATION_Q_DISTRIBUTIONS.svg');plt.close(fig)
rows=pd.DataFrame(stats)
text='''# OPPJOINT K4：完整混合配比示例

直接复用阶段03B全部有限面板、当前楼外标签与v2.1端点；0新增融合/评分。不是只展示最佳配比格，也不把有限12选6面板称为全人员池全部组合。

选择范围为共同标签支持、n≥20、完整924队全部可评分、至少3种完整人数向量的95个面板。保存三个例子：全部范围的构成间Q方差中位代表；构成间Q方差≥1的30面板中构成占比中位代表；总方差≥1的48面板中构成占比约第10百分位的弱区分例。选择依据和所有候选面板均保留，属于比较后的解释案例。

完整32格、每格所有成员队、Q均值/5%低尾/中位/95%/极值/类内SD和失败分母都保留。其余全部质量、结构、几何、时间分项在完整分布表中；未知时间没有补零。q1至q4按该建筑楼外历史Q中心排序，与原C编号映射在逐折角色表中；所有人数向量都包含固定背景D。

典型范围和弱差异都显示：配比格均值可以不同，同一格内具体成员仍可造成更大波动。它与较大块、明确角色方向的严格ABC是不同研究切面，不能把面板内较低方差解释率直接当作主换类方向无效。

## 文件

- `ALL_CONFIGURATIONS_Q_READABLE.csv`：三个例子的所有32个配比格，均值、低尾、withinSD及分母。
- `ALL_CONFIGURATIONS_ALL_METRIC_DISTRIBUTIONS.csv.gz`：所有既有分项分布。
- `ALL_EXACT_TEAMS_AND_ENDPOINTS.csv.gz`：2,772个团队关联，精确成员、端点和指标。
- `SELECTED_PANELS_EXACT_BACKGROUNDS.csv`：固定D、12名变量池、真实人员池与全空间未覆盖量。
- `CASE_SELECTION.csv`、`ALL_ELIGIBLE_PANELS_FOR_SELECTION.csv`：选择规则及全候选分母。
- `LOBO_ROLE_DEFINITIONS_AND_MEMBERS.csv`：实际折的类别含义和人员。
- `ALL_CONFIGURATION_Q_DISTRIBUTIONS.png`：每格均值、5—95%与全范围；上方数字为格内团队数。

完整原答、几何、照片由既有主缓存及机制案例连接，不在此重复打包。
'''
(O/'README.md').write_text(text,encoding='utf-8')
(O/'COMPLETE.json').write_text(json.dumps(dict(cases=3,configurations=len(q),team_links=len(links),new_fusions=0,new_scores=0),indent=2))
print(rows.to_json(orient='records',force_ascii=False),flush=True)
