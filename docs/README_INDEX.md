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
- [MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md](paper_a_manhattan/MANHATTAN_HEIGHT_REPROJECT_SAFETY_CONTRACT_v1.md)
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
- `tools/paper_a_manhattan/manhattan_assist_review_harness.py` provides offline M15.x review/evaluation rows and summaries, including M15.9 diagnostic-only height reproject applicability evaluation; it does not generate candidates, write annotations, add UI, route, or create formal artifacts.
- `tools/paper_a_manhattan/run_height_reproject_applicability_smoke.py` runs the M15.10 offline height applicability regression fixture through the review harness and emits JSON rows/summary only; it does not generate y candidates, write annotations, add UI, route, or create formal artifacts.

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
