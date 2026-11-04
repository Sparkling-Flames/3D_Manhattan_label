# 指标、支持与身份字段

## 1. 身份与方向

| 字段 | 含义 |
| --- | --- |
| `analysis_cohort` | `legacy_current_label_conditional`为当前标签合法旧存量；`batch12_strictABC_direct_legs`为批12保存端点的AC/BC腿；`current_capacity_gap_supplement`为本轮冻结补缺；`legacy_plus_capacity_gap`仅为主目标14/7、20/7旧存量与不重叠补缺图合并显示 |
| `scope` | `primary`普通Manual原目标；`other_admitted`其它已准入目标。不可混合解释 |
| `pool_id`,`reference_id`,`reference_version` | 精确目标池与参考身份；其它目标同图可有多个池 |
| `n`,`m`,`replacement_fraction` | 相同A/C人数、相等X/Z换块人数、m/n；D人数为n−m |
| `D_workers`,`X_workers`,`Z_workers` | 以竖线分隔的具体成员；A=D∪X、C=D∪Z，三个集合两两不相交 |
| `D_current_C1/C2/C3/unknown` | 按该目标图楼外折当前标签统计的D人数；未知背景不自动剔除 |
| `D_category` | 当前实际背景为混类、纯类、空背景或含未知标签；不是旧设计名称的改名 |
| `design_status` | 原特定合同仍成立，或仅通用AC合法。后者不据旧pure/neutral名称作当前设计结论 |
| `canonical_physical_pair_id` | 物理A/C无向对身份；每来源条件一次，不被多个方法链接重复计权 |
| `class_pair`,`direction` | 当前类别的无向对及当前展示方向。物理底表统一较低编号→较高编号 |
| `source_class_current`,`target_class_current` | 与物理底表规范化A/C绑定的当前类别 |
| `current_source_class`,`current_target_class`,`current_direction` | 在物理底表中与上述规范化字段同义；没有保留相反端点方向 |
| `registered_current_*` | 原事件在当前标签下的登记方向，可能与规范化展示相反；原旧TARGET方向另保留原字段 |
| `orientation_sign` | 原登记向与规范向的关系，−1表示规范化时交换A/C与X/Z；时间、分项符号同步处理 |
| `orientation_sign_view` | 六方向结果的±1展示视图，反向不是新验证 |
| `event_id`,`original_event_id`,`source_leg`,`source_registry` | 原方法事件和源表身份。批12多腿可指向同一物理对，见别名表 |

## 2. 质量、结构与位置

`A_`、`C_`前缀为规范化两端保存值；`delta_`统一为C−A。质量误差降低为负，质量/召回提高为正，表达数量增加本身不保证更好。

| 指标 | 单位、解释 |
| --- | --- |
| `B8L2`,`Q_A`,`Q_C`,`dQ` | 本轮主Q，0–100分；dQ=Q_C−Q_A |
| `D10` | 原正式体系保存的另一质量总分，0–100；作为分项接续，不替代主Q |
| `IoU3D100` | 3D IoU×100，差值为百分点；不是Q本身 |
| `iou_2d` | 底面2D IoU，0–1比例；差值0.01对应1个百分点 |
| `S_bottom_deg` | 原评分底边位置/角误差，度，越低越好 |
| `dir` | 原方向误差，度，越低越好 |
| `Hmean`,`Hcenter` | 全局/局部高度相对偏差，无量纲，越低越好 |
| `omission`,`extension` | 参考范围遗漏/预测外扩比例，0–1；分母遵循保存的原指标定义，不交换两者 |
| `nodes` | 被融合选中的节点数，不等同于有效转折数 |
| `fusion_turn_n` | 原融合端点有效转折数：底面相邻有向边转向角>5°的节点数 |
| `fusion_short_turn_edges` | 原短结构边数：边长/周长<0.04且该边两端转向角均≥15°；继承原阈值，未重新选择尺度 |
| `fusion_redundancy_n` | 原近共线/冗余节点数：上述转向角≤5°；表达差异而非独立质量分 |
| `ref_node_recall_9`,`ref_edge_recall_9` | 原9°参考节点/边召回比例，保留原对应口径 |
| `geometry_area_h2` | 底面面积，以相机高度平方归一化，描述范围大小 |
| `matched_ref_top_abs_deg`,`matched_ref_bottom_abs_deg` | 在参考水平匹配≤9°的角点对上，上/下边纵向绝对角误差的均值 |
| `matched_ref_horizontal_abs_deg` | 上述被接受匹配的水平绝对角误差均值 |
| `matched_ref_pair_fraction` | 被接受匹配数/参考角点对数；每端匹配集合可能不同，需与误差均值一起解读 |
| `geometry_bev_distance_AC` | A/C底面多边形的1−IoU，描述两融合结果的形状/位置变化，不直接衡量对GT优劣 |
| `geometry_centroid_distance_AC` | A/C底面质心距离，以相机高度归一化 |
| `geometry_log_area_distance_AC` | A/C底面积比绝对对数，描述范围尺度变化 |
| `geometry_pair_angle_AC` | A/C角点对通过全局分配匹配后，每对上/下角距离较大者的均值，度 |
| `geometry_top_angle_AC`,`geometry_bottom_angle_AC` | 同一A/C角点对分配下，上/下点角距离均值，度 |
| `geometry_unmatched_pairs_AC` | 两端角点对数量之差的绝对值；不是按语义判断遗漏 |
| `geometry_same_pair_count_AC`,`same_node_count` | 两端点对数/选中节点数相等的描述标志；不蕴含位置、对应、连线相同 |

新补端点的参考匹配与A/C几何距离沿用 `research/workers/personnel_v21_reselection_20261029/analysis/legacy_geometry_diagnostics.py`。参考水平坐标按1024宽全景环绕最短距离转角，再用全局线性分配；匹配集合随端点改变。表达分项的冻结定义见 `research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py` 中 `expression()`。旧端点分项均直接复用原metric shard。

## 3. Q五输入算术分解

令I为2D IoU，S为底边角误差，D为方向角误差，Hm/Hc为全局/局部高度偏差：

```text
b = S²/32
d = 1.5 D²/(D²+64)
h = (Hm/0.8)²+(Hc/0.25)²
Q = 100 I / [I + hypot(1−I+I b, I d) + I h]
```

`Q_term_range_2d_IoU/bottom_boundary/direction/global_height/local_height`是改变相应输入对ΔQ的算术贡献。枚举5输入全部32子集，按`k!(4−k)!/5!`加权计算加入该输入的边际差；等价全部120种代入次序的平均。每个物理对五项相加等于保存的实际dQ，之后再按冻结权重汇总。不能将图均指标先代入公式代替逐对分解；两者一般不等。

中间混合输入不是新几何，此分解不证明机制因果或中介路径。Q原本不可得的端点不做分解、不构造假0分改善。

## 4. 支持、汇总和不确定性

| 字段 | 解释 |
| --- | --- |
| `version` | `automatic`原自动端点；`manual_order_assisted`只接入已批准且成员/目标/参考完全相同的人工顺序端点 |
| `support` | `original_common`双端原来均有Q；`new_common_after_approved_order`批准顺序后新增双端Q；`expanded_common`两者合计 |
| `registered_physical_pairs`,`registered_method_event_aliases` | 去重物理对数与原方法别名数，不等于独立统计样本数 |
| `registered_unique_teams`,`common_Q_unique_teams` | 登记/共同Q范围A与C团队键并集数；不能相加跨条件去重数 |
| `images`,`buildings` | 实际该指标可用的去重图/楼数，优先解释此支持 |
| `image_equal_mean` | 按固定层级先同图汇总，再图片等权平均 |
| `building_equal_mean` | 先同图，再楼内图片平均，最后楼等权；与图片等权是不同估计对象 |
| `abs_dQ_image_equal_mean` | 先每对abs(dQ)，再同一层级平均；不是abs(image_equal_mean) |
| `positive_images`,`negative_images` | 图均值严格正/负，数值容差1e−10 |
| `up_gt_1p0_images`,`down_lt_minus_1p0_images`,`within_pm_1p0_images` | 图均>+1、<−1、绝对≤1Q；0.5/2为敏感性字段 |
| `cluster_bootstrap_low/high` | 建筑作为重采样单元的图片等权平均95%百分位区间；建筑仅一个时不伪造区间 |
| `building_equal_bootstrap_low/high` | 对应建筑等权均值的区间 |
| `leave_one_building_out_*` | 逐一删楼后的描述性稳定性范围，不是另一次独立研究 |
| `support_tier` | ≥10图且≥5楼标为supported；有图但不足标sparse；零图为none。只是阅读分级，不是显著性判断 |
| `component_denominator` | 共同Q且该分项双端可得；`COMPONENT_NATIVE_SUPPORT.csv`另给非Q状态下原生分项可得量 |
| `symmetric_Q_band`,`midpoint_Q` | M=(QA+QC)/2的层。abs(dQ)≤2min(M,100−M)，高端关联部分由数学边界决定 |

自动版原共同与辅助版原共同的每对Q均未改变；同支持行共用相同CI。主Q与`delta_B8L2`也是同一结果，CI逐行绑定，避免随机种子造成伪差异。不同n/m、背景、来源或图片池的结果不能直接解释为受控比例效应。

## 5. 合法记录劳动

| 字段 | 解释 |
| --- | --- |
| `time_whole_single_source` | A/C全员正值、记录齐全、两端使用同一种合法来源 |
| `dT_whole` | 满足全队规则后T_C−T_A，秒；缺失保留缺失 |
| `time_blocks_single_source` | X/Z全员正值、记录齐全、两块使用同一种来源 |
| `dT_blocks` | T_Z−T_X，秒；完全相同D严格相消，即使D记录不可得也不填0 |
| `A/C/D/X/Z_time_source_counts` | 成员记录来源种类及人数，JSON字符串 |
| `A/C/D/X/Z_known_positive_time_n` | 实际正值已知成员数，不是原团队人数 |
| `Q_labor_support=labor_available` | T可得范围，仅报T；不附另一个事件子集上的Q均值 |
| `Q_labor_support=same_pairs_Q_and_labor` | 先筛同一批双端Q且合法T的物理对，再联合汇总，才可解释Q/T关系 |
| `geometric_mean_labor_ratio` | 先每对log(T_C/T_A)或log(T_Z/T_X)，经同层级汇总后取exp；不是两组平均总时间比 |
| `labor_scope` | 主目标为源标注记录劳动；其它目标只保留源记录，不冒称该目标耗时 |

保存来源包括`inherited_v1_audited_source`与`user_processed_reported_not_raw_log_replayed`，保留来源身份，后者不声称已重放原始时序日志。只在相同来源且完整正值支持上作主劳动对比；既有数据的缺失或混合来源不被本轮填补。记录劳动不包含完整协调、返工、融合运行或人工排序成本，也不等同于共识到达时间。

## 6. 输出状态

`A_score_status`,`C_score_status`继承原正式输出状态，如`complete_conditional`、`no_connection`、`invalid_floor`、`below_four`；几何/连接原因另保存`geometry_status/reason`、`order_status`、`connection_available`等原字段。`Q_state_transition`仅描述双端Q是否存在，不替代更细状态。

`minimum_support`为固定n的原名义投票阈值；全部实际A/C对的该阈值相同。局部节点实际票数是否跨过阈值、对应重组或连接变化需查看`../mechanisms/`原生轨迹，不能由总分差、节点总数差或此字段单独推断。
