#!/usr/bin/env python3
"""Extract usable direct-AC large-team results, keeping phases explicit."""
from pathlib import Path
import importlib.util
import pandas as pd

ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'analysis/large_team_ac_tail'
spec=importlib.util.spec_from_file_location('size_findings',ROOT/'analysis/size_paths/code/write_size_findings.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
h=helper.h;md=helper.md

def main():
 n=pd.read_csv(OUT/'FIXED_N35_BY_N_SUMMARY.csv.gz');k=pd.read_csv(OUT/'CURVE_BY_K_SUMMARY.csv.gz');b=pd.read_csv(OUT/'FROM_STRICT_TAIL_BY_K_SUMMARY.csv.gz')
 e=pd.read_csv(ROOT/'results/large_team_ac_tail/EVENT_METRICS.csv.gz',low_memory=False)
 def extract(summary,axis,cohort):
  z=summary[(summary.cohort==cohort)&summary.phase.isin(['ALL_PHASES','selection_heldout_building'])&summary.difficulty.eq('ALL')]
  metrics=['B8L2_CA','B8L2_abs_CA','A_B8L2','C_B8L2','D10_CA','IoU3D100_CA','iou_2d_CA','nodes_CA','matched_ref_top_abs_deg_CA','matched_ref_bottom_abs_deg_CA','C_failed','C_failure_or_loss10_CA']
  w=z[z.metric.isin(metrics)].pivot(index=['method','phase',axis],columns='metric',values='image_equal').reset_index();w.columns.name=None
  q=z[z.metric.eq('B8L2_CA')].set_index(['method','phase',axis])
  w['positive_images/valid_images']=[f"{int(q.loc[(row['method'],row['phase'],row[axis]),'positive_images'])}/{int(q.loc[(row['method'],row['phase'],row[axis]),'valid_images'])}" for row in w.to_dict('records')]
  w['positive_buildings/valid_buildings']=[f"{int(q.loc[(row['method'],row['phase'],row[axis]),'positive_buildings'])}/{int(q.loc[(row['method'],row['phase'],row[axis]),'valid_buildings'])}" for row in w.to_dict('records')]
  return w
 nt=extract(n,'n','fixed_pool_N35');kt=extract(k,'tail_step','all_fixed_anchors_by_k');h.save_csv(nt,OUT/'KEY_N35_AC_CONDITIONS.csv');h.save_csv(kt,OUT/'KEY_ALL_CAPACITY_AC_CONDITIONS.csv')
 failures=[]
 for cohort,g0 in [('all_fixed_anchors_by_k',e),('fixed_pool_N35',e[e.pool_n.eq(35)])]:
  g0=pd.concat([g0.assign(summary_phase=g0.phase),g0.assign(summary_phase='ALL_PHASES')])
  for (method,phase,ks),g in g0.groupby(['method','summary_phase','tail_step']):
   row=dict(cohort=cohort,method=method,phase=phase,tail_step=ks,n_min=int(g.n.min()),n_max=int(g.n.max()),paths=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique())
   for arm in 'AC':
    flag=h.truth(g[arm+'_failed']);row[arm+'_failure_events']=int(flag.sum());row[arm+'_failure_unique_endpoints']=g.loc[flag.eq(1),arm+'_team_key'].nunique();row[arm+'_unique_endpoints']=g[arm+'_team_key'].nunique()
   for metric in ['C_loss10_CA','C_failure_or_loss10_CA']:
    value=h.num(g[metric]);row[metric+'_events']=int(value.sum());row[metric+'_valid_events']=int(value.notna().sum())
   failures.append(row)
 fail=pd.DataFrame(failures);h.save_csv(fail,OUT/'KEY_AC_FAILURE_COUNTS.csv')
 keep=['A_change_B8L2','C_change_B8L2','CA_change_B8L2','joint_AC_A_change_B8L2','joint_AC_C_change_B8L2','joint_AC_CA_change_B8L2','C_change_nodes','C_new_failure_or_loss10_given_previously_scored']
 z=b[b.tail_step.eq(7)&b.phase.isin(['ALL_PHASES','selection_heldout_building'])&b.difficulty.eq('ALL')&b.metric.isin(keep)]
 motion=z.pivot(index=['cohort','method','phase'],columns='metric',values='image_equal').reset_index();motion.columns.name=None;h.save_csv(motion,OUT/'KEY_AC_PER_ARM_MOVEMENT.csv')
 # Scientific plot of the complete fixed-N35 curve, not only selected n.
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 methods=sorted(nt.method.unique());fig,axs=plt.subplots(len(methods),2,figsize=(11,7),squeeze=False)
 for i,method in enumerate(methods):
  for phase,label,style in [('ALL_PHASES','All stages','-'),('selection_heldout_building','Heldout buildings','--')]:
   z=nt[(nt.method==method)&(nt.phase==phase)].sort_values('n')
   axs[i,0].plot(z.n,z.B8L2_CA,style,marker='o',label=label)
   axs[i,1].plot(z.n,z.A_B8L2,style,marker='.',label=label+' A')
   axs[i,1].plot(z.n,z.C_B8L2,style,marker='.',label=label+' C')
  for j in range(2):axs[i,j].set_xlabel('n, fixed pool N=35; m=7');axs[i,j].grid(alpha=.25);axs[i,j].legend(fontsize=8)
  axs[i,0].set_title(method+' signed C - A');axs[i,1].set_title(method+' actual A / C scores')
 fig.suptitle('Direct AC tail; original source-class Y members enter common background');fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(OUT/'AC_TAIL_Q_CURVES.png',dpi=180);fig.savefig(OUT/'AC_TAIL_Q_CURVES.svg');plt.close(fig)
 show=['method','phase','n','B8L2_CA','B8L2_abs_CA','positive_images/valid_images','positive_buildings/valid_buildings']
 ns=nt[nt.n.isin([21,24,26,28])][show]
 ks=kt[kt.tail_step.isin([0,7])][['method','phase','tail_step','B8L2_CA','B8L2_abs_CA','positive_images/valid_images','positive_buildings/valid_buildings']]
 nf=fail[(fail.cohort=='fixed_pool_N35')&fail.tail_step.eq(7)&fail.phase.isin(['ALL_PHASES','selection_heldout_building'])][['method','phase','paths','A_failure_events','C_failure_events','C_failure_unique_endpoints','C_failure_or_loss10_CA_events','C_failure_or_loss10_CA_valid_events']]
 qq=nt[nt.n.eq(28)][['method','phase','D10_CA','IoU3D100_CA','iou_2d_CA','nodes_CA','matched_ref_top_abs_deg_CA','matched_ref_bottom_abs_deg_CA']]
 text=f'''# 固定7人换类块延伸至大团队：直接 AC 结果

## 采用判断

**大团队仍存在可用的换类方向。** 固定 N35 人员池，DSTRUCT_K3 的原 X7 与目标 Z7 不变，把原 Y7 源类人员逐步加入共同背景，n28 时两队共同背景有21人、实际替换7人（团队的25%）。在全部研究阶段，该方向平均 C−A 为 +2.868 Q，51/57可评图片、17/20楼正向；在选型保留建筑子域为 +4.016 Q，25/26图、9/10楼正向，52个注册事件中的C失败或相对A下降10分均为0。建议把 **n28/m7 的 DSTRUCT 方向保留为大背景中的定向质量用途**。

这不等于 n28 同类/跨类幅度已得到证明。严格 ABC 在该池容量下到 n21；Y 进入背景后 B 不再存在，本目录只有直接 AC。n21 的同/跨幅度证据应回到 `analysis/size_paths/`。

联合 Scope 方向在 n28 同样有正向质量结果：全部 N35 队列平均 +3.868 Q、37/39图正向；保留楼 +5.081 Q、14/14可评图和7/7楼正向。不过保留楼28事件有1次C融合失败；n22/n24/n26也出现失败。**按大团队升质候选保留，同时单列失败风险，不因为可评均值较高而忽略失效队伍。**

## 完成范围与设计身份

286条路径、2288个直接AC事件、2002个相邻步骤、90图22楼，底层真人v2。共4392个去重端点；其中572个复用严格路径末端，3820个登记集合由执行阶段补算。每路径k0…7全部完成，n实际从16至28；没有查看效果来选择进入顺序。

原 X7/Z7 始终固定，每次同一个原 Y7 源类人员进入 A/C 的共同背景。m恒7，不是“每步换1人”；逐步加背景与 A/C 间的7人替换是两个不同概念。路径覆盖1/7!的Y顺序，各k的具体可行背景子集数保存在设计中。n28仍不等于全员35人唯一终点，两队分别保留不同7人块。

## 固定 N35 队列：全部阶段与保留楼并置

图片内先平均注册路径，再图片等权。CA采用两队可评分的队对；失败仍在注册分母与下表之外的专门失败表中。各阶段分开，不能把全部阶段覆盖称为未参与选型的建筑覆盖。

{md(ns)}

完整n21…28都在 `KEY_N35_AC_CONDITIONS.csv` 与图中。DSTRUCT保留楼从n21的+5.826缩到n28的+4.016；方向保留，净优势有所减弱。联合Scope不单调；有些n的均值会受具体成员、几何变化和失败可评分分母影响。

## 全部容量路径：相同286锚点的 k0 与 k7

各图片的实际池大小不同，k0为各自N−14、k7为N−7；这个比较保持全部锚点，回答原Y全部加入背景后的变化，不能和上面的固定N35人数曲线混为同一个估计。

{md(ks)}

## C 自身变化与 CA 差的变化

相对各自严格ABC末端的k7变化：

{md(motion)}

普通A/C自身变化各用可用队对；`joint_AC_*` 三列严格同分母，满足 CA变化=C变化−A变化。不能把CA均值增长直接称为C升质，或把CA缩小全部解释成C变差。完整逐步结果保留每一步的新进入者、前后端点和失败/恢复。

## n28质量分项

{md(qq)}

上下界绝对角度误差的负CA表示改善。n28仍有边界位置和三维差异，平均节点数变化较小；因此剩余作用并非仅是“画出更多节点”。具体结构正确与否须结合原图和已保存的投票/连接案例。

## n28失败与明显损失：精确事件计数

{md(nf)}

同一终点可能在不同锚点复用，完整表同时给唯一端点分母，事件数不冒充独立证据。C失败没有填0分。全部阶段DSTRUCT仍有个别相对A超过10分的质量损失；保留楼子域在此n28范围没有这类损失，这两条都保留。

## 时间与适用范围

本尾段每次给A/C加入同一个人的原库存记录时间。固定X/Z的绝对CA秒差不随人数变化；百分比时间差随共同分母扩大。该路径不产生新的生产计时，也不是节时方向的重新发现。

这里只评价普通Manual、已具备对应源/目标容量的原锚点、上述历史角色方向。楼外标签与原阶段身份全部保留。部分困难图N不足35，已在全部容量k结果保留，不应从N35子域外推“所有困难图大团队均改善”。

## 可接续文件

- `KEY_N35_AC_CONDITIONS.csv`：实际n21…28、全部阶段与保留楼。
- `KEY_ALL_CAPACITY_AC_CONDITIONS.csv`：全部固定锚点k0…7。
- `KEY_AC_PER_ARM_MOVEMENT.csv`、`KEY_AC_FAILURE_COUNTS.csv`：自身/净变化与失败真实分母。
- `CURVE_BY_K_*`、`FIXED_N35_BY_N_*`：完整指标逐图、逐楼与汇总。
- `FROM_STRICT_TAIL_EXACT.csv.gz`、`STEP_EXACT.csv.gz`、`PATH_EVENT_MEASURES.csv.gz`：精确关联和可重聚合指标。
- `AC_TAIL_Q_CURVES.png`/`.svg`：完整固定N35曲线。
- `design/large_team_ac_tail/EVENTS_EXACT.csv.gz`：精确D/X/Z、原Y及进入顺序、A/C成员与端点。

同类/跨类区分度的正式结论仍由严格ABC提供；本目录补足“相同7人类别块在更大共同背景里是否还改变结果”。
'''
 (OUT/'FINDINGS.md').write_text(text,encoding='utf-8')
 h.save_csv(pd.DataFrame([dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=h.sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.csv' and not p.name.endswith('_LOG.txt') and '__pycache__' not in str(p)]),OUT/'FILE_MANIFEST.csv')
 print('Saved complete direct-AC large-team findings and extracts.')

if __name__=='__main__':main()
