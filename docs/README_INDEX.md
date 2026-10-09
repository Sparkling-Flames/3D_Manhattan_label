# HOHONET 文档入口

更新：2026-10-09。本页只列当前入口。逐阶段历史结果见[旧版研究与实验导航](thesis_main/history/研究与实验导航_旧版_20261009.md)；不从旧报告中的“下一步”推导当前任务。

## 当前研究

- [统一研究模型](thesis_main/研究模型_人员图片与融合不确定性_20261006.md)：研究问题、变量、现状和当前安排。
- [术语](thesis_main/CONTEXT.md)：统一概念和解释边界。
- [研究数据说明](thesis_main/研究数据说明_来源预处理与用途_20261006.md)：输入真源、预处理、人员与参考、补充证据及结果入口。
- 图片难度：[最新事实分层方案与12图试点](thesis_main/图片客观难度评分_20261009.md)、[场景独立分层](../analysis_results/objective_difficulty_20261009/stratified/REPORT.md)；[同源布局模型比较](../analysis_results/objective_difficulty_20261009/model_comparison/REPORT.md)、[DINOv3视觉两轴](../analysis_results/objective_difficulty_20261009/dino_probe/REPORT.md)及[首轮实算](../analysis_results/objective_difficulty_20261009/REPORT.md)保留历史。优先少量任务事实，不继续堆评分模型；OOS子类／门洞／可标性独立，未记录不认证正常。
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
