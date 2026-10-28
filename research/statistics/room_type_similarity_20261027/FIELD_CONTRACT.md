# 同用途不同房间：字段、支持与连接合同

本合同适用于 `research/statistics/room_type_similarity_20261027/` 的当前交付。源对象为真人 v2；计算起点 b9bcec809fbaec8ab055931a1abb7baa5db44dac，采用版本 b2b0898b90bd631df37f1f2e75e8380800a43cf8，五个核心输入字节等价。精确版本及路径见 `inputs/INPUT_RECEIPT.json`、`source/MAIN_UPDATE_SOURCE_CHECK.json`。CSV 的实际表头为机器接口；本文件说明关键字段的语义、尺度及关联规则。

## 1. 对象键与分析单位

| 字段或键 | 含义与连接规则 |
|---|---|
| `object_id` | 唯一作答对象键，必须读作字符串；既有长 ID，也有 `v2:new:…`，不能改成整数。连接 annotations、几何、OOF、gate 与案例。 |
| `worker_id` | 匿名人员编号 Wxxx；不同条件保持同一个人身份，但分析分条件。 |
| `image_id` | 源数据的图片身份键。 |
| `image` / `image_code` | 可读图片名，如 b8cTxDM8gDG-07。 |
| `building` / `building_id` | 建筑身份；用于严格跨楼对照和外折。建筑不是房间。 |
| `room_id` | 原记录中的房间字段，可能缺失；本轮不由建筑、用途、Q 或聚类补造。 |
| `condition` | `manual` / `semi`；同一图片的两条件是不同分析池。 |
| `image_key` | `image_code + '__' + condition`；`images.csv` 的唯一键。 |
| `pool_id` | 旧构成研究人员池连接键；本轮不据此创建新团队或新融合端点。 |
| `reference_id` / `reference_version` | 对象实际冻结参考及版本，不按更好 Q 换参考。 |
| `workers_json` / `object_ids_json` | 图片正式作答所含人员/对象清单，CSV 单元格中的 JSON 数组。 |

`annotations.csv.gz` 为全库存 10,439 行、122 列；`annotation_geometry.jsonl.gz` 同样以 10,439 个 `object_id` 一一连接。`images.csv` 为 313 个图片×条件、91 列；`image_labels.csv` 为 261 张图片。主正式子域中 `(image_key, worker_id)` 唯一；不要在全部库存未经资格过滤就假定同样唯一。

跨建筑源图与目标图必属不同物理房间，因此本轮主比较不需要把同楼未知关系当作“确认异房”。原同房声明组不改写，也不将用途相同解释为同一个房间。图对、三图事件和人员记录大量共享图片/人员，事件数表示比较覆盖，不等于独立房间样本数。

## 2. 用途、难度与资格

| 字段 | 语义 |
|---|---|
| `room_type` | 既有用途原标签；保留缺失。源为 v2 audit 的 `image_evidence.room_spatial_classification.coarse_type`。 |
| `room_type_model` | 有标签时与原标签相同；仅真正缺失记为 `__MISSING__`，不根据质量填补。 |
| `room_type_status` | `recorded_purpose`、`missing`、`explicit_unknown`（无法判断）、`multifunction`（开放复合空间）。 |
| `room_classification_sources_json` | 原用途来源记录；从已存元数据引用，不改造成新人工裁定。 |
| `functions_json` / `focus_json` / `boundary_json` | 原用途/范围多维信息；仍为 JSON，不强制压为单一用途。 |
| `difficulty` | 已采用的简单/中等/困难等标签，保留原值及缺失。 |
| `is_oos` / `is_doorway` | 冻结 OOS 与门洞交界身份。 |
| `layer` | 依次区分 `oos`、`doorway`、`ordinary`、`other_or_hold`。对象层普通条件来自 `quality_use='ordinary_primary'`；图片层普通条件按正式对象共同资格汇总。 |
| `formal_quality` | `quality_usable` 的布尔副本，表示冻结正式质量资格。 |
| `quality_use` / `quality_exclusion_reasons_json` | 正式用途及不可评分/暂停的原原因。 |
| `cleaning_disposition` / `geometry_status` | 清洗处置与几何状态，分别保留。 |
| `pool_analysis_eligible` / `independent_vote_eligible` | 原人员池/独立投票资格；不因本轮用途分析恢复被排除票。 |
| `raw_original_available` / `reference_full_available` | 原始完整作答/完整参考是否真正保存。 |
| `binding_status` / `ring_confirmed` / `order_status` | 原绑定、环序与顺序证据。 |
| `origin` / `data_release` | 原来源批次与真人 v2 身份；不混同研究轮次名称。 |

主普通 Manual 过滤为 `condition=='manual'`、`layer=='ordinary'`、`formal_quality` 且 Q/D10 非缺失，5,719 份/177 图/60 人/22 楼。普通 Semi 使用同条件规则，为 901 份/32 图/59 人/12 楼。当前正式支持上 Q/D10 没有缺配。未通过正式质量资格的记录仍在全库存，可用于已有行为/来源说明，不进入本轮正式 Q 的均值或预测。

用途支持的几个不同分母须并列保存：

| 子域 | 定义 |
|---|---|
| `ALL` / 全 177 图 | 所有普通 Manual 正式图片，包含用途缺失/待定/复合/单楼特殊用途。 |
| 已记录用途 163 图 | `recorded_purpose`；其中 2 张特殊用途仅来自一栋楼。 |
| `REPEATED_RECORDED_PURPOSE` / 161 图 | 已记录且在至少两栋实际建筑有支持的用途，共 7 类；5,236 份、60 人、21 楼。 |
| 六大用途 155 图 | 卧室、卫浴、通行与连接、起居与休闲、厨房与用餐、工作与学习；另 6 图为储藏。 |

161 图子域根据标签与跨楼容量决定，不根据模型误差决定；使用同一套全 177 图外折预测直接重聚合。图片预测文件 `LOBO_TARGET_PURPOSE_SUPPORT.csv` 保存每目标楼外同用途历史图/楼数；个人历史支持进一步按实际人员计算，不把用途总体容量自动当成每个人的历史。

## 3. 质量和图片分布

| 字段 | 单位与含义 |
|---|---|
| `Q` / `B8L2` | 同一冻结主质量分数，当前正式对象上两列相同，分数越高越好。 |
| `D10` | 冻结敏感性质量分数，与 Q 在相同正式对象上检查。 |
| `mean_Q` / `mean_D10` | 图片内实际正式人员池的算术平均。 |
| `sd_Q` / `sd_D10` | 图片内正式个人分数的样本标准差，`ddof=1`。 |
| `p10_Q` | 图片正式个人分数经验 10% 分位数，pandas 默认线性插值；不是融合团队 P10。 |
| `low_Q50` / `low_Q60` | 有正式 Q 的图片内分数严格小于 50/60 的比例，非全库存失败率。 |
| `n_records` / `n_formal` / `n_people` | 全对象数/正式作答数/正式人员数。 |
| `n_reference_ids` | 正式对象实际涉及参考数；图片没有唯一参考时汇总参考键留空。 |
| `mean_*` / `sd_*` / `n_*` | 几何诊断的图片内可计算均值/样本标准差/实际可计算数，各指标分别保留支持。 |

各分项原值从 `measurements.same_reference_measurements` 沿用：`iou_2d`、`S_bottom_deg`、`dir`、`Hmean`、`Hcenter`、`height_mean_ratio`、`iou_3d_corner_mean`、`IoU3D100`。这些字段不重新组合为新 Q。

`S_bottom_deg` 是已有底点角误差诊断，单位度。`dir` 在冻结案例接口中是作答自身墙向正交性偏差，不等于与 GT 墙向的逐边对应误差。`Hmean`、`Hcenter`、`height_mean_ratio` 仍按旧质量字段含义使用；尤其不能与下文 `ref_H` 混淆。若分析需要它们的完整原定义，应追踪固定评分源，而不凭列名补造尺度。

## 4. 结构、范围和定位诊断

### 4.1 原答表达

| 字段 | 定义及解释范围 |
|---|---|
| `pair_n` | 保存的上下边界角点对数量。 |
| `near_straight_nodes_5deg` | 近共线节点数，沿用 5° 容差；3°/10° 版本分别保留。 |
| `annotation_turn5` | `pair_n - near_straight_nodes_5deg`，用于把明显转折与近共线分段区分。 |
| `short_turn_edges` | 冻结的短转折边计数，不从类别名称推断。 |
| `turn_delta` | `annotation_turn5 - ref_turn5`。 |
| `actual_simplification` | 原答与参考转折均可算时，`1(annotation_turn5 < ref_turn5)`；否则缺失。 |
| `corner_delta` | 原答节点对数减参考节点对数，包含近共线节点，不能代替 `turn_delta`。 |
| `area_camera_height_sq` / `height_camera_height` | 保存的相机高度归一化面积/高度量；不是平方米/米。 |
| `log_area` / `log_height` | 相应有效正值的对数。 |

`actual_simplification` 是计数诊断，不能自动断言某个必要墙角漏标；更多转折也不能自动判为更好。具体解释需查看原图、完整原答与参考。

### 4.2 五个参考几何预测字段

| 字段 | 冻结含义 |
|---|---|
| `ref_turn5` | 参考地面多边形转角大于 5° 的转折数，排除近共线细分。 |
| `ref_short_edges` | 参考边长/周长小于 0.04，且两端转角均至少 15° 的边数。长条房间端墙也可能满足，不能全部称为细小凹槽。 |
| `ref_min_horizontal_deg` | 全部参考边的端点视线方位角跨度的最小值，按环绕角差计算，单位度。 |
| `ref_radius_p90_h` | 参考地面角点距相机半径的 90% 分位数，以相机高度为单位。 |
| `ref_H` | 假定实心不透明墙时的几何自遮挡代理；**不是房高，也不是照片中家具/窗帘遮挡标注**。 |

辅助 `ref_short_min_horizontal_deg` 只对满足短边定义的参考边计算最小方位跨度；没有短边时保留缺失。`ref_geometry_status` 和原参考键随这些字段一起保留。

含这些特征的模型要求目标已有审定参考结构；本轮以其区分“用途的增量”与“用途只是结构代理”。它不是仅凭 RGB 或完全无 GT 的部署验证。任何目标原答实际结构和目标 Q 都没有作为预测输入。对参考几何的缺失处理由每折训练变换器完成，不用目标结局填补。

### 4.3 同图原答—参考的定位/范围量

以下定义沿用冻结 `tools/thesis_main/analysis/same_room_structure_transfer_20261020.py::geometry_features`，本轮读取保存值：

| 字段 | 精确定义 |
|---|---|
| `unmatched_ref_9` / `unmatched_ref_12` | 底点球面方向一对一最小总代价匹配后，角距分别不超过 9°/12° 的有效匹配数除以参考节点数，再用 1 减去该比值。 |
| `bottom_bias_9` | 9° 有效匹配内 `answer_y - reference_y` 的平均值；单位为 1024×512 标注坐标的像素，正数表示图像中更靠下；没有有效匹配则缺失。 |
| `omission` | `1 - intersection_area / reference_area`。 |
| `extension` | `answer_outside_reference_area / answer_area`。 |
| `log_area_ratio` | `ln(answer_area / reference_area)`。 |

范围三量仅在双方底点均位于地平线下、投影多边形有效且面积为正时定义。该 BEV 投影以相机高度归一化。9°/12° 匹配是同图角度诊断，不是已人工确认的物理墙角身份，也不把异图对应关系自动延续过去。`omission/extension` 不是人工 scope 判断正确率。

## 5. 个人相对结果与预测接口

对对象 i、图片 j 的 Q/D10/转折 y，正式同行数为 n：

`actual_relative = y_i - (sum_j(y) - y_i)/(n - 1)`。

此定义排除本人，只用同图可评价同行形成目标结局。它反映该图上相对同行的表现，绝对水平另由 `observed` 和图片均值保存。不同图片相对结果相关不自动证明用途专长，因为稳定的一般个人能力也会产生相关。

| 文件/键 | 核心字段及含义 |
|---|---|
| `results/personal/OOF_{outcome}.csv.gz` | 唯一 `(object_id, method)`；含 `outcome`、`observed`、`actual_relative`、`predicted_relative`、`error`、绝对/平方误差、楼外历史建筑数。 |
| `HISTORY_SUPPORT_{outcome}.csv.gz` | 每对象一般历史/同用途历史均值及实际 `*_n_records/images/buildings`；源均来自目标楼之外。 |
| `CROSS_BUILDING_REPEATABILITY_ROWS.csv.gz` | `history_type_deviation` 为来源用途表现减一般历史；`target_after_general` 为目标相对表现扣除一般个人预测。用于描述残差重复，不是把目标结果再训练回自身。 |
| `MODELS_{outcome}.jsonl.gz` | 每外折和回归方法的特征、系数、变换和训练建筑信息；强度见 FOLDS/INNER_CV。 |
| `PER_IMAGE_METHODS.csv.gz` / `PER_BUILDING_METHODS.csv` | 同支持方法误差；图片层先平均人员，建筑层再平均本楼图片。 |
| `PER_PERSON_METHODS.csv` / `PER_PERSON_PURPOSE_METHODS.csv.gz` | 每人/每人×用途的实际目标支持及误差。 |
| `PERSON_PURPOSE_CARDS.csv` 及报告补充表 | 原始与去一般历史/几何后的表现、用途增量、图/楼/人员覆盖。 |
| `results/personal_protected_purpose/PROTECTED_PURPOSE_OOF.csv.gz` | 保护一般历史基线后独立收缩用途偏差的有限补充；完整外折、λ 和共同支持均另存。 |

主方法名：`zero`、`person_history`、`same_purpose_history`、`person_ridge`、`person_purpose`、`person_geometry`、`person_geometry_purpose`。其中 `person_geometry` 包括个人与难度/五几何的条件表达；用途方法不是给每个人贴永久场景类型。

主相对模型在目标的**已知人员名单**内对预测中心化，只使用预测值。这个名单来自本轮正式人员池，属于本数据的条件性事后应用设定，不声称在未完成清洗的实际部署前就必然知道全部可用人员。

`gain` / `mae_gain` 通常为“基线绝对误差减新增方法绝对误差”，正值表示误差下降；`error` 为预测减真实。图对距离差的方向定义不同，见下一节。近零/缺失相关系数不能解释为证明所有人员完全相同；例如一张图所有人转折数相同，秩相关没有定义。

旧 gate 分支保留相同目标，按 `same_room_v2_training_allowed` 排除 216 个旧 holdout 训练对象，训练同行均值也相应变化。该分支不是新的外部样本；主模型与此敏感性不互相覆盖。

## 6. 图片对照、三图匹配与均值预测接口

| 文件 | 主键及含义 |
|---|---|
| `results/image/CROSS_BUILDING_IMAGE_PAIRS.csv.gz` | `pair_key=image_key_a+'|||'+image_key_b`，跨建筑无序物理图片对；`common_workers` 为 `|` 分隔的实际共同人员。 |
| `MATCHED_THREE_IMAGE_EVENTS.csv.gz` | `(regime,target_key,source_same_key,source_different_key)`；T 固定，S/C 同一外楼，分别同用途/异用途；三图共同人员使用精确交集。 |
| `LOBO_IMAGE_PREDICTIONS.csv.gz` | `(metric,method,image_key)` 唯一；图片均值 `actual/predicted`、误差及相同支持标签。 |
| `LOBO_MODELS.csv` / `LOBO_INNER_TUNING.csv.gz` | `(metric,method,heldout_building)` 对应模型选择和训练信息。 |
| `LOBO_HISTORY_FEATURES.csv.gz` | 基于目标已知正式名单计算楼外个人历史特征；训练行还排除自身建筑，内校准时重新排除内留出建筑。 |
| `LOBO_TARGET_PURPOSE_SUPPORT.csv` | 每图楼外同用途历史图/楼数、是否已记录、是否跨楼重复用途。 |
| `LOBO_INCREMENT_PER_IMAGE.csv` / `LOBO_INCREMENT_SUMMARY.csv` | 同图同指标的用途增量，图片等权与建筑等权分别保存。 |

共同人员图对每指标至少 3 个可计算共同人员才给相应统计量；每指标支持独立保存。共同人员相对 Q 也排除本人，但这个图对步骤尚未扣除一般个人能力，不能将其直接称为用途特异重复。

三图控制层级为源建筑、S/C 同难度、再加最接近的参考几何。几何邻近匹配不使用 Q。汇总先在同一 S 锚点内平均 C，再对源建筑中的 S 平均，再对目标的源建筑平均，最后按目标图汇总；避免候选控制图多的建筑独占权重。收尾提供 T/S/C 都同难度的严格共同支持表，不能与仅要求 S/C 同难度的分母混读。

距离结果 `same_minus_different` 为同用途距离减异用途距离，**负值表示同用途更接近**；相关差为同用途相关减异用途相关，正值表示更重复。图片/建筑正向比例须随指标语义解释，不能把所有 positive 列都读作质量改善。

图片均值预测截在 0–100；外折整栋留出，内折按建筑校准。12 方法保持相同目标键，模型灵活度对照在同一模型库中比较几何与几何+用途；参考特征的应用条件见第 4 节。

## 7. 时间、scope、筛除和初始化

| 字段 | 语义 |
|---|---|
| `source_time_seconds` | 源作答活动时间，单位秒；仅合法来源、状态和正值进入本轮时间分析。 |
| `target_time_seconds` | 原目标匹配时间字段，保留但本轮不与源时间混合。 |
| `time_source` / `time_source_status` | 语义来源/有效状态；模型分来源拟合。 |
| `time_binding` / `time_source_file` | 原绑定及来源文件。 |
| `time_missing_reason` / `time_target_missing_reason` | 两种时间字段各自缺失原因。 |
| `log_time` | 正源活动时间的自然对数；缺失和非正值仍缺失。 |
| `scope_response_recorded` / `scope_judgement_opportunity` / `scope_correct` | 是否作答、有无相容人工裁定机会、该机会下是否正确；没有机会不补零错误。 |
| `personal_exclusion_category` / `specific_person_error_candidate` | 原排除归因/个人错误候选，不把 GT 暂停自动算作人员失误。 |
| `semi_error_confirmed` / `semi_error_reported` / `semi_known_error_unchanged` / `semi_reported_error_unchanged` | 已确认初始化错误、自报错误以及各自未改状态，保留机会边界。 |

时间两个来源分别为 `(inherited_v1_audited_source, usable)` 和 `(user_processed_reported_not_raw_log_replayed, reported_processed)`；同图同来源至少 3 人才形成相对对数时间。`TIME_LOBO_PREDICTIONS.csv.gz` 以对象键连接，保存 `relative_log_time`、三种预测和外折参数。对数误差单位不是秒，描述表另外报告秒制几何均值及中位数。活动时间不代表排队、真实交付日历时间或货币成本。

本轮 scope、筛除和 Semi 初始化字段仅用于条件支持/机制连接，没有合成总分、改类或开展新的初始化干预实验。

## 8. 计权、缺失和几何文件

主预测误差先对每张图人员等权，再对图片等权；建筑等权则先平均每栋内部图片，再平均建筑。个人卡以人员为观察对象另报，不能把其均值等同图片等权总体。建筑重抽针对已保存 OOF 损失或描述事件的建筑依赖，既不是重新抽人，也不是新增房间或随机进入路径。

空值表示该指标未定义/不可计算，具体资格和来源原因保留在相应状态字段。主预测不把缺 Q 填零；无方差秩相关留空；不合法范围几何留空；没有合法历史时使用脚本规定的基线/收缩回退，并保留 0 历史机会数。不得仅凭缺 Q 计算“融合失败率”，本轮没有新增融合执行。

`annotation_geometry.jsonl.gz` 每行包含身份、资格、`original_points`、`received_processed_points`、`preprocessed_points`、`points_1024x512`、`reference_evidence`、`coordinate_evidence`。不存在的版本保持 null。案例 `CASE_GEOMETRY.jsonl.gz` 与 `CASE_ALL_FORMAL_ANSWERS.csv` 以 `object_id` 一一连接；`CASE_VISUAL_LOCATIONS.json` 提供原图路径、对象与显示窗口。展示完整上下边界时按冻结环序/上下点交替合同解释，不按视觉方便重排。

`code/package_verify.py` 针对真实 ZIP 的 CSV/gzip/JSONL 完整读取和关键对象关联，运行方式见 `REPRODUCE.md`。旧描述统计、构成用途分层、人数 256 自然路径和历史 32 条策略配对均按原身份引用；它们不构成本轮新类别或严格 ABC 试验。
