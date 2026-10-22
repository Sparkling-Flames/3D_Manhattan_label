# Semi 换类续研：字段、来源与复现

## 1. 入口与文件层次

本目录从 `REPORT_ZH.md` 与 `EFFECTIVE_SEMI_CONDITIONS.csv` 阅读。`EVENTS_COMPLETE.csv.gz` 为 13,882 条完整逐事件结果，不是索引；`EVENTS_REGISTERED_ALL.csv.gz` 为评分前冻结的同一事件清单。`CONTINUOUS_QT_COMPLETE.csv.gz` 为 886 条同支持连续基线比较。完整团队端点存于本轮公共 `native/batches/*/ENDPOINT_SCALARS.csv.gz` 和 `ENDPOINT_GEOMETRY.csv.gz`，旧端点直接引用历史 compact；每个实际来源及 SHA256 在 `ENDPOINT_SOURCE_REFERENCES.csv`。

| 类别 | 文件 | 用途 |
|---|---|---|
| 推荐与完整条件 | `EFFECTIVE_SEMI_CONDITIONS.csv`、`CONDITION_RESPONSES.csv` | 推荐条件及全部尝试的效应、图楼分母、失败与时间 |
| 分类 | `INHERITED_LABELS_LOBO_WITH_UNKNOWN.csv.gz`、`CLASS_ROLES_AND_MEMBERS.csv`、`TRAINING_CLASS_CENTERS.csv` | 逐折标签、未知原因、实际成员及历史中心 |
| 类中心适用性 | `CLASS_CENTER_VS_AVAILABLE_SUBGROUP.csv` | 全历史类中心与目标图实际可用人员的楼外历史比较 |
| 精确覆盖 | `CAPACITY_ALL_ATTEMPTS.csv`、`ALL_CLASS_CONFIGURATIONS.csv`、`COVERAGE_BY_CELL_AND_LAYER.csv`、`FULLY_ENUMERATED_CELLS.csv` | 容量不足分母、全部 631 配置、成员／背景覆盖、8 个完整整格 |
| 冻结请求 | `DESIGN_FREEZE.json`、`CONFIGURATION_COMPLETION_FREEZE.json`、`EVENTS_REGISTERED_ALL.csv.gz` | 预先冻结范围、种子及精确成员 |
| 完整结果 | `EVENTS_COMPLETE.csv.gz`、`CONTINUOUS_QT_COMPLETE.csv.gz` | 三队各端点分项、三种变化、结构／几何及控制 |
| 背景与成员 | `BLOCK_BACKGROUND_RESPONSES.csv.gz`、`MEMBER_RESERVOIR_RESPONSES.csv`、`SOURCE_MEMBER_BLOCK_ASSOCIATIONS.csv` | 固定背景重复性、成员出现关联 |
| 图楼聚合 | `IMAGE_N_M_RESPONSES.csv`、`BUILDING_N_M_RESPONSES.csv`、`IMAGE_OVERALL_RESPONSES.csv`、`BUILDING_OVERALL_RESPONSES.csv` | 图／楼均值、同向与反例 |
| 风险与分母 | `FAILURE_AND_QUALITY_TAIL_COUNTS.csv`、`METRIC_DENOMINATORS.csv` | 失败唯一端点、物理事件与各指标分母 |
| 人数路径 | `NESTED_N_RESPONSES.csv.gz`、`NESTED_N_RESPONSE_SUMMARY.csv` | 固定成员块、嵌套共同背景随 n 的实际变化 |
| 对照 | `CONTINUOUS_QT_SAME_SUPPORT_SUMMARY.csv` | 无选择机会、实际不同团队与完整控制分别汇总 |
| 案例 | `SELECTED_CASES.csv`、`mechanism_cases/` | 精确事件选择、原答—票账—融合状态 |
| 分批恢复 | `completed_pools/`、`POOL_COMPLETION_LEDGER.csv`、`EVALUATION_PROGRESS.json` | 每池结果完成即落盘；端点未齐时保留已完成部分 |

## 2. 关键字段

### 事件身份与设计

- `event_id`：有向事件唯一标识。A/B 镜像是不同 event，但同一物理 ABC，统计时不得作为两张独立图片。
- `pool_id`、`image`、`building`、`condition`：准确图片池、图、楼、采集条件；本目录条件恒为 Semi。
- `analysis_layer`：`source_partition_expansion` 是主层，冻结储备内完整枚举源块划分；`configuration_completion` 是 441 个先前未覆盖配置的单次物理 ABC 补齐层。两层分开汇总。
- `cell_id`：图片×逐折类别方向×n×m；`reservoir_id` 是源／目标成员储备；`background_id` 是精确 D；`config_id` 是完整类别人数配置。
- `n`、`m_AB`、`m_AC`、`m_BC`：实际团队人数及两队实际更换人数。纯块主设计均为登记 m；实际成员差由集合核验。
- `source_class`、`target_class`：仅在 `heldout_building` 对应折内解释的编号；不能跨楼按 K 号硬合并。
- `common_background`、`outgoing_block_X`、`same_count_block_Y`、`changed_count_block_Z`：竖线分隔的精确 worker ID；A=D∪X、B=D∪Y、C=D∪Z。四块不交。
- `team_A/B/C`：去重后的实际成员集合端点键。多个事件可使用相同端点，终点不重复计算。
- 类别人数向量、`class_center_delta_*`：实际席位变化与楼外历史解释。新增目标 m 人、源类减少 m 人，不等于总人数增加。

### 端点、质量与变化

- `A_*`、`B_*`、`C_*`：各队原端点，包括 B8L2、D10、IoU3D100、iou_2d、S_bottom_deg、dir、Hmean、Hcenter、omission、extension 等；定义完全沿用现有冻结评分合同。
- `same_*`：B−A；`cross_*`：C−A；`net_*`：C−B。汇总表对应字段为建筑等权均值。
- `C_minus_mean_source_B8L2` 等：C−(A+B)/2，不随任意 A/B 命名变化。镜像平均净 Q 与此相同。
- `common_quality_within_abs`、`common_quality_cross_abs`：共同可评分条件下 |B−A| 与 |C−A|。B−A 有符号均值按完整源划分和镜像设计抵消，不能用来证明稳定。
- `all_scored`／`all_complete`：三队可评分／完整性状态。主 Q 分项在共同三队可评分支持上比较；原事件保留各两队可计算数值和缺失。失败单独分析，不填零分。
- `A/B/C_failure`、`score_status`、`below_four`、`connection_available` 等：失败及具体状态。
- `net_loss_gt5`／`net_loss_gt10`：C−B 严格小于 −5／−10。条件表为分层建筑等权率；风险计数表另给原始唯一 B–C 比较数和原始比例。
- `*_minimum_support`、`*_node_supports`、`*_identity_groups_n`：现有融合票数与门槛诊断。不能以这些诊断替代完整对应和连接分析。
- `common_geometry_*`：冻结两队几何差异，区别于两队各自对参考的质量差。质量相同不自动等于几何相同。
- `ref_node_recall_9`／`ref_edge_recall_9`、`fusion_short_turn_edges`、`fusion_redundancy_n`：参考节点／边及结构表达诊断。9°是该诊断角阈值，不是融合内部墙角对应参数。
- `dir` 为冻结算法的轴／正交方向残差，不表示相对 GT 整体旋转；ERP 像素均值、高度比和面积比是有符号几何变化，不自带“越大越好”解释。

### 时间

来源是库存 `user_processed_reported_not_raw_log_replayed`，单位秒。`*_source_time_total_seconds` 为团队全部成员的记录秒数之和。只在两队 n 条时间均已知、来源单一且相同、总量为正时比较；本轮新批域支持这些条件。

`*_recorded_time_logratio=log(T_后/T_前)`。汇总先按质量同一层级聚合 log 比，再用 `100×(exp(均值)-1)` 转百分比，因此它是几何平均比值。它不是各事件百分数的简单算术平均，也不是新测的生产墙钟耗时、并行完工时间或算法运行时间。时间分母不强制等于三队可评分分母，表内分别保留。

### 连续对照

连续 QT 在与类别 C 相同 D、同剩余候选人员域选择 m 人，用目标建筑之外的 `z(q_history)−z(t_history)`。保存 `team_QT`、精确 QT 块、候选集合、`C_QT_actual_m`。剩余候选恰好 m 人的控制无方法选择机会；有选择机会但结果相同与实际不同端点分别统计。该基线不是所有可能连续策略的穷举。

## 3. 聚合与分母

主层按“源块划分→共同背景→成员储备→方向/n/m 格→图片→建筑”等权。主层 13,000 有向事件对应 6,500 物理 ABC；总体计入补齐层为 13,882／6,941。全员集合或无可替换成员不会用零波动充当分类有效证据。不同 n/m 支持的图片域不同，跨行均值不直接当作人数因果对照。

`CAPACITY_ALL_ATTEMPTS.csv` 的理论容量与机会不足行覆盖完整候选范围；其中 `registered_*` 列保留初始主层登记身份，合计 6,500 个物理 ABC、190 个已登记配置。最终补齐后的 6,941 个物理 ABC、631／631 配置，以 `EVENTS_REGISTERED_ALL.csv.gz`、`COVERAGE_BY_CELL_AND_LAYER.csv` 与 `COVERAGE_RECEIPT.json` 为准；不能把初始容量表的登记列当作最终覆盖。

失败同时给物理 ABC 数、唯一源／目标端点数；镜像 A 失败与 B 失败是同一端点重用。大损失以三队共同可评分的唯一 B–C 对为原始分母，原始计数与建筑权重率分别列出。`METRIC_DENOMINATORS.csv` 保留质量分项、时间、几何及结构的真实可用数量。

## 4. 输入及冻结合同

相对于仓库根目录，主要输入为：

- `research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz`。
- 同包 `composition/PANELS.csv`。
- `research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange/ALL_USED_ENDPOINT_SCALARS.csv.gz` 及配对 geometry。
- `research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz`。
- 旧 joint `evaluate_joint.complete_event` 与 `personnel_global_composition_20261021/continuation_20261021/n20_abc/event_kernel.py`。
- 本轮中央 `native/batches` 中完成且有 `COMPLETION.json` 的标量／geometry 批次。

参考绑定、预处理、环序、评分资格、B8L2 主评分、D10 敏感性和融合规则不变。登记输入 SHA、种子在两份冻结 JSON；实际端点来源 SHA 在 `ENDPOINT_SOURCE_REFERENCES.csv`。底层始终为真实数据 v2。

## 5. 复现与恢复

从仓库根目录运行，Python 依赖沿用仓库已有研究环境。以下阶段独立保存结果；已有结果交付完整时只需重新聚合，不应重算全部融合。

```bash
python research/workers/personnel_exchange_closure_20261022/semi/register_semi_closure.py
python research/workers/personnel_exchange_closure_20261022/semi/register_configuration_completion.py
python research/workers/personnel_exchange_closure_20261022/semi/describe_inputs.py
```

以上重新产生冻结范围的精确成员和去重请求。中央端点执行由本轮根目录 `run_native_closure.py` 负责，加载已有缓存后仅补请求键；本次已完成的端点无需重算。69 格已登记的成员范围与全部 70 亿理论有向 ABC 是不同范围，复现本轮不应展开未登记空间。

```bash
python research/workers/personnel_exchange_closure_20261022/semi/evaluate_semi_closure.py
python research/workers/personnel_exchange_closure_20261022/semi/summarize_semi_closure.py
python research/workers/personnel_exchange_closure_20261022/semi/analyze_nested_n.py
python research/workers/personnel_exchange_closure_20261022/semi/finalize_semi_deliverables.py
```

`evaluate_semi_closure.py` 不调用融合或评分，只读已算端点并使用冻结事件几何内核。每个池完整后立即写入 `completed_pools/`，再合并完整文件。恢复时复用有 JSON 回执的完整池；缺端点的池留在 `POOL_COMPLETION_LEDGER.csv`。合并文件使用临时文件后原子替换，历史中断遗留 `.tmp` 不作为正式交付。

机制案例如需重导出，运行 `export_semi_cases.py`。它仅重放少量融合内部状态、核对既有 geometry digest，不重新评分或改变端点；完整 `CASE_EXPORT_RECEIPT.json` 记录状态重放数与零评分。保存的 case JSON 可直接复用，不必重复重放。

发布包保留完整合并事件、必要标签／团队／请求、关键小表及代码；如已保留完整合并文件，`completed_pools/` 只用于恢复，不需要重复打包所有分池大表。端点和原图在本轮统一包共享，Semi 目录不复制一遍全量旧缓存或原图全集。
