# 当前口径描述统计与复核结果（2026-10-15）

后续已完成[2026-10-16参考重算统计](../descriptive_statistics_rescored_20261016/README.md)：90份实际重算、84份新增当前质量，总数891。本页807份及160待处理为重算前阶段快照，历史文件保留；逐项审计见[41图506份清单](../../data/scope_quality_rescore_20261016/README.md)。

本报告按用户新授权更新当前统计。旧[3152／1145／931／836报告与图表](../descriptive_statistics_20261015/README.md)保持历史快照，没有把旧难度标签直接换成新标签继续使用旧范围分数。本次不锁定论文大纲、不选择唯一质量公式、不按预期调参；所有比较首先展示真实覆盖、缺失和限制。

当前读取CURRENT指向的`scope_preferred_difficulty_review_20261015_v3`。库存仍为3152条、259图，当前类别如下。其中206图只是图片模块的普通难度**候选**，还必须通过来源人数、继承图片暂停、作答限制及指标参考检查；不能称为最终可分析图片数。

|当前类别|图片数|
|---|---|
|中等|27|
|单列|44|
|困难|30|
|待修正GT|3|
|待复核|4|
|简单|151|

## 来源池人数与实际分析范围

人数规则版本为`retained_independent_humans_by_image_condition_min3_20261015_v1`：仅annotation且cleaning_disposition=retained、independent_vote_eligible=true，既有作答excluded门不纳入；同image_id/condition按worker_id去重。图级GT/范围/既有暂停不抹去真实人数；人数>=3仍须图级门及各指标参考/时间资格。本门不读取质量分数，不修改合格来源池内k=1/2轨迹。 每个来源池是`image_id×condition`，manual、semi、oos分别计数；同图可以出现在不同条件，不把条件池数量相加当作独立图片。分数或时间缺失不把真实参与人数改成零，人数合格也不保证每项指标都有3名有效分数。

|条件|有作答来源池|至少3名有效真人|通过图片门|普通难度来源池|
|---|---|---|---|---|
|manual|232|190|184|153|
|oos|9|9|9|0|
|semi|43|43|43|40|

有作答但尚未过人数门的来源池为42个：有效真人为1—2名的40个，零名有效真人的2个。零有效不代表未采集，而表示已有记录均未通过本次有效作答规则。空的图×条件组合不列为待补人任务。补人后动态重查，不永久删图；GT、修订GT、重复提交和融合结果不能凑人数。

人数不足与GT／范围／旧暂停可以重叠。下面按原因组合列来源池，不把重叠原因逐项相加：

|条件|原因组合|来源池数|记录数|
|---|---|---|---|
|manual|current_gt_error／effective_workers_below_3／historical_gt_substantive_error／historical_quality:hold_reference_quality|1|1|
|manual|current_gt_error／historical_gt_substantive_error／historical_quality:hold_reference_quality|1|6|
|manual|current_gt_error／historical_quality:hold_reference_quality|1|5|
|manual|current_target_scope_unresolved／effective_workers_below_3|1|1|
|manual|effective_workers_below_3|37|58|
|manual|effective_workers_below_3／historical_consensus:hold_all_analysis／historical_quality:hold_all_analysis|2|4|
|manual|effective_workers_below_3／historical_gt_substantive_error／historical_quality:hold_reference_quality|1|2|
|manual|historical_consensus:hold_main_analysis／historical_gt_substantive_error／historical_quality:hold_main_analysis|1|5|
|manual|historical_consensus:inner_space_only_reference_hold／historical_gt_substantive_error／historical_quality:hold_reference_quality|1|6|
|manual|historical_gt_substantive_error／historical_quality:hold_reference_quality|1|4|
|manual|historical_quality:hold_reference_quality|1|5|
|manual|none|184|2247|
|oos|none|9|234|
|semi|none|43|574|

当前有记录且带图级暂停／未决原因的图片共11张，完整列在下表。当前新增的3张GT错误为jtcxE69GiFV-05、jtcxE69GiFV-17、wc2JMjhGNzB-14；既有GT实质错误、旧quality/consensus暂停继续优先，不能因新难度候选表未写出就恢复。普通难度排除不等于专项不可研究，但明确GT或图级暂停仍约束专项。

|图片|条件|有效真人数|图级暂停原因|
|---|---|---|---|
|S9hNv5qa7GM-09|manual|1|current_target_scope_unresolved|
|jtcxE69GiFV-05|manual|6|current_gt_error；historical_gt_substantive_error；historical_quality:hold_reference_quality|
|jtcxE69GiFV-11|manual|1|historical_consensus:hold_all_analysis；historical_quality:hold_all_analysis|
|jtcxE69GiFV-17|manual|1|current_gt_error；historical_gt_substantive_error；historical_quality:hold_reference_quality|
|pRbA3pwrgk9-12|manual|2|historical_gt_substantive_error；historical_quality:hold_reference_quality|
|pRbA3pwrgk9-16|manual|2|historical_consensus:hold_all_analysis；historical_quality:hold_all_analysis|
|uNb9QFRL6hY-32|manual|5|historical_consensus:hold_main_analysis；historical_gt_substantive_error；historical_quality:hold_main_analysis|
|uNb9QFRL6hY-51|manual|4|historical_consensus:inner_space_only_reference_hold；historical_gt_substantive_error；historical_quality:hold_reference_quality|
|wc2JMjhGNzB-14|manual|4|current_gt_error；historical_quality:hold_reference_quality|
|x8F5xyUWy9e-01|manual|5|historical_quality:hold_reference_quality|
|zsNo4HB9uLZ-05|manual|4|historical_gt_substantive_error；historical_quality:hold_reference_quality|

## 新空间、修订GT与旧分数兼容性

39张确认新空间逐图追溯来源、JSON指针和底面坐标，分布如下。确认的含义是整个空间体的竖向边界，同时限定墙、顶、底归属；精确顶角尚未完备是独立状态。即使新旧底面相同，也不能由此认证旧完整WQ或3D质量符合新空间。没有捏造顶界，也没有把虚拟裁切边界当成实体墙。

|来源|图片数|来源坐标已核对|顶界待完备|
|---|---|---|---|
|analysis_results/research_input_20260929/floor_scope_update_20261015.json|4|4|4|
|analysis_results/scope_difficulty_audit_20261011/reference_registry_snapshot.json|33|33|33|
|research/quality_scope_model_handoff_20261015/TWO_IMAGE_SCOPE_DELTA.json|2|2|2|

两份用户修订GT对应7y3sRwLe3Va-26、x8F5xyUWy9e-03，新坐标来源已核对，原GT保留。其旧完整评分共10条，未迁移为新版目标成绩，保留待重评。当前原始loader数据与评分源ZIP的逐对象几何核对结果、目标来源及每条原因见参考审计明细。

旧1145条完整分数中，985条仅满足输入／完整参考几何可复用条件，160条仍需参考处理或重评。几何可复用不授予分析资格；再交人数、图片、角色与旧hold限制后，实际当前完整质量为807条：

|条件|当前完整质量记录|图片|人员|
|---|---|---|---|
|manual|768|67|24|
|semi|39|3|18|

旧同目标836条中保留768条，移出68条，新增0条。移出原因组合如下；逐条身份与所有原因保存在[historical_panel_changes.csv](historical_panel_changes.csv)，不能用总量相近代替集合一致。

|移出原因组合|记录数|
|---|---|
|effective_workers_below_3|31|
|complete_target_coordinates_not_equal_or_unavailable；target_floor_changed_or_unknown；top_geometry_pending|26|
|complete_target_coordinates_not_equal_or_unavailable；target_floor_changed_or_unknown|10|
|complete_target_coordinates_not_equal_or_unavailable；effective_workers_below_3；target_floor_changed_or_unknown；top_geometry_pending|1|

## 当前质量与时间的描述分布

下表分条件、难度并列原WQ、A10、B8L2和现用3D IoU百分分。人数、有效图数和缺失与均值、中位数、样本标准差同时报告；“—”表示无有效值，不能填成低分。B8L2是人工偏好版本，尚未宣布唯一最终公式。IoU3D100采用均高棱柱口径，不是任意实体精确IoU。

|条件层|难度|指标|来源记录|有效n|缺失n|有效图|均值|中位数|标准差|
|---|---|---|---|---|---|---|---|---|---|
|ordinary_manual|中等|WQ|318|70|248|7|48.18|45.98|18.04|
|ordinary_manual|中等|A10|318|70|248|7|52.59|53.20|19.05|
|ordinary_manual|中等|B8L2|318|70|248|7|55.58|56.26|18.46|
|ordinary_manual|中等|IoU3D100|318|70|248|7|73.28|76.63|12.24|
|ordinary_manual|困难|WQ|194|53|141|8|52.30|52.02|15.63|
|ordinary_manual|困难|A10|194|53|141|8|58.38|58.19|16.17|
|ordinary_manual|困难|B8L2|194|53|141|8|60.54|59.93|15.82|
|ordinary_manual|困难|IoU3D100|194|53|141|8|75.81|77.73|13.60|
|ordinary_manual|简单|WQ|1241|645|596|52|65.57|66.70|19.07|
|ordinary_manual|简单|A10|1241|645|596|52|70.63|73.66|18.23|
|ordinary_manual|简单|B8L2|1241|645|596|52|72.54|76.07|17.37|
|ordinary_manual|简单|IoU3D100|1241|645|596|52|80.70|84.45|13.17|
|ordinary_semi|中等|WQ|4|0|4|0|—|—|—|
|ordinary_semi|中等|A10|4|0|4|0|—|—|—|
|ordinary_semi|中等|B8L2|4|0|4|0|—|—|—|
|ordinary_semi|中等|IoU3D100|4|0|4|0|—|—|—|
|ordinary_semi|困难|WQ|19|0|19|0|—|—|—|
|ordinary_semi|困难|A10|19|0|19|0|—|—|—|
|ordinary_semi|困难|B8L2|19|0|19|0|—|—|—|
|ordinary_semi|困难|IoU3D100|19|0|19|0|—|—|—|
|ordinary_semi|简单|WQ|463|39|424|3|74.31|80.64|18.18|
|ordinary_semi|简单|A10|463|39|424|3|78.23|84.48|15.88|
|ordinary_semi|简单|B8L2|463|39|424|3|79.89|84.90|14.70|
|ordinary_semi|简单|IoU3D100|463|39|424|3|86.43|88.07|8.26|

表中来源记录是该条件和当前难度来源池的分母，指标有效值可能远少于该分母。难度组任务组成不同，粗均值并不等于难度的独立效应，也不能因某组均值不符合预期而改类。普通难度候选内保留的22处局部人工难度意见分歧没有批量改写为新等级；未审、空审核不当成认可。逐人、逐建筑、场景与同参考同伴比较见明细；原始人员平均成绩可展示，但不自动命名为能力排名。

时间单位为秒，只复用已核对active_time及其有效状态、来源文件和规则，不用lead_time补缺。`active_time_seconds`为通过来源池门后的采集任务有效时间；`target_matched_time_seconds`进一步只保留当前完整质量资格与有效时间共同成立的记录。新空间及修订目标逐作答匹配未知时，旧采集耗时不能解释为完成新目标所需时间。来源图片条件时间仍可描述，但不声称任务已经按新范围重做。

|条件层|时间口径|来源记录|有效n|缺失n|有效图|均值秒|中位秒|标准差秒|
|---|---|---|---|---|---|---|---|---|
|ordinary_manual|active_time_seconds|1753|960|793|115|223.94|131.50|343.19|
|ordinary_manual|target_matched_time_seconds|1753|418|1335|48|188.17|117.50|256.94|
|ordinary_semi|active_time_seconds|486|385|101|40|167.50|93.00|323.67|
|ordinary_semi|target_matched_time_seconds|486|22|464|3|252.05|179.50|231.24|
|special_manual|active_time_seconds|353|214|139|24|304.93|182.00|481.83|
|special_manual|target_matched_time_seconds|353|0|353|0|—|—|—|
|special_semi|active_time_seconds|32|26|6|3|214.46|167.50|203.31|
|special_semi|target_matched_time_seconds|32|0|32|0|—|—|—|
|special_oos|active_time_seconds|210|165|45|9|324.16|255.00|268.11|
|special_oos|target_matched_time_seconds|210|0|210|0|—|—|—|

## 特殊场景与同房比较

门洞、OOS、可标性和范围轴继续单列，不能预设一定低质或不可标。专项保留通过人数与图片门的来源池及有效采集时间；当前完整质量缺失时留空，不把历史分数搬入新空间来补表。各轴交集、分母和缺失见[场景表](by_scene.csv)。

|专项来源层|来源记录|图片|当前完整WQ|完整WQ缺失|
|---|---|---|---|---|
|special_manual|353|31|0|353|
|special_semi|32|3|0|32|
|special_oos|210|9|0|210|

同房比较只用普通manual合格来源池，并坚持已记录关系，不把建筑当房间，也不传递新增同房事实。明确可比且两端均有来源记录的图对为56对。共同人员只有1—2名的比较仍保留；来源图片人数门与图对共同人数是两个分母，各指标可配对数如下。

|指标|合格来源图对|至少一对有效人员的图对|共同人员仅1或2的图对|有效人员配对总数|有效配对数范围|
|---|---|---|---|---|---|
|A10|56|27|8|168|0—9|
|B8L2|56|27|8|168|0—9|
|WQ|56|27|8|168|0—9|
|active_time_seconds|56|5|8|18|0—6|
|iou_3d|56|27|8|168|0—9|

同房明细分别展示两端全体平均、共同人员平均及同人视角差值；小样本不作稳定规律或因果解释。未记录同房不等于确认异房。本轮没有新融合实验，也没有从合格来源池的已有轨迹中删除k=1/2节点。

## 查阅、复现与后续接入

- [筛选工作簿](现有研究数据描述统计_当前口径.xlsx)、[关键可视化](figures/FIGURES.md)、[独立复核记录](INDEPENDENT_AUDIT.md)。
- [当前逐条审计](record_audit.csv)、[当前目标与完整来源指针](current_images.csv)、[来源池与继承暂停](source_pools.csv)。
- [当前完整质量](quality_records.csv)、[待重评](pending_rescore.csv)、[待补人](pending_people.csv)、[各指标覆盖](metric_coverage.csv)。
- [逐人](by_worker.csv)、[逐建筑](by_building.csv)、[同参考同伴比较](peer_comparisons.csv)、[同房逐指标](same_room_pairs.csv)。
- [字段合同](FIELD_CONTRACT.json)、[检查摘要](CHECKS.json)、[逐表字段与CSV清单](FIELD_CONTRACT.json)。

生成入口为`tools/thesis_main/analysis/descriptive_statistics_current_20261015.py`，报告模块为`descriptive_statistics_current_report_20261015.py`。在仓库根目录运行：

```powershell
python -m tools.thesis_main.analysis.descriptive_statistics_current_20261015
```

未来新批次、人员及质量版本继续沿[版本化接入说明](../descriptive_statistics_20261015/EXTENSION_GUIDE.md)与manifest机制。新增数据先走正式loader和必要审核，新质量算法保留独立版本、来源及参考；人数门、旧暂停、目标／时间相容性须动态复核。登记版本不认证几何语义，也不自动兼容所有未来数据。

未重新评分、调参、采集、融合或推送；参考待完备、缺失和稀疏交叉限制结论外推。

具体变更范围、18项测试、复现与截图清理见[交付记录](HANDOFF.md)。

原库存仅底面指标仍在旧快照的`ledger_*`字段与部分指标覆盖表中保留；本次未把尚未完成当前目标／逐份参考重绑定的底面数值升级为新目标完整质量。

归档说明：逐表CSV、合同及交付工作簿入Git；重复聚合的`tables.json`仅留本地，可运行对应生成器重建后再生成工作簿。
