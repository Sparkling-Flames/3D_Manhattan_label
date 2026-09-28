# Agent 上下文入口

当前研究：`consensus_research_20260923_v1`。先读 `AGENTS.md`、`docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`、执行/统计 SOP，再按任务读取专题。历史 v23 合同固定为 `docs/thesis_main/PAPER_A_METHOD_CONTRACT_20260811_v23.json`，不可用当前 schema 解释旧阶段。

## 当前工作

- [当前方法摘要](../thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.md)、[执行 SOP](../thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md)、[统计计划](../thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)。
- [二次复核 SOP](../thesis_main/两人审核归并与二次复核SOP_20260925.md)、[全量台账](../../analysis_results/review_final_20260928/README.md)。
- [共享 x 预处理基线](../../analysis_results/shared_x_baseline_20260928/README.md)及相关输入禁止移动。预处理状态、资格与确认排列分别解释。
- [文档总索引](../README_INDEX.md)、[项目地图](../PROJECT_MAP_CLEAN_20260308.md)、[路径速查](REPO_PATH_MAP.md)、[写入规则](WRITE_RULES.md)。
- [CE-only 运营 SOP](../label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md)约束分发、可见性、权限和 GT 隔离。

## 按任务读取 playbook

- 代码与测试：[code_change_verification](playbooks/code_change_verification.md)。
- 文件结构与入口：[docs_sync](playbooks/docs_sync.md)。
- 方法、轮次与资格：[protocol_guard](playbooks/protocol_guard.md)。
- 统计、时间与重放：[statistical_plan_guard](playbooks/statistical_plan_guard.md)。
- Label Studio 运营：[label_studio_ce_guard](playbooks/label_studio_ce_guard.md)。
- 较大交付：[handoff_summary](playbooks/handoff_summary.md)。

## 历史与保护

- [旧文档归档](../legacy/paper_a_before_consensus_20260928/README.md)、[旧结果归档](../../analysis_results/legacy/research_cleanup_20260928/README.md)。历史材料供复算与回溯，不充当当前执行入口。
- `export_label/`、`import_json/`、`active_logs/` 和原始数据不移动、不改写；已有人工裁决不追改。
- 下游读取的历史分簇输入、人工原件和测试基线保留原路径；未知来源不凭版本日期清理。
- 开工核对 Git 状态；现有修改及新产物不纳入批量清理；本任务未提交或推送。
