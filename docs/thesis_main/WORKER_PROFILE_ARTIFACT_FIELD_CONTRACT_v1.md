# Worker profile 工件字段合同 v1

> 状态：Paper A vFinal 正式工件合同
> 更新：2026-07-18
> 边界：不改变已启动 C1 的 assignment、Label Studio schema 或原始 export。

## 0. 目的与命名

本合同规定 worker-task evidence、worker profile、P1 跨阶段支持和 C2 final policy profile 的字段。所有新增字段由 C1/C2 派生链生成。

正式三轴：

```text
Q_u_GT_task_adjusted  # task-adjusted external GT quality
R_u_LOO_compatible    # worker-excluded Geometry LOO compatibility
F_u_struct            # worker-caused structural failure rate
```

现有实现尚输出的 `r_u_calib`、`r_u_calib_lcb`、`r_u_calib_ci_*` 是 `R_u_LOO` 的兼容别名，不是 `Q_u_GT_task_adjusted`，不得直接作为 Strong Global 主分数。

## 1. 工件

C1 保留并扩展：

```text
worker_task_evidence_table_C1.csv
worker_profile_main_matrix_C1.csv
worker_failure_family_response_C1.csv
worker_subfamily_response_C1.csv
worker_profile_sidecar_C1.summary.json
p1_to_c1_predictive_validity.csv
p1_to_c1_predictive_validity_report.md
```

C2 正式输出：

```text
worker_task_evidence_table_C2_final.csv
worker_profile_main_matrix_C2_final.csv
worker_failure_family_response_C2_final.csv
worker_subfamily_response_C2_final.csv
p1_component_support_C2B.csv
worker_risk_resilience_C2_final.csv
worker_profile_sidecar_C2_final.summary.json
```

所有表至少携带 `schema_version`、`rule_version`、`stage`、`source_artifact`、`source_sha256`、`dependency_bundle_id`、`validity_status`、`interpretation_allowed`。

## 2. 词表

### 2.1 Stage / pool / condition

```text
stage: P1 | C1 | C2-B | C2-A-RP | T1 | V1

pool:
  PreScreen_manual | PreScreen_semi | PreScreen_oos
  Calibration_anchor | Calibration_core
  Calibration_common_anchor | Calibration_diverse_bridge
  Calibration_precision_adaptive
  Calibration_semi

condition:
  manual | semi | oos_gate | unknown
```

旧 `C2` 映射为未细分的 Calibration 历史记录；旧 `C2b_diagnostic_extension` 仅为 `legacy_diagnostic`，不得映射成正式 `C2-B`。

### 2.2 Scope / reference

```text
task_final_scope:
  in_scope | oos | unknown

geometry_reference_status:
  expert_hard_single | expert_hard_multi | consensus_reference
  soft_ambiguous | scope_ambiguous | audit_only | unavailable

worker_scope_response:
  correct_in_scope | correct_oos
  scope_false_positive | scope_false_negative
  unknown_or_missing | not_evaluable
```

`task_outcome_reference` 与 worker-specific LOO reference 是两个对象：

```text
task_outcome_reference:
  type, identity, sha256, cardinality, source, status

r_u_worker_specific_loo_reference:
  worker_id, task_id, mode, identity, sha256,
  excludes_worker, peer_support, status
```

LOO reference 必须排除被评价 worker。

### 2.3 Failure attribution

```text
none
worker_caused_structural_failure
policy_caused_failure
external_system_failure
not_evaluable
```

它与以下 diagnostic family 分离：

```text
geometry_quality_failure
scope_oos_failure
semi_correction_failure
undercoverage_failure
process_failure
```

现有 subfamily 词表继续有效，包括 geometry、scope、semi correction、undercoverage、process 和 `non_independent_submission`；`process_ok` 仅是 process-evaluable success，不是 failure taxonomy。

external 必须由完整事故注册表验证；policy/external/not-evaluable 不进入 worker capability 或 structural denominator。worker-caused structural failure 进入 `F_u_struct` 分子。

### 2.4 Support

默认支持标签继续为：

```text
insufficient: n < 3
weak:         3 <= n < 5
moderate:     5 <= n < 10
sufficient:   n >= 10
not_evaluable
```

阈值可由 outcome 前冻结 manifest 覆盖。所有结果必须同时保存原始 `n`，不得只保存标签。

## 3. Worker-task evidence

`worker_task_evidence_table_C1.csv` 行粒度为一个 worker-task evidence signal；同一 canonical annotation 可产生多个 diagnostic signal，但失败归因只有一个。

保留当前字段：

```text
worker_id
round_id
task_id
base_task_id
dataset_group
condition
stage
pool
task_final_scope
task_oos_subtype
worker_scope_response
geometry_reference_status
geometry_valid
process_invalid
quality_metric_name
quality_metric_value
family
subfamily
response_type
failure_observed
included_in_r_u_calib
included_in_r_geometry
included_in_r_scope
included_in_T_u
included_in_U_u
included_in_process_reliability
included_in_p1_predictive_capability
exclusion_reason
active_time_source
primary_active_time_eligible
assignment_expected
canonical_annotation_id
source_manifest_version
profile_rule_version
```

新增正式字段：

```text
failure_attribution
incident_id
incident_evidence_status
worker_caused_structural_failure
policy_failure
external_system_failure
structural_failure_evaluable
worker_reliability_eligible
included_in_Q_u_GT
included_in_R_u_LOO
included_in_F_u_struct
gt_reference_identity
gt_reference_sha256
loo_reference_identity
loo_reference_sha256
loo_reference_excludes_worker
loo_peer_support
metric_compatibility_status
```

兼容 flag 映射：

```text
included_in_r_u_calib -> included_in_R_u_LOO
included_in_r_geometry -> diagnostic geometry component inclusion
included_in_T_u        -> semi correction diagnostic inclusion
included_in_U_u        -> undercoverage diagnostic inclusion
```

`included_in_Q_u_GT=true` 至少要求合法独立 submission、manual/in-scope、可用外部 GT reference、合法 geometry、非 process invalid，且 failure disposition 允许 worker quality 评价。

`included_in_R_u_LOO=true` 至少要求合法独立 submission、manual/in-scope、metric compatible、worker-excluded reference 和足够 peer support。

`included_in_F_u_struct=true` 表示该任务是 structural-evaluable opportunity；worker failure 同时使其成为分子。external、policy、OOS、reference failure 和 not-evaluable 均为 false。

任何 insufficient 行仍需保留；不足在聚合层表达。

## 4. `worker_profile_main_matrix_C1.csv`

行粒度为 worker。保留当前实现字段：

```text
worker_id
round_id
r_u_calib
r_u_calib_lcb
r_u_calib_ci_low
r_u_calib_ci_high
r_geometry_u
r_scope_u
correction_reliability_u
coverage_reliability_u
blind_trust_or_correction_failure_rate
undercoverage_failure_rate
T_u
U_u
process_reliability
profile_confidence
protocol_confidence
diagnostic_profile_confidence
profile_confidence_notes
n_calib_support
n_geometry_support
n_scope_support
n_semi_support
n_undercoverage_support
n_process_support
calib_support_status
geometry_support_status
scope_support_status
semi_support_status
undercoverage_support_status
process_support_status
profile_version
profile_freeze_status
notes
```

新增三轴与设计字段：

```text
Q_u_GT_raw
Q_u_GT_task_adjusted
Q_u_GT_ci_low
Q_u_GT_ci_high
Q_u_GT_lcb
Q_u_GT_support
Q_u_GT_support_status
R_u_LOO
R_u_LOO_ci_low
R_u_LOO_ci_high
R_u_LOO_lcb
R_u_LOO_support
R_u_LOO_compatible
R_u_LOO_stability_status
F_u_struct
F_u_struct_numerator
F_u_struct_denominator
F_u_struct_gate_status
d_cal_A
risk_assist_candidate
risk_route_candidate
```

在真实 C1 GT reference/model 尚未完成时，新字段为空并标 `not_evaluable`，不能由 `r_u_calib` 复制填充。

## 5. Diagnostic family / subfamily

`worker_failure_family_response_C1.csv` 保留：

```text
worker_id
round_id
family
n_observed
n_fail
failure_rate
support_status
interpretation_level
interpretation_allowed
source_stages
profile_version
```

`worker_subfamily_response_C1.csv` 保留 worker、family、subfamily、task/observation/failure counts、rate、support、interpretation、global worker coverage、source stage 和 version 字段。低支持只改变 interpretation，不删除原始 evidence。

Diagnostic reliability 统一 higher-is-better；raw risk rate 统一 lower-is-better。`T_u`、`U_u` 仅作为历史 raw-risk alias，不进入 Strong Global。

## 6. P1 跨阶段支持

`p1_to_c1_predictive_validity.csv` 现有字段继续输出：

```text
worker_id
check_name
p1_metric_name
p1_metric_value
c1_metric_name
c1_metric_value
descriptive_directional_alignment
support_status
interpretation_allowed
notes
```

其正式扩展或 `p1_component_support_C2B.csv` 必须增加：

```text
component_id
failure_family
p1_candidate_status
c1_predictive_effect
c1_predictive_ci_low
c1_predictive_ci_high
c1_validation_status
c2b_confirmation_effect
c2b_confirmation_ci_low
c2b_confirmation_ci_high
c2b_confirmation_status
support_n_workers
support_n_tasks
range_restriction_status
preannotation_activation_available
activation_rule_version
full_component_eligible
exclusion_reason
freeze_version
```

进入 Full 必须同时满足 C1 predictive validation、C2-B confirmation、support、方向稳定和标注前可激活。P1 原值不能直接成为 Strong Global 分数；C2-A-RP 不用于发现或挑选新 component。

## 7. C2 final worker profile

`worker_profile_main_matrix_C2_final.csv` 保留所有 C1 字段并增加：

```text
Q_u_GT_task_adjusted_final
Q_u_GT_lcb_final
Q_u_GT_support_final
R_u_LOO_compatible_final
R_u_LOO_lcb_final
F_u_struct_final
B_u_risk_shrunk
B_u_interval_low
B_u_interval_high
B_u_stability_status
B_u_routing_eligible
p1_supported_families
p1_family_scores
process_eligible
independence_valid
strong_global_eligible
S_u_G
d_cal_F
risk_assist
risk_route
profile_version
profile_freeze_status
```

规则：

```text
S_u_G = Q_u_GT_lcb_final
B_u_routing_eligible=false -> B_u adjustment = 0
unsupported P1 component   -> component adjustment = 0
overall Full fallback      -> Full ranking = Strong Global ranking
```

`p1_family_scores` 必须有显式 family、estimate、direction、support 和 freeze provenance；每任务至多激活一个 family。

## 8. Timing 与 annotation identity

正式 annotation identity：

```text
project_id + ls_runtime_task_id + worker_id + annotation_id
```

保留：

```text
selected_annotation_id
selected_annotation_rule
selection_adjudication_status
active_time_source
active_time_match_status
primary_active_time_eligible
geometry_annotation_id
timing_annotation_id
```

同一 worker-task 多 annotation 必须先 adjudicate；禁止自动取最新或自动求和。Geometry 与 timing 必须绑定同一 selected annotation。

## 9. T1/V1 下游接口

Worker profile 工件只提供 outcome 前冻结输入：

```text
T1: risk_assist, worker-image isolation keys, profile_version
V1: S_u_G, B_u_risk_shrunk, B_u_routing_eligible,
    p1_supported_families, p1_family_scores,
    d_cal_F, risk_route, process_eligible, independence_valid
```

V1 outcome、T1 outcome、rerun 或事后专家审查不得回流修改 worker profile。

失败处理另存：

```text
T1 row_failure_attribution + pair_analysis_disposition
V1 worker/policy event + original/rerun resolver
```

不得把 policy failure 或 external incident 转成 worker profile 失败。

## 10. Summary / readiness

`worker_profile_sidecar_*.summary.json` 至少报告：

```text
input_sha256
rule_version
profile_version
failure_disposition_sha256
reference_registry_sha256
formal_inputs_present
artifacts_fresh
three_axis_complete
p1_validation_complete
c2b_confirmation_complete
c2arp_complete
strong_global_ready
full_integrated_ready
formal_closeout_ready
warnings
```

任一必需输入缺失、SHA 失配、complete disposition 不完整或 schema drift 均 fail closed。

## 11. 必测合同

至少验证：

1. C1 原始 export 不需要新增字段即可生成派生 worker evidence。
2. missing disposition 不能默认为 `none`。
3. policy/external/not-evaluable 不进入 worker GT、LOO 或 structural denominator。
4. worker-caused structural failure 只进入 structural 分子，不伪造成 IoU。
5. LOO reference 排除 worker 自身，且不填充 GT quality。
6. P1 component 未经 C1+C2-B 双门不得进入 Full。
7. C2-A-RP 不产生新 component。
8. Full fallback 时排序逐项等于 Strong Global。
9. T1/V1 outcome 不回流 profile。
## 追加：Strong Global 与 component evidence（2026-07-24）

`strong_global_worker_table.csv` 的正式主估计来自 Manual、GT-quality-evaluable submission 的
worker/task 交叉分类模型；同 task 记录采用 task-cluster covariance。最小字段为：

```text
worker_id
Q_GT_raw, Q_GT_task_adjusted, Q_GT_standard_error
Q_GT_CI_lower, Q_GT_CI_upper, Q_GT_LCB
Q_GT_centering_sensitivity
GT_support, task_support, F_struct
process_eligible, independence_eligible, reference_evaluable
global_eligible, exclusion_reason, model_version, profile_version
provisional_rank, global_rank
```

非正式 rehearsal 只允许写 `provisional_rank`；正式 `global_rank` 仅在冻结 manifest、模型、全部 gate
及 eligible worker 下限均通过后写入。

`routing_component_evidence.csv` 以 `worker_id + component_family` 为键，分列保存 P1 raw、P1
integrity-filtered、P1→C1 predictive、C2-B confirmatory 与 validated component。没有正式 C2-B 时必须为
`pending_c2b_confirmation`，且 `c2b_confirmed=false`、`full_component_eligible=false`。

## 追加：variable-k、Strong Global 与 enrollment profile

worker profile 必须按 task-condition-estimand-specific final unique-worker support 解释 Q_GT、peer、LOO、structural 与 timing，不得以单一固定 k 或 edge count 代替。peer profile 使用 task-level equal-weight aggregate，并保存 cluster support/share/normalized margin 与 stable/multimodal status。W014 的正式 profile 固定 excluded；W034 必须同时可审计 original-only 与 original+authorized（17 条）profile，W001 对应 original+authorized（3 条）；outside 不进入任何 primary component。

`S_G` 必须为冻结 administratively eligible、Q_GT-estimable cohort 内 `z(Q_GT_EB)`，而非 LCB；LCB 仅为 gate/sensitivity。`F_struct_raw`、`F_struct_EB` 与 interval 必须分列。Full profile 只有完整 component evidence、support、weight、threshold、fallback、version 与 input SHA 时可 formal；否则 fail closed。若滚动招募开启，profile 明确标示 original-only/pooled cohort 与 late-entry provenance；Stage 3 roster freeze 后不可再改变。
