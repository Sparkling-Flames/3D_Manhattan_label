# Verified 3D Local Assist Open Spec v1

This spec defines the M15.14/M15.15 verified 3D local assist harness for the
Paper A Manhattan experiment-outside toolchain.

## Scope

The harness is expert-side, button-triggered in concept, and no-writeback. It
is designed for offline review sidecars after an expert has verified the preview
order for a difficult single image.

It is not a Label Studio UI, not a plugin, not an annotation writeback path, not
formal `g_t`, not routing, not a worker-quality signal, and not a
P1/C1/C2/T1/V1 artifact.

## Inputs

- `ordered_pairs`: effective ordered top/bottom corner pairs in Label Studio
  0-100 percent coordinates.
- `metadata`: optional scope/Manhattan metadata consumed by the existing
  `RoomLayoutState` diagnostics.
- `topology_override`: optional provenance from the single-image CLI. Local x
  translation dry-run candidates require `order_verified_by_expert=true` and
  `preview_order_override_active=true`.
- `target_pair_indices`: optional explicit pair indices for local dry-run
  evaluation. These are review targets only and do not imply correctness.

## Output

The CLI and helper expose a `verified_3d_local_assist` object with:

- `schema_version`
- `operation_family`
- `before_metrics`
- `local_3d_diagnostics`
- `dense_corner_reclassification`
- `candidate_rows`
- `risk_reasons`
- `writeback_allowed=false`
- `ui_allowed=false`

Candidate rows for local x dry-runs include:

- `candidate_id`
- `operation`
- `candidate_family`
- `candidate_rank`
- `target_pair_indices`
- `dx`
- `status`: compatibility alias for the review decision
- `candidate_decision`: `suggested_review`, `neutral_review`, or `suppress`
- `before_metrics`
- `after_metrics`
- `improved_metrics`
- `before_local_geometry_metrics`
- `after_local_geometry_metrics`
- `geometry_metric_deltas`
- `local_geometry_score_before`
- `local_geometry_score_after`
- `local_geometry_score_delta`
- `before_local_wall_angle_summary`
- `after_local_wall_angle_summary`
- `wall_angle_residual_sum_delta_deg`
- `wall_angle_residual_max_delta_deg`
- `affected_wall_indices`
- `affected_corner_indices`
- `x_order_crossing_after_translation`
- `crossed_pair_indices`
- `crossing_scope=2d_x_only_not_topology`
- `decision_reasons`
- `risk_reasons`
- `expert_action_allowed=false`
- `y_change_allowed=false`
- `writeback_allowed=false`

## Dense Corner Reclassification

The harness first finds 2D near-duplicate corner pairs using a small `center_x`
threshold. It then reclassifies each local dense pair as:

- `true_duplicate_2d_3d`
- `dense_but_distinct_3d_corner`
- `unresolved_dense_corner`

The classification considers 2D `center_x` delta, BEV distance, floor-distance
delta, adjacent wall length, state warnings, and pair warnings. This is a
review diagnostic only. It does not decide GT, correctness, or enclosed scope.

## X-only Dry-run

The M15.15 candidate families are:

- `translate_single_pair_x_dryrun`
- `translate_pair_cluster_x_dryrun`
- `separate_dense_pair_x_dryrun`

The harness evaluates small local x translations in Label Studio percent units.
Symmetric dense-pair separation uses conservative internal `+/- dx` offsets.

The dry-run:

- changes only `top.x` and `bottom.x` internally for the target pair/cluster;
- never changes `y`;
- never changes pair order;
- never writes annotation;
- recomputes `RoomLayoutState` before/after metrics;
- suppresses risky candidates if state status worsens, seam warnings appear,
  `top_not_above_bottom` appears, or movement is too large.

The candidate rows intentionally do not include writeback payloads or annotation
patches.

## Local Geometry Scoring

M15.15b adds local 3D/BEV geometry scoring for each candidate. Metrics include:

- `local_manhattan_angle_residual_sum`
- `local_manhattan_angle_residual_max`
- `local_wall_length_min`
- `local_wall_length_ratio`
- `local_wall_length_change_max`
- `local_fold_or_self_intersection`
- `dense_pair_bev_distance`
- `dense_pair_floor_distance_delta`
- `movement_abs_max`
- `movement_penalty`
- `local_geometry_score`

The local scope is the target pair or cluster and adjacent wall segments. Angle
residual is measured against the nearest Manhattan direction (`k*pi/2`) in BEV.
Lower `local_geometry_score` means a more stable dry-run geometry under this
heuristic. It is a plausibility/stability score only, not correctness.

## Candidate Ranking

M15.15c ranks candidates by `candidate_decision`, then by
`local_geometry_score_delta`.

- `suggested_review`: local geometry score decreases and no blocking risk is
  present.
- `neutral_review`: no clear improvement and no blocking risk is present.
- `suppress`: state worsens, seam/top-bottom/self-intersection risk appears,
  a local wall becomes too short, movement is too large, or local wall length
  changes too much.

`candidate_decision` is not apply permission. It is a review-level sorting cue.
The current harness still does not generate y candidates, annotation patches, or
writeback payloads.

## M15.15d Angle and Order Provenance Diagnostics

M15.15d adds explainability fields for expert-side review:

- `pair_index_mapping`: maps each effective report pair index to its
  `source_preview_order_index`. Candidate `target_pair_indices` always refer to
  effective pair indices, not original Label Studio order or GT identity.
- `wall_angle_table`: per-wall direction, nearest Manhattan axis, angle
  residual, length, and source-order provenance for both endpoints.
- `corner_angle_table`: per-corner BEV turn angle, residual from 90 degrees,
  and local angle warning.

Angle diagnostics are plausibility and explainability signals only. They are not
correctness labels, GT decisions, formal `g_t`, routing signals, worker-quality
metrics, or P1/C1/C2/T1/V1 artifacts.

Candidate rows also report local before/after wall-angle summaries for the
affected wall/corner neighborhood. These fields explain why a dry-run may look
more or less stable, but they do not authorize any edit.

`x_order_crossing_after_translation` flags a 2D x-order crossing that would
occur after the dry-run translation. This warning does not rewrite topology,
does not change pair order, and does not by itself imply suppression when an
expert-verified preview order is active. It remains a manual review cue.

## Non-goals

This spec does not implement UI, ghost overlays, apply/undo, Label Studio
integration, y-coordinate height reproject candidates, local Manhattan snap,
wall moves, room-height sliders, automatic reorder, automatic merge, automatic
corner deletion, correctness labels, GT decisions, routing, worker profile
signals, or formal A-line artifacts.
