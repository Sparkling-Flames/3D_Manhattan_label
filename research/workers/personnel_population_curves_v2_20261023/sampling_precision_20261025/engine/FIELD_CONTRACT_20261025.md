# 新随机顺序与端点：研究台连接字段

本轮接口继续使用原 `pool_id`、`team_key`、`object_id`、图片和参考键。数据仍是真人 v2；新增的是模拟进入顺序和由这些原答集合计算的端点记录。

| 字段／文件 | 含义与连接方式 |
|---|---|
| `pool_id` | 冻结的图片、条件、参考绑定下的人员池。成员资格来自该池快照，不能由 Q 是否缺失倒推资格。 |
| `team_key` | `pool_id + '__' + sha256(canonical_json(sorted(member_workers)))[:20]`，标量及几何均按此唯一连接。 |
| `member_workers` / `member_object_ids` | `|` 分隔的实际人员／原答 object_id。主新标量中按排序后的人员一一对应；完整顺序另存于设计表。 |
| `path_id` / `worker_order` | 某池的一条完整进入序列。每人只出现一次，每个人数都由当前前缀的原答集合独立融合。 |
| `base_path_id` | 策略的自然顺序来源；策略和自然对照按 `pool_id, base_path_id, k` 配对。 |
| `workers` / `worker_order` / `base_worker_order` | 前两列均为该行实际执行的完整进入顺序；策略行按 target 先行稳定分割。`base_worker_order` 单独保留其配对的原自然顺序。自然行三列相同。采用本轮更正后的设计表，详见 `design/POLICY_ORDER_METADATA_CORRECTION_RECEIPT.json`。 |
| `replicate` / `new_index` | 旧自然 MC 为 replicate 0..23。本轮 replicate=24+new_index；均衡新增的 new_index 为 0..23，焦点追加为 24..71。新策略配对使用 new_index 0..7，即 replicate 24..31。 |
| `batch` | `balanced_new24`、`focus_new48`、`policy_new8`。焦点独立新 72 是前两者合并；主固定 48 为旧 24 加 balanced_new24。 |
| `k` / `pool_n` | 当前团队人数／实际人员池容量，均不同于路径条数。满员每池只有一个确定的团队端点。 |
| `sampling_weight_new_batch` | 该新增批次内部的路径权重。合并批次时重新在每池内按实际路径等权；跨图片不能因焦点池多算路径而多计权。 |
| `EXACT_MARGINAL_TEAM_DESIGN` | 按 `pool_id,k,team_key` 唯一。`marginal_weight=1/C(N,k)` 是有限总体独特队权重，不能把这些行作为额外随机路径。 |
| `endpoint_source` | 登记时的端点来源：旧人口缓存、本轮计时新队或需新执行的队。`new_native_required_20261025` 保留的是登记来源标签，**不是当前仍未计算的状态**；当前计算完成性以输出连接和 COMPILE_RECEIPT 为准。 |
| `reference_id` / `reference_version` | 原冻结参考绑定。引用旧端点时已经按实际人员、object_id、参考和输入池检查；不借本轮恢复暂停资格。 |
| `pool_input_sha256` | 冻结池的规范 JSON 哈希。完整设计依赖表和本轮原生端点均保存；部分旧标量本来没有该列，按 pool_id 回连设计依赖表即可。 |
| `B8L2` / `D10` | 正式质量主指标／敏感性指标。缺失保留为空；不把延期、失败或未计算填零。 |
| `score_status` | 本轮新主端点实际出现 complete_conditional、below_four、invalid_floor、no_connection、two_person_deferred。其他历史状态保留原值，不统并为人员错误。 |
| `score_available` | 是否有可用 B8L2；本轮新端点 B8L2 和 D10 支持一致。 |
| `policy_deferred` | n=2 的原设计暂缓。它不同于实际融合失败。 |
| `score_failure_nonpolicy` | 非 n=2 延期、但没有可评分 Q 的端点。分析失败概率应以相应路径／有限总体尝试为分母，不能直接把存储去重后的全部端点平均成一条自然曲线。 |
| `floor_evaluable` | 具有原流程认可的底面；也可能是节点不足四个的部分底面。 |
| `complete_floor_evaluable` / `complete_evaluable` | 冻结规则下的完整底面／完整可评状态。几何分析按沿用的资格选取，保留相应分母。 |
| `geometry_available` | 旧包装字段表示 candidate 字典存在，连 n=2 延期也可能为 true；它不能替代可用底面或完整几何状态。 |
| `NEW_ENDPOINT_GEOMETRY_COMPACT` | 每个主新增端点一行最终候选、节点支持、参考和状态。`geometry` 可含空的 points/footprint；须联合上述状态解释。 |
| `full_state_pointer` | 相对 `new_endpoints/` 的 gzip JSONL 路径及 `#L<一基行号>`。两条复用的计时新队指向 `../engine/benchmark/parts/`，其余指向 `parts/`。 |
| `geometry_shard` / `geometry_line_1based` | 新标量中的完整 state 分片定位，与上述 pointer 一致。全 state 位于可选 P03 包；轻量几何无需加载它。 |
| `source_time_total_seconds` / `time_source_kinds` | 原图记录活动耗时总和及来源语义。known_n<k 则总耗时缺失；来源含 `|` 时不得自动按同一种耗时解释。 |
| `native_evaluation_wall_seconds` | 计算端点的程序计时，绝不是人员标注耗时。多进程各行计时相加不等于整体经过时间。 |

`NEW_ENDPOINT_SCALARS` 为存储去重表，不是随机抽样权重表。重复命中的 team_key 在 `NEW_PREFIX_VALUES_COMPACT` 中保留每次抽取的路径乘数；使用该值表估计自然曲线和策略差异。正式完成文件包含 323,809 个主新增端点、403,376 个新前缀值以及 14,904 个精确边际值，缺端点连接为零。

完整源对象／参考点与评分输入可在 `engine/frozen_repo/.../fusion/INPUT_SNAPSHOT.json.gz` 或固定版本仓库的人口输入快照中按 pool_id、object_id 连接。原图仍引用原 Release；本轮不复制原图全集。

## 策略顺序清单的元数据更正

初次登记时策略行复制了自然行，`workers` 和 `worker_order` 未覆盖为策略次序；实际前缀却正确使用了策略顺序 `po`。因此这是一处顺序清单错误，不是执行团队错误。更正从冻结的 `NEW_PREFIX_TEAM_LINKS.csv.gz` 按 k 还原实际 entrants，并逐行验证其等于同一 base 的 target 先行稳定分割；403,376 条前缀的成员散列均匹配原 team_key。5,024 个策略行全部核对，5,022 行的顺序字段实际改变，另外 2 行原自然顺序恰好已经满足该策略。7,200 自然行所有原字段不变。

原顺序表和原登记脚本完整保存在 `design/source_original/policy_order_metadata_20261025/`，仅供追溯；正式使用 `design/NEW_EXACT_ORDER_DESIGN.csv.gz`。`engine/correct_policy_order_metadata.py` 可从原件和已执行前缀重复这项更正，不运行融合。团队请求、成员、前缀、标量、几何、Q 和抽样权重均未改变；回执保留更正前后 SHA256。
