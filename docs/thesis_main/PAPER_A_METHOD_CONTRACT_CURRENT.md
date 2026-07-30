<!-- PAPER_A_MACHINE_STATUS: generated -->
# Paper A 当前方法合同（自动生成）

> 本文档只由 `PAPER_A_METHOD_CONTRACT_CURRENT.json` 渲染；不得手工定义规范性字段。

- 合同版本：`paper_a_method_20260730_v6`
- JSON SHA-256：`4682e3b4401952837abdd53928c267dab372dc74e17a87a545cfd942892595e8`
- 正式启动默认值：`false`

## 画像、质量与同行

- 正式三轴唯一为 `Q_GT`、`R_peer`、`F_struct`；`R_LOO_medoid` 与 `R_LOO_strict` 仅为独立 sensitivity/tie-break 状态。
- C1-only Q_GT：`Q_GT=worker_fixed_effect+task_fixed_effect+error`；C1+C2 final：`Q_GT=worker_fixed_effect+stage_fixed_effect+building_random_intercept+task_within_building_random_intercept+error`。没有冻结的跨阶段 anchor 或等价支持结构时，stage effect 为 `not_identifiable`。
- `R_peer_task` 是 worker-task 内 pairwise similarity 中位数；`R_peer_all` 是其 task-equal 中位数；`R_peer_stable` 排除 supported-multimodal task。
- R_peer 的 support 状态：`<= 2` 为 `insufficient_support`，`3-4` 为 `weak_descriptive`，`>= 5` 才为 `estimated`。C2-B 需要 `estimated`。
- 历史同行字段不构成规范字段，也不能被正式生产者或消费者读取。

## 行级 eligibility

所有 primary estimand 先通过 `formal_assignment_eligible`；outside 永不进入 primary estimand。规范字段为：

| 用途 | 唯一字段 |
|---|---|
| GT quality | `gt_primary_analysis_eligible` |
| peer | `peer_analysis_eligible` |
| LOO medoid / strict | `loo_medoid_analysis_eligible` / `strict_loo_analysis_eligible` |
| structural / time | `structural_opportunity_eligible` / `time_analysis_eligible` |
| Semi correction / predictive / routing feature | `semi_correction_analysis_eligible` |

## Global、Full 与 C2-B

- C2-B roster 只消费 `worker_profile_v2.c2_risk_model_eligible`，并要求 Q_GT、R_peer、F_struct 三轴；LOO 和 timing 不是 roster 硬门。
- Strong Global 的静态顺序是 `S_G -> R_peer_stable -> R_LOO_medoid -> frozen_random`。peer 或 LOO 仅在当前并列组全部可评价时使用，否则整层跳过；availability/capacity 只属于运行时 scheduler。
- Full 中 unsupported、family ambiguity 或 conditional support 不足只使相应局部 component 为零；超出 calibration support、profile version conflict 或 endpoint instability 才整体回退 Strong Global。

## rolling、reference、T1 与 V1

- rolling registry：`calibration_enrollment_registry.csv`；主画像为 pooled，必须同时提供 original-only sensitivity。amendment 时只可见 C1 部分执行和 W014/W034 运营状态，不能读取 final profile、C2、T1/V1 outcome、quality、peer、rank、activation 或 policy divergence。
- reference registry 必须在 formal C1 Q_GT 前冻结；任何 submission 不能用其触发的 reference revision 为自身计分；Stage 3 前再冻结 final reference registry。
- T1：一个预冻结 pair 在唯一合法 rerun 后仍不可评价，则整个 image 从主要 paired estimand 行政删失；可用 pair 只作 sensitivity。
- V1：在线引擎只消费当前可见状态并追加 ledger；batch 模块只做 replay/audit。它只消费 `policy_candidate_v2.global_rank_S_G`，并校验 method contract、policy manifest、candidate roster SHA 和 profile version。层级是 severe failure、unresolved+severe、delivery-adjusted quality superiority、count/cost。
