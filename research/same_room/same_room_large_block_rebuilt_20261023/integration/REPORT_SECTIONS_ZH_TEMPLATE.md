# 最终综合报告结构与证据绑定（编辑工作稿）

本文件供正式报告填入已完成统计，不预填尚未结束的端点结果。待采用路径为 `research/same_room/same_room_large_block_rebuilt_20261023/REPORT_ZH.md`。人员主报告和旧同房报告的接续入口分别见本目录的插入稿与修正补丁。

## 开篇：先给实际研究判断，再给来源身份

开篇按正式结果回答三件事：哪些混合条件出现跨类幅度差异；哪些中文类别方向贡献了它；哪些结果随视角、背景或实际成员改变。所有判断分别落到条件效应和可追溯表，不把“幅度更大”替换成“升质”。然后用下表说明三套产物的身份。

|内容|本轮身份|采用边界|
|---|---|---|
|main中的既有同房设计、独立AC补算和已保存普通图片研究|沿用并按需要重聚合|原实验的支持、团队与计权保持原身份；不代替丢失的新大块原件|
|本轮strict ABC设计、端点、几何与条件汇总|新设计、新融合及随后重新汇总|使用固定main和冻结资格/算法；不声称恢复旧精确设计或旧111,054端点|
|已存人数自然/策略路径与完整04C|原精确设计上的分析重建|无新增顺序或融合；bootstrap程序为本轮新实现；与ABC计数分开|

正式成果数量取完成回执，设计数量取冻结manifest；正在运行或尚未合并的产物不写成已交付。正文结果页不混用旧10A数值与本轮新设计。

## 一、纯块、混合背景与替换比例

先给普通Manual结构主表，行依次为全部、D空纯块、D非空混合、混合中m/n<1/2、=1/2、>1/2。并列Q同类幅度、对称跨类幅度、额外幅度、C−A、C−B、建筑等权额外幅度、正向图对比例、六端点Q共同支持和全部尝试失败。联合Q/T和门洞/范围差异另外列小表。

数据源：`results/OVERALL_CONDITIONS.csv`；逐n/m：`results/N_M_CONDITIONS.csv`；精确事件：`results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz`。`within=|B−A|`；`cross=(|C−A|+|C−B|)/2`；`extra=cross−within`。各项先在两个视角上取规定平均，再在同一图对/方向/n/m配置内汇总。Q的三种幅度使用六端点共同可评支持，失败使用全部尝试分母。

正文必须保留一项分项例证：必要转折、短转折、近共线分段或参考召回实际怎样变化；如结构无变化而底面/上界定位改变，则直接如此解释。几何距离取 `geometry_summary/GEOMETRY_CONDITIONS.csv`，明确单位为相机高度h；同角点数且冻结对应唯一的距离子域，与异数/失败诊断分开。

**填写判断：** `{{纯块与混合条件的实际发现}}`。不同子域的均值差不写作规模效应；规模和背景使用第三节共同锚点证据。

## 二、到底是哪类换哪类

按实际历史角色方向列主表：分类方案、source/target role key、源→目标中文意义、各折原类编号、实际人员覆盖、n/m、D构成、Q C−A/C−B/额外幅度、转折/短转折/冗余变化、底面/方向/高度分项、同语义共同Q/T劳动比、降质>5分、新增与恢复失败。主要结果可取普通混合与少于半队两层；完整层次保留CSV。

统计来源：`results/DIRECTION_RESULTS.csv`。可读整理：`direction_tables/DIRECTION_READABLE_ZH.csv`。各折原始类与历史中心：`direction_tables/FOLD_DIRECTION_ROLES_MEMBERS.csv`；背景与精确事件连接：`direction_tables/DIRECTION_BACKGROUND_MEMBER_INDEX.csv.gz`。中文意义由楼外中心解释，TURN2、TURN3、JOINT等family key保留；不能跨折直接合并M1/J1。

本轮实际输入只提供匿名人员编号Wxxx，沿用编号，不补造姓名。成员并集仅说明覆盖范围；单队及机制图标注读取事件里的D/X/Y/Z。各方向Q/T共同支持可能不同，先报告各自效果，再对有限共同支持作比较，不能按不同子域的劳动均值排优劣。

**填写判断：** `{{主要贡献方向与相反或近零方向}}`。分类的组织价值可以成立而无需超过连续Q/T；历史结构角色也不保证每张目标图上都增加结构。

## 三、固定A的换人数路径与固定替换块的背景路径

分两张表，避免把两种问题混合。

1. 真正固定A和n，增大m：并列 `C_large−C_small`、`B_large−B_small`、两者净差。A必须两个视角均为相同team_key，见 `fixed_A_endpoint_verified`/路径回执。canonical X/Y交换时按 `nominal_A_role` 恢复真实路径身份，不能直接把设计字母A当作固定锚点。
2. 固定同一实际X/Y/Z，D沿同一成员前缀增加：比较可行的纯块、半队、首次少于半队及最大D。这里A/B/C本身都会因加背景变化，因此分别列A/B/C质量变化和额外幅度变化。纯块到最大D的变化回答背景与比例共同作用，不是只改m。

来源：`anchor_paths/ANCHOR_PATH_TRANSITIONS.csv.gz`、`ANCHOR_PATH_EFFECTS.csv.gz`、`PATH_PAIR_CONFIG_SUMMARY.csv.gz`、`PATH_OVERALL_RESULTS.csv`。质量与分项比较使用同一实际转移的12个端点引用共同支持；同端点在不同阶段重复是保留锚点的设计事实。失败表 `PATH_FAILURE_LOWTAIL_PAIR_CONFIG.csv.gz` 用全部尝试，缺失不补零。比较标签可重叠，同一物理转移已经去重；不同标签结果不再相加当作独立实验数。

**填写判断：** `{{规模扩大来自C变化还是B变化以及背景路径的实际条件}}`。m范围由合法容量决定；本轮严格ABC的2m源类+m目标类约束不同于仅AC容量，不能把m9/10没有合法ABC写成算法无效。

## 四、建筑、声明组计权与具体成员

建筑等权、物理图对等权、声明组后建筑等权并列；对应强调不同研究对象，不选唯一正确均值。先给逐栋留一效应/正向比例范围，再单列删除uNb9QFRL6hY后的混合与少于半队结果、剩余图对与建筑。取 `LEAVE_ONE_BUILDING_OUT.csv`、`EXCLUDE_UNB_SPECIFIC.csv` 与 `OVERALL_CONDITIONS.csv`；不要手工用原均值扣除一栋楼。

成员表每人两行：宽背景构成匹配、精确D匹配。列Wxxx、楼外角色、相关图对/楼、匹配后图对/楼、事件保留比例、匹配前效应、包含/缺席效应、缺席后正向比例。来源 `sensitivity/MEMBER_MATCHED_SUMMARY.csv`、`MEMBER_SELECTION_AND_CAPACITY.csv`、`MEMBER_FOLD_ROLES.csv`。角色family key可由building+target_class接 `design/CLASS_ROLES_AND_MEMBERS.csv`；来源方向原类也保留。没有合法缺席对照的人员保持容量/设计受限。

**填写判断：** `{{哪些方向是较宽成员支持哪些依赖有限子域}}`。结果只支持对应合法匹配子域；不把其中少数成员的正向缺席效果概括为整个结果不依靠关键成员。原始到匹配后变化同时受支持和匹配层计权改变，不能当作删除该人的因果贡献。

## 五、历史Q接近子域及结构—位置解释

先列三块历史Q最大差≤2与≤5的真实支持、独立实际目标块、XYZ块、D集合，再在相同pair/direction/n/m和进一步exact D的支持上比较近Q子域与其覆盖的较宽事件集。两种集合嵌套；不是去除历史Q后的因果效应。

来源：`history_q/HISTORY_Q_DOMAIN_SUPPORT.csv`、`HISTORY_Q_COMMON_SUPPORT_RESULTS.csv`、`HISTORY_Q_MATCHED_STRATA.csv.gz`。并列B8L2额外幅度、有符号Q、转折/短转折、底面/方向/高度，以及唯一对应的BEV/顶点距离。每个指标的有效匹配层、图对和建筑均单列；几何与Q支持不同则明确各自分母，不强行用一个量代替另一量。

G236旧三锚点共享目标块、历史较多转折成员在目标图也可能简化等证据，只在可取得的旧精确证据身份下引用。它说明历史倾向与具体任务响应不同，不作为42次独立人员重复；更不据有限近Q子域否定旧广图结构表达差异。本轮机制案例只用本轮真实事件/几何，并与旧案例区分。

**填写判断：** `{{近Q域还保留哪些结构或位置区别及其范围}}`。不把旧约0.242分或本轮近Q效应除以总体效应，推算历史Q解释百分比；联合Q/T是独立对照支持。

## 六、已存人数过程：路径抽样与建筑差异

本节引用已完成的 `population_stability/README_ZH.md` 及其独立专题，不重算新ABC。自然困难10→20保留均Q、逐图P10、逐图SD、失败，并列固定图片的完整路径重抽与固定路径的建筑整块重抽；不能把前者窄区间解释为跨建筑稳定。前段策略取四策略共同支持及其策略/自然配对路径，Manual/Semi分开。

自然曲线：`population_stability/results/KEY_NATURAL_INTERVALS.csv`；策略：`KEY_POLICY_EARLY_EFFECTS.csv`。筛选键包含condition/layer/difficulty/panel/interval或phase/metric/weighting/resampling。每个k先在每图有效路径上算均值、线性插值P10和ddof=1的SD，再图等权或楼等权；失败保留全部尝试。SD不足两条有效路径时缺失，bootstrap无效轮次单列。

后段可以称平台，准确表述为：“后段平均变化较小，现有结果未显示明确持续升高或下降；低尾与成员波动仍改善。” 不写已经证明完全不变。时间只采用 `results/time_semantics/` 的单队全已知、单一语义、双端同语义和共同Q支持；四策略直接比较用 `FOUR_POLICY_COMMON_TIME_EFFECTS.csv`，其共同域没有新做bootstrap。已弃用旧时间列不可用于成本结论。

本节已完成的可采用段落见 `population_stability/PERSONNEL_REPORT_INSERT_ZH.md`、`TIME_SEMANTICS_CORRECTION_ZH.md`、`FOUR_POLICY_TIME_COMMON_ZH.md`；不重复填造bootstrap结果。

## 收尾：采用表与可接续入口

最后用一张“研究问题→结果→敏感性/反例→支持→精确表/代码→采用判断”表收束。区分主文结论、条件性补充、机制例和不再推进。三个历史口径修正依本目录patch原样保留：共同可评支持上的源端阈值、2.006分层算术劳动比、严格零阈值49/120与旧50/120来源差异。

此编辑稿只定位证据和叙述职责；正式报告须删除所有双花括号占位内容。字段来源和正式文件状态由 `REPORT_EVIDENCE_BINDINGS.csv` 与 `TEMPLATE_SCHEMA_CHECK.json` 登记，不能把技术烟测的数值填入正式结论。
