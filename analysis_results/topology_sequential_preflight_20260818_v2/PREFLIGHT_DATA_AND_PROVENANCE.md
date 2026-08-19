# HOHONET topology sequential preflight v2

开发诊断工件；不构成科学结论、正式政策冻结或 Main 启动依据。v1 状态为 `superseded_development_descriptive_only`。

- development_only: true
- diagnostic_pre_stage3: true
- scientific_conclusion_prohibited: true
- block3: false
- formal_policy_frozen: false
- formal_profile_frozen: false

## 输入、人数与支持

真源为冻结 C1 geometry、structural validation、task-building binding、operational reference audit 与 manual k>=5 crowd-structure sidecar。历史 inventory 为78个 base task；live worker 固定20人（W14行政排除，W18/W27 withdrawn）。按共同 admission（structurally valid 且 geometry metric evaluable），47个任务具有固定k=5历史反事实支持，覆盖12个building；其余31个任务只标记 `historical_counterfactual_support_shortfall`。该31/78不是未来候选池耗尽率，也不用于政策质量或部署成本比较。

## 主 estimand 与顺序

seed=20260818，replicates=1000。主比较严格限定共同47任务；F0、M0_corner_count_gate_geometry_medoid、M1在每个task/replicate使用完全相同的无放回order，共141000个政策行，并先在task内汇总再做task-equal平均。每项指标分别报告实际task、replicate和building support。building bootstrap为12-block敏感性，不外推至缺失的第13个building。

F0/M0/M1共用结构/metric admission、invalid/replacement和attempt ledger。M0停止门只使用repaired point count/2，但最终选择使用完整geometry medoid；因此M0与F0同时存在停止时机和解析规则差异，不能把质量差全部归因于节省提交。M1的开发性保守门为：k=3仅3:0；k=4仅4:0或3:1；k=5仅5:0或4:1；其他k=5状态为`unresolved_expert_escalation_required`，不得强制选择medoid。该门尚非正式政策。

## 质量、成本与harm lanes

public-GT complete-case质量只作诊断。将自主部分未交付记0的结果明确标为`reference-evaluable autonomous-delivery mITT sensitivity`：成功输出若缺少合格reference仍保持missing，因此它不是完整ITT；M1包含expert fallback后的最终质量和总成本均为not_identifiable。47任务上的paid valid submissions和savings是已有至少5个有效候选条件下的成本诊断，不包含未来invalid/replacement、expert fallback、availability或调度成本，不允许解释为生产总成本降幅。正式质量规则仍为superiority；未创建或从结果选择NI margin。continuous geometry delta与corner-count change分开报告；因无冻结material tolerance，不二值化material geometry。selected structural invalidity为shared admission造成的rule-defined zero，不给[0,0]经验风险区间。actual expert/reference delivery harm为source_absent。

M2状态为`not_evaluated_leakage_safe_estimator_absent`；M3状态为`pending_pre_peer_timing_binding`。post-task meta禁止首次路由，且不声称causal routing effect。readiness仅为`conditional_go_shadow_only`，不冻结M1；actual live/Main为not_ready。

normalization_version_conflict_count=1
operational_geometry_and_structural_pool_distribution={4: 31, 5: 35, 20: 12}
