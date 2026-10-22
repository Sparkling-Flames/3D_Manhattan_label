# 研究台接口：当前类别构成作用的同房重复性

## 身份与版本

研究 ID：`same_room_current_class_composition_20261023`；实际输入提交：
`72a44e80c344975962e1071bd54d894dd86bb4b4`。
房间采用版本：`same_room_user_working_classification_20261016_v2`。
日期后缀延续仓库当前研究批次，不替代实际取得时间 `source_index/SOURCE_COMMIT.json`。

主分类为当前 `V3_BEHAVIOR` 的 Manual 楼外标签；`V3_JOINT_QT` 用同一批实际团队作对照。
标签键必须包含 `method + condition + heldout_building + worker_id`。
`selected_family`、`coarse_label` 和该折类中心均保存。不同楼外折的 M1/M2 等编号不可当作固定语义。
没有把旧 M0/M1 标签直接映射为本轮类别。

## 连接顺序

|表/键|含义与连接|
|---|---|
|`design/PANELS.csv: panel_id`|一个直接图对、当前类别对、人数、候选/背景重复面板|
|`pair_key`|两个既有 `pool_id` 的有序规范连接；关系来自原采用，未作传递闭包|
|`groups`|直接声明组 ID，以 `\|` 分隔；重叠保留，不把组数当独立房间数|
|`pool_id_a/b`|图片×条件×冻结正式人员池；连接 INPUT_SNAPSHOT|
|`image_a/b, image_id_a/b`|可读图片名及原对象图片键|
|`reference_id_a/b`|冻结参照；不可通过换参考提高结果|
|`design/PANEL_TEAM_LINKS.csv.gz`|`panel_id + selected_mask` 唯一确定有限面板团队；包含两视角的规范 `team_key`|
|`member_set_key`|排序后的实际 `worker_id`，以 `\|` 分隔；同一行在两个视角完全相同|
|`structure_vector/joint_vector`|整队完整类别计数的规范 JSON，包括固定核心，不只是替换块的比例|
|`joint_all_known`|联合分类标签是否全可用；未知不填入某个类别|
|`results/native/ENDPOINT_SCALARS.csv.gz: team_key`|冻结融合接口的规范团队键，保留池、实际成员、原答 `object_id`、参考、全部结果与状态|
|`study_request_id`|本轮辅助请求键，不替换规范团队键|
|`cases/mechanisms/MECHANISM_INPUT_INDEX.csv`；`cases/budget/G117_LOW_HIGH_INPUT_INDEX.csv`|代表案例的图片、原图 Release 成员、原答/参考/几何、局部账本定位|

## 替换与相同配比

对同一面板两个 `selected_mask`，固定核心加交集就是实际不变背景 D；
`m = |members_from − members_to|` 是实际替换人数。
`r` 是高转折中心类别的净增人数，`0 ≤ r ≤ m`。
`r=0` 表示结构类别整队配比不变，具体成员改变；`r=m` 是纯类别块替换；其余是混合块。
方向仅按楼外转折中心排序，**不表示高质量或更适合目标图**。
精确事件键由 `panel_id + mask_from + mask_to` 生成；全事件可从链接完整枚举，不必保存数百万份重复几何。

相同 n/m 的总体类内与跨类比较仍可能有不同 D，因此另提供
`results/same_background/PRIMARY_ACTUAL_BACKGROUND_COMPARISONS.csv.gz`，保留主预算，严格固定实际 D、n、m；其它人数的分组/建筑摘要仍保留，全事件可从端点复算。
第二个候选/核心面板用于相同完整配比换实际成员检查；剔除相同实际团队后才比较。

## 结果与缺失

`B8L2` 主指标，`D10` 敏感性。两端效果要有四个实际团队评分；缺失保持缺失。
`complete_evaluable`、`score_status`、`geometry_status` 单列，不能把失败当 Q=0。
描述 Q 作用状态以绝对增量 ≤2 分为小变化，另保存 0/1/5 分敏感性；两边小变化不称结构不变。
`nodes` 是原生融合节点数；`fusion_turn_n` 去除 ≤5° 近共线点后的有效转折数。
同数不等于同一局部节点，也不等于必要结构保留。必要局部机制由案例票账说明。

`S_bottom_deg` 为参照底点误差；`dir` 为候选自身最佳正交轴方向残差，**不是相对参考的绝对墙向差**。
`Hmean` 是周长加权全局高度比的绝对误差，`Hcenter` 为中心化高度剖面误差。
`omission` 与 `extension` 的分母均为参考面积；明确方向为 `extension − omission = A_pred/A_ref−1`。
`geometry_area_h2` 单位为相机高度平方；BEV 位置 h 不是米。
对应角点距离仅在同一图片中比较两团队，并保留异数、不完整和对应不可计算；没有把两个视角空间配准。

## 时间

`BLOCK_TIME_*` 直接使用 INPUT_SNAPSHOT 中同一原答的 `source_time_seconds`，保留其 `time_source_kind`。
同一个删除/加入块在两视角全部已知且同一种语义时才可比较。未替换背景抵消，所以这是边际劳动变化。
不把它称总交付时间、并行完成时间或货币成本。
`user_processed_reported_not_raw_log_replayed` 与 `inherited_v1_audited_source` 分开。
混合语义或缺少机会为不可计算，不是零耗时。
原生端点 `recorded_time_total_seconds` 还沿用旧 profile-index 连接，部分旧 object_id 不匹配时缺失；
该字段没有用另一时间字段填补。两条时间证据的来源在表中分别保留。

## 计权与留出含义

主预算：复 0、`n=max(3,k,min(N−k,floor(N/2)))`；其它实际 n 全部保留。
主汇总：有限面板内事件→直接图对内类别面板→原声明组→建筑等权。
原始事件分母另列；数百万事件不是数百万独立样本。重叠组是描述性计权单位。
源端响应模型只用源图 Q/几何、楼外标签/画像；目标 Q 只评价。
去均值形状误差中的目标均值是评价量，不能当作已知预测输入。
楼外参数校准是固定实验银行的内部检查；它不是新人员、新建筑采集的外部验证。
本轮单源团队响应实验与上一轮“历史图片严格超过50%”的均值/个人/停止实验分开保存。

## 恢复身份

上一轮主要报告在当前 main 已采用，本包 `prior/` 摘接的是该固定提交中的报告文本与来源；`prior/adopted/`、`prior/dot_independent/` 保留取回的小表、关键代码和案例账本，
不是找回失效的 47.1 MiB 原 ZIP。旧原件仍不可复核。
本轮所有 `SRCC23` 团队是新增冻结方法重放；已有人员原答并未重新采集。
