# 人数抽样精度补充：连接键、估计量与缺失状态

数据为真人 v2。实际读取 main：`40d0fe62dc62f6f6c12723af10195b7abb7bc9fe`。本目录的 `20261025` 是研究轮次，不是数据版本。建议放入：

`research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/`

## 1. 精确连接

|键或字段|含义|接入要求|
|---|---|---|
|`pool_id`|图片、条件、冻结参考及合法人员池的既有键|原样连接，不由图片名自行重新生成|
|`image / image_id`|可读图片号及原图标识|建筑与图片分别保留；本轮未新增房间事实|
|`reference_id / reference_version`|冻结评价参考|不依据新结果改变参考或资格|
|`team_key`|池键加排序后的实际成员集合摘要|同成员只算一个端点，随机重复访问的次数仍保留|
|`member_workers / member_object_ids`|实际人员、对应正式原答对象|用 `object_id` 接回原答，不按人员总分替代几何|
|`path_id`|一条完整自然或策略顺序|抽样/重抽单位是完整路径，不能把各 k 当独立样本|
|`base_path_id`|策略对应的自然基础路径|同 base、同 k、同最终池比较策略；自然行与自身一致|
|`k / pool_n`|参与人数与该池实际容量|不同容量面板不直接相减；满员为每池实际 N|
|`seed / master_seed / new_index`|可重建顺序的种子与编号|seed按完整整数或字符串保存，禁止转成有损浮点数|
|`geometry_shard / geometry_line_1based`|新端点完整state位置|先由几何包索引找到文件，再按行读取；轻量几何直接按team_key连接|

原24条的精确顺序引用同一提交下的 `design/EXACT_ORDER_DESIGN.csv.gz`。本轮新增顺序在本目录 `design/NEW_EXACT_ORDER_DESIGN.csv.gz`，全部前缀连接在 `design/NEW_PREFIX_TEAM_LINKS.csv.gz`。

`endpoint_source=new_native_required_20261025` 保留的是设计登记时的来源身份，不表示目前尚未计算；本轮这323807队已经全部产生真实端点。完成状态以 `COMPILE_RECEIPT.json` 和相应输出为准，不能依据来源字段里的 `required` 把结果标为待算。

## 2. batch 与分析版本

`balanced_new24` 为194个Manual池各自新增的24条；`focus_new48` 为预先按旧噪声选择的53池再新增48条；`policy_new8` 为四策略共同157池各策略新增8条稳定优先排序。它们是抽样批次，不是新的人员类别。

分析版本 `old24 / new24 / pooled48 / focus96` 分别表示旧24、独立新增24、前两批等权合并48、重点池累计96。重点另有独立新增72的条件说明表。主总体比较统一使用前3个版本，96只在同一重点子域比较。重点选择基于旧24的噪声；其区间条件于这份既定名单，不包含重新挑选重点池的过程。

设计表中的 `sampling_weight_new_batch` 只在该新增批次内归一化。合并48时每条路径为1/48，累计96时每条为1/96；不能把两个批次各自总权重1直接与额外48批次混合。先逐图统计，再图等权或建筑等权，不按路径多寡给图片加权。

原四策略使用 `V3_BEHAVIOR/fine` 及 `V3_JOINT_QT/coarse` 的冻结楼外角色，角色含义由历史中心对齐。`target_class` 是相应楼外折内编号，不能把不同建筑同编号直接合成一个类。新设计保存实际 `target_members`；本轮没有重新分类。

## 3. 正式状态

|字段/状态|解释|
|---|---|
|`score_available` 与有限 `B8L2`|该端点实际有正式Q；Q条件分布只使用它|
|`policy_deferred`|2人阶段沿冻结合同暂停；Q留空，不算失败或成功|
|`score_failure_nonpolicy`|非延期的实际不可评分端点；用全部非延期尝试作分母|
|`incomplete_nonpolicy`|非延期且完整共识不可用；与Q不可评分别保存|
|`complete_floor_evaluable / geometry_status`|底面及几何指标的资格；存在JSON不等于可用|
|`geometry_available`|沿用旧包装的“候选字典存在”字段；延期记录也可能为true，不能用它统计有效或完整几何|
|未计算|未产生请求对应结果；正式合并程序会报缺连接，不把它填成失败|
|参考缺失/暂停|沿用原冻结资格，不用新Q、原答可见或几何存在恢复资格|

主194个Manual池的参考及正式人员均从原实验继承。OOS不并入普通Q；门洞单列。原答筛除、时间缺失及来源状态不因本轮抽样改变。CSV空值表示真实缺失，不能自动转成0。

本轮主新增323809条端点记录中，2114条是单人，7874条是两人合同延期，313821条为三人及以上。可评Q/D10为304202条（含单人）；三人及以上302088条可评，11733条不可评。`complete_conditional / below_four / invalid_floor / no_connection / two_person_deferred` 分别为304202 / 7068 / 121 / 4544 / 7874条。这里是新增独特端点的执行账，不是按图片等权的自然失败率；正式自然失败率必须沿随机路径频数和对应图片权重计算。全部记录均有真实状态，不把延期记成失败。

## 4. 指标及统计单位

- Q 为 B8L2；D10为冻结方向尺度敏感性。`B8_*_block` 是损失量，越小越好，不能当成直接可相加的Q分变化。
- 每图每 k：可评分路径均Q、线性经验P10、样本SD（ddof=1）。实际失败始终使用全部非延期路径。Q/几何/时间各自保存可用分母。
- 几何V为两条独立自然路径底面的平均 `1−IoU`。样本用去掉同一路径自配的U统计；不同路径恰好相同成员的0距离保留。质心和高度用相机高度归一化单位；转折/节点差另列。
- 精确边际对所有合法 k 人子集等权。真有限总体SD用ddof=0；真V的分母为 M²，包含两次独立抽到同一团队的0距离。不能除以M(M−1)而改变估计对象。
- k=N只有一支团队，顺序Monte Carlo误差为0；失败的满员仍无Q。满员零成员波动不是误差或参考偏差为0。
- 固定图片完整路径重抽与固定路径建筑整块重抽分别报告。范围为逐项95%范围，不是同时置信带，也不是新建筑外部验证。
- `MCSE≤1` 是一个标准误的工作量尺，不是95%误差≤1。P10经验区间与保守秩区间同时保留。只有1条有效Q、又非精确边际时，不把重抽零宽区间当作精确。
- 主要正/反向图数使用±1e−9数值零容差，另存严格符号计数。实际幅度仍以完整数值报告。

## 5. 主要表的职责

|表|用途|
|---|---|
|`design/ENDPOINT_DEPENDENCIES.csv.gz`|完整340055个请求集合、成员、参考与复用/新增身份|
|`new_endpoints/NEW_ENDPOINT_SCALARS.csv.gz`|本轮主实验实际新增端点；不重复旧大表|
|`new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz`|403376条新增路径前缀的真实值，含命中旧端点者|
|`new_endpoints/EXACT_MARGINAL_VALUES.csv.gz`|14904个精确边际目录条目及真实结果|
|`new_endpoints/NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz`|全部主新增端点的轻量最终几何/状态/完整state定位|
|`analysis_precision/new_results/NATURAL_POOL_K_BATCH_PRECISION.csv.gz`|逐图、全部人数、各批次估计与抽样精度|
|`analysis_precision/new_results/NATURAL_FIXED_SUPPORT_STABILITY.csv.gz`|固定容量/难度面板，路径误差与建筑差异分别汇总|
|`analysis_precision/new_results/HYBRID48_IMAGE_CURVES.csv.gz`|可采用的边界精确、中段48条结果；原表不被覆盖|
|`analysis_policy/results/POLICY_COMMON_PAIRED_EVENTS.csv.gz`|原8/新8策略的精确同base同k事件|
|`analysis_geometry/results/GEOMETRY_PATH_PRECISION.csv.gz`|V/质心/高度/转折/节点波动及抽样误差|

大于适宜单文件体积的新表按行分片，每片都是可独立读到结尾的gzip。`TABLE_SHARD_MANIFEST.json`与 `engine/restore_table_shards.py` 负责恢复统一文件。精确表名及相对位置以交付的实际文件清单为准。完整原生票账另在P03分包；一般统计和几何复算只需主数据包的标量与轻量几何。

## 6. 版本与原件身份

本轮包括：沿用原24及已有端点；重聚合原结果并增加精度分析；新生成独立路径并执行新增端点；穷尽可行有限边际。它不是找回一个丢失旧包后改名。计时中的额外端点另列，只有与正式设计精确相交的2队进入主复用；其余计时队不混入曲线或失败率。

## 7. P01第2版的策略顺序更正

正式顺序字段 `worker_order` 和 `workers` 现均为该 `path_id` 实际使用的进入顺序；`base_worker_order` 保存对应自然base，策略通常与其不同。第一版5,024个策略行误继承自然字段，但实际前缀及融合正确。第2版逐行按冻结前缀恢复并核对target先行稳定分割；5,022行字节内容改变，2行原来一致。自然7,200行的原字段不变。

原件位于 `design/source_original/policy_order_metadata_20261025/`，只用于追溯；正式运行使用上层 `design/NEW_EXACT_ORDER_DESIGN.csv.gz`。更正回执明确列出9个未改动的成员请求、关联、端点和结果SHA。P10定义诊断则是独立派生分析，保留linear与inverted_cdf两种有限参考；不改变原样本P10或融合。
