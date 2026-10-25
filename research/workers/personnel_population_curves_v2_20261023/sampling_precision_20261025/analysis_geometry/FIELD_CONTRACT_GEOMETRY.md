# 几何精度结果：研究台接入字段

本模块是本轮新顺序研究的几何分支。输入资格与几何来自冻结v2端点，旧源固定在main提交 `40d0fe62dc62f6f6c12723af10195b7abb7bc9fe`。不重新评分、融合或分类。

## 键和抽样身份

|字段|含义|
|---|---|
|`pool_id`|冻结图×条件×参考/版本的正式人员池键；沿用既有主键。|
|`image`、`image_id`|可读图片名及原始图片身份；不能仅用建筑当房间。|
|`building`、`condition`、`layer`、`difficulty`|原字段；本分支主层普通Manual，门洞Manual单列，未把门洞改成困难。|
|`team_key`|`pool_id`与排序后的实际成员集合哈希；连接原标量、精确成员、新/旧几何。|
|`path_id`、`k`|完整随机进入路径及当前人数；沿用设计文件，统计保留同队重复路径频率。|
|`cohort`|抽样预算身份：`old24`、`new24`、`combined48`、`focus48`、`combined96`。`focus48`是额外48条单独新路径，不是合计48条。|
|`minimum_pool_n`|固定容量支持范围20/30/35；正式曲线只输出`k≤minimum_pool_n`。0表示全部具有该k容量的池，后段图片支持可变化，`candidate_images`明确给出。|

`combined96`只存在于预先选择的53个重点池；不能将该层均值与所有194池的`combined48`直接相减。`GEOMETRY_OLD_ADDED_COMMON_SUPPORT.csv`已在相同具体图片/人数/指标上比较。

## 指标与分母

|字段/指标|含义|
|---|---|
|`V_floor`|有效完整底面的两次自然独立抽样输出之间，平均`1−IoU`，无量纲。|
|`V_centroid_h`|两个有效底面质心的欧氏距离，相机高度单位。|
|`V_height_h`|两个有效底面的保存平均高度之绝对差，相机高度单位。|
|`V_turn5`、`V_nodes`|保存实际转折数或输出节点数的绝对差。|
|`mean`|某图某k的路径U统计估计值，条件于该指标两端可用。|
|`mcse`|删除一整条路径后的jackknife蒙特卡洛标准误；不是跨图/新楼预测误差。少于3个有效路径时不估计。|
|`attempted_paths`|所有该预算保存的自然路径，包含无有效几何者。|
|`valid_paths`、`valid_pairs`|该指标有效路径数量及无序不同路径对数；重复同队路径仍可构成有效零距离对。配对数不是独立样本量。|
|`unique_teams`|所有尝试路径实际不同成员集合数，不按几何或Q成功筛除。|
|`full_pool_endpoint`|k等于该池N。有效时V=0是有限池成员集合唯一导致；失败时保持缺失。|
|`paired_paths`|前后人数保留相同进入路径；区间MCSE用共同删除路径，保留相关性。|
|`exact_mean`|精确枚举有限团队总体的几何期望。独立双抽样包含同队自配0，条件有效分母为有效团队数平方。|
|`exact_valid_teams`、`valid_fraction`|精确总体的有效团队数和比例。失败/无效不改成0距离。|

## 汇总与误差

`GEOMETRY_CURVE_MC_SUMMARY.csv`和`GEOMETRY_INTERVAL_MC_SUMMARY.csv`保留图片候选数、有效图数、建筑数、图等权估计、建筑等权估计、图间及建筑均值间标准差。`aggregate_mcse`仅合成各图随机顺序的抽样误差；`half_width_95_mc=1.96×aggregate_mcse`只是该误差的近似半宽。`building_mean_sd`是不同建筑平均结果的离散程度，不能当作另一个MCSE。

`GEOMETRY_SAMPLE_VS_EXACT.csv.gz`在已经穷尽的边际上给真实估计误差；`nominal95_covers_exact`检验近似区间是否覆盖该已知有限总体，仅作为误差校准描述。满员的零误差单列，不用大量相同满员路径夸大抽样精度。

`exact_kind=small_pool_all_subsets`也可能包含k=1、N−1和N，因此比较所有N−1时须按`k=pool_n−1`识别，不能只筛`all_leave_one_out`。后者只覆盖171个普通池；加上小池后为177。`GEOMETRY_NMINUS_COMMON_SUPPORT_ACCURACY.csv`已按实际人数识别，并给old24与每个追加预算的精确可用、各自可估、共同图片和建筑分母；其中96只比较实际预选的焦点池。

`GEOMETRY_UNCOMPUTED_LINKS.csv.gz`与`EXACT_GEOMETRY_UNCOMPUTED_LINKS.csv.gz`专门保存未计算端点；正式最终包应为0行。实际端点失败通过源标量状态保留，不与未计算混为一项。

## 文件与新旧依赖

逐图统计、同路径区间、共同支持、精确边际和图表数据均为本轮新增分析产物。旧源标量/几何通过固定main路径复用，不重复打包。新端点的全部标量和紧凑几何在本轮主数据包；全量full_state是可选机制材料。几何统计复算不依赖可选大full_state。

`old_pool_geometry_cache`、`new_compact_pool_geometry_cache`、`combined_pool_geometry_cache`以及逐池处理中间检查点均可由来源重建，不作为主要交付。VFua例外保留少量必要原答、参考、精确端点与状态，便于不下载全量数据即可阅读和重画机制图。

`GEOMETRY_OUTPUT_READBACK_RECEIPT.json`记录最终表的实际EOF/字段/行数核对、关键复合键检查和PNG/PDF完整读取。代码中的`safe_io.py`先在内存形成完整CSV和gzip，再原子写、fsync、字节及解压回读；它只保护交付I/O，不改变统计方法。
