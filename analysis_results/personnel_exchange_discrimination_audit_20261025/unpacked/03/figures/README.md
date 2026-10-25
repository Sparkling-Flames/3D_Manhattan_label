# 人员换人／换类：完整探索比较图

这组图直接重用本轮 `analysis/screen` 的实际结果，没有新增融合、重新建类或删除负向配置。底层为真人 v2；读取的 GitHub main 为 `972857b2b3f548316be215400e42d6ef6e639250`。本组为本轮探索阶段的可导出图，后续确认实验应保持阶段身份，不能以这组图冒充独立外部验证。

## 文件与建议用途

| 图 | 文件 | 主要用途 |
|---|---|---|
| 1 | [Q 幅度完整热力图 PNG](01_Q_GAP_ALL_METHODS.png)／[SVG](01_Q_GAP_ALL_METHODS.svg) | 呈现全部 27 个方法／层级实例、9 个 n/m 的同类与跨类 Q 变化幅度差。保留负向、弱差异与容量不足。 |
| 2 | [BEV 形状完整热力图 PNG](02_BEV_SHAPE_GAP_ALL_METHODS.png)／[SVG](02_BEV_SHAPE_GAP_ALL_METHODS.svg) | 检查分类是否同时区分实际融合底面形状；不把 Q 幅度差当作形状差。 |
| 3 | [难度分层 PNG](03_DIFFICULTY_WITHIN_CROSS_Q.png)／[SVG](03_DIFFICULTY_WITHIN_CROSS_Q.svg) | 对照新困难结构三类、既有结构粗类及历史 Q 二分。展示图等权均值、每图波动、实际图／楼分母。 |
| 4 | [DSTRUCT_K3 历史解释 PNG](04_DSTRUCT_K3_ALL_FEATURES.png)／[SVG](04_DSTRUCT_K3_ALL_FEATURES.svg) | 用实际人员的困难历史转折、近共线表达和上下界相对值解释 ALL 类别。 |

SVG 将字体嵌入为路径，可直接导入论文排版。PNG 为 180 dpi。图中中文与符号均经过实际图像查看；热力图适合整页或附录，难度图与类别图适合主文。

## 共同统计口径

严格三队为 A=D+X、B=D+Y、C=D+Z。D 为共同背景；X、Y 为同一源类的不同成员，Z 为目标类成员；X/Y/Z/D 互不重叠。三队图片、评价条件、总人数 n 与实际替换人数 m 相同。

- 同类幅度：`d(A,B)`。
- 对称跨类幅度：`[d(A,C)+d(B,C)]/2`。
- 幅度差 gap：跨类幅度减同类幅度。正值只表示跨类结果更不同，不表示跨类结果更好。
- Q 的距离为两队 B8L2 总分之差的绝对值。
- BEV 形状距离为两队输出底面的 `1−IoU`，不使用两队各自对参考的 IoU 之差代替。

图沿用已有分层汇总：同一 X/Y/Z 与同一目标类背景人数下先平均实际 D；再对该 X/Y/Z 的背景人数层等权；再对块、可行类别方向依次等权；最后按图片等权。建筑结果另行按建筑汇总。图中点已是图片层汇总，不是把重复事件当成独立图片。底层汇总代码和所有有符号变化、失败见 `../analysis/`。

不同方法／规模可行的图片集合不同，热力图用于完整展示候选与条件，不能直接当作共同图片上的方法排名。分数不可评不补零。两张热力图各有 **198 格可评、45 格没有严格 ABC 容量、0 格已尝试但该指标完全不可评**；共覆盖 243 格。代码保留“无可评”和“未汇总”两种独立状态供后续阶段使用。某一格可评不代表其所有端点均成功，失败应结合完整事件表和失败汇总阅读。

## 可直接使用的图注

**图 1：同类与跨类替换的 Q 幅度区分。** Manual 探索样本中，27 个方法／层级实例在 9 种 n/m 条件下的图等权幅度差。每格第一行为对称跨类绝对 Q 变化减同类绝对 Q 变化，第二行为该格实际可评图片数。红色为跨类幅度较大，蓝色为同类幅度较大，灰色表示真实人员容量无法形成严格 ABC。所有有支持的正向与负向格均保留；极大但只有少量图片支持的格不单凭均值采用。

**图 2：同类与跨类替换的融合底面形状区分。** 与图 1 使用相同候选和规模，距离改为两个融合底面之间的 `1−BEV IoU`。两图分别保留各自可评分母；Q 区分度与形状区分度可以不一致。该图不表示哪队更接近参考。

**图 3：难度怎样改变同类与跨类大块替换的幅度。** 比较 DSTRUCT_K3（n=10、m=7）、既有结构粗类（n=12、m=8）和历史 Q 中位数二分（n=12、m=8）。柱为图片等权均值；散点为图片汇总；每组下方列出“跨类幅度大于同类幅度”的图片及建筑数。三种方法在本探索样本中均呈现困难图更大的跨类变化；DSTRUCT_K3 的简单／中等／困难支持为 12／8／4 图，既有结构粗类为 8／7／3 图，历史 Q 二分为 17／14／14 图。困难层的强信号应连同真实支持量陈述；这不是同一批图片上三种方法的因果优劣比较。

**图 4：DSTRUCT_K3 全数据描述标签的历史标法。** ALL 描述标签含 59 名有支持人员：C1 为 8 人、C2 为 39 人、C3 为 12 人，3 人保留未知。非冗余转折和近共线冗余分别计量，避免将增加冗余点称为保留真实结构。数值为人员历史中相对同图、同条件人员中位数的残差，先在建筑内汇总，再按建筑等权形成个人历史值；不是原始角点数。上下界为辅助解释变量，未作为 DSTRUCT 建类输入；正值表示相对其他人员更向 ERP 下方偏移，不代表正确率。替换实验使用目标建筑外形成的标签，不能将 ALL 类别编号直接拼接为逐折类别。

## 图表数据与复现

- [HEATMAP_CELL_DATA.csv](HEATMAP_CELL_DATA.csv)：486 行，两项指标各自完整 243 格；包括状态、可评图片、可行图片／方向与同／跨均值。
- [DIFFICULTY_PLOT_DATA.csv](DIFFICULTY_PLOT_DATA.csv)：选定 3 个条件×3 个难度的全部 9 行及原支持字段。
- [DSTRUCT_K3_ALL_PERSON_FEATURES.csv](DSTRUCT_K3_ALL_PERSON_FEATURES.csv)：62 人，保留类别、来源、未知原因和困难／总体机会支持。
- [DSTRUCT_K3_ALL_CLASS_CENTERS.csv](DSTRUCT_K3_ALL_CLASS_CENTERS.csv)：三类特征中心及人数。
- [FIGURE_CAPTIONS.json](FIGURE_CAPTIONS.json)：机器可读图注和指标身份。
- [PROVENANCE.json](PROVENANCE.json)：输入路径、SHA256、实际源提交、绘图代码哈希。
- [FIGURE_MANIFEST.csv](FIGURE_MANIFEST.csv)：实际文件、字节数、SHA256、PNG 像素尺寸。
- [plot_screen_comparison.py](plot_screen_comparison.py)：实际运行代码。

从研究包根目录运行：

```bash
python figures/plot_screen_comparison.py
```

依赖 Python、numpy、pandas、matplotlib、Pillow。源表分别为 `analysis/screen/METHOD_N_M_COMPARISON.csv`、`DIFFICULTY_COMPARISON.csv`、`POOL_METHOD_N_M_SUMMARY.csv.gz`、`design/screen/CAPACITY_AND_ATTEMPTS.csv.gz`，以及 `features/HISTORY_FEATURES_ALL_LOBO.csv.gz`、`classifications/NEW_METHOD_LABELS_ALL.csv`、`NEW_CLASS_DEFINITIONS_ALL.csv`。

字体采用 Noto Sans CJK SC。优先读取 `fonts/NotoSansCJKsc-Subset.otf`（本图所需字符），也接受官方完整 `fonts/NotoSansCJKsc-Regular.otf`；来源和原字体哈希见 `fonts/FONT_SOURCE.json`。发布包不需要包含 16 MB 的完整字体或 matplotlib 缓存。
