# M15.25 Visual Verdict Pack — task218_ann3741

**No direct candidate fix is available.**

## Expert verdict

- candidate_2 is the largest perturbation but still inadequate; it remains a partial diagnostic, not a direct fix.
- Y-height inconsistency remains unresolved for pairs `[1, 2, 5, 6, 7, 8]`.
- Wall-surface / footprint problems remain around `2-3` and `5-6-7-8`.
- Primary edge `6-7` remains unresolved.
- candidate_5 is local x alignment only; it does not resolve `6-7`.
- No candidate may be applied directly in Label Studio.

## Per-candidate visual verdict

- **candidate_1:** `partial_diagnostic_only` — Insufficient; y-height and local wall-surface problems remain.
- **candidate_2:** `largest_visible_perturbation_but_still_inadequate` — Largest visible change, but it does not solve the root geometry.
- **candidate_3:** `partial_diagnostic_only` — Insufficient; no root wall-surface or y-height resolution.
- **candidate_4:** `partial_diagnostic_only` — Insufficient; no root wall-surface or y-height resolution.
- **candidate_5:** `local_x_alignment_only` — Improves local 5-6 residual but does not resolve primary edge 6-7.

## Algorithm gap

The current candidate families cover local x/y perturbations and limited joint search, but do not model the wall-surface, y-height, and footprint consistency needed for this case.

## Recommended sequence

1. Build `m15_23_5_multi_candidate_compare_grid` for clearer cross-candidate visual comparison.
2. After this verdict is archived, consider `m15_26_primary_edge_constrained_wall_surface_probe`.

## Source artifacts

- candidate_search: `analysis_results/paper_a_manhattan/local_candidate_search/task218_ann3741/candidate_search.json` — `daf2d0d57fb4f230e8f5764170f62bc569687b8221a0494a14075f86b8f94d76`
- projection_metrics: `analysis_results/paper_a_manhattan/local_3d_projection/task218_ann3741/projection_metrics.json` — `4b2952fa2106c6f01c873254c6d8749edaf7fac994f54541801c2c619f155ffb`
- projection_review_report: `analysis_results/paper_a_manhattan/local_3d_projection/task218_ann3741/projection_review_report.md` — `512b6fa0e75b5e5e50c3b4fe6d9329db7df532b8dea04656910d24c6a25ec808`
- expert_assertion: `analysis_results/paper_a_manhattan/local_candidate_search/task218_ann3741/expert_assertion.json` — `3032b5540f6be0e744a6182343156f053df8c84e3355ee4943cab7ec3bb3e698`

## Safety boundary

Expert-side, offline, dry-run sidecar only. It produces no annotation patch, Label Studio writeback, routing input, worker-facing output, or formal artifact.
