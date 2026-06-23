# HRC C6 Stability Audit

- Schema: `hrc_c6_stability_audit_v1`
- Conclusion: `B: C6 still audit-blocked; only task218_ann3741 has active HRC bucket audit`
- Conclusion basis: `only task218_ann3741 has active HRC bucket audit; task218_ann2369/task238_ann2389/gt75_task533/ordinary_compatible are unavailable for active HRC bucket audit and remain evidence-only`
- Active HRC bucket audit cases: `task218_ann3741`
- Unavailable active HRC cases: `task218_ann2369, task238_ann2389, gt75_task533, ordinary_compatible`
- Full multi-case bucket audit complete: `False`
- C4 overstrong risk: `False`
- Accepted: `False`
- Downstream recommendation: `False`

## Bucket selections: task218_ann3741

- `best_manhattan_feasible`: `m1528_candidate_0017` / `mixed` / accepted=`False`
- `best_height_consistent`: `m1528_candidate_0017` / `height_consistency` / accepted=`False`
- `best_short_wall_preserving`: `m1528_candidate_0001` / `layout_plausibility` / accepted=`False`
- `best_low_movement`: `m1528_candidate_0070` / `movement_cost` / accepted=`False`
- `best_hohonet_consistent`: `m1528_candidate_0007` / `c4_evidence` / accepted=`False`
- `best_balanced`: `m1528_candidate_0017` / `mixed` / accepted=`False`

## Evidence-only cases

- `task218_ann2369`: `unavailable_for_active_hrc_bucket_audit`; reason=`case-specific HRC expert_assertion/candidate_set is not available to the active runner`; accepted=false; downstream=false
- `task238_ann2389`: `unavailable_for_active_hrc_bucket_audit`; reason=`case-specific HRC expert_assertion/candidate_set is not available to the active runner`; accepted=false; downstream=false
- `gt75_task533`: `unavailable_for_active_hrc_bucket_audit`; reason=`no HRC projection artifact and active HRC candidate_set are available for this verified-order record`; accepted=false; downstream=false
- `ordinary_compatible`: `unavailable_for_active_hrc_bucket_audit`; reason=`fixture has no active HRC projection artifact and candidate_set`; accepted=false; downstream=false
