# 反推四人类的机制案例：独立于先前四个screen案例

**已完成：B6ByNegPMKs-47，困难，RFUSE_GEOM_K2，n12/m4。** 所选事件为留出建筑确认阶段 `f261cd4329817662818a5684`，使用该楼真实LOBO四人目标类W109/W112/W126/W130。旧四案例仍在 `../cases/`，本目录不覆盖其索引、图片或阶段身份。

## 主要发现与入口

[完整中文解释](f261cd4329817662818a5684/CASE_NOTE_ZH.md)串起真实成员、Q/分项、结构、票数、中位位置、共同背景观察的重新对应及原图语义。

- 同类Q变化0.439，对称跨类6.158，gap+5.718；C−B+5.938。
- A/B/C输出7/8/10节点。R4由4/4变6票，R9由3/5变7票；门槛为6。四名Z分别为两处各提供一票，背景还提供2票或3票。
- C相对B底面IoU+11.245个百分点，三维代理+10.836；Q仍只有55.46，方向和高度等偏差没有全部消失。
- 共同背景W124/W131的两份邻近观察重新分组，10个共同观察对被拆分；本例同时包含投票、对应和位置变化。
- 同图另一个背景也有正Q gap，但形状gap为负，完整保留。原图存在突出墙垛与打印机遮挡，称参考支持的回转结构补充，不把隐蔽背面硬称为直接可见的重新裁定。

图像：[ERP／原答／BEV／票数](f261cd4329817662818a5684/ABC_ERP_BEV_VOTES.png)、[三维代理](f261cd4329817662818a5684/ABC_3D.png)、[原图](originals/B6ByNegPMKs-47.png)。三张均已实际查看。

## 选例范围完整保存

- [SELECTION_RECEIPT.json](SELECTION_RECEIPT.json)：选择规则、分母和结果来源SHA。
- [SELECTION_FRAME_EVENTS.csv.gz](SELECTION_FRAME_EVENTS.csv.gz)：RFUSE_GEOM_K2 n12/m4的全部118事件、51图、17楼。
- [SELECTION_IMAGE_SUPPORT.csv](SELECTION_IMAGE_SUPPORT.csv)：每图成员／背景重复性、失败／不可评和正负gap。
- [SELECTED_IMAGE_ALL_EVENTS.csv.gz](SELECTED_IMAGE_ALL_EVENTS.csv.gz)：所选图的两个事件，包含反向形状结果。

中等／困难且目标类恰4人的范围有20事件、10图，19事件三队Q可评；5张图在至少两组XYZ和两种实际D中均有正Q gap。这里属于完成比较后的解释性选例，不是新的总体统计验证。本图两个事件对中位数等距，选择其中较小的gap，未取最大效应。

## 精确输入与证据

- [SELECTED_EVENT_EXACT.csv](SELECTED_EVENT_EXACT.csv)、[SELECTED_EVENT_METRICS.csv](SELECTED_EVENT_METRICS.csv)：D/X/Y/Z、ABC及全部已存分项。
- [SELECTED_FOLD_PERSON_LABELS.csv](SELECTED_FOLD_PERSON_LABELS.csv)、[SELECTED_FOLD_RESPONSE_CENTERS.csv](SELECTED_FOLD_RESPONSE_CENTERS.csv)：该目标楼的真实标签与反推中心；不以ALL替代。
- [CASE_DIFFICULTY_OPPORTUNITY.csv](CASE_DIFFICULTY_OPPORTUNITY.csv)：现有难度、范围和结构机会，参考ID精确匹配。
- [CASE_GEOMETRY.json.gz](f261cd4329817662818a5684/CASE_GEOMETRY.json.gz)：原答点、固定参考、三队完整融合状态、端点及精确事件。
- [VOTES.csv](f261cd4329817662818a5684/VOTES.csv)、[KEY_STRUCTURE_VOTES.csv](f261cd4329817662818a5684/KEY_STRUCTURE_VOTES.csv)：所有组和局部关键组，未选组不删除。
- [GROUP_MEDIANS.csv](f261cd4329817662818a5684/GROUP_MEDIANS.csv)、[GROUP_OBSERVATIONS.csv](f261cd4329817662818a5684/GROUP_OBSERVATIONS.csv)、[COMMON_D_OBSERVATION_ASSIGNMENTS.csv](f261cd4329817662818a5684/COMMON_D_OBSERVATION_ASSIGNMENTS.csv)：中位数原观察及共同背景变组。
- [REPLAY_RECEIPT.json](f261cd4329817662818a5684/REPLAY_RECEIPT.json)：3次原生重放与既存B8L2/D10/底面/3D标量最大差均为0，无失败。
- [CASE_SOURCE.json](CASE_SOURCE.json)、[原图来源回执](originals/ORIGINALS_RECEIPT.json)、[FILE_MANIFEST.csv](FILE_MANIFEST.csv)：代码、真实v2、Release单成员范围下载及实际文件哈希。

## 复现

在研究包根目录按顺序执行：

```bash
python cases_reverse/select_reverse_case.py
python cases_reverse/fetch_selected_originals.py --image B6ByNegPMKs-47
python cases_reverse/replay_reverse_case.py
python cases_reverse/complete_case_facts.py
```

下载只取这一张Release ZIP成员，不下载原图全集。重放复用 `cases/build_exchange_cases.py` 与本轮 `run_native.py`，保留既有GT、环序、资格、B8L2/D10与融合规则；参考角点对应全部在输出后用于诊断。最后一步保存的是已实际看图后的这一个案例说明，不用于自动裁定其它图片。
