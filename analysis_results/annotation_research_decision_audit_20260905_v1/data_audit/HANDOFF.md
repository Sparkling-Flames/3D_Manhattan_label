# 数据审计交接

- 状态：正式输出已完成，`QA.json` 为 `pass`。
- 本次实际计算：源底座重新物化；全量 `stage×condition×image` 支持普查；高支持单元 k=15–20 嵌套回放；旧 42 图独立性与当前 20 人敏感性；人—人、人—GT、人—HoHoNet、人—BiLayout 及模型间图像平面诊断比较。
- 旧包复用：`recomputed_historical_uncertainty/` 与 `recomputed_manual_strata/` 在最终目录中是旧冻结包副本。本会话曾完整运行两者，但原子输出在后续解析失败时未保留；最终交付不把副本称为本次重新计算。
- 底座等价：核心 CSV 在布尔格式归一和绝对误差 `1e-12` 下语义一致；字节差异为布尔大小写与 8 个浮点尾数，旧/新 workbook 元数据差异单列。
- 聚类回归：修复 pointwise correspondence compatibility 传递后，全量曲线已重算；旧 42 图的 full support、structure status、cluster count、second support 和规范化 worker partition 为 42/42 一致。
- 来源口径：10,956 是来源快照出现次数，不是独立响应数；120 个 unresolved 项为 23 个 import 文件与 97 个 active-log 文件，不是丢失的人类标注。
- 验证：`pytest tests/test_audit_annotation_research_data_20260905.py -q -p no:cacheprovider`，6 passed。
- 清理：本任务创建的失败 `.data_audit_*` staging 已删除；仅保留正式 `data_audit/`。未删除或修改旧冻结包、原始真源、协议、schema、routing 或 SOP。
- 地图同步：按委派隔离范围未修改 `docs/README_INDEX.md` 与 `docs/PROJECT_MAP_CLEAN_20260308.md`；主任务统一决定是否登记本次新增工具与输出。
