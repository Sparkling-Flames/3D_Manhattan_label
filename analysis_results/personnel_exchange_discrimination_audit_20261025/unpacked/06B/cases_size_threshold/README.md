# 人数跨档时的结构失选：固定七人块 n14→15

**已完成：6 个冻结端点机制重放、精确成员、原图、局部票账、原观察重对应、组中位位置、ERP／BEV／3D 图及同图两条完整规模路径。** 数据为真人 v2，`20261025` 是本轮研究目录。这里保存解释性案例，不代替全体规模实验的发生率统计。

主入口：[中文案例说明](CASE_NOTE_ZH.md)；[六面板机制图](SIZE_THRESHOLD_MECHANISM_ZH.png)；[可导出 SVG](SIZE_THRESHOLD_MECHANISM_ZH.svg)。

## 1. 本例能够说明什么

`jh4fc5c5qoQ-12` 是冻结普通 Manual 的困难图片。DSTRUCT_K3 楼外标签的源 C2→目标 C3，X/Y/Z 始终各 7 人。同一个 W117 加入 A/B/C 的共同背景，团队从 14 人增长到 15 人，替换规模仍为 m=7。

| 项目 | n14 | n15 | 改变 |
|---|---:|---:|---:|
| A 的 Q | 72.970 | 73.048 | +0.078 |
| B 的 Q | 87.728 | 86.810 | −0.918 |
| C 的 Q | 96.596 | 45.462 | −51.134 |
| C 的节点 | 8 | 6 | −2 |
| C 的底面 IoU | 98.146% | 86.345% | −11.801 个百分点 |
| C 的三维棱柱代理 | 97.371 | 85.807 | −11.564 |
| C 的方向残差 | 1.113° | 15.514° | +14.401° |

- **R4 是纯门槛失选：**同一 7 人、同一中位位置，门槛从 7 变 8，原 7 票组不再输出。
- **R6 是重新对应与门槛共同作用：**原 W115 的未改坐标观察与新 W117 形成 2 票小组，使原 8 票组只剩 7 票，也未达到 8 票门槛。
- 该 C 队随后失去两转折，按冻结环序连接出现斜向捷径。Q 下降同时包含结构、底面及方向项变化，不能把 51.134 分全称为几何下降。
- 六个端点都成功、可评分。本例说明大幅质量损失与规模反转，不是完整融合失败。
- 同图第二条已存路径加入 W128 时，C 再次下降约 50.654 分；其标量与全部规模过程一起保存，但没有对该锚点再作组票账重放，不把两次内部原因写成完全相同。

## 2. 文件定位

| 内容 | 文件 |
|---|---|
| 精确两事件 D/X/Y/Z、ABC、背景及路径 ID | [SIZE_PAIR_EXACT.csv](SIZE_PAIR_EXACT.csv) |
| 每个角色 n14/n15 的全部冻结质量、记录时间 | [SIX_ENDPOINT_SCALARS.csv](SIX_ENDPOINT_SCALARS.csv) |
| 当前留出建筑的真实标签 | [LOBO_LABELS.csv](LOBO_LABELS.csv) |
| 难度、参考绑定及遮挡结构机会 | [DIFFICULTY_OPPORTUNITY.csv](DIFFICULTY_OPPORTUNITY.csv) |
| 新进入者的原答、时间与来源 | [ENTRANT_W117_RAW.json](ENTRANT_W117_RAW.json) |
| 全部身份组中位位置与支持 | [ALL_GROUP_MEDIANS.csv](ALL_GROUP_MEDIANS.csv) |
| 每一真实观察所在组、原始位置 | [ALL_GROUP_OBSERVATIONS.csv](ALL_GROUP_OBSERVATIONS.csv) |
| n14/n15 全票账 | [ALL_VOTES_N14_N15.csv](ALL_VOTES_N14_N15.csv) |
| 同一观察在人数改变前后的组关联 | [GROUP_LINKS_ACROSS_N.csv](GROUP_LINKS_ACROSS_N.csv) |
| 原观察拆组／合组汇总 | [COMMON_OBSERVATION_REGROUPING_ACROSS_N.csv](COMMON_OBSERVATION_REGROUPING_ACROSS_N.csv) |
| 逐参考位置的两个状态 | [REFERENCE_GROUPS_ACROSS_N.csv](REFERENCE_GROUPS_ACROSS_N.csv) |
| 当前固定块完整 n10…19 路径 | [SELECTED_PATH_ALL_N_METRICS.csv](SELECTED_PATH_ALL_N_METRICS.csv) |
| 同图两锚点的全部规模端点 | [SAME_IMAGE_TWO_PATHS_METRICS.csv.gz](SAME_IMAGE_TWO_PATHS_METRICS.csv.gz) |
| 同图两路径全部相邻步 | [SAME_IMAGE_ALL_STEPS.csv.gz](SAME_IMAGE_ALL_STEPS.csv.gz) |
| 两锚点的 n14/n15 与改变 | [TWO_ANCHOR_N14_N15_METRICS.csv](TWO_ANCHOR_N14_N15_METRICS.csv)、[TWO_ANCHOR_STEP_CHANGES.csv](TWO_ANCHOR_STEP_CHANGES.csv) |
| 实际来源与选择身份 | [CASE_SOURCE.json](CASE_SOURCE.json)、[CASE_SELECTION.csv](CASE_SELECTION.csv) |
| 原图与下载核验记录 | [originals/jh4fc5c5qoQ-12.png](originals/jh4fc5c5qoQ-12.png)、[originals/ORIGINALS_RECEIPT.json](originals/ORIGINALS_RECEIPT.json) |

两事件子目录各自保存 `CASE_GEOMETRY.json.gz`，包含池中原答、冻结参考、精确成员、三个完整融合状态及缓存标量；另外保存 ABC 分项、成员、票数、对应、ERP／BEV／票数图和 3D 图：

- n14：[3b15e1f073610cfe79b11d8a/ABC_ERP_BEV_VOTES.png](3b15e1f073610cfe79b11d8a/ABC_ERP_BEV_VOTES.png)、[3D](3b15e1f073610cfe79b11d8a/ABC_3D.png)。
- n15：[d8c03de1c870a22a3d448441/ABC_ERP_BEV_VOTES.png](d8c03de1c870a22a3d448441/ABC_ERP_BEV_VOTES.png)、[3D](d8c03de1c870a22a3d448441/ABC_3D.png)。

## 3. 复现及阶段身份

从整个 `exchange_research_20261025` 的上一级目录运行：

```bash
python exchange_research_20261025/cases/build_exchange_cases.py \
  --events exchange_research_20261025/design/size_paths/EVENTS_EXACT.csv.gz \
  --out exchange_research_20261025/cases_size_threshold \
  --event-id 3b15e1f073610cfe79b11d8a \
  --event-id d8c03de1c870a22a3d448441

python exchange_research_20261025/cases_size_threshold/complete_size_case.py
```

首条命令使用本轮 `run_native.py` 的冻结融合和质量合同，并逐项核对已保存端点；6 个端点的 Q、D10、底面和三维最大绝对差均为 0。第二条只从已存状态汇总、绘图和写说明，不另融合。所依赖的设计、规模结果和上级重放代码都保留原路径；本目录没有再复制全库输入。字体附带 Noto 子集及许可。

研究输入提交：`972857b2b3f548316be215400e42d6ef6e639250`。本例是完成规模比较后为解释强反转而选择的机制展示；不是随机选例，也不把当前目标图用于重新建类。冻结 LOBO 标签、原始环序、参考、资格、门槛和质量算法均不变。

已有机会记录支持淋浴隔墙背面／浴帘遮挡下的密集转折。并非所有参考背面角线都能在原图中直接看全；说明明确区分可见画面和引用的遮挡结构支持。普通池资格也没有因画面中可见门而改动。

本例单独保留 `cases_size_threshold` 阶段，不改先前四个 screen 案例或反推案例的阶段归属。
