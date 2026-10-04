# 数值字段与解释

## 分型与来源

`policy=original / revised_where_available`控制Q校准使用哪套现有参考。`revised_where_available`只在四张已有修订参考的图片替换分数，不对每个人／组合选较好的参考。在本包两张几何图上，输出评价固定原参考。

`method=median2`是人为中位数二分；`ward2/3/4`是以校准Q均值为一维输入的Ward分组，不强制组人数相等。`subtype`从低校准Q到高校准Q排序，不是全库永久人员类型。`none/all`表示不分型。

`target`是整栋留出的建筑。`calibration_centered_iou`来自其他建筑，不包含目标图。`prediction`预测图内相对参考分数。外层平方误差的分母是相对“不区分人员”的基线SSE，不是百分制准确率。

`composition`按类号记录实际抽取人数，例如`3|3`是低类3人＋高类3人；不是三个组，也不表示两种“正确程度”。`class_sizes`是完整固定子类人员池容量。所有成员票权为1。

## 区域与分数

每图共同`U`为全24人原地面区域并集面积，纯类与混合类不换分母。积分tile来自人员边界，GT只用于事后交面积评价。使用离线全员细分不提供未来票，不据此决定当前类别或停止。

|字段|定义|不可混同|
|---|---|---|
|`expected_area_union`|E[共识面积]/U|不是IoU|
|`same_k_independent_symdiff_union`|E[两次独立抽组的共识对称差面积]/U|组间可共享人员，不是两组完全不同真人|
|`same_k_disjoint_symdiff_union`|相同构成且组间完全不重叠的输出对称差/U|当2k_g>N_g时缺失，不填0|
|`expected_ref_symdiff_union`|E[共识与固定参考对称差面积]/U|不是1−IoU；不是视觉错误面积|
|`expected_ref_symdiff_gt`|同上但除以参考面积|不可与U归一化值混比|
|`expected_omission_union`|E[参考未被覆盖面积]/U|参考不适用时不能解释为漏标真空间|
|`expected_extension_union`|E[超出参考面积]/U|不自动等于无效延伸|
|`squared_bias_union`|积分平方偏差项，等于参考对称差损失减去半个独立抽组差异|不是工人心理偏差，也不是因果偏差|
|`mean_iou`|对列明的全部实际集合分别计算IoU再平均|不是期望交面积/期望并面积|
|`sd_iou`、分位数|当前固定集合分布的离散度|不是均值标准误或总体置信区间|

## 联合人员过程

`operation=add`下的`change=1|0`为从剩余低类增加1人，`0|2`为从剩余高类增加2人。同一旧集合被完整保留。

`operation=swap`的`0->1`指移出当前低类1人，再从原集合外加入高类1人。`0->0`是同类换具体成员。新人不能是刚移出的同一人。

`expected_shape_change_union`是旧融合与新融合的期望对称差/U。`expected_growth_union`与`expected_shrinkage_union`分别是0→1与1→0面积；二者之和为变化，二者之差为期望面积改变。

`expected_ref_error_change_union`正值表示新融合更偏离这版参考，负值表示更接近。不是视觉正确性裁决。

## 原始作答与估计的分布

`mean_raw_pair_1_minus_iou`为不同真实成员的平均两两地面`1−IoU`。在同一个固定类内，随机子集的平均两两距离期望不随k变化；不是说经验分布不能被更准确估计。

`next_member_annotation_error_union`比较当前融合与剩余池下一人自己的原标注。`add_one_fusion_change_union`比较当前融合与纳入该人后的新融合。两者必须分开。

`expected_empirical_energy_distance`基于sqrt(对称差/U)距离，采用含自配对项的经验分布V统计定义，期望为2μ(1/k−1/N)。不是Jensen–Shannon散度、模式数量或新真人预测误差。

`expected_nearest_seed_sqrt_symdiff_union`度量一个未进入成员到当前种子的最近几何距离。k增大会机械增加最近邻机会，不能单独作为模拟器或候选发现有效的证据。

## 六人集合与方差

NPZ内`subsets`存0起始人员索引，需与同文件`worker`和`record_id`对应；两个规则分别有IoU和面积。每图134596个不同六人集合，不是134596个独立试验。

`between_share`按照所有六人集合自然出现的构成频率，计算Var(E[Y|构成])/Var(Y)。`within_share`是余项。它不是因果解释率，也不等于标签对新图的预测R²。

`extrema_diagnostic`中的极端人员组是事后诊断，`deployment_selection=false`。不得据此把GT最大值团队部署为“算法选出的最佳组合”。

## 名单传播与覆盖

`calibration_propagation`中每个目标图均枚举其他7栋建筑取4栋的35种校准集合。结果是已声明有限校准设计下的精确描述，不是35个独立数据集，也不是新建筑的抽样置信区间。

`computable_probability`仅依据台账中不可计算成员数做超几何覆盖核算。失败仍保留在原池。它不涵盖未知的新聚合失败，也不是参考兼容率。

所有NA必须按其含义读取：结构／数据不可用、某方法不适用、组合人数不足、参考不适用、分类未定彼此不同。不要一律归为错误、排除、零或“无不确定性”。
