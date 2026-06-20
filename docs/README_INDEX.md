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

关键文件：

- [MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md](paper_a_manhattan/MANHATTAN_GEOMETRY_TOOL_ROADMAP_v2.md)
- [MANHATTAN_CONSTRAINED_FIT_PLAN_v1.md](paper_a_manhattan/MANHATTAN_CONSTRAINED_FIT_PLAN_v1.md)
- [MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md](paper_a_manhattan/MANHATTAN_HYPOTHESIS_FEEDBACK_LEDGER_SCHEMA_v1.md)
- [MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md](paper_a_manhattan/MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md)
- [CONSERVATIVE_HEIGHT_REPROJECT_CANDIDATE_SPEC_v1.md](paper_a_manhattan/CONSERVATIVE_HEIGHT_REPROJECT_CANDIDATE_SPEC_v1.md)
- [ADAPTIVE_LOCAL_X_SEARCH_SPEC_v1.md](paper_a_manhattan/ADAPTIVE_LOCAL_X_SEARCH_SPEC_v1.md)
- [LOCAL_FLOORPRINT_DENSE_CORNER_PROBE_SPEC_v1.md](paper_a_manhattan/LOCAL_FLOORPRINT_DENSE_CORNER_PROBE_SPEC_v1.md)
- [LOCAL_3D_PROJECTION_REVIEW_SPEC_v1.md](paper_a_manhattan/LOCAL_3D_PROJECTION_REVIEW_SPEC_v1.md)
- [VERIFIED_3D_LOCAL_ASSIST_OPEN_SPEC_v1.md](paper_a_manhattan/VERIFIED_3D_LOCAL_ASSIST_OPEN_SPEC_v1.md)
- [MANHATTAN_LS_SANDBOX_READINESS_SPEC_v1.md](paper_a_manhattan/MANHATTAN_LS_SANDBOX_READINESS_SPEC_v1.md)
- [MANHATTAN_LS_SANDBOX_OPERATION_CHECKLIST_v1.md](paper_a_manhattan/MANHATTAN_LS_SANDBOX_OPERATION_CHECKLIST_v1.md)
- [OOS_SCOPE_POLICY_AUDIT_v1.md](paper_a_manhattan/OOS_SCOPE_POLICY_AUDIT_v1.md)
- [VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md](paper_a_manhattan/VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md)
- [VIS_3D_GEOMETRY_FIXTURE_PLAN_v1.md](paper_a_manhattan/VIS_3D_GEOMETRY_FIXTURE_PLAN_v1.md)

对应工具：`tools/paper_a_manhattan/`
- `tools/paper_a_manhattan/manhattan_candidate_gate.py` provides the M14.3 expert-side candidate gating core for constrained-fit outputs; it is not correctness, formal `g_t`, routing, worker quality, writeback, UI, or P1/C1/C2/T1/V1 logic.
- `tools/paper_a_manhattan/manhattan_layout_state.py` provides the M14.4 expert-side RoomLayoutState and pair diagnostics core; it is diagnostic only and has no UI, snap/apply/writeback, routing, worker quality, formal `g_t`, or P1/C1/C2/T1/V1 role.
- `tools/paper_a_manhattan/manhattan_pair_assist.py` provides the M14.5 expert-side low-risk pair diagnostics consumer and x-alignment preview candidate core; it does not apply, snap, reproject height, move walls, write annotations, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/manhattan_height_reproject_gate.py` provides the M15.8 diagnostic-only height reproject applicability and y-delta gate; it does not implement height reproject, return candidates, write annotations, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/manhattan_height_reproject_candidate.py` provides the M15.16 conservative fixed-bottom/top-y review-only dry-run rows; it does not change x/order, write annotations, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/manhattan_assist_review_harness.py` provides offline M15.x review/evaluation rows and summaries, including M15.9 diagnostic-only height reproject applicability evaluation; it does not generate candidates, write annotations, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/manhattan_verified_3d_local_assist.py` provides the M15.14-M15.18 expert-side verified 3D local assist harness for dense-corner reclassification, explicit target x-only dry-run metrics, adaptive local x-search, floor-footprint sensitivity, local unresolved-dense-corner hypothesis sidecars, and angle/order provenance; it does not add UI, write annotations, auto reorder/merge corners, route, or create formal artifacts.
- `tools/paper_a_manhattan/manhattan_local_floorprint_probe.py` provides M15.18 fixed bottom-y sensitivity and unresolved dense-corner local hypothesis dry-runs; it does not authorize edits, emit annotation patches, apply topology changes, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/run_height_reproject_applicability_smoke.py` runs the M15.10 offline height applicability regression fixture through the review harness and emits JSON rows/summary only; it does not generate y candidates, write annotations, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/run_single_image_manhattan_assist.py` provides the M15.x single-image expert-side diagnostic CLI for preview compatibility, override-pack provenance, RoomLayoutState, Align Pair X suggestions, height applicability rows, conservative height review rows, and verified 3D local assist sidecars; it does not implement UI, apply/writeback, routing, or formal artifacts.
- `tools/paper_a_manhattan/manhattan_3d_projection.py` mirrors the current `vis_3d.html` projection formula and computes local-only floorprint, turn, height, dense-pair, clamp, and provenance metrics; it is not correctness, GT, writeback, routing, worker scoring, or a formal artifact.
- `tools/paper_a_manhattan/run_local_3d_projection_review.py` generates the M15.23.7 flexible local compare grid (1–6 panels, visible per-panel remove, two rows per viewport with additional rows scrolling) and read-only bridges for M15.22, M15.26, and M15.27.1 candidates. Global display controls and active-panel inspection semantics are preserved.
- `tools/paper_a_manhattan/serve_local_3d_projection_review.py` serves one generated review from repository root on `127.0.0.1`; it is a read-only local launcher helper and does not connect to Label Studio or write annotations.
- `tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py` provides M15.20–M15.22 bounded local candidates, expert assertion gates, and three assertion-constrained joint probe families; it does not perform global optimization, authorize final fixes, write annotations, route tasks, or create formal artifacts.
- `tools/paper_a_manhattan/run_m1520_local_candidate_search.py` generates the local JSON/Markdown candidate report and reads the optional M15.21 assertion sidecar used by M15.22 joint probes; it does not add viewer UI or mutate Label Studio data.
- `tools/paper_a_manhattan/run_m1524_hard_case_audit_pack.py` aggregates the 3741/2369/2389 applicable, smoke, and safe-skip states into a read-only JSON/Markdown audit pack; it does not add candidates or change M15.22 scoring/gating.
- `tools/paper_a_manhattan/run_m1525_visual_verdict_pack.py` records the task218_ann3741 expert visual verdict and source hashes as a read-only JSON/Markdown sidecar. That verdict was archived from the pre-compare-grid M15.23.4 review; the later M15.23.5 compare grid improves visual comparison only and does not alter the verdict.
- `tools/paper_a_manhattan/manhattan_m1526_adaptive_local_probe.py` and `run_m1526_adaptive_local_probe.py` provide the deterministic bounded primary-edge/wall-surface-aware adaptive dry-run for task218_ann3741, with assertion-constrained variables, decomposed scores, beam trace, and conservative direct-trial gates; they do not modify projection, M15.22, annotations, routing, viewer behavior, or formal artifacts.
- `tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py` and `run_m1527_semantic_direct_search.py` provide the M15.27.1 deterministic semantic search and manual-review-only verdict contract; legacy M15.27 output is archived under the case-local `legacy/` directory.
- `tools/paper_a_manhattan/run_m1527_optimization_trace_ledger.py` seeds and atomically records the expert comparison of the M15.22/M15.26/M15.27.1 path; it writes only the local optimization ledger.
- `tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py` and `run_m1528_semantic_action_library.py` add decoupled x, primary-edge, short-wall-preserving, height-portfolio, and explicitly gated secondary-window actions. The official runner requires a reviewed trace ledger and never claims an automatic fix.
- `tools/paper_a_manhattan/manhattan_case_contract.py`, `manhattan_constrained_hypothesis_evaluator.py`, and `manhattan_hypothesis_portfolio.py` provide the Manhattan Constrained Hypothesis Ranking Core. Legacy M15.* remains a candidate source; hard gates and structured metrics drive expert-side offline portfolio ranking without apply, writeback, worker-facing, routing, or protocol behavior.
- `tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py` emits the standalone `manhattan_constrained_hypothesis_ranking_core_v1` output; M15.28 is retained only as its legacy candidate source.
  M15.28 compatibility fields are deprecated for the new core. New consumers must read only `portfolio_ranking` and `constrained_evaluations`; legacy portfolio, gate, and score fields are confined to compact `legacy_diagnostics`.
- `tools/paper_a_manhattan/materialize_manhattan_feedback_ledger_entry.py` validates a core output plus expert review and writes one feedback-ledger JSONL entry; it does not train, update parameters, apply candidates, or write annotations.

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
