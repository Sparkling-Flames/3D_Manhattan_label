# v2.1 已保存依赖清点

只读抽查，路径相对仓库根；逐项文件存在性、列名与一行样例见 [INVENTORY.json](INVENTORY.json)。不是完整团队接合验收，也没有重算融合或评分。自然新增208不在本清点内。

## 自然旧48

候选可复用；旧24与新增24需分别接 team_key；全部连接与状态未逐行核验。旧标量3个part为单一gzip的二进制顺序拼接；新增24每个part为独立gzip，按清单遍历，不可当单个文件解压。

- 存在 `research/workers/personnel_population_curves_v2_20261023/design/EXACT_ORDER_DESIGN.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/PREFIX_TEAM_LINKS.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/ENDPOINT_SCALARS.csv.gz.part001`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/ENDPOINT_SCALARS.csv.gz.part002`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/ENDPOINT_SCALARS.csv.gz.part003`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/ENDPOINT_GEOMETRY.json.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/design/NEW_PREFIX_TEAM_LINKS.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/new_endpoints/table_shards/NEW_ENDPOINT_SCALARS/part_001.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/new_endpoints/table_shards/NEW_ENDPOINT_GEOMETRY_COMPACT/part_001.jsonl.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_geometry/geometry_sampling_precision.py`

## 精确有限边际

候选复用旧及新增端点几何；exact设计与标量按team_key接合，保留exact_kind和marginal_weight；未逐队验证映射，缺失几何/失败不可填零。

- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/new_endpoints/EXACT_MARGINAL_VALUES.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/new_endpoints/GEOMETRY_SHARD_INDEX.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/new_endpoints/TABLE_SHARD_MANIFEST.json`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025/analysis_geometry/exact_geometry_margins.py`

## 完整配比

成员与标量存在；清单所指source_recovery批次路径实际缺失，不能声称已可直接重评分，需找到原包或其它等价几何并逐team_key核对。

- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/build_configuration_distributions.py`
- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/PANELS_USED.csv`
- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/PANEL_TEAMS.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/TEAM_MEMBERS.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/ENDPOINT_OUTCOMES_manual.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/ENDPOINT_OUTCOMES_semi.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/configurations/ENDPOINT_SOURCE_MANIFEST_manual.csv`
- 存在 `research/workers/personnel_mixture_comparison_20261022/SOURCE_RECOVERY_INDEX.json`
- 存在 `research/workers/personnel_useful_taxonomy_v3_20261021/composition/multin_design.py`

## 严格ABC

候选可复用交付几何 geometry_json.points；事件A/B/C端点与成员按实际键连接，需逐键核验覆盖及状态，不能假设所有历史事件都在交付集。

- 存在 `research/workers/personnel_exchange_closure_20261022/manual_joint/EVENTS_REGISTERED.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/structure/ALL_EVENTS_REGISTERED.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/semi/EVENTS_REGISTERED_ALL.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/mechanisms/EXACT_MEMBERS.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/exchanges/manual_structure/EXACT_EVENT_LINKS.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/exchanges/manual_structure/EVENT_OUTCOMES.csv.gz`

## 50%替换

事件和成员关联存在；旧端点的全部几何尚未找到，不应将严格ABC交付几何当成已覆盖历史50%；按来源清单恢复后逐键验。part01/02为gzip字节顺序拼接。

- 存在 `research/workers/personnel_mixture_comparison_20261022/exchanges/legacy_n20/EXACT_EVENT_LINKS.csv.gz`
- 存在 `research/workers/personnel_mixture_comparison_20261022/exchanges/legacy_n20/EVENT_OUTCOMES.csv.gz.part01`
- 存在 `research/workers/personnel_mixture_comparison_20261022/exchanges/legacy_n20/EVENT_OUTCOMES.csv.gz.part02`
- 存在 `research/workers/personnel_mixture_comparison_20261022/exchanges/legacy_n20/SOURCE_SHARDS.csv`
- 存在 `research/workers/personnel_mixture_comparison_20261022/SOURCE_RECOVERY_INDEX.json`
- 存在 `research/workers/personnel_mixture_comparison_20261022/restore_large_tables.py`

## 规模与背景

有几何候选及实际请求；各背景/规模事件需逐键接合核实范围，先按reference_id定位受影响端点。

- 存在 `research/workers/personnel_exchange_closure_20261022/structure/BACKGROUND_PANELS.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/structure/M_PATH_EVENTS_REGISTERED.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/structure/M_PATH_NEW_ENDPOINT_REQUESTS.csv.gz`
- 存在 `research/workers/personnel_exchange_closure_20261022/delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz`
- 存在 `research/workers/personnel_exchange_adoption_followup_20261022/structure_followup/background_gradient/ENDPOINT_GEOMETRY.csv.gz`

## 历史策略进入

路径/事件与旧几何存在；按pool_id/path_id/k接team_key，保留顺序频率；old16和new16事件各一次，pooled32是并集，不是第三批；新增策略是否全有几何须逐键核验。

- 存在 `research/workers/personnel_population_curves_v2_20261023/design/EXACT_ORDER_DESIGN.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/PREFIX_TEAM_LINKS.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/results/ENDPOINT_GEOMETRY.json.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/analysis_policy26/results/EXACT_PAIRED_EVENTS.csv.gz`
- 存在 `research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/design26/NEW_EXACT_ORDER_DESIGN.csv.gz`

## 同房跨视角

候选复用；locator geometry_shard相对native_endpoints，geometry_line_1based从1计数；跨视角成员保持同一member_set_key。仅抽查路径，未全量验覆盖。

- 存在 `research/same_room/same_room_large_block_rebuilt_20261023/native_endpoints/ENDPOINT_SCALARS.csv.gz`
- 存在 `research/same_room/same_room_large_block_rebuilt_20261023/native_endpoints/ENDPOINT_ARCHIVE_LOCATOR.csv.gz`
- 存在 `research/same_room/same_room_large_block_rebuilt_20261023/native_endpoints/GEOMETRY_SHARD_INDEX.csv.gz`
- 存在 `research/same_room/same_room_current_classes_v2_20261023/design/PANEL_TEAM_LINKS.csv.gz`
- 存在 `research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py`

## 同用途不同房间

原答object_id可与v2.1质量库存接合，重建预测需保留建筑留出与原支持。此处原答几何不是融合端点；输入模型与预测须按受影响情况重算。

- 存在 `research/statistics/room_type_similarity_20261027/code/build_inputs.py`
- 存在 `research/statistics/room_type_similarity_20261027/code/image_similarity.py`
- 存在 `research/statistics/room_type_similarity_20261027/code/personal_protected_purpose.py`
- 存在 `research/statistics/room_type_similarity_20261027/inputs/annotations.csv.gz`
- 存在 `research/statistics/room_type_similarity_20261027/inputs/annotation_geometry.jsonl.gz`
- 存在 `research/statistics/room_type_similarity_20261027/inputs/images.csv`

## DSTRUCT及历史Q输入

DSTRUCT只用Manual原答结构和困难响应，不直接输入Q；当前冻结脚本build_records实际要求RAW_POOL_MEMBER_FEATURES、IMAGE_DIFFICULTY_OPPORTUNITIES、INPUT_SNAPSHOT；历史联合Q/T另见discover_joint_qt，训练字段及源表仍需逐层追踪。

- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/classifications/code/build_condition_response_classes.py`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/01/features/RAW_CONDITION_RESPONSE_RECORDS.csv.gz`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/01/features/HISTORY_FEATURES_ALL_LOBO.csv.gz`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/01/classifications/NEW_METHOD_LABELS_ALL_LOBO.csv.gz`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/classifications/code/build_scope_increment.py`
- 存在 `research/workers/personnel_v3_20261021/repro/personnel_useful_taxonomy_v3_20261021/taxonomy/discover_joint_qt.py`
- 存在 `research/workers/personnel_v3_20261021/repro/personnel_useful_taxonomy_v3_20261021/taxonomy/discover_behavior_classes.py`

## RFUSE

实际拟合输入为NATURAL_TRAINING_ENDPOINTS及roster参数，包含真实成员、端点、path_occurrences；GEOM不使用Q域，GEOMQ使用；建筑外留出；重分后不得静默更改模型身份。

- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/code/prepare_natural_training.py`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/code/learn_natural_fusion_roles.py`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/inputs/NATURAL_TRAINING_ENDPOINTS.csv.gz`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/inputs/NATURAL_TRAINING_PATH_TEAM_LINKS.csv.gz`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/inputs/TRAINING_TEAM_MEMBER_LINKS.csv.gz`
- 存在 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/inputs/WORKER_TRAINING_SUPPORT_ALL.csv`

## 具体复核与注意事项

- 完整配比 Manual 端点来源清单登记 12 个几何批次，相对清单定位后本地存在 0 个；源包记录不等于已恢复。
- 同房随机抽查首条定位：分片存在 True，团队键一致 True，几何坐标存在 False。
- 旧人口 JSON 几何曾实际解析 318,616 项；示例含 team_key、pool_id、geometry.points。历史附件回执本身显示个别池 geometry_rows 少于 total，不能保证所有旧端点有几何。
- 参考版本和图像/条件/成员键都要核对；Q不可用、实际融合失败与延缓必须分别保留。参考依赖的诊断和分类也可能受影响，不能只替换 B8L2。
- 未逐项读取全部分片至 EOF、未逐键全覆盖接合、未审计几何有效性、未实施重新训练；详见 JSON 的存在性与样例。

## 训练实际输入补充

- DSTRUCT 的 `build_condition_response_classes.py --inputs` 实际输入为 `research/workers/personnel_population_curves_v2_20261023/inputs/RAW_POOL_MEMBER_FEATURES.csv.gz`、`IMAGE_DIFFICULTY_OPPORTUNITIES.csv`、`INPUT_SNAPSHOT.json.gz`；均存在。历史Q联合类 `discover_joint_qt.py` 调用 `discover_behavior_classes.py` 的 `load()`，从 `research/workers/personnel_marking_patterns_20261020/record_expression.csv` 和 `research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz` 按 object_id 接合，应用原资格并计算同图同条件同参考同层 Q 残差；两文件存在。各建筑留出训练，保持历史身份。
- RFUSE 的 `learn_natural_fusion_roles.py --inputs` 是 `analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03/reverse/inputs/NATURAL_TRAINING_ENDPOINTS.csv.gz`，`--roster` 由调用者提供；成员、路径频率与支持表同目录，准确 roster 实参尚未独立定位。
- 同房首个样例虽然定位及团队键吻合，但该行 geometry.points 为空；需逐行区分原状态及可评几何，不把首行等同全部分片有效。

## 2026-10-28 几何来源追索

- 完整配比 Manual 的 213442 个成员团队键与旧人口端点几何全量按键比较：匹配 4 队，其中 4 队保存坐标，涉及 4 池。成员来自配比 TEAM_MEMBERS，旧几何本身不带成员；参考兼容性仍需逐队核对。
- 完整配比与换类交付几何按 team_key 比较：匹配 0 行，其中 0 行有坐标；成员集合一致 0 行。逐行状态及参考兼容性尚未验证。
- 对来源清单中 v3_finite 明确包名，在专题目录、相邻人员档案、analysis_results 与 Downloads 的文件名范围搜索，找到 0 个同名 ZIP；未做全盘搜索。
- 同房首行 S9hNv5qa7GM-04__manual__c93fe8a825__002231637ac5e839e1db 为 no_connection、无坐标，保留失败；同片第二行 S9hNv5qa7GM-04__manual__c93fe8a825__005d493a733f45eb462e 有 8 个点，按 locator 的 1-based 行号可读取；标量找到=True，成员一致=True。
- 示例坐标、完整成员、来源和扫描范围见 [GEOMETRY_RECOVERY.json](GEOMETRY_RECOVERY.json)。匹配不自动证明参考版本一致，也不证明缺失端点可由其他实验恢复。
- 4 个旧人口重合团队进一步读取原标量：找到 4 个，成员集合一致 4 个。JSON保存逐队成员、坐标与原参考；新参考的对应仍需验证。另在 Downloads 下两处相关已解压研究目录按原包名搜索，找到 0 个。

## 原答与参考特征实现

已追到参考机会、球面一对一角点匹配、个人几何表达和 DSTRUCT 训练输入的上游函数及门槛，见 [FEATURE_SOURCES.md](FEATURE_SOURCES.md)。仅静态追踪，未重算或验证新旧输出等价。
