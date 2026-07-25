# docs 目录索引

> 2026-07-18：Paper A 正式文本已迁移到 vFinal。当前正文入口为
> `thesis_main/manuscript/overleaf_project/main.tex`；正式执行合同为
> `ROUND_BASED_EXECUTION_PROTOCOL_v1.md`、`ROUND_BASED_ASSIGNMENT_SOP_v1.md`
> 与 `STATISTICAL_ANALYSIS_PLAN_v1.md`。旧提纲仅作历史审计，不再定义 C2/T1/V1。
> 字段真源同步为 `C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md`、
> `WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 与 `ANALYSIS_DATA_FLOW.md`。

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
- [C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md](thesis_main/C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md)
- [WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md](thesis_main/WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md)
- [WORKER_PROFILE_ARTIFACT_MIGRATION_AMENDMENT_v1.md](thesis_main/WORKER_PROFILE_ARTIFACT_MIGRATION_AMENDMENT_v1.md)
- [WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md](thesis_main/WORKER_PROFILE_AND_THESIS_OUTLINE_AMENDMENT_v1.md)
- [WORKER_PROFILE_THESIS_DISPLAY_CONTRACT_v1.md](thesis_main/WORKER_PROFILE_THESIS_DISPLAY_CONTRACT_v1.md)
- [WORKER_PROFILE_AMENDMENT_COMPATIBILITY_BRIDGE_v1.md](thesis_main/WORKER_PROFILE_AMENDMENT_COMPATIBILITY_BRIDGE_v1.md)
- [PAPER_A_VFINAL_ANALYSIS_ARTIFACT_AMENDMENT_v1.md](thesis_main/PAPER_A_VFINAL_ANALYSIS_ARTIFACT_AMENDMENT_v1.md)：Paper A vFinal sidecar、dry-run 与正式数据边界
- [PAPER_A_VFINAL_EXECUTION_CONTRACT.json](thesis_main/PAPER_A_VFINAL_EXECUTION_CONTRACT.json)：C1→C2 主线 DAG、三段 freeze gate、风险通道与 legacy 隔离合同
- [C2B_RISK_DESIGN_CONTRACT_v1.json](thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json)：C2-B 唯一风险通道、分层、模拟与冻结状态合同
- [C2B_DESIGN_SELECTION_THRESHOLDS.json](thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json)：C2-B 正式设计审批阈值；默认空值时仅允许 candidate 输出
- `Paper_A_新版完整论文提纲_vFinal_Draft.md`：当前唯一 vFinal 提纲真源，包含 C1→C2→T1/V1 的 failure-disposition、重跑与行政删失合同。
- [meta_label_three_state_rule_manifest_v1.json](thesis_main/meta_label_three_state_rule_manifest_v1.json)：三状态 meta-label 候选规则
- [geometry_loo_candidate_rule_manifest_v1.json](thesis_main/geometry_loo_candidate_rule_manifest_v1.json)：Geometry LOO 候选规则
- [sequential_routing_candidate_rule_manifest_v1.json](thesis_main/sequential_routing_candidate_rule_manifest_v1.json)：历史冻结的时序 routing 候选规则
- [sequential_routing_candidate_rule_manifest_v2.json](thesis_main/sequential_routing_candidate_rule_manifest_v2.json)：统一 temporal replay 状态机与候选规则合同
- [model_issue_harmonization_rule_manifest_v1.json](thesis_main/model_issue_harmonization_rule_manifest_v1.json)：model issue 抖动容忍与 harmonization 候选规则
- [RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md](thesis_main/RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md)
- [STATISTICAL_ANALYSIS_PLAN_v1.md](thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)
- [ANALYSIS_DATA_FLOW.md](thesis_main/ANALYSIS_DATA_FLOW.md)
- [PRESCREEN_STEP4_5_CLOSEOUT_NOTE.md](thesis_main/PRESCREEN_STEP4_5_CLOSEOUT_NOTE.md)

对应工具：

- `tools/thesis_main/analysis/`
- `tools/thesis_main/registry/`
- `tools/thesis_main/data_prep/`
- `tools/thesis_main/foreign_recruitment/`

## 论文 B 线

目录：[paper_b/](paper_b/)

B-line covers ambiguity-aware HoHoNet, ZInD mapping, B0 relabel audit, later training, cue, bilayout, and model audit. It is maintained separately from thesis main protocol.

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
- `tools/label_studio/label_studio_c1_xml_freeze_manifest_v1.json` 记录历史 C1 XML 冻结 SHA 与未来 XML 版本边界。
- [SOP_labelstudio_experiment.md](label_studio/SOP_labelstudio_experiment.md)

对应工具：`tools/label_studio/`

- `tools/label_studio/vis_3d_pre_m15_19_2_backup.html` is the verbatim `vis_3d.html` snapshot from commit `f6d53b0`, retained only as a pre-M15.19.2 rollback/reference copy; runtime entry points continue to use `vis_3d.html`.

## Agent 与写入规则

目录：[agent/](agent/)

- [AGENT_CONTEXT_INDEX.md](agent/AGENT_CONTEXT_INDEX.md)
- [REPO_PATH_MAP.md](agent/REPO_PATH_MAP.md)
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
## 2026-07-24 代码入口补充

- C1 不可变 pre-closeout rehearsal：`tools/thesis_main/analysis/run_c1_precloseout_rehearsal.py`
- C1 人工 task outcome / 单一 GT reference：`tools/thesis_main/analysis/materialize_c1_operational_reference.py`
- P1→C1→C2-B component evidence：`tools/thesis_main/analysis/materialize_routing_component_evidence.py`
- T1/V1 正式推断：`tools/thesis_main/analysis/materialize_main_inference.py`
- C2 task-risk materializer：`tools/thesis_main/analysis/materialize_c2_task_risk.py`
- C1→C2-B 风险斜率/方差设计参数：`tools/thesis_main/analysis/materialize_c1_c2_design_parameters.py`
- P1→C1 predictive association：`tools/thesis_main/analysis/materialize_p1_c1_predictive_association.py`
- C1 closeout / C2 launch 两日入口：`tools/thesis_main/analysis/run_c1_closeout_launch.py`
