# HoHoNet 文档索引（当前执行版）

> 最后更新：2026-03-28

本索引只保留当前仍应视为正式入口或正式参考的文档。  
临时转交、讨论稿、旧阶段说明，统一归档到 `docs/legacy/`。

## 1. 当前最优先阅读

1. [ROUND_BASED_EXECUTION_PROTOCOL_v1.md](ROUND_BASED_EXECUTION_PROTOCOL_v1.md)
   - 当前 thesis-facing 的正式阶段/轮次合同。
   - 明确 `P1 / C1 / C2 / T1 / V1` 各轮允许更新、禁止更改与必须落盘的工件。

2. [ROUND_BASED_ASSIGNMENT_SOP_v1.md](ROUND_BASED_ASSIGNMENT_SOP_v1.md)
   - 当前按轮次执行的分发 SOP。
   - 用来把 round contract 落到实际导入、分配、补派与导出动作上。

3. [LS_CE_ONLY_OPERATION_SOP_v1.md](LS_CE_ONLY_OPERATION_SOP_v1.md)
   - 当前单实例、Community Edition、无代码改动前提下的 Label Studio 运营 SOP。
   - 明确 `P1 / C1 / C2 / T1 / V1` 应如何按项目切分运行，以及 GT 共实例但非共路径的边界。

4. [PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md](PRESCREEN_STAGE1_OPERATIONAL_GUIDE_20260327.md)
   - 当前 prescreen 正式运行手册。
   - 包含：正式文件清单、工具链边界、小型测试建议、运行流程。

5. [P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md](P1_PRESCREEN_LAUNCH_CHECKLIST_v1.md)
   - 当前 `P1` 启动前最直接的执行清单。
   - 用于导入 smoke test、active-log 检查、`tools/audit_active_log_quality.py` 审计、导出解析检查与正式启动判据。

6. [C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md](C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md)
   - 当前 line B 的 `C1/C2` 工件字段合同。
   - 把 `worker_state_snapshot_C1`、`scene_coverage_gap_C1`、`task_risk_rule_manifest_v1` 等文件收口为可直接填充的 schema。

7. [RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md](RQ3_MINIMAL_EVIDENCE_CHAIN_CONTRACT_v1.md)
   - 当前 `RQ3` 主证据链的最小数据合同。
   - 收口 `dt` 参考库摘要、meta-label consensus sidecar、offline replay config 与 task-risk manifest。

8. [STAGE3_OOD_PREPARATION_PLAN_v1.md](STAGE3_OOD_PREPARATION_PLAN_v1.md)
   - Stage 3 / Main-Validation / OOD-aware routing 的准备计划。
   - 明确 `d_t` / `g_t` / task-risk / `Validation_OOD` / Hard subset `H` / V1 audit schema 的 readiness、blocker 与 dry-run 边界。

9. [PROJECT_MAP_CLEAN_20260308.md](PROJECT_MAP_CLEAN_20260308.md)
   - 当前纯净仓库地图。
   - 用来确认哪些目录、脚本、结果仍属于主链。

10. [../analysis_results/README.md](../analysis_results/README.md)
   - `analysis_results/` 根目录整理说明。
   - 用于快速区分当前主链结果目录、历史保留目录与 `legacy/` 归档区。

11. [SOP_labelstudio_experiment.md](SOP_labelstudio_experiment.md)
   - Label Studio 导入、标注、导出的一般操作 SOP。
   - 使用时应以当前 Stage 1 正式导入文件和冻结结果为准，不要反向覆盖最新 freeze。

12. [README_DEVELOPER.md](README_DEVELOPER.md)
   - 部署、日志、服务、分析工具链的开发者入口。

13. [ANALYSIS_DATA_FLOW.md](ANALYSIS_DATA_FLOW.md)
   - 上游导出、active log、quality CSV、reliability 输出之间的数据流说明。

14. [手动分析流程.md](手动分析流程.md)
   - 你自己拿到一批数据后，手动跑 Pilot / PreScreen 的分析、审计、可视化和测试的流程说明。

15. [STATISTICAL_ANALYSIS_PLAN_v1.md](STATISTICAL_ANALYSIS_PLAN_v1.md)
   - 当前与论文提纲、round-based protocol 对齐的统计计划。
   - 只收口 `RQ1 / RQ2 / RQ3` 的统计口径、downgrade 规则与解释合同，不改主协议边界。

16. [../AGENTS.md](../AGENTS.md)
   - Codex 仓库级常驻上下文入口。
   - 只记录 source-of-truth、CE-only 边界、workflow rules 与验证入口。

17. [AGENT_CONTEXT_INDEX.md](AGENT_CONTEXT_INDEX.md)
   - Codex 上下文路由表。
   - 按 `P1 / C1-C2 / RQ1 / RQ2 / RQ3 / Label Studio / repo map` 指向先读文件。

18. [agent_playbooks/](agent_playbooks/)
   - Codex 狭义工作流 playbook。
   - 覆盖代码验证、文档同步、协议保护、统计计划保护、Label Studio CE 保护与 handoff。

## 2. Prescreen / Stage 1 正式参考

- [label studio注意事项.md](label studio注意事项.md)
- [prescreen_freeze_note_v1.md](prescreen_freeze_note_v1.md)
- [prescreen_oos_scoring_note_v1.md](prescreen_oos_scoring_note_v1.md)
- [final_gold_rebinding_contract_v1.md](final_gold_rebinding_contract_v1.md)
- [appendix_a_operator_freeze_note_v1.md](appendix_a_operator_freeze_note_v1.md)
- [实验集设定与用途.md](实验集设定与用途.md)

## 3. 提纲与一致性审计

- `docs/overleaf_project/sections/01_研究问题.tex`
- `docs/overleaf_project/sections/02_方法.tex`
- `docs/overleaf_project/sections/03_实验设置.tex`
- `docs/overleaf_project/sections/04_报告与可审计输出.tex`
- `docs/overleaf_project/sections/A1_扰动算子库.tex`
- `docs/overleaf_project/sections/A2_数据集汇总表.tex`
- [提纲一致性审计_20260313.md](提纲一致性审计_20260313.md)

## 4. 约束与工具实现边界

- `约束/README.md`
- `约束/A_约束清单.md`
- `约束/merged_all.md`
- `约束/visualize_output_v2.md`
- `约束/perturbation_operators.md`
- `约束/compute_dt_score约束规范.md`
- `约束/compute_spammer_score约束规范.md`
- `约束/difficulty_split约束规范.md`
- `约束/offline_replay约束规范.md`

说明：

- 这些约束是正式协议来源之一。
- 但其中部分工具在当前仓库里仍未 materialize 为正式脚本，必须结合当前实现状态使用。
- 对导入分池类旧脚本也应做同样处理：若 `tools/create_labelstudio_split_by_outline.py` 与当前 freeze/import 口径冲突，以已冻结导入文件和 round-based 文档为准。

## 5. 测试与审计

- [TEST_PLAN_AND_REVIEW.md](TEST_PLAN_AND_REVIEW.md)
- [B_FREEZE_V2_1_CONTRACT_AUDIT_20260317.md](B_FREEZE_V2_1_CONTRACT_AUDIT_20260317.md)
- [B_SELECTION_FREEZE_RERUN_20260317.md](B_SELECTION_FREEZE_RERUN_20260317.md)
- [PHASE1_PROGRESS_AUDIT_20260311.md](PHASE1_PROGRESS_AUDIT_20260311.md)

## 6. Legacy 归档

以下类型内容已或应归档到 `docs/legacy/`：

- 临时转交文件
- 暂存文本
- 已过时阶段草案
- 不再承担当前执行入口职责的旧说明

如需追溯历史判断，再进入 `docs/legacy/` 查看。
