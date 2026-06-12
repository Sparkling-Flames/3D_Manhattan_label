# Verified 3D Local Assist Open Spec v1

This spec defines the M15.14/M15.15a verified 3D local assist harness for the
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

Candidate rows for `translate_pair_cluster_x_dryrun` include:

- `candidate_id`
- `operation`
- `target_pair_indices`
- `dx`
- `status`: `eligible`, `review_only`, or `suppress`
- `before_metrics`
- `after_metrics`
- `improved_metrics`
- `risk_reasons`
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

`translate_pair_cluster_x_dryrun` evaluates small local x translations such as
`[-0.5, -0.25, 0.25, 0.5]` in Label Studio percent units.

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

## Non-goals

This spec does not implement UI, ghost overlays, apply/undo, Label Studio
integration, y-coordinate height reproject candidates, local Manhattan snap,
wall moves, room-height sliders, automatic reorder, automatic merge, automatic
corner deletion, correctness labels, GT decisions, routing, worker profile
signals, or formal A-line artifacts.
