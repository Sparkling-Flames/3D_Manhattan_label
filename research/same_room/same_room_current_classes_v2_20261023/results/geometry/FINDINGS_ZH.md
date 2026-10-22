# 同房人员调整的几何重复性：补充结果

交付说明：以下为完整研究的发现与工作文件定位。精简包不附全部15,165行面板大摘要，提供 `GEOMETRY_PRIMARY_M1_PANEL_STRATA.csv.gz` 的578行主预算小表和全部已交付层级结果；包内直接复画命令以 `../../code/engine/README.md` 为准。没有把省略的工作缓存当作缺失研究。

## 最值得保留的判断

**相同类别配比不能消除具体成员引起的定位变化；改变类别配比会略提高“两视角都明显改变”的比例，但单视角响应仍占很大部分。** 这里衡量每个视角内部替换前后对应底角点的位置变化，不能将两视角的位移幅度相似解释成同一物理方向移动。

完整新增原生团队池由主研究计算。本模块没有再融合或重新评分；它计算了 **1,954 个有限面板、153 个直接采用图对、2,140,619 个精确人员调整**的跨视角几何摘要。每一调整都在两个视角以完全相同的成员变更执行。主类别为当前采用的 `V3_BEHAVIOR`；其内部 `selected_family=TURN/JOINT` 原样保留，内部 JOINT 联合 E/R/G 结构行为轴，不是独立 `V3_JOINT_QT` 质量/时间分类。

## 同支持的一人调整比较

普通 Manual、replicate 0、人数为共同容量的截断中点。总体主层同构成替换支持114图对，跨类替换支持118图对。为把两种调整放在相同人员容量、人数与可行类别面板上比较，下表取同时存在两种调整的 **269个面板、114图对、58图、17个可重叠声明组、11栋建筑**。这是同面板内可行调整分布；严格固定实际背景的另项比较见主研究的 same_background 结果。

| 调整 | 实际调整事件数 | 两视角对应距离都可算的事件数 | 层级加权可算率 | 两边都≤0.02h | 只有一边>0.02h | 两边都>0.02h |
|---|---:|---:|---:|---:|---:|---:|
| 同类别配比，替换一名具体人员 | 35,348 | 30,236 | 84.08% | 39.81% | 37.99% | 22.19% |
| 跨类替换一人，增加高转折类人数 | 47,712 | 39,539 | 79.65% | 35.29% | 37.13% | 27.58% |

后三列以两视角均有唯一同点数几何对应的事件为分母，h为相机高度。先在有限面板内求比例，再按面板→直接图对→原声明组→建筑等权；因此加权率不等于表中事件数直接相除。声明组可重叠，不当作独立房间样本。

跨类替换使“两边都明显改变”从 **22.19%** 到 **27.58%**，增加 **5.39个百分点**。17个声明组中12组上升、1组相同、4组下降；G002、G078、G237的增加较明显，G015、G057、G202则提供不同响应。逐组表保留具体支持，不能只用总均值代替这些差别。

相同配比换人仍有约38%的调整只在一个视角超过小变化阈值，约22%在两个视角都超过。类别对位置的约束并没有抹去成员与视角的交互。与此同时，两种调整“四个团队端点都完整”的层级比例均约96.2%；对应距离可算率更低，主要来自角点数改变。异数是结构结果，不能填成零距离或一个很大的距离。

主层两视角几何同时严格相等的比例为0。因而质量在两个视角都处于±2分内，应称为质量作用较小，不能称为几何没有改变。主研究的有符号质量、转折、范围分项用于判断同向或反向；本表只判断位置变化幅度。

## 其它条件与机制案例

门洞、范围不同、其它采用状态分别保存在 `doorway_involved`、`scope_different`、`other_adoption_state`，不合为一条共同规律。全部人数、实际替换规模m和类别人数变化r也保留，没有只保存这一人调整摘要。

`SAME_STRUCTURE_OPPOSITE_Q_CANDIDATES.csv`是最多120条机制查看索引，包含四个精确团队键和结构变化向量。其选择条件是两视角的节点/转折/短边/冗余变化向量相同且非零，而两端Q变化均超过2分且相反；此表不是频率估计。G057的简明 W101→W130 案例及原图、原答、身份组票账由主研究案例模块解释，几何摘要没有重复或覆盖其人工解释。

## 文件与复算

- `PANEL_M_R_GEOMETRY_SUMMARY.csv.gz`：15165条 panel×m×r 充分摘要，含所有状态、分母、距离均值/p90及少量相关；没有存两百万行重复事件。
- `GEOMETRY_SUMMARY_BUILDING_EQUAL.csv`：主要条件与内部family分层的层级结果。
- `GEOMETRY_BY_PAIR.csv.gz`、`GEOMETRY_BY_GROUP.csv.gz`、`GEOMETRY_BY_BUILDING.csv`：逐图对/声明组/建筑结果与实际支持。
- `GEOMETRY_QUESTION_SUMMARY_LONG.csv`：每项指标自己的有效面板/图对/组/楼数；未定义的相关保持缺失。
- `figures/POSITION_CHANGE_REPETITION.png`和同名SVG：上表同支持比较与逐楼变化。
- `GEOMETRY_TRANSFER_RECEIPT.json`、`QUESTION_TABLE_DEFINITION.json`：完整性与指标定义。

输入采用main提交 `72a44e80c344975962e1071bd54d894dd86bb4b4`，精确设计见 `PANELS.csv`、`PANEL_TEAM_LINKS.csv.gz` 与 `REQUESTS.json.gz`。端点来自本轮 `native/pools/*.json.gz`。运行顺序为冻结引擎生成端点、几何摘要、层级表、绘图：

```bash
export HOHONET_REPO=/path/to/3D_Manhattan_label
python code/engine/new_team_engine.py --requests design/REQUESTS.json.gz --output run/native --jobs 6
python code/engine/summarize_geometry_transfer.py --design design --native run/native --output run/geometry
python code/engine/geometry_question_tables.py --input run/geometry/PANEL_M_R_GEOMETRY_SUMMARY.csv.gz --output run/geometry
python code/engine/plot_geometry_transfer.py --input run/geometry --output run/geometry/figures
```

`geometry_parallel_resume.py`可按图对并行续算，先停止旧进程再启动，避免并发写同一面板。首次方法接口核对仅有34次明确分离的确认/吞吐调用；正式设计团队数量另计。质量、参考资格、投票资格与融合规则均未改变。

每视角距离均值使用该视角自己的可对应事件；跨视角距离幅度差与三类定位状态使用两视角共同可对应的事件。`*_panel_p90_mean`是各面板p90经层级平均后的数值，不是汇总所有事件的p90。详细分项语义、坐标单位和资格定义见 `GEOMETRY_FIELD_CONTRACT.md`。
