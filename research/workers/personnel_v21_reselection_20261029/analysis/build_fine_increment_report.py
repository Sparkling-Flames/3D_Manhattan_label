"""Select supported uses from the completed, fully retained fine-class study."""
from pathlib import Path
import gzip,json,os
import numpy as np,pandas as pd
W=Path(__file__).resolve().parents[1];O=W/'analysis/fine_increment'
def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
def md(d):return '\n'.join(['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']+['| '+' | '.join(map(str,r))+' |' for r in d.itertuples(index=False,name=None)])

spec=[('联合四类父内/20人','OPPJOINT_K4',20,6,'QT__higher_Q__higher_logtime'),
 ('联合四类父内/26人','OPPJOINT_K4',26,3,'QT__higher_Q__higher_logtime'),
 ('跨条件几何/半队块','MSDGEOM_K4',8,4,'challenge_turn__higher'),
 ('跨条件几何/10人','MSDGEOM_K4',10,3,'challenge_turn__higher'),
 ('跨条件加scope/定向升质','MSDGEOM_SCOPE_K4',10,3,'challenge_turn__higher'),
 ('融合反推细类/风险','RFUSE_GEOMQ_K3',12,6,'response_hard_turn__higher'),
 ('目标结构细类/幅度','TARGET_DSTRUCT_K4',8,4,'challenge_turn__lower')]
s=pd.read_csv(O/'ALL_FINE_CONDITIONS.csv.gz',low_memory=False)
im=pd.read_csv(O/'IMAGE_DIRECTION_N_M_METRICS.csv.gz',low_memory=False)
bu=pd.read_csv(O/'BUILDING_DIRECTION_N_M_METRICS.csv.gz',low_memory=False)
e=pd.read_csv(O/'FIXED_PARENT_EVENT_METRICS.csv.gz',low_memory=False)
risk=pd.read_csv(O/'QUALITY_TAIL_AND_FAILURE_DENOMINATORS.csv')
selected=[];image_rows=[];events=[];risk_rows=[]
for name,method,n,m,direction in spec:
 def choose(df):return df.method.eq(method)&df.n.eq(n)&df.m.eq(m)&df.direction_semantic.eq(direction)&df.scope.eq('primary')
 xx=s[choose(s)&s.summary_axis.eq('direction_n_m')].copy()
 ii=im[choose(im)].copy();ee=e[choose(e)].copy();bb=bu[choose(bu)].copy()
 assert len(xx)>0 and len(ii)>0
 for r in xx.to_dict('records'):
  i=ii[ii.metric.eq(r['metric'])&ii.time_source.eq(r['time_source'])]
  b=bb[bb.metric.eq(r['metric'])&bb.time_source.eq(r['time_source'])]
  r['focus_use']=name
  for field in ['same_abs','cross_symmetric_abs','cross_AC_abs','gap_symmetric','gap_AC','BA','CA','CB']:
   r['building_mean_'+field]=r[field];r['image_mean_'+field]=i[field].mean()
   r['image_median_'+field]=i[field].median()
  for field in ['CA','CB','gap_symmetric','gap_AC']:
   r['images_'+field+'_negative']=int(i[field].lt(-1e-9).sum())
   r['images_'+field+'_zero']=int(i[field].abs().le(1e-9).sum())
   r['buildings_'+field+'_negative']=int(b[field].lt(-1e-9).sum())
  selected.append(r)
 for df in [ii,ee]:df.insert(0,'focus_use',name)
 image_rows.append(ii);events.append(ee)
 rr=risk[(risk.method==method)&(risk.n==n)&(risk.m==m)&risk.scope.eq('primary')&
  (risk.direction_axis+'__'+risk.role_direction).eq(direction)].copy();rr.insert(0,'focus_use',name);risk_rows.append(rr)
selected=pd.DataFrame(selected);save(O/'FOCUS_CONDITIONS_ALL_METRICS_BOTH_WEIGHTINGS.csv',selected)
save(O/'FOCUS_IMAGE_RESULTS.csv.gz',pd.concat(image_rows,ignore_index=True));event=pd.concat(events,ignore_index=True)
save(O/'FOCUS_EXACT_EVENTS.csv.gz',event);save(O/'FOCUS_FAILURE_AND_QUALITY_TAILS.csv',pd.concat(risk_rows,ignore_index=True))
counter=event[(event.C_nonusable==1)|(event.C_B8L2<=event.A_B8L2)|(event.C_B8L2<=event.B_B8L2)]
save(O/'FOCUS_NONPOSITIVE_AND_FAILED_EVENTS.csv.gz',counter)

# Q-rank is semantic, not a class ID. Preserve the exact per-fold lineage.
roles=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
roles=roles[roles.method.eq('OPPJOINT_K4')]
hier=pd.read_csv(W/'analysis/global_parent_links/METHOD_HIERARCHY_ALL_LOBO.csv')
hier=hier[hier.child_method.eq('OPPJOINT_K4')&hier.parent_method.eq('OPPJOINT_K3')]
lineage=[]
for building,g in roles.groupby('heldout_building'):
 parents=hier[hier.heldout_building.eq(building)].set_index('child_class').parent_classes.to_dict()
 for r in g.itertuples():lineage.append(dict(heldout_building=building,child_class=r.class_id,parent_class=parents[r.class_id],
  q_rank=r.q_rank_asc,workers=r.workers,members=r.members,historical_Q_center=r.m_all_B8L2,historical_log_time=r.m_all_log_time))
lineage=pd.DataFrame(lineage);save(O/'OPPJOINT_QRANK_PARENT_LINEAGE.csv',lineage)

# Same XYZ, m6, n12 versus n20: separate change in C from change in its B control.
z=e[e.method.eq('OPPJOINT_K4')&e.scope.eq('primary')&e.m.eq(6)&e.direction_semantic.eq('QT__higher_Q__higher_logtime')]
z=z[z.n.eq(12)].merge(z[z.n.eq(20)],on=['pool_id','source_class','target_class'],suffixes=('_12','_20'))
meta=['pool_id','source_class','target_class','image_12','building_12','block_id_12','event_id_12','event_id_20','D_12','D_20','X_12','Y_12','Z_12']
fields=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','geometry_area_h2','height_mean_h','S_bottom_deg','dir','Hmean','Hcenter','minimum_support','selected_support_min','identity_groups_n','unselected_groups_n','half_vote_nodes']
path=z[meta+[f'{letter}_{f}_{n}' for letter in 'ABC' for f in fields+['team_key'] for n in [12,20]]].copy()
path['same_XYZ']=(z.X_12==z.X_20)&(z.Y_12==z.Y_20)&(z.Z_12==z.Z_20)
path['D12_subset_D20']=[set(a.split('|'))<=set(b.split('|')) for a,b in zip(z.D_12,z.D_20)]
for letter in 'ABC':path[letter+'_Q_n20_minus_n12']=z[letter+'_B8L2_20']-z[letter+'_B8L2_12']
path['CB_Q_n12']=z.C_B8L2_12-z.B_B8L2_12;path['CB_Q_n20']=z.C_B8L2_20-z.B_B8L2_20
path['net_advantage_change']=path.CB_Q_n20-path.CB_Q_n12
save(O/'OPPJOINT_FIXED_BLOCK_N12_N20.csv',path)

q=selected[selected.metric.eq('B8L2')].copy()
columns=['focus_use','n','m','images','buildings','image_mean_same_abs','image_mean_cross_symmetric_abs',
 'image_mean_CA','image_mean_CB','building_mean_CB','images_CB_positive','images_gap_positive']
table=q[columns].copy()
for col in ['n','m']:table[col]=table[col].astype(int)
for col in columns[5:-2]:table[col]=table[col].map(lambda v:f'{v:.3f}')
table.columns=['用途','n','m','图','楼','同细类绝对ΔQ','跨细类绝对ΔQ','图均C−A','图均C−B','楼均C−B','净升质图','跨变化更大图']
report='''# 固定父类完整构成后的细类用途

固定提交 `a476461d7ede8db95da43de4139e612c05e618bc`，真人v2.1，复用现行冻结标签和端点。此处只研究真正的父内细分，25个子→父关系均来自已经核实的同一Ward树切分或原粗细标签，没有把不同K泛称独立分区。

## 1. 实际已完成

13,544个严格ABC事件，88个合法目标池、78图、17栋楼、36,524个去重端点。全部是Manual：原主目标12,136事件，其他已准入目标1,408；本子集没有门洞，不能扩写门洞结论。n为3—26、m为1—8；m7有1,245事件、61图16楼，m8有273事件、56图16楼，是25方法合计，单法和单方向的真实容量另列。

每个事件都满足D相同、人数相同、X/Y同细类、Z另一细类、三块各m且互不重叠；A/B/C的**完整父类人数向量相同**。原始成员、父向量、源/目标历史中心及缺失状态已保存，未改评分、GT或融合。

61个质量、结构、几何、时间和失败指标已全量汇总。`ALL_FINE_CONDITIONS.csv.gz`共135,432条条件/指标记录；不只保留正向条件。`FINE_METHOD_COMMON_POOL_N_M_COMPARISON.csv`另有3,665项方法对的共同目标池/n/m描述；它们的具体父角色、D可能不同，不能当作同背景随机方法试验。每种方法内部的ABC仍是严格同D。

## 2. 值得保留的少数用途

下表统一采用图均；楼均净变化并列。跨类幅度是 (|C−A|+|C−B|)/2，同类幅度是 |B−A|；单边|C−A|也完整保留。质量变化、幅度分离是两个用途。

'''+md(table)+'''

**建议保留以下判断。**

1. OPPJOINT K4可以作为主要联合工作分类。它的q1→q4大块主效应在当前广筛中跨K3父类；不能将全部主效应归给第四类。真正父内方向仍有条件性升质：较高历史Q/较慢的细类在n20/m6净升质7/8图，n26/m3净升质7/9图；但多数图的幅度较小，不能把楼均或单个大例子的收益写成每图典型增益。
2. MSDGEOM K4/K3的父内细分值得保留为补充。复杂结构机会中历史转折较多的细类，n8/m4同时有较多图片升质及更大的跨类变化；n10/m3仍有18/26图跨类变化更大。它利用Manual与Semi几何历史，当前效果只评价Manual。
3. 加scope的MSDGEOM_SCOPE K4/K3在n10/m3主要支持定向升质：15/16图C−A正、12/16图C−B正，而跨类幅度更大仅8/16图。该用途成立，不需要附加声称所有同类都更可互换。
4. RFUSE_GEOMQ K3/K2的n12/m6较多历史复杂融合转折方向是风险用途：跨类变化更大，但Q均下降。它说明细分可识别有代价的方向。TARGET_DSTRUCT K4/K3的n8/m4更多描述变化幅度，不作普遍升质推荐。

这些条件从本轮完整内部比较后选择，是探索采用；标签由目标建筑之外形成，不等于选型过程未见这些材料。当前广筛大多每图/条件只有一组成员块，深入成员/背景扩展以主分类重点条件为准；没有把事件数写成独立样本数。完整反向、无变化、失败及10分损失分母均保留。

## 3. 第四个小慢类有实际组织价值

OPPJOINT K4的ALL名单里，W027/W036/W121三人形成慢小类，历史相对log时间中心1.238、Q中心+2.85；它拆自K3中同时包含26名较快成员的父类。楼外折多数保留相同三人，部分扩成4—5人；VFua折没有相同独立的小慢类。实际逐折定义在 `OPPJOINT_QRANK_PARENT_LINEAGE.csv` 及 `oppjoint_small_slow/FROZEN_SMALL_SLOW_ROLE_BY_FOLD.csv`，不能拿ALL编号替代楼外类别。

已有同团队完整配比结果中，K3→K4的记录时间构成间方差解释由27.84%升到43.60%，Q由11.11%升到12.85%。这是细类增加组织信息，而不是节时比例。

为检验小类的实际作用，又从已存12选6面板提取全部可行m1严格ABC：固定父构成，从快细类取X/Y，换入慢细类Z。27面板、9图8楼、5,157个实际共同D、8,316个无序ABC，13,326个既有端点，**0次新增融合**；n为12、20、24、25、27、28、29。A/B两种方向各半权，来源对只保存一次，避免工号排序制造有符号效应。完整有限面板内穷举，不称为全人员池所有可能团队。

可评分范围内，同细类绝对Q变化楼均0.900，跨细类1.414，8/9图跨类变化更大，但差距绝对量小。换入慢类后Q图均−0.989、楼均−1.064，7/9图下降。实际目标为W015/W027/W121：W121占7图，W015与W027各1图，W036没有可用团队机会。

**时间组织用途主要由W121支持。** 新时间来源可比的5图4楼中，换入W121使记录总时间图均+10.407%、楼均+10.678%，5/5图费时；同支持Q图均−1.016、楼均−1.171，4/5图下降。反向直接AC换成同父快类，真实记录时间比例楼均−8.898%、图均−8.784%，Q楼均+1.171、图均+1.016。反向没有同小类B，不冒充该方向的严格ABC；也不能把正向+10.68%简单翻成−10.68%。

因此保留这个小细类用于时间预算和具体成员替换判断。当前证据支持这些有限面板里的组织选择，不需要三人都能组成大块同类B；也没有声称其他两人都产生与W121相同的效果。记录时间仍是历史作答之和，不是新测生产耗时。

## 4. 人数/背景变化怎样影响细分作用

OPPJOINT父内m6的n12与n20有8个共同目标，同一X/Y/Z全部一致，7/8的D12包含于D20。`OPPJOINT_FIXED_BLOCK_N12_N20.csv`分别给出A、B、C各自变化，不能将净优势变化当作C队升质。

e9z-19最能说明机制：n12→20时C队Q下降1.748，B队下降33.384，B的转折数从6变5而C保持6；因此C−B净优势增加31.636。这说明同一细分在结构临界和背景变化下可能变得很重要，也说明“同类更接近”可能是两支同类队都同样丢结构。当前标量支持此分解；具体对应、票数门槛或连接原因继续由原票账机制材料判别，不仅凭转折数归因。

## 5. 文件与分母

- `FIXED_PARENT_EVENT_METRICS.csv.gz`：全部13,544事件、精确A/B/C和D/X/Y/Z、全部原指标及楼外角色中心。
- `ALL_FINE_CONDITIONS.csv.gz`、`CELL_METRICS.csv.gz`：完整方法/方向/n/m、背景和父内条件结果。前者CA等原列是建筑等权均值。
- `FOCUS_CONDITIONS_ALL_METRICS_BOTH_WEIGHTINGS.csv`：重点条件图均、楼均、图中位数并列；`FOCUS_IMAGE_RESULTS.csv.gz`可直接核对支持比例。
- `QUALITY_TAIL_AND_FAILURE_DENOMINATORS.csv`：真正逐事件质量低尾、10分损失和A/B/C失败，区分三队可比、两队可评和全部事件分母。
- `REGISTERED_FINE_CAPACITY_AND_FAILURES.csv`：真实人数、源/目标容量、成员块/背景覆盖及所有失败。
- `FOCUS_NONPOSITIVE_AND_FAILED_EVENTS.csv.gz`：推荐方向的反向、无提升及失败事件，不只给正例。
- `oppjoint_small_slow/`：慢小类的完整有限m1实验、三队关联及精确反向AC。
- `../fine_increment_analysis.py`、`fine_increment_followup.py`、`build_fine_increment_report.py`、`oppjoint_small_slow_role.py`、`oppjoint_small_slow_reverse.py`：实际代码。

几何方向和质量改善分开评价；时间保留原来源。构成差异、定向质量变化、效率及风险可以分别成立。
'''
(O/'README.md').write_text(report,encoding='utf-8')
small='''# OPPJOINT K4小慢类：有限面板内m1严格ABC

来源角色在目标楼外冻结：每折相对log时间最高、人数≤6、log时间中心≥0.7的类，与它唯一的同父快细类比较。阈值识别已存在的小慢角色，没有按目标质量调类。

`COMMON_BACKGROUND_TARGETS.csv.gz`给出完整D、目标Z及全部可选源成员和端点。`EXACT_UNORDERED_ABC_SOURCE_PAIR_INDICES.csv.gz`每行的source_i/source_j是0起点，指向对应背景行按|分隔的source_workers/source_team_keys；两人分别为X/Y，Z和D已经固定。无序源对只列一次，两种A/B方向各半权。因此有符号BA的总体均值为0，CA/CB相同是设计对称性；同类/跨类绝对变化仍逐真实端点计算。

全部8,316无序三队组合都满足实际换人数1、完整父类人数向量不变。5,157个背景独立作为覆盖单元，先平均其所有源对，再按面板→目标→图片→楼汇总。这里的独立指不同的成员集合背景，不是统计独立抽样假设。

`BACKGROUND_TARGET_METRICS.csv.gz`保留全部质量、结构、几何、时间和失败。时间只有三队完整记录、同一来源时可用；`B8L2_on_time_support`给同时间分母的Q。`SMALL_SLOW_ROLE_SUMMARY.csv`的CA/CB为建筑等权，逐图表可算图均。实际覆盖及无机会面板在 `PANEL_OPPORTUNITY_AND_COVERAGE.csv`。

`REVERSE_DIRECT_AC_TIME_SAME_SUPPORT.csv.gz`保留反向AC的实际时间比，`REVERSE_DIRECT_AC_SUMMARY.json`同时给图均和楼均。反向缺少同小类B，不作严格ABC结论。

原始合法目标、GT、质量及融合均未改变；0新增融合。端点标量和精确成员在 `USED_ENDPOINT_SCALARS_AND_MEMBERS.csv.gz`，全几何仍引用阶段03B主目标库存。未枚举有限面板之外的全人员池组合。
'''
(O/'oppjoint_small_slow/README.md').write_text(small,encoding='utf-8')
(O/'REPORT_COMPLETE.json').write_text(json.dumps(dict(focus_conditions=len(spec),full_metrics=61,fixed_parent_events=len(e),
 source_scope='manual, primary and other admitted targets; no doorway events',new_fusions=0,report_weights='image and building means explicitly separate'),indent=2))
print(json.dumps(dict(focus_conditions=len(spec),selected_metric_rows=len(selected),focus_events=len(event),counterevents=len(counter))),flush=True)
