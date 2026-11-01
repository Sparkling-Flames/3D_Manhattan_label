#!/usr/bin/env python3
"""Join current path metrics to previously saved case endpoints and write Chinese notes."""
from pathlib import Path
import json
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'stage05_cases/manual'

def table(d,columns,formats=None):
    formats=formats or {}
    rows=['| '+' | '.join(columns.values())+' |','| '+' | '.join(['---']*len(columns))+' |']
    for _,r in d.iterrows():
        vals=[]
        for c in columns:
            v=r[c]
            vals.append('缺失' if pd.isna(v) else (formats.get(c,'{}').format(v)))
        rows.append('| '+' | '.join(vals)+' |')
    return '\n'.join(rows)

for folder in ['VFuaQ6m2Qom-04','pa4otMbVnkk-11','e9zR4mvMWw7-17']:
    p=OUT/folder
    d=pd.read_csv(p/'CURRENT_PATH_PREFIX_VALUES.csv.gz',low_memory=False)
    keyfile=p/'SELECTED_CACHED_ENDPOINTS.csv'
    keys=pd.read_csv(keyfile if keyfile.exists() else p/'EXACT_ENDPOINT_POINTERS.csv').team_key
    x=d[d.team_key.isin(keys)].drop_duplicates('team_key').sort_values('k')
    x.to_csv(p/'TRACED_ENDPOINT_METRICS.csv',index=False)
    c=pd.read_csv(p/'CURRENT_256_CURVE.csv')
    c[c.k.isin([3,6,10,14,20,25,30,31,33,34,35])].to_csv(p/'KEY_CURVE_POINTS.csv',index=False)

v=OUT/'VFuaQ6m2Qom-04';c=pd.read_csv(v/'CURRENT_256_CURVE.csv')
curve=table(c[c.k.isin([3,14,20,25,30,33,34,35])],
    {'k':'人数 k / N=35','unique_teams':'实际不同团队','Q_valid':'可评路径 / 256','Q_mean':'B8L2 条件均值','Q_p10':'条件 P10','Q_sd':'成员波动 SD','complete_evaluable_rate':'完整可评比例'},
    {'k':'{:.0f}','unique_teams':'{:.0f}','Q_valid':'{:.0f}','Q_mean':'{:.3f}','Q_p10':'{:.3f}','Q_sd':'{:.3f}','complete_evaluable_rate':'{:.3%}'})
(v/'README_ZH.md').write_text('''# VFuaQ6m2Qom-04：接近满员仍切换结构，并在满员失去完整输出

## 本例回答什么

本图在 30–35 人后段没有进入可靠的稳定输出阶段。34 人的不同成员组合可形成两种质量与底面布局明显不同的四节点结果，也可不足四节点；35 人满员的唯一团队只保留三节点。增加人数并不保证此图的条件均 Q、低尾或完整输出率持续改善。

这是普通 Manual、冻结“困难”图，N=35，目标和参考 `gt_original` 没有改变。本文所有曲线采用当前正式 256 条完整随机排列的嵌套前缀，路径的重复团队保留原访问权重。本次主曲线全部复用历史缓存，另对已存在的满员团队按冻结入口诊断回放，补齐原来缺失的完整轨迹；没有新增科学团队、路径或改变主分析分数。代表端点按高、低、失败三种已观察输出选取，用于解释机制；总体支持仍来自全部路径与完整 35 支留一人队。

## 当前 256 路结果

'''+curve+'''

满员的 256 行均指向同一支实体团队，不能当作 256 次独立失败；它说明该冻结人员池的满员结果失败。Q 保持缺失，图中没有填成 0。可评条件均值必须与完整可评比例一起读：例如 k=33 的条件均 Q 只基于 118 条可评路径，失败路径仍计入 256 条尝试分母。

34 人只有 C(35,34)=35 支可能团队，当前路径覆盖全部 35 支。完整有限分布为：15 支四节点高 Q 团队（79.758–80.457），14 支四节点低 Q 团队（26.119–26.504），3 支五节点团队（60.720–61.159），3 支三节点失败团队。32 支可评队的精确等概率均 Q 为 54.679、P10 为 26.205、有限总体 SD 为 25.625；全部 35 支的失败比例为 3/35=8.571%。这与当前路径加权均值 52.514 回答不同估计口径，没有用团队去重后等权替代主曲线。

## 已由完整状态验证的机制

|实际团队与局部门槛|右后位置 node_002|左后相邻位置 node_015|实际结果|
|---|---|---|---|
|缺 W103|17 票，入选|16 票，未入选|4 节点，Q=79.845|
|缺 W113|16 票，未入选|17 票，入选|4 节点，Q=26.176|
|缺 W134|16 票，未入选|16 票，未入选|3 节点，无法形成完整可评输出|
|满员 35 人，门槛 18 票|17 票，未入选|17 票，未入选|3 节点，无法形成完整可评输出|

前三行均为 k=34、门槛 17 票。这些是实际候选组和完整原答对应记录，不是根据总 Q 反推的原因。本次从保存的 assignments 独立重数了三个 k=34 队每一个候选组的独立人员支持，并核对入选标志；检查记录在 `VOTE_LEDGER_CHECKS.csv`。满员行来自新增诊断回放，它通过了与冻结端点的 47 项核对，见下文。

两位置组的全景底点横坐标约 635 与 396（1024 像素口径），确为不同位置。缺 W113 时，保存的连接环为 `node_000 → node_003 → node_001 → node_015`，它跨过房间大块底面；相较缺 W103，底面 IoU 从约 0.845 降至 0.480，而平均高度仅从约 1.705 变为 1.695 个相机高度。主要差异是位置被保留与连接方式改变。四节点计数相同没有表示相同布局。

共同成员 W104（原答 `v2:new:101650`）的第二个点对，在缺 W103、缺 W113 队里属于 node_015，在缺 W134 队里变为 node_004。人员集合改变先影响对应，再影响票数和连接；不能把所有变化简化成从固定分组中减掉一票。三支五节点队还说明两处表达可能同时过票，并非算法总是二选一。

35 人的完整诊断状态确认：共有 21 个身份组，两处关键组都为 17 票，未达到 18 票门槛；只有 node_000、node_001、node_003 入选，支持为 35、25、35。这直接连接到最后一人进入后的失败：从缺 W103 或缺 W113 的可评四点队进入满员时，两处关键位置最终都未过门槛。

**满员并不是没有连接。** 保存的唯一完整投影环 `node_000 → node_001 → node_003` 有 25 名来源支持，仍能重建三点底面；其中 node_001→node_003 斜边的原答直接相邻支持为 0，跳过未入选点后的投影支持为 25。真正导致正式 Q 缺失的是输出不足四节点，不是连接程序报错，也不是把三角形评分为零。直接邻接与投影邻接的区别解释了为什么“有连接”仍不能说明表达完整。

诊断回放使用原 35 份完整原答、固定 gap=7.5 和原冻结依赖，全部点坐标、底面、顺序、状态、18 票门槛、所选支持、候选总数及已有底面分项都与缓存一致（47 项通过）。未改任何输入和参数，未替换原缓存。原始包缺轨迹的历史事实保留在 `legacy_evidence/`；本轮新状态单列 `FULL35_VERIFIED_DIAGNOSTIC_STATE.json.gz`。实现首遍在验收适配器列名处中断、重跑后通过，两个执行尝试均记入日志，仍只涉及同一个已有科学团队。

`COMMON_RAW_PAIR_ASSIGNMENT_TRANSITIONS_TO_FULL.csv` 同时区分组编号交换与真正成员对应改变：以共同原答点对集合做一一最大重叠对齐后，加入 W103 时 W102 的第二点对从 node_010 转到 node_001；加入 W134 时 W104 第二点对从 node_004 转到 node_015。其余部分原始编号交换不计为新增结构分歧。奇偶人数门槛与本图后段波动相联系，但本例不能推广为所有图片的奇偶规律。

## 直接查看与追溯

- 打开 `VIEWER.html` 可在同一原图上查看全部 35 人的完整原答、正式参考及四个保存端点。默认 W104 有助于核查对应变化。
- `FIG_VFUA_RESPONSE.*` 是当前 256 路曲线；`FIG_VFUA_GEOMETRY.*` 对照同尺度底面，虚线三点轮廓仅显示失败缓存的候选连接，不是完整输出。
- `TRACED_ENDPOINT_METRICS.csv` 保留四队当前 Q、分项、人数比例、状态、记录劳动和精确人员/原答身份；`REPRESENTATIVE_COMPLETE_NESTED_PATHS.csv.gz` 给出三条实际进入路径的全部前缀。
- `EXACT_N34_CURRENT_TEAMS.csv` 给出完整有限总体；`COMPLETE_CASE_EVIDENCE.json.gz` 包含当前完整人员池、正式参考、四个几何及三个完整状态；`legacy_evidence/` 保留来源包原身份与原说明，原 24/48/96 路数字不充作本轮主曲线。
- `FULL35_CANDIDATE_GROUP_VOTES.csv`、`FULL35_RAW_ASSIGNMENTS.csv`、`FULL35_CONNECTION_EDGES.csv` 与 `FULL35_RING_DIAGNOSTICS.json` 保存新增满员轨迹；`NEAR_FULL_CRITICAL_VOTE_COMPARISON.csv` 将 34/35 人关键局部票数合并。`COMPLETE_CASE_EVIDENCE.json.gz` 的独立字段也纳入此回放状态，保持三支历史状态原身份不变。

所有记录劳动是合法同源作答时长之和，不是多人并行标注的墙钟时间。几何异常的语义判断可对照原图右后与左后两个位置；已保存票账足以解释算法如何选择它们，但并不据此给人员贴“乱标”标签。
''',encoding='utf8')

p=OUT/'pa4otMbVnkk-11';c=pd.read_csv(p/'CURRENT_256_CURVE.csv')
curve=table(c[c.k.isin([3,6,10,20,30,35])],
    {'k':'人数 k / N=35','Q_mean':'B8L2 均值','Q_p10':'P10','Q_sd':'成员波动 SD','complete_evaluable_rate':'完整可评比例','nodes_mean':'节点数'},
    {'k':'{:.0f}','Q_mean':'{:.3f}','Q_p10':'{:.3f}','Q_sd':'{:.3f}','complete_evaluable_rate':'{:.0%}','nodes_mean':'{:.0f}'})
(p/'README_ZH.md').write_text('''# pa4otMbVnkk-11：平均质量很早稳定，但稳定在与参考不一致的表达上

## 本例回答什么

本图从 k=3 到满员 k=35，当前 256 路的均 Q 全范围只有 0.752 分，属于很早出现平均质量小变的例子；满员 Q 仅 22.367。成员波动从 SD=2.433 持续收缩到 k=30 的 0.108，P10 从 21.013 上升至 22.216，但平均质量并未因此变成高质量。这说明均值平台、换组波动缩小与符合正式参考是三个问题。

本图是普通 Manual、冻结“中等”图，N=35。当前采用目标 `user_floor_20261015:pa4otMbVnkk-11`、参考版本 `user_adopted_reference_20261028`，均照原记录保留。此案例按“低均 Q 而均值很早小变”的实际结果选入，用于解释主分析的一类边界，不作为全体图片频率估计。

## 当前曲线和保存的局部支持

'''+curve+'''

35 人时只有一支团队，SD 数值约为机器精度下的 0，属于有限人员池的组合消失；不能据此证明每个人的坐标意见完全相同。P10 与均值也在满员机械地相等。

35 份完整原答全部为 8 个上下点对，而现行参考为 4 个上下点对。所有已观察融合端点的标量计数均为 8 节点/8 有效转折。我们恢复了真实进入路径 `new_space256::pa4otMbVnkk-11__manual__v21_249__new256_0` 的 k=3、10、20、35 四支团队完整几何：四队均有 8 个候选身份组、0 个未入选组，每个入选组都获得该队全部成员支持，即分别 3、10、20、35 票，均远离各自 MV50 最低支持 2、5、10、18 票。

这四队在同一底面坐标下维持八角布局，相对于四角参考同时存在遗漏和外扩；满员遗漏项为 0.267993、外扩项为 0.182341，底边位置角误差为 9.445770°，IoU3D100 为 57.634。它不是某个临界候选组随一票反复切换造成的低 Q。继续在相同人员池中增加人数主要缩小位置估计和成员组成的波动，保留下来的八角表达仍与本次正式参考不同。

## 原图可以确认什么、仍需人工判断什么

原图可见卧室主区及右侧入口/过渡区域。`FIG_PA4_GEOMETRY.*` 将四个实际底面与冻结四角参考放在同一尺度；`FIG_PA4_PANORAMA.*` 和 `VIEWER.html` 提供原图、参考全点对及全部 35 份原答。这些足以确认“人员高度一致的八角表达与现行四角参考不一致”。

需要人工判断的具体问题是：**当前四角主目标是否有意排除右侧入口/过渡区域，以及标注八角范围的这 35 份原答是否符合该目标的合法范围规则。** 当前计算不改空间归属，不把这个差异直接定性为 GT 错误或人员共同乱标。无论语义裁决如何，本例已经支持“现有人员池内继续加人无法自行消除这种参考相对偏差”的结论。

## 数据和入口

- `CURRENT_256_CURVE.csv` 与 `CURRENT_PATH_PREFIX_VALUES.csv.gz` 保存全部人数、所有路径与重复团队频次。
- `CURRENT_POOL_FULL_INPUT.json.gz`、`raw_answers/` 和 `ALL_RAW_POINT_PAIRS.csv` 保存全部 35 人完整原答与正式参考。
- `EXACT_ENDPOINT_POINTERS.csv` 指到当前 v2.1 `new_space_natural256` 的精确分片和行；`SELECTED_CACHED_ENDPOINTS.json.gz` 保留四队完整几何，`SAVED_SELECTED_NODE_SUPPORTS.csv` 保留实际局部支持。
- `TRACED_ENDPOINT_METRICS.csv` 保留四队全套质量分项、状态及合法同源记录劳动。该代表路径 k=3/10/20/35 的记录劳动依次为 279.557/1570.700/2962.079/5019.599 秒，是原答劳动之和。

此批缓存采用 `full_state=False`，没有保存逐个原答到身份组的完整轨迹；本文不虚构这一部分。候选总数、未入选数、已入选全票支持和实际输出几何均来自已保存端点。新增融合 0、新增质量评分 0。
''',encoding='utf8')

e=OUT/'e9zR4mvMWw7-17';x=pd.read_csv(e/'TRACED_ENDPOINT_METRICS.csv')
score=table(x,{'k':'人数 k / N=31','B8L2':'B8L2','D10':'D10','IoU3D100':'IoU3D100','S_bottom_deg':'底边位置误差 / °','B8_floor_block':'B8 底面损失块','B8_direction_block':'B8 方向损失块','B8_height_block':'B8 高度损失块'},
    {'k':'{:.0f}','B8L2':'{:.3f}','D10':'{:.3f}','IoU3D100':'{:.3f}','S_bottom_deg':'{:.3f}','B8_floor_block':'{:.5f}','B8_direction_block':'{:.5f}','B8_height_block':'{:.5f}'})
changes=pd.read_csv(e/'SAME_COUNT_GEOMETRY_CHANGES.csv')
ct=table(changes.iloc[:2],{'k_from':'起点 k','k_to':'终点 k','entrants':'新增成员','B8L2_delta':'ΔB8L2','floor_1_minus_iou':'底面 1−IoU','area_percent_change':'面积变化 / %','centroid_distance_h':'质心移动 / h','cyclic_matched_corner_rms_h':'对应角点 RMS / h','max_corner_displacement_h':'最大角点移动 / h'},
    {'k_from':'{:.0f}','k_to':'{:.0f}','B8L2_delta':'{:+.3f}','floor_1_minus_iou':'{:.5f}','area_percent_change':'{:+.3f}','centroid_distance_h':'{:.5f}','cyclic_matched_corner_rms_h':'{:.5f}','max_corner_displacement_h':'{:.5f}'})
(e/'README_ZH.md').write_text('''# e9zR4mvMWw7-17：节点与转折不变，位置和尺度仍使 Q 大幅往返

## 本例回答什么

本图中同一条真实进入路径从 11 人增加到 12 人，Q 提高 9.954；再增加第 13 人，Q 下降 8.098。三队都是四节点、四有效转折，四个位置组均得到全体成员支持，没有候选组因 MV50 门槛入选或退出。变化主要发生在同四个对应角点的位置和底面尺度上。结构计数稳定不能替代布局或质量稳定。

这是普通 Manual、冻结“简单”图，N=31。采用目标 `e9zR4mvMWw7-17:primary:floor:4d7867ad4377d12a`、参考版本 `user_adopted_reference_20261028`。代表路径是 `new_space256::e9zR4mvMWw7-17__manual__v21_3__new256_225`，来自原有随机排列，不是重新挑选成员制造变化。案例是在全部现成事件中寻找“同计数、非小幅度变化”后选入，选型目的与范围保留在 `stage07_summary/manual/SAME_COUNT_NONTRIVIAL_NEWSPACE_EVENTS.csv`。

## 质量分项与实际几何

'''+score+'''

三个 B8 损失块越小越好。底面块 0.32960→0.17050→0.29862 是主要变化，方向和高度块变化很小；D10 与 IoU3D100 也同向往返。这里的 B8 分项按冻结质量公式由原始分项换算，未重新评分。

'''+ct+'''

h 表示相机高度单位。这不是根据节点数量猜测对应：对保存的四角坐标完整检查了四种循环移位及反序，共 8 种对应，最佳均为原顺序且唯一，下一最佳 RMS 大于 2.88h；四个角的逐点移动保存于 `CORRESPONDING_CORNER_DISPLACEMENTS.csv`。底面相交计算还回算了三个端点相对正式参考的 IoU，与原缓存值在 1e−10 内一致。上述三对几何距离是本轮新增测量，输入全部为既有真实几何。

11 人队成员为 W012、W030、W033、W103、W105、W110、W114、W119、W125、W127、W131。12 人队仅加入 W108；13 人队再加入 W101。每个候选角点的支持依次为 11/11、12/12、13/13，最低门槛分别为 6、6、7。相同计数、全票支持、相同对应和没有未入选候选共同排除了“这两步主要由节点过票开关造成”的解释；保存的几何直接显示位置/尺度改变。没有完整原答分组轨迹，不能进一步断言具体是哪一份坐标触发了每个位置估计。

## 放回整张图的曲线

所有 k≥3 的当前 256 路均完整可评，均为四节点/四有效转折；但均 Q 并非一路改善。k=3 的均 Q=63.824、P10=51.115，k=20 为 72.198、61.081，k=30 为 69.155、65.058，满员 k=31 为 66.252。20→30 人期间均值下降约 3.044，低尾却提高约 3.977，成员 SD 从 9.476 收缩到 3.385。满员唯一团队的波动归零只是组合数量归一。

本例因此同时提供两条结果：局部新增一人可在节点不变时造成近 8–10 分的往返；后段均值变差时，低尾和换组波动仍可能改善。W108、W101 在这个固定背景中的局部效果不能推广为人员的普遍质量标签。

## 直接查看

- `FIG_E9Z_NESTED_PATH.*`：该条真实进入路径与整图均曲线，并列底面面积；橙色带是所追踪的 11–13 人。
- `FIG_E9Z_POSITION_OVERLAY.*`：三个保存底面在同一坐标轴叠加，可直接看到左后角移动。
- `FIG_E9Z_RESPONSE.*`：全部人数的均值、P10、成员 SD、完整可评率；`FIG_E9Z_GEOMETRY.*`：分队同尺度几何。
- `VIEWER.html`：原图、31 人完整原答、参考及三队完整上下点对；`TRACED_ENDPOINT_METRICS.csv` 与 `REPRESENTATIVE_COMPLETE_NESTED_PATH.csv.gz`：当前分项、实际成员和路径关联。
- `EXACT_ENDPOINT_POINTERS.csv`：原仓库分片和精确行；`SAVED_SELECTED_NODE_SUPPORTS.csv`：全票支持记录；`GEOMETRY_DISTANCE_REFERENCE_PARITY.csv`：几何距离回算核验。

三支代表队的记录劳动都有同源完整支持，依次 1038.672、1109.944、1211.962 秒；整个 31 人池只知 30 人记录时长，满员劳动不得冒称完整。新增融合 0、新增质量评分 0，新增三对几何度量。若需进一步视觉判断，请核查原图左后边界/家具遮挡与正式四角参考的落点；当前证据已能确认算法输出的定位变化，不把语义不确定性写成 GT 错误。
''',encoding='utf8')

(OUT/'README_ZH.md').write_text('''# 普通 Manual 的三个可追溯人数响应案例

本目录连接当前 v2.1 的实际 256 条嵌套路径、冻结参考与人员身份、原图、全量原答、缓存端点和实际支持票。不是重新设计分类或重新融合的实验。

|图片|冻结难度 / N|主要现象|可直接确认的机制|入口|
|---|---|---|---|---|
|VFuaQ6m2Qom-04|困难 / 35|近满员仍有大幅成员波动，满员无法完整输出|k34 的 16/17 票临界、原答对应改变、不同位置与连接|`VFuaQ6m2Qom-04/README_ZH.md`、`VIEWER.html`|
|pa4otMbVnkk-11|中等 / 35|k3 起均 Q 全范围仅 0.752，但满员 Q=22.367|35 份八角原答、四支检查队均八节点全票支持，持续偏离现行四角参考|`pa4otMbVnkk-11/README_ZH.md`、`VIEWER.html`|
|e9zR4mvMWw7-17|简单 / 31|同四节点、四转折，新增一人使 Q +9.954 再 −8.098|对应角点移动、面积与质心改变；节点全票、无过票切换|`e9zR4mvMWw7-17/README_ZH.md`、`VIEWER.html`|

三张是按已观察现象选出的解释案例，其数量不当作总体发生比例；总体比例见逐图/分层主结果。两张新目标案例仅有端点保存的支持汇总，没有完整身份组轨迹；VFua 有三支 k34 历史完整状态，并通过一次既有满员队的冻结诊断回放补齐完整候选票账，47 项缓存一致性全部通过。每个案例分别标清了证据到哪一步。

每张均提供英文标题的 PNG、PDF、SVG、绘图原表、当前完整路径表、全部人员原答、正式参考和可脱网打开的 `VIEWER.html`。`PANORAMA_ORIGINAL.png` 是原始全景图；HTML 内嵌该原图，不依赖互联网。`raw_answers/` 是完整点对记录，不是人工挑选片段。

代码为 `scripts/build_manual_cases.py`、`scripts/write_manual_case_notes.py`，以及 `scripts/replay_manual_full35.py`、`scripts/integrate_manual_full35.py`。本轮没有新增科学团队、路径或正式质量分数；VFua 的一个既有团队做了诊断回放，实际两个执行尝试（一次验收适配器中断、一次完整通过）。本轮新增的端点几何度量是 e9z 的三对凸四边形比较。源仓库固定提交 e1873bfadc1d0e61499809c91fba9dc39c717f83。已恢复案例可独立阅读；全库复现仍依赖项目源表清单及对应缓存，诊断还需同交付的 `stage04_doorway_cases/replay_engine` 和 `vendor` 依赖，不宣称这三个案例目录包含全库引擎。
''',encoding='utf8')
print('Three Chinese case notes and traced metric tables written.')
index=[]
for image,difficulty,N,phenomenon,question in [
    ('VFuaQ6m2Qom-04','Hard',35,'Late member-dependent topology and below-four full-pool output',
     '票数、对应和连接机制已有实证；如需语义复核，查看原图右后与左后两个位置分别代表什么墙界。'),
    ('pa4otMbVnkk-11','Medium',35,'Early low-quality mean stability with shrinking member variation',
     '现行四角目标是否有意排除右侧入口/过渡区域；八角原答是否符合该目标合法范围。'),
    ('e9zR4mvMWw7-17','Easy',31,'Equal node counts and unanimous support with position/scale-driven Q reversal',
     '原图左后边界/家具遮挡与正式四角参考落点是否一致；输出位置变化已量化。')]:
    folder=OUT/image;c=pd.read_csv(folder/'CURRENT_256_CURVE.csv');r=json.loads((folder/'CASE_RECEIPT.json').read_text())
    full=c[c.k.eq(N)].iloc[0];post=c[c.k.ge(3)]
    index.append(dict(image=image,difficulty=difficulty,N=N,paths_per_k=256,
        mean_Q_full_tail_range=post.Q_mean.max()-post.Q_mean.min(),full_B8L2=full.Q_mean,
        full_complete_evaluable_rate=full.complete_evaluable_rate,phenomenon=phenomenon,
        diagnostic_existing_team_replays=r.get('diagnostic_existing_team_replays',0),
        human_semantic_question=question,readme=f'{image}/README_ZH.md',viewer=f'{image}/VIEWER.html',
        all_raw_answers=f'{image}/CURRENT_POOL_FULL_INPUT.json.gz',all_path_values=f'{image}/CURRENT_PATH_PREFIX_VALUES.csv.gz'))
pd.DataFrame(index).to_csv(OUT/'CASE_INDEX.csv',index=False)
