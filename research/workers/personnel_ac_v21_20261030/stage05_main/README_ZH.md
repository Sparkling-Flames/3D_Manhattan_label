# 完整直接 AC 与整类等量主结果

本目录只汇总已经冻结登记并执行完成的团队，不重新拟合分类或改变评分。
正式完成回执为 `SUMMARY_RECEIPT.json`，覆盖全部258个执行池。

`POOL_CONDITION_EFFECTS.csv.gz`、`IMAGE_CONDITION_EFFECTS.csv.gz`、
`BUILDING_CONDITION_EFFECTS.csv.gz` 分别保留逐目标池、逐图、逐楼结果。
`CONDITION_METRIC_SUMMARY.csv.gz` 是正文精确源表；`KEY_OUTCOME_SUMMARY.csv.gz`
及 `HEADLINE_CONDITIONS.csv` 只是方便读取的子集，不增加事件。

固定人数 AC 和整类等量主表使用事前指定的 neutral_members_0 背景路径。
每个目标池内先平均可评成员组合，同图多个合法目标再等权合并，最后图等权；
楼等权结果另报。类别方向依各楼外折的冻结历史角色对齐，不是当前目标Q排序。
覆盖漏斗还包括其它登记背景，因此不能直接混用两种口径的均值。

每个指标单独保留有效事件、池、图和楼数。缺Q不填0。`image_mean` 为图平均响应的平均；
`image_balanced_mean_absolute` 先对每个事件取绝对值，再池内/图内平均，不是平均响应的绝对值。
`image_p10`/`image_p90` 是图平均值的描述性分位数，不是置信区间。
质量下降超过10分的事件比例使用严格 `< -10`，先池内统计再图等权。

`A_B8L2`/`C_B8L2` 及相应D10的端点分布各用各自可评端点，可能图片集合不同；
它们的低尾差不能冒称匹配的因果效应。`B8L2_CA`/`D10_CA` 只用双方可评分事件。
几何同时报告可用底面和双方完整输出子集；完整输出不意味着语义必然正确。
`legacy no_connection` 只表示未形成可用点序列，具体原因需读完整状态。

不含同类B队的直接AC不能计算跨类相对同类的额外区分。
旧严格ABC衔接、所有合法容量到执行的漏斗和状态迁移见 `../stage05_funnel_bridge/`；
成员/背景敏感性见 `../stage05_sensitivity/`。
同一物理对被多个方法或设计关联选中，不能当成独立重复。

科学源始终为 `../stage04_metrics/metric_shards/` 的258个完整分片。
临时池缓存、早期预览和 `.partial` 不是交付结果；已完成正式总表经独立复算及完整读取验证。
