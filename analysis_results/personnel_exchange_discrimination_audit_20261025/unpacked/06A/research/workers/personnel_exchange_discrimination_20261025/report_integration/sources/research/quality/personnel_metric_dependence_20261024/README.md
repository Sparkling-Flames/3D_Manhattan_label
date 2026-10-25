# 主要人员结论对质量指标的依赖：固定端点与共同支持

日期：2026-10-24；真人 v2。只重读既有同房严格 ABC 与人数端点的相同团队，不改变原答、参考、冻结 B8L2、分类或融合。逐团队并列 B8L2、D10、底面 IoU（0—1）、均高棱柱代理 `IoU3D100`（0—100）、底边角差/方向残差/高度、参考节点/边召回及融合结构量。`dir`、`S_bottom_deg`、`Hmean`、`Hcenter` 是残差，较小常较好；结构计数本身无自动的正确方向。失败以全部尝试为分母，质量缺失保留空。输入和逐项路径见脚本 `tools/thesis_main/analysis/personnel_supplement_metric_dependence_20261024.py`。

## 1. Manual 结构类的跨类变化与难度

普通 Manual 结构类的保存严格 ABC 中，29,543 个事件／59,086 个图端尝试；主结果取固定背景 `D_n>0` 的严格混合子域，78 直接图对、9 楼。同一图端 A、B、C 都可评分时，沿用原研究定义：同类幅度 `|B−A|`，跨类幅度 `(|C−A|+|C−B|)/2`，额外幅度为后者减前者；先在两视角、配置内，再在图对平均。**同一指标的 A/B/C 共同支持**为 78 图对；图对不是独立人员数。原按指标各自有效的跨类 B8L2 额外幅度均值 +1.960、中位 +1.086，61/78 图对为正；D10 +1.816、60/78，IoU3D100 +1.183、61/78，底面 IoU +0.0081、56/78。方向残差额外幅度 +0.282°、52/78；输出转折数 +0.134、仅22/78 为严格正（大量为零）。这些广域诊断的事件分母不同，不能直接作为同事件指标比较。全普通与严格混合两域均保留，节点/边召回、位置及高度各自原量纲见 [`SWAP_IMAGE_PAIRS.csv`](SWAP_IMAGE_PAIRS.csv) 与 [`SWAP_BUILDINGS.csv`](SWAP_BUILDINGS.csv)。

为并列指标，另固定**两视角共六端点正式 B8L2 可评**，再与各指标交集；B8L2、D10、底面 IoU、IoU3D100、底边角差、方向及两项高度、方向置零变体的共同事件交集为严格混合 **25,472个事件**。相同78图对/9楼、相同配置和事件支持下，B8L2额外幅度 +1.960（61/78图对正）、D10 +1.816（60/78）、底面 IoU +0.0081（56/78）、IoU3D100 +1.183（61/78）、方向残差 +0.274°（52/78），方向置零 B8L2 +1.177（58/78）。原方向 +0.282° 与 +0.274° 的差来自正式 Q 缺失事件，不是方向定义变化。逐共同事件与配置/图对汇总见 [`SWAP_FIXED_Q_EVENTS.csv.gz`](SWAP_FIXED_Q_EVENTS.csv.gz)、[`SWAP_FIXED_Q_IMAGE_PAIRS.csv`](SWAP_FIXED_Q_IMAGE_PAIRS.csv)、[`SWAP_FIXED_Q_SUMMARY.csv`](SWAP_FIXED_Q_SUMMARY.csv)。结构计数与召回仍按各自有效诊断呈现，不并入这个九指标共同交集。

同一批严格混合事件按两视角难度分层：简单/简单 50 图对 B8L2 额外幅度均值 +1.377、40/50 正；困难/困难只有 2 图对，均值 +9.573、2/2 正。中等/困难 3 对、困难/中等 1 对也有较大幅度，但支持很少。完整分层与 D10、IoU、结构量见 [`SWAP_SUMMARY.csv`](SWAP_SUMMARY.csv)。这支持“效果随条件不同”的有限描述，不能把 2 对困难/困难当成普遍交互估计。严格混合子域的实际失败：结构类同类 B 图端 1,166/55,546，跨类 C 661/55,546；联合类 B 1,033/28,602、C 287/28,602。完整普通域也在 [`SWAP_ATTEMPTS.csv`](SWAP_ATTEMPTS.csv)。这些是重复团队的事件端尝试，**不能当独立失败率差的推断样本**。

### 原有向换类×难度：同一条件和同一评分支持

另接原 `manual_joint_A/all_registered_directions/q_down__faster` 的严格 ABC 条件 `ca2a651478a2ab2966a4`，沿原事件去重、固定背景→类对→图片→建筑等权，三端正式 Q 都可评才计算每项；这与上面的同房结构类图对是**不同实验**。原 Q 均值精确复现：简单 11图/11楼净 C−B **−1.247**（0/11图正），中等 2图/2楼 **+5.911**（2/2正），困难 9图/9楼 **+8.590**（6/9正）。同一支持上的 D10 分别 −1.097、+4.343、+7.940；底面 IoU −0.0071、−0.0035、+0.0107；IoU3D100 −0.821、−0.571、+0.905。方向残差 C−B 分别 +0.188°、−0.886°、−2.994°。将方向输入在三个既存端点均置零后重新代入固定评分模型，Q 差分别 −0.873、−0.514、+0.800；困难 3/9 图为正。**困难层平均增益很依赖此方向块，固定其它输入后并未完全消失；它不证明单独改变方向就能产生同样收益。**逐事件、逐图、逐难度见 [`DIRECTIONAL_SWAP_EVENTS.csv.gz`](DIRECTIONAL_SWAP_EVENTS.csv.gz)、[`DIRECTIONAL_SWAP_IMAGES.csv`](DIRECTIONAL_SWAP_IMAGES.csv)、[`DIRECTIONAL_SWAP_SUMMARY.csv`](DIRECTIONAL_SWAP_SUMMARY.csv)。

## 2. 困难人数过程：均值、波动和指标并列

普通困难 Manual 且可到20人的固定29图／15楼，24条自然路径各尝试一次。10→20人的已有边际 Q 均值变化 −0.216、中位 +0.662；**同一650条路径**两端正式 Q 可评、九指标均齐全时，B8L2 配对变化图等权平均 −0.532，14/29 图均值为正；D10 −0.748、底面 IoU **−0.0103**、IoU3D100 −0.924。早先按指标各自有效的底面 IoU −0.0127 使用660条路径，仍保留为广域诊断，不能与650条 Q 路径直接并列。后段平均接近平台与某些几何代理轻微退步可并存。已有底面换组波动 `V_floor_mean` 在 27/29 图下降，平均 −0.0431；同一资料的 Q 标准差 23/29 图下降。**V 是不同成员集合的底面差，不是质量**。原各指标有效的路径、逐图、逐楼结果仍见 [`NATURAL_PATH_METRICS.csv.gz`](NATURAL_PATH_METRICS.csv.gz)、[`NATURAL_IMAGE_METRICS.csv`](NATURAL_IMAGE_METRICS.csv)、[`NATURAL_BUILDING_METRICS.csv`](NATURAL_BUILDING_METRICS.csv)。

早段 3→6 在同一29图的**共同586条路径**上，B8L2 均值 +7.596、28/29 图为正；D10 +7.945、底面 IoU **+0.0511**、IoU3D100 +5.211。原各指标有效的底面 IoU +0.0514 使用592条路径；原主线的 **29/29** 来自各人数各自可评分路径的边际 `Q_mean_delta`。本次共同路径的 28/29 反例是 `pa4otMbVnkk-18`，19条两端可评路径平均 −0.610，而边际 Q 均值 +0.877。两个分母不能互换。共同路径逐项见 [`NATURAL_FIXED_Q_PATH_METRICS.csv.gz`](NATURAL_FIXED_Q_PATH_METRICS.csv.gz)、[`NATURAL_FIXED_Q_IMAGE_METRICS.csv`](NATURAL_FIXED_Q_IMAGE_METRICS.csv)、[`NATURAL_FIXED_Q_SUMMARY.csv`](NATURAL_FIXED_Q_SUMMARY.csv)；脚本断言九指标的精确 `(interval,pool_id,path_id)` 集合相同。10→20 困难路径 696 次尝试中，起点失败 29、终点失败 22；门洞17图的同区间 408 次尝试中为 82→64，失败不补零，详见 `NATURAL_FAILURE_*.csv`。

## 3. 高历史Q／较多转折先进入的前段

原主结论的共同域是普通 Manual、N≥20、四策略均存在的 **157图/22楼**，每策略与同一8条基础自然顺序配对，人数 `k=3..floor(N/2)`。本轮逐路径按同池/replicate/k取共同可评，先固定策略与自然两端**正式 B8L2 均可评**，再要求表中九项指标同样可评；先每图每k均值、再图内k等权、最后图等权。四策略 B8L2 与原保存点估计逐项误差 <1e−9。每策略表内九项拥有完全相同的有效路径：高Q 17,771、较多转折 17,723、较快 17,550、人数最多结构类 17,463；不同策略的有效路径仍各自不同。

| 优先规则 | B8L2 图均值；正图 | D10 | 底面 IoU | IoU3D100 | 方向置零 Q |
|---|---:|---:|---:|---:|---:|
| 联合历史高Q | +7.710；152/157 | +7.199 | +0.0387 | +4.716 | +5.703 |
| 结构较多转折 | +6.146；137/157 | +5.736 | +0.0304 | +3.778 | +4.461 |
| 联合历史较快 | −1.651；53/157 | −1.656 | −0.0125 | −1.414 | −2.006 |
| 历史人数最多结构类 | −1.845；40/157 | −1.695 | −0.0093 | −1.076 | −1.344 |

原两条升质策略在底面和均高棱柱代理上同向，方向置零后仍分别为 +5.703 和 +4.461；快类及人数最多结构类的平均Q代价也未消失。逐路径、逐图人数、逐图前段与同策略共同路径分母见 [`POLICY_ORIGINAL_COMMON_PATHS.csv.gz`](POLICY_ORIGINAL_COMMON_PATHS.csv.gz)、[`POLICY_ORIGINAL_COMMON_K.csv`](POLICY_ORIGINAL_COMMON_K.csv)、[`POLICY_ORIGINAL_COMMON_IMAGES.csv`](POLICY_ORIGINAL_COMMON_IMAGES.csv)、[`POLICY_ORIGINAL_COMMON_SUMMARY.csv`](POLICY_ORIGINAL_COMMON_SUMMARY.csv)。四策略共享图片与基础自然路径，但策略端有效路径集合未强制相同；本表是已观察相关，不是重新训练的前瞻政策检验。

另有更宽普通域的三个固定人数补充：在同池、相同 replicate、相同人数且保存 `paired_for_policy=true` 的共同支持上，`joint_highq_first` 相对自然顺序：k3 B8L2 平均 +13.646、166/174 图均值为正；k6 +9.775、162/174；k10 +6.869、162/170。`structure_moreturn_first` 分别为 +10.231、149/173；+7.760、145/172；+5.718、143/167。它的图片与人数域和上表不同，见 [`POLICY_IMAGE_METRICS.csv`](POLICY_IMAGE_METRICS.csv) 与 [`POLICY_PAIRED_METRICS.csv.gz`](POLICY_PAIRED_METRICS.csv.gz)。冻结排序的观察不能解释为 Q 或多转折是独立因果因素，亦不外推为新人规则。

## 4. 方向评分块的固定几何诊断

分析定义在计算前固定：在五项原测量值中仅把 `dir` 输入设为0，仍调用原 B8L2 模型，其余底面、底边、高度及参考不变；记作 **`B8L2_no_direction` 非正式诊断**。脚本先用原五项反算并逐端点核对正式 B8L2（最大误差 <1e−7），再计算该变体；不扫描尺度或权重，也不覆盖正式分数。

Manual 结构类严格混合78图对的跨类额外幅度从正式 B8L2 +1.960 变为方向置零 +1.177，仍有 58/78 图对为正；IoU3D100 与底面 IoU 的额外幅度也为正。困难29图的早段配对图均值从 +7.596 变为 +7.707，后段从 −0.532 变为 −1.512；高Q先进入 k3 的普通 Manual 174图中，方向置零仍有172图均值向好。方向块影响**幅度和个别方向**，没有让这些观察完全消失；差值不能称为方向项“因果贡献百分比”。指标敏感性也不等于四套分类对 Q 定义的稳定性，后者另需重新建类，本轮未做。

## 5. 适用界线

字段合同：`SWAP_ATTEMPTS` 一行=原严格ABC事件×视角，失败0/1保留全部尝试；`SWAP_VIEW_METRICS` 一行=事件×视角×指标且A/B/C同可评；`SWAP_EVENT_COMMON_VIEWS` 仅保留两视角共同支持；`SWAP_IMAGE_PAIRS`、`SWAP_BUILDINGS`、`SWAP_SUMMARY` 分别为配置等权图对、图对等权建筑、建筑等权难度层，`subset` 区分普通全域与 `D_n>0` 严格混合。`DIRECTIONAL_SWAP_EVENTS` 为原有向条件去重事件×指标，`DIRECTIONAL_SWAP_IMAGES` 与 `DIRECTIONAL_SWAP_SUMMARY` 沿原背景、类对、图、楼权重聚合。`NATURAL_PATH_METRICS` 一行=相同自然路径两个预设人数×指标且两端可评；`NATURAL_IMAGE_METRICS`/`NATURAL_BUILDING_METRICS` 再分层等权。`NATURAL_FIXED_Q_PATH_METRICS` 仅含普通困难 Manual、N≥20、两端正式 Q 与九指标共同可评路径×指标；`NATURAL_FIXED_Q_IMAGE_METRICS` 与 `NATURAL_FIXED_Q_SUMMARY` 分别为同一路径支持的逐图和图等权汇总。`NATURAL_FAILURE_3_6` 与 `NATURAL_FAILURE_10_20` 一行=实际路径尝试；`POLICY_PAIRED_METRICS` 一行=宽域同池同 replicate 同人数的优先/自然路径×指标。`POLICY_ORIGINAL_COMMON_PATHS/K/IMAGES/SUMMARY` 分别为157图主域的配对可评路径、每图人数、每图前段和图等权汇总。各指标保留原量纲，`B8L2_no_direction` 仅用于敏感性，不属于正式评分字段。

这些端点共享人员和图片，数十万路径/事件不是独立样本；图与建筑支持分别保留。IoU3D100 是同参考均高棱柱代理，不是完整真实房间体积 IoU。门洞满员6/17失败和相邻一票的定向机制见 [`doorway_vote_sensitivity_20261024`](../../fusion/doorway_vote_sensitivity_20261024/README.md)；不能把门洞缺Q当低Q。OOS正式Q仍无资格。
