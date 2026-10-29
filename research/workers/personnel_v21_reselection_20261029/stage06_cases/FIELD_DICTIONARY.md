# 案例字段与路径

- `event_id`：冻结精确事件身份。`source_stage` / `case_source_stage` 区分全局广筛与 focused；不把新增机制选择当成新建类。
- `pool_id` / `reference_id`：合法目标身份；同一原图不同目标不能按 image 合并为一个融合池。
- `A/B/C_members` 与 `D/X/Y/Z`：实际人员编号，用竖线连接；A=D+X、B=D+Y、C=D+Z，各块不重叠。
- `A/B/C_class_vector`：实际对应折内完整类别人数，包括 unknown。类编号不跨折拼接。
- `m` / `actual_m_AB/AC/BC`：换出的具体成员数。`seat_net_change_l1` 是两类席位人数变化的 L1 和，等于2m，不误作换人数。
- `B8L2` / `Q`、`D10`：当前冻结评分。失败Q缺失，不用0填补。
- `nodes`：入选对应组数；只有 `connection_available` 且完整评分资格成立时才有完整融合环，失败时不可据 nodes 宣称完整输出。
- `support`：对应组的独立标注者票数；`D_support` 和 `block_support` / `replacement_support` 是共同背景与换入块的贡献。
- `observations`：对象ID:原答点对索引，跨端点追踪原观察，不依赖 feature_id 同名。
- `IoU3D100`：既定三维代理IoU乘100；BEV `iou_2d` 为0—1。3D绘图空间以相机高h归一化，非实测米制尺寸。
- `source_time_total_seconds`：历史来源库存记录的秒数和；不同于目标专用 `recorded_time_total_seconds`。缺少目标专用时间保留缺失。
- `record_time_*_pct_source_matched`：两个队伍来源种类及人数一致时的百分比；C−B和C−A分别计算，不互相替代。
- `time_comparable_ABC`：三队时间来源人数构成都匹配；某一对匹配不要求另外一对也匹配。
- `trace_file` / `figure_directory`：相对 stage06_cases/；`original_file` 和 CASE_FIGURE_INDEX 的图路径相对分包解压根目录。
- 图中的完整原答：正式输入的全部上下点对，保留其原来点序与资格；仅为绘制跨ERP接缝的连续边界作断开，不移动/补造角点。
- `m_all_B8L2` / `m_all_log_time` /结构历史中心：沿候选原方法采用的图内中心化历史特征，不能直接读成原始质量分或秒数。
