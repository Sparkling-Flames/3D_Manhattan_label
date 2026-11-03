# v2.1论文选题、研究覆盖与两刊组织依据

日期：2026-11-02。用途：与导师讨论题目、贡献和章节安排；两套提纲是同一项研究的备选成稿方案。依据当前专题结果、保存的核验记录，以及“研究方法细节12（统筹线程3）”本日对遗漏专题的回复整理。本次不新增实验，不修改原始数据、参考、分类或历史论文文件。

完整提纲：[TOMM中英双语版](论文提纲_TOMM_中英双语_20261102.md) · [IJHCS中英双语版](论文提纲_IJHCS_中英双语_20261102.md)。每个 subsection 均给出目标、内容和图表建议。下文 E01—E24 是两份提纲共用的证据索引。

## 1. 选题判断与拟定题目

**这项研究应作为一篇完整的“方法＋实证”论文推进。** 它已经形成两项相互支撑的方法工作，以及人数、人员构成、任务条件与跨视角表现的多层次实证。最有辨识度的部分，是把真实原答中的空间表达差异，与受控成员重组、局部支持、坐标定位和全局连接接到同一条证据链上。大量实验的价值在于这些相互衔接的发现，而不是实验数量本身。

**共识方法的首要目标是忠实汇总参与者的结构支持。** 输出与参考有多接近，是另一个评价问题。论文应同时报告支持与来源、完整输出状态、参考质量、几何波动和劳动。medoid 的 Q 输赢不能替代共识忠实性的评价；规则如何计票、对应是否正确及连接如何产生，则是共识方法自身需要展示的证据。

### TOMM首选题目

**中文：人工全景三维布局标注的质量评价与结构共识：人数和人员构成的影响**

**English: Quality Assessment and Structural Consensus for Human Annotation of Panoramic 3D Layouts: Effects of Annotator Number and Composition**

中心论证：对同时包含连续几何和离散结构的布局标注，建立可解释的质量测量与可追踪的结构共识方法，并据此解释人数、具体成员和任务条件如何改变输出。

Central argument: Interpretable geometric assessment and traceable structural aggregation reveal how group size, membership, and task conditions shape panoramic layout annotations.

### IJHCS首选题目

**中文：全景布局标注中的个体差异与群体共识：人数、人员构成和任务条件的作用**

**English: Human Variation and Collective Consensus in Panoramic Layout Annotation: Roles of Group Size, Composition, and Task Conditions**

中心论证：人们对同一空间的范围、结构和位置存在不同表达；技术聚合规则会保留、改变或无法连接这些贡献。通过真实作答、受控重组和跨视角比较，说明如何理解和组织复杂几何标注中的群体贡献。

Central argument: People express spatial scope, structure, and location differently; aggregation rules determine how these contributions form collective outputs, with consequences for annotation organization and tool design.

题目使用“结构共识／collective consensus”，正文明确它指独立作答经技术规则形成的结果。人员之间没有实际协商记录，不把离线重组称作协作实验。

## 2. 两刊依据与组织差别

TOMM 官方范围包括多媒体内容分析、创作工具和三维环境。本文应把全景图像、结构化几何标注与三维布局数据生产的联系放在引言前部，并充分交代方法、对照和复现材料。[TOMM作者指南](https://tomccap.hosting.acm.org/guide.html)

作为组织参照，TOMM 的 *Perceptual Quality Assessment of Omnidirectional Images: A Benchmark and Computational Model* 将数据与实验设计、行为分析、计算方法和方法评价连接起来。本稿可以采用这种完整证据链，但测量对象是布局标注的几何质量，不借用该文的主观画质或心理物理效度主张。[Liu等，2024](https://doi.org/10.1145/3640344)

IJHCS 官方范围包括用户行为实证、计算交互、人机交互评价与交互技术设计。因此，本文的人、任务、界面输入和聚合规则需要共同构成研究问题，设计启示应来自已经观察到的行为与结果。[IJHCS期刊范围](https://shop.elsevier.com/journals/international-journal-of-human-computer-studies/1071-5819)

IJHCS 的 *Modeling and Mitigating Human Annotation Errors to Design Efficient Stream Processing Systems with Human-in-the-Loop Machine Learning* 把标注行为解释、实证研究与计算干预接在一起。这支持本稿采用“行为发现—技术机制—组织启示”的组织方式，不要求把现有数据改写为未经测量的心理过程。[Pandey等，2022，作者全文](https://chato.cl/papers/pandey_purohit_castillo_shalin_2022_modeling_errors_human_ml.pdf)

上述是官方范围和实际论文组织方式的参考，不是期刊规定的章节模板。可访问的 TOMM 指南载有旧式模板与页数说明；本提纲不把它当作已核实的现行硬性排版限制。IJHCS 完整作者指南本轮未能直接读取。最终页数、声明与提交格式在正式投稿时对照投稿系统核实。

| 写作决策 | TOMM | IJHCS |
|---|---|---|
| 引言从哪里开始 | 全景三维布局数据的测量、结构汇总和可靠生产 | 人对空间的不同表达，以及技术如何汇总这些贡献 |
| 两项方法的位置 | 各设一章，公式、算法和验证充分展开 | 保留独立方法小节，用图解释其如何观察与组织人的贡献 |
| 人数与构成 | 并列核心结果章 | 并列核心结果章 |
| 原答、人员、Semi、scope | 作为独立实证章，服务输出解释 | 扩展为第一组核心发现，明确任务流程和行为分母 |
| DSTRUCT / RFUSE | 原答结构分类与融合响应的正反分析 | 个体表达与群体作用之间的联系 |
| 同房、门洞、OOS | 跨视角一致性、目标空间与表示适用性 | 任务定义、视角依赖和技术表达约束 |
| 应用与讨论 | 测量与聚合的工程意义、选人和劳动权衡 | 对标注工具、人员组织、审核与辅助编辑的启示 |
| 必须保留的结果 | Q-only、完整状态、升降抵消、参考质量对照 | 同左，另突出连续画像、初始化错误修改及scope行为 |

## 3. 已完成研究与论文位置

当前工作可以归为四组贡献：**几何质量测量、结构支持汇总、人数与成员构成的系统实证、任务条件与人员组织的可迁移认识。** 表内各专题都有论文用途；其中同用途、旧进入策略和部分数学推导适合补充材料，不需要把每个实验包装成独立创新。

| 研究与可采用的发现 | 主要结果或内容 | TOMM位置 | IJHCS位置 | 证据 |
|---|---|---|---|---|
| 数据、参考与目标空间 | 10,439份原始记录；主目标正式Q 8,154份；普通Manual 6,512份、206图、60人；其它空间231份独立扩展 | §3 | §3 | E01—E02 |
| 几何质量评价 | 区域、底边位置、自身方向规整性、均高和高度轮廓互补；总分与局部形状分别解释 | §4 | §4.1 | E03—E05 |
| 组合与响应验证 | 受控扰动、候选组合、真实近分异形、人工个案、D10尺度敏感性 | §4.2—4.3 | §4.1；补充A | E03—E05 |
| 结构共识方法 | 周期对应、独立人员票、位置中位数、来源环；未连接保留形成状态 | §5 | §4.2—4.3 | E06 |
| 原答与人员多维差异 | 范围／结构／定位；相近平均Q下低尾、劳动和审核行为不同 | §6 | §5.1—5.2 | E07—E08 |
| Semi、scope与可靠性 | 冻结v2确认错误机会156次中25次未改；scope回答倾向与正确性分开 | §6.3 | §5.3 | E07 |
| 难度和几何机会 | 当前206图楼外比较：加几何特征后结构简化数量MSE改善约33.3%；Q MAE未改善 | §6.2 | §5.4 | E09 |
| 快慢与困难响应 | 当前K3匹配100对：困难相对简单的慢者转折／短边优势均值−0.0537／−0.0289，53／55对为正；旧63对条件规律保留 | §6.4 | §5.5 | E24 |
| 自然人数与形成状态 | 固定171图20→30人：平均Q +0.500，P10 +2.848，Q标准差 −2.031 | §7.1 | §6.1 | E10 |
| 逐图进程与困难图抵消 | 206图中163图检出既定口径的回顾性平稳段；固定27困难图20→30平均 −0.174，平均绝对变化4.772 | §7.2 | §6.2 | E10 |
| 数学化与抽样精度 | 自然256、历史策略32、精确有限边际；抽样误差与真实团队变异分开 | §3.3、7.3 | §3.3、6.3 | E11 |
| DSTRUCT、RFUSE、联合画像 | 原答出发的结构类别、融合响应反向解释、质量／劳动／结构画像各司其职；两套RFUSE响应类保留正文效果对照 | §8.1、8.6 | §7.1、7.6 | E12 |
| 构成间与同构成内变异 | 当前231面板、40图的DSTRUCT K3 Q方差：构成间15.43%，构成内84.57% | §8.2 | §7.2 | E12 |
| 固定背景的ABC与AC | 当前14/7：147合法事件；67共同可评图，换类相对同类GS +3.767，C−B +6.380 | §8.3 | §7.3 | E12—E13 |
| 具体成员、背景、替换幅度 | 固定A、固定XYZ、背景嵌套分别回答成员与共同背景问题 | §8.3—8.4 | §7.3 | E14 |
| 完整类别联盟 | 403项可执行更新联盟已齐；205图中169图存在Q高于全员的纯类队，人数不同，属事后比较 | §8.4 | §7.4 | E15 |
| 同容量Q-only | 14/7共同Q 68图，结构政策−Q-only +0.0619；换入top7高度重合 | §8.4 | §7.4 | E16 |
| 原答到输出的机制 | 定位中位序变化、过半门槛、对应修正、来源连接；当前30图63事件诊断 | §5.3、8.5 | §7.5 | E13、E17 |
| 同房的公共、个人与操作效果 | 同房公共均Q可预测；控制稳定个人水平后配对残差相关接近零；19图对的指定换人平均方向全部为正 | §9.1 | §8.1—8.2 | E18 |
| 门洞与其它合法空间 | 相机交界、目标空间与闭合表示；584/439双版本、17图共同k=3—14 | §9.2 | §8.3 | E02、E19 |
| OOS与可标性 | 28图1,222条；非正交可辨可标而超出表示；表达／scope／劳动单列 | §9.3 | §8.4 | E20 |
| 选人、停止与实际劳动 | n=5时QT劳动比0.8134、Q差+0.2184；计入历史的停止政策项目劳动比2.1153 | §10 | §9.1—9.2 | E21 |
| 历史进入策略 | 旧角色策略在原图与新增图表现不同，作为策略迁移补充 | §10.1；补充F | §9.1；补充F | E22 |
| 同用途补充 | 当前加用途后均Q预测MAE 5.158→5.379；不支持稳定增益，与同房分开 | §9.1简述；补充E | §8.2简述；补充E | E23 |

### 共同的版本与统计约定

1. **人数不是记录数。** 10,439是库存记录；62为来源ID计数，不直接写成62名独立招募参与者。正式研究按专题说明人员、图片、建筑、目标池和可评支持。8,154＋231＝8,385仅用于声明采用扩展时。
2. **当前与历史分开。** DSTRUCT是当前正向分类，RFUSE反向解释，JOINT/OPPJOINT为联合画像与应用。冻结v2行为证据、旧分类、旧策略和冻结实际团队保留身份。ALL标签用于展示，LOBO标签用于相应楼外评价。
3. **总体现象与有限团队分布分开。** 重组团队反复使用同一批真实原答，不增加独立参与者数量；图片、图对、建筑与团队层的权重按各源表记录。团队抽样误差、图间差异、构成内差异分别解释。
4. **目标与形成状态分开。** 未形成、未连接、自交、不可评、Q缺失、Q=0、OOS分别记录。Lee只有底面时，在共同可比底面比较；不补造其顶面或直接列作完整布局失败。
5. **劳动有来源。** 使用记录劳动或有明确来源的active time，不叫实际交付时间；固定人数不等于固定劳动预算。已有历史与计入历史获取成本两种情景都保留。

### 两个贯穿正文的数学对象

令图片／目标池的固定人员集合为 U，人数 k 的团队为 S⊆U。由同一批原答直接生成 F(S)，分别记录支持、形成状态、Q、几何差异及劳动。自然路径的每个前缀从相应原答重新汇总；不能递归融合已有融合结果。满员时只有一个团队，跨团队变异归零具有有限总体原因。

对既定抽样分布和类别构成 G，使用 Var(Y)=Var(E[Y|G])+E[Var(Y|G)] 区分构成间和构成内变化。它不是图片噪声与人员噪声分解。严格ABC定义 A=D∪X、B=D∪Y、C=D∪Z；X、Y同类，Z异类，三块等大且互不重叠。主文同时报告方向差 C−B 与 GS=(|C−A|+|C−B|)/2−|B−A|，避免把“换类更不同”写成“换类必然更好”。

## 4. 近邻研究怎样比较

正式相关工作表建议固定六列：任务／输出表示、人员对应、支持计数、完整结构连接、评价目标、人员与条件分析。以下各有直接关联，应按具体环节比较：

- [Parting Crowds，CSCW 2016](https://idl.cs.washington.edu/files/2016-CrowdParting-CSCW.pdf)：已有按共同作答模式识别人群与多种合理解释。本文增量落在连续几何＋离散结构、受控重组和形成过程，不主张首次发现“人员有不同类型”。
- [Polygon Consensus，SIGSPATIAL 2016](https://www1.pub.informatik.uni-wuerzburg.de/pub/budig/papers/ACM-SIGSPATIAL-2016_Budig_VanDijk_Feitsch_GiraldoArteaga.pdf)：已有多边形节点聚类与后继连接。比较周期对应、独立人员支持、上下点对和完整来源连接的具体处理。
- [Braylan等，JAIR 2023](https://mattlease.com/papers/braylan-jair23.pdf)：比较结构化标注的分解、汇总与重组；把本任务的对应和全局可连接性写清楚。
- [BiLayout，CVPR 2024](https://liagm.github.io/Bi_Layout/)：比较全景布局的范围歧义。本文的门洞相机交界与闭合表示问题另有几何含义，不全部归入enclosed/extended二分。

## 5. 共用证据索引

链接指向专题入口；具体作图沿入口回到源CSV与对象ID，不把本文或提纲当数值真源。

| ID | 证据入口 | 主要用途 |
|---|---|---|
| E01 | [当前21模块与采用状态](../../research/data/releases/v2.1/research_readiness_20261031/README.md)、[主目标库存](../../research/data/releases/v2.1/quality_inventory.csv) | 当前身份与分母 |
| E02 | [其它合法空间及当前难度接续](../../research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/README.md) | 31池、30目标、28图及受影响下游 |
| E03 | [质量分项、组合与几何解释](../../research/quality/v2_profile_combo_quality_20261021/CLOSEOUT_20261022.md)、[论文案例](../../research/quality/v2_profile_combo_quality_20261021/PAPER_RESULTS.md) | Q定义、近分异形、局部恢复 |
| E04 | [质量独立响应验证](../../research/quality/quality_independent_validation_20261024/README.md) | 受控变形、局部高度、人工案例 |
| E05 | [组合机制候选与独立审查入口](../../research/quality/quality_combination_review_20261016/README.md) | 组合研究与采用状态 |
| E06 | [完整共识方法收尾](../../research/fusion/fusion_paper_closeout_20261022/README.md)、[v2.1方法共同面板](../../research/data/releases/v2.1/fusion_common_panel/COMMON_SCENE_SUMMARY_OLD_V21.csv) | 对应、票、定位、连接及medoid／Lee |
| E07 | [人员连续画像与可靠性](../../research/workers/personnel_profiles_composition_20261020/PROFILE_FINDINGS.md)、[当前可靠性表](../../research/data/releases/v2.1/personnel_descriptive/reliability.csv) | 冻结行为与当前人员来源 |
| E08 | [原答标法](../../research/workers/personnel_marking_patterns_20261020/README.md)、[当前逐人难度表](../../research/data/releases/v2.1/q_only_exchange_20261031/diagnostic_20261031/WORKER_DIFFICULTY_CURRENT.csv) | 结构差异与人员条件响应 |
| E09 | [当前可计算难度比较](../../research/data/releases/v2.1/difficulty_computable_comparison/README.md) | 几何机会与楼外比较 |
| E10 | [当前逐图人数进程](../../research/workers/image_response_v21_20261101/README.md)、[自然曲线](../../research/data/releases/v2.1/natural_results/NATURAL_CURVES.csv.gz) | 固定支持、低尾、波动、逐图抵消 |
| E11 | [统一数学模型](研究模型_人员图片与融合不确定性_20261006.md)、[256与精确边际采用入口](../../research/statistics/pro_return_review_20261023/population256_20261027/README.md) | 有限总体、抽样精度和数学说明 |
| E12 | [更新分类、构成和合法事件](../../research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/README.md)、[构成源表](../../research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/composition/primary/ALL_METHOD_COMPARISON.csv) | DSTRUCT、RFUSE及15.43%／84.57% |
| E13 | [当前半队30图63事件解释](../../research/data/releases/v2.1/half_team_current_exceptions_20261031/README.md) | 成员、结构与连接机制 |
| E14 | [完整构成研究](../../research/data/releases/v2.1/simulated_population_evidence/README.md)、[背景与替换幅度](../../research/data/releases/v2.1/simulated_population_evidence/exchange/README.md) | 固定A、固定XYZ与背景变化 |
| E15 | [完整类别联盟收尾](../../research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031/README.md) | 全员、纯类与联盟 |
| E16 | [Q-only公平对照](../../research/data/releases/v2.1/q_only_exchange_20261031/README.md)、[不同成员诊断](../../research/data/releases/v2.1/q_only_exchange_20261031/diagnostic_20261031/README.md) | 政策增量与成员重合 |
| E17 | [五条下游与形成链](../../research/data/releases/v2.1/full_chain_downstream_20261030/README.md) | 当前机制、同房、策略与成本 |
| E18 | [同房原始问题与全部层次](同房研究_原始问题结论与证据索引_20261101.md) | 公共均值、个人、配比、调整 |
| E19 | [门洞584／439当前结果](../../research/data/doorway_review_20261030/screen439_results_20261031/RESULTS_ZH.md) | 相机交界、筛选、空间与人数 |
| E20 | [OOS统计](../../research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/oos_statistics_20261024/README.md)、[语义复核](../../research/difficulty/difficulty_mechanisms_v2_20261020/scope_closeout_20261022/OOS_REVIEW_20261024.md) | 可辨、可标、表示适用性 |
| E21 | [共同支持的选队、停止与成本](../../research/data/releases/v2.1/full_chain_downstream_20261030/README.md) | Q／QT与历史劳动 |
| E22 | [历史角色策略的当前参考结果](../../research/data/releases/v2.1/current_policy_results/README.md) | 原图／新增图分开 |
| E23 | [当前同用途比较](../../research/data/releases/v2.1/room_type_similarity/COMPARISON_OLD_NEW_SUPPORT.csv)、[核验记录](../../research/data/releases/v2.1/room_type_similarity/INDEPENDENT_CHECKS.json) | 补充研究及无稳定增益 |
| E24 | [当前快慢×难度匹配表](../../research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/speed_difficulty/CURRENT_SAME_PEOPLE_SUMMARY.csv)、[固定与更新支持说明](../../research/data/releases/v2.1/full_chain_downstream_20261030/README.md) | 当前100对与旧63对分别解释 |

## 6. 成稿取舍

先保留两项方法、人数、构成、人员条件、同房及门洞的主结果；每章用一幅组合图或一张核心表形成论证。完整参数、候选分类、每名人员画像、每图曲线、完整机制图库和历史敏感性移入补充材料。OOS保留一组真实场景和统计摘要。同用途用一个短段落报告当前结果，再给补充材料。

两刊都不以“我们做了许多实验”为贡献句。TOMM按“定义和实现了什么、验证了什么、发现了什么”组织；IJHCS按“观察到什么人类表达、技术规则怎样作用、对工具和组织有什么含义”组织。现有证据足够据此进入完整初稿写作。
