# OOS描述统计字段合同

`schema=oos_closeout_v1`，`release=v2`。仅新增派生表，不改冻结protocol、标注、参考、难度或质量资格。OOS为超出标注标准的独立诊断；受约束GT可能不忠实，不使用其分数作正确性结论。

## 记录与因素

- 主键：逐份`object_id`；因素`image_id`唯一；逐图`image_code,condition,origin,time_source`唯一。
- `factors`为可重叠的竖线分隔因素；不可相加作互斥比例。`target_factor_status=not_adjudicated`；`angle_degrees`空表示未测量，不是0度。
- `analysis_pool = pool_analysis_eligible AND independent_vote_eligible`。仅此门内计算新结构特征；门外留`outside_existing_pool`。库存、时间与scope仍保留，绝不据新因素改变旧门。
- `feature_status=valid_floor`只表示保存点位能构成有效单平面底面。环序使用保存的声明顺序，`ring_confirmed`另外保留，不称全部人工确认。工作台继续仅在确认环序时连线。

## 几何与分歧

- 底面根据相机高度1投影；不做修点/自动多边形修复。OOS的多地面、斜顶不一定符合这个表示假设，数值描述**人员受约束表达**。
- `declared_pair_count`为保存的上下点对数；`turns_over_5deg`为底面转角大于5°的节点数；`near_straight_nodes_5deg`为不超过5°；`short_turn_edges`复用既有“边长<周长4%、两端转角≥15°”描述。它们不是结构正确率。
- `R_pair_union_mean`：同图、同条件、同origin和time_source内可测人员对的`面积(A△B)/面积(A∪B)`均值，0表示两份底面重合，1表示无重合。分母是**每对自身并集**，不能当作统一模型中以全池并集为固定分母的另一种R。
- `pair_n`为存在于旧人员对表的对数；`measurable_pair_n`为有底面分歧的对数；`comparable_node_pair_n`为节点数关系已知的对数。几何/节点数缺失分别排除，不计0分歧或相同。
- `height_camera_height`为每份作答各上点的推导高度均值（地面-1，相机0），并非真实房高。逐图`implied_height_P10/P90`是人员间分位数。
- `implied_height_within_relative_range = (max(h)-min(h))/mean(h)`，在一份作答内部计算，再取逐图中位数。顶面推导不可用时为空，不填0。

## 时间、选择和汇总

- `source_seconds`为证据表`source_active_time_seconds`；保持来源与status，不用lead_time回填。图内时间/几何表达取中位数，子类再对有效图片等权平均；表中`*_image_mean`因此不是逐份加权均值。
- `scope_response`为当前统一字段；`historical_raw_scope`保存v1原始选择。v1有207条OOS选择未承接为统一二值，因此v1的`scope_out_rate`一律留空，原始分布单独输出。
- 新Manual的`scope_out_rate`是该图统一字段out_of_scope／已回答数。`scope_out_majority_images`严格大于0.5，平局另计。无相容任务gold，不计算正确率。
- `geometry_image_n`、`R_image_n`、`scope_comparable_image_n`与`image_n`各有分母；同一图可在时间/选择表出现但不进入几何表。因子表不能把不同有效图拼成同支持质量—时间结论。
- `worker_condition_source`只作描述；个体任务组成不同，不据该表作能力或效率排名。

## 历史融合

`source,pool_id`标识旧实验与池；不合并不同方法/路径。`states`是保存前缀，不是独立团队；满员完整性每池一次。`formal_Q_allowed`全部false。旧Lee的输出数量不是几何正确率；没有被执行的池不记成融合失败。

工作台数据仍为`oos_review_v1`，新增只读`diagnostic`对象（新Manual逐图摘要）不改用户草稿`oos_review_drafts_v1`。浏览器已有草稿不自动覆盖采用因素；二者分开展示。
