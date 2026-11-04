# 人工辅助顺序对纯类与联盟的影响

## 版本、范围与方法

在原 `closeout_20261030/alliance_completion_20261031` 的联盟表上补入12个物理团队、19个实际引用。其中17行取得条件可评分结果；pa4otMbVnkk-18同一自交端点的2个标签快照引用仍为空。当前403个可执行改变联盟与11个仅容量记录保持，既有全表其它行不变。参见[AFFECTED_ALLIANCE_ROWS.csv](AFFECTED_ALLIANCE_ROWS.csv)与[ALLIANCE_414_RESOLUTION_ASSISTED.csv](ALLIANCE_414_RESOLUTION_ASSISTED.csv)。

原字段`version=frozen/updated`表示标签快照；本交付另用`connection_version`表示自动/人工顺序。标签、成员、人数、参考、类别容量和未知背景边界不变，不进行分类选型。全员与最佳纯类采用原可评规则，先池内挑选、再图片等权；不是将各类Q行直接混合平均。原自动摘要已复现，最大绝对误差4.55e-13，见[BASELINE_REPRODUCTION.csv](BASELINE_REPRODUCTION.csv)。

## 主比较与其它目标

|connection_version|scope|version|pools|images|mean_full_minus_best_pure|pure_better_images|full_better_images|tied_images|
|---|---|---|---|---|---|---|---|---|
|automatic|other_admitted|frozen|24|23|1.200119|6|10|7|
|automatic|other_admitted|updated|24|23|-0.077642|7|9|7|
|automatic|primary|frozen|205|205|-6.385821|173|32|0|
|automatic|primary|updated|205|205|-6.050732|169|36|0|
|manual_assisted|other_admitted|frozen|25|23|-0.548008|6|10|7|
|manual_assisted|other_admitted|updated|25|23|0.049069|7|9|7|
|manual_assisted|primary|frozen|205|205|-6.385821|173|32|0|
|manual_assisted|primary|updated|205|205|-6.050732|169|36|0|

来源：[FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv](FULL_VS_BEST_PURE_CONNECTION_COMPARISON.csv)。当前updated主目标205图仍为169图最佳纯类较好、36图全员较好，均值−6.050732保持；原frozen主目标173/32和均值−6.385821也保持。未知背景两图边界独立保留。

其它目标的比较池由24增至25，仍是23图。当前updated的全员减最佳纯类图片均值由−0.077642变为+0.049069，符号改写，但7图纯类较好、9图全员较好、7图持平不变，不能写成全员获得稳定总体优势。frozen快照则由+1.200119变为−0.548008。这两种方向变化必须按标签快照和支持条件区分。

`uNb9QFRL6hY-88`的纯C2三人队首次可评，使两个标签快照各新增同一比较池；其全员−最佳纯类为+11.493446。`wc2JMjhGNzB-26`的frozen快照在原可比较池内出现新可评纯类，最佳纯类Q由24.259815提高到67.381095，全员差由+46.644651降至+3.523370。这里是候选集合扩展，旧团队Q没有变化。详见[AFFECTED_POOL_COMPARISONS.csv](AFFECTED_POOL_COMPARISONS.csv)。

全部类别的Q、D10、IoU、结构分项与劳动分母详见[MANUAL_ASSISTED_CLASS_METRIC_SUMMARY.csv](MANUAL_ASSISTED_CLASS_METRIC_SUMMARY.csv)及[SUPPORT_COUNTS.csv](SUPPORT_COUNTS.csv)。图片/建筑层影响分别保存；多个目标池不当作多张独立图片。

## 单独的F2/F9坐标候选

主57组固定坐标结果保留。另按用户指定x=438.8037载入候选端点，固定其它y、节点身份、顺序、票数、成员与参考。候选Q=39.615619、D10=41.305788，kernel=false，属于conditional几何；没有作为正式坐标替换。

它仅命中pa4otMbVnkk-18的2个C1纯类引用。全员与最佳纯类的每个池及全部摘要均保持，新增比较池数和最佳纯类选择变化数均为0。C1自身条件均值与支持变化如下：

|connection_version|version|registered_pools|eligible_pools|valid_images|mean|
|---|---|---|---|---|---|
|MANUAL_ASSISTED_FIXED_COORDINATES|frozen|204|152|150|75.466377|
|MANUAL_ASSISTED_FIXED_COORDINATES|updated|204|168|166|74.880274|
|COORDINATE_CANDIDATE_NOT_ADOPTED|frozen|204|152|151|75.228955|
|COORDINATE_CANDIDATE_NOT_ADOPTED|updated|204|168|167|74.669108|

来源：[coordinate_candidate/SUMMARY_COMPARISON.csv](coordinate_candidate/SUMMARY_COMPARISON.csv)、[coordinate_candidate/CHECKS.json](coordinate_candidate/CHECKS.json)。这是不同方法条件下的新增可评结果，不是原无Q从0提升，也不等同单纯排序修复。

## 可保留和需限定的解释

主目标“最佳可评纯类通常高于全员”的既有描述保持；其它目标的均值与最佳纯类候选集合需按辅助条件改写。新增可评支持不等于相同旧支持质量变化。原标注劳动字段不变，但人工排序与候选坐标审查没有计时，不能据此估计包含人工介入的效益。

复现：`python -m tools.thesis_main.analysis.evaluate_manual_order_alliances_20261104`；已完成主分支时，`--candidate-only`只运行独立坐标候选传播。定向57组不能外推全部无环结果可修复。逐条判定见[CONCLUSIONS.csv](CONCLUSIONS.csv)。
