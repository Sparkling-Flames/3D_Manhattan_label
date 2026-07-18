# Paper A 正式分析数据流

> 更新：2026-07-18
> 真源：Paper A vFinal、正式 protocol/SOP/SAP 与字段合同。
> `export_label/`、`import_json/`、`active_logs/` 是输入真源；`analysis_results/` 仅存派生和审计。

## 1. 不变的 C1 原始层

已经开始的 C1 不返工：

```text
Label Studio assignment/import
Label Studio raw export
active_time raw logs
```

不要求标注员补填 failure、incident、GT、LOO、risk 或 routing 字段。所有新字段由后处理生成。

## 2. C1 派生链

```text
raw export
+ assignment manifest
+ active logs
-> selected annotation registry
-> c1_canonical_annotations.csv

canonical roster
+ sparse incident_registry.csv
+ structural/policy adjudication
+ frozen failure rule manifest
-> complete failure_disposition.csv

canonical annotations
+ complete disposition
+ external GT/reference registry
-> Q_u_GT_raw / Q_u_GT_task_adjusted / CI / LCB

canonical geometry
+ worker-excluded LOO reference
-> R_u_LOO / compatibility / stability audit

canonical submissions
+ complete disposition
-> F_u_struct numerator / structural-evaluable denominator
```

三条测量链不得互相代填：

- GT 缺失不能用 LOO 代替。
- LOO support 不足不能写作 GT failure。
- external/policy/not-evaluable 不能写作 worker structural failure。
- missing disposition 不能默认为正常。

## 3. P1、C1 与 C2

```text
P1 candidate components
-> C1 predictive validation
-> C1 variance/graph/power simulation
-> freeze C2-B design
-> C2-B common anchor + diverse bridge
-> C2-B confirmation + hierarchical shrinkage B_u
-> C2-B submissions -> post-C2-B worker profile -> profile manifest -> C2-B closeout SHA
-> C2-A-RP precision-adaptive completion
-> C2 final worker/policy freeze
```

C1 simulation 决定：

```text
n_common_anchor
n_diverse_bridge
n_unique_tasks
per-task support
worker-task graph connectivity
expected Q/B interval width
budget
```

C2-A-RP 只缩窄已定义 component 的不确定性；不搜索新风险或新 P1 family。

最终 worker state：

```text
Q_u_GT_task_adjusted
R_u_LOO_compatible
F_u_struct
B_u_risk_shrunk
P1 supported components
d_cal_F
```

`d_cal_A` 只用于 C1 后设计 C2；`d_cal_F` 只用于 C2 后的 V1 eligibility/fallback。

## 4. T1 流

```text
frozen T1 pair manifest
-> Manual/Semi × ordinary/stress_assist execution
-> canonical row outcomes
-> row_failure_attribution
-> pair_analysis_disposition
-> original/rerun pair resolver
-> final analysis pair
-> RQ1 paired analysis
```

每个 `pair_run_id` 必须恰好一条 Manual、一条 Semi。external 影响一行时，另一行仍可为 `none`；pair 整体最多重跑一次。不能合法完整重跑则整对行政删失；关系或证据失败则 `not_evaluable`。

主输出：

```text
structurally_valid
delivery_adjusted_quality
valid_only_GT_quality
owner_valid_active_time
mode_x_risk_assist
blind_trust / correction failure / over-correction
```

## 5. V1 政策执行流

```text
C2 frozen worker profile
+ frozen task pre-annotation features
+ availability snapshot
+ shared worker roster
-> block randomization: Strong Global vs Full-Integrated
-> independent symmetric capacity ledgers
-> recommendation
-> offer / accept / timeout / replacement
-> dynamic redundancy
-> GT-blind aggregation
-> resolved | unresolved | severe_failure
-> original/rerun ITT resolver
-> RQ3 analysis
```

Strong Global：

```text
S_u_G = LCB(Q_u_GT_task_adjusted)
```

Full：

```text
S_u,t_F = S_u_G
          + risk_route * lambda_B * B_u_risk_shrunk
          + activated_supported_P1_component
```

两臂共享候选池、availability、quota 规则、offer/timeout、replacement、动态冗余和 GT-blind aggregation；唯一实验差异是推荐排序。Full 的整体 fallback 必须精确回到 Strong Global。

旧 Random/Global/Full offline replay 仅为 `legacy_diagnostic`，不能替代上述前瞻 V1。

## 6. V1 failure 与 rerun

```text
worker-caused invalid submission
-> worker event
-> 按两臂相同 replacement rule 继续
-> 若最终 resolved，不把任务最终质量强制置 0

policy-caused failure
-> 保留原随机化臂 ITT
-> policy failure
-> 无交付时 delivery-adjusted quality = 0

verified external incident
-> 同臂、同 freeze version、对称预留容量下最多重跑一次
-> resolver 以合法 rerun outcome 替代 original
-> 仍归 original randomized arm

external 无法合法重跑
-> administrative censor
```

必须关系验证：

```text
original_task_id
rerun_task_id
policy_arm
freeze_version
rerun_sequence
reservation_id
reservation_arm
reservation_capacity_before
reservation_capacity_after
```

`external_system_failure_pending_disposition` 只是运行中状态，不得进入最终政策终态。

## 7. 输出与审计

每次 formal materialization 保存：

```text
schema/rule/freeze version
input path + SHA-256
reference registry SHA-256
incident registry SHA-256
failure rule manifest SHA-256
code commit
random seed
dependency bundle
formal readiness
downgrade / warning / not-evaluable counts
```

最终分析同时报告：

- C1/C2 三轴、support、C2-B 图结构和 C2-A-RP stop；
- P1 跨阶段 validation/confirmation；
- Strong Global/Full activation、fallback 和政策差异；
- T1 original/rerun/censor/not-evaluable/final pair；
- V1 两臂 ITT、终态、质量、容量、流程和 rerun；
- external incident 的条件/臂分布；
- V1 50:50 design estimand 与独立生产分布标准化 estimand。

任何 schema drift、missing required field、active-time source mismatch、SHA 失配、跨臂/跨版本 rerun 或 capacity 透支均 fail closed，不得静默删行。

## 8. 兼容说明

旧 `quality_report_*.csv`、`reliability_report_*.csv`、`r_u_calib`、`T_u/U_u` 可继续作为兼容/诊断字段读取；正式解释分别映射到 task-level quality、LOO compatibility 和 raw diagnostic risk。旧 notebook 中“按 r_u 重分配并与随机比较”的示例不是当前 RQ3 正式数据流。
