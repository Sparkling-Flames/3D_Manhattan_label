# HOHONET 项目地图

更新：2026-09-28。规范版本 `consensus_research_20260923_v1`，唯一当前方法真源为 `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`。本地图只说明位置与用途，不定义方法、资格或阈值。

## 当前入口

| 用途 | 路径 |
|---|---|
| 当前规范、执行与统计 | `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`；`ROUND_BASED_ASSIGNMENT_SOP_v1.md`；`STATISTICAL_ANALYSIS_PLAN_v1.md` |
| 全量复核与资格台账 | `analysis_results/review_final_20260928/` |
| 续审与覆盖补审 | `analysis_results/review_continue_20260928/`；`review_coverage_followup_20260928/` |
| 确认修复交付 | `analysis_results/review_closeout_20260928/` |
| 全研究共享 x 输入 | `analysis_results/shared_x_baseline_20260928/`，本目录及其原始/复核/修复/GT输入链禁止移动 |
| 排序工作台与初筛 | `analysis_results/order_studio_20260926/`；`order_candidates_20260928/` |
| 共识研究包 | `analysis_results/consensus_research_20260923/` |
| 新 Pro 研究与独立审查 | `research/pro_layout_20260927/`；`analysis_results/pro_return_audit_20260928/` |

完整可点击入口见 [文档索引](README_INDEX.md)，历史材料集中见 [文档归档](legacy/paper_a_before_consensus_20260928/README.md) 和 [结果归档](../analysis_results/legacy/research_cleanup_20260928/README.md)。

## 真源与输入边界

- `export_label/`：运行时原始标注导出；禁止清理或移动。
- `import_json/`：planned import / planned split；禁止清理或移动。
- `active_logs/`：原始 active-time；禁止清理或移动。
- `data/`、`trap集/`、`output/`：数据、候选素材、推理资产；本次未清理。
- `analysis_results/`：通常为输出与审计，但有下游已读取的固定输入；不能因目录名为结果而整体删除。
- `docs/thesis_main/PAPER_A_METHOD_CONTRACT_20260811_v23.json`：历史机器合同，固定原路径、原字节。其他机器 JSON 配置同样保留。

## 代码与测试

- `tools/thesis_main/analysis/`：数值分析、共识、复核与展示；当前复核/预处理/排序主要为 `finalize_review_20260928.py`、`order_review_20260928.py` 及对应构建工具。
- `tools/thesis_main/registry/`：registry、freeze、risk-rule、final-gold 与历史阶段消费者。
- `tools/thesis_main/data_prep/`、`foreign_recruitment/`：数据准备与历史招募运营。
- `tools/paper_a_manhattan/`：Manhattan、sandbox、expert review 与 post-hoc audit-only。
- `tools/paper_b/`：训练、cue、bilayout、B0/B1/B2 与审计。
- `tools/label_studio/`、`official/`：共享 XML、viewer、server、上传与导入工具。
- `tests/`：合同和工具验证；历史测试所需输入仍保留原路径。
- `tools/` 根目录只保留入口索引与稳定包结构。

## 文档与历史

- `docs/thesis_main/`：当前合同、SOP、复核/GT依据、研究任务及仍使用的机器配置。
- `docs/paper_a_manhattan/`、`paper_b/`、`label_studio/`、`agent/`、`shared/`：对应主题资料。
- `docs/legacy/paper_a_before_consensus_20260928/`：旧字段合同与提纲、历史讨论、原 history/archive_20260918 和旧 T1/V1 Overleaf 工程，展开保留。
- `analysis_results/legacy/research_cleanup_20260928/`：封闭旧结果 ZIP 与已有压缩包，包含原路径成员及恢复说明。
- `analysis_results/repo_cleanup/research_cleanup_20260928/`：处理清单、路径映射、保留原因、验证与交付摘要。
- 更早的 `docs/legacy/`、`analysis_results/legacy/` 材料保留，不自动升级为当前入口。

## 工作规则

参见 [Agent 上下文](agent/AGENT_CONTEXT_INDEX.md)、[文档同步](agent/playbooks/docs_sync.md)、[代码验证](agent/playbooks/code_change_verification.md)。协议与统计变更须分别检查 protocol_guard 和 statistical_plan_guard。Label Studio 运营先读 CE-only SOP。部署兼容路由 `/tools/vis_3d.html` 不代表源码位于 tools 根目录。

- [2026-09-28研究交接：清洗与角点重排](thesis_main/研究交接_清洗与角点重排_20260928.md)：当前进度、用户意图、必读输入及后续未开展方向。
