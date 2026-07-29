# Paper A 当前方法合同（自动生成）

> 本文档由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 自动生成，不得手工定义规范性方法字段。

- 合同版本：`paper_a_method_20260729_v2`
- JSON SHA-256：`d628172fc04e24793839202520dd9633116ff7012e2d593789a7c04413014a44`
- Formal launch 默认：`false`

## 冻结方法

- C2 候选：`D8, D10, D12`；C2-A-RP 每人最多 `4` 张。
- 基础工人轴：`Q_GT, R_peer, F_struct`；LOO 只作用途级 tie-break/sensitivity。
- Strong Global：`S_G=z(Q_GT_EB)`；静态顺序为 `S_G -> R_peer_stable -> R_LOO_medoid -> frozen random`。
- 非唯一 complete-link partition 的主分析状态为 `not_evaluable`。
- T1 唯一重跑后任一 pair 不可评价时整图行政删失。
- V1 在线引擎只消费当前状态；批处理仅作 deterministic replay/audit。

## Rolling amendment 信息集

- C1 已部分执行，W014/W034 运营状态已知。
- final worker profile、C2 outcome、T1/V1 outcome 尚不可见。
- assignment 不得读取 C1 quality、peer、ranking、component activation 或 policy divergence。

## 机器合同

- `assignment_evidence_v2`
- `peer_worker_task_v2`
- `worker_profile_v2`
- `policy_candidate_v2`
- `geometry_cluster_v2`
