# HOHONET 项目地图

更新时间：2026-06-08

本地图记录当前仓库的主要目录边界。新增、删除、移动文件后必须检查本文档是否需要同步。

## 顶层目录

- `tools/`：脚本和运行资源，按论文线与共享运行层拆分。
- `docs/`：协议、SOP、字段合同、论文线文档和 agent 规则；论文模板/参考资料等大块写作资产默认按 `.gitignore` 留在本地。
- `import_json/`：planned import / planned split 真源。
  - `stage1_prescreen_foreign_https_20260609/`：Stage 1 / P1 外国标注员 HTTPS Label Studio 导入包；仅将正式中文包的 `data.vis_3d` base URL 改为 `https://label.sparkle0825.top`，任务池、顺序、metadata、proposal 与图片 URL 保持不变。
- `export_label/`：Label Studio 运行时标注导出真源，不作为脚本写入目标。
- `active_logs/`：原始 `active_time` 日志真源。
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
    - `c1_live_collection_monitor.py`、`c1_canonicalize_exports.py`、`run_c1_raw_to_closeout_dryrun.py`、`c1_materialize_quality_table.py`、`c1_materialize_worker_state.py`、`c1_materialize_worker_profile_sidecar.py`、`c1_materialize_c2_gap_audits.py`、`build_c2_assignment_manifest_from_c1_gaps.py`、`materialize_p1_post_closeout_evidence_correction.py` 与 `materialize_p1_post_closeout_geometry_scores.py`：C1 live raw-data 采集健康监控、正式 export canonicalization、raw-to-closeout dryrun、quality/worker/profile/gap sidecar、reserve-only C2 draft，以及只读 P1 post-closeout evidence/geometry correction；只生成 provisional / audit artifacts，不冻结 C1/C2 协议参数。
    - `rebuild_stage1_chinese_completion_excel.py`：按最新 `标注人员.xlsx`、`退出标注.xlsx`、Stage 1 中文 LS JSON 导出和 active logs 重算中文 P1 完成情况工作簿。
  - `registry/`：registry、manifest、freeze、final-gold、trap/materialization、risk-rule、`d_t/g_t` dry-run、export inventory。
  - `data_prep/`：数据集准备和 MP3D smoke/import 生成。
  - `foreign_recruitment/`：P1/PreScreen 外国标注员 HTTPS 英文适配包。
- `tools/paper_b/`
  - Paper B 工具。当前包括 `validate_b0_relabel_audit.py`；后续 B0/B1/B2 训练、cue、bilayout、审计脚本只进本目录。
- `tools/label_studio/`
  - 三条线共享的 Label Studio XML、3D viewer、server/CORS、COS/upload、import/build helper 和 `official/`。
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
  - `THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md` 是 Paper A 写作/审计合同，配套 `.tex` 是最终 LaTeX 提纲载体；`THESIS_MANUSCRIPT_MIGRATION_MAP_v1.md` 记录旧 Overleaf section 到新章节的迁移关系。
  - `manuscript/` 可保存 Overleaf 项目和主线论文写作资产，但按现有 `.gitignore` 默认不提交。
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
- `active_logs/` 是原始 active-time 日志真源。
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
