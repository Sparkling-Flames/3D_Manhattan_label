# AC 人工顺序接续：独立数值、支持、计权与残余机会复审

## 核心结论

**AC 核心数值接续通过独立复审；通过数值验收不能表述为全部 AC 条件均已获得同等人工处理机会。** 本复审未导入本轮 AC 生产脚本，以冻结源表、前批自动/辅助输出和独立聚合代码核对身份、权重与缺失值。30 项核心检查全部通过；1,867 条分项/层级均值翻向记录、29,559 条统计单位贡献闭合，最大绝对差为 `7.105427357601002e-15`。60 条涉及 Q 的统计记录另从完整下层支持复算，包含两版合计 1,030 个单位值。详见 [PEER_CHECKS.json](PEER_CHECKS.json)、[PEER_CHECKS.csv](PEER_CHECKS.csv) 和 [独立下层重算值](Q_REVERSAL_LOWER_LEVEL_VALUES_RECALCULATED.csv.gz)。

**RAW3 其它合法目标、n=m=4、纯类 1→2 的翻向，当前应写为 7/16→13/16 可评支持上的 `+15.212662→−13.675955`。** 三个残余 C 端均无来源环，且没有可复用的已确认人工顺序。进一步以合法 Q 范围作缺失值界限分析：即使允许这三个端点全部或部分补入，且新 Q 在 `[0,100]` 任意取值，固定条件均值仍只能落在 `[-20.722480, -1.972480]`。因此，无需新增人工排序来判断这个固定条件的负方向能否被三端补入扭回；实际完整 16/16 均值及同等人工处理机会仍不能宣称已知。详见 [残余与界限回执](RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json)。

本复审未生成顺序、未融合、未重评分、未增加团队、未变更坐标，也未把未可评旧 Q 当作 0。57 组仍是定向辅助案例。下列结论均限定于实际检查的条件，不外推所有无环端点。

## 1. 核心验收覆盖什么

|检查内容|独立复核结果|证据|
|---|---|---|
|全部均值翻向目录|独立从各族原/新汇总逐项枚举，1,867 条身份、统计字段、原值、新值一致|[目录复核分布](CATALOGUE_CENSUS_RECHECKED.csv)、核心回执|
|单位分解与权重|全部 29,559 条单位贡献满足恒等分解；图像、楼栋、池的单位名称与冻结聚合合同一致|核心回执；上级 `ac/REVERSAL_UNIT_CONTRIBUTIONS.csv.gz`|
|60 条 Q 记录|从完整原下层数据独立重算单位身份、值和均值，原/新共 1,030 个单位值一致|[Q 下层重算值](Q_REVERSAL_LOWER_LEVEL_VALUES_RECALCULATED.csv.gz)|
|改变分析行的真实事件来源|209 条分析行解析为 377 条“条件×事件”引用、153 个不同事件；逐项核 A/C 团队、成员、方向、原/新两端 Q 和差值|核心回执；上级 `ac/Q_REVERSAL_EVENT_TEAM_TRACE.csv.gz`|
|原共同事件与缺失语义|9 个实际受影响池的 14,665 条方法事件中，原已可评端点 Q 和原共同 C−A 值不变；新增可评事件的原 ΔQ 继续为空|核心回执|
|别名去重|完整事件集合与精确分数权重同时核对；不能仅因新增事件相同就断定为同一完整估计量|下述 RAW3 与 funnel 证据|

60 条 Q 记录包含有符号质量差、背景端点质量变化、批次差、方法绝对幅度差、三段路径分项，以及不同权重与视图别名。它们不是 60 个独立实验，也不是 60 次同一种 C−A 质量效应翻向。`Q_REVERSAL_EVIDENCE_ALIASES.csv` 中 30 个新增事件集合标签只说明新增证据重叠，不能替代完整队列和权重的去重证明。

核心追溯表聚焦改变的分析行。它不能单独证明某个条件内所有失败对手都已处理。全 60 条件的注册/可评/残余机会清单由上级 AC 验收输出另外报告；本目录中的额外机会审查专门覆盖下述 RAW3 完整 16 事件。

## 2. 图像等权、楼栋等权、池等权必须分别说明

冻结主分析先在池内聚合事件、再在图内聚合池。图像等权直接平均图效应；楼栋等权先平均同栋图效应、再平均楼栋。新增一个楼栋时，两种权重可产生不同方向。以下两项均是**楼栋等权翻向、图像等权仍为正**，应标为“条件变化”，不能合并成无条件的质量方向结论。

|其它合法目标、方向 1→2|图像等权：原→扩展|楼栋等权：原→扩展|可评图数 / 楼栋数 / 事件数|
|---|---:|---:|---|
|OPPSTRUCT_K3，完整类不等人数，全部外部背景|`+5.005676→+0.776540`|`+5.937436→−2.707188`|`9→10 / 4→5 / 9→10`|
|TARGET_DSTRUCT_K3，完整类不等人数，D=0|`+18.628660→+6.142643`|`+18.628660→−3.100873`|`4→6 / 2→3 / 5→7`|

第一项新增 `wc2JMjhGNzB-26`，图效应为 `−37.285685`，同时新增一个楼栋。第二项新增 `uNb9QFRL6hY-67`（`+5.462497`，已有楼栋）和 `wc2JMjhGNzB-26`（`−43.121281`，新楼栋）。原可评图的事件值保持。完整池级和图级来源分别见 [池明细](BUILDING_ONLY_FLIP_POOL_DETAILS.csv)、[图明细](BUILDING_ONLY_FLIP_IMAGE_DETAILS.csv)、[汇总](BUILDING_ONLY_FLIP_SUMMARIES.csv)。

方法比较与 execution funnel 的冻结合同是池等权。部分历史字段名包含 `image`，但不能据字段名更换统计单位。主目标当前一图一池时，两种计算可数值相同；本轮已明确其真实池等权定义。strict bridge 同样保留冻结的池等权合同。

## 3. 两个小支持翻向的完整事件解释

### 3.1 RAW3 纯类：九条统计行来自同一完整事件与权重

条件为 `other_admitted / V21_DSTRUCT_RAW3_K3 / n=4 / m=4 / D=0 / 1→2`，包含两个已注册池，各 8 个事件：

|池|注册事件|原可评→扩展可评|扩展池均值|
|---|---:|---:|---:|
|`rPc6DW4iMge-22__manual__other_space_11`|8|7→7|`+15.212662`|
|`wc2JMjhGNzB-26__manual__other_space_25`|8|0→6|`−42.564572`|

原来只有第一池可评；扩展后两池等权，因此总体从 `+15.212662` 变为 `−13.675955`。在原共同事件上，Q 与 C−A 值全部保持。新池的 A 端原 Q 缺失，人工辅助后为 `67.381095`，六个原来已有 Q 的 C 端因而组成新的可评对。这里的 `C−A` 是新支持上的质量差，不能写成 A 从 0 分提高到 67.381095。

三个主视图 `A_fixed_n_pure_class`、`whole_equal_fixed_n_pure_class`、`whole_equal_fixed_n_all_m_pure_class`，成员面板的 `class_count_preserving_members_D_not_fixed` 均值，以及 funnel `1/3→2/3`，拥有完全相同的 16 个注册事件和可评权重。本条件一池一图一栋，图像与楼栋等权也完全一致。因此主视图六条、成员均值两条、funnel 一条合计九条翻向记录是一份统计证据。

精确权重为：原七个可评事件各 `1/7`；扩展后这七个各 `1/14`、新池六个各 `1/12`。这一结论同时核对未受影响的 rPc22 原 shard，未只比较九个变动池或六个新增事件。见 [完整别名核验](RAW3_PURE_CLASS_EXACT_ALIAS_VERIFICATION.csv)、[完整事件及精确权重](RAW3_PURE_CLASS_COMPLETE_EVENT_WEIGHTS.csv)、[16 事件原/新状态](RAW3_PURE_CLASS_FULL16_EVENT_STATUS.csv)。

### 3.2 主目标 OPPSTRUCT，n=28、m=1：新增一图导致均值翻向

`primary / OPPSTRUCT_K3 / n=28 / m=1 / 1/3→3/3` 的完整注册队列只有两池、14 事件。原 `VFuaQ6m2Qom-03` 七个可评事件的池均值为 `−0.052785`；新增 `x8F5xyUWy9e-08` 六个可评事件的池均值为 `+63.332843`。两池等权后为 `+31.640029`，可评图数由 1 变 2，可评事件由 7 变 13。

新增六个事件共享 A 团队 `x8F5xyUWy9e-08__manual__0b13997fd3__fb261248c4a2c1b66d0b`；A 原 Q 为空，辅助 Q 为 `30.829880`，六个 C 原来已可评。余下事件 `ddeb875af2fd21eeb924c85d` 的 C 只有 3 个节点，排序不能补足当前完整布局合同。这一条件的 `ALL_CANONICAL_DIRECTIONS` 恰好选中同一完整队列，所以该行和具名方向行也是别名。见 [完整队列](FUNNEL_N28_M1_EXACT_ALIAS_COHORT.csv)、[新池全部七事件](FUNNEL_N28_M1_X8_ALL_EVENTS.csv)。

## 4. RAW3 三个残余 C 端：没有现成顺序可直接复用

|变量|事件 ID|C 团队完整身份|节点|固定 A Q|
|---|---|---|---:|---:|
|q0|`a63415f78c6f8edd39b5ac22`|`rPc6DW4iMge-22__manual__other_space_11__7264832710c1375c6311`|11|47.898696|
|q1|`554c5483aab8ad2fdb45b595`|`wc2JMjhGNzB-26__manual__other_space_25__f75d0212c66c3f1117cf`|8|67.381095|
|q2|`dfd1596297c00f22af034a1d`|`wc2JMjhGNzB-26__manual__other_space_25__0ea94e0e255592c4cb9c`|8|67.381095|

三端均为 `no_connection / needs_manual_order`；其 Q 继续为空，不能按节点不足排除。冻结 prepared 已包含全部点对、票数、成员与参考，与原 stage03 端点的节点数、票数、成员和参考绑定一致。三个几何彼此不同。

对当前已确认 57 组及历史 `order_import.json` 的 33 个 accepted 顺序分别做同图、完整节点身份与坐标、忽略局部 ID 的精确点对集合核对，均无可复用顺序。具体为：wc2-26 在 57 中只有三个 7 节点组，两个残余 C 各有 8 节点；rPc22 无 57 同图组。历史 33 中这两张图均无顺序。既有顺序核查限于仓库登记，不假定未导出的浏览器本地内容存在。详见 [顺序复用检查](RAW3_RESIDUAL_ORDER_REUSE_CHECK.csv)、[三端原始冻结记录](RAW3_RESIDUAL_FROZEN_ENDPOINT_RECORDS.json)。

三端未进入 57 队列有源码依据：冻结 `close_current_ring_audit_20261104.py` 仅选主半队、指定同房、Q-only、变化联盟，以及普通主目标满员的已定位无环诊断；AC 引用本身不构成入队条件。三端的当前引用分别只有 AC，或 AC 加其它目标自然路径，均未命中上述队列选择规则。原诊断已将它们标为 `current_no_source_ring_nodes_ready`，原有顺序匹配为 0。见 [原诊断三行](RAW3_RESIDUAL_CURRENT_LINKED_DIAGNOSTIC_CHECKS.csv)、[原实际引用九行](RAW3_RESIDUAL_CURRENT_INVENTORY_LINKS.csv)、[冻结队列源码](source_cache/close_current_ring_audit_20261104.py)。

这说明**没有发现这三端漏用适用的已确认顺序**，同时也说明**该 AC 条件的人工处理机会不完整**。不能把前者改写成后者已满足。若要得到三端真实 Q 或完整 16/16 的确切均值，仍需要新人工判断与实际几何验收；本次方向结论可由下一节界限判断完成，无需追加队列。

## 5. 合法 Q 界限：方向可确定，缺失值仍未知

冻结 `working_models.py` 的 `checked()` 要求 IoU 分量 `I∈[0,1]`，其它损失非负。评分公式为：

\[
Q=\frac{100I}{I+\operatorname{pooled}+I(g+l)},\qquad \operatorname{pooled},g,l\ge0;
\]

当 `I=0` 时返回 0。因此，对实际可评 Q，`0≤Q≤100`。这是源码定义域，不是根据本批最高最低分推定的经验范围。完整源码、Git blob 与 SHA256 见 [working_models.py](source_cache/working_models.py) 和 [源文件清单](source_cache/EXTRA_CODE_SOURCE_MANIFEST.json)。

令 q0、q1、q2 分别对应上表三个仍缺失的 C 端 Q，保持其它 13 个事件和 A 端固定。如果三端全部变为可评，各池均有 8 个事件，总均值为：

\[
\bar\Delta Q_{16}=\frac{-331.559681653471+q_0+q_1+q_2}{16}.
\]

于是完整 16 事件均值的合法范围为 `[-20.722480103342, -1.972480103342]`。另外，将每个端点设为“仍不可评”“合法下界 0”“合法上界 100”三种状态，共枚举 `3³=27` 个边界组合，覆盖全部 8 种可评子集以及各自的线性极值点。每种固定可评子集内，均值对未知 C Q 是正权线性函数，因此边界枚举覆盖了合法区间内全部可能取值。27 个组合全部为负，下界和上界与完整 16 的界限一致。

**边界表中的 0 和 100 是数学极值，绝非实测补值；空白 q 表示该端点仍不可评并按该指标的支持合同不进入均值。** 原缺失 Q 没有改变，实际结果表也未加入模拟值。[27 组合表](RAW3_PURE_CLASS_MISSING_Q_BOUNDS_SCENARIOS.csv) 逐列保存 q0/q1/q2 的完整团队身份与状态；[回执](RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json) 保存公式、定义域出处、变量映射、假设及不能据此作出的结论。

可采用的结论是：“固定 RAW3 纯类 n=m=4 条件在当前定向辅助支持上由正转负；剩余三个 C 端即使在合法域内全部或部分补入，也不能将该固定条件均值扭回正向。”完整实际均值、人工处理公平性、各缺失几何是否可修复，以及其它无环条件的方向均不能由此推断。

## 6. 逐条判定与复现

|命题|判定|依据及适用范围|
|---|---|---|
|原共同事件的质量数值是否被人工分支改变|保持|9 池全部原可评端点与原共同 C−A 不变；不把新可评事件称为同端点提分|
|两个仅楼栋等权翻向条件是否代表图像等权也翻向|条件变化|图像等权仍正；需保留权重、背景、目标范围和支持图数|
|RAW3 三个主视图、成员均值与 funnel 是否为多次独立发现|需改写|完整 16 注册事件及两版权重完全一致，九条统计行是一份证据|
|主目标 OPP 28/1 的小支持均值翻向|条件变化|新增一图、六个可评事件；原图事件值不变；具名方向与 ALL 是别名|
|RAW3 扩展支持的实际效应幅度|幅度变化|`+15.212662→−13.675955`，明确 7/16→13/16、1→2 图|
|RAW3 残余三端会不会把这个固定条件均值扭回正向|保持负向|在现有值和合法评分域不变的前提下，所有可评子集及未知 Q 取值的上界仍为 −1.972480|
|RAW3 完整 16/16 的精确效应与同等人工处理机会|尚不能判断 / 条件未满足|三 C Q 仍缺，三端未获人工排序；界限分析不能替代真实结果或对称处理|
|是否需要为上述方向判断重选团队或再派人工排序|不需要|已由合法域界限完成固定条件方向判断；不能为了恢复原方向继续抽样|

核心复审脚本：`tools/thesis_main/analysis/peer_review_manual_order_ac_acceptance_20261104.py`。从 HOHONET 根运行：

```bash
python tools/thesis_main/analysis/peer_review_manual_order_ac_acceptance_20261104.py
python tools/thesis_main/analysis/peer_review_manual_order_ac_acceptance_20261104.py --residual-only
```

第一条核验核心 30 项，第二条只核验三端绑定与界限，不重复核心全表。脚本依赖前五批及 AC 验收源快照；全部写入本目录，不改变生产结果。完整大 pool/link 缓存可以不打包，本目录 `inputs/` 保存已核查条件的全部注册池/链接子集及源 SHA256。额外 rPc22 原 shard 必须保留，它证明未变动池也被纳入完整 16 事件核对。

源版本统一为 `Sparkling-Flames/3D_Manhattan_label` 的冻结提交 `ac395e703d1fef573d1ef3e105df0286d62a0468`。三条 prepared 通过不可变 GitHub ZIP 的字节范围读取，验证条目头、CRC 和提取文件 SHA256；未重新下载并计算整个约 294 MB 分片集合的 SHA256，回执已明确该验证边界。它们是原已保存的中间节点，本轮没有重放融合。

### 可核查原始来源

- Sparkling-Flames（仓库维护账号），2026，《working_models.py》，GitHub 研究评分源码；Git blob `fb9c5788f4e2ab5035343a45426ca966eb6bc4ac`。[冻结原文](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ac395e703d1fef573d1ef3e105df0286d62a0468/research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py)。
- Sparkling-Flames（仓库维护账号），2026，《close_current_ring_audit_20261104.py》，GitHub 人工队列选择源码；Git blob `c6dbdf5bcf16b3c2db73a4b91e5971a98cdb3c88`。[冻结原文](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ac395e703d1fef573d1ef3e105df0286d62a0468/tools/thesis_main/analysis/close_current_ring_audit_20261104.py)。
- Sparkling-Flames（仓库维护账号），2026，《order_import.json》，GitHub 历史 33 项 accepted 人工顺序登记；Git blob `40dc17ed0f8337ab3154e3b9cc7fa06c33e13ade`。[冻结原文](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/ac395e703d1fef573d1ef3e105df0286d62a0468/analysis_results/consensus_delivery_20261008/order_import.json)。
- 原事件 shard、端点 part、prepared 分片及三条诊断/九条实际引用的精确路径、版本、源摘要和提取校验分别见本目录 `source_cache/EXTRA_FROZEN_SOURCE.json`、`ENDPOINT_PART_DIRECTORY.json`、`RAW3_PREPARED_SOURCE_MANIFEST.json`、`RAW3_EXISTING_DIAGNOSTIC_EXTRACTION.json`。这些是项目数据与源码，不冒称期刊论文或会议文献。
