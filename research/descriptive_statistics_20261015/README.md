# 现有研究数据详细描述统计（2026-10-15）

> 后续用户规则与数据已更新：只含1—2名有效标注者的图片暂不纳入分析；图片难度v3、39图新空间与GT错误排除需接入。[合并交接](../../docs/thesis_main/四线程成果与论文主线核对_20261015.md)第3.1节为准。本文数值/工作簿保留原快照，不表示已经应用这些新条件；原统计线程接续更新。


后续核验与扩展已接续：[独立审计](INDEPENDENT_AUDIT.md)、[关键数据可视化](figures/FIGURES.md)、[新增人员／批次及算法版本接入](EXTENSION_GUIDE.md)。独立复算入口为 `python -m tools.thesis_main.analysis.verify_descriptive_statistics_20261015`；本页以下保留原统计快照与分母。

本次接到新的本地整理与统计授权后，已实际执行描述统计并生成明细、汇总及可复用入口。上一轮“只整理文档、统计暂不执行”是该轮的历史事实，本报告不追改它。本次不固定论文大纲，不调参、不重新评分、不新增融合实验，不覆盖源标注或人工审核，不推送远端。

## 数据集合及分母

当前人员库存为 **3152 条**，涉及 **259 张图**、**27 人**、**22 栋建筑**。库存按人员×图片有 16 条超额记录，按人员×图片×条件有 14 条超额记录。这只是重复组合计数，不表示可直接删除；既有版本与资格仍由源记录裁决。

| 集合 | 记录数 | 人数 | 图数 | WQ有效数 | 用途 |
| --- | --- | --- | --- | --- | --- |
| inventory_3152 | 3152 | 27 | 259 | 1145 | 全部人员对象库存，保留失败、排除及未评分 |
| scored_1145 | 1145 | 24 | 135 | 1145 | 已冻结参考下的数值评分；含特殊与范围待定诊断 |
| worker_931 | 931 | 24 | 112 | 931 | 已有人员主画像集合；部分参考与难度目标尚不兼容 |
| target_836 | 836 | 24 | 95 | 836 | 普通图且参考与难度目标兼容的条件比较子集 |

四个集合各有用途，不能相加，也不能选一个数替代其余分母。库存中独立投票资格为真 2921 条，不等于这些记录都可评价、可进入人员画像或已人工认可。清洗状态、独立票、质量门和共识门在明细中分别保留；评分存在也不授予新资格。

| use_panel | 评分记录数 | 图片数 | 人数 |
| --- | --- | --- | --- |
| floor_only_target_equivalence | 54 | 4 | 23 |
| hold_scope_or_reference | 41 | 5 | 23 |
| image_only_different_target | 41 | 14 | 17 |
| ordinary_same_target_conditional | 836 | 95 | 24 |
| separate_secondary_or_exception | 56 | 14 | 18 |
| separate_special_or_pending | 117 | 11 | 24 |

931主画像包含836条同目标、54条仅底面等价和41条目标底面不同记录。后95条仍是原绑定参考下的人员描述，不能套用新难度目标解释完整质量。其余214条评分按场景、次层及范围保留；可计算分数不等于目标或资格已解决。

| 条件 | 清洗状态 | 记录数 |
| --- | --- | --- |
| manual | excluded_by_review | 62 |
| manual | historical_not_accepted | 79 |
| manual | retained | 2195 |
| manual | retained_pending | 8 |
| oos | excluded_by_review | 6 |
| oos | historical_not_accepted | 18 |
| oos | retained | 210 |
| semi | excluded_by_review | 17 |
| semi | historical_not_accepted | 36 |
| semi | retained | 518 |
| semi | retained_pending | 3 |

以下均值默认作答行等权，`image_equal_mean`另给先逐图平均再图片等权的结果。库存平均时间会保留库存中不同条件和资格的覆盖；正式比较须筛选相同条件与适用集合。缺失不是低分，不可计算、参考不适用和未冻结时间均不补零。

库存原评分状态如下；它与独立票或主质量资格不同。

| ledger_score_status | 记录数 |
| --- | --- |
| conditional_full | 115 |
| conditional_scope_diagnostic | 10 |
| floor | 217 |
| full | 1010 |
| geometry_unavailable | 3 |
| held | 1259 |
| historical_only | 10 |
| oos_not_applicable | 406 |
| route_unavailable | 1 |
| target_version_unresolved | 121 |

原账本已有的部分指标也单独保留在`ledger_*`列和[部分指标覆盖表](ledger_metric_coverage.csv)：尤其仅底面可算记录的底面IoU、底角误差和原floor_WQ，不因缺少完整WQ而丢弃。这些值沿用`ledger_reference_id`与原状态，未与1145条完整评分或新难度目标自动合并；floor_WQ不是完整WQ。

## 质量与时间总体分布

| 集合 | 指标 | 集合记录数 | 有效n | 缺失n | 有效图数 | 均值 | 中位数 | 样本SD | P25 | P75 | IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| inventory_3152 | WQ | 3152 | 1145 | 2007 | 135 | 57.098 | 57.318 | 23.303 | 39.188 | 76.492 | 37.303 |
| inventory_3152 | A10 | 3152 | 1145 | 2007 | 135 | 61.616 | 65.167 | 23.609 | 44.580 | 81.348 | 36.768 |
| inventory_3152 | B8L2 | 3152 | 1145 | 2007 | 135 | 63.925 | 67.272 | 22.739 | 47.656 | 82.558 | 34.901 |
| inventory_3152 | IoU3D100 | 3152 | 1145 | 2007 | 135 | 75.902 | 80.355 | 17.219 | 68.257 | 88.424 | 20.167 |
| inventory_3152 | active_time_seconds | 3152 | 1949 | 1203 | 214 | 226.036 | 135 | 344.043 | 60 | 259 | 199 |
| scored_1145 | WQ | 1145 | 1145 | 0 | 135 | 57.098 | 57.318 | 23.303 | 39.188 | 76.492 | 37.303 |
| scored_1145 | A10 | 1145 | 1145 | 0 | 135 | 61.616 | 65.167 | 23.609 | 44.580 | 81.348 | 36.768 |
| scored_1145 | B8L2 | 1145 | 1145 | 0 | 135 | 63.925 | 67.272 | 22.739 | 47.656 | 82.558 | 34.901 |
| scored_1145 | IoU3D100 | 1145 | 1145 | 0 | 135 | 75.902 | 80.355 | 17.219 | 68.257 | 88.424 | 20.167 |
| scored_1145 | active_time_seconds | 1145 | 631 | 514 | 102 | 218.639 | 137 | 338.258 | 65 | 243 | 178 |
| worker_931 | WQ | 931 | 931 | 0 | 112 | 60.792 | 60.870 | 20.963 | 44.312 | 77.415 | 33.102 |
| worker_931 | A10 | 931 | 931 | 0 | 112 | 65.698 | 68.755 | 20.775 | 49.378 | 82.396 | 33.018 |
| worker_931 | B8L2 | 931 | 931 | 0 | 112 | 67.875 | 71.174 | 19.862 | 52.639 | 83.817 | 31.178 |
| worker_931 | IoU3D100 | 931 | 931 | 0 | 112 | 78.869 | 82.228 | 14.260 | 72.045 | 89.046 | 17.000 |
| worker_931 | active_time_seconds | 931 | 526 | 405 | 86 | 189.451 | 124.500 | 239.478 | 59 | 221 | 162 |
| target_836 | WQ | 836 | 836 | 0 | 95 | 63.191 | 63.953 | 19.497 | 47.547 | 78.954 | 31.407 |
| target_836 | A10 | 836 | 836 | 0 | 95 | 68.219 | 71.197 | 18.994 | 54.634 | 83.062 | 28.428 |
| target_836 | B8L2 | 836 | 836 | 0 | 95 | 70.231 | 72.796 | 18.159 | 57.253 | 84.550 | 27.297 |
| target_836 | IoU3D100 | 836 | 836 | 0 | 95 | 79.852 | 83.149 | 13.228 | 73.278 | 89.288 | 16.010 |
| target_836 | active_time_seconds | 836 | 466 | 370 | 75 | 185.204 | 120 | 246.556 | 57 | 209 | 152 |

WQ、A10、B8L2沿用已有冻结评分，并列保留版本；用户偏好B8L2不等于已宣布它为唯一最终公式。IoU3D100为现用均高棱柱3D IoU乘100，不是任意实体的精确IoU。底面IoU、底角误差、方向与高度分项见各汇总表；其量纲和优劣方向不能直接相加比较。WQ未覆盖的库存记录应结合`ledger_score_status`、资格及范围状态解释，不解释为已观察到的低质量。

| 评分台账状态 | 库存记录数 | 已有WQ数 |
| --- | --- | --- |
| conditional_full | 115 | 115 |
| conditional_scope_diagnostic | 10 | 10 |
| floor | 217 | 0 |
| full | 1010 | 1010 |
| geometry_unavailable | 3 | 0 |
| held | 1259 | 0 |
| historical_only | 10 | 10 |
| oos_not_applicable | 406 | 0 |
| route_unavailable | 1 | 0 |
| target_version_unresolved | 121 | 0 |

## 图片难度：库存覆盖与同目标比较

| 版本 | 粗类 | 库存图数 |
| --- | --- | --- |
| scope_preferred_difficulty_20261011_v2 | 中等 | 30 |
| scope_preferred_difficulty_20261011_v2 | 单列 | 42 |
| scope_preferred_difficulty_20261011_v2 | 困难 | 38 |
| scope_preferred_difficulty_20261011_v2 | 待复核 | 5 |
| scope_preferred_difficulty_20261011_v2 | 简单 | 144 |

粗类是当前采用目标范围下的分类；“单列”和“待复核”保留独立身份。不能用旧结构粗类替代当前版本，也不能把同目标子集的图数当成全库图数。

| 难度 | 指标 | 集合记录数 | 有效n | 缺失n | 有效图数 | 均值 | 中位数 | 样本SD | P25 | P75 | IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 中等 | WQ | 80 | 80 | 0 | 10 | 49.322 | 47.583 | 18.018 | 36.472 | 59.965 | 23.493 |
| 中等 | A10 | 80 | 80 | 0 | 10 | 53.722 | 53.995 | 19.092 | 37.827 | 67.543 | 29.716 |
| 中等 | B8L2 | 80 | 80 | 0 | 10 | 56.479 | 57.338 | 18.442 | 40.378 | 70.721 | 30.343 |
| 中等 | IoU3D100 | 80 | 80 | 0 | 10 | 74.039 | 76.920 | 12.368 | 68.315 | 81.585 | 13.271 |
| 中等 | active_time_seconds | 80 | 56 | 24 | 9 | 201.089 | 145.500 | 286.633 | 66 | 224.250 | 158.250 |
| 困难 | WQ | 85 | 85 | 0 | 14 | 56.985 | 57.738 | 16.930 | 44.968 | 71.047 | 26.079 |
| 困难 | A10 | 85 | 85 | 0 | 14 | 62.517 | 65.713 | 16.900 | 53.275 | 74.702 | 21.427 |
| 困难 | B8L2 | 85 | 85 | 0 | 14 | 64.599 | 67.874 | 16.425 | 54.831 | 76.564 | 21.733 |
| 困难 | IoU3D100 | 85 | 85 | 0 | 14 | 78.581 | 80.728 | 12.218 | 74.087 | 85.973 | 11.886 |
| 困难 | active_time_seconds | 85 | 65 | 20 | 13 | 212.785 | 139 | 299.189 | 87 | 238 | 151 |
| 简单 | WQ | 671 | 671 | 0 | 71 | 65.631 | 67.064 | 19.124 | 50.628 | 81.165 | 30.537 |
| 简单 | A10 | 671 | 671 | 0 | 71 | 70.670 | 73.682 | 18.319 | 57.612 | 85.851 | 28.239 |
| 简单 | B8L2 | 671 | 671 | 0 | 71 | 72.584 | 76.181 | 17.461 | 59.909 | 86.819 | 26.910 |
| 简单 | IoU3D100 | 671 | 671 | 0 | 71 | 80.706 | 84.467 | 13.279 | 74.176 | 90.471 | 16.295 |
| 简单 | active_time_seconds | 671 | 345 | 326 | 53 | 177.429 | 116 | 228.336 | 50 | 203 | 153 |

上表每档的集合记录数、有效数和有效图数同时展示。三档的人员组成、建筑及每图作答数不同；均值差异只是当前覆盖下的描述，不证明难度的独立作用，也不由结果反向修改难度标签。时间缺失可能改变比较对象，不能把质量与时间的不同有效分母默认为同一批作答。

实际结果并非随三档单调下降：简单、中等、困难的原WQ均值分别为65.63、49.32、56.98；B8L2分别为72.58、56.48、64.60。中等与困难仅覆盖10图和14图，且任务组成不同，不能据此认定中等固有地更难。

## 门洞、OOS、可标性与范围

这些是不同分轴。OOS未知不能认证正常；门洞可标性未决不等于不可标；非正交但清晰可标也不能与曲面、多层等表示限制合并。范围待定、仅底面参考和顶部待核独立保留。

| 分轴 | 状态 | 图数 |
| --- | --- | --- |
| oos_axis | no | 37 |
| oos_axis | pending | 1 |
| oos_axis | unknown | 196 |
| oos_axis | yes | 25 |
| doorway_axis | no | 23 |
| doorway_axis | unknown | 217 |
| doorway_axis | yes | 19 |
| markability_from_explicit_label | conditional_nonorthogonal_annotatable | 2 |
| markability_from_explicit_label | recorded_doorway_annotatable | 2 |
| markability_from_explicit_label | unknown_not_inferred_from_difficulty | 255 |
| top_boundary_pending |  | 226 |
| top_boundary_pending | True | 33 |

OOS×门洞的逐图交集如下；unknown/pending原样保留，未记录不推成否。

| oos_axis | doorway_axis | 图数 |
| --- | --- | --- |
| no | no | 22 |
| no | unknown | 13 |
| no | yes | 2 |
| pending | unknown | 1 |
| unknown | unknown | 181 |
| unknown | yes | 15 |
| yes | no | 1 |
| yes | unknown | 22 |
| yes | yes | 2 |

| 分轴 | 状态 | 指标 | 集合记录数 | 有效n | 缺失n | 有效图数 | 均值 | 中位数 | 样本SD | P25 | P75 | IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| oos_axis | no | WQ | 574 | 273 | 301 | 26 | 68.936 | 75.240 | 20.526 | 51.825 | 84.657 | 32.832 |
| oos_axis | pending | WQ | 2 | 0 | 2 | 0 | — | — | — | — | — | — |
| oos_axis | unknown | WQ | 2172 | 872 | 1300 | 109 | 53.391 | 53.608 | 22.890 | 35.897 | 71.300 | 35.403 |
| oos_axis | yes | WQ | 404 | 0 | 404 | 0 | — | — | — | — | — | — |
| doorway_axis | no | WQ | 199 | 84 | 115 | 17 | 73.062 | 79.600 | 19.829 | 60.278 | 89.651 | 29.373 |
| doorway_axis | unknown | WQ | 2713 | 936 | 1777 | 106 | 59.485 | 59.482 | 21.382 | 43.001 | 76.344 | 33.343 |
| doorway_axis | yes | WQ | 240 | 125 | 115 | 12 | 28.492 | 27.449 | 16.077 | 17.876 | 36.438 | 18.562 |
| special_layer | doorway | WQ | 217 | 125 | 92 | 12 | 28.492 | 27.449 | 16.077 | 17.876 | 36.438 | 18.562 |
| special_layer | oos | WQ | 381 | 0 | 381 | 0 | — | — | — | — | — | — |
| special_layer | oos_pending | WQ | 2 | 0 | 2 | 0 | — | — | — | — | — | — |
| special_layer | other | WQ | 2529 | 1020 | 1509 | 123 | 60.603 | 60.789 | 21.575 | 43.931 | 78.252 | 34.321 |
| special_layer | overlap | WQ | 23 | 0 | 23 | 0 | — | — | — | — | — | — |

特殊层中有数值分数不自动表示主质量适用；同参考分数、范围未决诊断和正式可评价覆盖必须区分。完整分轴、难度交集和人员条件差异分别见`by_scene`、`scene_intersections`、`by_scene_intersections`和`worker_scene`表；稀疏组合保留样本量，不强行形成方向性结论。

## 有效标注时间与来源核对

| 条件 | 时间状态 | 记录数 |
| --- | --- | --- |
| manual | historical_time_ineligible | 102 |
| manual | known_manual_adjustment | 83 |
| manual | lead_time_fallback | 180 |
| manual | new_collection_time_unfrozen | 651 |
| manual | usable | 1328 |
| oos | lead_time_fallback | 54 |
| oos | usable | 180 |
| semi | historical_time_ineligible | 14 |
| semi | lead_time_fallback | 119 |
| semi | usable | 441 |

时间单位为秒。按项目、运行任务、人员连接冻结时间上下文，再经历史canonical身份核对图片、建筑和条件。`active_time_seconds`仅保留合格时间；`raw_active_time_seconds`保留原值以便审计，不能用于填补有效时间。`timing_status`、`time_source`、`time_source_file`、`time_rule_version`保留原规则与来源。lead_time是另一种日志量，未用它替代active_time。已知人工加秒记录排除于有效秒数。

新增项目93/94/95的日志存在，但现有分析明确标为时间未冻结，因此本次继续留空，不能写成“这些人没有时间日志”。历史时间未重估，也没有重新冻结新增批次。

本次复用既有`worker_behavior_time_20260910.audit_sources`做来源一致性核对：P1的1128条、C2-B的160条、C2-A-RP两批各40条以及C1的780条，数值和状态均无不一致。C1的26份冻结与现存日志逐事件一致，字节差异来自表示形式，未据此修改任何时间。只读扫描active_logs的261份JSONL共78286事件，无JSON解析错误；项目93/94/95共5712事件。这些是本次核对的审计证据，不是新增有效时间样本。

## 逐图、逐人、建筑与共同参考对照

`by_image`给出逐图质量及时间；`by_worker`给出逐人原始平均；`by_building`给出建筑覆盖。`worker_difficulty`、`worker_scene`、`worker_room_type`、`worker_building`用于核查个人任务组成，每项都保留n、中位数、SD、分位数和缺失。原始人员平均不命名为能力排名。房间类型是已有空间粗类，不是已确认的物理房间ID；建筑也不等于房间。

共同参考对照在同图片×条件×reference_id单元中，比较个人值与其余人员均值。`peer_records`保存逐项差值，`worker_peer_comparison`汇总该人员有共同对照的单元。只有一个人的单元保留对照缺失；这比跨不同任务直接比较原始均值更可解释，仍受共同图覆盖、对照人员组成及稀疏性影响，不自动消除人员选择或建筑差异。

| worker_id | 集合记录数 | 有效n | 缺失n | 有效图数 | 均值 | 中位数 | 样本SD | P25 | P75 | IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| W001 | 37 | 36 | 1 | 36 | -7.369 | -7.169 | 14.398 | -17.341 | 2.064 | 19.406 |
| W002 | 36 | 35 | 1 | 35 | 11.158 | 10.243 | 20.165 | 2.901 | 24.914 | 22.013 |
| W006 | 37 | 37 | 0 | 37 | -2.893 | -0.594 | 11.660 | -9.651 | 5.339 | 14.989 |
| W008 | 37 | 37 | 0 | 37 | 3.957 | 5.026 | 14.883 | -4.091 | 14.413 | 18.505 |
| W010 | 33 | 33 | 0 | 33 | -2.710 | -0.629 | 13.287 | -7.582 | 6.064 | 13.647 |
| W011 | 27 | 26 | 1 | 26 | -1.420 | -1.035 | 9.386 | -5.576 | 5.285 | 10.861 |
| W012 | 34 | 33 | 1 | 33 | -14.310 | -18.290 | 13.663 | -23.286 | -6.363 | 16.922 |
| W013 | 33 | 31 | 2 | 31 | -1.387 | -0.915 | 10.569 | -8.718 | 4.681 | 13.399 |
| W014 | 19 | 19 | 0 | 19 | 0.330 | 3.254 | 10.735 | -5.094 | 5.833 | 10.926 |
| W015 | 41 | 41 | 0 | 41 | 4.908 | 4.020 | 13.319 | -0.584 | 9.541 | 10.126 |
| W017 | 38 | 37 | 1 | 37 | -1.506 | -1.366 | 10.137 | -7.226 | 5.339 | 12.564 |
| W018 | 19 | 19 | 0 | 19 | 5.208 | 5.125 | 20.147 | -8.385 | 19.168 | 27.554 |
| W021 | 10 | 10 | 0 | 10 | 2.156 | 5.047 | 9.864 | -3.248 | 6.662 | 9.910 |
| W027 | 22 | 22 | 0 | 22 | 21.260 | 21.459 | 16.981 | 12.186 | 31.259 | 19.073 |
| W028 | 37 | 36 | 1 | 36 | -4.012 | -5.602 | 14.537 | -12.302 | 4.980 | 17.281 |
| W029 | 38 | 37 | 1 | 37 | 4.701 | 2.676 | 11.348 | -3.335 | 12.724 | 16.059 |
| W030 | 42 | 40 | 2 | 40 | 1.597 | 1.045 | 10.946 | -3.579 | 8.826 | 12.405 |
| W031 | 48 | 48 | 0 | 48 | -1.895 | 0.804 | 12.451 | -9.941 | 6.134 | 16.075 |
| W032 | 45 | 45 | 0 | 45 | -7.634 | -8.442 | 12.410 | -15.793 | 1.197 | 16.990 |
| W033 | 47 | 47 | 0 | 47 | 4.815 | 3.735 | 12.263 | -1.928 | 12.425 | 14.353 |
| W034 | 45 | 45 | 0 | 45 | -5.013 | -5.412 | 14.680 | -14.488 | 5.288 | 19.777 |
| W035 | 42 | 40 | 2 | 40 | 3.570 | 2.174 | 11.288 | -5.528 | 13.593 | 19.122 |
| W036 | 36 | 35 | 1 | 35 | 9.896 | 14.131 | 19.955 | 2.773 | 20.598 | 17.825 |
| W037 | 33 | 33 | 0 | 33 | -12.482 | -14.609 | 13.680 | -19.020 | -3.022 | 15.998 |

上表为同目标集合的WQ共同参考差值：正数表示比该单元其他人员的均值高，负数表示低。按稳定人员ID排列，不按分数排序。不能把有限单元的差值称为人员能力或因果效果。

## 同集合的评分版本与时间关联

| 集合 | 配对差值 | 集合记录数 | 有效n | 缺失n | 有效图数 | 均值 | 中位数 | 样本SD | P25 | P75 | IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scored_1145 | A10-WQ | 1145 | 1145 | 0 | 135 | 4.519 | 4.027 | 3.361 | 1.487 | 7.154 | 5.667 |
| scored_1145 | B8L2-WQ | 1145 | 1145 | 0 | 135 | 6.828 | 7.645 | 4.063 | 3.033 | 10.298 | 7.265 |
| scored_1145 | B8L2-A10 | 1145 | 1145 | 0 | 135 | 2.309 | 2.098 | 1.886 | 0.682 | 3.700 | 3.017 |
| scored_1145 | IoU3D100-WQ | 1145 | 1145 | 0 | 135 | 18.804 | 18.288 | 13.294 | 6.930 | 30.121 | 23.191 |
| worker_931 | A10-WQ | 931 | 931 | 0 | 112 | 4.906 | 4.689 | 3.380 | 1.948 | 7.607 | 5.659 |
| worker_931 | B8L2-WQ | 931 | 931 | 0 | 112 | 7.083 | 7.935 | 4.047 | 3.474 | 10.463 | 6.990 |
| worker_931 | B8L2-A10 | 931 | 931 | 0 | 112 | 2.177 | 1.967 | 1.798 | 0.675 | 3.410 | 2.735 |
| worker_931 | IoU3D100-WQ | 931 | 931 | 0 | 112 | 18.077 | 16.856 | 13.235 | 6.586 | 28.984 | 22.399 |
| target_836 | A10-WQ | 836 | 836 | 0 | 95 | 5.028 | 4.874 | 3.408 | 2.015 | 7.830 | 5.815 |
| target_836 | B8L2-WQ | 836 | 836 | 0 | 95 | 7.040 | 7.761 | 4.055 | 3.402 | 10.544 | 7.141 |
| target_836 | B8L2-A10 | 836 | 836 | 0 | 95 | 2.012 | 1.801 | 1.658 | 0.654 | 3.145 | 2.491 |
| target_836 | IoU3D100-WQ | 836 | 836 | 0 | 95 | 16.661 | 15.539 | 12.440 | 5.827 | 26.450 | 20.623 |

所有配对差值使用同输入、同绑定参考与同资格集合；分数整体升高是公式输出变化，不是“更正确”的验证，也不据此逐例择高分或调参。

| 集合 | 质量指标 | 共同有效n | 缺失n | 集合图数 | Spearman相关 |
| --- | --- | --- | --- | --- | --- |
| scored_1145 | WQ | 631 | 514 | 135 | -0.097 |
| scored_1145 | A10 | 631 | 514 | 135 | -0.095 |
| scored_1145 | B8L2 | 631 | 514 | 135 | -0.096 |
| scored_1145 | IoU3D100 | 631 | 514 | 135 | -0.066 |
| worker_931 | WQ | 526 | 405 | 112 | -0.055 |
| worker_931 | A10 | 526 | 405 | 112 | -0.057 |
| worker_931 | B8L2 | 526 | 405 | 112 | -0.058 |
| worker_931 | IoU3D100 | 526 | 405 | 112 | -0.033 |
| target_836 | WQ | 466 | 370 | 95 | -0.028 |
| target_836 | A10 | 466 | 370 | 95 | -0.032 |
| target_836 | B8L2 | 466 | 370 | 95 | -0.034 |
| target_836 | IoU3D100 | 466 | 370 | 95 | -0.027 |

相关只在质量和有效时间均非缺失的记录计算；分难度×条件的结果见`time_quality`。该表的n_images是原集合图数，共同有效覆盖须结合有效n与明细检查。重复人员、图片和建筑形成相关结构，因此这里只作描述，不给独立样本显著性推断，不能从相关推出花时更多使质量提高或降低。

## 已确认同房图片

同房关系、视点差异、每图平均与共同人员的逐对比较见[同房说明](SAME_ROOM_NOTES.md)。主表以同目标集合为准，旧人员主画像另存后缀`_931`；后缀`_manual_inventory`使用库存中独立Manual作答观察有效时间，不扩大质量资格。不靠关系传递新增同房事实，未记录同房不等于确认异房。

## 明细与汇总导航

CSV使用UTF-8 BOM，可按表头在Excel等工具筛选；列表及字典单元格采用JSON。`tables.json`（本地可重建聚合副本，Git保留逐表CSV）与CSV为同一份计算结果，[FIELD_CONTRACT.json](FIELD_CONTRACT.json)列出字段、单位、集合、评分版本及缺失约定。

| 表 | 行数 | 字段数 |
| --- | --- | --- |
| [records.csv](records.csv) | 3152 | 118 |
| [overview.csv](overview.csv) | 40 | 19 |
| [images.csv](images.csv) | 259 | 30 |
| [ledger_metric_coverage.csv](ledger_metric_coverage.csv) | 90 | 20 |
| [by_image.csv](by_image.csv) | 6010 | 20 |
| [by_worker.csv](by_worker.csv) | 990 | 20 |
| [by_building.csv](by_building.csv) | 840 | 20 |
| [by_difficulty.csv](by_difficulty.csv) | 160 | 20 |
| [by_condition.csv](by_condition.csv) | 70 | 20 |
| [by_use.csv](by_use.csv) | 170 | 20 |
| [by_ledger_status.csv](by_ledger_status.csv) | 160 | 20 |
| [by_room_type.csv](by_room_type.csv) | 410 | 20 |
| [by_time_status.csv](by_time_status.csv) | 200 | 20 |
| [worker_difficulty.csv](worker_difficulty.csv) | 3670 | 21 |
| [worker_room_type.csv](worker_room_type.csv) | 8400 | 21 |
| [worker_building.csv](worker_building.csv) | 14240 | 21 |
| [by_scene.csv](by_scene.csv) | 500 | 21 |
| [worker_scene.csv](worker_scene.csv) | 6710 | 22 |
| [by_scene_intersections.csv](by_scene_intersections.csv) | 430 | 22 |
| [scene_intersections.csv](scene_intersections.csv) | 19 | 6 |
| [score_comparison.csv](score_comparison.csv) | 12 | 23 |
| [peer_records.csv](peer_records.csv) | 10359 | 12 |
| [worker_peer_comparison.csv](worker_peer_comparison.csv) | 285 | 21 |
| [time_quality.csv](time_quality.csv) | 60 | 8 |
| [same_room_relations.csv](same_room_relations.csv) | 756 | 24 |
| [same_room_pair_metrics.csv](same_room_pair_metrics.csv) | 3780 | 68 |
| [same_room_worker_pairs.csv](same_room_worker_pairs.csv) | 3325 | 30 |
| [same_room_relations_931.csv](same_room_relations_931.csv) | 756 | 24 |
| [same_room_pair_metrics_931.csv](same_room_pair_metrics_931.csv) | 3780 | 68 |
| [same_room_worker_pairs_931.csv](same_room_worker_pairs_931.csv) | 3760 | 30 |
| [same_room_relations_manual_inventory.csv](same_room_relations_manual_inventory.csv) | 756 | 24 |
| [same_room_pair_metrics_manual_inventory.csv](same_room_pair_metrics_manual_inventory.csv) | 3780 | 68 |
| [same_room_worker_pairs_manual_inventory.csv](same_room_worker_pairs_manual_inventory.csv) | 11150 | 30 |

## 来源、复用及验证

输入沿[当前统一包manifest](../../analysis_results/research_input_20260929/manifest.json)读取，参考[研究数据说明](../../docs/thesis_main/研究数据说明_来源预处理与用途_20261006.md)；本次不重建统一包。最新图轴取[图片覆盖表](../difficulty_special_coverage_20261015/image_coverage_259.csv)，质量与范围绑定取[评分接入表](../difficulty_target_integration_20261015/quality_bindings_1145.csv)，A10/B8L2取[冻结A/B分数](../quality_ab_feedback_handoff_20261015/prior_AB/results/SCORES_1145.csv)，人员集合取[四轴人员面板](../worker_four_axis_update_20261015/quality_panel_931.csv)。全库存评分台账及冻结几何快照取[质量收尾审查包](../quality_joint_closeout_review_20261015/pro_closeout_delta.zip)，主生成器验证其几何快照与当前loader一致。时间取[冻结上下文](../../analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/active_time_context.csv.gz)，身份另核对[annotation_spine](../../analysis_results/uncertainty_cloud_inputs_20260906_v1/facts/annotation_spine.csv.gz)。这些派生入口只消费其声明用途，不升格为原始标注真源。

可复用生成入口：

```powershell
python -m tools.thesis_main.analysis.descriptive_statistics_20261015
```

主生成器读取现有版本化输入，检查稳定身份、评分集合与参考一致性后生成统计；报告函数直接消费同一份tables，不另行评分。[工作簿](现有研究数据描述统计.xlsx)是同一快照的筛选查阅版，全部指标与审计字段保留在CSV。工作簿生成器为[descriptive_statistics_workbook_20261015.mjs](../../tools/thesis_main/analysis/descriptive_statistics_workbook_20261015.mjs)，从可解析artifact-tool的工作目录使用捆绑Node运行；验证记录见[WORKBOOK_VERIFICATION.json](WORKBOOK_VERIFICATION.json)。

关键边界检查包括：库存对象ID唯一，评分记录与库存身份一致，A/B的对象、人员、图片、条件、参考及WQ一致，人员与同目标集合包含关系，图片轴一图一行且版本一致；缺失时间不得回填lead_time，人工加秒记录不得进入有效时间，同房证据不传递扩充。实际测试命令和结果以本次交付记录为准。

## 剩余边界与最少未决问题

范围或顶部仍待定的图继续保留其原状态，本次不要求用户重复已有审核。若后续需要把这些记录升级为主质量结论，只需针对尚未确认的目标／参考适用性补证据；若后续需要新增人员的时间比较，需要单独完成新增批次的时间冻结。评分最终公式尚未确定，当前并列版本足以继续描述比较，无需为本次报表先选唯一公式。小样本、未记录图轴和不均衡人员／建筑组成会限制外推；本报告不宣称总体规律或因果效应。

本次未重评分、未运行新融合、未重估旧active_time、未推送远端。仍需注意：数值可计算与参考适用、独立作答及人工认可各有边界，不能互相替代。

实际改动范围、13项测试与定向检查见[交付及验证记录](HANDOFF.md)。

归档说明：逐表CSV、合同及交付工作簿入Git；重复聚合的`tables.json`仅留本地，可运行对应生成器重建后再生成工作簿。
