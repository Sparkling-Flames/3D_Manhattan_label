# 人员分类收尾补充：容量与来源匹配的随机参照、上游定向复现

统筹已独立验收本包及多指标、门槛两专题；核验范围、修补及采用决定见[独立验收](INDEPENDENT_ACCEPTANCE.md)。

**2026-10-26数学化衔接：** 本包已经保存旧四套分类的总方差、构成间／构成内方差、η²及匹配随机参照，不再作为待补实验。条件方差公式和权重解释见[统一模型第3.6节](../../../docs/thesis_main/研究模型_人员图片与融合不确定性_20261006.md#36-类别构成与具体成员已有方差分解怎样解释)。此处“当前四套”指2026-10-24的Manual/Semi结构与结构＋Q/T方案；不是随后DSTRUCT或RFUSE的标签。新标签若需同类结果，应先核对共同团队与楼外标签，再单独重聚合，不能给旧表换名。

日期：2026-10-24。对象为真人 v2 的当前四套分类；Manual/Semi 分开，结构与结构＋Q/T 分开。ALL 名单仅用于描述，以下团队实验全部使用目标建筑排除后的标签。没有新增融合、更换正式分类、调参或重算原始质量；定向检查对已选模型做了重新拟合。

## 1. 固定面板随机标签参照

输入为 [`configurations`](../personnel_mixture_comparison_20261022/configurations/README.md) 的 336 个固定背景面板、每面板 12 选 6 的全部 924 队、目标楼外标签及唯一端点。只纳入该方法、层级下 **924 队全员有标签**的面板；部分标签和未知人员不补成常规类。评价指标 B8L2、融合转折数、同源且完整的记录总秒数、失败（全部尝试），每项保留自己的有效分母。常数结果没有可定义的解释方差，故失败只有 3—9 楼的可变支持。

随机单位是**面板内候选人员的整个人员标签**，固定背景 D 原标签不动；在新/旧来源层内置换，保留该面板每类×来源的人数、成员集合、924 个实际结果与每格容量。预先固定种子 `20261024`，目标 99 个不同标签分配；容量只允许更少分配时保留实际不同数，重复抽中不计为独立参照。完整固定设计见 [`DESIGN.json`](random_reference/DESIGN.json)。对每指标计算配比人数向量解释的面板内方差比 η²，逐面板比较实际与参照均值，按面板与建筑保存；下表为先面板后建筑等权的 `实际−随机均值`，不是逐图等权。总方差、配比间及配比内方差按各指标原量纲的平方逐面板保存；同一面板内实际与随机配置格的数量和格容量相同，避免更多类机械增加组间方差的伪优势。逐面板全部实际值、参照分布与 5%/95% 点、不同分配数见 [`PANEL_REFERENCE.csv`](random_reference/PANEL_REFERENCE.csv) 和 [`RANDOM_DRAWS.csv.gz`](random_reference/RANDOM_DRAWS.csv.gz)。

| 当前细层 | B8L2：楼/面板、Δη²、正向楼 | 转折：Δη² | 同源时间：Δη² | 失败：Δη²及支持楼 |
|---|---|---:|---:|---:|
| Manual结构 | 22/231；+0.0497；18/22 | +0.0857 | +0.0507 | +0.1007；9楼 |
| Manual结构＋Q/T | 21/179；+0.0674；19/21 | +0.0751 | +0.3511 | +0.1796；6楼 |
| Semi结构 | 10/59；−0.0031；6/10 | +0.0408 | −0.0437 | −0.0209；3楼 |
| Semi自身结构＋Q/T | 9/31；−0.0257；3/9 | −0.0012 | +0.3067 | +0.0312；3楼 |

完整粗/细层与逐楼结果在 [`SUMMARY.csv`](random_reference/SUMMARY.csv)、[`BUILDING_REFERENCE.csv`](random_reference/BUILDING_REFERENCE.csv)。Semi 结构的转折虽有正方向，只有 6 楼可变；Semi 的 Q 不高于匹配随机参照，不能宣称四套分类都得到普遍 Q 价值。Manual 联合类的时间优势有 20/21 楼支持，仍不能推出可互换或实际组队节约。η² 描述这个固定池的配比区分，不是跨图预测 R²。每面板独立置换标签，同一人员在另一面板可能得到不同随机标签，因此**本参照只检验固定面板的组织价值**，不证明人员类别能跨图或跨楼迁移。旧 `personnel_interchangeability_20261020` 的随机参照检验不同类别设计，未挪用为这四套的结果。

跨建筑响应及连续结构、Q/T 的现有独立对照继续见 [`source_response`](../personnel_mixture_audit_20261022/source_response/SEMI_RESPONSE_CHECKPOINT_ZH.md) 和各 `manual|semi/{geometry_common,qt_common}/PREDICTION_SUMMARY.csv`。本次随机参照没有要求分类必须优于连续量；也没有把固定池 η² 解释成跨楼预测或新人的永久类型。

## 2. 从原答至标签的定向复现

从归档的 `record_expression.csv`、资格字段及画像 `record_index.csv.gz` 重载，按原脚本计算同图同条件/参考的相对原答、个人建筑等权特征、Q/T 支持、稳健标准化、Ward 选定切割和标签。对四套 ALL 与四套目标楼 `7y3sRwLe3Va` 留出折，各检查 62 人的已保存特征、粗细分区和当折所选家族/类数；数值字段逐项相符，分区 ARI 均为 1（允许类别编号置换）。独立按保存候选账查可用模型最低内层误差与一标准误粗切割，并对这八个选择的模型重新拟合/评价 **132 个内侧目标楼**，与保存损失逐行相符。明细见 [`FEATURE_LABEL_SELECTION_CHECKS.csv`](taxonomy_replay/FEATURE_LABEL_SELECTION_CHECKS.csv)、[`SELECTED_INNER_REPLAY.csv`](taxonomy_replay/SELECTED_INNER_REPLAY.csv)。目标楼在折的训练特征及内层选型中均排除；ALL 描述拟合不用于目标楼验证。

复现深度：重执行归档作者的原答处理/选中模型拟合及 132 个内层评价；候选全网格只对保存的选择账独立核算赢家，**没有独立重实现整套嵌套搜索，也没有重跑所有目标楼**。归档脚本移到更深目录后，其 `REPO` 相对路径旧值失效；复现器仅在内存中修正读取根路径，不修改归档原件。当前标签可信度的这个核查不等于分类作用的外部验证。

## 3. 复算与边界

字段合同：`PANEL_REFERENCE` 一行=`panel_id×method×tier×metric`，`valid_teams` 为该指标非缺失团队；`total_variance`、`observed_between_variance`、`observed_within_variance` 与 `random_*_mean` 为原单位平方，`observed_eta2` 与随机分位为无量纲。`RANDOM_DRAWS` 一行=上述键×不同标签分配序号，序号是保存排序，不代表独立实验重复；`possible_assignments` 与 `distinct_assignments` 保留容量。`BUILDING_REFERENCE` 一行=条件×方法×层级×指标×楼；`SUMMARY` 再对楼等权。`FEATURE_LABEL_SELECTION_CHECKS` 一行=方法×条件×ALL/楼外折；`SELECTED_INNER_REPLAY` 一行=该选择×内层目标楼，损失同归档定义。

- 随机设计、全抽样及汇总：`tools/thesis_main/analysis/personnel_supplement_random_reference_20261024.py`。
- 上游定向复现：`tools/thesis_main/analysis/personnel_supplement_taxonomy_replay_20261024.py`。
- 同源时间只用 `recorded_time_total_seconds` 资格内的团队；缺值不设零。失败率以全部尝试为分母，Q/几何只在原可评分团队计算。
- 本包不改变 v2 资格、LOBO 标签、冻结 B8L2、端点或投票门槛；OOS 仍独立。
