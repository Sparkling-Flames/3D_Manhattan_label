# 结构类别换人／换类字段与计算口径

## 三队与标签

`A=D+X`、`B=D+Y`、`C=D+Z`。D 为相同具体成员背景；X／Y 为同一源类，Z 为目标类。每个事件 X／Y／Z 人数均为 m，四部分相互不重叠，A／B／C 总人数均为 n。

`same_*` 为 B−A，`cross_*` 为 C−A，`net_*` 为 C−B。涉及几何距离的字段本身是两份融合之间的距离，不能将其理解为相对 GT 的质量改善。例如 `net_corner_top_mean_h` 是 B／C 顶点配对距离；它不是 C−B 的顶点质量分差。

`source_role`／`target_role` 使用保存的训练侧角色 `TURN/K3/E2`／`TURN/K3/E3`。`source_class`／`target_class` 保留对应目标建筑外训练的原始类编号。`CLASS_LABELS_REUSED.csv.gz` 是实际实验楼外标签；`CLASS_LABELS_ALL_DATA_DESCRIPTION.csv` 只用于全数据成员说明，不用于目标建筑评价。

`turn_history` 是有效转折数相对同图同参考人员中位数的残差，经每栋训练楼先取均值，再对楼等权。有效转折数排除了 ≤5° 近共线节点；`short_history` 表达相邻明显转折之间长度不足周长 4% 的短边历史。它们描述可见表达倾向，不能单独判定真实必要结构或错误。

## 四种独立实验组

| `study_group` | 实际含义 |
|---|---|
| `main_n20` | 全体正式可用人员域，n20，m4／m7／每图方向最大可行 m≥4；每个可行背景类别人数向量均覆盖 |
| `new_only_n20_recorded_time` | 新来源人员域的 n20／m4 时间与质量补充，单独评价 |
| `linked_n` | 固定 X／Y／Z，按保存次序扩展 D；同一替换块在多个可行人数上的表现 |
| `linked_m` | n20，原队 A 完全不变；按 X／Y／Z 前缀逐步扩大替换块，D 相应缩减 |

`linked_n` 的 n20 行、`linked_m` 的最大 m 行引用主实验已有端点和物理三队。它们供配对路径分析，不作为额外独立证据与主层合并。

`physical_triple_id` 标识忽略 A／B 方向后的三队集合，`event_id` 包括实验身份。确定性融合以 `team_key`（图片池＋排序后的真实成员集合）只计算一次。

## 质量与几何

| 字段 | 单位与解释 |
|---|---|
| `B8L2`、`D10` | 原冻结总体质量分；B8L2 主结果、D10 方向残差尺度敏感性 |
| `IoU3D100` | 角点平均高度形成的棱柱三维 IoU ×100，适用的三维代理，不是真实房间体积测量 |
| `iou_2d` | 底面与参考的 IoU，0—1 |
| `S_bottom_deg` | 底面球面边界对称距离，度，越小越好 |
| `dir` | 标注自身最佳正交轴的方向残差，度；不是相对 GT 的全局朝向误差 |
| `Hmean` | 周长均值高度比例的绝对残差，越小越好 |
| `Hcenter` | 去中心后的局部高度残差，越小越好 |
| `omission`、`extension` | 既有遗漏／外扩分项，分别保留原合同；正负质量方向结合原定义解释 |
| `ref_node_recall_5/9`、`ref_edge_recall_5/9` | 原参考节点／边的 5°／9° 对应召回；5° 与 9° 分开，参考外真实细节不自动视作错误 |
| `fusion_turn_n`、`fusion_short_turn_edges`、`fusion_redundancy_n` | 融合有效转折、短转折边、近共线冗余节点计数 |
| `centroid_*_h`、`geometry_area_h2`、`height_*_h` | 摄像机高度归一化坐标、面积和高度，不能直接读作米或平方米 |
| `top_y_mean_px`、`bottom_y_mean_px` | 融合上下界平均图像 y 坐标；变化不直接等于参考质量改善 |
| `within_corner_*`、`cross_corner_*` | A／B 与 A／C 的冻结角点对应距离，仅在对应可用时保留；同点数与警告状态分开记录 |
| `common_corner_*` | 对同一批 ABC 都完整、两组对应距离都可得的事件，比较类内与跨类底点／顶点变化；逐事件派生值另存 `PAIR_LOCAL_COMPONENTS_COMMON.csv.gz` |
| `minimum_support` | 冻结 MV50 支持门槛 `ceil(n/2)`；n20→21 为 10→11，身份对应也可能同时变化，不能只凭门槛数字归因 |

`abs_Q_change_advantage = |C−A|−|B−A|` 只在三队 Q 都可评价时计算。正值说明该测试中跨类变化幅度更大，不代表质量更好。`net_B8L2 > 0` 才表示 C 相对同类替换 B 升质。二者分别判断。

`COMMON_ABC_COMPARISON.csv` 将三种有符号变化也限制在同一批 ABC 都可评分事件中，再用完全相同的层级汇总。该表中 `C−A − (B−A) = C−B` 严格成立。原逐对表保留所有各自可比事件，因此在失败不同的情况下，三列总体均值不必满足这一等式。`RECOMMENDED_CONDITIONS.csv` 同时保留逐对分母与 `ABC_common_*` 字段。

## 时间与失败

`recorded_time_single_source` 要求 A／B／C 中所有人员时间都有值、均为正、时间来源种类相同且单一。`*_recorded_time_pct = 100(exp(log(T₂/T₁))−1)`，T 为参与人员的库存记录秒数之和。这是原记录总时间的对比，不是本轮新测得的生产耗时或并行墙钟时间。

算术百分比均值与对数均值再指数化的几何百分比分开保存。时间与 Q 共同有效的子集另存 `TIME_QUALITY_COMMON_SUPPORT.csv`。缺时间、缺初始化／scope／困难机会均保留未知。

`A_failure`／`B_failure`／`C_failure` 依原冻结 `complete_evaluable` 定义，失败仍在登记分母内。质量损失 >10 分的分母是该对 Q 可比事件；合并“失败或损失”指标保留可判断分母。每个条件同时报告事件出现次数和去重失败端点数。

## 汇总与覆盖

主均值依次为：一个具体 D 内的成员组合等权，D 在同一类别人数向量内等权，人数向量在图片内等权，图片在楼内等权，最后楼等权。这个设计让深度成员面板不会挤压只登记一个背景的其它可行人数配置。`event_mean` 与 `image_equal_mean` 同时提供作敏感性解释。

`CONDITION_METRICS_LONG.csv.gz` 的每个指标单独保留 event／panel／image／building 分母、正向数量及楼重采样区间。图／楼同向比例基于对应图／楼均值；大量复用同一端点的事件不算新增图片。

`CAPACITY_AND_COVERAGE.csv.gz` 精确保存方向条件的全部可行背景、无向 X／Y 配对 ABC 空间和已登记数量；`COUNT_VECTOR_COVERAGE.csv.gz` 保存全部可行背景类别人数向量。完整向量覆盖不等于完整具体人员枚举，也不等于所有加入顺序。目标集合不重复融合；本轮只展开明确登记的 n／m 路径。
