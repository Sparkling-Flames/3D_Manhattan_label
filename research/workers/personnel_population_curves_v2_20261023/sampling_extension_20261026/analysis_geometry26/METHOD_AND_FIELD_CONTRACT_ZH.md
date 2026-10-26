# 人数曲线追加：几何波动方法与字段合同

本分支只读取已经冻结、实际保存的端点标量与几何。源 main 为 `b9bcec809fbaec8ab055931a1abb7baa5db44dac`；本分支不调用融合、不调整参考与资格，也不生成新人员类别。新增进入顺序和融合端点由上层 `design26/`、`new_endpoints26/` 保存。

## 估计对象

在一个固定图片人员池中，随机顺序是池内人员的均匀排列。同一个 k 的前缀因此是均匀的 k 人子集。令 T 和 T′ 是两次独立这样的抽样，地面几何波动为：

`V_floor(k) = E[1 − IoU(footprint(T), footprint(T′)) | 两个端点均满足既有完整地面资格]`。

重复抽到同一个团队是合法的抽样结果，其距离为 0。两个不同团队产生完全相同几何时，其地面距离也为 0。主结果保留每条进入顺序的频数，不把见过的团队去重后随意等权。完整的有限目录另算：每个目录团队等概率，独立两抽包括同队配对，分母为有效团队数的平方。

除 `V_floor` 外保留：

| metric | 距离 | 单位与支持 |
|---|---|---|
| `V_centroid_h` | 地面多边形质心的欧氏距离 | 相机高度单位；同一完整地面资格 |
| `V_height_h` | 保存的平均高度之绝对差 | 相机高度单位；完整地面资格且两端高度有限 |
| `V_turn5` | 保存的实际转折数之绝对差 | 个；沿用 `floor_turn5_n` |
| `V_nodes` | 保存的输出节点数之绝对差 | 个；沿用 `nodes` |

这些量描述换同样人数成员后的输出变化，不能直接代替对参考质量的优劣判断。失去正式完整资格的候选几何不重新纳入；分母中的尝试路径仍保留。质量与实际失败在主标量分析中分别报告。

## 计算与误差

R 条进入顺序在每个 k 提供 R 个端点，主估计使用所有不同路径索引之间的有效成对距离，分母为有效路径数 `q(q−1)`。只移除某条路径与它自己的自配对，保留不同路径抽中同队的零距离。该 U 统计量不会把 O(R²) 个距离当作 O(R²) 个独立样本。

路径蒙特卡洛标准误沿用删除一整条进入顺序的 jackknife。删除一次路径，同时删除这条路径在所比较人数处的端点。人数变化的标准误使用两个端点的成对删除值之差，保留人数过程的关联。无效路径删除后条件均值保持原值；少于 2 条有效路径时点估计缺失，只有 2 条有效路径时点估计存在、标准误缺失。k=2 沿用既有暂缓规则，不解释为失败或 0 波动。

一张图满员只有唯一团队，合法时所有随机顺序的端点相同，V=0、路径 MCSE=0，原因是成员空间退化为一队。满员无完整地面资格时，V 保持缺失。固定起始人数恰好等于该池实际满员时，其“到满员”变化为合法的 0；不能将这些图片移除后声称固定支持。

为节省几何计算，程序仅在**坐标数组形状和 float64 字节完全相同**时复用多边形距离；不四舍五入、不近似合并。随后以原路径索引展开矩阵，重复团队和重复几何均保留原抽样频数。高度和节点等独立标量不会因地面相同而被合并。该优化与原程序已在真实 6 池、159 个 k 上比较，旧 48 的最大点估计差为 `6.66e−16`，最大 MCSE 差为 `1.03e−16`。详细实际计时和原值核对保存在 `GEOMETRY_TIMING_EQUIVALENCE.csv`；它只是计算等价性与预算检查，不是新抽样。

## 批次、固定支持和建筑差异

| cohort | 内容 | 用途 |
|---|---|---|
| `old48` | 原 24 + 前轮独立新 24 | 保留旧主样本 |
| `stage1_104` / `stage2_104` | 本轮两批独立 104 | 两批独立重复比较 |
| `new208` | 本轮两批合计 208 | 不含旧 48 的独立新增样本 |
| `pooled152` | 旧 48 + 第 1 批 104 | 阶段结果 |
| `pooled256` | 旧 48 + 新 208 | 本轮主样本 |
| `prior96` / `all_history304` | 有前轮焦点额外 48 的池 | 仅该焦点子域；不充当全库统一预算 |

主汇总同时给图等权与建筑等权，普通 Manual、门洞分开。图片范围由池容量预先定义，例如普通 N≥30 固定 157 图、22 栋建筑；N≥35 采用实际可用固定范围。全曲线记录 k=1…N 的原始结果，不以若干高人数点替代。某一比较若存在不可计算几何，汇总在预先指定各批次的共同可算图片上计算，同时保存所有候选图片的支持状态；原始逐图状态不删除。

`path_mcse` 只反映固定图片、固定人员池条件下随机顺序抽样的误差。建筑重抽区间在既有建筑中以建筑为块重抽 2,000 次，分别重算图等权/楼等权结果；它反映当前建筑集合的异质性与权重敏感性，不能写成新建筑外部验证。两类误差分别列出，不用路径标准误代替跨建筑差异。曲线表区间是逐点区间；`GEOMETRY_WHOLE_CURVE_REPLICATION.csv` 的最大/RMS 批次曲线差是实测描述，不是同时置信带。

## 文件及关联

- `GEOMETRY_PATH_PRECISION.csv.gz`：逐池、逐 k、逐批、逐指标的点估计/MCSE/状态，键 `pool_id + cohort + k + metric`。
- `GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz`：完整路径配对的人数变化，键 `pool_id + cohort + k_from + k_to + metric`。`ends_at_actual_full` / `same_endpoint` 明确满员与零跨度。
- `GEOMETRY_DISTANCE_COMPUTE_ACCOUNTING.csv.gz`：逐池 k 的唯一路径团队、完全相同几何数与实际计算距离数。
- `GEOMETRY_FIXED_SUPPORT_CURVES.csv.gz`、`GEOMETRY_FIXED_SUPPORT_INTERVALS.csv.gz`：固定候选范围、难度、共同图片支持及两种计权。
- `GEOMETRY_TO_ACTUAL_FULL_*`：固定起始人数到各图片实际满员；`k_to` 在逐图表保留原始数值。
- `GEOMETRY_COMMON_IMAGE_SUPPORT.csv.gz`：候选图片是否进入本次共同支持及必需批次列表，不把未进入者算 0。
- `GEOMETRY_FIXED157_INTERVAL_IMAGE.csv.gz`、`GEOMETRY_FIXED157_INTERVAL_BUILDING.csv`：普通固定 157 范围与门洞相应范围的关键区间逐图/逐楼证据，`layer` 不混合。
- `GEOMETRY_SAMPLE_VS_EXACT.csv.gz`、`GEOMETRY_EXACT_COMMON_SUPPORT_ACCURACY.csv`：复用前轮完整有限目录，与主随机样本分开。完整目录定义固定、没有新融合。
- `finite_margin_cases/`：wc2-46、VFua-04 和 rPc6-06 的近满员目录、实际新旧路径频数、两种 P10 约定及几何差异；通过 `team_key`、成员/对象/参考键连接既有几何。固定三例另用完整目录计算一/二阶 U 方差，条件于各版本实际有效几何数；保留旧 jackknife 并列。校准模拟不计为新增进入路径。

`cache/` 和逐池 `checkpoints/` 用于恢复计算，不必进入最终小包；最终合并结果与代码足以复算。`BASELINE_NONCOMPLETE_WITHOUT_GEOMETRY.csv` 列出旧 200 条本就无完整资格且无旧几何记录的端点，未把它们补成几何或恢复资格。其余所需完整地面端点的几何已实际读到 EOF。

## 运行

```bash
python analysis_geometry26/geometry_extension.py --study STUDY --population POPULATION --prior PRIOR_PRECISION --prepare
python analysis_geometry26/geometry_extension.py --study STUDY --stage 2 --jobs 1
python analysis_geometry26/summarize_geometry_extension.py --root STUDY/analysis_geometry26 --stage 2 --replicates 2000
python analysis_geometry26/finite_margin_cases.py --study STUDY
```

上层先冻结并完整保存 `design26/links_by_pool/stage{1,2}/POOL.csv.gz`，并写入 `REGISTRATION_RECEIPT.json`。早期长开文件描述符的全局 prefix 导出未通过完整读回，已排除为输入；本程序只读逐池原子完成的权威分片。每个池的 native 部分实际完成后才写 `new_endpoints26/stage{1,2}/parts/POOL/POOL_RECEIPT.json`；即使所有团队来自缓存也要有完成回执。几何分析只接入已完成的池，逐池保存结果和完成回执，支持重启。最终输出写入临时文件、完整读回后原子替换，防止未完成 gzip 被当作成品。
