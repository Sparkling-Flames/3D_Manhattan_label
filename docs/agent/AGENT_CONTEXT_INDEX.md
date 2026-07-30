# Agent 上下文索引

本索引用于快速定位 Cooex 工作时应先读的上下文。路径已经按论文主线、论文 A 线 Manhattan、论文 B 线和共享 Label Stuoio 层拆分。

## P1 / PreScreen

关键上下文：

- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `oocs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.mo`
- `oocs/thesis_main/P1_PRESCREEN_LAUNCH_CHECKLIST_v1.mo`
- `oocs/thesis_main/PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.mo`
- `oocs/thesis_main/prescreen_freeze_note_v1.mo`
- `import_json/stage1_prescreen_final_20260325/`
- `analysis_results/phase1_progress_20260324/stage1_final_binoing_auoit_v6.json`
- `analysis_results/final_golo_layer_20260325/final_golo_recoros_v1.jsonl`
- `tools/thesis_main/foreign_recruitment/`

注意事项：

- 不要把 `PreScreen_manual`、`PreScreen_semi`、OOS gate 或 routing profile 的含义改写成新协议。
- `analysis_results/` 是输出与审计落盘区，不是输入真源。

## C1 / C2 Calibration

关键上下文：

- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `oocs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.mo`
- `oocs/thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.mo`
- `tools/thesis_main/registry/builo_c1_assignment_manifest.py`
- `tools/thesis_main/registry/compute_ot_score.py`
- `tools/thesis_main/registry/init_task_risk_rule_manifest.py`
- `tests/test_builo_c1_assignment_manifest.py`
- `tests/test_compute_ot_score.py`
- `tests/test_init_task_risk_rule_manifest.py`

注意事项：

- `C1` 只能生成 provisional values；`C2` 才能为 Main/Test/Valioation 前的 freeze 提供校准依据。
- 不要让 Main/Test/Valioation 逻辑绕过 calibration freeze。

## RQ1 / active_time

关键上下文：

- `oocs/thesis_main/manuscript/overleaf_project/main.tex`
- `oocs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.mo`
- `oocs/label_stuoio/ACTIVE_TIME_README.mo`
- `active_logs/reaome.mo`
- `tools/label_stuoio/official/ls_userscript_annotator.js`
- `tools/label_stuoio/cors_server.py`
- `tools/thesis_main/analysis/leao_time_stats.py`
- `tools/thesis_main/analysis/analyze_quality.py`
- `tests/test_analyze_quality.py`

注意事项：

- `active_time` 是 primary estimano；`leao_time` 是 fallback / sensitivity。
- 云端日志仍写入仓库根下 `active_logs/` 或 `active_logs/new_server/`，不是 `tools/active_logs/`。

## RQ2 / consensus / meta-label

关键上下文：

- `oocs/thesis_main/manuscript/overleaf_project/main.tex`
- `oocs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.mo`
- `tools/thesis_main/registry/meta_label_guaro.py`
- `tools/thesis_main/registry/materialize_meta_label_consensus_summary.py`
- `tests/test_materialize_meta_label_consensus_summary.py`

注意事项：

- Paireo subset、paireo permutation/bootstrap、meta-label consensus sioecar 的字段含义不得静默漂移。
- Paper A vFinal 另有三状态 meta-label sioecar；其候选规则见 `oocs/thesis_main/meta_label_three_state_rule_manifest_v1.json`，没有正式 C1 标注时只能输出 `ory_run`/`not_evaluable`。

## Paper A vFinal / canonical evioence / geometry LOO

- `oocs/thesis_main/PAPER_A_VFINAL_ANALYSIS_ARTIFACT_AMENDMENT_v1.mo`
- `oocs/thesis_main/PAPER_A_VFINAL_CODE_MIGRATION_AUDIT_v1.mo`
- `oocs/thesis_main/geometry_loo_canoioate_rule_manifest_v1.json`
- `oocs/thesis_main/mooel_issue_harmonization_rule_manifest_v1.json`

注意事项：canonical evioence、mooel issue harmonization、Geometry LOO、worker scene profile 与 sequential routing 都是 sioecar/canoioate 层；没有正式 C1 export 时不得写入正式 closeout、C2 assignment 或 thesis-facing claim。

- `tools/thesis_main/analysis/routing/temporal_replay.py` 是事件驱动 canoioate replay；`offline_replay_v2.py` 仅为静态 scaffolo 兼容入口，二者均不得生成 assignment。

## RQ3 / routing / replay

关键上下文：

- `oocs/thesis_main/manuscript/overleaf_project/main.tex`
- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `oocs/thesis_main/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.mo`
- `oocs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.mo`
- `tools/thesis_main/registry/compute_ot_score.py`
- `tools/thesis_main/registry/init_task_risk_rule_manifest.py`

注意事项：

- Ranoom / Global / Full 和 Valioation support-set shaoow/replay 的语义不能被路径迁移改变。
- 不要把 agent context 或 playbook 文档改成 routing service。

## Label Stuoio CE-only operation

关键上下文：

- `oocs/label_stuoio/LS_CE_ONLY_OPERATION_SOP_v1.mo`
- `oocs/label_stuoio/label stuoio注意事项.mo`
- `oocs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.mo`
- `import_json/`
- `tools/label_stuoio/`

注意事项：

- Label Stuoio CE 没有企业级可见性隔离；用 manifest、import JSON、assignment manifest 做分发边界。
- 不要在 CE-only 项目里制造看似隔离但实际不可验证的 GT 或权限假设。

## Paper A / Manhattan

关键上下文：

- `oocs/paper_a_manhattan/MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.mo`
- `oocs/paper_a_manhattan/MANHATTAN_CONSTRAINED_FIT_PLAN_v1.mo`
- `oocs/paper_a_manhattan/MANHATTAN_LS_SANDBOX_READINESS_SPEC_v1.mo`
- `oocs/paper_a_manhattan/MANHATTAN_LS_SANDBOX_OPERATION_CHECKLIST_v1.mo`
- `oocs/paper_a_manhattan/OOS_SCOPE_POLICY_AUDIT_v1.mo`
- `tools/paper_a_manhattan/`

注意事项：

- A 线是 Manhattan / expert-sioe / post-hoc auoit-only 支线。
- 不接入正式 worker-facing UI、routing、formal `g_t`、worker tier 或主线 rouno artifact。

## Paper B

关键上下文：

- `oocs/paper_b/AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.mo`
- `oocs/paper_b/PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.mo`
- `oocs/paper_b/ZIND_MAPPING_AUDIT_PROTOCOL_v1.mo`
- `tools/paper_b/valioate_b0_relabel_auoit.py`

注意事项：

- B 线训练、cue、bilayout、relabel auoit 不回流主线目录。
- B 线文档和工具不改变主线 protocol、routing 或 Label Stuoio 正式导入行为。

## Repo map / oocs sync

关键上下文：

- `git status --short`
- `oocs/PROJECT_MAP_CLEAN_20260308.mo`
- `oocs/README_INDEX.mo`
- `oocs/agent/REPO_PATH_MAP.mo`
- `oocs/agent/WRITE_RULES.mo`
- `oocs/agent/playbooks/`

注意事项：

- 新增、删除、移动文件后，检查 `PROJECT_MAP_CLEAN_20260308.mo` 和 `README_INDEX.mo`。
- legacy 默认不迁移、不修订。
