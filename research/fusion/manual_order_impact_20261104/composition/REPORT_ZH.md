# 人工辅助顺序对完整有限配比的影响

只对已有的2个其它目标Manual面板补入2个固定节点人工顺序端点；35队与10队的成员全集、类别标签、参考和人数均保持。原67面板、28图、9楼的其它65面板统计直接沿用。11种既有冻结标签仅用于保留原方法映射，不开展分类重选。

## 两个新增可评端点

|图片|团队人数|融合节点|原状态|辅助Q|
|---|---:|---:|---|---:|
|rPc6DW4iMge-06|4|10|no_connection|44.296907|
|uNb9QFRL6hY-88|3|7|no_connection|35.769679|

原Q为空，新增Q不是从0提高。来源：[AFFECTED_ENDPOINT_STATUS.csv](AFFECTED_ENDPOINT_STATUS.csv)。

## 全部原面板上的质量方差分解

每个面板按完整团队类别计数向量分组，保留method_known与11方法共享shared_known两种支持。按原实现分解总方差=同配比成员内方差+配比间方差；再按面板→目标池→图片→建筑等权汇总，最后以宏观配比间方差除以宏观总方差。不会先对各面板比例直接平均。

|冻结方法|标签支持|原配比间占比|辅助后占比|原可评团队链接→新链接|
|---|---|---:|---:|---:|
|RFUSE_GEOMQ_K2|method_known|14.134366%|14.223949%|7391→7393|
|RFUSE_GEOMQ_K2|shared_known|14.134366%|14.223949%|7391→7393|
|RFUSE_GEOMQ_K3|method_known|18.995165%|19.055025%|7391→7393|
|RFUSE_GEOMQ_K3|shared_known|18.995165%|19.055025%|7391→7393|
|RFUSE_GEOM_K2|method_known|11.961417%|11.952682%|7391→7393|
|RFUSE_GEOM_K2|shared_known|11.961417%|11.952682%|7391→7393|
|RFUSE_GEOM_K3|method_known|26.720986%|26.662319%|7391→7393|
|RFUSE_GEOM_K3|shared_known|26.720986%|26.662319%|7391→7393|
|TARGET_DSTRUCT_K2|method_known|27.929874%|28.031721%|7391→7393|
|TARGET_DSTRUCT_K2|shared_known|27.929874%|28.031721%|7391→7393|
|TARGET_DSTRUCT_K3|method_known|32.439565%|32.534050%|7391→7393|
|TARGET_DSTRUCT_K3|shared_known|32.439565%|32.534050%|7391→7393|
|TARGET_DSTRUCT_K4|method_known|34.282236%|34.374485%|7391→7393|
|TARGET_DSTRUCT_K4|shared_known|34.282236%|34.374485%|7391→7393|
|TARGET_RFUSE_GEOMQ_K2|method_known|17.963594%|18.048531%|7391→7393|
|TARGET_RFUSE_GEOMQ_K2|shared_known|17.963594%|18.048531%|7391→7393|
|TARGET_RFUSE_GEOMQ_K3|method_known|22.762329%|22.804458%|7391→7393|
|TARGET_RFUSE_GEOMQ_K3|shared_known|22.762329%|22.804458%|7391→7393|
|TARGET_RFUSE_GEOM_K2|method_known|11.961417%|11.952682%|7391→7393|
|TARGET_RFUSE_GEOM_K2|shared_known|11.961417%|11.952682%|7391→7393|
|TARGET_RFUSE_GEOM_K3|method_known|26.760159%|26.703016%|7391→7393|
|TARGET_RFUSE_GEOM_K3|shared_known|26.760159%|26.703016%|7391→7393|

来源：[ALL_METHOD_COMPARISON.csv](ALL_METHOD_COMPARISON.csv)。表中方法顺序沿冻结方法名称，未根据辅助结果选择分类。

## TARGET_DSTRUCT_K3的受影响面板

|图片/人数|支持|原Q可评队→新队|原同配比方差→新|原配比间方差→新|原配比间占比→新|
|---|---|---:|---:|---:|---:|
|rPc6DW4iMge-06/4|method_known|34→35|46.331064→45.007319|132.344570→153.654222|74.069736%→77.344724%|
|rPc6DW4iMge-06/4|shared_known|34→35|46.331064→45.007319|132.344570→153.654222|74.069736%→77.344724%|
|uNb9QFRL6hY-88/3|method_known|9→10|39.984926→35.986434|102.264767→102.275949|71.891028%→73.972361%|
|uNb9QFRL6hY-88/3|shared_known|9→10|39.984926→35.986434|102.264767→102.275949|71.891028%→73.972361%|

来源：[AFFECTED_PANEL_VARIANCE.csv.gz](AFFECTED_PANEL_VARIANCE.csv.gz)。分布、分位数、标准差、IQR、范围与失败支持见[AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz](AFFECTED_CONFIGURATION_DISTRIBUTIONS.csv.gz)、[AFFECTED_CONFIGURATION_COUNTS.csv.gz](AFFECTED_CONFIGURATION_COUNTS.csv.gz)。同配比仍有成员波动时，不能用一个配比均值代替成员分布。

这两个新增可评端点在TARGET_DSTRUCT_K3下恰好各自属于一个只有1队的配比：rPc6-06为C1:2、C2:2、C3:0的混合配比，uNb9-88为C1:0、C2:3、C3:0的纯C2配比。各自由0队可评变为1队可评，其同配比成员波动仍不可估。面板整体同配比方差下降包含新增单队配比所带来的分母变化，不表示原有成员组合变得更稳定。

## 原共同支持与未变项

辅助版另在每一指标原有可评团队上重算：全部原质量/几何支持与方差保持。失败、连接可用性等形成指标单独更新，不当作旧Q改善。标签、团队类别计数、已知/共享已知支持、组合容量与完整成员穷举判断逐项校验保持。原标注时间字段及其按来源拆分的分布和方差均保持；人工排序劳动没有计时，不能计算包含介入成本的总效益。

57组人工处理为定向选择；这里2队不能外推到所有无环团队，也不能作为分类选型的新样本。

## 复现与来源

`python -m tools.thesis_main.analysis.evaluate_manual_order_composition_20261104`

原聚合函数：`research/workers/personnel_v21_reselection_20261029/composition/code/aggregate_frozen_panels.py`。本脚本先精确复现原2面板的方差、配置计数和分布，再逐面板替换原全表并重跑原macro；固定标签来源`composition_other_labels.csv.gz`与难度/范围来源`composition_other_conditions.csv`均保留散列。检查与来源见[CHECKS.json](CHECKS.json)、[INPUT_MANIFEST.json](INPUT_MANIFEST.json)。
