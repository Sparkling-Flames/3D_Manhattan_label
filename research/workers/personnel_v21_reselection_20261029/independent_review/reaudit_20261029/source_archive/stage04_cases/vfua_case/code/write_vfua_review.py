#!/usr/bin/env python3
"""Write the focused VFua negative-tail explanation and local HTML entry."""
from pathlib import Path
import pandas as pd
import html

ROOT=Path(__file__).resolve().parents[1]
summary=pd.read_csv(ROOT/'results/COMMON_SEVEN_POOL_MEAN_AND_SIGN.csv')
arms=pd.read_csv(ROOT/'results/SIX_ARM_METRICS_AND_RING_COVERAGE.csv')
events=pd.read_csv(ROOT/'results/FOUR_EVENT_SOURCE_ROWS.csv').set_index('event_id')
good='f48b5b2dcce86d87b6ce5ece';failed='cee80eb52074a9b2d594a037'

def table(headers,rows):
 return '| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'+'\n'.join('| '+' | '.join(map(str,r))+' |' for r in rows)
def number(x,d=4):return '不可评' if pd.isna(x) else f'{x:.{d}f}'

text=["""# VFuaQ6m2Qom-04：共同七池负尾、方向口径和固定换入块的背景响应

## 为什么必须补这一张

本补充回答一个已经发现的具体问题：普通 Manual、n=16、m=8、留楼外困难图转折倾向中间组→较多组这一方向上，TARGET_DSTRUCT_K3 与 V21_DSTRUCT_RAW3_K3 的共同七图片池有六图直接跨类幅度大于同类、六图 C−A 为正，但图片等权均值却为负。VFuaQ6m2Qom-04 的大负尾说明了这个分歧，也说明为什么 C−B 为正不能直接表述成“跨类换入升质”。

本轮只对已有端点导出必要 full_state，没有新房间、新团队或新的同房实验。四条方法事件实际上只有两套不同 ABC：

| TARGET 事件 | RAW3 事件 | 三臂状态 |
| --- | --- | --- |
| f48b5b2dcce86d87b6ce5ece | 724f9d200edfa11b34e56ebb | ABC 均可评 |
| cee80eb52074a9b2d594a037 | 44ebc9dfe43f07b6030f2fcd | ABC 均不可连接 |

每对方法事件的 D/X/Y/Z、A/B/C 成员、team_key、当前参考均逐字一致，而非仅输出数值巧合。已逐个验证互斥八人 D/X/Y/Z，以及两法各自留楼外 X/Y 同类、Z 异类。因此在这张图上，不能把同一个实际团队的负尾解释为 RAW3 或 TARGET 某一方参数特有的失败。六个唯一端点重放最大标量误差 1.78×10⁻¹⁵，Q 缺失保留缺失。

原图：[VFuaQ6m2Qom-04.png](originals/VFuaQ6m2Qom-04.png)。全局对照：[共同七池逐事件](results/COMMON_SEVEN_POOL_EVENTS.csv)、[各池等权均值](results/COMMON_SEVEN_POOL_MEANS.csv)、[均值与正负图片数](results/COMMON_SEVEN_POOL_MEAN_AND_SIGN.csv)。

## 共同七池：幅度、方向、均值和多数比例同时保留

同类幅度为 |B−A|；直接跨类幅度为 |C−A|；对称跨类幅度为 (|C−A|+|C−B|)/2。下表各数均为图片池内事件先均值、再七池等权；不可评事件不填 Q=0。七个共同池包含六栋建筑。六个池的全部 ABC 身份在两法间一致；仅 pa4-05 的具体 ABC 不同，TARGET 两条、RAW3 四条，本轮保持其现有参考而不做人工复裁。共同池比较控制了图池、n/m 和方向，但不能误称七池成员完全匹配。
"""]
names={'Q_CA':'C−A','Q_CB':'C−B','direct_gap':'直接跨幅度−同类','symmetric_gap':'对称跨幅度−同类'}
rows=[]
for r in summary.itertuples():
 rows.append([r.method,names[r.metric],number(r.mean),f'{r.positive_images}/{r.pools}',number(r.vfua_value),number(r.other_six_mean_diagnostic_only)])
text.append(table(['分类','Q 比较量','七池均值','正值图比例','VFua本图','其余六图均值（解释用）'],rows))
text.append("""
“其余六图”列只是说明均值为何与多数方向不一致；VFua 仍包含在主均值中，不能事后删掉。两法在共同七池的均值差异集中于唯一成员设计不同的 pa4-05，不能据此证明分类边界本身有普遍优劣。

## 第一套 ABC：C 比 B 好，但比原队 A 差

[完整 ERP/BEV](figures/f48b5b2dcce86d87b6ce5ece/ERP_BEV.png) · [三维及全票账](figures/f48b5b2dcce86d87b6ce5ece/3D_VOTES.png) · [右侧关键四组放大](figures/f48b5b2dcce86d87b6ce5ece/LOCAL_CRITICAL_VOTES.png) · [全部原答及坐标](figures/f48b5b2dcce86d87b6ce5ece/RAW_ANSWERS.csv)

A/B/C 的 Q 为 79.7922、26.1511、44.8821。因此 B−A=−53.6411，C−A=−34.9101，C−B=+18.7310。三者严格满足 C−A=(B−A)+(C−B)：同类替换 B 已经大幅降质，C 相对于 B 的恢复仍没有回到 A 的水平。只报告 C−B 会把这个降质事件误说成升质。

同类幅度为 53.6411；直接 AC 幅度为 34.9101，因此直接幅度差 −18.7310。对称跨幅度为 26.8205，对称幅度差 −26.8205。这两个负数是不同口径，不应混写。
""")
g=arms[arms.event_id.eq(good)].set_index('arm')
metrics=[('B8L2','Q'),('nodes','入选角数'),('fusion_turn_n','转折数'),('fusion_short_turn_edges','短折边数'),('iou_2d','底面 IoU'),('IoU3D100','三维 IoU×100'),('S_bottom_deg','底角角距°'),('dir','方向误差°'),('omission','遗漏'),('extension','外扩'),('boundary_loss','边界损失'),('direction_loss','方向损失'),('height_loss','高度损失'),('source_ring_covering_all_selected_n','覆盖全部入选角的来源环数')]
text.append(table(['分项','A','B','C'],[[name]+[number(g.loc[a,field],0 if field in ['nodes','fusion_turn_n','fusion_short_turn_edges','source_ring_covering_all_selected_n'] else 4) for a in 'ABC'] for field,name in metrics]))
text.append("""
### 支持票如何产生这条响应

当前冻结参考有 14 个底角，涉及浴室多个壁龛、洗手台附近的细折。A 的四角粗表达近似保留了主体周边，虽然没有全部细节，但方向损失很小。B 有五角，C 有九角；更多角并没有自动提高当前 Q。

在右侧区域，A 用于四边形的粗候选角约为 ERP (635.62, 307.20)，得到 D3+X5=8 票，刚好入选。换成同类 Y 后，同一共同 D 观测对应的候选只有 D3+Y3=6 票，未入选；同时邻近 x≈651、704、691 的更细候选分别只有 7、7、7 票，也都未过 8 票门槛。B 因而没有该区域必要的中间转折，实际来源建议环从一侧直连另一侧，形成大对角线。底面图可直接看到其截去大块区域；遗漏从 0.1287 增到 0.5183，方向误差从 0.5826°增到 21.9202°，高度损失仍很小。这次崩落主要与结构选取、连接后的边界/方向有关，不是高分集中或纯顶边偏移。

跨类 Z 给部分细节补足了票：x≈705 和 691 两组均达到 D3+Z5=8 票，若干左侧短折也达到 8/9 票，C 形成九角。它因此比 B 少漏区域，遗漏降至 0.2577，方向误差降至 13.5820°，Q 恢复 18.7310 分。但是当前参考 x≈650 附近的组仍只有 D3+Z3=6 票；相邻 x≈648 的另一组仅 5 票，此外左侧数处细角为 7 票未选。实际 C 环包含部分细折，同时残留跨过缺失折点的长斜边。因此它仍比粗 A 更偏离当前参考的边界和方向。

这不是简单的“每人投一个既定角”过程。共同 D 原始 65 个角观测在三臂完全相同，但 A→B、A→C 各有 16 对共同 D 观测的同组关系变化。原答结构、位置和对应分组共同影响了局部支持票；不能把所有差异都归结为 Z 只增或只减某几张票。跨臂的 node 编号不得直接对齐；详见 [共同 D 对应变化](results/COMMON_D_COASSIGNMENT_CHANGES.csv) 和各图目录的 COMMON_D_GROUP_LINKS。

### 记录劳动量方向也是负面结果的一部分

A/C 的 16 人源时间都已知，来源签名相同，均为旧审计来源 2 人＋新处理记录 14 人。总记录劳动量从 1872.385 秒增至 2257.643 秒，+20.5758%，同时 C−A 的 Q 为 −34.9101。本次是“相对原队降质且增加记录劳动量”的明确事件。B 的来源签名为旧 1＋新 15，不与 A/C 混作同口径三臂时间结论。此劳动量是既有标注记录的累加，不是现场重复标注耗时预测。

## 第二套 ABC：三臂均不满足来源环覆盖规则

[完整 ERP/BEV](figures/cee80eb52074a9b2d594a037/ERP_BEV.png) · [入选点与全部支持票](figures/cee80eb52074a9b2d594a037/3D_VOTES.png) · [全部原答](figures/cee80eb52074a9b2d594a037/RAW_ANSWERS.csv)

A/B/C 的入选节点数为 7/5/10，覆盖全部入选节点的来源环数都是 0，状态均为 `no_connection`。全部 Q、完整底面和三维质量缺失，不填成零，也不计入上述本图可评 Q 均值。三种失败不是完全相同的票数冲突：

| 臂 | 最小无共同来源支持的入选组 | 票数 | 说明 |
| --- | --- | --- | --- |
| A | node_004、node_005、node_010 | 8、9、8 | 任意两组尚有共同支持者，三组同时没有 |
| B | node_001、node_002、node_005 | 10、9、11 | 不含恰好半票的入选角，三组仍无共同来源 |
| C | node_002 与 node_010（另有两组同类最小冲突） | 8、8 | 两组支持者完全互斥，均过半票门槛 |

最小冲突是对当前入选组的人员集合交集作穷尽检查所得，完整每人账保留在 [MINIMUM_SOURCE_RING_COVER_OBSTRUCTIONS.csv](results/MINIMUM_SOURCE_RING_COVER_OBSTRUCTIONS.csv)。这表明当前连接失败既可能来自互斥半票组，也可能来自多组在整体上没有共同来源，不能把所有失败都只解释为“恰好 8 票”。当前冻结引擎采用来源建议环，未找到覆盖全部入选组的来源时不补环；这些结果不声称数学上不存在任何别的闭环。

第二组 B/C 来源签名都为旧 3＋新 13，记录劳动量 2036.942→2494.725 秒，+22.4740%。两端均失败，故该记录劳动差只能作为失败状态下的人员劳动输入差异，不能拼造质量增益。

## 同一 Z 八人，在两种背景下可评性不同

两套 C 都使用同一换入块：W017、W033、W102、W112、W115、W122、W126、W130。变化的是八人 D 背景，两个 D 只共享 W113、W117。第一套 C 的右侧粗组 x≈635 为 D3+Z3=6 票未选，第二套 C 变成 D5+Z3=8 票入选；与此同时，细角 x≈691 为 D3+Z5=8 票入选。第二套粗组八人为 W017、W032、W033、W102、W104、W113、W117、W127；细组八人为 W101、W103、W112、W115、W121、W122、W126、W130，恰好互斥。由此，固定同一个 Z 可以因背景改变而由九角可评变成十角不可连接。

这是在 C 端点层面对固定 Z 的直接比较。两套完整 ABC 的 X/Y 也不同，所以不能把两套完整替换效果的全部差异仅归给背景。它也不支持“高转折块永远补细节”或“换八人一定淹没背景”的表述。

## 人工需看什么，哪些事实已不需要人工判断

已经确定：四条方法事件是两套相同实体 ABC；Q 的有符号关系；每个支持票来自谁；哪些组跨线；来源环覆盖是否为零；评分损失集中在哪些分项。这些均已回连原始坐标和当前执行结果。

人工可查看原图左右洗手台及壁龛下方被柜体遮住的墙地边界，重点为 ERP x≈288–427 与右侧 x≈635–706。需要判断当前 14 角参考中各短折在本任务范围内的真实必要性，以及 x≈635 的粗表达、x≈648/650 的邻近组究竟对应同一实际角的不同定位，还是不同结构/遮挡推断。该判断可帮助解释为什么具体成员采用不同原答；本轮不据此擅自修改参考、合并对应组或修补失败环。

对采用方案的意义是保留范围：共同七池六图同向与均值受负尾拉低可以同时成立；C−B 为正不能替代 C−A；粗四角在某一评分下可比不完整的九角更高；人员块的作用依赖背景和对应/连接过程。由于两法此图使用完全相同团队，这些证据支持解释条件与反例，不构成择优调整某个分类边界的依据。

## 两套精确成员块
""")
rows=[]
for eid in [good,failed]:
 for block in 'DXYZ':rows.append([eid if block=='D' else '',block,events.loc[eid,block].replace('|','、')])
text.append(table(['TARGET 事件','块','成员'],rows))
text.append("""
## 文件与复现

`traces/` 保存两套实际 ABC 的完整原答、参考、几何、110 组支持状态、全部来源环与六臂标量；`figures/` 保存 PNG/PDF ERP、BEV、三维、票图与右侧关键四组放大。`results/FOUR_EVENT_SOURCE_ROWS.csv` 与 `FOUR_EVENT_FULL_METRICS.csv.gz` 保留四条方法事件；`ALL_110_VOTE_GROUPS.csv`、`ALL_VOTE_OBSERVATIONS.csv.gz` 保留 110 组、781 条观测票；`COMMON_SEVEN_POOL_EVENTS.csv` 保留全七池对应事件，保证本图机制与总体均值能回连。源校验见 VFUA_AUDIT_RECEIPT.json。

重算本补充表使用 `python audit_case_vfua/code/audit_vfua.py`；图形使用 `code/render_exact_abc_case.py` 和 `code/render_critical_vote_closeups.py`；本说明由 `code/write_vfua_review.py` 生成。full_state 只需针对两条 TARGET 事件重放，RAW3 同实体端点无需重复重放。可复现等价命令保留在 source/TRACE_EXPORT_COMMAND.txt。新算仅为票账诊断与已完成七池结果汇总，新增物理实验数为 0。
""")
(ROOT/'VFUA_COMMON_POOL_NEGATIVE_TAIL_ZH.md').write_text('\n\n'.join(text),encoding='utf-8')

page=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VFua 共同七池负尾诊断</title><style>body{font-family:system-ui,sans-serif;max-width:1250px;margin:auto;padding:28px;background:#f1f4f6;color:#1e3443}p{line-height:1.7}section{background:white;padding:20px;margin:20px 0;border-radius:10px}img{width:100%;height:auto}a{color:#17668d}code{font-size:.9em}</style><h1>VFuaQ6m2Qom-04：共同七池负尾</h1><p>普通 Manual，n=16、m=8，困难转折倾向中间组→较多组。两法同实体团队；2套ABC、6个唯一端点，均为已完成实验。</p><p><a href="VFUA_COMMON_POOL_NEGATIVE_TAIL_ZH.md">完整中文说明</a> · <a href="results/COMMON_SEVEN_POOL_MEAN_AND_SIGN.csv">七池均值与多数比例</a> · <a href="results/ALL_110_VOTE_GROUPS.csv">110组完整票账</a> · <a href="originals/VFuaQ6m2Qom-04.png">原图</a></p>']
for eid,title,description in [(good,'C 比 B 好，但比 A 差','Q 79.7922 / 26.1511 / 44.8821。B−A −53.6411；C−A −34.9101；C−B +18.7310。角数4/5/9，部分细折入选而关键折点缺失，实际环形成长斜边。'),(failed,'同一 Z 换入另一背景，三臂均不可连接','入选角7/5/10，全部来源环覆盖数为0。A/B存在三组整体无共同支持者；C有互斥8票组同时入选。失败Q留空。')]:
 base='figures/'+eid
 page.append(f'<section><h2>{title}</h2><p>{description}</p><p>事件 <code>{eid}</code> · <a href="{base}/RAW_ANSWERS.csv">原答及成员</a> · <a href="{base}/COMMON_D_GROUP_LINKS.csv">共同D对应变化</a></p><img src="{base}/ERP_BEV.png" alt="实际ERP及底面">')
 if eid==good:page.append(f'<details open><summary>右侧关键四组</summary><img src="{base}/LOCAL_CRITICAL_VOTES.png" alt="关键四组与门槛"></details>')
 page.append(f'<details><summary>三维及全部候选组票数</summary><img src="{base}/3D_VOTES.png" alt="入选点和全部支持票"></details></section>')
page.append('<p>范围与当前参考保持。人工可核对柜体遮挡下的墙地折线，以及右侧相邻对应组的真实结构含义。数值机制已由原答、几何和票账确定。</p></html>')
(ROOT/'index.html').write_text('\n'.join(page),encoding='utf-8')
print(ROOT/'VFUA_COMMON_POOL_NEGATIVE_TAIL_ZH.md')
