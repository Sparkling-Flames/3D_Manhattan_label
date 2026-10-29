# 状态名称和机制解释的定向补充

原版`METRIC_DICTIONARY.json`及所有已算指标保持原样。本补充只纠正解释层：**本轮正文将legacy `no_connection`称为“未形成可用点序列”**。

冻结评分器在n≥3、选中节点不少于4个时，以`candidate.points is None`标记`no_connection`。因此，`A_connection_failure`和`C_connection_failure`这两个现存布尔列，是该legacy状态的标志，不单独证明缺少连接环。组装代码同时要求存在完整来源投影环、且所有入选节点的位置都已确定；任一条件不满足，都可能没有可用点序列。这里说明的是代码分支，不声称本轮实际同时出现了全部分支。

完整状态案例中再分别查看来源投影环、所有入选及未入选组、位置中心、`node_consensus.status`、`ring_diagnostics.reason`和`candidate.reason`。来源完整环必须覆盖全部入选节点且各出现一次，单纯集合包含不够。案例导出表另存`selected_unresolved_location_groups_n`、`native_ring_reason`、`native_candidate_reason`和`no_connected_points_mechanism`，通过真实证据解释个案。

`fusion_structural_failure`与`fusion_failure_observed`仍保留冻结值，是依照状态组合的输出失败指标；包含的`no_connection`不因此变成唯一机制。缺Q不填0，测量异常、仅底面参考和其它缺分仍分别保留。没有为本补充全面重跑定位或连接诊断，也没有改变融合、参考、排除或分类。

几何单位一并保持明确：`geometry_bev_distance_AC=1−IoU`无量纲；质心距离才以相机高度h计。完整可核验定义、原字典SHA256与源码SHA256见同目录`METRIC_DICTIONARY_SEMANTIC_ADDENDUM.json`。
