# HOHONET 项目地图

更新：2026-09-28。规范版本 `consensus_research_20260923_v1`，唯一当前方法真源为 `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`。本地图只说明位置与用途，不定义方法、资格或阈值。

## 当前入口

| 用途 | 路径 |
|---|---|
| 当前研究方向 | `docs/thesis_main/研究方向_空间差异与共识_20260930.md`：表示优先，空间差异、分簇、融合、合理候选分开；合同同步说明 |
| 连线与表示阶段1 | `docs/thesis_main/布局表示地基与坐标核验_20260930.md`；工具 `tools/thesis_main/analysis/layout_foundation_20260930.py`；全量表示清点 `analysis_results/layout_foundation_20260930/`，不修改资格或选择权重 |
| 当前规范、执行与统计 | `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`；`ROUND_BASED_ASSIGNMENT_SOP_v1.md`；`STATISTICAL_ANALYSIS_PLAN_v1.md` |
| 最终研究输入 | `analysis_results/research_input_20260929/manifest.json` 为统一入口；完整生成/读取 `tools/thesis_main/data_prep/consolidate_research_input.py`，坐标组件生成 `materialize_current_research_input.py`；说明 `docs/thesis_main/最终审核数据接入_20260929.md` |
| 全量复核与资格台账 | `analysis_results/review_final_20260928/` |
| 研究解释与交叉机器表 | `analysis_results/review_research_tables_20260929/`；生成器 `tools/thesis_main/analysis/build_review_research_tables_20260929.py`，不新增裁决 |
| 全批次评论机器表 | `analysis_results/review_comments_20260929/`；生成器 `tools/thesis_main/analysis/build_review_comment_table_20260929.py`，原文与来源出现记录分开 |
| 续审与覆盖补审 | `analysis_results/review_continue_20260928/`；`review_coverage_followup_20260928/` |
| 确认修复交付 | `analysis_results/review_closeout_20260928/` |
| 历史共享 x 快照 | `analysis_results/shared_x_baseline_20260928/`，本目录及其原始/复核/修复/GT输入链禁止移动 |
| 排序工作台与初筛 | `analysis_results/order_studio_20260926/`；`order_candidates_20260928/` |
| 双人排序接收与同房扩展复核 | `analysis_results/order_same_room_review_20260928/`，114图独立复审层 |
| 共识研究包 | `analysis_results/consensus_research_20260923/` |
| 9/29 全量数值探索与 Pro 交接 | `research/pro_layout_20260929/`；本地结果 `analysis_results/research_round_20260929/`；工具 `tools/thesis_main/analysis/research_round_20260929.py` |
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

- [原始GT主筛顺序复核](../analysis_results/order_gt_screened_20260928/index.html)：本轮已接收1160份确认，1份配对问题；历史队列保留。
- [本轮审核接收与改序规律补查](../analysis_results/order_pattern_recall_20260929/README.md)：77份候选、24图；接收与研究工具位于tools/thesis_main/analysis/receive_order_results_20260929.py及order_pattern_recall_20260929.py。
- [独立顺序续审](../analysis_results/order_followup_20260929/README.md)：77份待检查对象；由接收器生成，配对汇总及同房Matterport当前快照位于order_pattern_recall_20260929。
- [77份接收与预标注证据](../analysis_results/order_model_same_image_20260929/README.md)：工具receive_followup_model_audit_20260929.py；最新同房确认快照1237份，配对33份；order_same_image_followup_20260929为35份当前续审。
- [排序闭合审计](../analysis_results/order_completion_audit_20260929/README.md)：audit_order_completion_20260929.py重新核对259图3152份及全部已接收批次；最新确认1272份，顺序候选0，下一阶段34份配对/表示核查。
- [34份配对审核](../analysis_results/pairing_review_20260929/README.md)：build_pairing_review_20260929.py及pairing_review_20260929.html/js；平均x前坐标只读，配对集合独立保存，不确认排序。
- [全量x配对审计](../analysis_results/x_pairing_audit_20260929/README.md)：audit_x_pairing_20260929.py；34份接收、3152份历史/原始验证及默认x配对候选，原数据未应用修改。
- [2026-09-28研究交接：清洗与角点重排](thesis_main/研究交接_清洗与角点重排_20260928.md)：当前进度、用户意图、必读输入及后续未开展方向。
- [当前15份补齐配对复核](../analysis_results/pairing_completion_review_20260929/index.html)：6份角色限制、6份x补齐、3份删点预览；完整配对独立确认，暂不排序。生成器build_pairing_completion_review_20260929.py复用配对界面。
- [当前配对后排序：23份、18图](../analysis_results/order_after_pairing_20260929/index.html)：apply_pairing_preprocessing_20260929.py接收15份，原导出坐标直接共享x；[新预处理基线及去向](../analysis_results/pairing_applied_20260929/README.md)，1272份历史连接环沿用。
- [最终审核统计与同房分类](../analysis_results/final_review_summary_20260929/index.html)：final_review_summary_20260929.py；1295份确认、3152份闭合台账、同房原260组与候选259组、OOS/门洞、空间/细节评语分层收集及Matterport数据包。

- [Pro质量方法研究交接（2026-10-02）](../research/pro_quality_handoff_20261002/README.md)：独立源码、嵌入数据、复算入口和最新研究目标；配套[Pro/dot归档](../research/layout_methods_review_20261001/README.md)。
- [Lee tile第一阶段（2026-10-02）](../research/lee_tile_stage1_20261002/README.md)：固定BEV等权投票，12图人数重放、资格覆盖与数值诊断；工具 `tools/thesis_main/analysis/lee_tile_stage1_20261002.py`，结果 `analysis_results/lee_tile_stage1_20261002/`。
- [两线研究推进台账（2026-10-03）](thesis_main/研究推进台账_20261003.md)：已完成分析、A线粗难度与曲线、B线人员类型与组合；[参考均值精度补强](../research/lee_tile_precision_20261003/README.md)及独立审查数值证据，工具 `tools/thesis_main/analysis/lee_tile_precision_20261003.py`。
- [S2全量可比面板盘点（2026-10-03）](../analysis_results/research_panel_inventory_20261003/REPORT.md)：259图难度/资格/方法失败、人员共同覆盖；预选A线45图与B线24人×10图。工具 `tools/thesis_main/analysis/research_panel_inventory_20261003.py`，不新增资格或人员类型。
- [S3-A粗难度与人数曲线（2026-10-03）](../analysis_results/lee_difficulty_20261003/REPORT.md)：固定45图、1—8人、752个参考均值；质量水平与增益、去困难/同建筑对照、面积诊断和双参考配对。工具 `tools/thesis_main/analysis/lee_difficulty_20261003.py`，不宣称独立难度效应或稳定人数。
