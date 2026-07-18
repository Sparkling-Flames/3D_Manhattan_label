# C1/C2 工件字段合同 v1

> 状态：Paper A vFinal 正式字段合同
> 更新：2026-07-18
> 上位真源：`ROUND_BASED_EXECUTION_PROTOCOL_v1.md`、`ROUND_BASED_ASSIGNMENT_SOP_v1.md`、`STATISTICAL_ANALYSIS_PLAN_v1.md`

## 0. 边界

本合同定义 `C1 -> C2-B -> C2-A-RP -> Main freeze` 的最小物理字段。它不改变已经开始的 C1 assignment、Label Studio schema 或原始 export；所有新增字段均由 canonicalization、事故注册表、reference registry 和分析派生链生成。

```text
export_label/ raw export（不变）
+ import_json/ assignment manifest（不变）
+ active_logs/（不变）
-> C1 canonical roster
-> complete failure disposition
-> 三轴 worker state
-> C2-B design simulation / assignment
-> C2-A-RP precision completion
-> C2 final freeze bundle
```

任何 C1/C2 工件不得依赖 T1/V1 outcome。C1 是 provisional；只有 C2 closeout 且全部 SHA、support、freshness 和 freeze gate 通过后，才可形成 Main 输入。

所有正式表至少携带：

```text
schema_version
rule_version
stage
round_id
source_artifact
source_sha256
dependency_bundle_id
validity_status
interpretation_allowed
freeze_version
```

## 1. C1 canonical 与失败处置

### 1.1 `c1_canonical_annotations.csv`

行粒度为一个选定的 `canonical_annotation_id`。保留当前 canonical 字段，并要求：

```text
canonical_annotation_id
project_id
ls_runtime_task_id
task_id
base_task_id
image_id
worker_id
annotation_id
stage
pool
condition
annotation_created_at
annotation_updated_at
assignment_expected
active_time_source
primary_active_time_eligible
failure_attribution
incident_id
incident_evidence_status
worker_caused_structural_failure
policy_failure
external_system_failure
structural_failure_evaluable
worker_reliability_eligible
```

新增失败字段全部由派生链生成，不要求标注员填写。缺 disposition 行、未知归因或证据不足必须 fail closed 为 `not_evaluable`。

### 1.2 `incident_registry.csv`

行粒度为一个预先登记的外部事故：

```text
incident_id
incident_type
occurred_at
recovered_at
affected_project_ids
affected_task_ids
affected_scope_rule
evidence_path
evidence_sha256
recorded_at
recorded_before_outcome_review
```

external attribution 只有在 registry 存在、证据 SHA 匹配、任务处于影响范围、annotation 时间落入事故窗口且事故在 outcome review 前登记时才可成立。

### 1.3 `failure_disposition.csv`

行粒度与 canonical roster 一致，必须覆盖每个 canonical annotation：

```text
canonical_annotation_id
stage
task_id
worker_id
condition
failure_attribution
row_failure_attribution
incident_id
incident_evidence_status
analysis_disposition
disposition_reason
adjudicated_at
adjudicator_id
rule_manifest_version
rule_manifest_sha256
```

`failure_attribution` / `row_failure_attribution` 允许：

```text
none
worker_caused_structural_failure
policy_caused_failure
external_system_failure
not_evaluable
```

正常行必须显式为 `none`；sparse incident registry 不能直接当 complete disposition 使用。

## 2. C1 测量与设计工件

### 2.1 `worker_state_snapshot_C1.csv`

行粒度为 worker：

```text
worker_id
round_id
admission_status
r0_prescreen
w_max_locked
n_anchor_completed
n_core_completed
n_calib_completed
Q_u_GT_raw
Q_u_GT_task_adjusted
Q_u_GT_ci_low
Q_u_GT_ci_high
Q_u_GT_lcb
Q_u_GT_support
R_u_LOO
R_u_LOO_ci_low
R_u_LOO_ci_high
R_u_LOO_compatible
R_u_LOO_support
F_u_struct
F_u_struct_numerator
F_u_struct_denominator
structural_profile_status
d_cal_A
risk_assist_candidate
risk_route_candidate
worker_state_version
```

三轴含义固定：

- `Q_u_GT_task_adjusted`：外部 GT 质量，经 task composition 调整；Strong Global 的正式能力轴。
- `R_u_LOO*`：worker-excluded Geometry LOO 一致性/compatibility；仅作审计和冻结 tie-break。
- `F_u_struct`：worker-caused structural failure / structural-evaluable opportunities。

当前代码兼容映射：

```text
r_u_hat / r_u_calib           -> R_u_LOO（legacy LOO alias）
r_u_ci_low / r_u_calib_ci_low -> R_u_LOO_ci_low
r_u_ci_high                   -> R_u_LOO_ci_high
r_u_h / r_u_calib_lcb         -> R_u_LOO 的保守摘要
```

这些 legacy 列可以继续输出，但不得再命名为 GT quality、Strong Global score 或唯一 worker reliability。

### 2.2 C1 设计输入

保留现有：

```text
assignment_manifest_C1.csv
ci_precision_audit_C1.csv
scene_coverage_gap_C1.csv
scene_candidate_summary_C1.csv
dt_reference_summary_C1.json
```

其中 `assignment_manifest_C1.csv` 仍保存 `common_anchor` / `balanced_core`；旧 `needs_c2_ci_fill`、`needs_c2_scene_fill`、`coverage_gap` 继续作为 C2 设计模拟输入，不直接决定 reserve-only 补派。

### 2.3 `c2_design_simulation_C1.csv`

每行一个候选 C2-B 设计：

```text
design_id
n_common_anchor
n_diverse_bridge
n_unique_tasks
min_task_support
worker_task_graph_connected
graph_component_count
min_worker_degree
min_task_degree
Q_u_GT_expected_interval_width
B_u_expected_interval_width
routing_activation_rate
fallback_rate
budget_tasks
budget_time
feasible
selection_status
selection_reason
simulation_seed
source_c1_bundle_sha256
```

选择规则必须在查看 C2 outcome 前冻结；不得硬编码旧的 reserve-only 数量。

## 3. C2-B common anchor + diverse bridge

### 3.1 `assignment_manifest_C2B.csv`

行粒度为 `(round_id, worker_id, task_id)`：

```text
round_id
worker_id
task_id
base_task_id
image_id
dataset_group
assignment_batch
bridge_role
design_id
assignment_reason
expected_completion_order
manifest_version
manifest_sha256
```

`bridge_role` 只允许：

```text
common_anchor
diverse_bridge
```

共同 anchor 提供跨 worker 比较；diverse bridge 扩展 task/risk coverage。现有 `assignment_manifest_C2.csv` 可在迁移期作为文件别名，但必须携带 `bridge_role`，不得继续表达“仅 CI/scene reserve 补齐”。

### 3.2 `c2b_bridge_audit.csv`

```text
design_id
worker_id
n_common_anchor_assigned
n_common_anchor_completed
n_diverse_bridge_assigned
n_diverse_bridge_completed
n_unique_tasks
worker_degree
task_graph_component
graph_connected
support_status
validity_status
```

### 3.3 跨阶段确认

`p1_component_support_C2B.csv` 行粒度为 `(worker_id, component_id)`：

```text
worker_id
component_id
p1_candidate_status
c1_predictive_validation_status
c2b_confirmation_status
support_n
effect_direction_stable
preannotation_activation_available
full_component_eligible
exclusion_reason
freeze_version
```

只有 C1 validation 与 C2-B confirmation 均通过，且 support 和标注前 activation 合法时，`full_component_eligible=true`。

## 4. C2-A-RP precision-adaptive completion

### 4.1 `c2arp_precision_gap.csv`

```text
worker_id
component_id
target_estimand
current_interval_width
target_interval_width
current_support
precision_gap
routing_value_status
needs_c2arp
stop_reason
max_additional_tasks
```

### 4.2 `assignment_manifest_C2A_RP.csv`

```text
round_id
worker_id
task_id
base_task_id
task_stratum
assignment_sequence
c2_component
target_component
gap_reason
precision_before
support_before
support_after
selection_probability
design_manifest_sha256
c2b_summary_sha256
post_c2b_worker_profile_sha256
```

`assignment_reason` 只允许已由 C1/C2-B 定义的 precision gap；C2-A-RP 不搜索新 risk、failure family 或 P1 component。达到冻结上限仍不稳定时，对应调整归零并 fallback Strong Global。

正式生成还必须绑定完整 C1/C2-B assignment history，排除同一 worker 已见的
`task_id` 和 `base_task_id`，并执行冻结的 task support 上限。

### 4.3 `c2b_closeout.summary.json`

由 `materialize_c2b_closeout.py` 将 C2-B submissions、post-C2-B worker profile、
profile manifest 和 C2-B design summary 绑定为：

```text
c2b_submissions_sha256
post_c2b_worker_profile_path
post_c2b_worker_profile_sha256
post_c2b_profile_manifest_sha256
c2b_design_summary_sha256
c2b_closeout_ready
```

C2-A-RP formal 只能读取该 closeout，不接受测试或人工拼装 summary。

## 5. C2 最终冻结

### 5.1 `worker_state_snapshot_C2_final.csv`

保留 C1 三轴字段并增加：

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
B_u_routing_eligible
p1_supported_families
process_eligible
independence_valid
strong_global_eligible
S_u_G
d_cal_F
risk_assist
risk_route
profile_version
state_locked
```

`S_u_G = Q_u_GT_lcb_final`。`B_u_risk_shrunk` 是层级收缩风险韧性项；support/稳定性不足时 `B_u_routing_eligible=false` 且调整为 0。

### 5.2 `task_risk_rule_manifest_v1.json`

至少包含：

```text
meta
d_model_feat_rule
g_model_struct_rule
d_cal_A_rule
d_cal_F_rule
risk_assist_rule
risk_route_rule
family_activation_rule
support_rule
fallback_rule
```

`d_cal_A` 只用于 C1 后设计 C2；`d_cal_F` 只在 C2 后冻结供 V1 使用，不得反向改变 C2。

### 5.3 `policy_freeze_manifest_v1.json`

至少包含：

```text
strong_global
full_integrated
score_adjustment_cap
p1_component_registry
B_u_rule
profile_version
availability_rule
capacity_rule
offer_timeout_rule
replacement_rule
dynamic_redundancy_rule
gt_blind_aggregation_rule
terminal_state_rule
failure_disposition_rule_manifest_sha256
incident_registry_sha256
t1_pair_rule
v1_rerun_rule
analysis_plan_sha256
code_commit
frozen_at
```

Strong Global 只按 `S_u_G` 排序，LOO 仅作冻结 tie-break。Full 在 Strong Global 上加入经确认的 `risk_route`/`B_u` 和至多一个标注前激活的 P1 family 项；任何整体 fallback 条件成立时，其排序必须等于 Strong Global。

### 5.4 `calibration_freeze_report_v1.md`

必须报告：

- C1 输入、complete disposition 和三轴 worker state；
- C2-B simulation、选定设计、anchor/bridge 图结构；
- C2-A-RP assignment、停止和达到上限的 component；
- P1→C1→C2-B support；
- `d_cal_A` / `d_cal_F`、`risk_assist` / `risk_route`；
- Strong Global/Full eligibility、activation、fallback 和政策差异可行性；
- 全部 downgrade、manifest SHA、input SHA 和 code commit。

## 6. Main failure / resolver 接口

C2 freeze bundle 必须预先定义以下下游表；字段细节由 Main materializer 输出，但规则不得在 outcome 后改变。

### T1

```text
t1_row_failure_disposition.csv:
  pair_id, pair_run_id, condition, canonical_annotation_id,
  row_failure_attribution, incident_id

t1_pair_analysis_disposition.csv:
  pair_id, original_pair_run_id, rerun_pair_run_id,
  pair_analysis_disposition, rerun_sequence, freeze_version,
  final_analysis_pair_run_id, disposition_reason
```

每个 pair run 恰好一条 Manual 和一条 Semi；未受影响行保持 `row_failure_attribution=none`。

### V1

```text
v1_reservation_registry.csv:
  reservation_id, original_task_id, rerun_task_id, block_id, freeze_version,
  availability_snapshot_id, reservation_arm, reservation_capacity_before,
  reservation_capacity_after, reservation_status, reserved_at, consumed_at

v1_rerun_chain.csv:
  original_task_id, rerun_task_id, policy_arm, freeze_version,
  rerun_sequence, reservation_id, reservation_arm,
  reservation_capacity_before, reservation_capacity_after

v1_analysis_resolved_itt.csv:
  original_task_id, randomized_arm, selected_outcome_task_id,
  analysis_disposition, terminal_status, itt_included,
  delivery_adjusted_quality, provenance_status

v1_policy_task_summary.csv:
  block_id, task_id, policy_arm, risk_route, availability_snapshot_id,
  candidate_set, full_fallback, fallback_reasons,
  offers_used, completed_workers, candidate_exhausted,
  policy_failure, policy_failure_reason,
  terminal_status, policy_terminal_status, non_delivery,
  selected_worker_id, selected_annotation_id, selected_geometry_sha256, valid_k,
  largest_cluster_support, second_cluster_support, medoid_margin
```

合法 rerun outcome 必须绑定已消费的真实 reservation registry 行，替代 original
outcome 但保留原随机化臂；`external_system_failure_pending_disposition` 不能成为最终政策终态。

`materialize_vfinal_main_analysis.py` 只读取上述 resolver-finalized 表，并输出
`t1_pair_analysis.csv`、`t1_summary.csv`、`v1_itt_tasks.csv`、`v1_summary.csv`
与 `v1_standardized.csv`。正式运行必须绑定 resolved input、freeze manifest、
rule manifest 及可选 production-weights CSV 的 SHA-256。

## 7. 兼容与禁止语义

- `Calibration_reserve` 仍可作为任务来源标签，但不再定义 C2 的设计目的。
- 旧 `reserve_usage_audit_C2.csv` 可作为历史输入审计，不是当前 C2 成功标准。
- 旧 `C2b_diagnostic_extension` 映射到历史探索标签，不得与正式 `C2-B` 混用。
- 旧 Random/Global/Full offline replay 仅可标记 `legacy_diagnostic`；它不是正式 RQ3，也不能替代 V1。
- 不生成正式 C1/C2 数值，直到真实 C1 export、reference、事故/disposition 和 freshness gate 齐全。
