# v2.1 全合法目标的新增候选分类：实际形成与冻结

本阶段读取提交 `a476461d7ede8db95da43de4139e612c05e618bc`，已实际完成 **13 个新候选、ALL＋22 个楼外折、18,538 条人员标签登记**。标签先于本轮新团队效果比较冻结；它们是用于整体比较的候选，不把下面的 K3 展示默认定为最后推荐。

原 v2.1 官方 20 个前向方法原样保留作基线；其中部分虽有 ALL/楼外标签，历史仍限原主目标。新增候选接入全部 294 个合法目标池、8,385 份正式记录的库存，**按目标空间分开计算特征与同伴比较**。门洞和特殊范围保留库存字段，本批新人员历史仅使用 ordinary_manual/ordinary_semi；未将这些边界恢复为正式组队资格。

实际历史集合核对：官方 baseline20 的共同历史仍是“非门洞且有正式难度”，共 7,583 条，包括 111 条特殊范围辅助历史（Manual 66、Semi 45）；新候选的 7,703 条为双方共有 7,472 条普通历史＋231 条新目标，未使用那 111 条辅助历史。这是历史域、目标库存及权重共同调整的方案比较，不能把变化仅归因于新增目标。原正式池资格不变；逐对象与代码依据见 [阶段02历史域核对](../stage02/BASELINE_NEW_HISTORY_SCOPE_CHECK.json)。

## 1. 新方法的动机与实际配置

|家族|注册 K|怎样建类|ALL 容量|
|---|---|---|---|
|TARGET_DSTRUCT|2、3、4|合法空间总体结构＋有正式目标难度的困难结构/困难−简单；承接旧 DSTRUCT，但修正多目标权重并接入新空间总体历史|47/12；10/37/12；4/10/33/12|
|OPPSTRUCT|2、3、4、5|总体结构、确有几何挑战目标的结构、相对于连续结构机会的个人表达响应|49/10；11/38/10；5/11/33/10；1/5/10/33/10|
|OPPGEOM|2、3、4|结构总体/机会响应＋顶底界、面积和高度总体/机会响应|50/9；7/43/9；4/3/43/9|
|OPPJOINT|2、3、4|结构响应、边界尺度响应、Q总体/低尾/响应、来源内时间总体/响应，四域等权|48/8；19/29/8；26/19/3/8|

结构和几何方法各折均有 59 人；OPPJOINT 各折 56 人。没有为了大块实验强制类均衡，也没有因 K5 拆出 1 人类就删除整个候选；有限小类按其容量研究，不能构造不合法的同类 B 块。

### 连续结构机会的具体定义

对每个目标参考提取三个可计算量：

- log(1＋max(非冗余转折数−4,0))；
- log(1＋边界自遮挡数量 H)；
- log(1＋短转折边数量)。

在目标楼之外的训练目标中，按目标在图内等权、图在楼内等权、建筑等权计算各轴中位数与 p85−p15；退化时用标准差，再退化用 1。各轴标准值截到 [−3,3]，等轴相加并除以 √3。

这个分数是**可计算结构机会**，不宣称替代正式图片难度。它使无正式难度的其它合法目标仍能提供“有何结构机会、人员如何响应”的信息；没有把另一空间的简单/中等/困难复制过来。

每人的响应斜率为：历史同伴残差与机会分数的加权协方差/机会分数加权方差。权重每折重算，依次保证同一人员的记录在目标内、目标在图内、图在楼内、楼在历史中等权。无变化机会的响应保留未知，不补零。原答结构、边界和尺度公式沿用冻结定义；新增几何实现与 60 份不同主目标原答的官方 v2.1 已存字段逐项对应，最大差约 9×10⁻¹⁶。

## 2. 支持、缩放和时间

普通历史至少 12 图/3 楼。TARGET_DSTRUCT 的困难/简单支持沿用 4 图/2 楼和 5 图/2 楼；未知难度目标只进总体历史。OPPSTRUCT 的挑战域要求至少 4 图/2 楼，响应要求机会方差大于 10⁻⁵、至少两个实际机会水平。OPPJOINT 时间域要求至少 12 个有可靠正计时的图片、3 栋楼及可估响应。

行为和质量先减图片×参考目标×条件的同伴中位数。时间先取 log，再在同组加 origin 与 time_source 分层中心化。这里的时间是库存来源明确的记录劳动时间，不是新的生产耗时测量。

每个家族独立按字段 median/p85−p15 缩放、截断 3，每域最多 PCA2，域 RMS 归一化并等权，然后 Ward 同树切所有登记 K。K 没有按本轮目标团队 Q 调整。OPPJOINT 的低尾是采用同一历史分层权重的经验 p20；这与旧版按原答行直接取 p20 的口径不同，已在配置中说明。

## 3. 可见的人员角色：用于看人，效果仍用对应楼外名单

以下仅展示 ALL 的 K3，完整 K2—K5、全部楼外折和缺失原因已保存。

|候选|类别及 ALL 成员|已形成的历史解释|
|---|---|---|
|TARGET_DSTRUCT K3|C1：W001/W028/W030/W031/W032/W035/W037/W103/W105/W125；C2：37 人，详见表；C3：W002/W015/W017/W021/W027/W102/W109/W112/W115/W122/W126/W130|C1 在复杂机会简化较多且近共线冗余偏多；C2 为较常规表达；C3 在结构机会下保留较多非冗余转折|
|OPPSTRUCT K3|C1：W001/W028/W030/W031/W032/W037/W103/W105/W113/W125/W127；C2：38 人；C3：W002/W021/W027/W102/W109/W112/W115/W122/W126/W130|C3 的挑战目标同伴转折残差约＋1.31，C1约−0.51、C2约−0.33；区分以连续结构机会响应为依据|
|OPPGEOM K3|C1：W008/W028/W029/W030/W031/W035/W037；C2：43 人；C3：W002/W021/W027/W109/W112/W115/W122/W126/W130|C1 兼有复杂结构简化、底界偏下和较小底面；C3 更多转折且顶界相对偏上；C2 较接近同伴中心|
|OPPJOINT K3|C1：19 人；C2：29 人；C3：W002/W102/W109/W112/W115/W122/W126/W130|C1/C2 总体历史 Q 接近，但来源内时间和结构响应不同；C3 历史 Q 与结构响应较高，计时并不自动更快|

C3 等编号只能在其方法及折内解释。表中 Q 是同图同目标同伴残差的历史均值，不能当人员绝对 Q；几何偏移也不是已确认错误。历史“更多转折”需要在具体机会中区分必要结构、参考省略细节与冗余，本阶段不以正残差自动判好。

## 4. 实际文件与接入

- [NEW_LABELS_ALL_LOBO.csv.gz](NEW_LABELS_ALL_LOBO.csv.gz)：13 方法的完整标签；按 method＋heldout_building＋worker_id 关联。
- [NEW_CLASS_CENTERS_ALL_LOBO.csv.gz](NEW_CLASS_CENTERS_ALL_LOBO.csv.gz)：逐折中心、人数和精确成员。
- [NEW_CLASS_DEFINITIONS_ALL.csv](NEW_CLASS_DEFINITIONS_ALL.csv)：便于阅读的总体成员与中文解释。
- [NEW_PERSONNEL_LABELS_AND_MISSING_ALL.csv](NEW_PERSONNEL_LABELS_AND_MISSING_ALL.csv)：逐人缺失原因。
- [NEW_CANDIDATE_REGISTRY.csv](NEW_CANDIDATE_REGISTRY.csv)：全部候选/折的容量和描述性 silhouette。
- [HISTORY_FEATURES_ALL_LOBO.csv.gz](HISTORY_FEATURES_ALL_LOBO.csv.gz)：实际用于建类及事后解释的历史特征和支持。
- [RAW_TARGET_RESPONSE_RECORDS.csv.gz](RAW_TARGET_RESPONSE_RECORDS.csv.gz)：8,385 份逐原答合法目标关联、现行 Q、来源时间、原答几何和同伴残差。
- [CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json](CANDIDATE_CONFIG_BEFORE_TEAM_RESULTS.json)、[TRANSFORMS_ALL_LOBO.json](TRANSFORMS_ALL_LOBO.json)：域、门槛、权重、缩放与投影。
- [OLD_V2_TO_CURRENT_V21_LABEL_CHANGE_SUMMARY.csv](OLD_V2_TO_CURRENT_V21_LABEL_CHANGE_SUMMARY.csv) 及对应逐人 transitions：旧 v2→官方 v2.1 的名单变化。
- [NEW_TO_OFFICIAL_BASELINE_OVERLAP_SUMMARY.csv](NEW_TO_OFFICIAL_BASELINE_OVERLAP_SUMMARY.csv) 及对应逐人 transitions：新目标条件候选与原同 K 家族的成员关系；最优重叠映射仅用于看名单，不替代实验语义。
- [build_target_aware_candidates.py](code/build_target_aware_candidates.py)、[describe_candidate_labels.py](code/describe_candidate_labels.py)：实际运行代码。

本批可直接对各目标池构造严格 ABC 或另列直接 AC，按池内类别容量决定 n/m。下一环节是把所有有依据的候选放进同一主要条件比较，再依据用途选主方法和补充方法。此处没有预判 DSTRUCT、OPPSTRUCT 或某个 K 必然胜出。

