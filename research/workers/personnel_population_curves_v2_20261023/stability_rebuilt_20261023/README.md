# 人数路径稳定性与同来源时间：本地接入

本目录保存 R03 完整分析输入、2,000 次路径/建筑重抽的作者结果与实现，以及四策略共同时间支持。它重用既有人数路径，没有新增融合端点或重新分类。

- [作者报告](README_ZH.md)：自然人数、前段策略和两种重抽范围。
- [四策略共同时间支持](FOUR_POLICY_TIME_COMMON_ZH.md)：同一批图、同一 base/k、相同记录语义下比较质量与劳动时间。
- [时间口径修正](TIME_SEMANTICS_CORRECTION_ZH.md)：原先全员已知时间并不自动意味着同来源语义。
- [独立核验](../../../statistics/same_room_rebuilt_audit_20261023/README.md)：本地重新计算与采用范围。
- [来源逐项索引](LOCAL_SOURCE_FILES.csv)：R03 原包到仓库的对应。

`inputs/PREFIX_VALUES_COMPACT.csv.gz` 是全部 404,082 前缀的必要列投影，配合 12,398 精确顺序可运行原报告内的复算命令。原自然/策略端点仍在上一级，必要时按其 README 恢复；本目录不再复制原大表。

收到的 `figures/PATH_VS_BUILDING_STABILITY.pdf` 为零字节。现按原 `code/make_report.py` 绘图片段和已交付汇总重建，已读为一页并渲染查看；原空件保存在 `source_original/R03/figures/`，PNG、数值与作者回执保持原样。完整归档/修补记录见[同房专题](../../../same_room/same_room_large_block_rebuilt_20261023/LOCAL_REPAIRS.md)。
