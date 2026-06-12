# Conservative Height Reproject Candidate Spec v1

Status: M15.16 conservative review harness.

Scope: Paper A Manhattan experiment-outside / expert-side assist prototype.

This spec defines a conservative `fixed_bottom_top_y_reproject` dry-run row for
single-image Manhattan review. It is not a Label Studio UI, not writeback, not
an annotation patch, not correctness/GT, not routing, not worker quality, and
not a P1/C1/C2/T1/V1 artifact.

## Operation

`fixed_bottom_top_y_reproject` keeps:

- `bottom.x` unchanged;
- `bottom.y` unchanged;
- `top.x` unchanged;
- pair order unchanged.

It only computes a review-level `top.y` candidate that would move the target
pair's `ceiling_height_estimate` toward the current
`layout_height_candidate`. The row is a sidecar diagnostic for visual review,
not an edit instruction.

The implementation intentionally does not include free y optimization,
room-height sliders, wall moves, annotation patches, apply/undo, UI state, or
writeback payloads.

## Required Row Fields

Each row includes:

- `operation`
- `target_pair_index`
- `candidate_decision`: `suggested_review`, `neutral_review`, or `suppress`
- `decision_reasons`
- `top_y_before`, `top_y_after`, `bottom_y_before`, `bottom_y_after`
- `top_y_delta`, `bottom_y_delta`
- `height_residual_before`, `height_residual_after`,
  `height_residual_delta`
- `layout_height_candidate`
- `layout_height_spread_before`, `layout_height_spread_after`
- `max_abs_y_delta`
- `gate_status`, `gate_reasons`
- `y_change_allowed=false`
- `writeback_allowed=false`
- `expert_action_allowed=false`
- `annotation_patch_allowed=false`

The implementation may include additional provenance fields such as
`top_x_before`, `top_x_after`, `bottom_x_before`, and `bottom_x_after` to prove
that x coordinates did not change.

## Conservative Gates

The candidate is suppressed when:

- `state_status != ok`
- target pair is missing
- computed y is non-finite
- `top_y_after >= bottom_y_after`
- `abs(top_y_delta) > MAX_TOP_Y_DELTA_PERCENT`
- layout-height spread worsens severely

Current conservative harness thresholds:

- `MAX_TOP_Y_DELTA_PERCENT = 8.0`
- `MIN_HEIGHT_RESIDUAL_IMPROVEMENT = 0.05`
- `MAX_LAYOUT_HEIGHT_SPREAD_WORSENING = 0.10`

Angle regression is not directly applicable to the current fixed-bottom/top-y
operation because BEV wall/corner geometry is derived from x and floor distance;
this candidate does not change x, bottom.y, or pair order. Angle regression is
therefore treated as not applicable unless recomputed state warnings change.

`suggested_review` is only used when the target height residual drops by at
least `MIN_HEIGHT_RESIDUAL_IMPROVEMENT` and no blocking gate fires.
Small/uncertain improvement is `neutral_review`. Neither decision authorizes
editing.

## Regression Example

Task 238 / annotation 2389 is the motivating regression. Pair 4 has a height
residual of about `0.462`, while the default preview is compatible and x-only
dry-runs do not address the y/height issue.

Expected review behavior:

- pair 4 ranks first by height residual;
- pair 4 emits a conservative `fixed_bottom_top_y_reproject` row;
- the row reduces pair 4 height residual;
- x coordinates and pair order remain unchanged;
- no writeback or annotation patch is emitted;
- pairs with already-small residuals remain `neutral_review` or lower priority.

## Boundary Statement

This M15.16 candidate is review-level only. It does not alter the older
`height_reproject_applicability` rows, does not change protocol/SOP/routing,
does not create formal `g_t`, and does not change worker-facing Label Studio
behavior.
