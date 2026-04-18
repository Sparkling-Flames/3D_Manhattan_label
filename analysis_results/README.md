# analysis_results

这个目录只存放分析产物、freeze 输出、registry、图表和审计结果，不存放代码。

## 先看哪些目录

- `final_gold_layer_20260325/`
  - 当前 final gold 主层。
  - Stage 1 主合同入口看这里。

- `phase1_progress_20260324/`
  - 当前 Stage 1 / prescreen 的主 freeze 与 binding 审计目录。
  - `stage1_final_binding_audit_v6.json` 是当前 machine-readable go/no-go 核心文件。

- `truth_layer_extraction_20260324/`
  - current truth-layer / manual annotation extraction 输出。
  - 是 final-gold preflight 与 rebinding 的上游之一。

- `trap_collection_freeze_20260320/`
  - `trap集/` 的 staged freeze 输出。
  - 仍有方法学价值，但不是当前最核心的 go/no-go 审计目录。

- `mp3d_txt_smoke_test_20260328/`
  - 当前 smoke-test 输出目录。
  - 用于验证 `.txt` 导入/渲染链，不是论文主结果目录。

## 仍保留在根目录、但偏历史/支撑的目录

- `c_manifests_20260310/`, `c_manifests_20260311/`
  - C 线 manifest / trap-side bundle 历史输出。

- `phase1_progress_20260311/`
  - Phase 1 较早期的 progress / readiness 审计。

- `selection_freeze_20260317/`
  - 显式 selection freeze 历史输出。

- `stage_aware_analysis_freeze_v1_20260316/`
- `stage_aware_analysis_freeze_v2_20260317/`
- `stage_aware_analysis_freeze_v2_1_20260317/`
- `stage_aware_analysis_freeze_v2_1_selection_v1_20260317/`
- `stage_aware_analysis_freeze_v2_1_main_facing_v1_20260317/`
  - stage-aware freeze / rerun 历史链路，主要用于回溯和 blocker 审计。

- `registry_20260308/`, `registry_20260308_march7_check/`, `rerun_20260308/`
  - 更早期的 registry / rerun 输出，主要保留为可追溯历史。

- `export_inventory_20260309/`
  - export 真源审计输出。

- `pooled_qa/`
  - pooled QA 图包与最小审计表。

## 已归档

- `legacy/20260329_pre_p1_cleanup/`
  - 2026-03-29 做过一次根目录清理。
  - 这里存放早期数值命名目录、文献提取目录、`devcheck`、旧图表目录、旧 March 7 formal check、以及散落在根目录的临时文件/日志/预览文件。

## 使用约定

- 新的正式结果不要直接散落在根目录，优先创建带日期或 round 名称的子目录。
- 如果某个目录已经不再承担当前主链入口职责，优先移动到 `legacy/`，不要继续堆在根目录。
- 如果不确定一个结果目录是不是当前主链，先看：
  1. `phase1_progress_20260324/`
  2. `final_gold_layer_20260325/`
  3. `truth_layer_extraction_20260324/`
  4. `docs/PROJECT_MAP_CLEAN_20260308.md`
