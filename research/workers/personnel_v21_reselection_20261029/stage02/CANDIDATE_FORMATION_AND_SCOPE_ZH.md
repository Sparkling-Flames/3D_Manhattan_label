# 阶段02：v2.1 候选分类形成、真实成员与容量

本阶段承接 [旧形成与选型流程回顾](../stage01/OLD_FORMATION_AND_SELECTION_ZH.md)，读取同一提交 `a476461d7ede8db95da43de4139e612c05e618bc`。已实际形成并冻结新增候选，保留现有 v2.1 基线，供后续全局换人/换类比较。**这里不提前选择优胜，也不默认 K3、n18/m7 应继续主用。**

## 1. 本轮已有可用于全局比较的 45 个登记

|来源|登记数|实际处理|
|---|---:|---|
|v2.1 官方前向分类|20|复用当前参考和评分下的 DSTRUCT、DBOUNDARY、DJOINT、MSDGEOM、scope 联合及轴对照；不重新做相同计算|
|v2.1 原主目标 RFUSE|4|保留作为有效训练范围对照|
|V3 结构与联合 Q/T 粗细层|4|复用已接续版本；同分区的粗细层仍能登记，但其差异不能当独立方法增量|
|新合法目标/结构机会前向分类|13|TARGET_DSTRUCT K2/3/4；OPPSTRUCT K2/3/4/5；OPPGEOM K2/3/4；OPPJOINT K2/3/4|
|新目标等权 RFUSE|4|TARGET_RFUSE_GEOM K2/3；TARGET_RFUSE_GEOMQ K2/3，已实际重新拟合|

合并标签是 [MAIN45_LABELS_ALL_LOBO.csv.gz](../classification/MAIN45_LABELS_ALL_LOBO.csv.gz)：64,170 行，45 方法×ALL/22 楼外折×62 人名册。人数、参数和类数是候选定义；每个方法在哪些图片上实际能换多少人，由容量和团队实验另定。45 不是 45 个完全不同的分区，更不代表全部算法穷举。

旧 31 方案中，本轮实际接续 28 个：20 前向、4 V3 粗细、4 原主目标 RFUSE。旧 XCOND_GEOM、XCOND_GEOM_QT、XCOND_PAIRED 三方案在当前 v2.1 正式目录尚无对应楼外重拟标签，本轮保留它们的旧结果与未采用原因，未把 v2 名单改称 v2.1 重测。现轮已有 MSDGEOM/Scope 等 Manual＋Semi 候选，它们和旧 XCOND 是不同形成方法，不能合并身份。

新增 13 前向候选的完整特征公式、支持与类容量见 [新增目标条件分类说明](../classification/NEW_TARGET_AWARE_METHODS_ZH.md)。其标签登记为 18,538 行；几何/结构方案每折 59 人，Q/T 联合每折 56 人。新增 4 个反推候选为 5,704 行，每折均有 59 人可建类。

## 2. 相比旧流程，这次实质改变了什么

### 接上合法空间，而非把不同空间当作人员错误

全部库存是 294 池、8,385 份正式原答，保留 image、condition、reference_id 和版本。新前向历史在此库存中使用普通条件 7,703 份，其中新准入目标 231 份全部进入总体/结构机会历史；门洞和特殊范围记录仍在库存而不进入本批新拟合。

同伴中心改为图片×目标×条件，计时另加来源批次及 time_source。每个人先在同一目标内平均，再将目标在图内等权、图片在楼内等权、建筑等权。目标楼在两条件历史中完全排除。未有正式难度的其它空间不继承主目标三档难度。

TARGET_DSTRUCT 承接旧结构公式，同时纳入合法其它目标的总体历史；难度分层只用正式目标分级。OPPSTRUCT/OPPGEOM/OPPJOINT 用目标自身转折、自遮挡 H、短边构成连续机会，研究人员如何随机会改变表达、位置、尺度、质量与时间。它们支持对新增目标直接建模，不需要先补齐一套人工三档标签。

这是方案级比较。当前官方 baseline20 的原答历史实际仍采用“非门洞且有正式三档难度”规则，共 7,583 条：7,472 条普通历史加 111 条特殊范围辅助历史（Manual 66、Semi 45，来自 e9zR4mvMWw7-16、jtcxE69GiFV-18）。本批新前向候选的 7,703 条则是相同 7,472 条普通历史加 231 条新准入目标，排除上述 111 条特殊范围辅助历史。因此目标库存、图内目标权重及辅助历史域同时改变，不能把 TARGET_DSTRUCT 的名单或用途变化单独归因于 231 条新增记录。正式目标池与组队资格没有因建类而改变。依据是官方 `refit_v21_condition_classes_20261028.py` 的实际规则、`refit_v21_scope_axes_20261028.py` 对共同历史的复用，以及本轮逐对象集合核对；详见 [历史域比较](BASELINE_NEW_HISTORY_SCOPE_COMPARISON.csv)、[111条辅助历史](BASELINE_ONLY_SPECIAL_HISTORY_RECORDS.csv) 与 [读取回执](BASELINE_NEW_HISTORY_SCOPE_CHECK.json)。

### 新反推修正的是目标权重，旧扩展并没有混合不同目标中心

实读旧 RFUSE 程序和扩展输入后发现：扩展的 `group_id=pool_id×n`，旧程序确实按此中心化。**不同空间没有被合并成同一个同图×n中心。** 需要修正的是权重：旧程序在每图内将所有“目标×人数”组等权，因此有 5 个人数点的空间比只有 1 个人数点的空间得到 5 倍权重。

TARGET_RFUSE 保留既有目标分组、实际自然随机端点、嵌套留楼 ridge、alpha=0.1/1/10、响应域、PCA、Ward K2/K3，单独改为建筑→图片→目标→可行人数等权，之后按实际自然顺序出现次数分配权重。全部重拟已完成，没有新增融合，也没有看本轮替换结果改类。

该训练库存有 28,312 个去重端点；28,002 个可入模型，209 池/200 图/22 楼。其它准入目标提供 331 个可拟合端点/10 池；9 张图在训练中同时有多个合法目标。其它小于 n10 的池未被当前 n10/12/14/16/20/24 训练设计覆盖，应明确其缺口，不能说 RFUSE 历史已覆盖所有 31 个新池。

目标等权后，GEOM K2 的全部 23 折分区与原扩展完全一致；GEOM K3 有 9 折变化，GEOMQ K2 有 5 折、K3 有 13 折变化。ALL 容量依次为 55/4、21/34/4、52/7、18/34/7。这些变化有实际计算依据，但不意味着改变更多的候选必然更好。

证据与复现：

- [反推配置](../classification/target_rfuse/CONFIG_BEFORE_TEAM_RESULTS.json)
- [实际训练池库存](../classification/target_rfuse/TRAINING_TARGET_INVENTORY.csv)
- [每个目标×n的原/新权重](../classification/target_rfuse/EXACT_OLD_NEW_GROUP_WEIGHTS.csv.gz)
- [全部楼外标签](../classification/target_rfuse/LABELS_ALL_LOBO.csv.gz)
- [原扩展到目标等权的名单变化](../classification/target_rfuse/OLD_EXTENDED_TO_TARGET_EQUAL_SUMMARY.csv)
- [实际运行代码](../classification/code/build_target_weighted_rfuse.py)

## 3. 每类到底有哪些人、怎样标：统一解释表已保存

[CLASS_ROLES_ALL_LOBO.csv.gz](../classification/CLASS_ROLES_ALL_LOBO.csv.gz) 有 **3,054 个“方法×折×类别”行，ALL 132 个类**。每行保留精确 members、人数、原建类条件及共同历史特征。

共同历史中心仅作并列解释：给所有已冻结标签使用同一套 v2.1 目标条件历史，**不重新拟合或篡改旧类**。这样能看清类别在非冗余转折、近共线点、Q/低尾、来源内时间、底界、顶界、面积和高度上各有什么差异。RFUSE 还独立保留其真实融合响应中心，不能拿个人原答中心替代响应系数。

跨折不要直接合并 C1/C2/C3。表中可直接使用：

- `turn_rank_asc`：总体转折历史从少到多，1 最少；
- `hard_turn_rank_asc`、`challenge_turn_rank_asc`：正式困难或可计算挑战机会下的转折排序；
- `q_rank_asc`、`time_rank_asc`、`area_rank_asc`、`height_rank_asc`、`redundancy_rank_asc`；
- `size_rank_desc`：1 为该训练折人数最多的类；`dominant` 为布尔标记；
- `k`、各轴 `range_*`、并列层数 `rank_*_levels`：保留实际差异大小与并列，排名不自动表示差别很大；
- RFUSE 的 `own_fusion_*` 及 `response_*_rank_asc`：自身模型中的结构/几何/Q响应。

这些角色由目标建筑之外的历史定义，没有利用目标替换效果排序。聚合时可先按“转折序位＋是否人数最多类”对齐，再分质量、时间和范围等用途。全部指标大小仍应与排序一起看。

便于主文引用的文件：

- [每类成员与共同历史中心精选表](../classification/CLASS_MEMBER_CENTER_EXTRACT_FOR_MAIN_REPORT.csv)
- [ALL角色表](../classification/CLASS_ROLES_ALL.csv)
- [完整共同历史中心](../classification/CLASS_MEMBERS_COMMON_HISTORY_CENTERS_ALL_LOBO.csv.gz)
- [精简逐折角色表](../classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz)
- [新旧人员转换](../classification/OLD_V2_TO_CURRENT_V21_WORKER_LABEL_TRANSITIONS.csv.gz)

例如当前 DSTRUCT K3 的 ALL 三类为 8/39/12 人；在共同历史解释中，较小的 8 人类兼有困难结构简化与近共线冗余，39 人类更接近常规表达，12 人类非冗余转折与历史 Q 较高。OPPSTRUCT K3 为 11/38/10 人，较多转折类成员有所收窄；OPPGEOM K3 为 7/43/9 人，额外区分底界向下、底面较小与复杂结构简化的组合。OPPJOINT K3 的 19/29 两类平均历史 Q 接近，但时间和结构机会响应不同，8 人类历史 Q/结构响应较高。它们不是只按总角点数或临时 Q 阈值命名。

## 4. 小类是用途范围，不是“不合法分类”

严格 ABC 要求来源池至少 2m 人、目标池至少 m 人、整池至少 n＋2m 人。这约束的是**具体图片和方向**，不要求总体每个类都很大。

一个四人目标类，在某图四人齐全、来源至少八人且池内 N≥n＋8 时，可以完整换入 m4。若 N=35，严格设计理论上可做到 n27/m4；“小类只有四人”不自动把团队人数限制为 n12。反方向以这四人为源类，则最多 m2。全员队 n=N 没有非零 m 的严格三队空间，属于设计容量，不是分类无效。

本阶段对当前全部 294 池、45 方法、所有实际出现的有向类对已计算**69,890 行合法容量**，没有按旧 n18/m7 提前筛掉其它条件：

- [各图实际类容量与成员](../classification/CLASS_CAPACITY_BY_CURRENT_POOL.csv.gz)
- [每方向的 n/m 容量](../classification/STRICT_DIRECTION_CAPACITY_BY_CURRENT_POOL.csv.gz)
- [人数和规模支持汇总](../classification/METHOD_CAPACITY_SCOPE_SUMMARY.csv)

以 206 个普通 Manual 主目标池为例，下表是“存在至少一个可行有向类对”的容量，**不是已经完成的实验，更不是同一语义方向的效果覆盖**：

|方法|某方向可换 m7 的池|n18/m7 可行池|n24/m4 可行池|n30/m2 可行池|
|---|---:|---:|---:|---:|
|DSTRUCT K3|132|122|150|120|
|TARGET_DSTRUCT K3|128|124|150|120|
|OPPSTRUCT K3|97|94|150|120|
|OPPGEOM K3|60|59|149|120|
|OPPJOINT K3|124|109|149|120|
|TARGET_RFUSE_GEOM K2|0|0|74|116|
|TARGET_RFUSE_GEOMQ K3|139|116|150|120|

这解释了为何“旧特定方向 33 张图”和“全局还有许多其它合法条件”可以同时为真。新目标普通 Manual 有 30 池；DSTRUCT/TARGET_DSTRUCT/OPPSTRUCT K3 各有 14 池可支持某方向 m2、2 池可支持 m4；TARGET_RFUSE_GEOM K2 有 6 池可支持 m2，最大 m3。小空间需要按真实容量安排，也能另列没有同类 B 的直接 AC。

## 5. 本阶段已经收尾与后续接口

已完成：旧流程恢复，13 新前向＋4 目标等权反推的实际建类，ALL/楼外名单及变类记录，45 方法共同历史解释和逐目标真实容量。新增标签、参数与代码均已保存，并实际检查 gzip 可读取；一次阶段历史文件尾部不完整已用原输入重算缺失历史折并补存，已冻结标签不变。

未在本阶段做结论：哪个候选应为主方法、哪个方向最好、n/m 的实际效果。这些必须由全局共同条件比较及新增团队结果回答，不能靠类容量、silhouette、历史 Q 或本章中的直观解释代替。也不会因一个小类或一个反例预先取消候选。后续以固定标签、真实容量和明确的共同背景开展比较，正向、负向、无差异与失败均保留。

