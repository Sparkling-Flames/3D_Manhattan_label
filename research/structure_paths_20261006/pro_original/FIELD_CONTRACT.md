# 字段与范围合同

所有角度为度；画布1024×512 continuous，几何长度h为共同相机离地高度单位，不是米。这里是独立研究字段说明，不修改正式合同。

## 身份与路径

`id/worker/pair_index`标识作答、人员及处理后点对索引；`source_pair_index`是源角对索引，不得混用。输入及`source_path_catalogue`完整保留源点与源环。

`path_id`指按原环顺序连续的一或两条边。可反向比较，但方向字段必须保留；不是重新给源环排序。`internal_observations`是原内部点，不自动获得端点身份的票数。

`anchor_distance_deg`是给定候选外端点的原距离。锚点由有限搜索提出，并非已人工认证。`path_length_outside_declared_domain`表示本次120°弧长域不包含该路径；`anchor_outside_gate`不是人员错误。

`accept/reject`只针对指定顺序、端点、侧别、数值误差及未校准阈值。上下分别取Fréchet距离，不表示已有共同的内部上下绑定参数。`numerically_unresolved`不能自动填通过或失败。`not_witnessed`不是语义cannot-link。

## 原MV与结构对照

`support`是相应几何身份组的独立worker数，`selected`沿用ceil(N/2)。`N`是完整选中人员池，不随方法成功程度改变。相同坐标来自不同人，分别计票。

`center`沿用原medoid锚定的周期x中位数、上下y中位数；它是条件于对应的坐标估计，不是“多数人标在这个坐标”。

`lost_comemberships/new_comemberships`是新旧分区的关系差，不自动是损害/纠错。`affected_nodes`包括所有未审人员变化。人工辅助不作为自动成功率。

`minimum_four_pairs_enforced=false`。不足三对不生成面积，原达票点仍保留。三对也不自动成为合法房间。

`x_diagnostic`是新中心按x组成的探索性诊断环，不继承源环确认；分数只归该诊断对象。`all_complete_observed_cycles`仅保存源原序完整覆盖全部选择身份、无删点的候选。没有全员一致有效源身份环时主输出只是点/路径层，不选择人数最多的环。

## 路径候选

`role=single_observed_path_replacement_with_frozen_raw_anchor_centers_not_all_person_consensus`明确是有限条件候选。原base环境保留，局部由另一个原始连续路径替代，两端使用完整原身份组中位中心。它不是全24/15人完整共识，也不是新增独立标注。

`base_internal_vertices_removed_in_candidate_only`记录本候选省去的源内部点；原答与备选仍保留，不称真实细节误删。`donor_internal_vertices_retained`不是新增真实性认证。

`anchor_only_control_points`只移动相同两个锚点，保留base内部结构；相对它的面积和参考差分离结构替换与锚点估计影响。

`new_edges`中的精确原边供者按上下端点round9数值匹配，不是语义容差；无人精确提供不表示无人认可，但禁止继承原边票数。`whole_candidate_support=not_established`。

`post_center_path_comparison`在中心估计后重新与base/donor比较，必须重新满足各侧阈值；原两路径相容不转移成新路径相容。`outside_previous_local_gate`不等于场景质量错误；候选及原因均保留。

## 真值与参考

真实对应只使用此前已记录的开发人审，不拓展到其他人。真实细节真假和错误结构新增为`not_evaluable_no_local_semantic_truth`，不填0。合成真值在控制说明中给定，不能称自动识别。

GT只在冻结候选后的evaluation阶段读取。范围遗漏/外扩对既有参考、base、anchor-only三个对象分开命名。四图只有旧原参考，无当前新附件参考或新增修订版本。

精确环编码去重仅作为候选重复计数说明，不是一般几何/语义等价，也不对人员投票去重。
