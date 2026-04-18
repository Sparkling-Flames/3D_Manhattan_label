# P1 预筛查启动检查清单 v1

> 最后更新：2026-03-28

## 0. 目的

这份检查清单是 `Round P1` 的即时执行配套文件，适用于：

- `docs/ROUND_BASED_EXECUTION_PROTOCOL_v1.md`
- `docs/ROUND_BASED_ASSIGNMENT_SOP_v1.md`
- `docs/PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md`

它的作用范围很窄：

- 启动 `Stage 1 / PreScreen`
- 将运行限制在冻结后的 `P1` 合同内
- 在正式收集之前，强制执行最小化的 smoke test、日志、导出和产物规范

它不会重新定义池子、分配方式，或后续 Calibration/Main 合同。

## 1. P1 范围

`P1` 是正式的 PreScreen 准入轮次。

它只允许更新：

- worker admission
- `r_u^(0)`
- `w_max`
- blind-trust pre-evidence
- prescreen quality 和 scope-gate 审计输出

它**不能**：

- 修改 `PreScreen_manual / PreScreen_semi / OOS gate`
- 生成正式的 `r_u / r_u^(s)`
- 定义 `tau_d`
- 写入任何正式的 routing profile

## 2. 必需输入

在启动前，请确认以下文件就是当前正在使用的准确输入：

- `analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json`
- `analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl`
- `analysis_results/final_gold_layer_20260325/final_gold_summary_v1.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_import_summary_v4.json`

## 3. 启动前门槛

只有当下面所有检查都通过时，才允许正式启动。

### 3.1 合同检查

- `manual_binding_ready = true`
- `semi_binding_ready = true`
- `oos_binding_ready = true`
- `prescreen_ready = true`

### 3.2 导入检查

- `manual` 导入不包含 prediction payload
- `semi` 导入在预期位置包含 prediction payload
- `oos` gate 任务不会泄漏到几何评分逻辑中
- 导入数量与冻结的 JSON 文件一致

### 3.3 界面 / 运行时检查

- 3D viewer 能正常加载
- `semi` 中 proposal 渲染正常
- 提交时必须填写 `scope`
- meta-label 保护逻辑会拦截非法组合
- annotator userscript 会写入包含 `task_id / annotator_id / session_id / script_version` 的 active logs

### 3.4 导出 / 解析检查

- 小型导出样本不包含缺失的 `scope`
- `tools/extract_truth_layer.py` 能正常解析，不会发生 join failure
- `tools/analyze_quality.py` 能在 smoke sample 上运行
- `OOS` 记录与主几何指标保持分离

## 4. P1 执行顺序

### 第 1 步：小型 smoke import

分别从以下文件中导入 `2-3` 个任务：

- `stage1_prescreen_manual_import_v2.json`
- `stage1_prescreen_semi_import_v5.json`
- `stage1_prescreen_oos_import_v2.json`

记录：

- `import_file`
- `expected_count`
- `actual_imported_count`
- `prediction_present_count`
- `prediction_missing_task_ids`

### 第 2 步：短时内部试跑

至少执行一次简短的内部标注流程，并检查：

- `scope` 提交保护
- `difficulty / model_issue` 互斥保护
- proposal 初始化
- 3D 刷新稳定性
- active-log 写入成功

记录：

- `task_id`
- `dataset_group`
- `ui_error_flag`
- `meta_guard_block_count`
- `proposal_render_ok`
- `log_write_ok`

建议同时跑一次：
- `python tools/audit_active_log_quality.py active_logs --summary-json analysis_results/.../p1_active_log_smoke_audit_summary.json --per-file-csv analysis_results/.../p1_active_log_smoke_audit.csv`

### 第 3 步：smoke 导出

立即导出 smoke 样本，并验证：

- `scope_missing_count = 0`
- `semi` 中没有 schema drift
- truth-layer extraction 没有解析错误
- quality-analysis 没有 join failure

记录：

- `export_snapshot`
- `n_tasks`
- `n_annotations`
- `scope_missing_count`
- `parse_error_count`

### 第 4 步：正式导入

只有在第 `1-3` 步全部通过后，才可以：

1. 导入 `PreScreen_manual`
2. 导入 `PreScreen_semi`
3. 导入 `OOS gate`

不要把 holdout 或仅用于审计的层导入到主 `P1` 运行中。

### 第 5 步：正式收集

在收集过程中，持续监控：

- active-log 覆盖率
- 缺失的 `script_version`
- 未知任务匹配
- 提交时保护失败
- 按 dataset group 区分的 UI 失败

如果这些信号显示出系统性故障，请暂停 `P1`，先修复运行时问题，再继续收集。

## 5. P1 必需产物

在正式 `P1` 运行结束时，必须存在以下输出：

- `prescreen_worker_admission.csv`
- `prescreen_r0_snapshot.csv`
- `w_max_locked.json`
- `prescreen_blind_trust_audit.csv`
- `prescreen_scope_gate_audit.csv`
- `prescreen_round_report.md`

建议同时保留的配套产物：

- `p1_import_smoke_audit.csv`
- `p1_active_log_smoke_audit.csv`
- `p1_active_log_smoke_audit_summary.json`
- `p1_export_parse_smoke_audit.csv`

## 6. 轮次结束判定

只有在以下条件都满足时，`P1` 才可以标记为完成：

- admission list 已冻结
- `w_max` 已冻结
- Stage 1 admission boundary 已冻结
- 不再存在未解决的导入 / 日志 / 导出阻塞项

`P1` 完成**不代表**：

- 正式 `r_u`
- 正式 `r_u^(s)`
- 正式 `Score`
- 正式 `N_{u,s,min}`
- 正式 `tau_d`
- 冻结后的 routing contract

这些属于 `C1 / C2`，不属于 `P1`。
