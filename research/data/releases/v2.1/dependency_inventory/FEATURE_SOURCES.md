# 原答与参考特征的上游实现（只读定位）

本表根据实际脚本和输入字段追踪，未重算、未验证数值等价。所有路径相对仓库根；函数可在新版本的独立代码中调用，但原 `main()` 固定输出旧目录，不应直接运行以免覆盖旧成果。

## 参考条件 reference_conditions.csv

入口 `tools/thesis_main/analysis/difficulty_mechanisms_v2_20261020.py`：`reference_traits(floor)`。旧 `main()` 从 `research/statistics/v2_evidence_audit_20261019/records.json.gz` 的非 OOS `records` 取每个 `reference_id` 对应的 `reference_evidence.floor_xz_h`（沿用已存环序，XZ、相机高度为1），一个参考仅计算一次；然后以 reference_id 连接原答。新 `research/data/releases/v2.1/reference_catalog.json` 的 `target_id`、`floor_xz_h`、`points_1024x512` 是已确认的新输入字段；v2.1 的 object_id→chosen_target_id 应从 `reference_bindings.json` 按实际绑定获取，不能默认每张图单一参考或照搬旧 evidence。

- 输入：有限、至少3点的有效 Shapely Polygon；长度 `<=1e-8` 返回 zero_length_edge。相邻边夹角 `turn` 由 arccos 点积求角；`ref_turn3/5/10` 分别严格 `>3/5/10` 度；`ref_short_edges` 为边长/周长 `<0.04` 且两端 turn 均 `>=15` 度的边数。`ref_short_min_horizontal_deg` 是这些边端点方位夹角最小值，`ref_min_horizontal_deg` 全边最小值，`ref_radius_p90_h` 是原点半径 90% 分位。
- `ref_H`：调用 `tools/thesis_main/analysis/scope_difficulty_review_20261011.py` 的 `floor_features(floor)` → `tools/thesis_main/analysis/gt_order_visibility_20261009.py` 的 `visibility_from_floor(floor)`。原点到顶点射线与非相邻墙边的严格内部交叉才记 hidden；`EPS=1e-8`，擦角/共线另列、不算隐藏。多边形无效或相机不严格在内部返回 hidden=None，不能填0。`floor_features.N_turn` 是严格共线阈值的另一个量，不能替代 `reference_traits.ref_turn5`。

## record_conditions.csv.gz

同一 difficulty 脚本的 `main()`：`record_expression.csv` 左连同房结构转移 `record_features.csv.gz` 的 `corner_delta, unmatched_ref_9/12, bottom_bias_9, omission, extension, log_area_ratio`（object_id 一对一），再按 reference_id 多对一连参考特征。`annotation_turn5=pair_n-near_straight_nodes_5deg`，`same_difficulty_target` 是绑定 reference_id 与难度目标 target_version 相等；`personal_sample` 还要求 personal_comparison、independent_vote_eligible 和 peer_n≥3；`reference_sample` 额外要求 quality_usable、同难度目标和可用 ref_turn5。保留不同对象参考身份和失败/缺失，不要直接将原参考计算的记录连接到新参考。

实际角点及底面积函数：`tools/thesis_main/analysis/same_room_structure_transfer_20261020.py` 的 `geometry_features(points, reference)`，生成器 `collect(records)`；读取相同 v2 evidence 的原答 `points_1024x512` 与其绑定 `reference_evidence.points_1024x512`。各点为 1024×512 ERP 的上下交替点对；两者至少6点且原答有限偶数点才纳入。球面底点方向的角距离矩阵交给 `scipy.optimize.linear_sum_assignment` 全局一对一最小成本，再按 9°/12°分别筛选：`unmatched_ref_t=1-匹配参考点数/参考点数`；`bottom_bias_t` 为匹配原答底点 y 减参考底点 y 的平均值（像素，非角度），无匹配为 NaN。`corner_delta` 是原答与参考的点对数差。底点全部 y>256 时 `floor(points)` 以 r=1/tan((y/512−0.5)π) 投到相机高1底面；两多边形有效且面积>0才计算 `omission=1-intersection/reference.area`、`extension=difference(annotation,reference)/annotation.area`、`log_area_ratio=log(annotation.area/reference.area)`。此对应是几何诊断而非物理墙身份或语义漏标。

## BEHAVIOR_RECORDS.csv.gz 与原答几何

`research/workers/personnel_v3_20261021/raw_answer_evidence/taxonomy/discover_behavior_classes.py` 的 `main()`、`load()` 生成该表；`--features-only` 仍会写历史脚本自身所在目录，不适合直接运行。`load()` 输入 `research/workers/personnel_marking_patterns_20261020/record_expression.csv` 与 `research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz`，按 object_id 一对一；Q/T 资格和时间来源照原规则而非所有原答。

`record_expression.csv` 的实际几何计算由 `tools/thesis_main/analysis/personnel_marking_patterns_20261020.py` 的 `geometry_features(points)` 完成，`main()`从 v2 evidence 的非 OOS 对象读取 `points_1024x512`。它调用 `research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py` 的 `viewer_geometry(points)`：以底点射线求相机高度1平面上的底面；底点要求低于地平线至少 0.5°。在可用底面上验证多边形/正面积及边长度，再用与参考相同的边长比例0.04和转折15°规则求 `short_turn_edges`，角度≤5°计 `near_straight_nodes_5deg`；`pair_n` 为底点数，`turn_n=pair_n-near_straight_nodes_5deg` 在 behavior `load()` 派生。`log_area=log(底面积)`；`log_height` 的高度由顶点与成对底点的同一水平半径估计，只在高度>0存在。顶点异常时底面仍可能存在而高度缺失，状态按原函数返回。

`primary_observations()` 以 worker_id/image_id/condition/reference_id/layer 去重：单份直接保留，多份只有恰一份 independent_vote_eligible 时保留该份；personal_comparison 还排除 coordinate repair evidence 并要求有效底面。peer_n 按 image_id/condition/layer/reference_id 聚合；`load()` 中行为量以这些组的可比较对象中位数计算 history 残差，`complex_opportunity` 由组转折中位数≥6定义。质量残差按同图同条件同层同参考 quality_usable 且普通层 ordinary_primary 的可用值均值；时间 log 残差另按 origin 与时间来源分组。LOBO 后按 worker、building 等聚合，不能把全体平均代替每个留出建筑的训练历史。

## DSTRUCT 精确路径

`research/workers/personnel_population_curves_v2_20261023/code/summarize_raw_pool_opportunities.py` 将 `personnel_mixture_comparison_20261022/difficulty/record_opportunity_index.csv.gz` 通过完整团队 `member_object_ids` 接到实际 pool_id；只有 pool_reference_id 与特征的 reference_id 一致才保留参考相关特征，输出 `RAW_POOL_MEMBER_FEATURES.csv.gz`。`build_annotations.py` 将难度目标和 reference_conditions 按 target_id 连接形成 `IMAGE_DIFFICULTY_OPPORTUNITIES.csv`；对象详细几何在 `INPUT_SNAPSHOT.json.gz`。最后 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/classifications/code/build_condition_response_classes.py` 的 `build_records(inputs)` 使用上述三项，计算参考点方位匹配的其他边界特征后按 image_id/condition 求每个指标 peer 中位数残差；`history_eligible` 要求非门洞且难度为简单/中等/困难。DSTRUCT输入 `turn_n, short_turn_edges, near_straight_nodes_5deg, unmatched_ref_9` 的 Manual 全部及困难/难易差；保留每个建筑外留出的所有变换。此分类的匹配边界函数 `matched_boundary_features` 使用水平角差，与前述球面 `unmatched_ref_9` 是不同实现，不能互换。

## 范围与风险

这些实现均已读取，函数/参数/路径是静态源码核查；未执行重算、比较新旧特征、重新建立难度标签或重新拟合分类。v2.1 对象质量库存不包含坐标时，须按 object_id 从真实原答几何输入读取，结合 chosen_target_id 获取对应参考，先检查字段、资格、参考版本和完整环序；不能因 `current_target` 而替代实际 chosen_target。目录与项目地图保持现状，因为这是 v2.1 构建期内部清点，不新增正式公开入口。
