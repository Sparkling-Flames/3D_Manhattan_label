# 大块同房新实验：字段与研究台接入合同

版本 `same_room_strict_abc_rebuilt_20261023_v1`；分析版本 `SRLB_REBUILT_20261023_v1`。
实际读取提交 `e92abe8631d7f01dc192ee796b46f295ece37a6d`；原始数据为真人 v2。
本目录是遗失设计之后重新登记、重新计算的实验，不是旧 111,054 个端点的恢复。

## 1. 主键与最短连接

|表|主键|用途|
|---|---|---|
|`design/STRICT_ABC_EVENTS.csv.gz`|`event_id`|62,676 个唯一物理 ABC，保留 D/X/Y/Z 和两视角六个团队键|
|`design/ENDPOINT_REQUESTS.csv.gz`|`team_key`|311,333 个本轮去重原生执行请求；未声称所有键在历史全库从未出现|
|`native_endpoints/ENDPOINT_SCALARS.csv.gz`|`team_key`|所有尝试的标量、状态、实际人员、对象、参考及几何行号|
|`results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz`|`event_id`|不另造团队；精确设计与六端点连接后的逐事件差值|
|`geometry/EVENT_GEOMETRY_RESULTS.csv.gz`|`event_id,view,comparison`|两个视角各 AB/AC/BC，全部 376,056 次事件几何对照；可复用同一团队对计算|
|`design/FROZEN_COMMON_CLASS_MEMBERS.csv.gz`|`pair_key,method,condition,worker_id`|双方正式共同成员、两个 object_id、楼外类别及连续历史|
|`design/CLASS_ROLES_AND_MEMBERS.csv`|`method,condition,heldout_building,tier,class_id`|冻结类、历史中心、角色语义对齐键和真实成员|
|`design/DESIGN_PATH_LINKS.csv.gz`|按表中路径/阶段/事件键|设计路径与实际 ABC 的关联；需保留 nominal_A_role|
|`anchor_paths/ANCHOR_PATH_TRANSITIONS.csv.gz`|`path_transition_id`|真实固定 A 或固定 XYZ 的去重相邻/阶段迁移；不是不同支持均值相减|

从事件访问六端点：使用 `team_A_a/team_B_a/team_C_a/team_A_b/team_B_b/team_C_b`。
`a/b` 只是该直接图对的排序，不表示训练/验证或固定的源/目标。
几何记录以标量中的 `geometry_shard`、`geometry_line_1based` 定位；相对根为 `native_endpoints/`，不能丢失 `parts/<pool_id>/` 目录。
每个 JSONL 行含 `team_key`、原生 `full_state`、几何及缺失/失败状态。`full_state.identity_groups` 与 `node_consensus` 的 feature_id 仅在该团队内有效，不可按同名 node_000 跨队或跨视角认作同一墙角。

`native_endpoints/ENDPOINT_ARCHIVE_LOCATOR.csv.gz` 另把每个团队连到实际 R06 分片文件名，适合按事件只下载所需几何包。分片计划中的历史本地 source 路径是来源记录；实际复用解析 `geometry_shard` 相对路径和行号，不依赖原容器路径。

`pool_id` 绑定图片、条件、冻结参考与正式人员池；`reference_id/reference_version` 与 `image_id/image` 分别保留。
人员编号 `worker_id` 沿用研究匿名编号 Wxxx；`object_id` 是原答主键。原答几何来自冻结预处理后的作答，不擅自恢复被筛除者的投票资格。
物理图对直接关系与原声明组见 `pair_key/groups/relation_version/relation_tier/scope_comparable`。
同一物理图对只在图对等权层计一次；多个重叠声明不是多个独立房间。

## 2. 严格 ABC 与成员覆盖

`A=D∪X, B=D∪Y, C=D∪Z`。四块两两不相交，三替换块都为 m；X/Y 同源类，Z 来自目标类；n=m+|D|。
两视角使用同一批实际人员。成员字段以 `|` 分隔，`D_class_counts` 为逐折类号人数 JSON。
纯块 `D_empty=true`，混合团队 `D_empty=false`；比例保留 `m/n`。分段仅为全队、超过一半、一半、少于一半。

X/Y 采用字典序规范化以去掉 A/B 镜像重复。因此 B−A 是该精确人员调整的有符号差值，不是同类调整固有的升降方向。
`source_role_key/target_role_key` 保留分类家族、类数和中文语义。`JOINT` 结构家族不是 `V3_JOINT_QT`；不能仅按 M/J 编号跨折合并。
`source_workers/target_workers` 的并集列只表示实际覆盖，不是同时存在的队伍；精确队伍在事件表。
`unique_actual_Z_blocks/unique_actual_XYZ_blocks/unique_actual_D_sets` 用于区分事件多、背景多与独立目标块多；不把共享 Z 的多锚点算作多人重复。

## 3. 质量与几何的量纲和方向

|字段|含义|解释|
|---|---|---|
|`B8L2`, `D10`|冻结 0–100 主评分及敏感性评分|越高越好；不可评分缺失，不填零|
|`S_bottom_deg`|相对参考的底面角距离|角度，越小越好|
|`dir`|输出自身最佳正交轴的方向残差|角度；不是相对 GT 的整屋朝向误差|
|`Hmean`, `Hcenter`|冻结相对均高及中心高度误差项|无量纲误差；不是米|
|`IoU3D100`|角点均高棱柱的三维代理|百分尺度；不是完整三维重建真值|
|`iou_2d`|底面区域交并比|0–1|
|`omission`, `extension`|冻结参考遗漏、外扩项|分别保存，不合成新的扣分|
|`fusion_turn_n`|扣除近共线节点后的实际转折数|更多不自动代表必要结构更多|
|`fusion_short_turn_edges`|周长 4% 以下且两端转角≥15°的短边|不与绝对长度 0.03h/0.05h 的另一诊断混用|
|`fusion_redundancy_n`|≤5°近共线分段节点|与真实转折分开|
|`geometry_area_h2`, `centroid_*`, `height_mean_h`|面积、中心、平均高度|相机高度 h 或 h²；不是米/平方米|
|`top_y_mean_px`, `bottom_y_mean_px`|上下边界像素均值|1024×512 冻结坐标；有符号变化不是自动改善|
|`bev_mean_h/top_mean_h` 等|同角点数的循环对应距离|同图、同参考相机坐标，单位 h；不做跨视角坐标硬对齐|

几何对应复用冻结 `corner_distance.corner_compare`。异数、不完整、歧义及大角距警示全部保留；无法对应不设距离为 0。
质量分项在标量表完整保存；各分项的共同六端点有效事件/图对/建筑数在条件表的 `<metric>_common6_*` 字段中。
同时解释质量与某一几何诊断时，应使用明确共同支持；`geometry_summary` 另列 Q 与唯一对应都可用的子域。

## 4. 幅度、重复性、低尾与失败

对每个视角：

```text
within = abs(B-A)
cross  = (abs(C-A)+abs(C-B))/2
extra  = cross-within
BA=B-A; CA=C-A; CB=C-B; CS=C-(A+B)/2
```

事件层跨两视角取算术平均；质量主比较要求同一事件六端点均可评 (`Q_common6`)。
跨类幅度更大不等于升质，也不等于几何距离更大。结构、位置、分项与 Q 分开报告。
`eps0_*` 使用精确零阈值；`eps2_*` 以绝对变化严格超过 2 分为响应；恰为 2 分属于近零范围。
重复性分类：双方近零、双方同向非零、双方反向、单边响应。含双方零的符号一致率独立保存。
源端触发分析先限定六端点共同可评，再分别以每端作为源端计触发；属于共同支持上的回顾性分析。
同时要求两端响应的条件率不能解释成只看源端即可达到的成功率。

`*_loss_gt5_fraction` 为两视角可评差值中损失严格超过 5 分的比例，`*_any_loss_gt5` 为至少一端出现该损失。
这些是精确调整的坏尾，而非 Q 总体分位数。人数路径专题另提供逐图 P10 和样本标准差。
失败使用全部事件尝试或全部去重端点尝试，明确区分六端点引用次数与唯一端点数。
`new_score_failure_*`/`recovered_score_*`、不完整的新增/恢复单列。失败不进入 Q 均值，但始终进入相应尝试分母。

## 5. 时间、历史量与资格

`recorded_time_total_seconds` 只在本队全部记录齐全、总秒数为正、单一语义时提供。
主要三臂两视角时间比较要求六队同一来源语义 (`time_common6`)；联合 Q/T 再要求六队 Q 可评。
`QT4_*` 是另列的四端点补充：仅相应两队、两视角共同 Q/T；不能替代三臂幅度比较的六端点支持。
劳动时间为成员记录之和，不是排队、交付或金钱成本。`source_parallel_active_seconds` 仅为同时开工假设下的活动时间上界诊断。
时间比先逐事件/视角求比，再按配置、图对、建筑作算术汇总；`time_logratio_*` 是另外保存的量，不混称。

`q_X/q_Y/q_Z` 是目标建筑外、同任务调整后的相对 Q 块均值，不是绝对 Q。
`t_X/t_Y/t_Z` 是调整后的对数时间块均值，不是秒。
三块历史 Q 极差≤2（主）及≤5（宽）是预先登记的条件子域；known_n/full_known 保留。
这个子域的效应不能换算成“历史 Q 解释了总体百分之几”。

## 6. 计权、匹配与缺失

同图对、方向、n/m 配置内先平均已覆盖的实际成员组合；再图对等权。
建筑等权先平均该楼图对；声明组分层先平均组内图对，再组、楼等权。它们回答不同集合问题。
`LEAVE_ONE_BUILDING_OUT` 和 `EXCLUDE_UNB_SPECIFIC` 不重新选择团队。
成员较宽匹配固定图对、方向、n/m、D 类别构成；严格匹配额外固定实际 D。
成员 present 指出现在 D/X/Y/Z 并集中；无合法缺席对照标容量/设计受限，不写成零效应。
原均值与匹配均值的权重不同，且支持会减少；这不是删除某人的因果试验。

所有未知、不可评分、不完整、无法对应及缺时间保持状态。Semi 无 m>4 严格容量，不输出伪零效应；已有 Semi 人数路径另按自己的支持报告。

## 7. 与人数稳定性专题的连接

人数专题位于 `research/workers/personnel_population_curves_v2_20261023/stability_rebuilt_20261023/`。
键为 `pool_id/path_id/base_path_id/k/team_key`，精确顺序不变。
完整路径重抽保持策略与自然路径配对；建筑重抽保留建筑内全部图和路径。
P10 和 SD 先逐图、逐 k 计算（SD 的 ddof=1），再按图或楼平均；质量缺失不补零，失败分母用全部尝试。
四策略同语义时间共同支持表与各自时间支持表分别保存，不能相减解释策略差异。
