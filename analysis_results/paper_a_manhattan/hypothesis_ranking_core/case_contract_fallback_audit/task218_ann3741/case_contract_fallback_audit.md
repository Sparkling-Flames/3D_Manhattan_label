# HRC C1.1 Case Contract Fallback Audit

- Schema: `hrc_c1_1_case_contract_fallback_audit_v1`
- Case: `task218_ann3741`
- Active runner unchanged: `True`
- Accepted: `False`
- Downstream recommendation: `False`

## Cases

### task218_ann3741

- contract_source: `rule_based_projection_v2`
- legacy_default_contract.used: `False`
- auto_contract_summary.source: `projection_rule_based_v1`
- risk: `None`
- recommended_next_status: `projection_rule_based_contract_available`

### synthetic_missing_metrics

- contract_source: `rule_based_v1`
- legacy_default_contract.used: `True`
- auto_contract_summary.source: `legacy_fallback`
- risk: `legacy_default_contract_in_active_contract`
- recommended_next_status: `contract_unavailable_expert_review_only_fail_closed_candidate`

