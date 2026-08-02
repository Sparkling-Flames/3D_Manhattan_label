<!-- PAPER_A_MACHINE_STATUS: normative -->
<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260802_v15 SHA-256 24d4dd64ba6d1cc7af0ea5fa34ecb2b03940059a3125e7a6c030d00dc3a594b6 -->
# Agent 上下文索引

本索引用于快速定位 Codex 工作时应先读的上下文。路径已经按论文主线、论文 A 线 Manhattan、论文 B 线和共享 Label Studio 层拆分。

## P1 / PreScreen

关键上下文：

- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`
- `docs/thesis_main/P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md`
- `docs/thesis_main/PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md`
- `docs/thesis_main/prescreen_freeze_note_v1.md`
- `import_json/stage1_prescreen_final_20260325/`
- `analysis_results/phase1_progress_20260324/stage1_final_binding_audit_v6.json`
- `analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl`
- `tools/thesis_main/foreign_recruitment/`

注意事项：

- 不要把 `PreScreen_manual`、`PreScreen_semi`、OOS gate 或 routing profile 的含义改写成新协议。
- `analysis_results/` 是输出与审计落盘区，不是输入真源。

## C1 / C2 Calibration

关键上下文：

- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`
- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `tools/thesis_main/registry/build_c1_assignment_manifest.py`
- `tools/thesis_main/registry/compute_dt_score.py`
- `tools/thesis_main/registry/init_task_risk_rule_manifest.py`
- `tests/test_build_c1_assignment_manifest.py`
- `tests/test_compute_dt_score.py`
- `tests/test_init_task_risk_rule_manifest.py`

注意事项：

- `C1` 只能生成 provisional values；`C2` 才能为 Main/Test/Validation 前的 freeze 提供校准依据。
- 不要让 Main/Test/Validation 逻辑绕过 calibration freeze。

## RQ1 / active_time

关键上下文：

- `docs/thesis_main/manuscript/overleaf_project/main.tex`
- `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`
- `docs/label_studio/ACTIVE_TIME_README.md`
- `active_logs/readme.md`
- `tools/label_studio/official/ls_userscript_annotator.js`
- `tools/label_studio/cors_server.py`
- `tools/thesis_main/analysis/lead_time_stats.py`
- `tools/thesis_main/analysis/analyze_quality.py`
- `tests/test_analyze_quality.py`

注意事项：

- `active_time` 是 primary estimand；`lead_time` 是 fallback / sensitivity。
- 云端日志仍写入仓库根下 `active_logs/` 或 `active_logs/new_server/`，不是 `tools/active_logs/`。

## RQ2 / consensus / meta-label

关键上下文：

- `docs/thesis_main/manuscript/overleaf_project/main.tex`
- `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`
- `tools/thesis_main/registry/meta_label_guard.py`
- `tools/thesis_main/registry/materialize_meta_label_consensus_summary.py`
- `tests/test_materialize_meta_label_consensus_summary.py`

注意事项：

- Paired subset、paired permutation/bootstrap、meta-label consensus sidecar 的字段含义不得静默漂移。
- Paper A vFinal 另有三状态 meta-label sidecar；其候选规则见 `docs/thesis_main/meta_label_three_state_rule_manifest_v1.json`，没有正式 C1 标注时只能输出 `dry_run`/`not_evaluable`。

## Paper A vFinal / canonical evidence / geometry LOO

- `docs/thesis_main/PAPER_A_VFINAL_ANALYSIS_ARTIFACT_AMENDMENT_v1.md`
- `docs/thesis_main/PAPER_A_VFINAL_CODE_MIGRATION_AUDIT_v1.md`
- `docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json`
- `docs/thesis_main/model_issue_harmonization_rule_manifest_v1.json`

注意事项：canonical evidence、model issue harmonization、Geometry LOO、worker scene profile 与 sequential routing 都是 sidecar/candidate 层；没有正式 C1 export 时不得写入正式 closeout、C2 assignment 或 thesis-facing claim。

- `tools/thesis_main/analysis/routing/temporal_replay.py` 是事件驱动 candidate replay；`offline_replay_v2.py` 仅为静态 scaffold 兼容入口，二者均不得生成 assignment。

## RQ3 / routing / replay

关键上下文：

- `docs/thesis_main/manuscript/overleaf_project/main.tex`
- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`
- `docs/thesis_main/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md`
- `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md`
- `tools/thesis_main/registry/compute_dt_score.py`
- `tools/thesis_main/registry/init_task_risk_rule_manifest.py`

注意事项：

- Random / Global / Full 和 Validation support-set shadow/replay 的语义不能被路径迁移改变。
- 不要把 agent context 或 playbook 文档改成 routing service。

## Label Studio CE-only operation

关键上下文：

- `docs/label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md`
- `docs/label_studio/label studio注意事项.md`
- `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md`
- `import_json/`
- `tools/label_studio/`

注意事项：

- Label Studio CE 没有企业级可见性隔离；用 manifest、import JSON、assignment manifest 做分发边界。
- 不要在 CE-only 项目里制造看似隔离但实际不可验证的 GT 或权限假设。

## Paper A / Manhattan

关键上下文：

- `docs/paper_a_manhattan/MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md`
- `docs/paper_a_manhattan/MANHATTAN_CONSTRAINED_FIT_PLAN_v1.md`
- `docs/paper_a_manhattan/MANHATTAN_LS_SANDBOX_READINESS_SPEC_v1.md`
- `docs/paper_a_manhattan/MANHATTAN_LS_SANDBOX_OPERATION_CHECKLIST_v1.md`
- `docs/paper_a_manhattan/OOS_SCOPE_POLICY_AUDIT_v1.md`
- `tools/paper_a_manhattan/`

注意事项：

- A 线是 Manhattan / expert-side / post-hoc audit-only 支线。
- 不接入正式 worker-facing UI、routing、formal `g_t`、worker tier 或主线 round artifact。

## Paper B

关键上下文：

- `docs/paper_b/AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.md`
- `docs/paper_b/PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md`
- `docs/paper_b/ZIND_MAPPING_AUDIT_PROTOCOL_v1.md`
- `tools/paper_b/validate_b0_relabel_audit.py`

注意事项：

- B 线训练、cue、bilayout、relabel audit 不回流主线目录。
- B 线文档和工具不改变主线 protocol、routing 或 Label Studio 正式导入行为。

## Repo map / docs sync

关键上下文：

- `git status --short`
- `docs/PROJECT_MAP_CLEAN_20260308.md`
- `docs/README_INDEX.md`
- `docs/agent/REPO_PATH_MAP.md`
- `docs/agent/WRITE_RULES.md`
- `docs/agent/playbooks/`

注意事项：

- 新增、删除、移动文件后，检查 `PROJECT_MAP_CLEAN_20260308.md` 和 `README_INDEX.md`。
- legacy 默认不迁移、不修订。
## Paper A 当前批次执行

- 唯一机器真源：PAPER_A_METHOD_CONTRACT_CURRENT.json。
- C1-A snapshot、C2-B Batch A/B 与最终 pooled Stage 3 gate 是独立状态；旧字段合同和旧 protocol 仅在 docs/legacy/ 中审计。

