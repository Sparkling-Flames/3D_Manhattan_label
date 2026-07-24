# C1 Pre-closeout 审计字段合同

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
