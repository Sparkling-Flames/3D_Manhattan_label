# 审查结果字段

本目录只保存固定反例与控制的认证审查，不是新增真人实验或正式融合合同。

- `reproduction.json.cases`：既有两人、新增三人分别保存原／补丁状态、实际生成映射、独立minimax映射、独立成员间角距和固定映射的候选残差。角度单位为度，连续ERP为1024×512。
- `independent_joint36`：仅新三人三点例的完整36状态枚举，`feasible_count`与`optimal_count`是状态数，不是人员或概率。
- `ordinary_control`：既有一图三人输入的补丁状态及独立固定映射残差，不重新评价GT。
- `remaining_mixed_population`、`remaining_top_domain`：受控接口边界，不是现实数据污染或视觉错误的证据。
- `tests`：本地6项隔离回归及独立最大角距；不包括dot提供的25项原测试日志。
- `source_copies.json`：Downloads只读来源、隔离副本与逐字节比较；旧两人JSON值相等但格式字节不同。没有改写外部源或既有归档。

所有完整数值保存在JSON中；报告显示小数仅为阅读。复现只向本目录写结果，不修改算法、资格、输入或阈值。
