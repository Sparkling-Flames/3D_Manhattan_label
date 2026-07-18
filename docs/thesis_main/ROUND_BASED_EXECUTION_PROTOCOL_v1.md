# Round-Based Execution Protocol v1

## 0. 定位与效力

本文是论文主线 `Pilot -> PreScreen -> Calibration -> Main(Test + Validation)` 的正式执行协议。

正式轮次固定为：

```text
Pilot -> P1 -> C1 -> C2-B -> C2-A-RP -> T1 -> V1
```

- P1 属于 PreScreen。
- C1、C2-B、C2-A-RP 属于 Calibration。
- T1 属于 Main-Test。
- V1 属于 Main-Validation。

本文以 `Paper_A_新版完整论文提纲_vFinal_Draft.md` 的设计为准，明确替换此前的 reserve-only C2、Calibration_manual 上 Random/Global/Full 离线主比较和单臂 Full deployment V1。历史文件或代码中的旧口径不得覆盖本协议。

P1、C1 已发生的 assignment、raw submission 和 admission 不回改。尤其是 C1 不返工：后续合同变更只允许从既有原始 export 重跑派生链。

## 1. 全局硬约束

### 1.1 阶段职责

| 轮次 | 核心职责 | 允许更新 | 禁止用途 |
|---|---|---|---|
| P1 | 准入、高信息诊断、预测候选 | admission、failure-family 候选、预测特征 | 直接形成正式 routing profile |
| C1 | 基础能力、任务调整、风险发现和设计模拟 | provisional worker state、C2 设计、T1/V1 功效参数 | 最终政策或 Main 结论 |
| C2-B | common anchor 与 diverse bridge | 跨 worker 比较、风险确认、层级收缩 | 根据结果是否有利选择任务 |
| C2-A-RP | 精度自适应补齐 | 缩窄已定义 component 的不确定性 | 搜索新风险或新 failure family |
| T1 | Semi-Auto 条件效应 | RQ1 结果与机制分析 | 修改 worker state、risk 或政策 |
| V1 | Strong Global 与 Full-Integrated 前瞻政策比较 | RQ3 结果与流程审计 | 重新调权重、阈值或回流 Calibration |

Main 结果不得回流修改 admission、worker state、`risk_assist`、`risk_route`、capacity、offer/replacement、dynamic redundancy、aggregation、terminal state 或统计计划。

### 1.2 信息时序

首次 assignment/routing 只可读取：

```text
公开任务 metadata
冻结的 HoHoNet feature/output risk
冻结的 Calibration worker state
availability snapshot
对应政策臂的剩余 capacity
历史 process eligibility
```

当前任务响应到达后才可读取：

```text
合法提交
冻结几何相似度
结构有效性
Scope/冲突状态
已到达响应数
```

不得回填首次 routing：

```text
当前任务事后 Difficulty
Model Issue 票
最终 crowd consensus
GT 评价
专家裁决
T1/V1 outcome
```

### 1.3 Estimand-specific inclusion

每条 submission 分别保存：

```text
eligible_for_active_time
eligible_for_GT_quality
eligible_for_LOO
eligible_for_structural_failure
eligible_for_semi_correction
eligible_for_predictive_validity
eligible_for_routing_feature
```

不得用一个全局 `valid` 字段替代这些分析资格。

### 1.4 Failure attribution 与 analysis disposition

行级 failure attribution 固定为：

```text
none
worker_caused_structural_failure
policy_caused_failure
external_system_failure
not_evaluable
```

- worker-caused structural failure 进入对应 worker/condition 的结构机会分母。
- candidate exhaustion、替补规则失败和容量耗尽属于 policy-caused failure，归入原政策臂。
- external system failure 不归责工人或政策。
- 证据不足或无法唯一归因的异常为 `not_evaluable`。

行级归因与 T1 pair / V1 task 的分析处置必须分开保存，不得为了让整对重跑而把未受影响的行伪标为 external。

external incident 必须在结果可见前登记，并验证：

```text
incident_id
incident_type
occurred_at
recovered_at
affected_project_ids
affected_task_ids 或 affected_scope_rule
evidence_path
evidence_sha256
recorded_at
recorded_before_outcome_review
```

只有证据文件 SHA 匹配、任务在影响范围内、annotation 时间落入事故窗口且登记早于 outcome review，才可归类为 external。任一条件不满足即为 `not_evaluable`。

## 2. Round P1 — PreScreen

### 2.1 目标与输入

P1 同时承担准入、高信息诊断和跨阶段预测候选发现。输入为 Pilot 冻结的 assignment、GT/reference、Label Studio export 和 owner-valid active-time 证据。

### 2.2 允许更新

- admission 与 process-integrity 状态；
- geometry、blind trust、correction、Scope、structural 等 failure-family 候选；
- P1 到 C1、C2-B、T1 的预测假设；
- pass-count contingency。

### 2.3 禁止更新

- 不把 P1 原始表现直接当成 Strong Global 分数；
- 不把未经 C1 predictive validation 和 C2-B confirmation 的 P1 component 放进 Full；
- 不用后续 Main outcome 反向选择 P1 component。

### 2.4 必须落盘

assignment、raw/canonical submission、admission、failure-family evidence、active-time provenance、预测候选词表及 freeze manifest。

## 3. Round C1 — Calibration 主校准轮

### 3.1 不返工边界

C1 当前标注任务、assignment 与 raw export 保持原状。正式处理从 raw export 重跑：

```text
canonicalization
-> complete failure disposition
-> quality / LOO / structural profile
-> C1 design simulation
```

不得要求工人补填新的事故或分析字段。

### 3.2 目标

- 估计 GT 外部质量、任务效应和 worker/task/building 方差；
- 形成 provisional 三轴 worker state；
- 发现 `risk_assist` 与 `risk_route` 候选；
- 验证 P1 predictive component；
- 模拟 C2-B 结构及 T1/V1 功效。

### 3.3 三轴 worker state

```text
Q_u_GT_task_adjusted
R_u_LOO_compatible
F_u_struct
```

- `Q_u_GT_task_adjusted` 是任务组成校正后的外部正确性，并保存 CI/LCB 与 support。
- Geometry LOO 是同行一致性审计、metric compatibility 检查和 tie-break 证据，不替代 GT quality。
- `F_u_struct` 只使用 structural-evaluable opportunities；external、reference failure、OOS 和未知归因不得进入其分母。

### 3.4 C1 后模拟

模拟并冻结 C2-B 候选设计所需的：

```text
每人任务数
common anchor 数
diverse bridge 数
unique task 数
每图 worker support
worker-task 图连通性
层级模型区间宽度
routing activation / fallback
```

C2-B 数量不得预先机械固定为 6+6、12+12 或 reserve-only 补派。

## 4. Round C2 — Calibration 补齐与冻结

### 4.1 C2-B

C2-B 由 C1 simulation 选择并在分发前冻结：

- common anchor：所有工人共同完成少量 ordinary/stress 任务，用于横向比较和波次校正；
- diverse bridge：按平衡不完全区组覆盖更大的任务池，增加 unique task 和外推能力；
- 同时满足每图 support、worker-task 图连通性和预算约束。

C2-B 用于确认 `risk_route`、P1 component、任务调整质量和风险韧性层级状态。

### 4.2 C2-A-RP

C2-A-RP 仅对以下对象做精度补齐：

- 区间仍过宽；
- 少量任务可能改变 routing eligibility；
- 不存在 process/independence blocker。

每个补测 block 为 `1 ordinary + 1 stress`，每人最多 1–3 个 block；实际上限在 C1 simulation 后冻结。选择依据是预期降低决策不确定性，不能依据当前结果是否有利于 Full。

达到上限仍不稳定时：

```text
B_u_routing_eligible = false
B_u adjustment = 0
fallback = Strong Global
```

C2-A-RP 不搜索新风险、新 family 或新政策形式。

### 4.3 两类风险

- `risk_assist`：只服务 T1，描述模型初始化与纠正风险。
- `risk_route`：只服务 V1，描述 Manual 外部质量、LOO disagreement、结构失败或 worker ranking instability 风险。

设计 C2 使用 C1 版本 `d_cal^A`；C2 后计算并冻结 V1 使用的 `d_cal^F`，不得用 `d_cal^F` 反向解释 C2 选择。

### 4.4 Strong Global 与 Full-Integrated

Strong Global eligibility 至少要求 process/independence 合法、GT support 充分、结构失败率不过阈值且 task-adjusted GT quality LCB 达标。正式排序为：

```text
S_u^G = LCB(Q_u_GT_task_adjusted)
```

LOO、availability、capacity 和冻结随机规则只用于 tie-break 或 eligibility 审计。

Full 以 Strong Global 为基线，只增加经验证 component：

```text
S^F_u,t
= S^G_u
 risk_route 激活的收缩风险韧性项
 任务 family 激活的收缩 P1 项
```

P1 component 必须同时满足 C1 predictive validation、C2-B confirmation、support、标注前可激活和 V1 前冻结。单项 unsupported 时关闭该项；`d_cal^F` 越界、family 激活含糊、supported 工人不足、排序不稳定或 profile version 不兼容时，Full 整体退化为 Strong Global。

### 4.5 C2 冻结门

启动 Main 前必须冻结：

```text
reference registry
三轴 worker state
Strong Global / Full
risk_assist / risk_route
support 与 fallback
T1 assignment / pair / rerun
V1 capacity / offer / replacement / dynamic redundancy
GT-blind aggregation / terminal states
failure / incident / censor rules
statistical analysis
全部 manifest 和输入 SHA
```

同时完成政策差异可行性 gate，报告 activation、fallback、首选不同率、初始集合不同率、supported candidate count 和 capacity 后差异。未达到预注册可识别性条件时，V1 不启动并生成审计结论；阈值不得根据 V1 outcome 设置。

## 5. Round T1 — Main-Test

### 5.1 设计

T1 是：

```text
Manual / Semi
x
ordinary / stress_assist
```

每图分配 `2 Manual + 2 Semi`。四个 slot 在合格工人中约束随机分配，同一工人不得看到同图两种模式，并平衡 worker 的 mode、risk 与 workload。

分析单位使用预生成的 `pair_id`；每个 pair 必须恰好含一条 Manual 和一条 Semi。同一图的两条 pair 分开进入 image-level 汇总。

### 5.2 Failure disposition

worker-caused failure 保留在原条件：

```text
structurally_valid = 0
delivery_adjusted_quality = 0
```

external incident 触发的是 pair-level disposition，而不是修改另一行归因：

- 完整 Manual/Semi pair 在原条件、原 freeze version 和 worker-image 隔离下最多重跑一次；
- 合法重跑替代原 pair 进入分析，并保留 original/rerun provenance；
- 无法完整重跑则整对行政删失；
- 证据或关系验证失败则整对 `not_evaluable`。

重跑/删失决定必须在查看 T1 条件结果前冻结。

### 5.3 禁止更新

T1 不得修改 Calibration worker state、风险、政策、配额、聚合和 V1 freeze。

## 6. Round V1 — Main-Validation

### 6.1 前瞻试验

V1 在 task/block 层随机比较：

```text
Strong Global
vs
Full-Integrated
```

两臂使用共享 worker pool，但每个 block 在随机化前冻结同一个 availability snapshot、候选 roster 和对称 worker quota，并维护独立容量账本：

```text
capacity_global[u]
capacity_full[u]
```

主试验不得跨臂借用容量。

### 6.2 相同执行规则

两臂必须完全相同：

```text
offer timeout
completion timeout
maximum offer attempts
decline/no-response replacement
invalid-submission replacement
candidate-exhaustion terminal rule
dynamic redundancy
GT-blind aggregation
```

唯一允许差异是推荐排序。保存 candidate set、availability snapshot、recommendation、offer、accept、completion、replacement、capacity 和 terminal evidence 全链路。

### 6.3 GT-blind aggregation 与终态

聚合只使用截至当前的合法提交和冻结几何规则，审计 largest/second cluster、medoid margin、结构有效性与多峰状态。

最终政策终态只有：

```text
resolved
unresolved
severe_failure
```

`external_system_failure_pending_disposition` 只允许作为中间态。合法 external task 必须在原臂、原 freeze version、对称预留容量下最多重跑一次；成功重跑替代原任务 outcome 且保留原随机化臂 ITT，无法合规重跑则行政删失。不得跨臂借容量或由 V1 outcome 触发。

policy-caused failure 保留在原臂 ITT；worker invalid submission 记录为 worker event，若替补后任务 resolved，不把最终任务质量强制改为 0。

### 6.4 禁止更新

V1 不得修改 P1/C1/C2 产物、Strong Global、Full、风险、配额、重跑、聚合、终态或统计层级。事后专家审查只能解释 unresolved、GT 冲突、OOS 与反例，不能替换政策输出。

## 7. 报告分布

T1 与 V1 分别报告 ordinary/stress 分层结果。

50:50 设计平均：

```text
V_design = 0.5 * V_ordinary + 0.5 * V_stress
```

仅解释为平衡实验分布。

生产标准化使用独立自然任务池的比例：

```text
V_prod = p_ordinary * V_ordinary + p_stress * V_stress
```

若无唯一生产比例，报告预注册情景分析，不从 50:50 试验样本估计生产比例。

## 8. 协议变更

任何涉及 assignment、worker state、risk、policy、capacity、rerun、aggregation、terminal state 或统计分析的变更均须：

1. 在受影响 Main outcome 可见前登记 amendment；
2. 保存旧/新 manifest、输入 SHA、原因与批准时间；
3. 不回改 P1/C1 raw 数据；
4. 不用 T1/V1 结果选择版本。

本次 vFinal 迁移是用户明确授权的正式协议替换，不是保留旧 RQ3 口径的兼容 amendment。
