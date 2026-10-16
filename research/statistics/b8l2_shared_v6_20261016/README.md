# B8L2共同评分与描述统计：固定v6（2026-10-16）

本次主线实际采用原版`WQ-B8L2-20261015`，不等待Pro的新模型或调参。输入固定为`scope_preferred_difficulty_scope_resolved_20261016_v6`和既有3152份原作答；运行不再读取实时CURRENT，也不导入新人或新图片。模型方向尺度8、上限1.5，底边平方尺度32，高度尺度0.8/0.25，底面与方向L2组合；冻结测量未改变。

**本次完整测量1624份，当前合格1622份；旧v4的891份全部保留，新增731份是原库存首次完整评分覆盖。** 另2份人工指定其它合法空间只作诊断。旧891份同输入、同参考的B8L2在1e-8数值精度内不变；42份仅按v6改变分组。731不是新采集、提高分数或放宽人员门，也不是B8L2比WQ更好导致的“新增合格”。

|condition|analysis_layer|records|images|workers|B8L2_mean|IoU3D100_mean|
|---|---|---|---|---|---|---|
|manual|ordinary_current|1137|95|25|67.40|77.77|
|manual|special_or_pending_separate|23|1|23|69.39|76.02|
|semi|ordinary_current|438|28|24|79.42|84.59|
|semi|special_or_pending_separate|24|1|24|84.19|87.72|

其中1575份为ordinary_primary，47份仅special_conditional_only。OOS几何可计算不等于表示适用性已验证；其它模块仍应保留自己的适用性暂停，不能因本表存在一个条件指数就强行开放其完整质量终点。

## 共同输入：下游应读哪份

[CROSS_MODULE_INPUTS.json](CROSS_MODULE_INPUTS.json)是本轮唯一共同交付清单，版本`b8l2_shared_v6_20261016_v1`。默认读[quality_records.csv](quality_records.csv)取得合格评分；完整库存、空分与排除原因读[shared_records.csv](shared_records.csv)。按完整身份、输入/参考/算法版本连接，不把旧WQ列改名为B8L2，也不复制旧目标分数。

人员线按条件、用途层选择当前评分后自行重建画像与组合分析；这里的逐人均值不是能力类型。融合线同时读取source_pools与冻结原作答，先核人数与图片门，再核状态目标和完整参考；合格池内k=1/2节点可保留。没有为统计覆盖而改融合几何、阈值或已有成员。共同参考目录可算不代表每份作答都属于它；uNb-36保持当前质量待定，不能以完整GT替代问题裁决。

同房线只读直接关系并在同条件、共同人员内对照；本页同房描述不是新迁移或墙线融合研究。各模块不得把已完成的旧WQ模型/曲线直接称为新B8L2结果。

## 输入变化、样本变化和换指标分开

[输入变更审计](audit/INPUT_CHANGE_AUDIT.md)记录v4至v6的17张仅标签变化、2张目标变化、3张资格变化（可交叉），以及3441对象的身份、点序、既有门全部未变。S9-09与zsNo-13采用新目标，两图均只有明确标示的顶界外推预览，仍不计算完整评分；S9虽解除范围门，但仅1名有效真人。GT错误与旧排除继续优先。

[member_changes.csv](member_changes.csv)逐对象区分891保留、731首次评分覆盖及其余1530未进入。新增普通manual309、普通semi375；专项manual23为uNb-63的OOS条件记录，专项semi24为e9-16。后者当前粗类简单但v6普通资格标志仍为false，统计继承该标志单列，没有擅改上游标签或资格。专项不能合入普通难度均值。

WQ/A10/B8L2/同参考均高棱柱IoU均在本轮固定输入上实算保留。[algorithm_comparisons.csv](algorithm_comparisons.csv)展示同集合指标差异；新旧总体均值之差同时受新增覆盖和标签影响，不能归因于换公式。缺分不填0，OOS适用性及未决空间单列；IoU不是任意实体精确体积IoU，B8L2的D仍是自身方向规整性，未升级为参考结构正确性。

## 分层统计、时间与图簿

普通难度描述如下，分条件展示实际有效数和覆盖；标签是人工辅助粗类，部分参考过作答，均值分层不是独立验证，不要求顺序单调。

|panel|difficulty_class|metric|n_valid|n_missing|n_valid_images|mean|sd|
|---|---|---|---|---|---|---|---|
|ordinary_manual|中等|B8L2|121|112|15|61.09|19.08|
|ordinary_manual|中等|IoU3D100|121|112|15|76.30|13.39|
|ordinary_manual|困难|B8L2|236|188|16|49.04|23.22|
|ordinary_manual|困难|IoU3D100|236|188|16|66.36|23.21|
|ordinary_manual|简单|B8L2|780|310|64|73.93|17.43|
|ordinary_manual|简单|IoU3D100|780|310|64|81.45|12.88|
|ordinary_semi|中等|B8L2|15|11|4|84.88|16.14|
|ordinary_semi|中等|IoU3D100|15|11|4|95.59|6.65|
|ordinary_semi|困难|B8L2|4|0|1|70.43|28.26|
|ordinary_semi|困难|IoU3D100|4|0|1|86.49|14.34|
|ordinary_semi|简单|B8L2|419|33|23|79.31|16.99|
|ordinary_semi|简单|IoU3D100|419|33|23|84.18|12.20|

库存有可用原采集时间1949份，其中当前合格来源分析时间1750份；它们不是同一个分母。完整质量与来源时间共有1042份，已审计同目标质量/时间共有440份。新评分没有据采集时长推断新目标完成时间，也没有使用lead_time替代。source/time状态与秒单位逐行保留，time_coverage展示条件与层的真实覆盖。

- [B8L2共同评分工作簿](B8L2共同评分_描述统计.xlsx)：逐人、逐图、人员×难度、场景、建筑、同房、时间、成员变化和完整/缺失分母。
- [七组关键图及说明](figures/FIGURES.md)：B8L2为主，保留WQ/A10/IoU对照。
- [空间点位职责与冗余派生视图](../../data/scope_redundant_vertices_20261016/README.md)：补充显示/诊断资料，不参与本快照评分。按原target_id使用新环，不追加已被新目标排除的旧GT角点；严格等价与精度内近似分开，未知高度不生成完整点对视图。仅2份参考自比及1份真人作答已核验B8L2差值为0，不作全库不变性结论。
- [冻结参考与绑定审计](inputs/REFERENCE_BINDING_AUDIT.json)、[独立评分审计](audit/SCORING_AUDIT.md)。

43张受影响图的511份作答仍全部列在affected_records；3152份总绑定另列shared_bindings。41个确认新空间中12个具完整参考、29个仍待补，371份原作答尚无唯一空间绑定。小幅源域越界可能涉及坐标精度口径；诊断保留源JSON与ERP转换差异，未通过调容差、snap或外推来改变评分参考。

## 复现与边界

```powershell
python -m tools.thesis_main.analysis.b8l2_shared_snapshot_20261016 --snapshot-dir research/statistics/b8l2_shared_v6_20261016
```

现有目录已经固定FROZEN_INPUTS、库存/时间、历史比较、来源/参考绑定及模型/测量实现。本命令只消费这些固定资料；未来增量另起版本和目录。原始标注、GT、CURRENT、正式合同、评分参数和历史结果未覆盖；不推送、不启动采集。图簿用各自既有生成器，复现命令见图表说明及工作簿验证记录。
