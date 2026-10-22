# 字段、分母与来源

本模块只重新关联、汇总和绘图，不改原答、不重算融合、不重评分。冻结输入提交为 `ef148c82df18582228b2d23837faa2659e79eba7`，实际底层数据为真人 v2。

## 原答库存与楼外标签

| 字段／字段组 | 实际来源 | 本模块处理与解释 |
|---|---|---|
| `object_id, worker_id, image_id, image_code, building_id, condition, origin` | `personnel_v3_20261021/raw_answer_evidence/taxonomy/BEHAVIOR_RECORDS.csv.gz` | 原标识保持；`origin=v1` 指历史人员来源，不是底层数据版本 |
| `coarse_label, fine_label, heldout_building, selected_family, known, missing_reason` | 同目录 `ALL_METHOD_LABELS_LOBO.csv.gz` | 只匹配目标建筑折；不跨折拼类别编号，不用 ALL 描述标签检验目标图 |
| `q_history, q_downside, t_history, turn_history, short_history` 等 | 同一冻结楼外标签表 | 历史 Q/T/结构特征保留来源和支持；不是当前图的个人 Q/T |
| `role, role_group` | 同目录 `OUTER_CLASS_ROLE_MAP.csv.gz` | 按每折训练历史中心，既有最高／最低角色；本模块未重新选类 |
| `current_difficulty, target_id, is_oos, is_doorway` | `difficulty_mechanisms_v2_20261020/scope_closeout_20261022/image_scope_support.csv` | 当前主线简单／中等／困难与资格；不从低 Q 或失败反推难度 |
| `same_current_target, primary_behavior` | 上述表与原答原参考关联 | 主原答要求可用行为、普通条件、当前目标一致、非 OOS；其它库存行仍保留 |
| `complex_opportunity` | 冻结原答行为表 | 同图实际转折中位数≥6 的机会标签，不是主线难度 |
| `ref_turn5, ref_H, ref_short_edges, ref_geometry_status` | `difficulty_mechanisms_v2_20261020/record_conditions.csv.gz` | 参考几何机会；H 为几何自遮挡指标，不是 RGB 遮挡 |
| `turn_n, short_turn_edges, near_straight_nodes_5deg` | 冻结行为表 | 实际转向、短转折边与近共线冗余点分别统计，不能用总角点代替 |
| `unmatched_ref_9/12, bottom_bias_9` | 难度原答诊断表 | 对应参考的原答诊断，不是融合内部墙角对应阈值 |
| `reference_turn_deficit/excess, reference_reduced/extra` | 当前参考转折与原答转折的差 | 只在参考和资格支持时计算；多于参考不是自动错误 |
| `B8L2,D10,quality_usable,quality_use` | 冻结个人评分／资格 | 原资格不通过时主 Q 留空；行为可用不会恢复组队或评分资格 |
| `source_active_time_seconds,time_source_kind,time_task_key` | 原行为表与 `personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz` | 单位秒，保留既有时间来源；并非新测生产耗时 |

`log_time_peer_delta` 是按既有图与来源调整后的时间对数指标。本模块快慢按楼外 `t_history` 定向，要求差至少 `ln(1.5)`；“近 Q”要求楼外相对 Q 差绝对值≤3 分。两人必须同来源、同目标折联合类，有当前图同参考记录。所有缺机会和无时间留空，不以零替代。

## 原答对照的汇总层级

`role_image_contrasts.csv.gz` 是每图同条件、同参考、角色两侧各至少 2 人的精确对照。`source=all` 表示现实来源混合的总差异，`new`、`v1` 表示同来源补充。每指标先对角色内实际人员取均值，再算高角色−低角色。

`role_difficulty_summary.csv` 与 `same_class_nearQ_speed_summary.csv` 的主 `building_equal_mean` 均先图内汇总、楼内平均，再楼等权。`images/buildings` 是该指标有值分母；`positive/negative/zero` 包含无明显差异。角色所有层级和指标是关联结果，不当作独立重复实验。

`same_people_speed_difficulty.csv` 改为同一有向快／慢人员对，要求简单与困难各至少 2 图；先各难度内按图／楼汇总，再比较困难−简单，最后人员对等权。它与图楼等权问题不同。人员对共享人员，63 对不等于 63 个独立实验。

`same_building_easy_hard.csv` 则固定类别方法、角色、来源和建筑，比较该建筑不同难度图片的角色差。它控制楼集合变化，没有控制图片或背景成员完全相同，不能称纯难度因果。

## 融合结果与难度连接

输入由本轮相邻换类模块提供：`exchanges/ALL_CONDITIONS.csv`、`ALL_IMAGE_EFFECTS.csv.gz`、`ALL_BACKGROUND_EFFECTS.csv.gz`。85 个条件保留 `analysis_batch, study_group, method_id, condition, tier, source_domain, direction_role, n, actual_m_AB/AC/BC, design`；相同类别编号不跨楼直拼。

| 字段组 | 含义 |
|---|---|
| `same_*` | B−A，同类换人；A=D+X、B=D+Y |
| `cross_*` | C−A，跨类相对原队；C=D+Z |
| `net_*` | C−B，跨类相对同类替换 |
| `symmetric_*` | C−(A+B)/2，沿用相邻模块定义，保留但不冒充 C−A |
| `within_abs_*` | `abs(B−A)`，变化幅度不表示更好 |
| `cross_abs_*` | `abs(C−A)`；与同类对比时保持已登记人数、实际 m 与 D |
| `B8L2,D10` | 冻结综合分；D10 只改变方向项尺度，几何不变 |
| `iou_2d, S_bottom_deg, dir, Hmean, Hcenter` | 冻结底面、底点、融合自身正交方向和高度分项；dir 不是相对 GT 的朝向误差 |
| `IoU3D100` | 既有角点平均高度棱柱代理，不能表述为完整真实三维网格 IoU |
| `omission,extension` | 相对参考底面积遗漏／外扩；不是额外独立罚项 |
| `nodes, fusion_turn_n, fusion_short_turn_edges, fusion_redundancy_n` | 融合角点、实际转折、短转折边和冗余；后三项连接本轮 `inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz` 的冻结几何派生值 |
| `ref_node/edge_recall_9, diag_*` | 既有参考对应和局部结构诊断，不作为独立语义裁定 |
| `geometry_area_h2, height_mean_h, top/bottom_y_mean_px` | 原端点几何单位为相机高度或 1024×512 参考帧像素 |
| `recorded_time_logratio` | 合格来源时间总和的比值取 log；聚合后用 `100*expm1` 转百分比，不把预测误差转成工时收益 |
| `A/B/C_failure, *_loss_gt5/10` | 分别保存失败与可评分质量下降；失败不当作 Q=0，不从事件分母消失 |

`exchange_difficulty_join.csv` 对每图当前难度进行精确连接，2,641 个条件×图记录全部一致。该连接不是新人工难度重标。

`exchange_difficulty_full.csv.gz` 是每条件×难度×指标的完整结果：每项独立 `images, buildings, image_equal_mean, building_equal_mean, image_median/p10/p90` 及正／负／零数量。`exchange_difficulty_core.csv` 为 201 格宽表；逐楼结果可重新聚合。`exchange_same_building_easy_hard.csv.gz` 保留同楼简单／困难对照，限制与上文同理。

## 两个新机制目录

`case_7y13_background` 的 924 对是同一候选 12 人选 6 的全部有限集合，在固定新增 13 个背景成员路径 n20→33 的终点比较；不是全池所有成员，也不是固定 n 的 ABC。输入是本轮 `configurations/CASE_7y13_BACKGROUND_ADDITION_PAIRS.csv.gz` 及恢复的 `v3_finite/composition/batches/batch_001` 确定性端点。面板字段 `__v1__` 表示 `variable_panel_no=1`，与来源和数据版本均无关。只保存 6 个必要端点和 37 位原答；真实原图来自已经接收的 closure `mechanisms/originals` 单张图，哈希见回执。

`case_qdown_pa4` 从完整 `manual_joint_A` 中保留条件 n20/m3 的全部难度分母，2,810 个物理严格三队互不重复。某一 C 端点可与 10 种 X/Y 分割组成 10 个事件，因此 `failed_events` 不等于独立失败端点。`DIFFICULTY_SUPPORT_AND_RISK.csv` 并列事件数、不同 A/B/C 数、图楼背景分母与标准楼等权率；没有混用。

本例选择 pa4-18 的 100 个事件中距净 Q 中位数最近的一条，保存完整 100 个图内事件并保留 5 个净负向。类别中心严格复用原登记方式：此折 Manual 全部已知人员的历史类均值，实际 n20 团队限新来源有标签人员。每个端点可从 team_key 关联完整库存，必要原答由 `v2_evidence_audit_20261019/records.json.gz` 导出，点序与处理后的坐标均不修改。

## 可复现与文件保存

五个实际分析／渲染脚本均在本目录。原答分析依赖仓库输入；机制导出依赖恢复的端点和原答库存，具体文件名已写入脚本与各 `RECEIPT.json`。所有必要案例几何已经随模块单独导出，读图不依赖全库缓存。

`FILE_INDEX.csv` 是最终实际文件列表，含相对路径、字节、SHA256、可解析 CSV 的行列数、角色与阶段。它不列不存在的包，也不把原图全集或虚拟环境打入模块。gzip 按完整字节原子保存并读至 EOF；PNG 已通过完整读取和可视检查。`FINAL_RECEIPT.json` 记录最终数值和完整性验证。研究报告采用关系由现有人员主报告维护，本文件只说明本模块字段和来源。
