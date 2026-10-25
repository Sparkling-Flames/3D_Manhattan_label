# 本轮新增人员分类：条件响应、几何方向及跨条件 scope 联合

本目录是 `20261025` 研究轮次的**实际候选标签与原答用途结果**。底层仍为真人 **v2**。读取的 main 提交为 `972857b2b3f548316be215400e42d6ef6e639250`。分类冻结在目标融合结果计算之前；本目录本身不包含新融合结论。

## 1. 已经保存什么

- `CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz`：20 个有限候选 × ALL/22 个楼外折，逐人标签、已知状态、缺失原因、输入条件。62 人历史名单中，当前正式原答有 60 人；W019/W026 无本输入正式历史、W022 只有 2 条 Manual，保留未知。
- `CANDIDATE_CLASS_DEFINITIONS_COMPLETE_ALL.csv`：ALL 人员名单与历史特征中心。`...ALL_LOBO.csv.gz` 保存每折定义；不同折不按 C1/C2 直接合并类别含义。
- `CURRENT_POOL_CLASS_CAPACITY.csv.gz`：每张图、每个方法的当前真实成员与类别容量。
- `STRICT_ABC_CAPACITY_BY_N.csv.gz`、`STRICT_ABC_CAPACITY_SUMMARY.csv`：给定 n 的可行 m；容量是可行性，不表示已经计算所有团队。
- `HELDOUT_RAW_DISTANCE_BY_IMAGE.csv.gz`、`HELDOUT_RAW_DISTANCE_SUMMARY.csv`：在目标建筑未参与建类的条件下，原答类内/类间差异。包含同角点数子集；这是原答用途检验，与融合换类结果分开。
- `WARD_HIERARCHY_PARENT_LINKS.csv`：同一 Ward 树下 K3/K4 子类到 K2 父类的精确映射。
- `NEW_OLD_LABEL_CROSSWALK_SUMMARY.csv`：与已有 V3_BEHAVIOR、V3_JOINT_QT 的楼外名单对应程度。新方法不是把旧类别重新命名。
- `../features/HISTORY_FEATURES_ALL_LOBO.csv.gz`、`HISTORY_FEATURES_WITH_SCOPE_ALL_LOBO.csv.gz`：每人每折的连续历史特征与机会分母。
- `../features/RAW_CONDITION_RESPONSE_RECORDS.csv.gz`、`RAW_ORIGINAL_PAIR_DISTANCES.csv.gz`：逐原答特征及同图实际原答距离。其原始几何沿输入 snapshot 的 object_id 定位，避免重复大几何。

## 2. 有限候选网格与新增之处

|家族/对照|输入|实际候选|与旧方案的区别/用途|
|---|---|---|---|
|DSTRUCT|Manual|K2、K3、K4|按当前简单/困难分层的非冗余转折、短边、冗余点及参考角点对应；表达困难相对简单的响应|
|DBOUNDARY|Manual|K2、K3、K4|有符号顶界、底点误差与尺度/高度的困难响应；观察位置方向而非只看角点数|
|DJOINT|Manual|K2、K3、K4|困难结构、困难边界、分难度 Q、分难度记录时间四域等权联合|
|MSDGEOM|Manual+Semi|K2、K3、K4|Manual 困难响应加 Semi 自身结构、上下界和尺度；区别于旧 XCOND 的无难度分层面积/高度主特征|
|MSDGEOM_SCOPE|Manual+Semi+scope|K2、K3、K4|加入有来源与机会分母的范围回答倾向及困难−简单差异；不是范围正确率|
|DSTRUCT_AXIS2|Manual|中位二分|以困难图非冗余转折响应为可解释连续轴，检验较大可换块|
|DBOUNDARY_AXIS2|Manual|主轴中位二分|困难上下界/尺度方向主轴，阈值只在训练建筑形成|
|MSDGEOM_SCOPE_AXIS2|Manual+Semi+scope|主轴中位二分|五域联合主轴；检验增大类别容量是否帮助区分大块替换|
|Q_MEDIAN2|Manual|中位二分|同支持人群的总体历史 Q 简单对照|
|Q_HARD_MEDIAN2|Manual|中位二分|同支持人群的困难历史 Q 对照|

共 20 个配置。它们是**有依据的一轮有限比较**，没有穷举所有算法，也没有按目标图融合效果反复调 K。Ward K2/K3/K4 使用同一棵树，方便检验细分增量；轴二分是另一个可解释方法，不冒称天然类型。

## 3. 历史输入与缺失

7302 条当前正式池原答：Manual 6356 条、Semi 946 条。分类结构/质量历史使用当前可评分池中的普通图片、固定简单/中等/困难分层；门洞仍在替换容量和原答用途表中单列，不混入困难历史。历史被筛除者不会因本表恢复正式组队资格。

Manual 的几何/难度支持要求：至少 12 张普通图、3 栋楼；简单至少 5 图/2 楼；困难至少 4 图/2 楼。Semi 总体支持至少 6 图/3 楼。Semi 困难历史只有极少记录，**没有制作 Semi 困难适应特征**。DJOINT 还要求简单至少 5 条、困难至少 4 条可靠来源的时间，ALL 有 56 人；其余几何方法 ALL 为 59 人。

scope 由 `../features_scope/` 独立代码整理：最新 v2 ledger 及 286 条与旧问卷精确对应的 `oos` 原字符串恢复。该恢复仅用于历史特征，不改变质量资格或 GT。scope 在同图片×条件×来源内形成回答残差，再组合有支持的 Manual/Semi；普通场景回答倾向与困难−简单差异组成一个域。不以缺机会当零，不把拒绝多解释为判断正确。

ALL 描述名单只用于看人；所有目标图片用途均取该建筑的 LOBO 名单，Manual 和 Semi 的目标建筑记录同时排除。scope 同样先排除目标楼。源数据的同图中心化不跨建筑，所以预先计算同图中心化不会使用被排除建筑来估计其他建筑特征。

## 4. “实际怎么标”的初步可解释角色

下述是 **ALL 描述中心**，不是目标图质量效应。

- DSTRUCT_K2 的较多转折类共 12 人：W002、W015、W017、W021、W027、W102、W109、W112、W115、W122、W126、W130。困难图中其非冗余转折比同图中位数平均多约 1.92 个，常规类 47 人为少约 0.46 个。新增细节是否必要仍需具体结构机会解释，不能把“多”直接判对。
- DBOUNDARY_K2 的偏向收缩/上下界下移角色为 W008、W011、W029、W030、W033、W035、W124；其底点、顶点同图相对残差方向与大类不同。此类 ALL 只有 7 人，某些图真实容量更少，所以保留大块容量更充足的轴二分对照。
- DJOINT_K3 将相对常规群再分为普通速度与较快角色，并保留困难图高 Q/较多转折角色。K4 把高 Q 类拆出 7 名新批人与 5 名旧批人，来源关联很强，因此不能只凭这次细分就宣称普适的细类增量。
- MSDGEOM_SCOPE_K2 的第二类 13 人为 W001、W002、W012、W027、W102、W104、W109、W112、W115、W122、W126、W130、W133。整体困难转折响应较高、范围拒绝残差较低；K4 进一步分出 W001/W012/W104/W133 的边界/尺度响应子群与 9 人较多转折子群。它包含几何与范围的共同角色，不能只命名为“高能力”。
- DSTRUCT_AXIS2、DBOUNDARY_AXIS2、MSDGEOM_SCOPE_AXIS2 的 ALL 容量均为 30/29；阈值和每折投影载荷可追溯。人数接近是训练侧中位二分的结果，不是靠目标图表现强行重新分配人员。

## 5. 如何读原答距离

原答对照分 `all_pairs` 与 `same_corner_count`。后者要求两个原答具有完全相同的原始角点对数，可观察类别是否区分同点数下的位置/尺度，而不只区分点数。角点匹配使用特征分析用的 9° 方位匈牙利对应，匹配外比例单列；这不是融合内部对应参数，也不改变原环序。

每张图中：类内距离先按类别取均值再等权汇总，类间距离先按无序类别对取均值再等权汇总。然后分别按图片和建筑汇总；不会让一个大类别的大量成员对自然压过小类。位置有符号历史是建类输入，原答距离使用两个真实原答的绝对差。原答距离更大不代表更差，距离更小也不代表更接近 GT。

## 6. 容量与真正实验范围

严格 ABC 中 D/X/Y/Z 两两不重叠，三块 X/Y/Z 均 m 人，总队 n 人：需要至少 n+2m 个真实可用人，源类至少 2m、目标类至少 m。容量表同时列出只使用有标签成员为背景以及允许未知标签成员作共同背景两种最大 m，主实验可固定其中一种口径。

例：包括门洞的 Manual 库中，DBOUNDARY_AXIS2 的 n14/m9 在 146 图/22 楼有容量；n14/m10 在 64 图/20 楼有容量。MSDGEOM_SCOPE_K2 的 n14/m9 有 34 图/10 楼。**这些是容量，不是实验结果或已穷尽团队。** 同一最终成员集合只需融合一次；实际抽样、端点和事件覆盖由主实验目录保存。

## 7. 复现顺序

代码都在 `code/`：

1. `build_condition_response_classes.py`：使用 prior_population 的 `inputs/`，生成首 12 个 Ward 配置、原始新增边界特征与历史中心。
2. `build_axis_controls.py`：用 `HISTORY_FEATURES_ALL_LOBO.csv.gz`，生成 4 个轴/质量对照。
3. `build_scope_increment.py`：合并 `features_scope/SCOPE_FEATURES_ALL_LOBO.csv.gz`，生成 3 个 scope Ward 和 1 个 scope 轴配置。
4. `describe_candidate_support.py`：合并 20 方法、保存真实容量、楼外同图原答距离。
5. `assemble_classification_links.py`：汇总中心、父子关系和旧方案对照。

读取每个脚本的 `--help` 可见实际路径参数。参数、输入 SHA256、阈值、投影与缺失规则均保存；不依赖未保存的环境内聚类状态。相同候选的融合用途采用主实验结果，不在本目录自行宣布优胜。
