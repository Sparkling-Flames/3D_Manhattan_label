# 分项与几何变化字段

以下字段均按同一图片、同一参考比较两个精确团队 A→B，再跨视角比较其变化。不跨视角直接匹配坐标或假定相机已配准。

## 已有端点分项：直接计算 B−A，不需再次评分

| 字段 | 含义、量纲 | 好方向 |
|---|---|---|
| `B8L2`, `D10` | 冻结总质量分，0–100；D10 只改自身方向尺度 | 增加 |
| `iou_2d` | 当前固定参考的底面 IoU，0–1 | 增加 |
| `IoU3D100` | 冻结平均角点高度三维代理 IoU×100，不是完整任意三维体积真值 | 增加 |
| `S_bottom_deg` | 重建底边界与参考的双向球面距离，角度 | 减少 |
| `dir` | 候选自身最佳正交轴上的方向残差，角度；不是与外部绝对墙向的差 | 减少 |
| `Hmean` | `abs(候选周长加权平均墙高 / 参考周长加权平均墙高 − 1)`，无量纲 | 减少 |
| `height_mean_ratio` | 上述有符号比例，理想为 1；可判整体过高/过低 | 接近 1 |
| `Hcenter` | 先只将候选垂直高度轮廓均值居中，再算最近底面位置双向高度均方根残差/参考平均高度，无量纲；反映局部高低不一致 | 减少 |
| `omission`, `extension` | 分母均为参考面积：`(A_GT−交集)/A_GT`、`(A_pred−交集)/A_GT` | 减少 |
| `height_mean_h` | enrich 中顶底点重建高度的角点算术均值，单位相机高度 h；与评分的周长加权平均高不是同一统计量 | 有符号变化，需解释 |
| `top_y_mean_px`, `bottom_y_mean_px` | 1024×512 ERP 的顶点/底点 y 坐标均值 | 有符号变化，需解释 |

Hcenter 的临时居中仅用于统计度量，没有修改融合几何或另行认可布局。B8L2 把底面忠实度和自身方向损失以 L2 合并，不能把分项差直接相加为分数差；必要机制可以调用冻结 `working_models.attribution()` 做删除分项诊断，但它不是因果效应。

由冻结面积公式，`extension−omission = A_pred/A_GT−1`，可描述净面积内缩/外扩。它可能在遗漏、外扩同时很大时接近零（例如位置偏移），所以与 `omission+extension`、定位分项联合解释，不能独自充当范围或定位正确性。

## 已有结构与参考支持

- `nodes` 是冻结融合节点数。
- `fusion_turn_n`、`fusion_short_turn_edges`、`fusion_redundancy_n` 是当前人员构成包的固定几何表达定义：冗余转角 ≤5°；短边长度/周长 <0.04 且两端转角 ≥15°。
- `ref_node_recall_5/9`、`ref_edge_recall_5/9` 是 5°/9°一对一角点及相邻边对应的参考召回。
- `diag_corner_recall_05`：参考与候选转角 >10°的角点，在 `0.05×sqrt(参考面积)`距离内先最大化匹配数、再最小化距离的召回。
- `diag_wall_coverage_03/05`：墙向差 ≤10°且投影到参考线附近 `0.03/0.05×sqrt(参考面积)` 带内的参考边覆盖比例。
- 这些参考几何指标不自动意味着“必要结构”人工真值，不能惩罚所有错误新增墙，也不替代原图解释。
- `minimum_support`、`node_supports`、`selected_support_min`、`identity_groups_n`、`unselected_groups_n`、`minority_observations_n` 均由原冻结融合保存；`node_supports`是身份组票数，不是所有附近原点命中数。

## 同图 A/B 对应位置变化

`geometric_effects.prepare()`每端点验证一次，`compare()`沿用仓库 `corresponding_corner_distance_v2`：要求同点数、有效完整几何，同方向环序（必要时只改变对应方向），选择最大顶/底球面距离最小的唯一循环移位。没有旋转、平移、缩放拟合。

| 输出 | 意义 |
|---|---|
| `status` | `unique_cyclic_candidate`、`different_corner_count`、`missing_connected_geometry`、`incomplete_geometry`、`ambiguous_cyclic_match` 等真实状态 |
| `bev_mean_h/max_h` | 对应底点 BEV 距离，单位相机高度 h |
| `top_mean_h/max_h` | 对应顶点三维距离，h |
| `bottom_angular_mean_deg/max_deg` | 同一候选对应下的底点球面距离 |
| `top_angular_mean_deg/max_deg` | 同一对应下的顶点球面距离 |
| `signed_height_change_mean_h` | 对应顶点的平均垂直变化 B−A，h |
| `matched_reflex_disagreement_n` | 对应角点凹/凸身份不同的数量 |
| `exact_geometry_equal` | 连续原顺序顶底坐标严格相同 |
| `cyclic_geometry_equal` | 循环对应后所有3D顶底坐标相同（数值容差1e−12） |
| `high_angle_correspondence_warning` | 最佳对应的最大顶/底角距离 >12°，解释时查看对应是否仍合理 |

点数不同不强行补点求平均距离。两视角“结构变化相似”应报告两个视角的转折、短边、冗余等变化向量，另列双方结构都不变；不能只凭最终点数相同称局部结构完全相同。

## 跨视角效应状态

`paired_effect_state(dx,dy,tolerance=2)`将质量差分成：双方都在±2分内；只有源端实质变化；只有目标端实质变化；双方实质同向；双方实质反向。±2是解释阈值，不是数值严格相等；可另给 0/1/5 分敏感性。两端都接近零不计为“同向改善”的成功。结构计数则可用0阈值作确切整数变化比较。没有用目标端阈值挑出“好迁移样本”后再声称可预测总体。

## 层级汇总建议

主结果先在每个直接同房图对内部，对背景/实际替换/类别方向等重复求分布；再对图对或建筑等权汇总。并排给出图对数、图片数、建筑数、精确团队数/实际调整数。大量面板队不当作大量房间。机制研究可以保留强正例与反向例，结合原图、原答与局部身份组票账解释。
