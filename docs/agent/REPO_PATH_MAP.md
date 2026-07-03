# HOHONET 全局路径速查地图

本文用于快速判断“某类文件应去哪里找、应写到哪里”。它不是 protocol，也不替代 `docs/PROJECT_MAP_CLEAN_20260308.md` 的目录边界说明。

## 根目录真源

- `import_json/`：Label Studio planned import / planned split 真源。
- `export_label/`：Label Studio 运行时导出真源；只读输入，不作为脚本写入目标。
- `active_logs/`：active-time 原始日志真源。
- `analysis_results/`：分析输出、审计、manifest、图表和中间产物；不是输入真源。
- `tests/`：pytest 覆盖和字段合同回归测试。
- `data/`：数据资产。
- `output/`：HoHoNet 推理和中间产物。
- `trap集/`：trap / manual 候选素材层。

## 主线 Thesis Main

- `docs/thesis_main/`：正式执行协议、SOP、统计计划、字段合同、PreScreen、Calibration、Main(Test + Validation)、论文主线材料。
- `docs/thesis_main/manuscript/`：论文主线写作资产和 Overleaf 项目。
- `tools/thesis_main/analysis/`：质量分析、active-time audit、stage-aware 分析、统计汇总、图表。
- `tools/thesis_main/analysis/quality_core/`：分析核心 helper，例如 active-time loader。
- `tools/thesis_main/registry/`：registry、assignment manifest、freeze、final-gold、risk-rule、`d_t/g_t` 相关工具。
- `tools/thesis_main/data_prep/`：数据准备、import 生成、dataset helper。
- `tools/thesis_main/foreign_recruitment/`：外国标注员 HTTPS 英文适配包和说明。

## Label Studio 共享运行层

- `docs/label_studio/`：CE-only SOP、active-time、云端部署、COS、标注员/开发者说明。
- `tools/label_studio/`：共享 Label Studio XML、3D viewer、server/CORS、COS/upload、import/build helper。
- `tools/label_studio/official/`：正式中文 annotator userscript。
- 云端兼容 URL `/tools/vis_3d.html` 是部署路由，不代表源码仍在 `tools/` 根目录。

## Paper A / Manhattan

- `docs/paper_a_manhattan/`：Manhattan 方案、sandbox、expert review、OOS audit、3D geometry 兼容和 HRC contract。
- `tools/paper_a_manhattan/`：Manhattan、sandbox、expert review、post-hoc audit-only 工具。
- `tools/paper_a_manhattan/dev_only/`：Manhattan sandbox userscripts。

## Paper B

- `docs/paper_b/`：Paper B 模型、ZInD mapping、B-line freeze/audit、训练计划。
- `tools/paper_b/`：B0/B1/B2、训练、cue、bilayout 和模型审计工具。

## Agent / Repo 管理

- `AGENTS.md`：仓库级 agent 工作入口。
- `docs/agent/AGENT_CONTEXT_INDEX.md`：按任务链路定位应先读的上下文。
- `docs/agent/WRITE_RULES.md`：tools/docs 写入边界。
- `docs/agent/playbooks/`：代码、文档、协议、统计、Label Studio 变更的检查流程。
- `docs/agent/REPO_PATH_MAP.md`：本文，路径速查地图。
- `docs/README_INDEX.md`：docs 总索引。
- `docs/PROJECT_MAP_CLEAN_20260308.md`：项目地图和目录边界。

## 默认不动

- `docs/legacy/`、`tools/legacy/`、`tools/legacy_server/`、`tools/backups/`：历史或备份材料，默认不迁移、不修订。
- `analysis_results/` 下历史分析产物：除非任务明确要求，不作为输入真源改写。
- `export_label/`：运行时导出真源，不移动、不重命名。
