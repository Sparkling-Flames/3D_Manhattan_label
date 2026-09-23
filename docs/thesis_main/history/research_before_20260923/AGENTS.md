# HOHONET Agent 上下文

## 项目概览

HOHONET 是半自动全景布局标注与分析仓库。

正式执行主线：

`Pilot -> PreScreen -> Calibration(C1 + C2-B + C2-A-RP) -> Main(T1 + V1)`

当前工作重点是 Label Studio 导入/导出、`active_time`、registry 拼接、分析脚本、round artifacts 和 audit evidence。

## 关键目录

- `tools/thesis_main/`：论文主线工具，包含分析、registry、freeze、risk-rule、final-gold、数据准备和 `foreign_recruitment/`。
- `tools/paper_a_manhattan/`：论文 A 线 Manhattan / sandbox / expert review / post-hoc audit-only 工具。
- `tools/paper_b/`：论文 B 线训练、审计、cue、bilayout 和 B0/B1/B2 相关工具。
- `tools/label_studio/`：三条线共享的 Label Studio 配置、viewer、server、COS/upload、import/build helper 和 `official/`。
- `docs/thesis_main/`：论文主线协议、SOP、统计计划、字段合同、PreScreen/Calibration/Main 说明和论文主线材料。
- `docs/paper_a_manhattan/`：论文 A 线 Manhattan 方案、sandbox、review、OOS audit 和 3D geometry 兼容说明。
- `docs/paper_b/`：论文 B 线模型、ZInD mapping、B-line freeze/audit 和支线研究说明。
- `docs/label_studio/`：Label Studio CE-only、active-time、云端部署、标注员/开发者说明。
- `docs/agent/`：Codex/agent 上下文、playbook 和写入规则。
- `docs/shared/`：论文模板、参考资料、共享写作资产。
- `docs/legacy/`：历史材料，默认不迁移、不更新。
- `import_json/`：planned import / planned split 真源。
- `export_label/`：Label Studio 运行时标注导出真源。
- `active_logs/`：原始 `active_time` 日志真源。
- `analysis_results/`：生成结果、审计、manifest 和图表落盘区。
- `tests/`：tools 与字段合同的 pytest 覆盖。
- `trap集/`：trap / manual 候选素材层。
- `data/`：数据资产。
- `output/`：HoHoNet 推理与中间产物。

## 真源层级

- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json` 是 Paper A 机器可读的唯一规范方法真源；
  `PAPER_A_METHOD_CONTRACT_CURRENT.md` 由该 JSON 渲染生成。
- `docs/thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md` 与
  `docs/thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md` 是执行和分析消费者，必须引用合同版本与 SHA，
  不得自行定义规范字段或正式 eligibility 语义。
- `docs/PROJECT_MAP_CLEAN_20260308.md` 是仓库地图；新增、删除、移动文件后必须检查是否需要同步。
- `docs/label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md` 与 `docs/label_studio/label studio注意事项.md` 约束 Label Studio CE-only 运营。
- `export_label/` 是运行时标注真源。
- `import_json/` 是 planned import / planned split 真源。
- `active_logs/` 是原始 `active_time` 来源。
- `analysis_results/` 是输出与审计落盘区，不是输入真源。
- 若 `tools/label_studio/create_labelstudio_split_by_outline.py` 含旧配额逻辑，不得用它覆盖已冻结协议或导入工件。
- 云服务器运行时 URL `/tools/vis_3d.html` 是部署路由兼容保留，不代表仓库源码仍位于 `tools/` 根目录。

## 写入规则

- `tools/` 根目录只保留入口索引和稳定包结构；新增 Python 脚本不得直接写入 `tools/` 根目录。
- 主线工具写入 `tools/thesis_main/analysis/`、`tools/thesis_main/registry/` 或 `tools/thesis_main/data_prep/`。
- 论文 A 线 Manhattan、sandbox、expert review、post-hoc audit-only 工具只写入 `tools/paper_a_manhattan/`。
- 论文 B 线 B0/B1/B2、训练、cue、bilayout、审计工具只写入 `tools/paper_b/`。
- 三条线共享的 Label Studio XML、viewer、server、COS/upload、official userscript 和 import helper 写入 `tools/label_studio/`。
- `docs/` 根目录只保留 `README_INDEX.md` 与 `PROJECT_MAP_CLEAN_20260308.md`；新增主题文档必须进入对应分类目录。
- 主线文档写入 `docs/thesis_main/`；论文 A 线写入 `docs/paper_a_manhattan/`；论文 B 线写入 `docs/paper_b/`；Label Studio/active-time/云端运行说明写入 `docs/label_studio/`；agent 规则写入 `docs/agent/`。
- 新增、删除或移动 `tools/`、`docs/` 文件后，同步检查 `docs/README_INDEX.md` 与 `docs/PROJECT_MAP_CLEAN_20260308.md`。
- 不移动或修改 `export_label/`，不改变 protocol、schema、routing、SOP 语义。

## 强制工作规则

- 修改前先运行 `git status --short`。
- 新增、删除、移动文件后检查 `docs/PROJECT_MAP_CLEAN_20260308.md`。
- 修改代码后运行相关测试。
- 修改 docs、SOP、字段合同或分析合同后检查是否与 protocol 冲突。
- 修改 analysis 输出字段、manifest 或 CSV schema 后补测试或字段合同。
- 不得静默忽略 schema drift、missing fields 或 active-time source mismatch。
- 涉及 Label Studio 运营、分发、可见性、权限或 GT 隔离时，先读 CE-only SOP。
- 默认使用简体中文回答；报告、交付说明和新增/修订文档也尽量使用中文，除非用户明确要求其它语言。

## Playbook 触发条件

- 修改 `tools/` 或 `tests/`：使用 `docs/agent/playbooks/code_change_verification.md`。
- 新增、删除或移动文件：使用 `docs/agent/playbooks/docs_sync.md`。
- 修改协议、轮次、RQ 解释、routing、admission、`w_max`、`r_u`、`tau_d`、Score、worker tier 或 Validation：使用 `docs/agent/playbooks/protocol_guard.md`。
- 修改统计、`active_time`、IAA、replay、bootstrap、permutation 或 MDE：使用 `docs/agent/playbooks/statistical_plan_guard.md`。
- 修改 Label Studio 运营、分发、可见性、assignment、权限或 GT 隔离：使用 `docs/agent/playbooks/label_studio_ce_guard.md`。
- 较大改动交付前：使用 `docs/agent/playbooks/handoff_summary.md`。

## 验证命令

只使用仓库中实际存在文件对应的命令：

- `pytest tests/test_analyze_quality.py`
- `pytest tests/test_build_c1_assignment_manifest.py`
- `pytest tests/test_compute_dt_score.py`
- `pytest tests/test_materialize_meta_label_consensus_summary.py`
- `pytest tests/test_init_task_risk_rule_manifest.py`
- `pytest tests/test_materialize_final_gold_records.py`
- `pytest tests/test_materialize_main_failure_outcomes.py`
- `pytest tests/test_c2_vfinal_design.py`
- `pytest tests/test_v1_policy.py`
- `pytest tests/test_materialize_vfinal_main_analysis.py`

纯文档修改可使用定向路径/引用检查：

- `git status --short`
- `rg -n "AGENT_CONTEXT_INDEX|agent/playbooks|STATISTICAL_ANALYSIS_PLAN|LS_CE_ONLY" AGENTS.md docs/README_INDEX.md docs/PROJECT_MAP_CLEAN_20260308.md docs/agent/AGENT_CONTEXT_INDEX.md docs/agent/playbooks`

## 完成定义

- diff 最小且范围明确。
- 协议边界未改变。
- 已运行并汇总相关测试或检查。
- 若文件结构变化，已检查 `PROJECT_MAP_CLEAN_20260308.md`。
- 未运行的测试已说明原因。
- handoff summary 说明改了什么、未改变的边界、验证结果、地图同步决策、剩余风险和下一步安全任务。
