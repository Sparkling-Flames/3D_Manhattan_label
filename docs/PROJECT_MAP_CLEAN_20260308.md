# HOHONET 项目地图

> 2026-07-18 vFinal 更新：Paper A 正式主线已改为 C1 设计 C2-B
>（common anchor + diverse bridge）、C2-A-RP 精度补测、T1 2×2 条件试验，
> 以及 Strong Global 对 Full-Integrated 的 V1 前瞻双臂政策试验。
> `docs/thesis_main/manuscript/overleaf_project/main.tex` 是唯一论文入口；
> 已删除该工程内未引用的旧版重复章节。C1 原始 export、assignment 和标注界面未改变。
> 新正式实现位于 `tools/thesis_main/analysis/materialize_main_failure_outcomes.py`、
> `build_c2_assignment_manifest_from_c1_gaps.py`、`c1_materialize_c2_gap_audits.py`
> 和 `routing/v1_policy.py`；分别负责完整事故处置与 resolver、C2-B、C2-A-RP
> 以及 Strong Global/Full-Integrated 的 V1 前瞻执行。
> `tools/thesis_main/analysis/materialize_vfinal_main_analysis.py` 只消费 resolver
> 最终表，生成 T1 pair estimand 与 V1 ITT/设计和生产标准化结果。

更新时间：2026-06-08

本地图记录当前仓库的主要目录边界。新增、删除、移动文件后必须检查本文档是否需要同步。

## 顶层目录

- `tools/`：脚本和运行资源，按论文线与共享运行层拆分。
- `docs/`：协议、SOP、字段合同、论文线文档和 agent 规则；论文模板/参考资料等大块写作资产默认按 `.gitignore` 留在本地。
- `import_json/`：planned import / planned split 真源。
  - `stage1_prescreen_foreign_https_20260609/`：Stage 1 / P1 外国标注员 HTTPS Label Studio 导入包；仅将正式中文包的 `data.vis_3d` base URL 改为 `https://label.sparkle0825.top`，任务池、顺序、metadata、proposal 与图片 URL 保持不变。
- `export_label/`：Label Studio 运行时标注导出真源，不作为脚本写入目标。
- `active_logs/`：原始 `active_time` 日志真源；`operational_incidents/` 保存 C1 起不可变的运行事故证据，不与分析输出混用。
- `analysis_results/`：生成结果、审计、manifest、图表和中间分析产物。
- `tests/`：tools 与字段合同的 pytest 覆盖。
- `data/`：数据资产。
- `output/`：HoHoNet 推理与中间产物。
- `trap集/`：trap / manual 候选素材层。

## tools 布局

- `tools/README.md`：tools 总入口；根目录不再保留旧脚本 wrapper。
- `tools/thesis_main/`
  - 论文主线工具。
  - `analysis/`：质量分析、active-time audit、stage-aware 分析、图表、统计汇总。
    - `c1_live_collection_monitor.py`、`c1_canonicalize_exports.py`、`failure_disposition.py`、`materialize_main_failure_outcomes.py`、`c1_materialize_quality_table.py`、`c1_materialize_worker_state.py`、`c1_materialize_worker_profile_sidecar.py`、`c1_materialize_c2_gap_audits.py`、`build_c2_assignment_manifest_from_c1_gaps.py`、`materialize_c2b_task_eligibility.py`、`materialize_p1_post_closeout_evidence_correction.py` 与 `materialize_p1_post_closeout_geometry_scores.py`：C1 live 监控、canonicalization、失败归因、逐轴证据、C2-B 严格任务资格、候选设计与冻结 assignment 消费，以及只读 P1 post-closeout evidence/geometry correction。
    - `rebuild_stage1_chinese_completion_excel.py`：按最新 `标注人员.xlsx`、`退出标注.xlsx`、Stage 1 中文 LS JSON 导出和 active logs 重算中文 P1 完成情况工作簿。
  - `registry/`：registry、manifest、freeze、final-gold、trap/materialization、risk-rule、C2 failure-disposition manifest、`d_t/g_t` dry-run、export inventory。
  - `data_prep/`：数据集准备和 MP3D smoke/import 生成。
  - `foreign_recruitment/`：P1/PreScreen 外国标注员 HTTPS 英文适配包。
- `tools/paper_b/`
  - Paper B 工具。当前包括 `validate_b0_relabel_audit.py`；后续 B0/B1/B2 训练、cue、bilayout、审计脚本只进本目录。
- `tools/label_studio/`
  - 三条线共享的 Label Studio XML、3D viewer、server/CORS、COS/upload、import/build helper 和 `official/`。历史 C1 XML 保持原语义；C2/Stage3 未来语义使用 `label_studio_view_config_c2_future.xml` 与英文对应文件；冻结 SHA 记录在 `tools/label_studio/label_studio_c1_xml_freeze_manifest_v1.json`。
  - `vis_3d_pre_m15_19_2_backup.html`：commit `f6d53b0` 的 viewer 原样备份，仅用于回滚/对照，不是运行时入口。
  - 云服务器运行时 URL `/tools/vis_3d.html` 保持兼容，这是部署路由，不代表源码仍在 `tools/` 根目录。
- `tools/legacy/`、`tools/legacy_server/`、`tools/backups/`
  - 历史或备份目录，默认不迁移、不修订。

## docs 布局

- `docs/README_INDEX.md`：docs 总索引。
- `docs/PROJECT_MAP_CLEAN_20260308.md`：本文件，仓库地图。
- `docs/thesis_main/`
  - 正式执行主线文档。
  - 包括 protocol、assignment SOP、PreScreen、Calibration、Main(Test + Validation)、统计计划、字段合同、worker-profile sidecar contract、final-gold、registry、论文主线写作材料。
  - Paper A 当前唯一提纲真源为 `Paper_A_新版完整论文提纲_vFinal_Draft.md`。v3-v5 提纲、迁移 map/audit 与 standalone `.tex` 已归档到 `docs/legacy/paper_a_pre_vfinal_20260724/`；`WORKER_PROFILE_ARTIFACT_FIELD_CONTRACT_v1.md` 等字段合同继续保留。
  - `manuscript/` 可保存 Overleaf 项目和主线论文写作资产，但按现有 `.gitignore` 默认不提交。
  - `tools/thesis_main/analysis/materialize_c2b_closeout.py` 绑定 C2-B submissions、post-C2-B profile、profile manifest 与 design summary，形成 C2-A-RP formal 所需的真实 SHA closeout。
  - `tools/thesis_main/analysis/materialize_frozen_routing_profiles.py` 从 Manual GT submission、冻结 worker state 和跨阶段 component evidence 生成 Strong Global 与 Full component 冻结表。
  - Paper A vFinal 代码迁移合同、四个候选 rule manifest 与审计记录保存在该目录；这些文件只定义可审计的结构和候选规则，不把 dry-run 产物升级为正式 C1 数据。对应的 canonical→concrete-tag、Geometry LOO 与 temporal replay 代码位于 `tools/thesis_main/analysis/`，且无正式 export 时只能输出 dry-run/not-evaluable。
  - Paper A vFinal 代码迁移合同、四个候选 rule manifest 与审计记录保存在该目录；这些文件只定义可审计的结构和候选规则，不把 dry-run 产物升级为正式 C1 数据。
- `docs/paper_b/`
  - Paper B 支线文档。
  - 包括 ambiguity-aware HoHoNet、ZInD mapping、B-line freeze/audit、模型架构和后续训练计划。
- `docs/label_studio/`
  - Label Studio CE-only、active-time、云端部署、COS、标注员/开发者说明。
- `docs/agent/`
  - Agent 上下文、playbook、写入规则和给 Codex 的补充说明。
  - 关键入口：`AGENT_CONTEXT_INDEX.md`、`REPO_PATH_MAP.md`、`WRITE_RULES.md`、`playbooks/`。
- `docs/shared/`
  - 论文模板、参考资料、共享写作资产；按现有 `.gitignore` 默认不提交。
- `docs/legacy/`
  - 历史材料，默认不迁移、不修订。

## 真源与输出层

- `import_json/` 是 planned import / planned split 真源。
- `export_label/` 是 Label Studio 运行时导出真源；本次 tools/docs 迁移不写入、不移动、不重命名。
- `active_logs/` 是原始 active-time 日志真源；`active_logs/operational_incidents/` 是 C1 起外部系统事故的原始证据源。
  - 云服务器端仍应位于仓库根下，例如 `/home/ubuntu/workspace/HoHoNet/active_logs/`。
  - 若云端设置 `ACTIVE_LOG_DIR="active_logs/new_server"`，新日志应进入 `/home/ubuntu/workspace/HoHoNet/active_logs/new_server/`。
  - `tools/label_studio/cors_server.py` 的源码迁移不应改变日志存储根目录。
- `analysis_results/` 是输出、审计和图表落盘区，不是输入真源。

## 写入与迁移规则

- 新增 `tools/` 脚本必须进入对应论文线或共享 Label Studio 目录，不得直接放在 `tools/` 根目录。
- 新增 `docs/` 主题文档必须进入对应分类目录，不得直接放在 `docs/` 根目录。
- 主线工具和文档分别进入 `tools/thesis_main/` 与 `docs/thesis_main/`。
- Paper B 工具和文档分别进入 `tools/paper_b/` 与 `docs/paper_b/`。
- Label Studio 共享资源和说明分别进入 `tools/label_studio/` 与 `docs/label_studio/`。
- Agent 规则和 playbook 进入 `docs/agent/`。
- legacy 默认不迁移、不修订。
- 不改变 protocol、schema、routing、SOP 语义。
## 2026-07-24 Paper A 分析链收口补充

- `tools/thesis_main/analysis/run_c1_closeout_launch.py`：Paper A C1→C2-B 公开入口；保留 `rehearse-c1`、`freeze-c1`、`audit-c1`、`finalize-c1`、`design-c2b`、`build-c2b` 等细粒度审计命令，并提供可恢复的 `close-c1-and-plan-c2b` 薄入口、scene-building 展开与 runbook 命令合同检查。`design-c2b` 在任何候选枚举前调用 `derive_c2b_design_thresholds.py`，只消费 SHA 绑定的公式合同、C1 design parameters、capacity 与 reviewer approval。`run_c1_precloseout_rehearsal.py` 仅保留为其内部 C1 证据物化器；正式 C2-B 资格由 `materialize_c2b_task_eligibility.py` 直接连接冻结证据。
- `tools/thesis_main/analysis/c1_task_adjusted_quality.py`：C1 唯一 task-adjusted Q_GT 估计器，固定 worker effect、task random intercept 与 task/building cluster bootstrap，同时输出 FE 敏感性和 normal-normal EB 测量证据；排名仅由后续 policy materializer 生成，EB 失败不得回退 raw mean。
- `tools/thesis_main/analysis/c2b_static_evidence.py`：C2-B P1 integrity、reference/candidate path/content SHA 泄漏审计、resolved P1/C1 identity history 推导、scene-building 显式映射展开、非支配 source/holdout 候选与 `c2b_static_freeze_manifest.json` 物化工具；P1 文件冻结与 predictive evidence ready 分开报告。
- `tools/thesis_main/analysis/materialize_c1_operational_reference.py`：把冻结 candidate inventory 中已存在的
  人工 scope 标签和 `groudTruth.json` 单一几何 reference 接入 C1；未复核/冲突任务保持 pending。
- `tools/thesis_main/analysis/materialize_routing_component_evidence.py`：P1→C1→C2-B component evidence
  分层物化；缺 C2-B 时 Full 自动禁用。
- `tools/thesis_main/analysis/materialize_main_inference.py`：T1 image-level 与 V1 ITT 的 manifest/SHA 绑定
  cluster bootstrap 推断入口。
- `tools/thesis_main/analysis/materialize_c2_task_risk.py`：固定 HoHoNet/LHFeat、结构输出、统一 `risk_design_vector_A`/`risk_design_score_A` 的候选任务风险入口；缺少 feature/C1 冻结依赖时 assignment fail-closed。
- `tools/thesis_main/analysis/freeze_c2_feature_reference.py` 与 `tools/thesis_main/registry/hohonet_feature_backend.py`：一次性提取训练参考库和候选池 LHFeat，冻结 PCA/whitening cache、off-grid rotation reinference circular audit 与独立 seam audit；四相位置换仅为恒等性 diagnostic，manifest 中只有声明而无匹配 cache/leakage evidence 时不得 ready。
- `tools/thesis_main/analysis/materialize_c1_c2_design_parameters.py`：从 C1 三轨 eligibility、task-level risk 与 completion 拟合 worker fixed-intercept、worker random-slope、building 与 task-within-building risk model，并按预注册单边界链生成 C2-B 模拟参数；不生成 routing profile。
- `tools/thesis_main/analysis/derive_c2b_design_thresholds.py`：验证冻结公式白名单与 reviewer SHA approval，从 C1 design parameters 和 capacity 机械派生正式 design threshold manifest；不读取 candidate/simulation/feasibility。
- `tools/thesis_main/analysis/materialize_p1_c1_predictive_association.py`：P1→C1 Spearman/Kendall、worker bootstrap 与 range-restriction 审计入口。
- `tools/thesis_main/analysis/geometry_consensus/`：同时物化 worker-specific peer median、任务 crowd structure、medoid LOO 与 strict LOO；3:2 多峰只作审计，不自动选多数簇。
- `tools/thesis_main/analysis/c1_structural_reliability_eb.py`、`materialize_global_policy.py`、`materialize_full_policy.py`、`materialize_counterexample_bank.py`：结构失败 Beta-binomial EB、候选 Global/Full 排名合同与不进入画像/GT/设计的轻量反例库。
- `docs/thesis_main/PAPER_A_METHOD_AMENDMENT_PEER_GT_SHRINKAGE_v1.md` 及四个配套 manifest：登记 estimand gate、同行/GT/EB 方法候选；当前 `status=candidate`、`interpretation_allowed=false`，不得生成正式 policy 或 assignment。
- `docs/thesis_main/PAPER_A_C1_C2_FORMAL_ARCHITECTURE.md`：Paper A C1→C2-B 单一生产 DAG、stage active-log freeze、状态 owner、风险/模拟和人工审批边界；与 vFinal/Protocol/SOP/SAP 配套，不改变其设计语义。
- `docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md`：隔离 GPU 环境、静态 feature/P1 integrity 准备、C1 freeze/audit/finalize 和 C2-B design/build 的正式命令。根因收口方法边界见 `docs/thesis_main/PAPER_A_C1_C2B_ROOT_CAUSE_AMENDMENT_v1.md`。
- `docs/thesis_main/PAPER_A_CLOSE_C1_PLAN_C2B_RUN_CONFIG.template.json`：`close-c1-and-plan-c2b` 可恢复薄入口的路径配置模板；占位符不得直接用于正式运行。
- `config/paper_a_analysis_requirements.lock.txt`、`config/paper_a_torch_requirements.lock.txt` 与 `docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json`：Paper A 隔离运行环境和 feature audit 审批真源；本地 `.venv-paper-a-gpu` 与静态缓存不提交。
- `import_json/paper_a_c2b/legacy_reverse_v3_1_manifest.csv`：20260702 v3.1 13 张人工 reverse 图的只读 provenance；不授予 eligibility 或排序优先权。
- `tools/thesis_main/analysis/c1_c2_mainline.py` 与 `materialize_c1_preannotation_task_features.py`：不可变 C1 row-eligibility sidecar join、estimand-specific worker/task/building/graph gates、唯一 C2-B worker design input，以及不读取 crowd geometry 的预标注 C1 task feature 合同；正式 DAG 由 `docs/thesis_main/PAPER_A_VFINAL_EXECUTION_CONTRACT.json` 固定，风险 exposure 由 `docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json` 固定，设计阈值公式由 `docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json` 固定，正式数值由 SHA 绑定输入机械派生。
