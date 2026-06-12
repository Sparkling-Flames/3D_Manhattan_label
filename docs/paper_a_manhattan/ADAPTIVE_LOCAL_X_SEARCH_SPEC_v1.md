# Adaptive Local X Search Spec v1

Status: M15.17 adaptive review harness.

Scope: Paper A Manhattan experiment-outside / expert-side assist prototype.

This spec defines a bounded local x-search sidecar for Manhattan assist review.
It is not a UI, not writeback, not an annotation patch, not correctness/GT, not
routing, not worker quality, and not a P1/C1/C2/T1/V1 artifact.

## Search Model

Adaptive local x search is derivative-free bounded 1D search. It is intended to
explain local directionality and score stability around a target pair or small
dense-corner cluster.

It does not use gradient descent and does not claim a global optimum. The
current search range is conservative:

- `ADAPTIVE_X_SEARCH_RANGE = [-0.75, +0.75]`
- coarse grid: `[-0.75, -0.50, -0.25, 0.0, +0.25, +0.50, +0.75]`
- fine search: `±0.20` around the best coarse dx with step `0.05`
- flat threshold: `FLAT_SCORE_EPSILON = 0.01`

## Applicable Targets

The sidecar may evaluate:

- explicit `target_pair_indices`, using `translate_single_pair_x_adaptive_search`
- dense-but-distinct 3D corner pairs, using single-pair and pair-cluster
  adaptive x search

The implementation is intentionally one-dimensional. It does not perform joint
2D dx optimization, free y optimization, automatic reorder, merge, delete,
apply, undo, or writeback.

## Row Contract

Each `adaptive_x_search_rows` entry includes:

- `search_schema_version = "adaptive_local_x_search_m15_17_v1"`
- `search_family`
- `target_pair_indices`
- `search_range`
- `coarse_grid`
- `fine_grid`
- `best_dx`
- `best_score`
- `baseline_score`
- `score_delta`
- `score_curve`
- `flat_score_region`
- `flat_score_dx_min`
- `flat_score_dx_max`
- `confidence_label`
- `decision_reasons`
- `affected_wall_indices`
- `affected_corner_indices`
- `x_order_crossing_at_best`
- `crossed_pair_indices_at_best`
- `y_change_allowed=false`
- `writeback_allowed=false`
- `expert_action_allowed=false`
- `annotation_patch_allowed=false`

Each `score_curve` point includes:

- `dx`
- `local_geometry_score`
- `wall_angle_residual_sum_deg`
- `wall_angle_residual_max_deg`
- `risk_reasons`
- `x_order_crossing_after_translation`

## Confidence Labels

`directional` means the best searched score is clearly lower than baseline and
no blocking risk is present.

`flat_uncertain` means there is some improvement, but multiple dx values near
the best score are within `FLAT_SCORE_EPSILON`. The exact dx should not be
treated as reliable; the row is only useful for rough directionality.

`no_improvement` means the best searched score is not better than baseline.
This is expected for examples where x-only movement does not address the main
issue, such as a height residual.

`suppressed` means searched points were blocked by risk gates or scoring was
unavailable.

## Risk And Boundary Rules

Adaptive search reuses the existing x-only candidate risk logic:

- state worsened
- wrap seam unresolved
- top not above bottom
- local self-intersection
- local wall too short
- local wall length change too large
- movement too large

2D x-order crossing is a warning and does not rewrite topology. It is not an
automatic suppression reason by itself.

All rows are review-level dry-runs. They do not change y, do not change pair
order, do not emit annotation patches, and do not contain writeback payloads.
Scores, angles, and confidence labels are not correctness or GT.
