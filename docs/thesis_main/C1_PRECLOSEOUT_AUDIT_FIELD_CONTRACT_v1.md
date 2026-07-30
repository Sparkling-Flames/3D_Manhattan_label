# C1 Pre-closeout 审计字段合同

## 2026-07-24 SHA 处置与 LOO 修订

- `c1_structural_validation_pre_disposition.csv` 是逐行结构裁决的输入快照；结构 disposition 必须以 `canonical_annotation_id + source_structural_audit_sha256` 绑定，并保存 Scope、最终归因、分母/分子资格、复核人和时间。
- independence 可由 annotation-level disposition 或 project-level provenance manifest 解锁。project manifest 必须绑定 `source_meta_sha256`，证明 parent 字段覆盖完整、跨 owner parent 数为零且 copy risk 已清除；否则保持 `not_evaluable`。
- `q_LOO_tu` 直接使用已规范化 pair 计算 held-out 与唯一 peer medoid 的 layout-mask IoU，不得再次配对。只有 `task_consensus_status=stable` 可进入 primary；worker 点估计和 2000 次 bootstrap 均以 base task 为单位并使用 mean。

状态：仅适用于 `precloseout_partial_c1` rehearsal；不得作为正式 closeout、冻结画像或 C2 启动依据。

## 完成度与任务支持

- `c1_worker_completion_audit.csv`：按正式 roster 输出 assigned、raw observed、canonical selected、missing 和 completion status。
- `c1_assignment_realization_audit.csv`：逐个 assignment edge 区分未提交与已提交但重复版本待裁决；后者不得计为缺交。
- `c1_task_support_deficit.csv`：按 task/condition 输出 planned、observed、structurally valid support 与支持状态。

## 结构、LOO 与可靠性门

- `structural_validation_audit.csv`：保存解析、配对、角点数、拓扑、多边形检查及工人/系统归因。
- `eligible_for_geometry_loo` 只表示几何可进入 worker-excluded 比较。
- `worker_reliability_eligible` 还必须满足冻结的独立性和过程门。独立性未知不阻止几何计算，但必须阻止正式工人画像。

## Active-time

- `c1_active_log_source_audit.csv`：判断日志是否覆盖实际 C1 时间窗。
- `c1_active_time_binding_reason_audit.csv`：区分 exact、annotation ID 缺失、project/worker mismatch 与无事件。
- `active_log_source_valid_for_c1` 与 `primary_exact_binding_ready` 是两个不同字段；来源正确不能替代 annotation 精确绑定。

## Operational reference 与 C2 roster

公共冻结 GT 几何可在 task outcome 仍为 pending 时计算 provisional quality；不得借此把 legacy scope proxy 提升为已裁决 task outcome。

`c2_eligible_roster_C1.csv` 必须显式输出 `c2_candidate_eligible`。空值不得解释为 eligible；nonstarter、支持不足、process 未清、independence 未冻结或 structural profile 不可评价均 fail-closed。

## 2026-07-24 最终收口字段

- `c1_geometry_anomaly_root_cause_audit.csv` 分离检测、验证状态、归因和 estimand inclusion；系统、解析、转换、seam、reference、OOS 与未知归因不得进入工人结构失败分子或分母。
- `c1_active_time_event_ledger.csv`、`c1_active_time_session_ledger.csv` 与 `c1_active_time_annotation_summary.csv` 只消费显式通过 page gate 且绑定 canonical server annotation ID 的累计事件，并合并 session 重叠区间。旧版 unknown/mixed 仅保留 forensic audit；新版仅当同一 session 的 `project+task+worker` 唯一 late-bind 到一个 server annotation ID，且 alias/page-gate 证据完整时，才可形成 `eligible_late_bound_session`。
- `C1_assigned_roster.csv`、`C1_observed_roster.csv`、`C1_analysis_roster.csv` 与 `c2_eligible_roster_C1.csv` 分开保存。partial 按局部有效 support 判断，nonstarter 不生成画像。
- `c1_three_track_worker_state.csv`（rehearsal）与 `c1_three_track_worker_state_formal.csv`（formal）的唯一三轨为 `Q_GT_task_adjusted`、`R_LOO_compatible`、`F_struct`；状态仅允许 `estimated`、`insufficient_support`、`not_evaluable_pending_independence`、`nonstarter`。active time 不属于三轨，也不阻断 C2。
- `c1_final_canonical_closeout_summary.json` 必须在 completion、version、independence、structural、Scope/reference 和 row eligibility 全部应用后重算；reviewed estimand-specific exclusion 不是全局 blocker。
# C1→C2-B estimand-specific freeze 补充

- 正式三轴只由 `Q_GT_FREEZE_STATUS`、`R_PEER_FREEZE_STATUS`、`F_STRUCT_FREEZE_STATUS` 记录；`R_LOO_MEDOID_STATUS` 与 `R_LOO_STRICT_STATUS` 是独立 sensitivity 状态，不参与 `three_axis_complete`。
- `C1_EVIDENCE_BUNDLE_FROZEN=true` 仅表示 collection 已关闭且三轴均到达终态；不得解释为所有轴均可估计。
- `C2B_BASELINE_INPUT_FROZEN=true` 只由 Q_GT、process、independence 与对应 worker support 产生。
- `c2b_baseline_eligible` 是 C2-B 参数模型和 simulation 的唯一 worker inclusion gate；nonstarter、行政排除和 `closed_partial_insufficient` 仍保留审计行但不参与模型。
- `Q_GT_baseline_source` 正式值必须为 `strong_global_task_adjusted`；原始逐行 IoU 不能冒充 worker baseline SE。
- `C2_TASK_FEATURES_FROZEN` 与 `C2B_ELIGIBLE_RISK_POOL_FROZEN` 分属 feature owner 和最终 eligibility owner，下游不得互相代写。
- completion 状态默认由冻结 assignment 与 export 自动计算；completion disposition 只处理行政排除等例外。无例外行不得要求 23 份逐人审批，错误 SHA、重复或孤儿 exception disposition 仍须 fail-closed。
- collection close 后，partial worker 按 row eligibility 转为 `closed_partial_usable` 或 `closed_partial_insufficient`；三轴 support 分列保存，不得以任一轴的数量替代其他 gate。

## C2-B 静态 evidence review queue

- `prepare-c2b-static` 输出 `authoritative_building_registry.review_queue.csv`、`source_split_evidence.review_queue.csv`、`future_holdout_evidence.review_queue.csv`、`history_overlap_audit.review_queue.csv`、`scope_registry.review_queue.csv` 和 `reference_registry.review_queue.csv`。
- 六份 queue 以 `image_id + base_task_id` 唯一，包含 inventory identity、source path、legacy reverse membership 与明确标记为 diagnostic 的旧 inventory 字段；正式 gate 字段保持空值或 `pending_review`。
- queue 的 `formal_evidence_ready=false`。正式证据必须另存于 evidence root，包含显式 reviewer/time/status，并由对应 approval manifest 绑定 SHA；仅改名或从 task/image 前缀推断 building 均不成立。
