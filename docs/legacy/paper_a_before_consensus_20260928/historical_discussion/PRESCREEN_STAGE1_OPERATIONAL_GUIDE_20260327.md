# Prescreen Stage 1 正式运行手册（2026-03-27）

## 1. 当前结论

当前仓库已经满足 **Stage 1 / prescreen 正式启动** 的条件，但这个结论只成立在 **prescreen 层**，不等于整篇论文的全部后续链路都已经完全实现。

当前 machine-readable 依据：

- `manual_binding_ready = true`
- `semi_binding_ready = true`
- `oos_binding_ready = true`
- `prescreen_ready = true`

对应文件：

- `analysis_results/phase1_progress_20260324/manual_binding_audit_v2.json`
- `analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json`
- `analysis_results/phase1_progress_20260324/oos_final_quota_binding_v2.json`
- `analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json`

## 2. 当前官方协议边界

按论文提纲第 1–4 节与附录，当前主流程应理解为：

`Pilot -> PreScreen -> Calibration -> Main(Test + Validation)`

当前 prescreen 只负责：

- 冻结 `PreScreen_manual = 30`
- 冻结 `PreScreen_semi ≈ 18`
- 冻结 OOS gate 小池
- 为后续 admission、`r_u^(0)`、`w_max`、blind-trust 证据 `T_u` 提供前置输入

当前 prescreen **不负责**：

- 完成 Calibration 的正式 `r_u / r_u^(s)` 估计
- 完成 `d_t / S_u / difficulty split / offline replay`
- 完成整篇论文主终点 `active_time` 的 estimand 闭环

后续 `Calibration / Main` 的正式轮次合同与分发规则，以：

- `docs/thesis_main/ROUND_BASED_EXECUTION_PROTOCOL_v1.md`
- `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`

为准。

若当前目标是立即启动 `P1`，则执行层以：

- `docs/thesis_main/P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md`

为直接操作清单。

## 3. 当前正式使用文件

### 3.1 Final gold / truth

- `export_label/人工精标/project-20-at-2026-03-27-14-57-e66c6481.json`
- `analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl`
- `analysis_results/final_gold_layer_20260325/final_gold_summary_v1.json`
- `analysis_results/truth_layer_extraction_20260324/trap_corner_records_v1.jsonl`
- `analysis_results/truth_layer_extraction_20260324/trap_scope_records_v1.csv`

说明：

- `scope + LS canonical corner geometry` 是当前 final gold 合同
- `.txt` 只作 `legacy_mp3d_reference`
- `poly` 只作 residue，不进入主合同
- `difficulty/model_issue` 不是 final-gold adjudication 字段

### 3.2 Stage 1 绑定与冻结

- `analysis_results/phase1_progress_20260324/manual_binding_audit_v2.json`
- `analysis_results/phase1_progress_20260324/prescreen_semi_final_selection_v10.json`
- `analysis_results/phase1_progress_20260324/oos_final_quota_binding_v2.json`
- `analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json`

### 3.3 Label Studio 正式导入文件

- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_import_v2.json`

辅助但不进主包：

- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_audit_only_import_v1.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_audit_holdout_v2.json`

导入摘要：

- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_import_summary_v4.json`

## 4. 各导入包当前构成

### 4.1 Manual

- 总数 `30`
- 由 `22` 个 expert-anchor 与 `8` 个 non-anchor 构成
- 场景类覆盖：遮挡明显、玻璃、拼接缝及拉伸、非常简单、纹理弱/纯色墙、遮罩

### 4.2 Semi

- 总数 `18`
- `control = 6`
- `main traps = 12`

当前主 trap family：

- `corner_drift = 3`
- `corner_duplicate = 3`
- `over_parsing = 3`
- `overextend_adjacent = 3`

当前 semi 边界：

- `625` 已替换 `474` 作为 natural `corner_drift`
- `overextend_adjacent` 当前采用 `natural-only`
- `underextend` 仍是 formal extension family，不进入默认主 12
- `fail` 当前不进活跃主包，只留 holdout
- `topology_failure` 当前没有 materialized asset，不构成启动 blocker

### 4.3 OOS

- gate 总数 `9`
- audit-only `1`

注意：

- `task560` 的目录 family 在 `边界不可判定`
- 但 final gold scope subtype 仍为 `oos_geometry`
- 当前执行层以 final gold scope 为准，因此 `560` 继续只作 `audit_only`

## 5. 工具链审计

### 5.1 已经完整到可支撑 Stage 1 prescreen 的部分

#### 导入与任务物化

- `tools/label_studio/prepare_labelstudio_docker.py`
- `tools/label_studio/build_stage1_prescreen_imports.py`
- `tools/label_studio/create_labelstudio_split.py`
- `tools/label_studio/create_labelstudio_split_by_outline.py`

#### 真值抽取与 final gold

- `tools/thesis_main/registry/extract_truth_layer.py`
- `tools/thesis_main/registry/materialize_final_gold_records.py`
- `tools/thesis_main/registry/build_final_gold_preflight.py`
- `tools/thesis_main/registry/rebind_stage1_to_final_gold.py`

#### Stage 1 冻结与重绑

- `tools/thesis_main/registry/freeze_prescreen_manual.py`
- `tools/thesis_main/registry/freeze_stage1_final_prep.py`
- `tools/thesis_main/registry/revise_semi_selection_v10.py`

#### 采集与运行时日志

- `tools/label_studio/official/ls_userscript_annotator.js`
- `tools/thesis_main/registry/meta_label_guard.py`
- `tools/label_studio/official/start_log_server.sh`
- `tools/thesis_main/analysis/lead_time_stats.py`
- `tools/thesis_main/analysis/split_active_logs.py`

#### 分析与可视化

- `tools/thesis_main/analysis/analyze_quality.py`
- `tools/thesis_main/analysis/aggregate_analysis.py`
- `tools/thesis_main/analysis/analyze_stage_aware.py`
- `tools/thesis_main/analysis/pooled_qa_plots.py`
- `tools/thesis_main/analysis/save_quality_figures.py`
- `tools/thesis_main/analysis/viz_quality_report.py`

当前判断：

> 对 **Stage 1 prescreen 正式启动** 而言，这条链已经够用，且关键输入输出已可机读审计。

### 5.2 仍未完整 materialize 的后续链路

以下内容在约束/计划中有正式规范，但当前仓库里没有对应正式实现脚本：

- `tools/thesis_main/registry/compute_dt_score.py`
- `tools/thesis_main/analysis/compute_spammer_score.py`
- `tools/thesis_main/analysis/difficulty_split.py`
- `tools/thesis_main/analysis/offline_replay.py`
- `tools/thesis_main/registry/meta_label_consensus.py`
- `tools/thesis_main/analysis/distribution_shift_detector.py`

当前判断：

> 对 **全文后续 Calibration / Main / offline strategy comparison** 而言，工具链还不是 fully materialized。

因此当前最稳的说法是：

- `prescreen`：可以正式开始
- `full thesis pipeline`：尚未完全实现

## 6. 导师讨论前建议先做的小型测试

目的不是重做 prescreen 设计，而是尽早暴露运行时问题。

### 6.1 导入正确性 smoke test

每个主导入文件各导入 2–3 条任务，核对：

- `manual` 无 prediction
- `semi` 全部有 prediction
- `oos` 不带 prediction，但 scope 字段可正常填写
- `task` 数量与导入 JSON 完全一致

建议记录：

- `import_file`
- `expected_count`
- `actual_imported_count`
- `prediction_present_count`
- `prediction_missing_task_ids`

### 6.2 前端交互与 userscript 测试

至少找 1 名内部试标者做短回合，记录：

- 3D 查看器能否正常加载
- `刷新 3D 视图` 是否正常
- `scope` 是否强制必填
- `difficulty/model_issue` 的 guard 是否按预期拦截
- `semi` 中 prediction 初始化是否与预期 proposal 一致

建议记录：

- `task_id`
- `dataset_group`
- `ui_error_flag`
- `meta_guard_block_count`
- `proposal_render_ok`

### 6.3 active_time 与日志采集测试

至少测试：

- 打开任务后持续操作 30–60 秒是否写入 log
- 页面切换/短暂失焦后计时是否符合预期
- `task_id / annotator_id / session_id / script_version` 是否完整

建议记录：

- `log_write_ok`
- `unknown_task_count`
- `missing_script_version_count`
- `active_time_source_coverage`

### 6.4 导出与 schema 稳定性测试

试标结束后立刻导出 1 次小样本，检查：

- `scope` 无空值
- `semi` 的 prediction/annotation 结构未漂移
- `extract_truth_layer.py` 能正常解析
- `build_final_gold_preflight.py` 不报 schema drift

建议记录：

- `export_snapshot`
- `n_tasks`
- `n_annotations`
- `scope_missing_count`
- `parse_error_count`

### 6.5 下游分析 smoke test

对小样本导出运行：

- `tools/thesis_main/analysis/analyze_quality.py`
- `tools/thesis_main/analysis/aggregate_analysis.py`（如有多导出）

确认：

- 不出现 join 失败
- 不出现 active_time schema 缺列
- OOS gate 行不被错误纳入主 layout 指标

## 7. 正式 prescreen 运行流程

### 步骤 0：锁定正式文件

只使用本手册第 3 节列出的正式文件，不混用 legacy / 讨论稿 / 中间版本。

### 步骤 1：先做小型 smoke test

建议先用极小子集跑 1 轮，确认：

- 导入正常
- userscript 正常
- 导出 schema 稳定
- active_time 可写
- analyze_quality 可跑通

### 步骤 2：正式导入

按顺序导入：

1. `manual`
2. `semi`
3. `oos`

如需保留非主包材料，再单独导入：

- `oos_audit_only`
- `semi_audit_holdout`

### 步骤 3：标注执行

执行时坚持：

- `scope` 必填
- `manual` 不看 prediction
- `semi` 使用当前给定 proposal，但允许纠正
- `OOS` 以 scope subtype 为主，不强求 geometry 主评分链

### 步骤 4：导出

按项目分别导出，保留原始快照到 `export_label/`。

### 步骤 5：分析

先跑：

- `tools/thesis_main/analysis/analyze_quality.py`

如需要跨项目对比，再跑：

- `tools/thesis_main/analysis/aggregate_analysis.py`
- `tools/thesis_main/analysis/pooled_qa_plots.py`
- `tools/thesis_main/analysis/viz_quality_report.py`

### 步骤 6：审计与归档

保留：

- 导入 JSON
- 导出 JSON
- active logs
- 分析 CSV/JSON
- 关键 freeze/binding 审计文件

## 8. 当前最重要的 reviewer-style 结论

### 可以正式说的

- Stage 1 / prescreen 已经具备正式启动条件
- final gold、binding、导入文件、truth-layer 抽取都已落盘
- 当前主链支持导入、标注、日志采集、导出、分析、基础可视化

### 不应说过头的

- 不应说全文后续 Calibration/Main 工具链已经全部实现
- 不应说 `active_time` 主终点问题已完全闭环
- 不应说 `topology_failure` 已有现成 audit asset

## 9. 当前建议保留的最小执行清单

### 导入

- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_manual_import_v2.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_semi_import_v5.json`
- `import_json/stage1_prescreen_final_20260325/stage1_prescreen_oos_import_v2.json`

### 绑定与真值

- `analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl`
- `analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json`

### 运行工具

- `tools/label_studio/official/ls_userscript_annotator.js`
- `tools/label_studio/official/start_log_server.sh`
- `tools/thesis_main/analysis/analyze_quality.py`
- `tools/thesis_main/analysis/aggregate_analysis.py`

### 辅助参考

- `docs/thesis_main/prescreen_freeze_note_v1.md`
- `docs/thesis_main/prescreen_oos_scoring_note_v1.md`
- `docs/thesis_main/final_gold_rebinding_contract_v1.md`
