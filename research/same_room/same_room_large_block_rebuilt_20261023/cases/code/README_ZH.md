# 新精确ABC的一例结构机制提取工具

这里新增的是读取、选择和制图代码。不会生成新团队，也不调用融合、评分、分类训练或参考修改。已交付的`cases/first_event/`保持原样。

## 选择规则

全量新事件结果完成后，运行一次`select_explanatory_case.py`。优先普通Manual当前结构类V3_BEHAVIOR的CA比较：两个视角发生相同且非零的实际转折数变化，Q作用符号相反，双端绝对Q变化均严格大于2。CA不存在时依次检查CB、BA；如果整个主条件没有候选，保留实际搜索数，转而检查结构反向，再检查真实不完整/连接失败。

在合格候选中，按类别方向、难度组合、替换比例段及转折变化形成解释单元，选择直接物理图对支持最多的单元，再选最小event_id。没有最大化Q，不假定候选事件之间属于独立人员重复。这是依据结果选择的机制说明，不能作为新外部验证。

## 提取及呈现

以`work/rebuild_large_block_20261023/`为运行根：

```bash
python cases/code/select_explanatory_case.py --effects results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz --out cases/structure_mechanism
python cases/code/extract_exact_case.py --event-id 实际所选event_id --design design/STRICT_ABC_EVENTS.csv.gz --native native_endpoints --snapshot engine/frozen_repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz --roles design/CLASS_ROLES_AND_MEMBERS.csv --effects results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz --geometry-events geometry/EVENT_GEOMETRY_RESULTS.csv.gz --selection-receipt cases/structure_mechanism/CASE_SELECTION.json --out cases/structure_mechanism
python cases/code/render_exact_case.py --case cases/structure_mechanism --originals cases/structure_mechanism/originals
python cases/code/describe_structure_case.py --case cases/structure_mechanism
```

原图必须先用Release的`IMAGE_INDEX.csv`对应到`image_id`，并实际取得文件。本代码遇到缺图就报告准确ID，不用替代图片。可选`--time-index`取得单份来源索引；原生端点时间资格及时间语义原样保留。可选`--roi-json`给出逐视角原图像素窗口`{"a":[xmin,xmax,ymin,ymax],"b":[...]}`，具体窗口保存在输出表，不当作新增墙角身份裁定。

实际提取的六条原生JSONL几何行不改内容；来源分片、原行号、字节SHA与本例行号写入`SOURCE_STATE_INDEX.csv`。仅存这六端点、两池原答/参考、设计行和相关表，不重复打包全量分片。

制图保留实际原答、未选身份组、票数门槛、位置子组、坐标中位数及连接状态。feature_id只在本团队内有效；不按相同node编号强行建立跨队或跨视角对应。坐标中位数不等于保存中心时只记录差异，不替换冻结几何。不可评分/无候选保持原状态，不补矩形或零Q。

ERP墙边由三维直边采样后投影为曲线，跨经度接缝分断；BEV单位为相机高度h，不是米。两幅BEV使用各自相机坐标，没有跨视角刚性配准。

使用Python3.12、numpy、pandas、matplotlib及Pillow即可，不依赖native融合环境。当前唯一第二例已按保存的规则完成，精确事件为 `ABC_0e2d9ba183c4f886c588`，解释见 `../structure_mechanism/README_ZH.md`。`describe_structure_case.py` 专用于这个实际选中病例，输出固定 B8 公式的分项重表达与局部票账，不重新运行融合、几何评分或拟类。
