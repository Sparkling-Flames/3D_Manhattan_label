# 资料与证据定位

本页只定位可核查来源，不把历史结果更新为本轮结果。仓库基准为42f7ea，正式输入为24360ad；摘要中的数字必须与对应版本配套。

## 当前输入与最新范围

| 内容 | 可直接打开的仓库入口 | 用途与限制 |
|---|---|---|
| 正式输入manifest | [manifest.json](../../analysis_results/research_input_20260929/manifest.json) | 按current loader物化当前审核层；旧基线JSON不是全部当前输入 |
| 当前加载器 | [materialize_current_research_input.py](../../tools/thesis_main/data_prep/materialize_current_research_input.py)、[consolidate_research_input.py](../../tools/thesis_main/data_prep/consolidate_research_input.py) | 读取当前点位、配对、环及正式gate |
| 14份审核层 | [quality_update_20261010.json](../../analysis_results/research_input_20260929/quality_update_20261010.json) | 原操作与解释保留；不自动恢复资格 |
| 最终范围总入口 | [35图包README](../quality_scope_review_complete_20261010/README.md)、[SUMMARY_FINAL.json](../quality_scope_review_complete_20261010/SUMMARY_FINAL.json) | 35确认、19新增、429作答、417底面valid、12不可算、0替代候选 |
| 最新确认 | [原始回执](../quality_scope_review_complete_20261010/data/raw_scope_receipt.json)、[规范确认层](../quality_scope_review_complete_20261010/data/normalized_confirmation_overlay.json) | 用户地面确认；不能推出顶界批准 |
| 参考绑定 | [reference_registry.json](../quality_scope_review_complete_20261010/data/reference_registry.json)、[source_bindings.json](../quality_scope_review_complete_20261010/data/source_bindings.json) | 每个范围的来源、父参考、准备度 |
| 最新BEV结果 | [record_metrics.csv](../quality_scope_review_complete_20261010/data/record_metrics.csv)、[BEV_REPORT.md](../quality_scope_review_complete_20261010/reports/BEV_REPORT.md) | 原GT、当前选定GT、确认地面三参考诊断；不是多候选完整Q |
| 无效和资格分层 | [12条不可算](../quality_scope_review_complete_20261010/data/noncalculable_12_records.csv)、[condition_gate_summary.csv](../quality_scope_review_complete_20261010/data/condition_gate_summary.csv) | 无效保留空值；BEV可算与正式资格分开 |
| 来源核验 | [bev_source_provenance.json](../quality_scope_review_complete_20261010/reports/bev_source_provenance.json) | 源代码、输入、LFS内容hash、当前loader一致性 |
| 本轮GT登记 | [GT_REFERENCE_EXCLUSIONS.md](GT_REFERENCE_EXCLUSIONS.md)、[机器登记](reference_exclusion_registry_20261010.json) | 按图像和具体参考版本连接，不依靠GT对象candidate状态 |

## 冻结质量代码与旧三图实验

- [quality_v11.py](../quality_scope_comparison_20261010/frozen_engine/core/quality_v11.py)：Q、D/F损失、4°/5°/2°/0.5及0.15参数；缺失值和几何可算性处理。
- [height_revision.py](../quality_scope_comparison_20261010/frozen_engine/height_revision/height_revision.py)：Hmean、Hlocal、Hstar实现。
- [strict_geometry.py](../quality_scope_comparison_20261010/frozen_engine/validity/strict_geometry.py)：几何有效性，不替代研究资格或GT真实性。
- [traditional_metrics.py](../quality_scope_comparison_20261010/frozen_engine/traditional/traditional_metrics.py)：角点均高与周长均高两种结果须分名。
- [三图README](../quality_scope_comparison_20261010/README_三图对照.md)、[comparison_18.csv](../quality_scope_comparison_20261010/results/comparison_18.csv)、[reference_metadata.json](../quality_scope_comparison_20261010/results/reference_metadata.json)：旧三图固定地面和条件顶界、18份同选16T/2G。原报告“下一批待确认”和旧分数只描述当时。
- [Pro返回独立核验](../../analysis_results/quality_scope_human_review_20261010/Pro返回独立核验_20261010.md)：非正交x8-09单图研究、目标接口守卫及局限，不是全库验证。

## 完整包内的yq-07固定GT诊断

在最新35图包恢复目录 `restored/quality_scope_review_complete_20261010/` 下查：

- `history/prior_stage_contents/order_score_recompute/README_复算结果.md`
- `history/prior_stage_contents/order_score_recompute/results/changed_three_scores.csv`
- `history/prior_stage_contents/order_score_recompute/results/complete_components.csv`
- `history/prior_stage_contents/order_score_recompute/results/full_old_new_results.json`
- `history/prior_stage_contents/order_score_recompute/results/source_provenance.json`
- `history/prior_stage_contents/order_score_recompute/recompute.py`

比较fae48e69旧输入与24360ad确认环，固定GT R02769、同一v1.1与采样。三份约77→65，边界扣分增加约11，方向改善、平坦略坏；六份均仍质量hold。包内“未上传GitHub”是原子包生成时历史说明，此材料已经随42f最终范围包归档。

## 旧全量质量研究及参数探索

由 [旧交接目录](../quality_scope_handoff_20261010/README.md) 恢复 `01_完整研究数值核心_20261009.zip`，解压后进入 `quality_research_20261009/`：

- `inputs/baseline/validation/prior_ablation/prior_ablation_summary.json`：旧3152份、2979可评、173不可评；只改0.15→0。实际扣分中位1.703946、P90 4.936319、最大8.832029。
- `inputs/baseline/validation/prior_ablation/prior_ablation_conclusion_zh.txt`：事后机制诊断，默认未替换、未选出赢家；涨分是去掉扣分的代数结果。
- `inputs/baseline/validation/prior_ablation/all_records_default_vs_no_prior.csv`：逐份默认与消融结果。
- `inputs/baseline/validation/expanded_nine_candidates_compact_summary.csv`：边界尺度3.5/4.0/4.5、高度尺度0.4/0.5/0.6的有限网格，全部标记未选为新默认。
- `inputs/baseline/validation/prior_ablation/comparison_with_existing_S_H_grid.csv`：消融与已有网格并列，不以改档数量选赢家。
- `historical_reports/全景布局质量评分_累计研究综合审查_20261009.txt`：历史综合材料，须结合最新输入、资格、GT登记与范围状态阅读。
- `reproduce/verify_package.py`、`reproduce/run_all.py`、`reproduce/复算说明.txt`：旧冻结结果复算。只复现旧输入，不把旧人数/NA/hold当当前结论。

更早的组合权重（包括G权重）也曾探索。本次不把它误记为现v1.1的0.15/0.30/0.45加重试验；后者尚未执行。若要引用更早权重探索的具体收益或数值，先定位该阶段原结果与公式，不在本交接中拼接不同版本的数字。

## 传统3D IoU的官方依据

- [HoHoNet eval_layout.py L65–101](https://github.com/sunset1995/HoHoNet/blob/master/eval_layout.py#L65-L101)：地面多边形交并面积和角点均高柱体。原代码有异常回退分支，研究表须额外保存异常标记，不将缺失冒充真实0分。
- [HoHoNet post_proc.py](https://github.com/sunset1995/HoHoNet/blob/master/lib/misc/post_proc.py)：高度重建及轴向墙面后处理；不能把模型后处理惯例未经说明地施加到人工输入上。

上述官方定义已于2026-10-10阅读核对。下一次复现实验应记录所使用官方文件的提交或内容hash，避免master移动造成版本不明。人工非平顶误差可能被均高掩盖，是由定义导出的待检验限制，不是对全体人工标注的实证结论。
