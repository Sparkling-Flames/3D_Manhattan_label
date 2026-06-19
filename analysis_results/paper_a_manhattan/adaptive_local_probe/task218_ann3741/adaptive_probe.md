# M15.26 Primary-Edge-Constrained Wall-Surface-Aware Adaptive Probe

## Baseline problem summary from M15.25

- No direct candidate fix was available in the archived visual verdict.
- Pairs 1/2/5/6/7/8 retain y-height inconsistency.
- Wall-surface / footprint problems remain at 2-3 and 5-6-7-8.
- Primary edge 6-7 remains unresolved.

## Search scope

- Movable variables: `[{'pair_index': 1, 'field': 'top_y'}, {'pair_index': 1, 'field': 'bottom_y'}, {'pair_index': 2, 'field': 'top_y'}, {'pair_index': 2, 'field': 'bottom_y'}, {'pair_index': 5, 'field': 'top_y'}, {'pair_index': 5, 'field': 'bottom_y'}, {'pair_index': 6, 'field': 'top_y'}, {'pair_index': 6, 'field': 'bottom_y'}, {'pair_index': 7, 'field': 'top_y'}, {'pair_index': 7, 'field': 'bottom_y'}, {'pair_index': 5, 'field': 'x'}, {'pair_index': 6, 'field': 'x'}, {'pair_index': 7, 'field': 'x'}]`
- Fixed anchors: `[4, 8]`
- Score-only frozen pairs: `[8]`
- No order mutation, merge/delete, auto reorder, or topology rewrite.

## Score components

- `primary_edge_6_7_residual` baseline: `35.367792295442314`
- `wall_2_3_surface_or_heading_residual` baseline: `37.02045729278922`
- `wall_5_6_7_8_footprint_residual` baseline: `47.97524026821071`
- `y_height_consistency_residual_pairs_1_2_5_6_7_8` baseline: `1.8914606548441415`
- `short_wall_penalty` baseline: `46.02326316635087`
- `movement_penalty` baseline: `0.0`
- `movement_l1_ls_percent` baseline: `0.0`
- `anchor_violation_penalty` baseline: `0.0`
- `assertion_violation_penalty` baseline: `0.0`
- `fold_or_self_intersection_penalty` baseline: `0.0`
- `local_score_total` baseline: `309.9149651039561`

## Best candidate

- Candidate: `m1526_candidate_0301`
- Decision: `partial_diagnostic`
- Direct LS trial allowed: `False`
- Local score: `212.019310`
- Primary edge 6-7: `35.367792` → `15.616643`
- Failed direct-trial checks: `['primary_edge_resolved_under_15_deg', 'short_wall_not_seriously_worsened']`

**Overall verdict: `no_direct_fix_available`; direct_fix_available = `False`.**

## Top 5 candidates

| candidate | decision | score | primary 6-7 | movement | assertion compliant | direct LS trial |
|---|---|---:|---:|---:|---|---|
| m1526_candidate_0301 | partial_diagnostic | 212.019310 | 15.616643 | 1.875000 | True | False |
| m1526_candidate_0306 | partial_diagnostic | 212.564885 | 15.681829 | 1.875000 | True | False |
| m1526_candidate_0327 | partial_diagnostic | 212.948008 | 15.748615 | 1.875000 | True | False |
| m1526_candidate_0332 | partial_diagnostic | 213.343826 | 15.817052 | 1.875000 | True | False |
| m1526_candidate_0353 | partial_diagnostic | 213.678885 | 15.887192 | 1.875000 | True | False |

## Search trace

| round | step | generated | retained | best | score | primary before | primary after | stop reason |
|---:|---:|---:|---:|---|---:|---:|---:|---|
| 1 | 1.0 | 26 | 5 | m1526_candidate_0015 | 260.075248 | 35.367792 | 25.029781 | improved_continue_with_smaller_step |
| 2 | 0.5 | 130 | 5 | m1526_candidate_0041 | 232.856545 | 35.367792 | 19.660347 | improved_continue_with_smaller_step |
| 3 | 0.25 | 130 | 5 | m1526_candidate_0171 | 218.901698 | 35.367792 | 16.963237 | improved_continue_with_smaller_step |
| 4 | 0.125 | 130 | 5 | m1526_candidate_0301 | 212.019310 | 35.367792 | 15.616643 | step_schedule_exhausted |

## Safety boundary

Expert-side, offline, deterministic dry-run only. No annotation patch, Label Studio writeback, automatic apply, global optimization, worker-facing output, routing input, or formal artifact is produced.
