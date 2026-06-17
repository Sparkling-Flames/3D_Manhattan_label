# Local Floor-Footprint & Dense-Corner Probe Spec v1

Status: M15.18.2 expert-side diagnostic sidecar.

Scope: Paper A Manhattan experiment-outside / offline / dry-run only.

This spec defines bottom-y floor-footprint sensitivity rows and local
dense-corner hypothesis rows. The rows are geometry review evidence only. They
are not correctness, GT, routing, worker quality, formal `g_t`, or
P1/C1/C2/T1/V1 artifacts.

## Floor-Footprint Sensitivity

For every effective ordered pair, the probe evaluates fixed bottom-y offsets
`[-3, -2, -1, +1, +2, +3]` in Label Studio percent coordinates. Each dry-run:

- changes only the target pair's `bottom.y`;
- leaves x, `top.y`, and pair order unchanged;
- rebuilds `RoomLayoutState`;
- reports affected wall/corner angle residuals, target height residual,
  self-intersection, state warnings, and x-order crossing;
- emits `schema_version = "floorprint_sensitivity_m15_18_v1"`.

The `decision_label` values `improves`, `worsens`, `neutral`, and `suppress`
describe diagnostic residual movement under a fixed perturbation. They are not
edit instructions and do not identify a correct corner.

## Local Dense-Corner Hypothesis Probe

The local hypothesis probe runs only when dense-corner reclassification emits
`unresolved_dense_corner`. It evaluates a local window around the dense pair
and emits the following hypothesis rows:

1. `keep_local_order`
2. `local_dense_pair_order_flip`
3. `allow_short_wall_between_dense_pair`
4. `keep_order_with_bottom_xy_micro_probe`
5. `short_wall_with_bottom_xy_micro_probe`
6. `keep_order_with_column_floor_probe`

Micro probes use fixed grids:

- `bottom_x_delta = [-0.50, -0.25, 0, +0.25, +0.50]`
- `bottom_y_delta = [-3, -2, -1, 0, +1, +2, +3]`

Top y remains unchanged. There is no free y optimization. Order variants are
evaluated in temporary sidecar state only; the official `ordered_pairs` are not
changed. Topology variants cannot receive a directional recommendation.

## M15.18.2 Candidate Policy

Bottom-only hypotheses are legacy sensitivity evidence. They use
`confidence_label=sensitivity_only`, include `not_editable_bottom_only`, and
set `recommendation_eligible=false`. They must not be used to edit Label Studio
points.

A directional row must use `probe_mode=column_constrained`. For each target
pair, column-constrained movement applies:

- `top_x += dx`
- `bottom_x += dx`
- `bottom_y += dy_floor`
- `top_y` remains unchanged

The row exposes equal `top_x_delta` and `bottom_x_delta`,
`pair_vertical_x_consistent=true`, and `column_x_changed=true`. A nominal
column probe with `dx=0` and only bottom-y movement is still sensitivity-only.
If unchanged top-y worsens the local height residual beyond the conservative
tolerance, the row is suppressed rather than recommended.

The dense-separation gate is applied to center-x and BEV distance. For each
metric, the after-candidate separation must be at least
`min(before_separation, threshold)`. Current thresholds are `1.0` Label Studio
percent for center-x and `0.3` geometry units for BEV. A candidate that further
compresses an already-dense pair is suppressed. Directional rows require
`dense_separation_gate_passed=true`.

Rows use `schema_version = "local_dense_corner_probe_m15_18_2_v1"` and expose
wall-angle, corner-angle, height-residual, short-wall, self-intersection,
x-order crossing, score, confidence, decision, and risk summaries. The local
geometry score is a plausibility/stability heuristic only, not correctness or
GT.

When a topology variant has a substantially lower score, its row remains
`neutral_review`. `decision_reasons` explicitly record that the score improved,
that the topology variant is manual-review-only, that the score is plausibility
rather than correctness, and that automatic topology change is forbidden.

Hard gates include non-finite movement, top not above bottom,
self-intersection, severe short wall, worsened state status/warnings, and
movement outside the fixed grid bounds. If no hypothesis improves clearly,
the probe still emits `no_improvement`, `neutral_review`, or `suppressed` rows.

## Permission Contract

Every M15.18 row contains:

- `writeback_allowed=false`
- `expert_action_allowed=false`
- `annotation_patch_allowed=false`

The parent `verified_3d_local_assist` JSON object exposes both sidecar contracts
independently of its legacy harness schema:

- `floorprint_sensitivity_schema_version = "floorprint_sensitivity_m15_18_v1"`
- `local_dense_corner_probe_schema_version = "local_dense_corner_probe_m15_18_2_v1"`

Markdown reports print both schema versions and all three permission flags in
the section preamble and row tables.

The implementation does not provide UI, plugin integration, ghost overlays,
apply/undo, annotation patches, writeback payloads, automatic reorder,
automatic merge/delete, routing, or formal artifacts.
