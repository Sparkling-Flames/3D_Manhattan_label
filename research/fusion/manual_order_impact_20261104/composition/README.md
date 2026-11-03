# 完整有限配比人工辅助敏感性补算

主报告：[REPORT_ZH.md](REPORT_ZH.md)。逐条结论：[CONCLUSIONS.csv](CONCLUSIONS.csv)。

只更新2端点所在的2个有限面板（35+10队），固定11种现有标签与method_known/shared_known支持。原其它65面板统计复用后，按原panel→pool→image→building计权重新汇总。没有分类训练、重新选型、添加团队或新的融合计算。

- `affected_inputs/`：精确2面板、45队的固定设计及原/辅助端点标量。
- `replay/automatic/`：复现的原2面板输出，必须与冻结结果逐项对齐。
- `replay/assisted_expanded/`：扩展可评支持下的2面板输出。
- `replay/assisted_original_support/`：逐指标遮罩到原有限值支持的敏感性对照，形成指标单独允许变化。
- `AFFECTED_PANEL_VARIANCE.csv.gz`：受影响面板各质量/几何/形成/劳动指标的方差分解。
- `AFFECTED_CONFIGURATION_COUNTS.csv.gz` / `AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz`：同配比的原、新可评队数、失败、完整成员穷举、分位数和成员波动。
- `ALL_PANEL_VARIANCE.csv.gz` / `ALL_METHOD_COMPARISON.csv`：原67面板的各版本全表与按原层级的宏统计。
- `DESIGN_INVARIANTS.csv`、`CHECKS.json`、`INPUT_MANIFEST.json`：固定标签/成员/时间、原基线parity和来源版本散列。

运行 `python -m tools.thesis_main.analysis.evaluate_manual_order_composition_20261104` 复现。原自动数据不覆盖；原缺失Q不能按0分计收益；人工排序未计时；2队属于57个定向案例，不能推广为所有无环结果的修复率。
