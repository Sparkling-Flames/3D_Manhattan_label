from pathlib import Path
import pandas as pd,json
O=Path(__file__).parent;D=O/'corner_core';df=pd.read_csv(D/'CORNER_INDEPENDENT_BOOTSTRAP.csv');r=json.load(open(D/'CORNER_STATISTICS_RECEIPT.json'))
text="""# 原冻结类别：同点数连续对应角点距离独立复查

## 结论与验收范围

新增距离证据支持部分原类别在特定背景与替换块规模下的平均几何分离；不能仅凭跨类变化较大宣布“好分类”。必须同时看类内绝对位移、最大角点位移、相对尺度、逐事件方向比例、完整结构风险和真实参考下的质量。

独立核验2,170条带replay_group的ABC记录、4,340个队对、17,571个逐角点记录。逐点BEV=sqrt(dx²+dz²)、顶部3D=sqrt(dx²+dz²+dh²)，以及队对均值/最大值均与输出一致，最大误差8.89e−16。缺失连续值均为null，没有补零。实际只有2,054个不同event_id；W132组复用了116个主事件，不能加作新独立实验。1,866条组内记录两边均有唯一对应，其余仍保留在完整尝试分母。

h是相机高度单位，不是米。这里的同点数指最终原始点对数；唯一环对应是候选，不代表语义转角已经人工证实相同。环方向规范只改变对应索引，不对几何做对齐或缩放。四个人审示例没有用于训练全局相近阈值，因此目前无法把下列数值一概称为“足够小”。

## 统计表

均值先在图内平均，再楼内图等权、楼等权。角点最大值是先每队对取最大，再按此层级平均，并非全数据最大值。
“跨更大%”同时给层级加权比例和原始共同事件比例。楼方向为差值正/负/零的建筑数。
下列区间是50,000次建筑簇重抽样的经验百分位区间，只有5–6楼，条件于选定旧v2数据；不校正搜索、多重比较或选择，不是外部确认。
"""
metrics=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','top_max_pairscale','bev_max_local_radius_fraction','top_max_local_radius_fraction']
for group in ['Rnew2_C02>C01_m5','Rnew2_C01>C02_m5','old_G_anchor','old_R_anchor','F01_time']:
 g=df[df.replay_group.eq(group)&df.gate.eq('all_common')].set_index('metric')
 first=g.iloc[0]
 text+=f"\n### {group}\n\n完整尝试{int(first.attempts)}条；共同可对应{int(first.eligible_events)}条/{int(first.eligible_images)}图/{int(first.eligible_buildings)}楼。\n\n"
 text+='| 指标 | 同类 | 跨类 | 跨−同[经验区间] | 跨更大%(加权/原始) | 楼方向+/-/0 |\n|---|---:|---:|---:|---:|---:|\n'
 for m in metrics:
  a,b,c,p=[g.loc[x+m] for x in ['within_','cross_','delta_','cross_larger_']]
  text+=f"| {m} | {a.estimate:.6f} | {b.estimate:.6f} | {c.estimate:+.6f} [{c.ci025:.6f},{c.ci975:.6f}] | {100*p.estimate:.2f}/{100*p.raw_event_cross_larger_fraction:.2f} | {int(c.positive_buildings)}/{int(c.negative_buildings)}/{int(c.equal_buildings)} |\n"
text+="""
## 必须与距离并列的结构风险分母

Rnew2 C02→C01 n13/m5完整58尝试、29图、6楼：
- 同类：55条可对应，2条确知点数不同，1条不完整。
- 跨类：51条可对应，5条点数不同，1条不完整，1条无连通几何。
- 两边共同只有50条/27图。主报告质量+6.652来自57条有限净质量，连续距离来自50条；不能拼接为每队的联合成功保证。

Rnew2 C01→C02 n13/m5完整58尝试：
- 同类53可对应、5条点数不同；跨类49可对应、9条点数不同。
- 两边共同47条/24图；没有不完整事件。

old_G：39尝试，同/跨点数不同4/6条，无不完整，共同33条。
old_R：58尝试，同/跨点数不同3/6条，无不完整，共同52条。
F01：480尝试，同/跨点数不同28/31条，不完整或无连通几何9/5条；共同428条。
完整所有方向见FULL_EVENT_STATUS_COUNTS.csv，不以失去共同对应支持解释成零位移。

## 9°/12°敏感性

上述Rnew2两种m5方向、old_G和old_R，9°和12°都保留与全唯一对应相同的共同事件，因此连续均值和逐事件方向比例不变；区间末位可能因Monte Carlo重抽样略有差异。这不是证明9°或12°是普遍人眼相近界限。

## 可采用的类别适用卡

1. Rnew2 n13/m5：保留当前35名新批人员中、完整构成与背景固定时的有向构成效用。跨类对应几何平均变化更大；C02→C01参考质量整体较好，但这不等于类内变化足够小。特别是均值差为正而逐事件跨更大的比例约一半，平均优势受幅度不对称和尾部影响。m2的C02→C01平均BEV反而跨类略小，故不能跨替换块规模笼统推广。
2. 原G方向：有条件几何分离线索保留；绝对最大角点位移与楼间异质性也明显，BEV平均差的经验区间接近或跨零。原R新增连续分离较弱，两项平均差区间跨零，旧阈值稳定率差不能等同为所有连续维度一致分离。
3. F01高Q23慢快类：更适合作为来源效率候选。跨类平均BEV和顶部位移反而稍小，最大BEV差近零；本证据不支持把慢快类改名为强几何互换类。仍须看来源时间、Q坏尾及完整率。
4. 高Q快5慢2整队：20条中转快4慢3有18条，转快6慢1仅2条/1楼，必须分开。单楼结果不提供bootstrap区间，避免重复抽样制造虚假精度；同构成72.5%不是某个目标比例的全部对照值。
5. W132：该组混合父事件与多种替代事件，本次简单分组均值不是替走W132的净效应。若解释该人的机制，应另按parent_event_id平均替代并共同支持匹配；不能从本组距离均值直接归因。

## 文件与限制

CORNER_STATISTICS_RECEIPT.json记录输入SHA与公式核验。CORNER_INDEPENDENT_BOOTSTRAP.csv含所有绝对、对称面积尺度、局部半径、方向比例及共同角度支持结果；CORNER_INDEPENDENT_BUILDINGS.csv保留逐楼值。

这些是当前成员、探索过的v2建筑与选定核心面板的条件证据。它们支持具体构成和几何变化的解释，不证明新人员外推或无需实际融合的人员替换保证。保留原参考、融合、Q、旧主判据及Pro新形状判据，不以新增距离取代它们。
"""
(O/'CORE_CORNER_AUDIT_ZH.md').write_text(text)
# Portable central result table, same-support all-gate records with all metrics and prevalence.
df[df.replay_group.isin(['Rnew2_C02>C01_m5','Rnew2_C01>C02_m5','old_G_anchor','old_R_anchor','F01_time'])].to_csv(D/'KEY_CLASS_ABSOLUTE_RELATIVE_EVIDENCE.csv',index=False)
