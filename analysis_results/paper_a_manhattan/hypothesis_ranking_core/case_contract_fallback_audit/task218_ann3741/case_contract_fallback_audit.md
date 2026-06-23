# HRC C1.1 Case Contract Fallback Audit

- Schema: `hrc_c1_1_case_contract_fallback_audit_v1`
- Case: `task218_ann3741`
- Active runner unchanged: `True`
- Accepted: `False`
- Downstream recommendation: `False`

## Cases

### task218_ann3741

- contract_source: `rule_based_projection_v2`
- contract_status: `available`
- fail_closed: `False`
- expert_review_only: `False`
- legacy_default_contract.used: `False`
- auto_contract_summary.source: `projection_rule_based_v1`
- risk: `None`
- recommended_next_status: `projection_rule_based_contract_available`

### synthetic_missing_metrics

- contract_source: `contract_unavailable`
- contract_status: `unavailable`
- fail_closed: `True`
- expert_review_only: `True`
- legacy_default_contract.used: `False`
- auto_contract_summary.source: `contract_unavailable_fail_closed`
- risk: `contract_unavailable_fail_closed`
- recommended_next_status: `contract_unavailable_expert_review_only_fail_closed_candidate`

### synthetic_partial_malformed_metrics

- contract_source: `contract_unavailable`
- contract_status: `unavailable`
- fail_closed: `True`
- expert_review_only: `True`
- legacy_default_contract.used: `False`
- auto_contract_summary.source: `contract_unavailable_fail_closed`
- risk: `contract_unavailable_fail_closed`
- recommended_next_status: `contract_unavailable_expert_review_only_fail_closed_candidate`

