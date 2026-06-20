# M15 Legacy Artifact Dependency Inventory v1

## 结论

本清单仅做只读迁移阻塞盘点。当前不得移动、改写路径、删除或重新计算以下目录及其哈希：

- `analysis_results/paper_a_manhattan/local_candidate_search`
- `analysis_results/paper_a_manhattan/adaptive_local_probe`
- `analysis_results/paper_a_manhattan/semantic_direct_search`
- `analysis_results/paper_a_manhattan/optimization_trace`
- `analysis_results/paper_a_manhattan/visual_verdict`
- `analysis_results/paper_a_manhattan/hard_case_audit_pack`

`local_candidate_search`、`adaptive_local_probe`、`semantic_direct_search` 与 `optimization_trace` 仍被 M15.28 legacy candidate source、上游兼容 runner 或 regression tests 直接引用。`visual_verdict` 保存旧 `local_3d_projection` 路径和 SHA-256，单独移动会破坏审计链。`hard_case_audit_pack` 仍是 3741/2369/2389 的有效 regression artifact。新 core runner 当前仍以 M15.28 作为 legacy candidate source，因此不能拆散这条兼容链。

## 已知代码与测试依赖

以下清单由 `rg` 对 `tools/`、`tests/` 与 `docs/` 的固定路径扫描得到。

### Tools

- `run_m1524_hard_case_audit_pack.py`：读取 `local_candidate_search`，默认写入 `hard_case_audit_pack`。
- `run_m1525_visual_verdict_pack.py`：读取 `local_candidate_search`，记录 `visual_verdict` 及旧 projection provenance。
- `run_m1526_adaptive_local_probe.py`：读取 `local_candidate_search` 与 `visual_verdict`，默认写入 `adaptive_local_probe`。
- `run_m1527_semantic_direct_search.py`：读取 `adaptive_local_probe`、`local_candidate_search` 与 `visual_verdict`，默认写入 `semantic_direct_search`。
- `run_m1527_optimization_trace_ledger.py`：固定引用 `local_candidate_search`、`adaptive_local_probe`、`semantic_direct_search` 与 `optimization_trace`。
- `run_m1528_semantic_action_library.py`：固定引用 `local_candidate_search` assertion、`semantic_direct_search` 与 `optimization_trace`。

### Tests

- `tests/test_local_3d_projection_review.py`：直接读取 `local_candidate_search`、`adaptive_local_probe` 与 `semantic_direct_search` 的 3741 artifacts。
- `tests/test_manhattan_m1520_local_candidate_search.py`：读取 `single_image_manual_test` 与 `local_candidate_search` regression inputs。
- `tests/test_run_manhattan_hypothesis_ranking_core.py`：读取 `local_candidate_search/task218_ann3741/expert_assertion.json`。
- M15.24–M15.28 runner tests 继续验证上述兼容工具及其默认 artifact contract。

### Docs 与历史报告

- `docs/README_INDEX.md` 与 `docs/PROJECT_MAP_CLEAN_20260308.md` 仍登记 M15.20–M15.28 compatibility tools。
- `analysis_results/paper_a_manhattan/visual_verdict/task218_ann3741/` 的 JSON/Markdown 记录旧 `local_3d_projection/task218_ann3741` 路径及哈希。
- `adaptive_local_probe` 与 `semantic_direct_search` 产物嵌入 visual-verdict provenance。

## 迁移条件

当前策略是 inventory only：no file move、no path rewrite、no deletion、no hash regeneration。

只有当 core 不再依赖上述固定路径时，才能把完整 M15.20–M15.28 compatibility chain 一次性迁移到：

`analysis_results/paper_a_manhattan/legacy/`

迁移必须整体更新代码、测试、文档、历史 provenance 与哈希验证；不得逐目录拆迁。
