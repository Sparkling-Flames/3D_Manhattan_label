# 人工辅助顺序对旧角色策略的影响

## 实际引用范围

唯一命中 `x8F5xyUWy9e-08__manual__0b13997fd3__fb261248c4a2c1b66d0b`：N=35池中的 k=28、`new16`批次、`structure_dominant_first`策略一条前缀路径。辅助Q=30.829880、D10=31.376466；原自动Q为空。该策略是历史 V3_BEHAVIOR 角色策略，不能因名称含“structure”就称为当前 DSTRUCT 策略。来源：[AFFECTED_PREFIX_AUTOMATIC.csv](AFFECTED_PREFIX_AUTOMATIC.csv)、[AFFECTED_PREFIX_ASSISTED.csv](AFFECTED_PREFIX_ASSISTED.csv)。

原主 cohort 153图/21栋保留；命中只传播到 new16 和 pooled32 的 `late_20_to_Nminus1`。old16、次要原old8、added_reference32、早段与全员端点无变化。实际后段paired-Q可评图片仍150/153、21栋，不能将一条补入路径当作新增独立图片。

## 主要结果

|version|weighting|estimate_automatic|estimate_assisted|images_assisted|buildings_assisted|building_lo_automatic|building_hi_automatic|building_lo_assisted|building_hi_assisted|
|---|---|---|---|---|---|---|---|---|---|
|new16|image_equal|-0.722012|-0.724289|150|21|-1.699170|0.115290|-1.700549|0.115243|
|new16|building_equal|-1.031994|-1.040127|150|21|-1.900724|-0.198790|-1.905194|-0.209944|
|pooled32|image_equal|-0.776979|-0.778220|150|21|-1.678785|-0.016132|-1.681315|-0.016801|
|pooled32|building_equal|-1.078062|-1.082493|150|21|-1.904494|-0.321733|-1.908229|-0.324162|

来源：[LATE_GLOBAL_COMPARISON.csv](LATE_GLOBAL_COMPARISON.csv)。表中建筑区间沿用原2000次bootstrap。pooled32图片等权的Q差从−0.776979到−0.778220，建筑等权从−1.078062到−1.082493；方向与原区间判定保持。new16图片等权建筑区间仍跨0，而pooled32图片等权仍为负区间，不能混用两个版本的显著性。

全部22项指标、难度层和两种权重共352个后段摘要组中，104个点估计格数值变化，点估计符号变化0处；路径区间与建筑区间相对0的关系变化均为0。质量分项、失败/不完整、达阈值、节点和结构项的全部逐格变化见[NUMERIC_CHANGES.csv](NUMERIC_CHANGES.csv)。新端点质量较低导致条件Q差略降，同时原失败支持减少；这两者可并存，不能将“能够评分”解释为Q必然更好。

## 支持、精度和劳动

保持原 fixed-k 支持、base_path_id、old8/prior_new8/new16 分层抽样以及2000次 whole-path bootstrap，seed=2026102603。原仓库未保存所需完整后段路径bootstrap缓存，故仅从既有153池标量表恢复命中策略的new16/pooled32后段缓存；没有重融合、重评分或产生新团队。恢复后的原自动全局点估计和所有区间与原保存结果最大绝对误差 3.55e-15。检查见[BASELINE_REPRODUCTION.csv](BASELINE_REPRODUCTION.csv)。

路径有效抽样次数及“conditional_on_estimable_draws”状态均原样保留。辅助版完整精度表见[POLICY_PRECISION_SUMMARY_ASSISTED.csv](POLICY_PRECISION_SUMMARY_ASSISTED.csv)，图片/人数/固定支持消费者见[ASSISTED_POLICY_IMAGE_PHASE.csv](ASSISTED_POLICY_IMAGE_PHASE.csv)、[ASSISTED_POLICY_IMAGE_K.csv.gz](ASSISTED_POLICY_IMAGE_K.csv.gz)、[ASSISTED_FIXED_SUPPORT.csv.gz](ASSISTED_FIXED_SUPPORT.csv.gz)。

原已评分端点值不变，原劳动3353.624秒及其它标注劳动字段保持；人工排序劳动未知。因此本节结论为旧策略后段效应幅度变化，不能推出包含人工介入成本的策略效率改善，也不能替代当前DSTRUCT策略证据。

复现：`python -m tools.thesis_main.analysis.evaluate_manual_order_policy_20261104`。数值完成后，报告生成器只读结果，不重复bootstrap。见[CHECKS.json](CHECKS.json)、[CONCLUSIONS.csv](CONCLUSIONS.csv)。
