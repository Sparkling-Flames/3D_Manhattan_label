# B 线 Freeze v2.1 Contract Audit（2026-03-17）

## 审计范围

本审计仅评估 `formal-prep-freeze-v2.1` 的 contract hardening，不宣称 B 线 formal analysis 闭环。

输入产物：
1. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/formal_prep_freeze_v2_1_manifest.json`
2. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/analysis_input_summary.json`
3. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/stage1_alignment_audit_v2_1.json`
4. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/active_time_estimand_audit_v2_1.json`
5. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/tim_mapping_spec_v2_1.json`
6. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/tim_rule_summary_v2_1.csv`
7. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/type4_evidence_v2_1.csv`
8. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/tim_row_audit.csv`
9. `analysis_results/stage_aware_analysis_freeze_v2_1_20260317/freeze_v2_1_consistency_audit.json`

说明：当前仓库数据仍是测试数据，且含旧版本数据。

## 核心结论

状态标签：`B: partial / formal-prep-freeze-v2.1`

可支持表述：
1. `selection_manifest_path` 已非空，且阻塞状态显式化。
2. Stage1 protocol 对齐状态已结构化为可审计 gate（当前为 blocked）。
3. `active_time` 主终点状态已结构化为 estimand 审计（当前为 mixed estimand）。
4. TIM 主链已将 Type4 从 M-tier 隔离，且与 Type4 evidence 达到行级一致。
5. v2.1 规则版本与 canonical 工件命名已对齐，并保留 legacy alias。

不可支持表述：
1. B 线 formal analysis 已完成。
2. B 线已 thesis-facing 闭环（当前 `thesis_selection_ready=false`）。
3. RQ1 主终点已修复（当前仍 mixed estimand）。

## 四项硬证据

### 1) Thesis readiness 阻塞显式化

证据（manifest + input summary）：
1. `selection_manifest_mode=autogen_default_gate`
2. `thesis_selection_ready=false`
3. `thesis_readiness_status=blocked_autogen_default_gate_selection_and_stage1_protocol_not_aligned`
4. `thesis_readiness_blockers=["autogen_default_gate_selection","stage1_protocol_not_aligned"]`

判定：
1. 当前 freeze 不是 thesis-facing selection。
2. 阻塞项不再是口头描述，而是 contract 字段。

### 2) Stage1 protocol gate（manual anchor / semi）

证据（`stage1_alignment_audit_v2_1.json`）：
1. `stage1_alignment_passed=false`
2. `manual_anchor_alignment_status=under_target_and_not_aligned`
3. `prescreen_semi_alignment_status=not_aligned_and_not_materialized`
4. blockers：
   - `stage1_manual_anchor_not_aligned`
   - `stage1_prescreen_semi_not_aligned`

判定：
1. Stage1 配额冲突已进入正式阻塞链，而非隐式风险。

### 3) Active time estimand gate

证据（`active_time_estimand_audit_v2_1.json`）：
1. `n_log=39`
2. `n_lead_time_fallback=75`
3. `mixed_estimand=true`
4. `primary_endpoint_ready=false`
5. `active_time_endpoint_status=mixed_estimand_log_plus_fallback`
6. `recommended_analysis_mode=log_only_primary_with_fallback_sensitivity`

判定：
1. RQ1 主终点当前不可写为 clean primary estimand。
2. 已形成 machine-readable 的审计与建议口径。

### 4) TIM/Type4 一致性与命名一致性

证据：
1. `tim_mapping_spec_v2_1.json` + `tim_rule_summary_v2_1.csv` + `type4_evidence_v2_1.csv` 为 canonical v2.1 工件。
2. `freeze_v2_1_consistency_audit.json`：
   - `consistency_gate_passed=true`
   - `missing/extra/scope_mismatch/tier_mismatch/type4_flag_mismatch` 全部为 `0`
   - `type4_in_m_row_audit=0`
   - `type4_in_m_type4_evidence=0`
3. manifest 声明：
   - `artifact_naming_policy=canonical_v2_1_with_legacy_aliases`
   - `legacy_alias_artifacts` 单列保留兼容文件

判定：
1. “规则版本 v2.1 / 文件命名 v1-v2 混杂”风险已收口。
2. “TIM 主链与 Type4 evidence 不一致”风险已收口。

## 与既有边界的一致性

以下边界不变：
1. A 线仍 `partial / blocked`。
2. B 线仍不是 formal analysis 闭环。
3. C 线仍 `partial / closest-to-closure`。
4. 第 4 章正文级证据链尚未完整闭环。

## 下一步（严格顺序）

1. 先提供 thesis-facing selection manifest（非 autogen）。
2. 再解决 Stage1 manual anchor / semi 配额对齐。
3. 在两项阻塞解除后推进 B v2.5/v3 主证据链。
