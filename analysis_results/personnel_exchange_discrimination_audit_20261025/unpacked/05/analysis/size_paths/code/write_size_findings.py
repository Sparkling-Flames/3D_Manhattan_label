#!/usr/bin/env python3
"""Readable, reproducible extracts from completed fixed-block size analysis."""
from pathlib import Path
import importlib.util,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'analysis/size_paths'
sp=importlib.util.spec_from_file_location('h',OUT/'code/analyze_fixed_block_paths.py');h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)

def md(d):
 def val(x):
  if pd.isna(x):return '未知'
  if isinstance(x,(float,np.floating)):return f'{x:.3f}'
  return str(x)
 rows=['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']
 rows+=['| '+' | '.join(val(x) for x in r)+' |' for r in d.itertuples(index=False,name=None)]
 return '\n'.join(rows)

def main():
 s=pd.read_csv(OUT/'CURVE_SUMMARY.csv.gz');b=pd.read_csv(OUT/'FROM_N10_SUMMARY.csv.gz');th=pd.read_csv(OUT/'THRESHOLD_GROUP_SUMMARY.csv.gz')
 e=pd.read_csv(ROOT/'results/size_paths/EVENT_METRICS.csv.gz',low_memory=False);paths=pd.read_csv(ROOT/'design/size_paths/ANCHOR_PATHS.csv.gz')
 step=pd.read_csv(OUT/'PATH_STEP_CHANGES.csv.gz',low_memory=False)
 wanted=[10,12,14,16,20,21];key=s[s.n.isin(wanted)].copy();h.save_csv(key,OUT/'KEY_SCALE_METRICS.csv.gz')
 def table(phase,cohort='fixed_capacity_n21',difficulty='ALL',ns=[10,14,20,21]):
  z=s[(s.cohort==cohort)&(s.phase==phase)&(s.difficulty==difficulty)&s.n.isin(ns)]
  metrics=['B8L2_within','B8L2_cross','B8L2_CA','B8L2_CB'];w=z[z.metric.isin(metrics)].pivot(index=['method','n'],columns='metric',values='image_equal').reset_index();w.columns.name=None
  g=z[z.metric.eq('B8L2_gap')].set_index(['method','n']);ca=z[z.metric.eq('B8L2_CA')].set_index(['method','n'])
  w['跨幅更大图/楼']=[f"{int(g.loc[(r.method,r.n),'positive_images'])}/{int(g.loc[(r.method,r.n),'valid_images'])}; {int(g.loc[(r.method,r.n),'positive_buildings'])}/{int(g.loc[(r.method,r.n),'valid_buildings'])}" for r in w.itertuples()]
  w['CA正向图/楼']=[f"{int(ca.loc[(r.method,r.n),'positive_images'])}/{int(ca.loc[(r.method,r.n),'valid_images'])}; {int(ca.loc[(r.method,r.n),'positive_buildings'])}/{int(ca.loc[(r.method,r.n),'valid_buildings'])}" for r in w.itertuples()]
  return w.rename(columns={'method':'方法','n':'n','B8L2_within':'同类幅度','B8L2_cross':'跨类幅度','B8L2_CA':'C−A','B8L2_CB':'C−B'})
 alltable=table('ALL_PHASES');held=table('selection_heldout_building');h.save_csv(alltable,OUT/'KEY_FIXED_N21_ALL_PHASES.csv');h.save_csv(held,OUT/'KEY_FIXED_N21_HELDOUT_BUILDINGS.csv')
 z=b[(b.cohort=='fixed_capacity_n21')&(b.phase=='ALL_PHASES')&(b.difficulty=='ALL')&(b.n==21)]
 metrics=['A_change_B8L2','B_change_B8L2','C_change_B8L2','joint_BC_B_change_B8L2','joint_BC_C_change_B8L2','joint_BC_CB_change_B8L2','C_change_nodes']
 motion=z[z.metric.isin(metrics)].pivot(index='method',columns='metric',values='image_equal').reset_index();motion.columns.name=None;h.save_csv(motion,OUT/'KEY_N21_VS_N10_PER_ARM.csv')
 t=th[(th.cohort=='fixed_capacity_n21')&(th.phase=='ALL_PHASES')&(th.difficulty=='ALL')&th.metric.isin(['C_change_B8L2','C_change_nodes','C_change_floor_turn5_n'])].pivot(index=['method','threshold_group'],columns='metric',values='image_equal').reset_index();t.columns.name=None
 diffs=[]
 for diff in ['简单','中等','困难']:
  z=table('ALL_PHASES','all_available',diff,[10,14]);z.insert(1,'难度',diff);diffs.append(z)
 difficulty=pd.concat(diffs,ignore_index=True);h.save_csv(difficulty,OUT/'KEY_DIFFICULTY_ALL_AVAILABLE.csv')
 sub=s[(s.cohort=='fixed_capacity_n21')&(s.phase=='ALL_PHASES')&(s.difficulty=='ALL')&s.n.isin([14,21])]
 quality=['D10_CA','IoU3D100_CA','iou_2d_CA','nodes_CA','matched_ref_top_abs_deg_CA','matched_ref_bottom_abs_deg_CA']
 q=sub[sub.metric.isin(quality)].pivot(index=['method','n'],columns='metric',values='image_equal').reset_index();q.columns.name=None
 # Exact path-level denominators alongside equal-image summary percentages.
 ids=set(paths.loc[paths.max_n.ge(21),'path_id']);reg=e[e.path_id.isin(ids)&e.n.isin([10,14,20,21])].copy();fail=[]
 for (method,phase,n),g in pd.concat([reg.assign(summary_phase=reg.phase),reg.assign(summary_phase='ALL_PHASES')]).groupby(['method','summary_phase','n']):
  row=dict(method=method,phase=phase,n=n,paths=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique())
  for arm in 'ABC':row[arm+'_failed']=int(h.truth(g[arm+'_failed']).sum())
  for c in ['C_loss10_CA','C_failure_or_loss10_CA','C_loss10_CB','C_failure_or_loss10_CB']:
   v=h.num(g[c]);row[c+'_events']=int(v.sum());row[c+'_valid_events']=int(v.notna().sum())
  fail.append(row)
 fail=pd.DataFrame(fail);h.save_csv(fail,OUT/'KEY_FAILURE_AND_LARGE_LOSS_COUNTS.csv')
 failures=fail[fail.phase.eq('ALL_PHASES')][['method','n','paths','A_failed','B_failed','C_failed','C_failure_or_loss10_CA_events','C_failure_or_loss10_CA_valid_events']]
 # Cases illustrate the completed average findings, selected after outcomes.
 cases=[]
 for method in sorted(step.method.unique()):
  z=step[(step.method==method)&step.phase.eq('selection_heldout_building')]
  for reason,sub in [('threshold_increase_C_loss',z[z.nominal_threshold_change.gt(0)&z.C_change_B8L2.lt(-10)].sort_values('C_change_B8L2').head(2)),
                     ('unchanged_threshold_C_gain',z[z.nominal_threshold_change.eq(0)&z.C_change_B8L2.gt(10)].sort_values('C_change_B8L2',ascending=False).head(1))]:
   sub=sub.copy();sub['case_selection_reason']=reason;cases.append(sub)
 case=pd.concat(cases,ignore_index=True);h.save_csv(case,OUT/'MECHANISM_STEP_CANDIDATES.csv.gz')
 support=paths.groupby('method').agg(paths=('path_id','nunique'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
 fixed=paths[paths.max_n.ge(21)].groupby('method').agg(paths=('path_id','nunique'),images=('pool_id','nunique'),buildings=('building','nunique')).reset_index()
 text=f'''# 固定换类块的规模路径：已完成结果与采用判断

## 判断

固定 X7/Y7/Z7 后，同一组人逐人加入共同背景，**类别差异不会在 n20 自动消失，也没有“人数越多、效果越大”的规律**。DSTRUCT_K3 在固定 n21 容量队列中，n20/n21 的跨类 Q 幅度仍分别约为同类的 1.71/2.10 倍；MSDGEOM_SCOPE_K4 在 n14 的分离更清楚，n20 明显收缩、n21 又扩大。各 n 都保留，不按某一个局部高点宣布普遍最优人数。

本实验的方向都是由楼外历史确定的“转折响应更多、历史 Q 较高”目标角色；具体折中源类编号可能不同。**建议采用 DSTRUCT_K3 的 m7、n10 至 n21 作为有用的规模条件族；联合 Scope 方案保留 n11 至 n16 的清楚分离和 n20/n21 的衰减/回升作为条件性发现。** 最终规模要与需要的替换比例和背景支持一起选，不把 n14 或 n21 的局部结果当作全数据搜索最优点。此处仅补固定块路径，其他 m 的采用判断仍须联读主实验。

## 完成范围

共 286 条固定块路径、3264 个严格 ABC 事件、2978 个相邻 n 步；全部 9792 个去重端点已有指标。n10 引用既有端点，8934 个 n>10 端点由本轮执行阶段补算。本目录只重新汇总，不执行融合。原队 A、同类替换 B、跨类替换 C 的精确成员均可回到 `design/size_paths/EVENTS_EXACT.csv.gz`。普通 Manual，90 图22楼；未混入 Semi 或特殊范围。

全部容量：

{md(support)}

固定 n21 容量队列（下列主要曲线保持这组路径，不能因失败而换队列）：

{md(fixed)}

## 同类与跨类、方向和支持

下表先图片内平均路径，再图片等权。幅度比较只用同一事件三队均可评的部分，CA/CB 用各自可评的队对，因此不同列有各自分母。跨幅更大图/楼是每张图/每栋楼的**均值幅度差为正**，不是只计个别漂亮事件。

### 所有研究阶段合并：固定 n21 容量队列

{md(alltable)}

### 选型保留建筑：同一容量队列的独立子域

以下只取 `selection_heldout_building`。这部分建筑未用于本轮按屏幕结果选取方向；楼外建类仍另外保证目标建筑不进入本折历史。它是反复使用 v2 材料中的内部保留检查，不称为外部盲测。全部阶段覆盖与这部分覆盖不互换。

{md(held)}

## 净优势缩小，有多少是 C 自身下降？

固定 n21 队列的 n21−n10：

{md(motion)}

`C_change_B8L2` 是 C 自身变化，`joint_BC_*` 三列同时要求 B、C 在两个人数都可评，严格满足净优势变化=C自身变化−B自身变化。不同有效分母下的普通 B/C 均值不可强行相减。本结果显示加背景并非只让 A/B 追近，C 本身也有下降与节点减少；因此不能把“净优势改变”简化为 C 升质或降质的全部来源。

## 质量分项和形状

{md(q)}

上下界绝对角度误差的负 CA 表示减少。多数简单图不增加节点，仍能因位置/边界更接近参考获得质量变化；较复杂图才更常出现转折补充或丢失。节点增多本身不等于正确，需结合具体机会和已有机制案例。

## 难度：保留全部可行图，避免最大容量筛掉困难图

固定 n21 队列中只有少数困难图具备完整容量，所以难度主呈现使用各 n 全部可行路径；n10/n14 这两点仍有相同的注册容量。如下：

{md(difficulty)}

困难图的绝对 Q 变化较大，方向与幅度更容易受局部结构影响。它不意味着所有困难图都同向，也不能用仅 2—3 张可评分困难图的 n21 分层当作广覆盖结论。逐 n 全表保留实际图/楼分母。

## 门槛与共同背景

固定 n21 队列，相邻步骤先在路径内平均、再图片平均：

{md(t)}

增加名义门槛的步骤中，C 的节点/非冗余转折平均减少；门槛不增加的步骤平均略有补回。这符合局部支持票相对于门槛变化的机制，但每步也加入了一个真实背景成员，因此不能单凭奇偶差宣称纯门槛因果。n15 起，Z7 即使某节点七人全支持，也需要 D 中额外票才能达到名义门槛；实际对应、每个人的投票以及连接仍要看保存案例。

已保存 `MECHANISM_STEP_CANDIDATES.csv.gz` 供机制图使用。保留楼 jh4fc5c5qoQ-12 的一个 DSTRUCT 路径在 n14→15 加入 W117 后，C Q下降约51.13、少2节点；同图另一成员路径也出现约50.65下降。反例属于可定位的结构风险，保留上述多数图片的方向发现。

## 失败和明显损失

固定 n21 容量队列的精确事件计数（不是图片等权百分比）：

{md(failures)}

失败不会被赋 Q=0，也不会从注册分母删除。完整表还给 CB 比较、新增失败/恢复与 C 自身相对 n10 的超过10分损失。记录总时间使用原库存 source 秒；同一个人进入三队，CA/CB绝对秒差保持不变（浮点误差小于2e−12秒），百分比差随共同背景增长而稀释。这条规模路径不提供额外生产计时证据。

## 文件入口

- `SCALE_CONDITION_COMPARISON.csv`：全部n、阶段、队列与难度的采用宽表。
- `KEY_FIXED_N21_ALL_PHASES.csv`、`KEY_FIXED_N21_HELDOUT_BUILDINGS.csv`：上述总体与保留楼表。
- `CURVE_*`、`FROM_N10_*`、`STEP_*`：完整逐图/楼与质量各分项。
- `PATH_EVENT_MEASURES.csv.gz`、`PATH_BASELINE_CHANGES.csv.gz`、`PATH_STEP_CHANGES.csv.gz`：精确事件/路径关联及派生量。
- `THRESHOLD_GROUP_*`、`THRESHOLD_ENTRANT_ROLE_*`：门槛与进入者角色。
- `KEY_FAILURE_AND_LARGE_LOSS_COUNTS.csv`、`TIME_ADDITIVITY_CHECK.csv`：失败与记录时间分母。
- `FIXED_N21_Q_CURVES.png`/`.svg`：同一容量队列的完整曲线。

大团队 n>N−14 的延伸另存 `analysis/large_team_ac_tail/`；那里仅有直接 AC，不能混作严格 ABC 的同类/跨类幅度证据。
'''
 (OUT/'FINDINGS.md').write_text(text,encoding='utf-8')
 files=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=h.sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.csv' and not p.name.endswith('_LOG.txt') and '__pycache__' not in str(p)]
 h.save_csv(pd.DataFrame(files),OUT/'FILE_MANIFEST.csv');print('Saved readable size-path findings and exact extracts.')

if __name__=='__main__':main()
