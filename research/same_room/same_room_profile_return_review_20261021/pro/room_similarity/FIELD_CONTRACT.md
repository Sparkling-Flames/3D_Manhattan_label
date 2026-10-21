# 字段和研究台连接合同

## 版本与身份

- Git 输入：`561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`。
- 房间关系：`same_room_user_working_classification_20261016_v2`。
- 本分支为“本轮新增／固定输入重建”。没有原件恢复宣称。
- `object_id`、`worker_id`、`image_id`、`image_code`、`reference_id`、`reference_version` 沿用原证据包；`chosen_target_id` 沿用绑定证据。
- `pair_id=R{index:04d}` 只是在该固定关系表中的本轮方便键；稳定连接应同时使用 `image_a,image_b` 和关系版本，不能假定未来表索引永不变化。
- `declaration_id` 是用户原 `Gxxx` 或原候选 ID；`declaration_source` 区分 original 与 candidate_subset。它们可重叠。
- 既有多历史 `group_id=MVxxxx` 直接复用。新增 `split_id=MVxxxx_meannew_{index}` 对应本轮明确加入单源后的枚举，**不是**旧 split_id；用 `group_id+history+target_image` 连接两轮。

## 资格

正式 Q：`pool_analysis_eligible && quality_usable && !is_oos && chosen_target_id==current_target_id && quality_use in {ordinary_primary,doorway_quality}`。原诊断分不授予资格。主比较额外普通 Manual、采用物理同房、范围可比、无实质冲突；条件与范围变化单列。模型训练再要求既有 admission 通过或 origin=new；评价资格不因训练 gate 改变。

当前正式 Q 下 `image_id×condition×worker_id` 唯一，且 `image_id×condition` 的参考唯一；本轮因此没有把多个参考面板当重复人员计数。缺失的均值、共同池或历史保持空值，不置零。源耗时仅在索引中保留原义，不进入本分支 Q 模型。

## 逐对与逐组

|字段|定义|
|---|---|
|`actual_mean_a/b`|该图实际正式人员池的 Q 平均|
|`common_mean_a/b`|只取双方相同人员的 Q 平均|
|`*_signed_gap`|B−A；绝对差字段取绝对值|
|`composition_signed_shift`|实际池差−共同池差；算术构成变化，不是随机换人的因果效应|
|`common_workers` / `common_object_ids_a/b`|同一顺序的人员和两端对象引用|
|`common_wasserstein`|两端相同人员 Q 分布的 1D Wasserstein 距离；忽略身份配对，因此可小于逐人变化|
|`common_person_abs_gap`|同一人的两端 Q 绝对差再平均|
|`whole_group_common_n`|整组所有有正式 Q 视角上的交集人数；不同于逐对交集|
|`delta_vs_other_views`|该图实际池均值−同组其它视角实际池均值，仅描述|
|`positive_movers/negative_movers`|共同人员 Q 变化分别 >5 / <−5；方向依 image_a/b 排序，无好坏筛选|
|`low50`|有正式 Q 的原答中 Q<50 比例；阈值性描述，不等于人工筛除率|

## 匹配背景

`anchor=A,same_room=B,unknown_target=X`。A–B 是采用的普通范围可比同房对；A–X 不在冻结关系注册表的任何条目中。X 为同建筑普通 Manual、至少 3 份正式 Q 的图。`strict_match` 要求 B/X 的现用难度、`N_turn`、`H` 全部相同。没有对 Q 匹配或按效应选 X。

`triple_workers` 是 A/B/X 的真实共同人员，三端都用这些人计算。主三共同池结果 `n_triple_common>=4`。每个方向先平均所有候选，再在建筑内平均方向，建筑等权。`matched_control_support_bridge.csv` 在严格匹配可支持的固定方向上重算宽松对照；其实际池前三行正例值完全一致。

## 均值预测

`direct_mean_*` 是全部123对／64图的单源用途，方向键为 `metric,pair_id,source_image,target_image`。单源预测无拟合，楼外历史不含目标建筑。汇总先在目标内平均来源，之后图片／建筑等权；这与逐对描述的图对／建筑等权不同。

精确行键：`metric,panel,group_id,split_id,target_image`。`history` 是以 `|` 分隔的源图集合；`m` 是选中的历史图片数，`N` 是冻结组图数。`actual_pool` 按各图实际人员；`common_workers` 固定全组共同人员（至少 3 人）。

- `source_mean`：历史图 Q 均值的等权平均。
- `outside_roster_mean`：外楼、训练准入合格的人员绝对 Q 历史在目标人员名单上的平均。
- `target_peer_history/source_peer_history`：外楼逐图留一同行残差的人员均值，再按对应图名单平均。
- `peer_adjusted_source = source_mean + target_peer_history − source_peer_history`。
- `outside_peer_roster_mean = external_image_mean + target_peer_history`。
- `calibrated_*`：没有调参的线性截距／斜率；外层排建筑，训练行历史再排自身建筑。参数和拟合支持保存在 `mean_calibration_folds.csv`。
- `known_difficulty_adjusted_source`：源均值加楼外难度类别均值的目标−源差；需要已知目标难度，作为条件基线，非纯无目标信息预测。

人员历史缺失时只平均有历史人员，`target_history_coverage`、`minimum_source_history_coverage` 明示；本轮最低 0.9706，没有替换目标实际 Q。名单校正方法假定可知目标正式人员池名单，简单源均值不需要此信息。

宽表 `mean_prediction_values.csv.gz` 的每种方法名为一列；`actual` 是评价真值，`all_methods_supported` 标记共支持。误差=方法列−actual，绝对误差取绝对值。逐目标表 `expected_bad10/15` 是历史子集上的“预测均值误差超过 10/15 分”比例，**不是**原答低 Q 比例、融合失败率或低尾质量。`history_records` 计已使用源图正式原答份数，不直接转换为劳动秒数、交付时间或金钱。

汇总顺序：历史子集→目标图／预算→重叠组→目标图→建筑。逐组所有 m 保留，minimum_majority/maximum_history 只是端点汇总。单源额外列示，不冒称满足严格多数。数千来源组合不是独立房间。
