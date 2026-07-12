# Worker profile artifact field contract v1

> 版本日期：2026-07-12
> 状态：Paper A 写作展示层与 artifact 语义合同；不改变既有代码、CSV/JSON 物理 schema、测试或原始工件。
> 运行真源：`export_label/`、`active_logs/`、现有 analysis artifacts。
> 论文真源：`THESIS_OUTLINE_AUDITABLE_DUAL_CHAIN_v3.md`。
> 不回写：本合同不回写历史预注册、protocol freeze、P1 admission、C1/C2 assignment、routing、统计执行参数或任何历史工件。

## 0. Contract purpose

本合同规定 worker-task evidence、worker profile main matrix、failure-family 长表和 predictive-validity 输出在 Paper A 中如何解释。它区分：

1. Calibration-only protocol reliability `R_u`；
2. P1-informed multi-dimensional diagnostic profile `D_u`；
3. raw risk rates；
4. provenance、validity、support 和 inclusion flags。

物理字段可继续使用历史名称；论文不能因此混淆符号方向或证据资格。

## 1. Required artifact families

以下是论文合同要求的 artifact family；已有实现与历史文件名保持兼容，未实现项不得被写成已生成：

```text
worker_task_evidence_table_C1.csv
worker_profile_main_matrix_C1.csv
worker_failure_family_response_C1.csv
worker_subfamily_response_C1.csv
p1_to_c1_predictive_validity.csv
p1_to_c1_predictive_validity_report.md
worker_profile_c2b_extension_audit.csv
c2b_exclusion_from_primary_r_u_calib_audit.json
```

若生成 C2 final 版本，文件名可沿用既有 `*_C2_final.*` 约定。P1 post-closeout correction/geometry artifacts 仍是只读 diagnostic/provenance 层，不得回写 admission 或 `R_u`。

## 2. Vocabulary contracts

### 2.1 Stage

允许值：`P1`、`C1`、`C2`、`T1`、`V1`；必要时保留 `Pilot` 或 extension/replication 标记。论文主线固定为 `P1 → C1 → C2 → T1 → V1`。

### 2.2 Pool and condition

保留现有 pool/condition 枚举及其物理字段。论文必须区分 `Calibration_manual`、`Calibration_semi`、`Calibration_reserve/C2b`、`Main-Test`、`Main-Validation`；不能将不同 pool 合并成一个未声明的 reliability denominator。

### 2.3 Independence status

```text
independent
confirmed_non_independent
suspected
not_evaluable
```

只有同 task、跨 owner、parent 先于 child、exact geometry hash 一致时，才可自动确认 `confirmed_non_independent`。`suspected` 需 expert review，不能自动记作 worker failure；`not_evaluable` 不是 success。

### 2.4 Scope and reference status

保留 scope response 和现有 OOS subtype。reference status 至少区分：

```text
expert_hard_single
expert_hard_multi
consensus_reference
soft_ambiguous
scope_ambiguous
audit_only
unavailable
```

`expert_hard_single` 使用单 reference；`expert_hard_multi` 使用 max-over-reference；`soft_ambiguous`、`scope_ambiguous`、`audit_only`、`unavailable` 不能进入 hard geometry primary。OOS subtype 是 expert audit metadata，不改变 worker main scope correctness。

### 2.5 Failure family

一级 family 固定为：

```text
geometry_quality_failure
scope_oos_failure
semi_correction_failure
undercoverage_failure
process_failure
```

failure family 是诊断链，不等于 `R_u`。同一 worker-task 可以有多个 evidence signals；undercoverage 不属于 OOS；process issue 不自动成为 geometry failure。

### 2.6 Support and interpretation

允许值：`sufficient`、`insufficient`、`not_evaluable`。所有 insufficient cells 必须保留，且 `interpretation_allowed=false`。support 阈值可做 sensitivity，但不得修改 raw evidence rows。

## 3. Evidence validity gate

每一行 evidence 至少记录以下语义（实际字段名按现有 artifact 兼容）：

```text
stage
pool
condition
worker_id / task_id / canonical_annotation_id
source_artifact_path
source_artifact_sha256
rule_version
independence_status
geometry_reference_status
geometry_valid
scope_valid / scope_adjudicated
process_evaluable
failure_family / failure_subfamily
support_status
interpretation_allowed
included_in_r_u_calib
included_in_r_geometry
included_in_D_u
included_in_T_u_raw_risk
included_in_U_u_raw_risk
included_in_process_reliability
```

Evidence gate 必须同时检查：annotation independence、owner-valid active-time identity、scope/final-gold provenance、reference cardinality/pairing、process/system issue 分离、dry-run proxy、expert-adjudicated undercoverage 和 missing evidence。缺任何关键证据时写 `not_evaluable`，不能隐式补成功。

## 4. Chain A: `R_u` contract

### 4.1 Primary inclusion

`included_in_r_u_calib=true` 当且仅当：

- `stage in {C1,C2}`；
- `pool/condition = Calibration_manual`；
- 通过 independence、scope/reference、geometry validity 和 canonical artifact gate；
- 不属于 C2b extension、P1、Calibration_semi、T1 或 V1；
- 任务和 worker support 可计算。

P1、`Calibration_semi`、C2b、Main/Test、Main/Validation 必须为 false 或明确 diagnostic/audit-only。

### 4.2 Estimator and freeze

合同层只要求记录当前冻结 estimator、CI、LCB、support 和 rule version；不得在文档中擅自选择未注册的新 estimator。C1 只能形成 provisional；C2 结束后冻结：

- `R_u` estimator；
- CI/LCB 和 support 规则；
- `R_{u,s}` activation/degeneration/fallback；
- worker tier、Score、`tau_d` 和 Validation routing contract 的引用版本。

Main/Test/Validation 结果不回流修改 `R_u`。

## 5. Chain B: `D_u` contract

主画像方向统一为越高越好：

| 画像维度 | 符号 | 正式定义 | 主要证据 | raw risk-rate |
|---|---|---|---|---|
| geometry reliability | `G_u` | 兼容 reference-gated geometry success | hard-single/hard-multi 或兼容 consensus evidence | geometry failure rate |
| scope reliability | `S_u` | scope decision success | scope/final-gold/adjudication | scope/OOS failure rate |
| correction reliability | `C_u` | `1 - semi correction failure rate` | semi initialization 与最终 geometry 的独立对照 | blind-trust/correction failure rate |
| coverage reliability | `V_u` | `1 - undercoverage failure rate` | expert-adjudicated full-room compliance | undercoverage failure rate |
| process reliability | `P_u` | `1 - process failure rate` | `process_evaluable` denominator | process failure rate |

`D_u=(G_u,S_u,C_u,V_u,P_u)` 的每一维都必须带 `n_observed`、`n_fail`、support status、stage/pool breakdown 和 inclusion flags。

### 5.1 Correction boundary

若当前数据只支持 issue recognition，则只生成 `issue_recognition_reliability` 或 audit field；不能把 `model_issue` 的选择写成 geometry correction 完成。`C_u` 只有在存在独立 correction evidence 时才可计算。

### 5.2 Process denominator

`process_evaluable=true` 的 worker-attributable rows 进入 `P_u` denominator；system collection issue、unknown-page evidence、无法归因的 timing missingness 为 false，不惩罚 worker。denominator 为零时 `P_u` 为空并标记 `not_evaluable`。

## 6. Raw risk-rate compatibility

现有物理字段 `T_u/U_u` 不删除、不静默改义。论文展示层必须明确：

- `T_u/U_u` 是 raw risk-rate 或 legacy aliases，不是 `D_u` reliability dimensions；
- raw risk-rate 越低越好；
- `C_u/V_u/P_u` 越高越好；
- 任何表格不能用同一列标题同时表示 failure rate 和 reliability；
- 若需要兼容旧输出，使用显式 derived display mapping，不声称物理 schema 已迁移。

## 7. Active-time field contract

```text
exact owner-valid annotation-level browser log   primary
known-only but integrity-suspect session          sensitivity
task-level fallback                               sensitivity/audit
lead_time fallback                                sensitivity/audit
unknown_annotation                                audit-only, unassigned
parent-derived timing                             forensic audit-only
system collection bug                             system issue
```

必须保留 `active_time_source`、`primary_active_time_eligible`、source identity、script version、fallback reason、parent-derived flag 和 missingness status。active-time 是 RQ1 cost/efficiency evidence，不是 worker quality 字段。

## 8. Geometry metric contract

P1 post-closeout geometry metric 是 diagnostic、post-closeout、reference-gated metric：

- hard-single 使用 single reference；
- hard-multi 使用 max-over-reference；
- pairing、范围、奇数点、歧义和 reference cardinality 必须过 gate；
- metric name、direction、normalization 必须随 component 记录；
- 不兼容 metric/direction/normalization 不合并；
- integrated `G_u` 只有在有足够兼容 stage/pool components 时才形成；
- geometry score 不是 GT correctness 的唯一替代；
- A-line Manhattan 几何工具不进入 Paper A 正式主实验。

## 9. Failure-family and subfamily tables

### 9.1 First-level response table

`worker_failure_family_response_C1.csv`（及 C2 final 版本）至少包含：

```text
worker_id
stage / pool / condition
failure_family
n_observed
n_fail
failure_rate
support_status
interpretation_allowed
source_manifest_version
```

`failure_rate = n_fail / n_observed`，分母为零时为空并标记 `not_evaluable`。同一 submission 的多个 family signal 不得强制互斥。

### 9.2 Subfamily table

subfamily 允许保留现有枚举（geometry degradation、scope subtype、correction、undercoverage、process integrity 等），但 support 不足时只做 audit/sensitivity。`non_independent_submission` 属于 process integrity subfamily，不得 relabel 为 geometry failure。

### 9.3 Counterexample bank

自动候选必须记录 candidate path、SHA、rule version、failure family 和 review status；只有 expert review 通过后才可成为 final counterexample。counterexample bank 是二级创新与解释性结果，不是唯一核心贡献。

## 10. Worker profile main matrix

`worker_profile_main_matrix_C1.csv`（及 C2 final 版本）的论文正式列为：

```text
worker_id
G_u / S_u / C_u / V_u / P_u
raw_geometry_failure_rate
raw_scope_oos_failure_rate
raw_blind_trust_or_correction_failure_rate
raw_undercoverage_failure_rate
raw_process_failure_rate
n_geometry_support / n_scope_support / n_correction_support
n_coverage_support / n_process_support
geometry_support_status / scope_support_status
correction_support_status / coverage_support_status / process_support_status
stage_pool_component_summary
diagnostic_profile_confidence
included_stage_pool_flags
freeze_stage
source_manifest_version
```

若当前物理文件仍使用 `r_geometry_u`、`r_scope_u`、`T_u`、`U_u` 等旧列，迁移表必须显式标注其展示层映射；不得把未实现的新列写成已经存在。

## 11. Predictive-validity output

`p1_to_c1_predictive_validity.csv` 至少记录：

```text
worker_id
p1_profile_component
target_stage / target_pool / target_component
independence_status
process_validity_status
n_predictor_support / n_target_support
support_status
effect_or_prediction_estimate
ci_or_uncertainty
interpretation_allowed
notes
```

`confirmed_non_independent` 不进入 capability predictor；`suspected` 保留 pending；`not_evaluable` 不形成 success。predictive validity 是跨阶段验证，不是 P1 自证，也不是 routing utility。

## 12. C2b extension exclusion

C2b 可以输出 diagnostic extension audit，但必须有明确排除记录：

```json
{
  "primary_r_u_calib_excludes_c2b": true,
  "c2b_role": "diagnostic_extension_only",
  "excluded_from_primary_fields": [
    "R_u estimator",
    "LCB/CI primary evidence",
    "worker tier freeze",
    "Validation routing freeze"
  ]
}
```

## 13. Required consistency checks

文档/实现审计至少检查：

1. `R_u` 只来自 C1/C2 `Calibration_manual`；
2. P1、Calibration_semi、C2b、Main 不进入 primary `R_u`；
3. `D_u` 五维均越高越好；
4. raw risk-rate 独立保留且越低越好；
5. OOS gate 不混入 manual geometry reliability；
6. undercoverage 不归入 OOS；
7. process/system issue 分离；
8. insufficient cell 保留且 `interpretation_allowed=false`；
9. missing evidence 为 `not_evaluable`；
10. 所有主张带 artifact path、SHA、rule version 和 inclusion flags。

## 14. Implementation status and non-goals

本次只更新写作与字段语义合同，不实现新的 materializer、schema migration、predictive model、routing service 或 geometry scorer。代码、测试、数据、分析结果、P1/C1/C2/T1/V1 协议和原始工件均不在本次范围内。
