# 人员分类、构成与人数过程：研究台图表

本目录将已核的真人 **v2** 结果整理成六组、16张可直接嵌入的PNG/SVG，配套实际名单、图表小表及68项名词解释。用途是连接既有研究台的研究叙事与数据浏览；结论真源继续是[人员主报告](../../../docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md)。

## 从哪里看起

|顺序|先回答的问题|主图及可继续查看的内容|
|---|---|---|
|1 分类依据与名单|哪些人怎样标，为什么分在一起？|[四套名单](figures/F1_class_rosters.png)、[联合特征](figures/F1_joint_features.png)；248行方案×人员名单、12人原答例、训练依据和ALL/楼外标签|
|2 混合配比|比例变了与同配比换人，分别怎样变化？|[Manual](figures/F2_manual.png)、[Semi](figures/F2_semi.png)、[联合类](figures/F2_joint.png)、[弱差异与失败](figures/F2_counterexamples.png)；7个分类视图（6个不同面板），每视图924队，全部配比格与分位带|
|3 匹配换人/换类|固定背景与换人数，方向和幅度有何区别？|[ABC设计](figures/F3_design.png)、[完整配对](figures/F3_general_magnitude.png)、[同房大块](figures/F3_same_room.png)、[规模与背景](figures/F3_scale_background.png)；成员及端点可沿精确设计追溯|
|4 图片难度|哪些图片条件放大或改变人员差异？|[难度连接图](figures/F4_difficulty.png)；原答表达、格间/格内波动与定向换类并列，各自显示支持|
|5 人数过程|加人后Q、低尾、形状波动和失败怎样变？|[Manual自然曲线](figures/F5_natural.png)、[Semi与门洞](figures/F5_conditions.png)、[进入顺序](figures/F5_policy.png)、[同源时间取舍](figures/F5_time_tradeoff.png)|
|6 真实机制|这些变化怎样发生？|[五个机制例](figures/F6_mechanisms.png)；继续进入完整个人标注、原图、投票与位置；补充同房G130/G172两视角|

各图的中文发现、读法、支持、原表与术语ID在 [FIGURE_MANIFEST.json](FIGURE_MANIFEST.json)。每图都有同名SVG，可放大查看。先看发现与图，再按需展开原表，不要求先读代号。

## 贯穿六组图的研究发现

- 结构类解释表达差异；结构＋Q＋T类同时刻画质量、速度和标法。四套都能用于配比和换人研究，并非分别绑定一个实验。细类数量、未知成员及楼外标签按实际来源保留。
- 改类别构成和同构成换人都能产生差异，二者幅度不必在所有条件下分离。完整配对中的Q差较小，联合类的时间区分更清楚；同房结构大块混合队中，61/78图对的跨类Q幅度更大，但单一视角的方向仍可不同。
- 困难图放大结构表达差异与同配比成员波动；部分定向换类随难度反转。升质、降质、费时、节时、弱响应和失败都是需要解释的结果。
- 困难图有早期加人收益，后段更多缩小成员与形状波动；门洞没有呈现普遍靠加人解决。Manual前段高Q/多转折优先的效果未在Semi复制；满员用同一批人，策略差必归零。
- 成员变化通过结构支持、票数门槛、位置估计与连接作用于结果。稳定或增加转折并不保证更接近参考，机制例须结合精确路径与总体背景。

## 名单与解释

[分类依据](notes/CLASSIFICATION_README.md)、[难度口径](notes/DIFFICULTY_README.md)、[六步讲述与常见问题](notes/TERMS_AND_STORY.md)分别维护，不混入新实验安排。

[GLOSSARY.json](GLOSSARY.json)每项提供短释义、详细解释、单位、方向、支持/分母、易混点和来源。重点区分：ALL描述名单与LOBO楼外历史、人工难度D与结构机会C、类别数与人数、Q准确性与V稳定性、成员分位带与重抽区间、劳动总量与交付时长。页面标题和文案使用中性研究称呼。

## 数据与展示合同

[CONSUMER_INTERFACE.json](CONSUMER_INTERFACE.json)给出六组顺序、数据入口、原答/机制图及必要明细来源。路径约定：接口的`*_path`、`path`、`source_paths`均以仓库根目录为基准；FIGURE_MANIFEST的图片和`data_paths`以本目录为基准，`source_paths`以仓库根目录为基准。

- `CLASSIFICATION_MEMBERS.csv`：方案×人员，248行；`known=false`表示该方案证据不足，仍保留人员。四套各62人不等于每张图有62人可用。
- `CLASSIFICATION_CENTERS.csv`：方案×叶类×特征，231行；单位与是否训练输入逐项保存。ALL中心只用于介绍总体分区。
- `MIXTURE_EXAMPLE_CONFIGURATIONS.csv`：七个实例分类视图的配比格（对应六个不同面板），均值/分位数只来自可评分队；团队总数与失败率含全部队，单队格不估成员波动。具体背景/候选人及楼外类定义使用接口中原表。
- `EXCHANGE_*.csv`：沿来源保留图/楼/图对等权，不将不同支持直接排名。旧完整配对的绝对差与新ABC对称幅度不同，图中明确说明。
- `DIFFICULTY_*.csv`：结果和逐图支持相连；缺困难Semi不填0。原答、配比和替换不是同一支持集，难度由人工主线提供。
- `NATURAL_CURVES_FIXED_N20.csv`：固定N≥20池，k=3—20的自然顺序；Q与失败、V保留各自有效数。进入策略在前半段对应自然路径比较，满员端点相同。
- 时间图采用当前R03独立复算的普通Manual67图18楼：联合质量时间4304单位；时间/失败4613尝试。不是此前88图、不同来源的历史时间域。

静态图为固定支持的概览，不能伪装成随所有筛选即时重算。筛选表可联动；图应明确固定支持，或由对应表重新绘制匹配筛选结果。Tooltip支持悬浮、键盘聚焦和点击固定，Escape关闭；单位、条件和关键分母常驻。

## 生成与检查

在仓库根目录依次运行：

```powershell
.venv/Scripts/python.exe -X utf8 tools/thesis_main/analysis/prepare_personnel_classification_figures_20261023.py
.venv/Scripts/python.exe -X utf8 tools/thesis_main/analysis/prepare_personnel_difficulty_figures_20261023.py
.venv/Scripts/python.exe -X utf8 tools/thesis_main/analysis/build_personnel_main_figures_20261023.py
```

分类提取核对正式名单、中心、选型和原答对象；难度提取含1058项值与支持断言；绘图核对七个分类视图各924队、失败分母、固定人数曲线与独立汇总一致、所有来源及词典ID。版式检查涵盖16张总览及高密度图的放大查看。新增展示文件不改动标注、参考、资格、评分公式、分类或融合实现。

已接入[既有研究台“人员研究六步”](../../statistics/research_explorer_v1_r2_20261017/index.html#release=v2&module=personnel_main)。页面增加24表（本包22表＋2表实例成员/角色），支持条件/方案/粗细类名单筛选、人员画像下钻、实例配比、图版放大和68项提示。研究台线程在Edge file页面检查六步、提示、原表跳转、名单和390px窄屏；相关9项测试通过。页面说明见[研究台README](../../statistics/research_explorer_v1_r2_20261017/README.md)。
