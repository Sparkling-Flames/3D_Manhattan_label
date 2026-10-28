# 当前有效文件清单：同用途的不同房间研究

采用main `b2b0898b90bd631df37f1f2e75e8380800a43cf8`，2026-10-27。以下01—04组成完整正式交付。统一解压到仓库根，文件落在 `research/statistics/room_type_similarity_20261027/`。原有人员/同房大块/人数曲线包不混入本轮编号。

| 文件 | 用途 | 状态与组合 |
|---|---|---|
| REPORT_ZH.html | 图像内嵌的独立综合报告 | 推荐先读；数值与MD一致 |
| REPORT_ZH.md | 仓库内中文主报告 | 本轮唯一正式报告；由下述01包含 |
| CLAIM_INDEX_ZH.csv | 问题→结论→支持→精确表→代码→采用 | 10项中文主张 |
| NEW_OLD_CONCLUSIONS.csv | 新旧采用关系 | 旧描述、同房、分类、曲线与本轮新增分开 |
| HOHONET_room_type_20261027_01_report_code_inputs.zip | 报告、关键小表、全代码、最小标量输入、标签/资格、图、补丁 | 可独立读报告，并从输入重跑；含中文重绘字体及许可 |
| HOHONET_room_type_20261027_02_cases.zip | 三张实际原图、104份完整原答/参考几何、选例和历史连接 | 当前更新版；已修复C02辅助图导出并更新b2/256采用文字；保留同一文件身份 |
| HOHONET_room_type_20261027_03_full_results_geometry.zip | 全OOF/参数、逐图逐人条件结果、原答几何 | 与01通过object_id/image_key关联；不含无效并发导出目录 |
| HOHONET_room_type_20261027_04_exact_matching_events.zip | 12289跨楼图对＋44694精确三图事件 | 完整共同人员与匹配键；不是新增融合队 |
| HOHONET_room_type_20261027_STAGE01_inputs_descriptive.zip | 先行输入与描述检查点 | 保留起始b9历史身份；最终由01接续，不应作为另一份最终报告 |

## 更新了哪些文档

新目录中 REPORT_ZH、README、REPRODUCE、FIELD_CONTRACT、SOURCE_DEPENDENCIES、主张索引和新旧对照均为本轮正式版本。`integration/ROOM_TYPE_CONTINUATION.patch` 精确接续旧scoping入口与全研究CONCLUSIONS，基于b2原文，可审阅后应用；没有代用户推送。

所有包内含逐文件散列清单；交付完成后另提供 `DOWNLOADS_AND_VERIFICATION.md`，列出实际可取回链接、字节、SHA及从下载件内部读取到末尾的结果。包内本清单负责说明组合和文档身份，外置清单负责最终下载入口。
