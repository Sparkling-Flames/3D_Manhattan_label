# M15.24 Hard-case Audit Pack

> Expert-side aggregate only: no writeback, annotation patch, routing, formal artifact, or correctness-oracle role.

## Summary

| case | category | status | generated | retained | joint | direct fix | best executable | best joint |
|---|---|---|---:|---:|---:|---|---|---|
| task218_ann3741 | dense_corner_topology_instability | applicable | 54 | 21 | 12 | False | candidate_1 | candidate_2 |
| task218_ann2369 | joint_search_smoke_applicable | applicable | 54 | 21 | 12 | False | candidate_1 | candidate_1 |
| task238_ann2389 | ineligible_safe_skip | ineligible_safe_skip | 0 | 0 | 0 | False | — | — |

## task218_ann3741

- Category: `dense_corner_topology_instability`
- Best executable: `candidate_1` / `height_aware_y_probe` / `partial_diagnostic`
- Best joint: `candidate_2` / `joint_5_6_7_dense_footprint` / `partial_diagnostic`
- Direct fix available: `False`
- Primary unresolved edges: `['6-7']`
- Persistent short-wall edges: `['5-6', '6-7']`
- Why diagnostic only: retained candidates still obey assertion and geometry gates; no aggregate row authorizes direct repair.

## task218_ann2369

- Category: `joint_search_smoke_applicable`
- Best executable: `candidate_1` / `joint_6_7_y_depth_balance` / `candidate_for_manual_review`
- Best joint: `candidate_1` / `joint_6_7_y_depth_balance` / `candidate_for_manual_review`
- Direct fix available: `False`
- Primary unresolved edges: `[]`
- Persistent short-wall edges: `[]`
- Why diagnostic only: retained candidates still obey assertion and geometry gates; no aggregate row authorizes direct repair.

## task238_ann2389

- Applicability: `ineligible_safe_skip`
- Safe-skip reason: M15.22 joint families require pairs 5/6/7/8; available pair count is 6 and assertion window is [2, 3, 4, 5].

## Interpretation boundary

- Expert-side only.
- No Label Studio writeback or annotation patch.
- No routing or formal artifact role.
- Not a correctness oracle.
