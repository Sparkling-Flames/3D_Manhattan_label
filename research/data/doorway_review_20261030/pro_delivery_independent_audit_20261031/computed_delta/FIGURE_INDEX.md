# 门洞修正图：英文论文导出

## Consensus quality across team sizes before and after scope correction for eight affected doorway pools using MV50

[300 dpi PNG](CHANGED_POOL_CURVES.png) · [矢量PDF](CHANGED_POOL_CURVES.pdf) · [矢量SVG](CHANGED_POOL_CURVES.svg) · [逐点数据](CHANGED_POOL_CURVES_DATA.csv)

**Caption.** Mean B8L2 among scoreable outputs across team sizes for eight affected doorway pools. Gray dashed curves show the original Pro delivery and teal solid curves show the corrected scope assignments; different line styles preserve distinction in grayscale. Each panel identifies the image, target pool, and corrected pool capacity N. Means retain the frequencies of 256 natural annotation orders, rather than weighting unique teams equally. The isolated k=1 point describes individual annotations; k=2 is omitted from these main curves and no line bridges it. Missing scores remain missing, and zero corrected support produces no corrected curve. The one-person pool is descriptive only. All panels use the same 0–100 quality scale. Changes in pool membership and capacity accompany the scope corrections; these are not pure effects of increasing team size or changing a reference. No confidence interval is shown; path-resampling intervals are supplied separately and do not represent across-building uncertainty.

数据来源：原版DOORWAY_02包的`stage05_results/POOL_K_METRICS.csv.gz`，metric=B8L2、estimator=natural256_MC、非敏感性池；修正版`CORRECTED_NATURAL_CURVES.csv`，metric=B8L2；均仅选`CHANGED_POOLS.json`中的8池。两版各自按pool_id/k唯一关联，不更改数字。CHANGED_POOL_CURVES_DATA.csv保留k=2用于追溯，但图中不画。

复现：`python -X utf8 -m tools.thesis_main.analysis.report_doorway_delta_20261031 --figures-only`。仅读既有汇总、重绘与导出，不重做融合、评分或bootstrap。原版输入仍依赖既有ZIP；输出图及逐点表可独立查看。
