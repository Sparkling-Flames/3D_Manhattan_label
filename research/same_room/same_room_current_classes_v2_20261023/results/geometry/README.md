# 几何重复性结果

这里保存全部有限实验的紧凑层级结果，以及足以重画主图的主预算一人调整小表。未重复打包全部端点几何或6.2MB的全 panel×m×r 中间摘要。

主结论：相同类别配比仍保留明显的成员定位差异。普通 Manual、中间人数、replicate 0 的同269面板对照覆盖114图对、58图、17个可重叠声明组、11栋建筑。同构成换人时，两视角位置都小变/仅一侧明显变/两侧明显变为39.81%/37.99%/22.19%；跨类一人替换为35.29%/37.13%/27.58%。这些比例以两视角均存在唯一同点数对应为条件，阈值为对应底角点平均BEV距离0.02个相机高度。两侧距离可算率分别84.08%和79.65%；异数与失败保留真实状态。

| 文件 | 用途 |
|---|---|
| `GEOMETRY_SUMMARY_BUILDING_EQUAL.csv` | 按面板→直接图对→已采用声明组→建筑等权的主要结果，含全部人数与不同条件层 |
| `GEOMETRY_BY_PAIR.csv.gz` | 逐直接图对结果、关系/范围/难度/类别方法与分母 |
| `GEOMETRY_BY_GROUP.csv.gz` | 逐声明组结果，原声明组可以重叠 |
| `GEOMETRY_BY_BUILDING.csv` | 逐楼结果；建筑用于汇总，不充当房间分类 |
| `GEOMETRY_M1_QUESTION_SUMMARY.csv` | 一人替换各指标的有效支持、层级均值及权重敏感性 |
| `GEOMETRY_PRIMARY_M1_PANEL_STRATA.csv.gz` | 主预算578条 panel×m×r 原始有限摘要，含309个面板、83100个精确调整；其中269面板支持同构成/跨类两种调整 |
| `GEOMETRY_TRANSFER_RECEIPT.json` | 完整几何研究已完成1954面板、153图对、2140619个精确调整的记录 |
| `QUESTION_TABLE_DEFINITION.json` | 指标、有效分母和权重定义 |
| `GEOMETRY_PACKAGE_SELECTION.json` | 小表筛选、源摘要与交付小表哈希，以及未随包重复的文件说明 |

主图位于 `figures/POSITION_CHANGE_REPETITION.png/.svg`；相对路径以成果包根目录为准。复算命令见 `code/engine/README.md`。

`V3_BEHAVIOR` 内的 `selected_family=JOINT` 联合E/R/G结构行为轴，仍是采用的结构分类的一部分；它不是独立的 `V3_JOINT_QT` 质量/时间联合类别。主结果不剔除任何内部family。门洞、范围不同、其它采用状态分别保留，不合成一个共同规律。

精确质量效果的正反方向、必要结构与原图机制由综合主报告解释；本表比较定位变化幅度，不能称为不同相机下同向物理移动。质量在两边都近零，也不等于几何严格没变。
