# 既有冻结融合与人数序列核查

接入后补记：五分包现已完整验收，实际重评分见 [FUSION_RESCORE.md](FUSION_RESCORE.md)。下文59/50等覆盖数属于接包前907快照的库存核查；不是最新922包的实际重评分分母。“包缺失”仅描述核查时状态。

日期：2026-10-13。只读核查；未重跑融合、未改参数、未覆盖交付。本清单依据本地当前工件，不能替代尚缺的 calibration ZIP 核验。

## 可以立即接入的部分

当前冻结源是 `analysis_results/consensus_delivery_20261008/`，不是历史 `direct_fusion_20261007` 原型。`outputs.json` 保存177图当前全员结果；每图 `<image_code>.json` 保存 `image_id`、`gap=7.5`、`n`、`automatic`、可选 `assisted`、`applied_reviews`。当前输出的160图有连接，159图 `geometry_status=ok`，17个两人池暂缓，1图常规三维不可用。另有整池失败 rPc-22，不在177有效池中，仍保留24人及失败原因。

重评分取 `candidate.points`，严格保留 `candidate.feature_ids` 顺序。点是已处理的ERP上下点对，不能冒充原始人员输入；原始观察索引可在 `identity_groups[].members` 的 `id/worker/pair_index/source_pair_index/points` 和 `assignments` 追溯。`automatic` 与 `assisted` 分层，不把同图两版本视为独立样本。Uw-09即使几何可算也有 `incomplete_consensus_observed`，不能悄悄升级为完整布局。

现有 `research/quality_top_height_response_20261012/inputs.json` 的907份快照可以按完整 `image_id` 精确绑定已有参考：177图中59图找到唯一参考，其中50图有候选连接。13图在该旧快照中属于参考适用明确层，其中9图有连接。**这些是可接入覆盖数，绝不是融合结果已有合格评价资格的数量。** 还须核查融合表达范围、参考版本、场景及人员池资格。其余118图在该快照没有参考绑定，不按相近文件名或最高分挑参考。

`fusion_inventory.json` 提供逐图路径、参考ID、状态和自动/辅助成员record_id。质量W编号与融合P编号不可按数字相等连接；通过record_id/object_id桥接后核对身份。

## 人数曲线：真实有什么、缺什么

| 来源 | 真实保存内容 | 本轮用途 |
|---|---|---|
| 当前 `consensus_delivery_20261008` | 全员名单、身份组、节点、连接、自动/辅助终点 | 可重评分终点；没有当前方法逐k序列 |
| `worker_count_composition_20261006/per_image.csv` | Lee tile有限池解析期望；k、method、reference version、构成比例 | 历史面积方法对照；没有实际抽组名单与逐k完整三维几何 |
| `clustering_numeric_received_20260920/results/prefix_arrivals.csv.gz` | unit/pool/replicate/k/subset_mask/next_pool_index；manifest绑定对象与人员 | 真实历史聚类进入序列；不能冒充10月8日墙线融合 |
| 同目录 `prefix_nodes.csv.gz` | 标签、代表对象索引、聚类数量及覆盖诊断 | 没有当前方法的逐k完整上下点融合几何 |
| `panorama_research_received_20260921/local_recompute/results/replay_prefixes.csv.gz` | 历史聚类order_id/k/诊断指标 | 不是当前融合曲线 |
| `consensus_reviews_20261003/worker_20261003/pro/results/permutation_original.npz` | null、observed置换统计量 | 名称含permutation，但不是人员进入顺序 |

当前方法 `fuse(records, gap=7.5)` 已存在于 `tools/thesis_main/analysis/consensus_delivery_20261008.py`；SOP第9节是未运行的前缀实验设计。当前没有发现对应执行器、序列ID、固定成员进入顺序、逐k完整候选或子集人审适用政策。不能由全员终点或历史聚类序列画新方法k曲线。

如后续确需新增当前方法轨迹，应另行冻结有限小面板、排列次数/种子及名单、参考绑定和子集政策，并调用上述函数写新目录。不可调用 `run()` 覆盖当前交付；不可把全员已审身份或顺序套到仅有k人的自动实验。此举是新的执行设计，应先报告方案，本轮未启动。

## 本阶段继续项与限制

主线程可先对有明确绑定的实际冻结终点做研究重评分，自动/辅助、可算/不可算、资格明确/未审分开。缺参考和不可算项保留null及原因。新ZIP若扩大参考覆盖，另记输入版本后更新账本；不得静默替代旧快照。

核查仅为路径、JSON字段、数量和历史CSV/NPZ表头，无大规模复算或新测试。地图与入口已检查，本目录新入口由主线程统一登记，本子任务不改索引。未检查所有历史归档的每条序列，也未声称不存在任何旧轨迹；结论只限当前冻结墙线融合未见可用逐k输出。
