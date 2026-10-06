# HOHONET 项目地图

2026-10-06发布交接入口：[Pro对应替代与上下目标分离任务](../research/point_route_review_20261006/README.md)；具体历史段落的“未提交”记录保留，当前发布范围以此入口及Git清单为准。

更新：2026-10-03。规范版本 `consensus_research_20260923_v1`，唯一当前方法真源为 `docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json`。本地图只说明位置与用途，不定义方法、资格或阈值。

## 当前入口

- [新增八图阈值扩展](../analysis_results/point_threshold_expanded_20261006/REPORT.md)：复用`point_threshold_sweep_20261006.py --expanded`，固定名单见输出PLAN；不改正式阈值合同。该入口的`--count-shortfalls`生成[137图点数与人数诊断](../analysis_results/point_threshold_expanded_20261006/PAIR_COUNT_REPORT.md)，保留原始MV、点数条件单列。
- [Pro结构约束main交接](../research/structure_constraints_20261006/README.md)：本目录保存9图150份作答、原图及108基线，代码直接使用仓库；无需ZIP。`tools/thesis_main/analysis/structure_paths_local_review_20261006.py --stage current`复算基线。
- [连续路径原件与本地核验](../research/structure_paths_20261006/README.md)：Pro/dot原件按研究资料保留，`analysis_results/structure_paths_review_20261006/`保存本地重放与解释；上述工具的`events`、`compare`模式用于定向核验，不是正式融合实现。

- [较宽阈值全员融合](../analysis_results/point_threshold_sweep_20261006/REPORT.md)：入口`tools/thesis_main/analysis/point_threshold_sweep_20261006.py`复用现有四路线，默认9°，三栏比较5°/9°/12°；阶段性工作值，非正式合同参数。

- [即时邻点与阈值敏感性检验](../analysis_results/point_context_probe_20261006/REPORT.md)：工具`tools/thesis_main/analysis/point_context_probe_20261006.py`、测试`tests/test_point_context_probe_20261006.py`及计划`research/point_context_probe_20261006/PLAN.md`；开发诊断，不改融合。

- [四图点融合路线与阈值探索](../analysis_results/point_route_panel_20261005/REPORT.md)：独立探索工具`point_route_panel_20261005.py`与`point_route_panel_view_20261005.py`；绑定、上下锚定及独立对应小面板，阈值未校准，新环未确认。
- [点路线修订与原图核验](../analysis_results/point_route_review_20261006/REPORT.md)：独立探索工具`point_route_review_20261006.py`与`point_route_review_view_20261006.py`；[人工核验页](../analysis_results/point_route_review_20261006/review.html)、[方法对照页](../analysis_results/point_route_review_20261006/index.html)，完整源身份环备选与未决端点保留，5°仅演示。
- [人工判断真源](../research/point_route_review_20261006/human_review.json)：保留原话与纠错；analysis_results仅为发布副本。现有点路线工具`--stage audit`可重生对应审计，独立探索，目标政策未定。

- [有限局部路径返回审查与修复](../analysis_results/local_path_review_20261005/REPORT.md)：原件在`research/local_path_research_20261005/`；本地工具`finite_local_paths_20261005.py`与`review_local_path_research_20261005.py`，仅补全候选依据，不接自动删点。
- [Lee底边表示与用途验收](../analysis_results/lee_boundary_usability_20261005/REPORT.md)：已有区域及底点摘录、回投数值与UI核验；显示改动在`consensus_result_studio_20261004.js`，不改Lee投票。
- [局部跨接证据与Pro并行交接](../research/local_shortcut_handoff_20261005/README.md)：`local_shortcut_projection_20261005.py`和`local_shortcut_figures_20261005.py`；结果在`analysis_results/local_shortcut_projection_20261005/`及`local_shortcut_evidence_20261005/`，含51操作回投、两图证据、dot复核和有限候选深研资料。
- [共识可靠性修复与空间候选执行](../research/layout_reliability_20261005/README.md)：原件精选归档、本地修复模块`tools/thesis_main/analysis/layout_reliability_20261005/`，定向复算及单点对删除入口；结果分别在`analysis_results/layout_reliability_fixed_20261005/`与`local_structure_deletion_20261005/`。

- [10月5日Pro共识可靠性返回独立审查](../analysis_results/layout_reliability_review_20261005/REPORT.md)：源绑定、包络与来源缺陷、排序补查及减法候选下一步；外部原件和运行算法未改。
- [共识可靠性后续方案与Pro深研资料](thesis_main/研究推进方案_共识可靠性与Pro深研_20261004.md)：本阶段完成条件、研究问题与创新边界；[交接包](../research/layout_foundations_handoff_20261004/README.md)含最新Pro／dot原件及四图66份完整当前名单，GT分离；只交接资料，未新增融合实验。
- [下一线程完整交接：连线、质量与完整共识](thesis_main/线程交接_连线质量与完整共识_20261004.md)：最新优先级、跨线程证据、算法与数据入口、已知缺陷、Pro分工、未提交边界及具体接续任务。
- [人员子类与完整共识返回审查](../analysis_results/worker_subtype_review_20261004/REPORT.md)、[Pro／dot精选归档](../research/worker_subtype_returns_20261004/README.md)：数值复核、认证反例和点身份并列提示；当前优先回到连线、质量与共识基础，跨线程进度和后续安排统一见研究方向。
- [人审来源到分析输入核查](../analysis_results/review_source_audit_20261004/REPORT.md)：后审traits与明确原话难度消费修复，`corrected_inventory/`为当前盘点，`pipeline/`为只读绑定审查；旧研究数值保留，难度分组需重新汇总。
- [完整共识并行研究交接](../research/full_layout_consensus_handoff_20261003/README.md)：复用现有固定输入、历史人工审核及代码，不复制重复包；本地与Chat Pro分工、汇合交付和目标提示词。
- [全员点对融合137图基础研究](../analysis_results/global_pair_consensus_20261004/REPORT.md)：全员跨点数、三阈值两规则、来源与连接诊断；`global_pair_consensus_20261004.py` 与 `global_pair_study_20261004.py`，默认工作台已接全员结果。
- [完整layout Pro返回独立审查](../research/full_layout_pro_review_20261004/REVIEW.md)：精简原包、384状态独立复算、来源绑定、认证对应不一致反例；源码仅作研究参考。

- [同房相似性](../analysis_results/same_room_similarity_20261003/REPORT.md)与[Lee真实数据demo](../analysis_results/lee_consensus_demos_20261003/index.html)：新工具分别为 `tools/thesis_main/analysis/same_room_similarity_20261003.py`、`lee_consensus_demos_20261003.py`；[人员粗分类溯源](thesis_main/人员粗分类原意与既有证据_20261003.md)补足Q/T/S/B及具名子类收敛的历史与当前职责。
- [点投票与区域投票溯源](thesis_main/点投票与区域投票_方法溯源_20261003.md)：[融合demo](../analysis_results/lee_consensus_demos_20261003/index.html)的整份标法分组与上下点中心候选由 `tools/thesis_main/analysis/point_pattern_demo_20261003.py` 提供；直接ERP上下区域轮廓由 `erp_region_demo_20261003.py` 提供，均为探索模块，Lee-BEV旧结果保留。新增[融合结果工作台](../analysis_results/consensus_result_studio_20261004/index.html)，构建器及展示适配为 `consensus_result_studio_20261004.py/js/css`，复用 Panorama Studio，仅重组四图全员结果的展示。

- [人员研究返回的本地审查](../analysis_results/worker_review_20261003/REPORT.md)、[前三轮Pro／dot精选归档](../research/consensus_reviews_20261003/README.md)：工具 `tools/thesis_main/analysis/audit_worker_returns_20261003.py`；保留连续画像、等权融合及重复坐标独立票，下一步画像迁移与人数×构成。

| 用途 | 路径 |
|---|---|
| Pro 方法与 dot 审核资料 | `research/layout_methods_review_20261001/`：精选外部报告、源码、结果及反例，非正式算法入口 |
| 当前研究方向 | `docs/thesis_main/研究方向_空间差异与共识_20260930.md`：BEV表示、质量评价与Lee融合；136图扩展及共同人员画像／固定4人构成基础已完成，接续深度研究 |
| 连线与表示阶段1 | `docs/thesis_main/布局表示地基与坐标核验_20260930.md`；工具 `tools/thesis_main/analysis/layout_foundation_20260930.py`；全量表示清点 `analysis_results/layout_foundation_20260930/`，不修改资格或选择权重 |
| 阶段2小型指标响应 | `tools/thesis_main/analysis/layout_metric_response_20261001.py`；`analysis_results/layout_metric_response_20261001/REPORT.md`及机器结果/字段合同/固定计划；74合成对照与12图描述，非全量研究或方法定案 |
| 排序后3D质量增量 | `tools/thesis_main/analysis/layout_3d_quality_probe_20261002.py`；`analysis_results/layout_3d_quality_probe_20261002/REPORT.md`；12图全部作答和17份改序，墙高/方向/水平顶面模型体积诊断，不改变资格或正式评分 |
| 阶段2最小当前快照 | `research/pro_layout_metric_response_20261001/`；独立入口 `tools/thesis_main/analysis/verify_layout_metric_snapshot_20261001.py`；只复算嵌入74+15，保留9条参考缺失，不重建上游或覆盖历史包 |
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

2026-10-03清理：活动目录 `.agents/skills/paper-a-c2-operator/` 的SKILL与UI元数据已移除，历史可从Git恢复；离线BEV与GT分析不触发旧C2运营。文档入口统一到现行A/B研究顺序，历史数据和结果路径保留。

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

- [扩图与高人数分析（2026-10-03）](../analysis_results/lee_expanded_20261003/REPORT.md)：136图1496份独立票，逐图最多24人；固定窗口与失败整池保留，工具 `tools/thesis_main/analysis/lee_expanded_20261003.py`。

- [共同人员画像与固定4人构成（2026-10-03）](../analysis_results/worker_profiles_20261003/REPORT.md)：24人×10图、整栋留出、IoU/质心及每图10626集合精算；[Chat Pro交接](../research/worker_consensus_handoff_20261003/README.md)，工具 `tools/thesis_main/analysis/worker_profiles_20261003.py`。
