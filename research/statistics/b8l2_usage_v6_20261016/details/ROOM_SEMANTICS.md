# 房间身份、登记关系组与视角描述口径

**历史严格层说明。** 当前采用已改为[已有人工分类的版本化工作分组](../details_room_adopted_v3/ROOM_SEMANTICS.md)。原260组全部看过，缺少全库唯一物理房间ID不能解释为缺少人工分类，也不再阻挡每组和人员×组统计。本页旧关系层和数值保留追溯，不再作为当前准入要求。

本页针对固定v6的新用途派生统计；质量字段消费父级新用途掩码，不改目标、CURRENT、同房审核或正式资格。生成函数为`tools/thesis_main/analysis/b8l2_room_descriptions_20261016.py::build_room_descriptions(records,bundle)`；输入为原3152条共同记录及父级`CROSS_MODULE_INPUTS.json`指向的旧共享`FROZEN_INPUTS.json`中的bundle。质量、来源时间和目标时间沿用共同记录已经执行的门与缺失掩码。

## 为什么不直接按room_id称“物理房间”

现有`room_id`的G编号至少可追溯到`finalize_review_20260928.py`将`room_map[image_id].candidate_id`写入记录。它是登记候选关系组标签，不是具有独立身份合同的建筑实体房间编号。不能把非空G数称为物理房间数，也不能用它覆盖一图多组、候选子组、明确讨论或待核状态。

冻结`room_registry`包含260个原组、259个候选子组、648张关系登记图片。当前259张库存图片中，236张有候选组成员关系，23张无此证据；163个候选组至少有一张当前库存图，其中30个达到现有`confirmed_comparable`规则。40张当前图属于多个候选组。这里的数量用于说明资料覆盖，不是新增房间确认或房间抽样数。

原始`user_room`、房间粗类型、主视觉空间等人审字段继续作为原始证据，不由本模块升级为稳定物理房间键。相同房间类型不意味着同一个房间，建筑相同也不意味着同房。没有登记关系不等于确认异房。

## 本模块实际汇总什么

- **registered_relation_group**：沿用既有候选子组的明确成员，不取传递闭包，不把原大组被排除的成员加回。保留candidate ID、来源原组代码、审核状态、物理同房支持与关系层。G编号保留追溯用途，但`physical_room_identity_certified=false`明确表示本轮没有建立全库物理房间身份表。
- **direct_registered_pair**：复用现有`relation_index`，把同一已登记候选子组内共同列出的两图作为关系证据，保留全部来源candidate ID与原规则层。它不是将A—B、B—C跨组传递出A—C，也不声称本轮重新对每一对图片作视觉确认。底层候选组成员本身的确认与不确定性随表保留。
- **原组证据**：260个原组的原始判断、解释及`source_pair_ids`单列，不能再与候选子组统计相加。它们解释“为什么有这个组”，不替代当前子组的采用边界。

关系层继续按旧代码定义：`confirmed_comparable`要求physical_same_supported、comparable_for_prediction、无oos_pending且explicit_confirmed；仅物理同房支持记为`supported_other`；其余为`candidate_unconfirmed`。这三个层分别展示，查看过不等于已确认，可比也不等于当前每项指标都有足够数据。

## 统计权重与重复人员

所有总体、人员×组、图像贡献均按`condition`和`analysis_layer`拆分，包含库存暂停层及其真实缺失；不把manual/semi/oos合并作一个房间成绩。每个组内对象ID只出现一次；重叠组会重复引用同一作答，组间结果不可相加得到全库样本数。

`B8L2_mean`、时间的`*_mean`是有效作答等权均值；`*_image_equal_mean`先在每图内求有效作答均值，再把有有效值的视角等权平均。二者的权重不同，不能互换。每个指标同时提供n、中位数、样本SD、四分位数及有效图片/人员覆盖；没有值保持空，单值SD为空。

同一个人贡献多张视角时，可以有多条作答，但`n_source_workers`等人员数按稳定worker_id去重。人员×组表仍报告该人有多少来源图片；不能将该人的多视角当作多个独立人员，也不从这些描述表作独立样本显著性推断。

质量、来源时间、目标时间各自的边际n可能不同。`quality_source_time_*`与`quality_target_time_*`另外只用质量和对应时间同时非缺失的共同作答，提供共同n、图片、人员及两侧分布。目标时间不由事后质量评分补造。

每组还报告全部声明视角是否都有当前记录，以及三指标各自“在全部声明视角都有有效值”的共同人员数。某组总体均值不表示每个人都画过每一张图；人员×图对只有一端记录时，`all_declared_views_have_records=false`，不能当成同人两视角配对比较。

## 输出表

- [room_group_registry.csv](room_group_registry.csv)：全部候选子组、来源指针、当前覆盖和重叠成员。
- [room_raw_group_evidence.csv](room_raw_group_evidence.csv)：原组原话、解释及原始source_pair_ids，仅供追溯。
- [room_group_memberships.csv](room_group_memberships.csv)：组×图片成员关系及该图片的候选组重叠数量。
- [room_group_summary.csv](room_group_summary.csv)、[room_worker_groups.csv](room_worker_groups.csv)：分条件／采用层的总体及人员×组描述。
- [room_group_views.csv](room_group_views.csv)：每组每图的视角贡献，用于检查人员组成和样本权重。
- [room_direct_pair_registry.csv](room_direct_pair_registry.csv)：全部既有候选共同成员图对及证据层，缺库存视角也保留其登记事实。
- [room_direct_pair_summary.csv](room_direct_pair_summary.csv)、[room_worker_direct_pairs.csv](room_worker_direct_pairs.csv)：两端均有当前库存时的图对／人员描述，指标缺失和各条件下单端覆盖仍如实报告。
- [room_unlinked_images.csv](room_unlinked_images.csv)：无登记候选成员证据的当前图片，保留库存及原room_id，不能当成独立房间或异房。

这些表补充房间/关系组层的查阅维度，不自行改变父级1787份质量用途的成员集合；OOS所有GT参照质量仅诊断，不进入这些质量描述均值，不替代现有逐图、逐建筑与直接同人图对比较。若未来确有独立、稳定、经审核的物理房间ID，再以新来源版本接入；本轮没有用连通分量、G编号或指标相似性制造这一身份层。
