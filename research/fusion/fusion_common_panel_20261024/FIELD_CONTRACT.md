# 固定共同面板字段合同

CSV 为 UTF-8。`pool_id`、`team_key`、`request_id`、`member_workers`、`member_object_ids` 均保留来源精确键；成员集合按原 ID 排序，不能只按显示名合并。n为实际团队人数，非全部池人数。缺失不是零。

|文件|行键与分母|字段|
|---|---|---|
|`POOL_REGISTRATION.csv`|48个 `pool_id`|原 `layer/condition/difficulty/scene`、图/楼、参考和容量；只用于选样支持。|
|`TEAM_REGISTRATION.csv`|138个原请求|预定n、原随机路径请求、精确人员及对象集合；不按输出成功选择。|
|`METHOD_ENDPOINTS.csv`|`team_key × method`，414条|`full_output`按完整布局能力记；`floor_output`按非空有效底面记；Lee能力是`floor_region`，其full=false为不适用。`full_evaluable`要求同队八个完整指标都非空。|
|`METHOD_GEOMETRY.json`|同上|墙线/medoid为原点对及相机高归一底面；Lee底面为GeoJSON；不修自交、不补连接。|
|`MEDOID_EXCLUSIONS.csv`|具体团队内不可作完整代表的原答|原worker/object和失败原因；无可用代表整队保留失败。本次排除0条，仍有字段表头。|
|`ALL_ATTEMPT_STATUS.csv`|场景层×难度×n×方法|全部尝试、图/楼、输出数、共同可评数、缺连接、不足四对、自交计数。自交缺失不等于false。|
|`COMMON_TEAM_METRICS.csv`|同队×二方法×指标×`support_domain`|`delta=left_value−right_value`。`complete_layout`各项用相同130队完整共同域；`floor_region`按该二方法底面共同域，不能跨分母排三方名次。|
|`COMMON_IMAGE_METRICS.csv`、`COMMON_BUILDING_METRICS.csv`|图/楼×层×n×比较×指标|先按图，再按楼聚合；不把同图的多个n当独立图片。|
|`COMMON_SCENE_SUMMARY.csv`|条件/层/难度/n/比较/域/指标|均值、图等权p10、提高与下降图片数；指标的数值方向按下文解释。|
|`THREE_METHOD_COMMON_FLOOR.csv`|131个三方共同队×方法|三方法各自底面IoU，三方同分母；汇总在`THREE_METHOD_FLOOR_SUMMARY.csv`。|

`B8L2/D10/IoU3D100`单位0—100；`iou_2d`、底角9° precision/recall为0—1；`S_bottom_deg/dir/corner_assignment_mean_deg`为度；`Hmean/Hcenter`为相对高度误差；`centroid_distance_h`为相机高度单位，越小表示位置更近。`diagnostic_turn5_n`为方向变化大于5°的底面顶点数，`diagnostic_short_edge_005_n`为边长小于0.05相机高度的数量；它们是几何解释，不是必要结构真值。`nodes/reference_nodes`为声明角点数，不自动代表语义结构。

普通Manual/Semi、门洞与special原层必须保留；门洞难度“单列”不改成普通困难。OOS没有进入本来源面板。正式/条件质量继承原来源，不因本轮新指标能计算而授予新资格。Lee没有顶部，因此完整质量与3D保持空值；不能把空值填成失败0分。方法全部尝试的失败分母独立于成功共同域。
