# JOINT K4：同图完整原答补充

更新日期：2026-11-04。方法：`OPPJOINT_K4`。数据冻结于提交 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`，与第 08 / 09 批解释层使用相同版本。

**JOINT K4 的展示缺口已补齐：在原有 4 张图上加入四类的完整标注、对应个人 Q / D10、质量分项及记录劳动时间。** 新增 28 个展示位，涉及 28 个原答对象、18 名工人；其中 23 个对象已在其他分类图板中出现，新增 5 个不同原答对象。整套图册共 39 个不同原答对象。本次沿用已有模型和结果，只扩充原答展示及其说明。

**阅读入口：** [直接打开 JOINT K4 离线图册](index.html#method=OPPJOINT_K4)。下方四张静态板也可直接打开原始分辨率；对应的逐对象指标保留在每张板及数据表中。

## 1. 与原图册保持同图、同源

三张主图继续使用同一建筑的简单、中等、困难图，第四张保留为跨建筑附例。K4 不重新参与原有选图排名。四类在每张图上都有实际原答；C3 在这四个 **new 同源图片组**中都只有 W121 一人，因此展示其 1 / 1 个原答，其余类按原来的 8 个几何特征中位距离选取 2 人。

| 原图 | 官方难度 | 同源有效人数 | K4 C1 | C2 | C3 | C4 | 实际展示人数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `jtcxE69GiFV-10` | 简单 | 34 | 16 | 10 | 1 | 7 | 2 + 2 + 1 + 2 = 7 |
| `jtcxE69GiFV-09` | 中等 | 34 | 16 | 11 | 1 | 6 | 2 + 2 + 1 + 2 = 7 |
| `jtcxE69GiFV-26` | 困难 | 31 | 14 | 10 | 1 | 6 | 2 + 2 + 1 + 2 = 7 |
| `yqstnuAEVhm-01` | 中等 | 30 | 17 | 6 | 1 | 6 | 2 + 2 + 1 + 2 = 7 |

C3 的 1 人是这些图中当前同源原答的实际容量，不能解释成 K4 全部训练人员中只有 1 人。以 `jtcxE69GiFV` 留楼外折为例，该折当前标签表列入 C3 的人员为 W027、W036、W121；前两人为 v1 来源。这里保持各展示组的来源一致，直接披露本图可用人数。相同 W121 出现在四张图上是四个不同任务的真实原答，不能计为四名不同工人。

选人特征仍为转折、短墙、近共线点、水平 / 顶边 / 底边偏差、面积比与高度的对数；Q、D10、时间及其排名没有参与本次图示选样。K4 的建类本身使用历史 Q / T，这与“图册选人不用 Q / T”是两个不同步骤。完整规则见 [选样规则](SELECTION_RULE.md)，候选距离见 [选样排名](SELECTION_RANKS.csv)。

## 2. 28 个展示原答的个人指标

以下 Q 为既有 B8L2，T 为 `source_active_time_seconds`，单位秒。Q / D10 保留 3 位小数，原始精度保存在 [SELECTED_RECORDS.csv](SELECTED_RECORDS.csv)；该表还包括 IoU2D、底边位置误差、方向、高度、遗漏 / 外扩面积等分项与对象 ID。所有本页 T 均来自 `new | user_processed_reported_not_raw_log_replayed`，描述已接受的用户预处理时间记录，未在本次重放原始计时日志。

### jtcxE69GiFV-10 · 简单主图

[打开完整 K4 对照板](figures/jtcxE69GiFV-10__JOINT_K4.png)

![jtcxE69GiFV-10 的 JOINT K4 四类完整原答及个人指标](figures/jtcxE69GiFV-10__JOINT_K4.png)

| 类别 | 工人 | Q | D10 | T（秒） | 转折 | 短墙 | 近共线点 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | W128 | 87.106 | 87.639 | 70.856 | 4 | 0 | 0 |
| C1 | W134 | 86.283 | 88.300 | 37.918 | 4 | 0 | 0 |
| C2 | W124 | 98.954 | 98.965 | 78.964 | 4 | 0 | 0 |
| C2 | W120 | 98.420 | 98.427 | 94.598 | 4 | 0 | 0 |
| C3（本图 1 / 1） | W121 | 91.284 | 91.872 | 263.866 | 4 | 0 | 0 |
| C4 | W122 | 99.457 | 99.471 | 111.260 | 4 | 0 | 0 |
| C4 | W126 | 99.637 | 99.639 | 59.402 | 4 | 0 | 0 |

### jtcxE69GiFV-09 · 中等主图

[打开完整 K4 对照板](figures/jtcxE69GiFV-09__JOINT_K4.png)

![jtcxE69GiFV-09 的 JOINT K4 四类完整原答及个人指标](figures/jtcxE69GiFV-09__JOINT_K4.png)

| 类别 | 工人 | Q | D10 | T（秒） | 转折 | 短墙 | 近共线点 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | W125 | 64.490 | 70.410 | 217.940 | 4 | 0 | 0 |
| C1 | W134 | 92.731 | 92.745 | 72.594 | 4 | 0 | 0 |
| C2 | W127 | 92.101 | 92.178 | 291.202 | 4 | 0 | 0 |
| C2 | W110 | 83.408 | 86.854 | 500.864 | 4 | 0 | 0 |
| C3（本图 1 / 1） | W121 | 59.535 | 62.964 | 427.824 | 4 | 0 | 0 |
| C4 | W126 | 63.202 | 69.177 | 97.332 | 4 | 0 | 0 |
| C4 | W112 | 88.980 | 90.663 | 378.920 | 4 | 0 | 0 |

### jtcxE69GiFV-26 · 困难主图

[打开完整 K4 对照板](figures/jtcxE69GiFV-26__JOINT_K4.png)

![jtcxE69GiFV-26 的 JOINT K4 四类完整原答及个人指标](figures/jtcxE69GiFV-26__JOINT_K4.png)

| 类别 | 工人 | Q | D10 | T（秒） | 转折 | 短墙 | 近共线点 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | W107 | 48.247 | 51.059 | 1146.891 | 9 | 1 | 0 |
| C1 | W125 | 73.513 | 79.436 | 986.096 | 6 | 1 | 0 |
| C2 | W127 | 52.483 | 56.148 | 740.365 | 5 | 1 | 0 |
| C2 | W116 | 50.577 | 54.772 | 563.670 | 6 | 1 | 0 |
| C3（本图 1 / 1） | W121 | 45.493 | 46.184 | 2894.746 | 4 | 0 | 0 |
| C4 | W112 | 61.802 | 68.134 | 3559.413 | 8 | 3 | 0 |
| C4 | W115 | 68.454 | 74.489 | 1018.229 | 8 | 3 | 0 |

### yqstnuAEVhm-01 · 跨建筑中等附图

[打开完整 K4 对照板](figures/yqstnuAEVhm-01__JOINT_K4.png)

![yqstnuAEVhm-01 的 JOINT K4 四类完整原答及个人指标](figures/yqstnuAEVhm-01__JOINT_K4.png)

| 类别 | 工人 | Q | D10 | T（秒） | 转折 | 短墙 | 近共线点 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 | W108 | 70.894 | 77.081 | 100.105 | 8 | 2 | 0 |
| C1 | W133 | 55.355 | 60.704 | 66.895 | 7 | 1 | 0 |
| C2 | W123 | 67.265 | 73.301 | 113.520 | 8 | 2 | 0 |
| C2 | W116 | 47.773 | 51.307 | 44.335 | 8 | 2 | 0 |
| C3（本图 1 / 1） | W121 | 46.064 | 49.209 | 285.970 | 7 | 2 | 0 |
| C4 | W130 | 97.747 | 98.078 | 118.097 | 8 | 2 | 0 |
| C4 | W115 | 94.380 | 95.254 | 98.514 | 8 | 2 | 0 |

## 3. 图示补充了哪些可观察解释

### 3.1 简单图：同为四个转折，仍可看到不同的质量与劳动

`jtcxE69GiFV-10` 的 7 个 K4 展示原答都是 4 个转折、0 段短墙，但 Q 从 86.283 到 99.637，T 从 37.918 秒到 263.866 秒。例如 C1 的 W134 为 Q 86.283 / T 37.918，C2 的 W124 为 Q 98.954 / T 78.964，C3 的 W121 为 Q 91.284 / T 263.866，C4 的 W126 为 Q 99.637 / T 59.402。完整边界和底面让读者看到位置与形状误差，个人时间让读者看到相同点数下的劳动差异。

### 3.2 困难图：结构表达、评分与劳动形成多种组合

`jtcxE69GiFV-26` 的参考为 8 个转折、3 段短墙。C4 的 W112 与 W115 均保留 8 / 3，Q 为 61.802 / 68.454，T 为 3559.413 / 1018.229 秒；相同类别、相同结构计数仍有明显的个人劳动与位置差异。C2 的 W127 / W116 表达 5 / 6 个转折和 1 段短墙。C3 的 W121 表达 4 个转折、0 段短墙，Q 为 45.493，T 为 2894.746 秒。

C1 中也存在不同组合：W107 有 9 个转折、1 段短墙，Q 为 48.247；W125 有 6 个转折、1 段短墙，Q 为 73.513。它们把“保留更多结构”“几何位置更准确”“投入更多记录时间”三个可观察维度具体展示出来。不能把原始转折数量直接换成 Q，也不应把一个类的所有工人描述为同一种作答。

### 3.3 跨建筑图：结构计数相同，位置精度仍能区分类内与类间原答

在 `yqstnuAEVhm-01` 上，C2 的 W123 / W116 和 C4 的 W130 / W115 都表达 8 个转折、2 段短墙。前两人的 Q 为 67.265 / 47.773，后两人为 97.747 / 94.380；对应匹配边界绝对偏差分别为 2.168° / 1.168° 与 0.140° / 0.196°。完整标注对照有助于看见结构计数之外的实际几何差异。这里仍使用该建筑自身的留楼外标签。

这些是选定原答的具体事实。图册负责把标法画出来，下面的全量共同支持统计负责说明各类在研究范围内的平均 Q / T 关系。

## 4. 与既有 K4 Q / T 发现怎样对应

下表直接读取本轮前已经完成的 [同记录、同源共同支持汇总](../rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv)，限定 `manual / primary / ALL difficulty / OPPJOINT_K4`。Q 差和时间比来自同一批具有合法正时间的原答，先同图比较，再按图片等权汇总。时间比为几何时间比；不是两个算术平均时间直接相除。它们没有因新增图板而重算。

| 类对（后一类减前一类） | 来源 | 图片 / 建筑 | Q 差 | 时间比（后一类 / 前一类） | 采用的解释 |
| --- | --- | ---: | ---: | ---: | --- |
| C2 − C1 | new | 162 / 17 | −0.133 | 0.8847 | Q 图均值接近，记录劳动平均约少 11.5% |
| C2 − C1 | v1 | 87 / 21 | +0.678 | 0.8340 | Q 图均值接近，记录劳动平均约少 16.6% |
| C3 − C2 | new | 143 / 21 | −4.171 | 2.9495 | 较长记录劳动与较低平均 Q 同时出现 |
| C3 − C2 | v1 | 49 / 14 | +9.097 | 3.6844 | 较长记录劳动与较高平均 Q 同时出现 |

“均值接近”是这里的数值描述，不是统计等效性检验结论。四张 new 图中的几何典型原答也不是 162 图总体 Q / T 关系的重新抽样证明；具体图片或具体两人的快慢方向可以与总体平均不同。C3 的 new / v1 结果应分别按来源、实际成员和图片支持解释，不能把本图 W121 的表现推广到所有折或所有来源的 C3。

这份补充使读者既能读到 K4 的质量—劳动关系，也能在同一张真实图上看到四类原答的结构和位置；已有总体结论及团队结果的数值和支持范围保持原值。

## 5. 标签、坐标、参考与时间接续

- **楼外标签**：每个对象按 `method=OPPJOINT_K4`、`heldout_building=building`、`worker_id` 绑定，且 `known=true`。没有用 `ALL` 名单代替当前图片的楼外标签，也没有重新拟合 K4。编号来自各折训练 Q 中心排序，并不是跨折固定的人员角色名称。
- **当前有效坐标**：直接读取 v2.1 有效输入对象的 `points_1024x512`，上下点和保存顺序完整展示。28 个 K4 原答的 `preprocessing_status=ready`、几何状态为 `surface_valid`；其 `order_status=default_unreviewed` 保留原记录含义。本次没有重新排序原答，没有采用 F2 / F9 坐标候选，也没有把融合节点人工顺序回写到个人原答。
- **同参考评分绑定**：Q、D10 与分项以 `object_id + reference_id + reference_version` 精确接续既有评分结果。独立核对的 28 / 28 条均匹配，Q / D10 浮点差异上界约为 `1.42e-14`。原图中的参考对应当前原答使用的同一参考和版本。
- **展示单位**：Release PNG 为 2048 × 1024；研究坐标为 1024 × 512，展示等比例映射，不改研究点位。底面投影单位仍为相机到地板的高度。
- **劳动来源**：本图组所有 T 都是同一 new 来源的合法正值。与 v1 的比较仅通过上节已分源的共同支持统计进行，不将两个来源直接拼成一个时间均值。

## 6. 可核查来源

1. Sparkling-Flames（2026）. *3D_Manhattan_label: v2.1 current effective annotation input*. GitHub 项目研究数据，固定提交 `48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b`。有效坐标：[`research/data/releases/v2.1/analysis_input/data.json.gz`](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b/research/data/releases/v2.1/analysis_input/data.json.gz)；评分：[quality_records.csv](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b/research/data/releases/v2.1/quality_records.csv)；参考：[reference_catalog.json](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b/research/data/releases/v2.1/reference_catalog.json)。
2. Sparkling-Flames（2026）. *Personnel v2.1 reselection: MAIN45 labels, ALL and LOBO*. GitHub 项目研究数据，同一固定提交。K4 原始标签：[`research/workers/personnel_v21_reselection_20261029/classification/MAIN45_LABELS_ALL_LOBO.csv.gz`](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b/research/workers/personnel_v21_reselection_20261029/classification/MAIN45_LABELS_ALL_LOBO.csv.gz)。本补充直接读取已整理的 [当前五方法标签表](../basis/WORKER_LABELS_ALL_LOBO.csv.gz)。
3. Sparkling-Flames（2026）. *Image difficulty 20261030: raw target response records*. GitHub 项目研究数据，同一固定提交。原答结构、Q / T 来源字段与官方难度：[`RAW_TARGET_RESPONSE_RECORDS.csv.gz`](https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b/research/data/releases/v2.1/admitted_space_extension/image_difficulty_20261030/classification/RAW_TARGET_RESPONSE_RECORDS.csv.gz)。
4. Sparkling-Flames（2026）. *quality-original-images-20261015*. GitHub Release 原图资产，[Release 页面](https://github.com/Sparkling-Flames/3D_Manhattan_label/releases/tag/quality-original-images-20261015)。本次复用第 09 批同一批原图，来源明细见 [ORIGINAL_IMAGE_RECEIPT.json](ORIGINAL_IMAGE_RECEIPT.json)。
5. 本项目本轮整理（2026）. *当前类别原答与团队效果解释：同记录同源 Q / T*. HOHONET v2.1 补充研究表。[Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv](../rfuse_joint/Q_T_COMMON_RECORDS_PAIR_SUMMARY.csv)、[RFUSE / JOINT 报告](../rfuse_joint/REPORT_ZH.md)、[总报告](../REPORT_ZH.md)。这是基于上述冻结数据的研究输出，不是新增外部文献。
