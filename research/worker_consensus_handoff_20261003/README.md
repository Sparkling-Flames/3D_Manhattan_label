# Chat Pro 深度研究交接：图片、人数与人员构成

2026-10-03。此目录只提供入口，不复制固定输入或再打重复包。仅本地提交，GitHub由用户同步后再交给Chat中的Pro；本地Codex没有调用Chat Pro。

## 先读这些材料

1. [当前方向与算法职责](../../docs/thesis_main/研究方向_空间差异与共识_20260930.md)及[推进台账](../../docs/thesis_main/研究推进台账_20261003.md)。规范以[当前合同](../../docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json)为准，历史研究包不规定当前前置任务。
2. [A线136图、最高24人数曲线](../../analysis_results/lee_expanded_20261003/REPORT.md)：固定人数窗口，难度缺失及失败整池保留；含固定输入、逐图/分组结果、完整排列与图表。
3. [B线共同24人×10图及4人构成](../../analysis_results/worker_profiles_20261003/REPORT.md)：画像、质心、建筑留出、参考/权重敏感性、10626集合/图精确构成，及GT无关成员区域差异。
4. [早期Pro与dot材料归档](../layout_methods_review_20261001/README.md)与[质量方法交接](../pro_quality_handoff_20261002/README.md)用于追溯；外部意见、当前报告及用户预期均不是应当证明的真理。

## 可复核工件

- [B线固定输入](../../analysis_results/worker_profiles_20261003/input.json)、[预选块](../../analysis_results/worker_profiles_20261003/block.json)、[来源绑定](../../analysis_results/worker_profiles_20261003/source_binding.json)。已预处理坐标、确认环与默认环均保留，不重新配对或重排。
- [逐答质量](../../analysis_results/worker_profiles_20261003/answer_metrics.csv)、[画像](../../analysis_results/worker_profiles_20261003/worker_profiles.csv)、[留出分组](../../analysis_results/worker_profiles_20261003/lobo_assignments.csv)、[λ敏感性](../../analysis_results/worker_profiles_20261003/weight_sensitivity.csv)。
- [逐图构成结果](../../analysis_results/worker_profiles_20261003/composition_exact.csv)、[分组摘要](../../analysis_results/worker_profiles_20261003/composition_summary.csv)、[全部子集结果](../../analysis_results/worker_profiles_20261003/subsets.npz)、[人员映射](../../analysis_results/worker_profiles_20261003/rosters.json)。
- [字段合同](../../analysis_results/worker_profiles_20261003/field_contract.json)、[本地验收](../../analysis_results/worker_profiles_20261003/acceptance.json)、[保留警告](../../analysis_results/worker_profiles_20261003/warnings.json)。
- [本轮脚本](../../tools/thesis_main/analysis/worker_profiles_20261003.py)复用[Lee核心](../../tools/thesis_main/analysis/lee_tile_stage1_20261002.py)与[精度/积分实现](../../tools/thesis_main/analysis/lee_tile_precision_20261003.py)。从仓库根运行报告中的固定输入重放命令即可；不需原图完成数值复核。

## 交接目标

请独立评估现有证据能否支持论文关于“图片困难、人员差异及人员组合如何影响共识”的叙事，辨别可靠结论、解释过度、算法或数据问题，并推进最有价值的深度分析。重点需要弄清人员区分是否可靠、质量分项是否提供必要而可解释的信息，以及共识接近参考与组合波动之间的关系。允许推翻现有解释，不追求显著差异或预期方向。

最后交回可复算的证据、修正后的结论、尚缺的信息和按价值排序的下一步目标。没有原图时不能宣称完成视觉审核；明确哪些问题必须由本地看图确认。

## 当前实质限制

共同块只有10图、8建筑，9图缺人工难度；λ敏感性不是效度验证；外建筑上下半是探索性相对分组，9人随留出折换组。4人精确构成不等于完整人数/构成曲线。GT修订同时可能影响校准和评价，已分开保存。区域对称差期望不是平均Jaccard，也不是增人稳定速度；低波动可以伴随偏离参考。相关测试23项通过，2条几何核验警告保留；完整运行没有原图视觉核验和独立外部样本验证。
