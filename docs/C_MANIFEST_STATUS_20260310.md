# C 线 Manifest 状态（2026-03-10）

本文件记录当前基于 A 线 frozen registry 已补齐的 C 线本周交付物。

对应产物目录：

- `analysis_results/c_manifests_20260310/`

本次补齐的交付：

1. `trap_manifest_schema_v1.json`
2. `natural_failure_bank_index_v1.csv`
3. `embedding_ood_protocol_v1.json`
4. `trap_manifest_draft_v1.csv`

当前状态分层：

- `trap_manifest_schema_v1.json`：`frozen_rule`
- `natural_failure_bank_index_v1.csv`：`realized`
- `embedding_ood_protocol_v1.json`：`frozen_rule`
- `trap_manifest_draft_v1.csv`：`2 realized natural rows + 13 frozen_rule synthetic rows`

与 A 线的 join 方式：

1. 主 join key 为 `base_task_id`
2. 对当前 draft trap 行，同时保留 `target_registry_uid`
3. 不再只依赖人工目录名或 basename 做口头关联

边界说明：

1. 本次补的是 manifest 层，不是最终几何生成层。
2. synthetic rows 当前锁定的是 family、seed、lambda、配额与 planned target，不是最终 corners 输出。
3. `d_t` / `I_t_OOD` 当前冻结的是 procedure，不是 realized score 名单。

一句话总结：

当前 C 线已经从“说明文档层”推进到“可 join 的结构化 manifest 层”，但还没有完成最终生成与回写阶段。
