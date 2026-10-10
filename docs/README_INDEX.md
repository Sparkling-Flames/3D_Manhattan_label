# HOHONET 文档入口

- 用户复审后[11图范围待裁定](../analysis_results/image_difficulty_full_review_20261010/user_review_20261010/scope_review.html)与[3份人员作答排序台](../analysis_results/image_difficulty_full_review_20261010/user_review_20261010/order_workbench/index.html)：三份顺序已采用主数据（有效确认1312）；GT不改，范围裁定后再审难度。

- [质量范围：3张最小人工试审与24张对照](../analysis_results/quality_scope_human_review_20261010/README.md)

- 质量研究最新：[正式输入与边界](thesis_main/质量研究正式输入与待研究问题_20261010.md)、[Pro独立研究资料](../research/quality_scope_handoff_20261010/README.md)。14份点位审核已接入正式loader；共同小范围和非正交质量方案仍待研究。

- 259图全量难度/范围复核：[分层标准与字段合同](thesis_main/图片难度全量复核与分层标准_20261010.md)、[全量报告](../analysis_results/image_difficulty_full_review_20261010/REPORT.md)、[人工粗审页](../analysis_results/image_difficulty_full_review_20261010/review.html)。259图3152份台账；25张分歧已重审（10改简单、8保留、7待核），当前115/18/24/60/42视觉建议；13张范围优先候选，旧工作表保留，待用户裁定。

更新：2026-10-09。本页只列当前入口。逐阶段历史结果见[旧版研究与实验导航](thesis_main/history/研究与实验导航_旧版_20261009.md)；不从旧报告中的“下一步”推导当前任务。

## 当前研究

- [统一研究模型](thesis_main/研究模型_人员图片与融合不确定性_20261006.md)：研究问题、变量、现状和当前安排。
- [术语](thesis_main/CONTEXT.md)：统一概念和解释边界。
- [研究数据说明](thesis_main/研究数据说明_来源预处理与用途_20261006.md)：输入真源、预处理、人员与参考、补充证据及结果入口。
- 最新图片工作分类：[6点对低遮挡看图更新](../analysis_results/objective_difficulty_20261009/review_examples/SIX_PAIR_UPDATE_20261010.md)、[259图工作表](../analysis_results/objective_difficulty_20261009/review_examples/working_classification_20261010.csv)。6图改简单；特殊组继续单列；保留旧自动结构类与看图来源。
- 图片难度：[当前GT结构粗分类与辅助证据](thesis_main/图片客观难度评分_20261009.md)、[259图交付](../analysis_results/objective_difficulty_20261009/structure_classification/REPORT.md)、[旧d_model冻结补缺](../analysis_results/objective_difficulty_20261009/d_model_expansion/REPORT.md)。旧自动结构基线只用GT点对数／结构自遮挡，127简单／39中等／91困难／2暂停待定；OOS／门洞／可标性独立。此前[场景分层](../analysis_results/objective_difficulty_20261009/stratified/REPORT.md)、[同源模型](../analysis_results/objective_difficulty_20261009/model_comparison/REPORT.md)、[DINO](../analysis_results/objective_difficulty_20261009/dino_probe/REPORT.md)及[首轮实算](../analysis_results/objective_difficulty_20261009/REPORT.md)保留历史，12图核查为可选补充。
- 图片难度审图：[21图原图与GT点位图集](../analysis_results/objective_difficulty_20261009/review_examples/index.html)、[样例名单、旧评分口径及场景交叉表](../analysis_results/objective_difficulty_20261009/review_examples/README.md)。特殊场景单列；一致／不一致／未评分目的性示例，不作为盲法验证，不改主分类。 最新[评分复核与使用解释](../analysis_results/objective_difficulty_20261009/review_examples/SCORE_RECHECK.md)：门洞／OOS独立评分待定，x8-01参考待核。
- 图片难度外部审查：[讨论汇总与Pro深度研究任务](thesis_main/图片难度研究汇总与Pro深度研究任务_20261009.md)，包含旧d_model／风险分数澄清、既有证据、未定方案与可复制提示词；不替代规范或冻结分类。
- 图片结构条件：[GT循环环序与自遮挡核验](../analysis_results/gt_order_visibility_20261009/REPORT.md)，不使用人员主观难度或作答结果定义；既定GT、射线遮挡及原／修订版本分开。
- 墙线融合：[当前方法](thesis_main/共识投票机制与三路线推进_20261007.md)、[操作 SOP](thesis_main/融合共识操作SOP_20261008.md)和[唯一当前结果报告](../analysis_results/consensus_delivery_20261008/REPORT.md)。数量、例外和待办以结果报告为准。
- [完整研究交接](thesis_main/线程交接_连线质量与完整共识_20261004.md)：保留研究原意、历史证据和状态，不替代当前安排。

## 规范、分析与运营

- [机器可读方法合同](thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)是规范真源；[Markdown 摘要](thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.md)由它生成。
- [轮次执行 SOP](thesis_main/ROUND_BASED_ASSIGNMENT_SOP_v1.md)与[统计分析计划](thesis_main/STATISTICAL_ANALYSIS_PLAN_v1.md)按当前合同执行。
- 审核追溯：[二次复核 SOP](thesis_main/两人审核归并与二次复核SOP_20260925.md)及[GT 修正依据](thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md)。
- Label Studio 运营、分发、可见性或权限任务先读 [CE-only 运营 SOP](label_studio/LS_CE_ONLY_OPERATION_SOP_v1.md)。
- Paper A、Paper B 与共享工具的分类入口见[项目地图](PROJECT_MAP_CLEAN_20260308.md)。

## 数据入口

- 后续分析从[统一输入包 manifest](../analysis_results/research_input_20260929/manifest.json)读取；分析结果和审计不是输入真源。
- `export_label/` 是运行时标注真源，`import_json/` 是计划任务真源，`active_logs/` 是原始时间日志真源。
- 原始审核、配对、环序与评论记录由数据说明和统一包追溯；不从派生结果反写源数据。

## 历史资料

- [历史文档目录与旧版导航快照](thesis_main/history/README.md)：说明已归档材料，并链接整理前的完整索引和地图。
- 更早的 Paper A 与外部材料见 `docs/legacy/`、`analysis_results/legacy/` 和各 `research/` 归档入口；均不自动成为当前方法或待办。

## 109条点编辑复核（2026-10-09）

- [绿色工作台打开与操作说明](../analysis_results/point_edit_review_20261009/README.md)：复用空间标本界面；独立点编辑草稿、确认/暂缓和导入导出，未应用到正式点、GT或人员资格。
- [109份审核范围与返回核对](thesis_main/109份点编辑审核范围与返回核对_20261010.md)及[逐条CSV](../analysis_results/point_edit_review_20261009/109份审核范围与返回核对_20261010.csv)：解释为何只审14份／8图，区分18条导出中的历史范围记录与本轮结果。
- 易用性更新：原图旁常用按钮自动准备独立草稿，补点单次结束；留痕撤销和最近记录恢复。操作说明沿用上述绿色工作台入口。
- 当前工作台支持复用旧完整点对拖动排序，审核原话固定原图旁；“完成本条／完成并下一条”无需理由或勾选。
- 排序可见性修复：新草稿按周期x生成可撤销的点对候选；奇数点或越界点会显示未配对点及原因。操作与边界见上述入口。
- 2026-10-10重筛复核：109份中已排除人员W019／W026（清单代号P013／P016）共84份不计待审；源清单选25份，已有单条`invalid`5份、OOS保留但无法计算5份及OOS无有效点1份移出重复审核；默认待核验队列为14份／8图，原109份均可查旧草稿。新收到的18条审核返回与旧排序核对见上述工作台入口中的逐条机器审计。

当前规范版本：`consensus_research_20260923_v1`，机器合同为`PAPER_A_METHOD_CONTRACT_CURRENT.json`。
