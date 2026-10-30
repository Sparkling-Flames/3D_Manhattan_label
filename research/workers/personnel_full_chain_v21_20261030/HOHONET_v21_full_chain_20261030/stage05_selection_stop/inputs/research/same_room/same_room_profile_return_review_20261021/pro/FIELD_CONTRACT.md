# 综合字段合同与研究台连接

本包分析版本 `same_room_quality_person_uncertainty_20261021_r1`。主输入commit `561584c8f64d5349d497ec1c6e91f1aeb4bbd7c9`；Dot固定PR输入 `e83286b7814afc614253aa392050e9a3851ae058`。本文件连接各分支，不改变仓库原有字段含义。

## 一、稳定键

|键|含义与连接|
|---|---|
|`object_id` / `target_object_id` / `member_object_ids`|如 `v2:new:...`，逐份原答ID；连接固定 `records.json.gz`。同人同图不应自行合并来源不同的记录|
|`image_id`|完整Release图像ID；原图文件为 `<image_id>.png`。通过图像索引映射可读简称|
|`image_code` / `image` / `target_image`|例如 `pa4otMbVnkk-42`；可读简称，不替代完整图像键|
|`building_id` / `building`|建筑层，不能当房间ID|
|`group_id` / `group_ids`|用户原声明组；允许一对/一图属于多个组。组数不可解释为相互独立的物理房间数|
|`pair_id`|分支内直接图对键；请同时保留两端图像与关系版本。房间/个人分支与团队分支可能使用不同字符串算法，不跨分支只凭裸pair_id连接|
|`relation_version`|`same_room_user_working_classification_20261016_v2`；沿用直接采用，不补传递关系|
|`scope_comparable`|实际目标范围是否可比较，独立于物理同房；未知保持未知|
|`reference_id` / `reference_version` / `chosen_target_id`|冻结质量参考与目标。G202两端参考版本不同，连接时不可省略|
|`condition`、`layer`、`origin`|Manual/Semi、普通/门洞/特殊、new/v1分别保留；它们定义资格与时间语义|
|`worker_id`|匿名人员键；个人所属类别取目标建筑排除版本|
|`heldout_building` / `label_version`|人员标签版本与楼外折；本轮采用校正 `labels/lobo_labels.csv`，不是全数据标签用于预测|
|`pool_id`|固定目标图片、条件、资格/参考池；团队键必须连池解释|
|`team_key`|池键＋排序实际成员的哈希。`member_workers`/`member_object_ids`保留精确成员。相同构成不等于相同团队|
|`path_id`、`event_id`|本轮固定A/B/C块、嵌套背景的替换路径及一个视角/人数事件；两视角完全相同成员替换通过path_id+n连接|
|`row_id`|个人预测输出到 `prediction_design.csv.gz` 的历史划分键；须带 metric 区分B8L2与D10|
|`local_feature_key`|本轮单图局部窗口键，例如G117某视角某转折；不是新增物理跨视角对应。身份组feature_id仅在一次融合状态内有意义|

## 二、质量、相似性与预测字段

- B8L2为主、D10敏感性，均分越高越好；`dir`为内在方向偏差，不是相对GT墙向误差。`Hmean/Hcenter`依固定引擎定义，不能擅自解释为百分比。
- 实际池均值：该图所有当前正式主观察。共同池均值：该对两端同一名单。三图匹配背景使用A/B/X同一名单；全组共同池另有严格支持，不与成对交集混用。
- 相对Q：本人Q减同图其他人员均Q；外部θ：目标建筑之外、沿用训练许可的普通Manual个人历史相对Q均值，历史同行也限训练许可；描述性剩余：相对Q−θ。个人分支排除本人及目标楼规则详见其字段合同。
- 描述性相关使用两端结果，不作为留出输入。预测P为所选且本人实际作答源图的同行公共均值；`source_n`与组级历史图数m分开，缺少本人源作答不补出。
- 个人 `main_prediction_rows_wide.csv.gz` 是主要规则逐历史精确预测；完整方法搜索结果在 `prediction_summary.csv`、`prediction_group_budget.csv`；模型参数及探索扩展时序另存。
- 平均主实验保留m=1和所有m>N/2；`min_majority`/`max_history`只是可读端点，不代表删掉中间实际m。
- 同类/跨类几何距离只在双方可算、角数相同、环对应有唯一候选时给数值。异数、未完成、歧义分别保存，NA不转为0。

## 三、替换与政策字段

`A_workers`为锚定组，`B_workers`同类替换，`C_workers`跨类替换；三块互不重叠且核心相同。`net_B8L2=C−B`是跨类相对于同类替换的净差，不是C−A，也不等于“增加一个人”。`n/m`为团队人数/实际替换人数。`block_history_Q_gap`是换入块与换出块的楼外Q均值差，不能当目标Q差。

`capacity_random`使用稳定种子在容量内选块；`outside_Q_gap_le3`仅在两块外部Q差≤3且历史有支持时选块。这一Q重叠支持与全体容量随机支持不同，不解释为总体类别因果效应。

`outside_Q`是楼外Q排序团队；`source_Q`是本人源Q排序；`half_Q`两者各半；`half_Q_structure`是保持混合均Q下降≤2的条件下提高M1人数；`outside_Q_outside_T_fast`/`outside_Q_source_T_fast`分别用楼外调整时间/单源活动时间做省时替换。候选名单和所有源图信息在目标评分前固定。

三次随机团队在同一目标/源/预算内部作为随机政策期望平均；不是三倍独立图片。`delta_Q`与`loss_over5`使用同目标、同人数、同候选名单下的楼外Q团队作基准，仅在两者可评分时有值；`complete_rate`和`both_scored`另表保留。故有失败时边际均值差不必严格等于配对delta。

## 四、劳动与停止

**重要历史字段别名：** 原生团队中的 `source_time_total_seconds` 指这支队伍在当前池图片（即选队目标）的记录活动时间。本轮策略表明确另存 `target_activity_seconds`；它不是源视角历史取得成本。真正源视角字段为 `selected_source_activity_seconds`、`source_roster_activity_seconds`。

省时主比较只用 `new_timed_history`；不补时间，不把旧/新不同计时语义无条件相加。时间比为同目标配对比的对数逐图/建筑平均后指数化。停止时间主表是另一统计量：先求目标平均时间之比，再层级平均；不能互换数字。

停止 `requested_k`（或决策所选k）与几何补收后 `actual_k` 分开；源Q选人数、目标几何完整补收、纯目标在线稳定分别定义。`full_common_pool`是每池实际上限，不是每图所有人员。

`loss_gt5_to_full_rate_paired`与`loss_gt5_to_fixed7_rate_paired`分母/基线不同；Q<50/80是绝对低尾；P10是逐目标路径分位数再层级平均。完整率不是以上任意一个质量量。未知/不可算保持缺失。

## 五、几何、图像与复原状态

原图2048×1024；处理后标注/参考使用1024×512坐标，顶部/底部绑定点序保留。图中ERP曲线由冻结球面投影绘制。BEV、推导3D以相机高h归一，不是实际米制。不同视角各自相机框架，没有凭空估计共同坐标配准。

图像清单的 `archive/archive_path/image_id` 为可移植定位；`file`保留本次原始取得路径，重画时不用该旧绝对路径。`indexed_sha256_verified=false`表示Release索引无既有SHA可比，本轮仍计算了CRC与SHA并留存。

恢复身份有四类：仓库原始证据引用、本轮重建、本轮新增、旧原件未恢复。`RECOVERY_AND_CHANGELOG.csv`逐条给状态、文件与判断。新的请求库不能被描述为上一轮丢失请求库的原件。

更细字段见各分支 `FIELD_CONTRACT.md/json`。所有表以UTF-8输出，JSON缺失使用null，CSV缺失为空；不通过插值制造完整曲线。
