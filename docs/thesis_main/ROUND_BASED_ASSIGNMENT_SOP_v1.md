<!-- PAPER_A_METHOD_CONTRACT_CURRENT.json paper_a_method_20260730_v5 SHA-256 bde2e7e20cb00fa4f67b377112fe6534e27e7938c34fb4f63b7987fd3c142e2b -->
# Round-Based Assignment SOP v1

> 本 SOP 只消费 `PAPER_A_METHOD_CONTRACT_CURRENT.json`（版本 `paper_a_method_20260730_v5`；SHA-256 `bde2e7e20cb00fa4f67b377112fe6534e27e7938c34fb4f63b7987fd3c142e2b`）。旧 Global、C2、LOO 或 rolling 语义均为 superseded。

## 0. 适用范围

本文把 `ROUND_BASED_EXECUTION_PROTOCOL_v1.md` 转成可执行的分发、冻结和落盘步骤。阶段边界固定为：

```text
Pilot -> P1 -> C1 -> C2-B -> C2-A-RP -> T1 -> V1
```

所有阶段遵守 Label Studio CE-only 运营约束。planned assignment 以 `import_json/` 为真源，raw submission 以 `export_label/` 为真源，active-time 以 `active_logs/` 为真源，`analysis_results/` 只存派生与审计结果。

C1 已开始且不返工：不得重建既有 C1 project、改变 assignment 或要求工人补字段。后续只从既有 raw export 重跑 canonicalization 和派生链。

## 1. 通用执行规则

### 1.1 每轮开始前

必须冻结并保存：

```text
round_id
assignment_manifest
eligible_worker_roster
task_roster
seed
code_commit
rule_manifest
input SHA
```

涉及事故、重跑和删失时还必须加载冻结的 incident/failure rule manifest，不得在结果可见后修改。

### 1.2 完整 failure disposition

先生成 canonical annotation roster，再与 sparse incident registry、structural validator 和 adjudication 拼接，输出每条 annotation 一行的完整 disposition：

```text
annotation_id
row_failure_attribution
structurally_valid
incident_id
failure_reason
evidence_status
```

正常记录显式写 `none`；异常不能静默丢弃。external 只有在以下验证全部通过时成立：

- incident registry 中存在；
- evidence file SHA 匹配；
- project/task 位于影响范围；
- annotation 时间位于 `occurred_at` 至 `recovered_at`；
- `recorded_at` 早于 outcome review；
- `recorded_before_outcome_review=true`。

否则写 `not_evaluable`。

## 2. P1 — PreScreen

### 输入

Pilot 冻结任务、GT/reference、CE-only user/project、planned assignment 和 owner-valid active-time 配置。

### 分发

- 只向预注册工人分发；
- worker 不得接触 GT、他人结果或正式路由画像；
- 保存 task-worker 映射、模式、顺序、seed 和暴露证据。

### Closeout

落盘 admission、pass-count contingency、process integrity、failure-family evidence、P1→C1/C2-B/T1 预测候选和 freeze manifest。

P1 component 此时只能标为 candidate，不能进入 Full。

## 3. C1 — Calibration 主校准轮

### 输入与不返工规则

继续使用已经冻结的 C1 import、assignment、Label Studio 项目和 raw export。禁止重新分配已经完成或正在执行的 C1 标注。

### 派生处理顺序

```text
raw export
-> canonical annotation roster
-> complete failure disposition
-> task-adjusted GT quality
-> Geometry LOO audit
-> worker structural profile
-> predictive validation
-> C2 design simulation
```

每一步保存输入/输出 SHA、代码 commit、rule manifest 和 schema validation。

### Closeout

必须落盘：

- `Q_u_GT_raw`、`Q_u_GT_task_adjusted`、CI/LCB 和 support；
- `R_u_peer`、peer support/status；另列 LOO medoid/strict state 与可用时的 tie-break evidence；
- `F_u_struct` 及可评价机会数；
- P1 predictive validation；
- `risk_assist`、`risk_route` 候选；
- worker/task/building 方差；
- C2-B 候选设计、功效与预算模拟。

## 4. C2-B — Common anchor + diverse bridge

### 4.1 设计冻结

从 C1 simulation 选择一个设计，明确：

```text
per_worker_count
common_anchor_count
diverse_bridge_count
unique_task_count
support_per_task
worker_task_graph_rule
ordinary_stress_balance
```

不得机械使用旧 reserve 配额。common anchor 由所有目标工人共同完成；diverse bridge 使用冻结的平衡不完全区组分发。

### 4.2 分发检查

- 每个 worker 满足冻结的 ordinary/stress 配比；
- common anchor 覆盖完整；
- bridge 提升 unique task 覆盖且满足图连通规则；
- 不依据工人当前结果有利与否更换任务；
- 保存 planned split、实际领取、完成和偏差原因。

### 4.3 Closeout

更新 task-adjusted GT quality、LOO/structural 审计、层级收缩风险韧性、P1 component confirmation、`risk_route` confirmation 和 `d_cal^F` support。

## 5. C2-A-RP — Precision-adaptive completion

### 5.1 触发

只在冻结规则判定区间过宽且少量任务可能改变 routing eligibility 时触发。process/independence blocker 存在时不得通过补题“修复”。

### 5.2 分发

每个 block 固定为：

```text
1 ordinary + 1 stress
```

每人 0–3 个 block，具体上限使用 C1 后冻结值。每次追加只依据预期区间缩窄量，不依据 component 方向或对 Full 是否有利。

### 5.3 停止

- 达到精度目标：停止并冻结；
- 达到上限仍不稳定：该 component 设为 unsupported，调整量为 0；
- 不允许搜索新风险或新 P1 family。

## 6. Main freeze

T1/V1 import 前必须生成一个版本一致的 freeze bundle：

```text
reference registry
worker_state_version
Strong Global policy
Full-Integrated policy
risk_assist / risk_route
support / activation / fallback
T1 allocation and pair contract
V1 block randomization
availability / quota / capacity ledger
offer / timeout / replacement
dynamic redundancy
GT-blind aggregation
terminal states
incident / rerun / censor rules
analysis plan
code and input SHA
```

运行政策差异可行性 gate。若 activation、首选差异或容量后差异未达到冻结阈值，停止 V1 创建并落盘“政策不可区分”审计；不得为了启动试验事后调 Full。

## 7. T1 — Main-Test

### 7.1 分发

按 `Manual/Semi × ordinary/stress_assist` 执行。

每图建立四个 slot：

```text
Manual pair A
Semi   pair A
Manual pair B
Semi   pair B
```

因此每图为 `2 Manual + 2 Semi`，但每个 `pair_id` 必须恰好包含一条 Manual 和一条 Semi。分配必须满足：

- 同一工人不看同图两种模式；
- worker 内 Manual/Semi 与 ordinary/stress 尽量平衡；
- workload cap；
- 保存 candidate set、seed、assignment probability 和 freeze version。

### 7.2 运行中异常

行级只记录该 submission 的 `row_failure_attribution`。一行 external 不得把同 pair 的另一行改标 external。

pair-level disposition：

1. external 证据验证通过后，将完整 pair 标为 pending；
2. 在原条件、原 freeze version 和 worker-image 隔离下最多完整重跑一次；
3. 重跑 pair 仍须恰好一 Manual、一 Semi；
4. 成功时 resolver 用重跑 pair 替代 original pair；
5. 不能完整重跑时整对行政删失；
6. 证据或关系不合法时整对 `not_evaluable`。

### 7.3 Closeout

保存 original/rerun pair、行级归因、pair disposition、行政删失原因、owner-valid active-time 和最终 analysis pair。T1 outcome 不得修改任何 Calibration/V1 freeze。

## 8. V1 — Main-Validation

### 8.1 Block 创建

每个 block 在随机化前冻结同一个：

```text
availability_snapshot_id
candidate_roster
worker_total_capacity
global_quota_per_worker
full_quota_per_worker
offer_timeout
completion_timeout
max_offer_attempts
replacement_rule
dynamic_redundancy_rule
freeze_version
```

按冻结 seed 将 task/block 分配到 Strong Global 或 Full-Integrated。共享候选池但建立两套独立账本，禁止跨臂借容量。

### 8.2 推荐与 offer

两臂只允许推荐排序不同。执行顺序统一为：

```text
recommend
-> offer
-> accept/decline/timeout
-> complete/incomplete
-> validate
-> replace or aggregate
```

每次事件保存 candidate set、推荐 rank、offered/accepted/completed worker、offer sequence、replacement reason、capacity before/after 和 candidate exhaustion。

### 8.3 动态冗余与 GT-blind 聚合

初始 `k`、追加条件、standard/exceptional cap 使用同一个冻结规则。聚合不得读取 GT，只能读取合法提交、冻结几何相似度、结构有效性、largest/second cluster、medoid margin 和多峰状态。

- 稳定单一输出：`resolved`；
- 有合法提交但到上限仍多峰/不稳定：`unresolved`；
- 到上限仍无可交付合法输出：`severe_failure`。

### 8.4 External rerun

`external_system_failure_pending_disposition` 只是运行中状态。合法重跑必须：

- original task 存在；
- rerun 与 original 同 policy arm、同 freeze version；
- `rerun_sequence=1` 且每个 original 最多一次；
- reservation arm 与 policy arm 相同；
- reservation ID 唯一且容量变化合法；
- 使用预先对称预留容量。

成功后 resolver 用 rerun outcome 替代 original，同时保持 original randomization arm 的 ITT。不能合规重跑则行政删失；不得跨臂、跨版本或二次重跑。

### 8.5 Closeout

落盘 recommendation/offer/completion 全事件、独立容量账本、worker/policy failure、original/rerun chain、最终任务终态、GT-blind 输出和 analysis-ready ITT 表。

## 9. 偏差与审计

任何 schema drift、missing field、active-time source mismatch、capacity 透支、跨版本 rerun 或缺失 manifest SHA 必须 fail closed，不得静默忽略。

每轮 closeout 保存：

```text
执行命令
测试摘要
code commit
输入/输出 SHA
冻结规则版本
计划与实际偏差
处置人和时间
```

Main 开始后的任何修改只能作为不改变主要合同的勘误或在 outcome 不可见时登记的 amendment；不得回流 P1/C1/C2。

## 追加：C1 assignment provenance 与 rolling enrollment

C1 roster 的正式 assignment provenance 固定为 `original_assignment`、`authorized_replacement_assignment`、`late_entry_calibration_assignment`、`outside_assignment_submission`。授权 replacement 必须绑定 original manifest/row、授权记录、分发证据和 SHA；outside submission 只进入 raw/exposure ledger，不能因 generic authorized exception 进入 GT、peer、LOO、structural 或 time。W014 不生成 replacement；W034 仅接收 17 条 non-anchor 授权补充任务，W001 仅接收 3 条授权补充任务，W034 的 B-004/B-022 永不再次分配。

每个 task-condition 按 estimand 计算 final unique-worker support；duplicate revision 只保留冻结 canonical row。active-time 仅在 owner-valid sentinel 和日志绑定通过后标记 expected/eligible，不回填既往缺失。rolling enrollment 无论启用与否都必须冻结 `calibration_enrollment_registry.csv`；关闭时明确记录 `rolling_activated=false`、`N_late=0`，启用时登记全部 original/late-entry worker 及 terminal status。assignment manifest 只证明任务来源，禁止用它推断 enrollment batch。Stage 3 roster freeze 后停止一切招募与 assignment 变更。

## v5 方法合同执行约束

`policy_candidate_v2.global_rank_S_G` 是 V1 唯一可消费的静态 Global 名次。启动前必须同时 SHA 绑定方法合同、Strong Global policy manifest、candidate roster 与 profile version；online engine 只读取当时可见状态并 append-only 写 ledger，batch 模块只做 replay/audit。容量和 availability 只能改变 scheduler offer，不能改写该静态 rank。
