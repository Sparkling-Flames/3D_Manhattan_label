"""Explain exact, same-final-pool priority marginals on admitted small targets."""
from pathlib import Path
import gzip,json,os
import numpy as np,pandas as pd

W=Path(__file__).resolve().parents[2];C=W/'composition';O=C/'small_pool_policy_results';O.mkdir(exist_ok=True)
def save(p,d):
 b=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 t=p.with_name(p.name+'.writing')
 with t.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 t.replace(p)
def md(d):return '\n'.join(['| '+' | '.join(d.columns)+' |','| '+' | '.join(['---']*len(d.columns))+' |']+['| '+' | '.join(map(str,r))+' |' for r in d.itertuples(index=False,name=None)])

summaries=[];n_summaries=[];strata=[];unknown=[];natural=[]
for condition in ['manual','semi']:
 root=C/f'exact_small_pool_policies_{condition}'
 p=pd.read_csv(root/'PRE_FULL_POOL_AVERAGE_DIFFERENCES.csv')
 gkeys=['method','policy','condition','image','building','metric','time_source']
 im=p.groupby(gkeys,dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index()
 s=pd.read_csv(root/'POLICY_SUMMARY.csv')
 sign=im.groupby(['method','policy','condition','metric','time_source'],dropna=False).agg(
   negative_images=('mean_minus_natural',lambda v:int(v.lt(-1e-9).sum())),
   no_change_images=('mean_minus_natural',lambda v:int(v.abs().le(1e-9).sum())),
   positive_images_tol=('mean_minus_natural',lambda v:int(v.gt(1e-9).sum()))).reset_index()
 summaries.append(s.merge(sign,on=['method','policy','condition','metric','time_source'],validate='one_to_one'))
 paired=pd.read_csv(root/'PAIRED_SAME_POOL_PREFIX_DIFFERENCES.csv.gz',low_memory=False)
 early=paired[paired.n.lt(paired.pool_n)].copy()
 for axis in ['n','geometric_challenge']:
  # n-specific -> target -> image -> building, with source-specific time.
  group=['method','policy','condition','metric','time_source',axis]
  pp=early.groupby(group+['pool_id','image','building'],dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index()
  ii=pp.groupby(group+['image','building'],dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index()
  bb=ii.groupby(group+['building'],dropna=False)[['mean_minus_natural','sd_minus_natural','p10_minus_natural']].mean().reset_index()
  m=bb.groupby(group,dropna=False).mean(numeric_only=True).reset_index()
  count=ii.groupby(group,dropna=False).agg(images=('image','nunique'),buildings=('building','nunique'),valid_images=('mean_minus_natural','count')).reset_index()
  m=m.merge(count,on=group,validate='one_to_one')
  (n_summaries if axis=='n' else strata).append(m)
 groups=pd.read_csv(root/'HISTORICAL_ROLE_PRIORITY_GROUPS.csv.gz')
 k=['pool_id','image','building','condition','method','policy','pool_n']
 groups['group_n']=groups.workers.fillna('').map(lambda s:len(s.split('|')) if s else 0)
 for keys,rr in groups.groupby(k,dropna=False):
  u=rr[rr.unknown_history_group]
  unknown.append(dict(zip(k,keys),unknown_people=int(u.group_n.sum()),
    unknown_workers='|'.join(u.workers.fillna('')),known_priority_levels=int((~rr.unknown_history_group).sum())))
 stats=pd.read_csv(root/'POLICY_PREFIX_DISTRIBUTIONS.csv.gz',low_memory=False)
 natural.append(stats[stats.policy.eq('natural')])

combined=pd.concat(summaries,ignore_index=True);save(O/'ALL_POLICIES_SUMMARY.csv',combined)
save(O/'BY_PREFIX_SIZE.csv',pd.concat(n_summaries,ignore_index=True))
save(O/'BY_TARGET_GEOMETRIC_CONDITION.csv',pd.concat(strata,ignore_index=True))
save(O/'UNKNOWN_HISTORY_PRIORITY_SUPPORT.csv',pd.DataFrame(unknown))
save(O/'EXACT_NATURAL_PREFIX_MARGINALS.csv.gz',pd.concat(natural,ignore_index=True))
q=combined[combined.condition.eq('manual')&combined.metric.eq('B8L2')].copy()
q=q[['method','policy','mean_image','mean_building','positive_images_tol','negative_images','no_change_images','mean_low_tail_difference','mean_sd_difference']]
for col in ['mean_image','mean_building','mean_low_tail_difference','mean_sd_difference']:q[col]=q[col].map(lambda x:f'{x:+.3f}')
q.columns=['方法','楼外角色优先','图均ΔQ','楼均ΔQ','正向图','反向图','不变图','图均Δp10','图均ΔSD']
report='''# 已准入小目标：同一最终人员池的精确进入策略

固定提交 `a476461d7ede8db95da43de4139e612c05e618bc`，真人v2.1。这个用途在分类及换类主实验之后单独保存；全部21个小池原已完成子集融合，本节只重汇总，新增融合为0。

## 设计与实际范围

20个Manual合法目标池，N=3—9，共1,081个端点；其中5池N3只有唯一全员终点，15池具有n<N过程，共14张图、8栋楼。另有1个Semi合法目标池N4、5个端点，效果单独计算。所有比较从n3开始，契合本轮端点库存；不把缺少n1/2写成已算。

自然随机进入时，每个n所有N选n成员集合等概率。某历史角色优先时，先全部选入更早角色，在当前角色内等概率选足n，其余角色后置。这正好是所有符合该角色优先约束的无放回随机排列的逐n边际；无需重复融合N!条顺序。未知类别或未知角色历史明确后置，不补零。Manual的7个候选使用各自楼外角色中心，Semi使用自身4法、自己的历史中心；目标楼在两条件历史中按既定标签规则排除。

**最终池完全相同，所以n=N逐项相等。** 这里研究前段改善速度、低尾和顺序波动；不估计跨n路径相关性，不冒充旧256自然序列或旧V3的32条配对路径。N11以上只有单n面板，没有拼造成新人数曲线。

## 全部Manual候选结果

每个目标先对n=3…N−1等权平均，再按图片/建筑汇总。正/反/不变图均保留，数值容差1e−9。Q及p10只在对应可评分集合上计算，失败率另用全部可能团队分母报告。SD是精确有限策略分布的标准差；确定性单队策略SD为0，但不据此声称有可替换成员。

'''+md(q)+'''

**用途判断：**RFUSE_GEOM_K3的高历史Q角色和较多转折角色在这批小目标的前段更常提高Q，均为10/14图正向；高Q优先图均+2.322、楼均+2.229，p10图均+9.979，失败率图均减少1.184个百分点。相反，同分类的快角色优先图均Q−3.954，支持具体质量代价的用途。DSTRUCT/目标扩展DSTRUCT的均值提升更大，但正向图数只有6/14，多张图所有人同角色而完全不变；不能只按均值排出唯一优胜。

这些是小合法目标上的进入策略候选用途，不据此选择整个主分类。RFUSE高Q角色也更常增加记录劳动时间，新时间来源可比子集中图均约+58.09秒；快角色的时间均值约−21.11秒，覆盖范围各自列明。这里只是已存作答记录之和，不是本轮重新测量的生产耗时；完整分源结果见 `ALL_POLICIES_SUMMARY.csv`。未知时间始终保留缺失。

Semi仅uNb-68一个新增空间：自身结构细类的多转折优先在n3比自然均值低0.367分，其余策略相同或几乎不变；n4全部相同。保留这一个小规模结果，不扩大成Semi普遍进入策略建议。

## 条件与文件

其它目标的正式难度沿用“未分级”；这里按目标自身可计算的结构条件分层，不复制同图主目标难度。`BY_TARGET_GEOMETRIC_CONDITION.csv` 是这种分层，`BY_PREFIX_SIZE.csv` 同时保留每个人数的实际图片覆盖。

- `ALL_POLICIES_SUMMARY.csv`：全部7×3 Manual与4×3 Semi方法/策略、全质量和几何/时间/失败指标，分母和正反比例。
- `EXACT_NATURAL_PREFIX_MARGINALS.csv.gz`：同最终小池的自然随机精确边际。
- `UNKNOWN_HISTORY_PRIORITY_SUPPORT.csv`：每个池/方法/策略未知历史成员，保持可追溯。
- `../exact_small_pool_policies_manual/`、`../exact_small_pool_policies_semi/`：完整逐n分布、精确端点概率关联、楼外角色排序、同池配对差与完成凭证。
- `../code/exact_small_pool_entry_policies.py`：实际计算；`build_small_pool_policy_note.py`：本说明和分层表。
- 端点及完整几何复用阶段03A，不重复打包。
'''
(O/'README.md').write_text(report,encoding='utf-8')
(O/'COMPLETE.json').write_text(json.dumps(dict(manual_methods=7,semi_methods=4,policies=3,
    manual_pools=20,semi_pools=1,unique_endpoints=1086,new_fusions=0,all_final_pools_equal=True),indent=2))
print(json.dumps(dict(summary_rows=len(combined),manual_q_comparisons=len(q),complete=True)))
