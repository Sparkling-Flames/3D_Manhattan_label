# 人数过程数据字典与关联方式

底层为真人 v2，源提交 `72a44e80c344975962e1071bd54d894dd86bb4b4`。本文件说明结果格式；实际完成量以 [results/COMPLETION.json](results/COMPLETION.json) 和覆盖表为准；研究判断统一见[人员主报告第6节](../../../docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md)。

## 1. 五个不同的数据单位

| 单位 | 主键 | 含义 |
| --- | --- | --- |
| 正式人员池 | `pool_id` | 同图片、同 Manual/Semi 条件、固定参考与资格的实际人员集合；不等同全部非 OOS 行为库存 |
| 进入顺序 | `pool_id, path_id` | 无放回人员排列；自然抽样或同一基础顺序的类别优先排列 |
| 顺序前缀 | `pool_id, path_id, k` | 前 k 个真实成员形成的一支团队；相同团队可能在不同顺序中出现 |
| 确定性端点 | `team_key` | pool_id 加排序后人员集合摘要；同集合只融合、测量一次，多个前缀可关联同端点 |
| 类别构成 | `pool_id, 分类, 层级, 完整人数向量` | 每一类均保留席位数，包含零席位和 UNKNOWN；与具体成员集合不同 |

`design/EXACT_ORDER_DESIGN.csv.gz` 保存完整进入顺序；`results/PREFIX_TEAM_LINKS.csv.gz` 将每一步关联到端点；`results/ENDPOINT_SCALARS.csv.gz` 保存去重端点及精确人员；`results/ENDPOINT_GEOMETRY.json.gz` 保存必要候选几何；`design/ENDPOINT_CLASS_VECTORS.csv.gz` 保存结构/联合粗细层的四种完整构成向量。展开分析文件 `results/PREFIX_RESULTS.csv.gz` 是 links 与 scalars 的 many-to-one 合并，未增加独立观测。

成员在一个顺序内不重复。`entrant_worker` 是当前新增的一人；`base_path_id` 将类别策略与原始自然顺序配对。两条策略在同 k 的实际换人数为 `k − |两队交集|`，不等于目标类席位差。改变类别的直接对照与固定比例换成员不是同一实验。

## 2. 质量、几何、失败

| 字段 | 单位、方向与解释 |
| --- | --- |
| `B8L2`, `D10` | 0—100，越高越符合当前工作指标。B8L2 为主，D10 为同几何的方向尺度敏感性 |
| `iou_2d` | 0—1，候选底面与当前参考的面积 IoU |
| `IoU3D100` / `iou_3d_corner_mean` | 0—100 / 0—1，冻结角点均高棱柱代理；不是实际连续三维实体体积 IoU |
| `S_bottom_deg` | 底边球面距离，度，低为好 |
| `dir` | 作答自身最佳正交轴下的边长加权 RMS 方向残差，度；不是逐墙对 GT 的方向误差 |
| `Hmean`, `Hcenter` | 沿墙长均高的相对误差、去均值后的局部高度轮廓残差；低为好 |
| `omission`, `extension` | 参考未覆盖面积/参考面积、候选超出面积/参考面积；均是几何方向诊断，不自动解释为漏画或目标范围选择 |
| `B8_floor_block` | `(1/IoU−1)+Sb²/32`，冻结底面惩罚块 |
| `B8_direction_block` | `1.5 d²/(d²+64)`，冻结方向惩罚块 |
| `B8_global_height_block`, `B8_local_height_block` | `(Hmean/.8)²`、`(Hcenter/.25)²` |
| `B8_height_block` | 两个高度惩罚块之和 |
| `D10_direction_block` | `1.5 d²/(d²+100)`，只用于同输入敏感性解释 |
| `B8_formula_residual` | 保存分数减由已有分项代入冻结公式所得值；仅是解释一致性诊断，不是新分数 |
| `nodes`, `candidate_pair_count` | 选中共识节点数、候选顶底点对数；须和有效转折及位置一起看 |
| `floor_turn5_n`, `floor_redundant5_n` | 底面折转大于5°的点数及不大于5°的冗余/近共线点数，新增几何诊断，不改评分 |
| `floor_short_edge_03_n`, `floor_short_edge_05_n` | 长度小于0.3/0.5个相机高度单位的边数；不直接等于必要细节 |
| `ref_node_recall_5/9`, `ref_edge_recall_5/9` | 按既有最大顶底球面角距配对后的参考角/相邻边覆盖，阈值5°/9°；不等同融合7.5°对应参数，也不是语义真值 |
| `ref_matched_nodes_5/9` | 命中的参考角 **0 基索引**，以竖线分隔；可追踪局部参考角机会 |
| `ref_top_pair_mean_deg`, `ref_bottom_pair_mean_deg` | 同一顶底最大角距 Hungarian 配对下，顶点/底点角距均值；未设截断阈值。仅说明实际分配点对的位置 |
| `ref_assigned_pair_n`, `ref_unassigned_pair_n`, `candidate_unassigned_pair_n` | 以上几何配对数及两侧未配对数；必须与位置误差并看，避免删点后剩余点误差小被误称完整 |
| `floor_area_camera_h2`, `centroid_x_h`, `centroid_z_h` | 候选底面面积与中心，单位为相机高度平方/相机高度；未宣称已知物理米制 |
| `height_mean_h`, `height_min_h`, `height_max_h`, `height_sd_h` | 顶底射线推导的角点高度描述；与质量 Hmean 的沿墙长均高定义不同 |
| `top_y_mean_px`, `bottom_y_mean_px` | 1024×512坐标下的平均顶点/底点 y；是形状位置描述，不是参考误差 |
| `minimum_support`, `node_supports` | 当前前缀门槛 `ceil(k/2)`、各选中节点的整数支持票数 |
| `selected_support_min` | 最小选中支持 **比例**，不是票数 |
| `score_available`, `score_failure_nonpolicy` | Q可用；排除两人政策延期后的Q不可用。不可用分数保留空值，不补0 |
| `policy_deferred` | `k=2`，按冻结环序/连接合同延期，单列政策空档 |
| `complete_floor_evaluable`, `complete_evaluable` | 几何可测与完整条件；不自动等于人工确认每个角身份或环序 |
| `geometry_status`, `geometry_reason`, `score_status` | 保留原计算状态及条件。`source_order_and_identity_unconfirmed` 是既有自动输出身份，不能把全部这类对象误记融合失败 |

B8L2采用 `100/[1+hypot(B8_floor_block,B8_direction_block)+B8_height_block]`。惩罚块越低，在其它项固定时 Q 越高；它们不能当线性可相加的Q贡献。历史 `WQ`、`direction_loss` 等未加B8前缀的列保留原身份，不能直接重新命名为B8分项。

## 3. 同人数换组波动

`results/PREFIX_GEOMETRY_VARIATION.csv.gz` 在每个 pool、策略和 k 内保留实际抽样顺序的频率。多个顺序遇到同一成员集合，其距离为0，但该端点只计算一次。

| 字段 | 含义 |
| --- | --- |
| `V_floor_mean`, `V_floor_p90` | 两个有效完整底面之间 `1−IoU` 的均值/P90 |
| `V_centroid_h_mean` | 两个底面中心的距离，单位相机高度 |
| `V_height_h_mean` | 两个候选角点均高的绝对差 |
| `V_turn5_mean`, `V_nodes_mean` | 两个输出的有效转折数/节点数绝对差 |
| `geometry_valid_paths`, `*_valid_pairs` | 实际可用路径及成对分母；失败仍留在全部路径数 |
| `unique_member_sets`, `member_variation_estimable` | 是否存在不同成员集合；单集合零波动是机械事实 |

Q的SD、P10和平均绝对成对差另表保留；最终自然曲线及案例背景的SD使用样本标准差ddof=1，单个可评分观测不估计SD。低分且低波动可能表示共同偏差。P10—P90是样本结果分布，不是均值置信区间。全员端点、以及类别优先恰好收齐该类的单一前缀集合，零成员波动不能作类型有效证据。

## 4. 时间与支持

`source_time_total_seconds` 是该前缀所有成员的**库存来源记录秒数之和**，只有全部成员时间已知才提供；`target_time_total_seconds` 要求更严格的当前目标匹配。`*_time_known_n` 和 `*_time_known_sum_seconds` 保留缺失支持，但后者不冒充完整耗时。`time_source_kinds` 保留来源身份。

自然无放回排列中，若整池来源时间完整，`E[T(k)]=k/N×整池记录时间总和`；解析期望与实际抽样值分别保存。该时间不是重新测量的生产耗时，也不是并行团队的墙钟历时。同最终人员池的不同顺序，收齐全员后的总记录时间必相同；类别优先只能改变前缀过程的时间—质量取舍。

`old_n/new_n` 是当前团队来源人数；`old_member_n/new_member_n` 是整个人员池的来源人数。不要混用。

## 5. 覆盖和推断边界

`coverage/ORDER_SPACE_COVERAGE.csv` 逐池区分所有可能的排列数与已登记/不同实际排列数；`coverage/PREFIX_MEMBER_SPACE_COVERAGE.csv.gz` 区分可行成员集合与实际计算集合；`coverage/PREFIX_CLASS_VECTOR_COVERAGE.csv.gz` 区分可行完整类别向量与观察向量。大排列数以十进制字符串保存。表中的可行数量不是已完成数量。

角色从目标建筑外的历史标签与中心确定；Manual/Semi分别评价。既有标签曾在v2内多轮探索，本轮属于内部重排验证。自然与策略的比较使用同 `base_path_id`；政策通常8条顺序的低尾和波动与相同8条自然顺序比较，不与全部24条直接混比；一个N=3的快类角色只有全6条，则两端均使用这6条。没有该角色或机会的池不补造结果。

主难度汇总先在图片内平均顺序，再作图等权及楼等权。固定N≥20的曲线在k≤20始终使用同一组图片；全可用人数曲线另表，明确后段支持池会减少。每个质量/时间/几何分项保留自己的真实分母。


## 6. 完整关系式事件与恢复宽表

`events/` 是557,138行完整事件，不是汇总抽样。四张 `*_LINKED.csv.gz` 分别保存自然相邻169,608行、自然区间45,960行、政策对自然229,050行、角色直接对照112,520行。原宽表重复的两端测量移到单份端点表；所有原事件变化值、比率、风险、元数据及没有直接端点替代的派生原值均保留。

| 关系字段 | 含义与关联 |
|---|---|
| `team_key_previous` / `team_key` | 自然相邻事件的前端／当前端；变化为current−previous |
| `team_key_from` / `team_key_to` | 同一自然路径区间的起点／终点；变化为to−from |
| `natural_team_key` / `priority_team_key` | 自然与其精确配对的角色优先前缀；变化为priority−natural |
| `comparison_team_key` / `focal_team_key` | 同基础路径、同人数的两个优先角色；变化为focal−comparison |
| `source_row_1based` | 原事件CSV的数据行号，不含表头；不是权重，也不是端点身份 |
| `members_added`, `members_removed` | 按上述变化方向，后端新增／前端移除的真实人员ID；空字符串表示空差集 |
| `members_added_n`, `members_removed_n`, `members_shared_n` | 实际成员集合差与交集；自然人数增长没有移除成员，不当作等人数换类 |
| `actual_m`, `actual_replacement_fraction` | 同人数事件的实际换人数及占总人数比例，按成员集合计算 |
| `target_seat_change`, `target_seat_fraction_change` | 目标角色席位净变化及比例，不等于实际换人数 |
| `*_net_seat_changes` | 角色直接对照中，完整本地类别人数向量差的half-L1；粗细与结构/联合各自保存 |
| `same_target_member_set`, `same_full_order` | 已存在的角色重叠与完整顺序相同状态，原样保留，不删除无差别对照 |
| `*_delta`, `*_change`, `*_logratio`, 风险列 | 沿用原计算结果和空值；关系化时没有重新计算这些科学结果 |

`events/COLUMN_RETENTION_AND_ENDPOINT_MAP.csv` 对每个原列登记保留或端点关联；`events/EVENT_RELATION_MAP.csv` 指定两端键、路径及人数。按 `team_key` 与 `results/ENDPOINT_SCALARS.csv.gz` 进行many-to-one左连接，可补回被移出的两端原测量。完整类别人数向量则连接 `design/ENDPOINT_CLASS_VECTORS.csv.gz`；类别轴、角色历史支持与UNKNOWN人数保留原折身份，不能跨建筑直接合并数字编号。

两端Q/D10、节点、记录总时间和关键状态已留在关系表中，可直接重聚合已有变化。恢复宽表仅恢复重复原值，不改变事件差值，也不新增团队或评分。源/目标行数和SHA在 `events/DELIVERY_COVERAGE.csv`，逐源独立保存与重读回执在同目录。

## 7. 空值、失败与共同分母

`ref_matched_nodes_5/9` 的空字符串要结合对应 `ref_node_recall_5/9` 判断：recall为0且列表空，表示有诊断但零命中；recall也未知，才表示诊断未知。不能把这两者都读成“没有角”，也不能排除已知零命中而夸大局部存在率。图示R1采用保存索引0；例如Uw-12的R4为索引3，uNb-60的R8为索引7。

单项有向变化使用两端该指标均有值的路径；风险按全部登记尝试，k2延期另列。不同分项的分母可以不同，Q改善与时间收益的联合判断必须再取共同完整支持。时间logratio是先在实际可比事件内取比再聚合，不等于“时间均值之比”；案例表的逐对百分比均值也与总量比区分。负向、零变化与失败在完整事件中都保留。

## 8. 来源与已完成数量

最终共有12,398条顺序、404,082条前缀、318,816个唯一端点。自然部分5,424条顺序、175,032条前缀；其余为既有角色优先过程。新增结果288,628个，历史复用30,188个。初期请求账中的30,189个cache hit包括本轮新做的1个benchmark端点，因此最终来源拆分将其计入新增，不将该差异当成缺件。来源列 `endpoint_origin` 与完成回执保留这一身份。

表数量是登记范围的完成量；完整可行空间另见coverage，不把MC路径数或大量事件复用误当穷尽全排列。完整历史阶段保持；最后状态和布局以本包README、SOURCE_AND_DESIGN和结果回执为准。
