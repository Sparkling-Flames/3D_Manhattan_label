# Paper A 当前方法合同（自动生成）

> 本文档由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 自动生成，不得手工定义规范性方法字段。

- 合同版本：`paper_a_method_20260730_v3`
- JSON SHA-256：`fe001e51ccf02baf45cb5a2929d8d9350781d5c3fe30a821d73c44ad7d57efce`
- Formal launch 默认：`false`

## 冻结方法

- C2 候选：`D8, D10, D12`；C2-A-RP 每人最多 `4` 张。
- 基础工人轴：`Q_GT, R_peer, F_struct`；LOO 只作可用时的 tie-break/sensitivity。
- R_peer：少于 `3` 个 task 为不足，`3-4` 为描述性，至少 `5` 个 task 才是正式 estimated。
- C2-B roster 只消费 `worker_profile_v2.c2_risk_model_eligible`。
- Strong Global：`S_G=z(Q_GT_EB)`；静态顺序为 `S_G -> R_peer_stable -> available R_LOO_medoid -> frozen random`。
- 非唯一 complete-link partition 的主分析状态为 `not_evaluable`，并保存全部候选 partition。
- rolling enrollment 的主画像为 pooled，同时必须生成 original-only sensitivity。
- 本轮只允许生成 C2-B 启动包；不自动导入 Label Studio，Stage 3/T1/V1 保持关闭。

## 机器合同

- `assignment_evidence_v2`
- `peer_worker_task_v2`
- `worker_profile_v2`
- `policy_candidate_v2`
- `geometry_cluster_v2`
