# v2.1 同房端点：保存几何重评分与缺口

仅对 `pools/DEPENDENCIES.json` 标记 reuse_geometry_rescore 的池，从历史保存的融合几何重新评分；不改变组队、同房关系、分类或融合。B8L2、D10、WQ、A10、旧working分项及参考几何诊断采用冻结实现。

- 大块同房：15176个受影响团队均从定位索引的35个实际分片读取，原成员和对象身份核对通过。
- 当前类别同房：22360个受影响团队，定位索引无同键；另从旧人口、精度和追加端点中，按完整team_key、成员、object_id、原参考和状态恢复42队。22318队无可核对几何，其中22166原有完整分数、150原连接失败、2原少于四节点。完整清单见 `MISSING_GEOMETRY.jsonl.gz`，不以旧分数替代新分数。
- 15218个可读取几何的团队已重评分：14679完整评分、7少于四节点、532原连接失败；每队保留原状态及精确 member_set_key。结果在 `shards/`，几何和标量来源、旧参考和旧分数在 `INPUT_TEAMS.jsonl.gz`。
- 17456条当前类别面板链接、5064条大块ABC事件链接逐行核对两视角相同成员；分别见 `CURRENT_CLASS_PANEL_LINKS.csv.gz` 与 `LARGE_BLOCK_EVENT_LINKS.csv.gz`。关系仅来自冻结直接图对，不扩张传递关系。
- 对有候选点的14686队，重新计算参考节点/边召回、参考节点缺口、角点召回和墙线覆盖；532队无候选点标为 not_applicable。旧参考下抽查4个池，B8L2误差最大约 1.5e-14，参考召回/覆盖与原记录及原生接口一致。

覆盖及状态详见 `COVERAGE.json` 和 `CHECKS.json`。所有缺几何队保留在清单中，不能据此称已全部接入；当前类别仍须在几何实际恢复后再计算。未重建事件对比或人员分类。

Downloads 顶层定向检查31个 HOHONET／personnel／同房相关 ZIP 的中央目录，未发现 `SRCC_20261023` 或 `same_room_current_classes_v2_20261023` 的原生端点几何或池文件；包括 20261026 S1/S2 数据包、20261022 换类包、20261027 room_type 包和 HoHoNet.zip。登记的四个 `HOHONET_01_REPORT_CODE_DESIGN.zip` 至 `HOHONET_04_BUDGET_RESULTS.zip` 不在 Downloads 顶层。此检查不排除其他位置或不同命名的归档。
