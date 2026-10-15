# 参考重算后的描述统计快照（2026-10-16）

本快照承接[上一版人数门与难度v3统计](../descriptive_statistics_current_20261015/README.md)，将实际完成的完整参考评分纳入；源库存3152份/259图、至少3人来源规则、GT及既有排除均未改变。

完整质量共891份，新增84份；条件及真实覆盖如下。全局807旧质量保留，新增可计算覆盖不表示总体质量改善。2834份可分析来源记录不等于完整质量数。

|condition|records|images|workers|
|---|---|---|---|
|manual|828|73|24|
|semi|63|4|24|

普通难度的分条件描述统计如下；缺失不补0，类别间任务与人员组成不同，不据此声称因果差异或难度算法已验证。

|panel|difficulty_class|metric|n_valid|mean|median|sd|
|---|---|---|---|---|---|---|
|ordinary_manual|中等|WQ|114|45.34|39.95|20.79|
|ordinary_manual|中等|A10|114|49.42|45.83|21.58|
|ordinary_manual|中等|B8L2|114|52.78|49.93|20.88|
|ordinary_manual|中等|IoU3D100|114|72.59|76.04|17.01|
|ordinary_manual|困难|WQ|53|52.30|52.02|15.63|
|ordinary_manual|困难|A10|53|58.38|58.19|16.17|
|ordinary_manual|困难|B8L2|53|60.54|59.93|15.82|
|ordinary_manual|困难|IoU3D100|53|75.81|77.73|13.60|
|ordinary_manual|简单|WQ|661|65.27|66.18|19.37|
|ordinary_manual|简单|A10|661|70.34|73.55|18.60|
|ordinary_manual|简单|B8L2|661|72.24|75.55|17.77|
|ordinary_manual|简单|IoU3D100|661|80.56|84.42|13.44|
|ordinary_semi|中等|WQ|0|—|—|—|
|ordinary_semi|中等|A10|0|—|—|—|
|ordinary_semi|中等|B8L2|0|—|—|—|
|ordinary_semi|中等|IoU3D100|0|—|—|—|
|ordinary_semi|困难|WQ|0|—|—|—|
|ordinary_semi|困难|A10|0|—|—|—|
|ordinary_semi|困难|B8L2|0|—|—|—|
|ordinary_semi|困难|IoU3D100|0|—|—|—|
|ordinary_semi|简单|WQ|63|69.55|72.70|18.07|
|ordinary_semi|简单|A10|63|73.21|72.90|16.35|
|ordinary_semi|简单|B8L2|63|75.00|73.03|15.25|
|ordinary_semi|简单|IoU3D100|63|81.65|80.34|11.21|

## 查阅

- [当前工作簿](现有研究数据描述统计_重评分口径.xlsx)
- [关键科研图](figures/FIGURES.md)
- [41图506份逐项审计、参考构造与冻结重算](../../data/scope_quality_rescore_20261016/README.md)
- [后续新人、新数据及质量版本接入](../../data/scope_quality_rescore_20261016/EXTENSION_GUIDE.md)

完整明细与字段合同落在本目录；所有人员、建筑、同房、难度及算法对照均从新逐条数值重建。仅重算完整质量，没有把新评分回填为旧采集目标耗时，也没有重跑原融合实验。IoU3D仍是现用均高棱柱口径。

归档说明：逐表CSV、合同及交付工作簿入Git；重复聚合的`tables.json`仅留本地，可运行对应生成器重建后再生成工作簿。
