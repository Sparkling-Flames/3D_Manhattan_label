# docs 目录索引

`docs/` 按论文线和共享运行层组织。根目录只保留本索引和项目地图；新增主题文档不要直接放在根目录。

## 根目录入口

- [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)：仓库地图，新增、删除、移动文件后必须检查。
- [README_INDEX.md](README_INDEX.md)：本文档。

## 论文主线

目录：[thesis_main/](thesis_main/)

主线覆盖正式执行协议、PreScreen、Calibration、Main(Test + Validation)、统计计划、字段合同、final-gold、registry 和论文主线写作材料。

关键文件：

- [ROUND_BASED_EXECUTION_PROTOCOL_v1.md](thesis_main/ROUND_BASED_EXECUTION_PROTOCOL_v1.md)
- [ROUND_BASED_ASSIGNMENT_SOP_v1.md](thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md)
- [P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md](thesis_main/P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md)
- [PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md](thesis_main/PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md)
- [C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md](thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md)
- [RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md](thesis_main/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md)
- [STATISTICAL_ANALYSIS_PLAN_v1.md](thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)
- [ANALYSIS_DATA_FLOW.md](thesis_main/ANALYSIS_DATA_FLOW.md)
- [STAGE3_OOD_PREPARATION_PLAN_v1.md](thesis_main/STAGE3_OOD_PREPARATION_PLAN_v1.md)
- [TEST_PLAN_AND_REVIEW.md](thesis_main/TEST_PLAN_AND_REVIEW.md)

对应工具：

- `tools/thesis_main/analysis/`
- `tools/thesis_main/registry/`
- `tools/thesis_main/data_prep/`
- `tools/thesis_main/foreign_recruitment/`

## 论文 A 线 Manhattan

目录：[paper_a_manhattan/](paper_a_manhattan/)

A 线覆盖 Manhattan geometry、sandbox、expert review、post-hoc audit-only、OOS scope audit 和 3D preview geometry 兼容计划。该线不接入正式 worker-facing UI、routing、formal `g_t` 或主线 round artifact。

### Current Active HRC / Contracts

- [HRC_STABILIZATION_STATUS_v1.md](paper_a_manhattan/HRC_STABILIZATION_STATUS_v1.md)：唯一当前状态入口。
- [HRC_SCORING_LAYER_CONTRACT_v1.md](paper_a_manhattan/HRC_SCORING_LAYER_CONTRACT_v1.md)
- [HRC_C3_2_CONSTRAINED_V0_SOURCE_CONTRACT_v1.md](paper_a_manhattan/HRC_C3_2_CONSTRAINED_V0_SOURCE_CONTRACT_v1.md)
- [HRC_C6_5_GLOBAL_HYPOTHESIS_PROBE_SPEC_v1.md](paper_a_manhattan/HRC_C6_5_GLOBAL_HYPOTHESIS_PROBE_SPEC_v1.md)：shadow-only global hypothesis probe spec；not generator execution.
- [HRC_C6_5A_4_SCORING_EVALUATOR_HARDENING_SPEC_v1.md](paper_a_manhattan/HRC_C6_5A_4_SCORING_EVALUATOR_HARDENING_SPEC_v1.md)：spec-only L0–L5 scoring/evaluator hardening contract；不修改 evaluator/ranking/portfolio。
- [HRC_CANDIDATE_SPECIFIC_C4_INPUT_CONTRACT_v1.md](paper_a_manhattan/HRC_CANDIDATE_SPECIFIC_C4_INPUT_CONTRACT_v1.md)：区分 baseline-only、candidate projection delta、candidate image evidence 与 manual visual note 的 fail-closed 输入合同；不是 full C4 或图像模型。
- [MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md](paper_a_manhattan/MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md)
- [MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md](paper_a_manhattan/MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md)：schema/contract；不是 training/update system。

### Audit Records / Milestone Evidence

Audit artifacts are evidence records, not accepted recommendations or writeback authorization.

- [HRC_C6_1_SELECTION_AUDIT_v1.md](paper_a_manhattan/HRC_C6_1_SELECTION_AUDIT_v1.md)
- [HRC_C6_2_SELECTION_AUDIT_v1.md](paper_a_manhattan/HRC_C6_2_SELECTION_AUDIT_v1.md)
- C1 fallback/fail-closed audit artifact：`analysis_results/paper_a_manhattan/hypothesis_ranking_core/case_contract_fallback_audit/`；runner：`tools/paper_a_manhattan/run_case_contract_fallback_audit.py`
- C3 constrained_v0 shadow/consolidation audit artifacts：`analysis_results/paper_a_manhattan/constrained_v0_shadow_audit/`；runners：`tools/paper_a_manhattan/run_constrained_v0_shadow_audit.py`、`tools/paper_a_manhattan/run_constrained_v0_consolidation_audit.py`

### Legacy M15 Background / Background Specs

Legacy M15 specs are background; current active selection remains HRC-gated and audit-blocked unless explicitly changed.

- [MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md](paper_a_manhattan/MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md)
- [MANHATTAN_CONSTRAINED_FIT_PLAN_v1.md](paper_a_manhattan/MANHATTAN_CONSTRAINED_FIT_PLAN_v1.md)
- [CONSERVATIVE_HEIGHT_REPROJECT_CANDIDATE_SPEC_v1.md](paper_a_manhattan/CONSERVATIVE_HEIGHT_REPROJECT_CANDIDATE_SPEC_v1.md)
- [ADAPTIVE_LOCAL_X_SEARCH_SPEC_v1.md](paper_a_manhattan/ADAPTIVE_LOCAL_X_SEARCH_SPEC_v1.md)
- [LOCAL_FLOORPRINT_DENSE_CORNER_PROBE_SPEC_v1.md](paper_a_manhattan/LOCAL_FLOORPRINT_DENSE_CORNER_PROBE_SPEC_v1.md)
- [LOCAL_3D_PROJECTION_REVIEW_SPEC_v1.md](paper_a_manhattan/LOCAL_3D_PROJECTION_REVIEW_SPEC_v1.md)
- [VERIFIED_3D_LOCAL_ASSIST_OPEN_SPEC_v1.md](paper_a_manhattan/VERIFIED_3D_LOCAL_ASSIST_OPEN_SPEC_v1.md)
- [MANHATTAN_LS_SANDBOX_READINESS_SPEC_v1.md](paper_a_manhattan/MANHATTAN_LS_SANDBOX_READINESS_SPEC_v1.md)
- [MANHATTAN_LS_SANDBOX_OPERATION_CHECKLIST_v1.md](paper_a_manhattan/MANHATTAN_LS_SANDBOX_OPERATION_CHECKLIST_v1.md)
- [VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md](paper_a_manhattan/VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md)
- [VIS_3D_GEOMETRY_FIXTURE_PLAN_v1.md](paper_a_manhattan/VIS_3D_GEOMETRY_FIXTURE_PLAN_v1.md)
- [OOS_SCOPE_POLICY_AUDIT_v1.md](paper_a_manhattan/OOS_SCOPE_POLICY_AUDIT_v1.md)
- [M15_LEGACY_ARTIFACT_DEPENDENCY_INVENTORY_v1.md](paper_a_manhattan/M15_LEGACY_ARTIFACT_DEPENDENCY_INVENTORY_v1.md)
- Other existing Paper A background files：`Aline-deep-research-report(legacy).md`、`后续方针.md`、`评分如何制定.md`、`当前主线的讨论对话.txt`、`*.docx` research notes。

对应工具：`tools/paper_a_manhattan/`

#### Current HRC tools

- `tools/paper_a_manhattan/manhattan_case_contract.py`
- `tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py`
- `tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py`
- `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py`
- `tools/paper_a_manhattan/manhattan_candidate_source_interface.py`、`tools/paper_a_manhattan/manhattan_legacy_m1528_candidate_source.py`

#### Audit / materialization tools

- `tools/paper_a_manhattan/run_case_contract_fallback_audit.py` materializes C1 fallback/fail-closed audit for real, missing-metrics, and partial/malformed-metrics paths; read-only audit runner; does not change active runner selection.
- `tools/paper_a_manhattan/run_hrc_c6_stability_audit.py` materializes the read-only C6.3c stability audit attempt, explicitly separating active HRC bucket audit cases, unavailable active-HRC cases, and evidence-only / fixture-only records; it does not change ranking, active source, or recommendation authorization.
- `tools/paper_a_manhattan/run_hrc_multicase_audit_input_pack.py` materializes C6.3d audit-only multi-case candidate input packs from existing artifacts / fixtures; it does not generate new candidates, change active runner selection, or authorize recommendation/writeback.
- `tools/paper_a_manhattan/run_hrc_candidate_adequacy_audit.py` materializes C6.4 read-only candidate adequacy coverage over current HRC payload and multi-case input packs; it does not generate candidates, change ranking, or authorize recommendation/writeback.
- `tools/paper_a_manhattan/run_hrc_shadow_global_probe_planner.py` materializes the C6.5a read-only planner from the C6.5 spec and existing C6.4/input-pack evidence; it generates no candidate or geometry variant and does not change active runner, ranking, or C3.
- `tools/paper_a_manhattan/run_hrc_source_artifact_readiness_audit.py` materializes the manifest-driven C6.5a.1 case/evidence source-readiness matrix with schema/identity/variant/row-count validation and a separate manual-evidence sidecar contract; it generates no candidate, proposal, or geometry.
- `tools/paper_a_manhattan/run_hrc_evidence_input_materialization.py` materializes C6.5a.2 audit-only C2/C4/C5 and fail-closed contract inputs for validated existing original variants; it does not project candidate rows, rank candidates, or authorize C6.5b.
- `tools/paper_a_manhattan/run_hrc_scoring_compliance_audit.py` materializes the C6.5a.3/4c L0-L5 compliance and selection regression audit; it records resolved layer-order violations and remaining evidence/manual-data blockers without authorizing C6.5b.
- `tools/paper_a_manhattan/run_hrc_gt_correction_audit.py` materializes the C6.5a.5/5.1 `4543gt` corrected-GT audit, independent 4-pair projection, and explicit-column sidecar; short-wall/keep-distinct are not applicable, old GT is preserved, and C6.5b remains blocked.
- `tools/paper_a_manhattan/run_hrc_c6_5a_6_candidate_dry_run.py` materializes the four fixed pair2 y-step 4-pair audit-only candidates and local 3D comparison preview for `task238_ann2389_4543gt`; it performs no search and changes no active ranking or authorization.
- `tools/paper_a_manhattan/run_hrc_c6_5a_6_2_manual_selection_ledger.py` materializes the C6.5a.6.2 human review-only selection of candidate 0003 (`y +0.75`); it does not accept, authorize, apply, or write back the candidate.
- `tools/paper_a_manhattan/run_hrc_c6_5a_7_blocker_closure_audit.py` materializes the C6.5a.7.1 blocker closure report, 2369 partial explicit-column / available keep-distinct verdicts, and the 3741 same-image updated-human-reference order; it does not authorize C6.5b or alter active ranking.
- `tools/paper_a_manhattan/run_hrc_candidate_specific_c4_contract_audit.py` materializes fail-closed candidate-specific C4 contract records for 3741/0017 and 4543gt/0003; projection delta does not imply image evidence.
- `tools/paper_a_manhattan/run_segment_aware_manhattan_refit_3741.py` materializes the C6.5a.9 deterministic 12-pair wall-line intersection refit and local review preview for 3741; no random/grid perturbation, active ranking, or writeback.
- `tools/paper_a_manhattan/run_constrained_v0_shadow_audit.py` materializes read-only constrained_v0 shadow audits; it does not change active source or ranking.
- `tools/paper_a_manhattan/run_constrained_v0_consolidation_audit.py` consolidates the two implemented constrained_v0 shadow families and their fail-closed/positive-fixture audits; it does not authorize a third family or active source replacement.
- `tools/paper_a_manhattan/materialize_manhattan_feedback_ledger_entry.py` validates a core output plus expert review and writes one feedback-ledger JSONL entry; it does not train, update parameters, apply candidates, or write annotations.

#### Legacy M15 / local review tools

- `tools/paper_a_manhattan/manhattan_candidate_gate.py`、`manhattan_layout_state.py`、`manhattan_pair_assist.py`：pre-HRC expert-side diagnostics and candidate-gating helpers.
- `tools/paper_a_manhattan/manhattan_height_reproject_gate.py`、`manhattan_height_reproject_candidate.py`、`manhattan_assist_review_harness.py`、`run_height_reproject_applicability_smoke.py`、`run_single_image_manhattan_assist.py`：M15 height/review harness background tools.
- `tools/paper_a_manhattan/manhattan_verified_3d_local_assist.py`、`manhattan_local_floorprint_probe.py`、`manhattan_3d_projection.py`、`run_local_3d_projection_review.py`、`serve_local_3d_projection_review.py`、`run_manhattan_hypothesis_local_review.py`：local projection/review background tools.
- `tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py`、`run_m1520_local_candidate_search.py`、`run_m1524_hard_case_audit_pack.py`、`run_m1525_visual_verdict_pack.py`、`manhattan_m1526_adaptive_local_probe.py`、`run_m1526_adaptive_local_probe.py`、`manhattan_m1527_semantic_direct_search.py`、`run_m1527_semantic_direct_search.py`、`run_m1527_optimization_trace_ledger.py`、`manhattan_m1528_semantic_action_library.py`、`run_m1528_semantic_action_library.py`：legacy M15 compatibility chain and local milestone tooling.
  M15.28 compatibility fields are deprecated for the new core. New consumers must read only `portfolio_ranking` and `constrained_evaluations`; legacy portfolio, gate, and score fields are confined to compact `legacy_diagnostics`.

## 论文 B 线

目录：[paper_b/](paper_b/)

B 线覆盖 ambiguity-aware HoHoNet、ZInD mapping、B0 relabel audit、后续训练、cue、bilayout 和模型审计。该线与主线协议和 A 线 Manhattan 工具分开维护。

关键文件：

- [AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.md](paper_b/AMBIGUITY_AWARE_HOHONET_EXTENSION_PLAN_v1.md)
- [PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md](paper_b/PAPER_B_MODEL_ARCHITECTURE_SPEC_v1.md)
- [ZIND_MAPPING_AUDIT_PROTOCOL_v1.md](paper_b/ZIND_MAPPING_AUDIT_PROTOCOL_v1.md)
- [B_FREEZE_V2_1_CONTRACT_AUDIT_20260317.md](paper_b/B_FREEZE_V2_1_CONTRACT_AUDIT_20260317.md)
- [B_SELECTION_FREEZE_RERUN_20260317.md](paper_b/B_SELECTION_FREEZE_RERUN_20260317.md)

对应工具：`tools/paper_b/`

## Label Studio 与云端运行

目录：[label_studio/](label_studio/)

该目录保存三条线共享的 Label Studio CE-only、active-time、云端部署、标注员和开发者说明。云服务器运行时 URL `/tools/vis_3d.html` 保持兼容；这是部署路由，不表示源码仍在 `tools/` 根目录。

关键文件：

- [LS_CE_ONLY_OPERATION_SOP_v1.md](label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md)
- [label studio注意事项.md](label_studio/label%20studio%E6%B3%A8%E6%84%8F%E4%BA%8B%E9%A1%B9.md)
- [ACTIVE_TIME_README.md](label_studio/ACTIVE_TIME_README.md)
- [COS_上传与导入中文说明.md](label_studio/COS_%E4%B8%8A%E4%BC%A0%E4%B8%8E%E5%AF%BC%E5%85%A5%E4%B8%AD%E6%96%87%E8%AF%B4%E6%98%8E.md)
- [README_ANNOTATOR.md](label_studio/README_ANNOTATOR.md)
- [README_DEVELOPER.md](label_studio/README_DEVELOPER.md)
- [SOP_labelstudio_experiment.md](label_studio/SOP_labelstudio_experiment.md)

对应工具：`tools/label_studio/`

- `tools/label_studio/vis_3d_pre_m15_19_2_backup.html` is the verbatim `vis_3d.html` snapshot from commit `f6d53b0`, retained only as a pre-M15.19.2 rollback/reference copy; runtime entry points continue to use `vis_3d.html`.

## Agent 与写入规则

目录：[agent/](agent/)

- [AGENT_CONTEXT_INDEX.md](agent/AGENT_CONTEXT_INDEX.md)
- [WRITE_RULES.md](agent/WRITE_RULES.md)
- [playbooks/](agent/playbooks/)

根目录 [../AGENTS.md](../AGENTS.md) 是 agent 的工作入口；`docs/agent/WRITE_RULES.md` 是 tools/docs 写入边界的细化说明。

## 本地共享材料

目录：[shared/](shared/)

保存论文模板、参考材料和共享写作资产。论文主线 Overleaf 项目可放入 `docs/thesis_main/manuscript/`。

这些资料目录按现有 `.gitignore` 默认不纳入仓库提交；需要共享时先确认是否应进入 Git、云盘或论文协作平台。

## 历史材料

目录：[legacy/](legacy/)

历史材料默认不迁移、不修订。路径检查和乱码修复默认排除该目录。
