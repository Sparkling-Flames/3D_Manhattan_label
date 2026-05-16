# VIS 3D Geometry Fixture Plan v1

> Status: synthetic fixture design only.
>
> Scope: documentation only. This file does not modify Label Studio UI, userscript behavior, `vis_3d.html`, `ls_3d_logic.js`, import/export files, routing artifacts, formal `g_t`, or any `P1 / C1 / C2 / T1 / V1` schema.
>
> Parent spec: `docs/VIS_3D_GEOMETRY_COMPATIBILITY_SPEC_v1.md`.

## 1. Purpose

This plan defines synthetic layout fixtures for future deterministic realtime Manhattan assistant tests. The fixtures are only for experiment-outside expert-side / lab-side prototype validation. They must not enter the current worker-facing experiment, must not create a new `Semi-Auto + Geometry Guidance` condition, and must not be interpreted as correctness labels.

All pixel expectations below assume:

- `W = 1024`
- `H = 512`
- percent-to-pixel conversion: `px = x * W / 100`, `py = y * H / 100`
- current preview pairing behavior: sort keypoints by pixel `x`, then apply greedy nearest-x ceiling/floor pairing using `threshold = W * 0.05 = 51.2 px`

The assistant may only emit an adjustment suggestion when the fixture is compatible with current 3D preview semantics. For compatibility failures, it must emit the failure status and withhold adjustment suggestions.

## 2. Fixture Schema

Each fixture should record:

- `fixture_id`
- `input_keypoints_percent`
- `expected_pixel_points`
- `expected_pairing_behavior`
- `expected_corner_order`
- `expected_compatibility_status`
- `adjustment_suggestion_allowed`
- `allowed_adjustment_type`

Allowed compatibility statuses:

- `compatible`
- `compatibility_failure_odd_keypoint`
- `compatibility_failure_duplicate`
- `compatibility_failure_wrong_order`
- `compatibility_failure_wraparound_unresolved`

Allowed adjustment types:

- `snap_to_axis`
- `vertical_pair_align`
- `duplicate_merge_candidate`
- `closure_check_only`
- `none`

## 3. Synthetic Fixtures

### 3.1 `clean_axis_aligned_rectangle`

Purpose: baseline compatible rectangle with four vertical ceiling/floor pairs.

`input_keypoints_percent`:

| point_id | x | y | role |
|---|---:|---:|---|
| p1 | 20.0 | 25.0 | ceiling |
| p2 | 20.0 | 78.0 | floor |
| p3 | 40.0 | 22.0 | ceiling |
| p4 | 40.0 | 80.0 | floor |
| p5 | 60.0 | 22.0 | ceiling |
| p6 | 60.0 | 80.0 | floor |
| p7 | 80.0 | 25.0 | ceiling |
| p8 | 80.0 | 78.0 | floor |

`expected_pixel_points`:

| point_id | px | py |
|---|---:|---:|
| p1 | 204.8 | 128.0 |
| p2 | 204.8 | 399.36 |
| p3 | 409.6 | 112.64 |
| p4 | 409.6 | 409.6 |
| p5 | 614.4 | 112.64 |
| p6 | 614.4 | 409.6 |
| p7 | 819.2 | 128.0 |
| p8 | 819.2 | 399.36 |

Expected outcomes:

- `expected_pairing_behavior`: four exact same-x pairs: `(p1,p2)`, `(p3,p4)`, `(p5,p6)`, `(p7,p8)`.
- `expected_corner_order`: x-ascending corner order at `x = [204.8, 409.6, 614.4, 819.2]`.
- `expected_compatibility_status`: `compatible`.
- `adjustment_suggestion_allowed`: `true`.
- `allowed_adjustment_type`: `closure_check_only`, with optional later `snap_to_axis` if the deterministic assistant can prove the same ordered corner list and current preview geometry.

### 3.2 `wraparound_seam_unresolved`

Purpose: seam-adjacent layout where the current x-sort order may not match the intended room order.

`input_keypoints_percent`:

| point_id | x | y | role |
|---|---:|---:|---|
| p1 | 2.0 | 26.0 | ceiling |
| p2 | 2.0 | 79.0 | floor |
| p3 | 18.0 | 23.0 | ceiling |
| p4 | 18.0 | 81.0 | floor |
| p5 | 82.0 | 23.0 | ceiling |
| p6 | 82.0 | 81.0 | floor |
| p7 | 98.0 | 26.0 | ceiling |
| p8 | 98.0 | 79.0 | floor |

`expected_pixel_points`:

| point_id | px | py |
|---|---:|---:|
| p1 | 20.48 | 133.12 |
| p2 | 20.48 | 404.48 |
| p3 | 184.32 | 117.76 |
| p4 | 184.32 | 414.72 |
| p5 | 839.68 | 117.76 |
| p6 | 839.68 | 414.72 |
| p7 | 1003.52 | 133.12 |
| p8 | 1003.52 | 404.48 |

Expected outcomes:

- `expected_pairing_behavior`: four same-x pairs are individually recoverable, but seam intent is unresolved after x-ascending order.
- `expected_corner_order`: current preview x-sort order would be `[2%, 18%, 82%, 98%]`; intended room order may require wraparound reasoning.
- `expected_compatibility_status`: `compatibility_failure_wraparound_unresolved`.
- `adjustment_suggestion_allowed`: `false`.
- `allowed_adjustment_type`: `none`.

### 3.3 `near_duplicate_corner`

Purpose: duplicate / near-duplicate vertical pairs that could create unstable wall geometry.

`input_keypoints_percent`:

| point_id | x | y | role |
|---|---:|---:|---|
| p1 | 20.0 | 25.0 | ceiling |
| p2 | 20.0 | 78.0 | floor |
| p3 | 40.0 | 22.0 | ceiling |
| p4 | 40.0 | 80.0 | floor |
| p5 | 40.3 | 22.2 | ceiling |
| p6 | 40.3 | 79.8 | floor |
| p7 | 80.0 | 25.0 | ceiling |
| p8 | 80.0 | 78.0 | floor |

`expected_pixel_points`:

| point_id | px | py |
|---|---:|---:|
| p1 | 204.8 | 128.0 |
| p2 | 204.8 | 399.36 |
| p3 | 409.6 | 112.64 |
| p4 | 409.6 | 409.6 |
| p5 | 412.672 | 113.664 |
| p6 | 412.672 | 408.576 |
| p7 | 819.2 | 128.0 |
| p8 | 819.2 | 399.36 |

Expected outcomes:

- `expected_pairing_behavior`: current greedy nearest-x pairing can form four vertical pairs, but two adjacent corners are near duplicates at `x = 409.6` and `x = 412.672`.
- `expected_corner_order`: x-ascending order would include adjacent near-duplicate corners: `[204.8, 409.6, 412.672, 819.2]`.
- `expected_compatibility_status`: `compatibility_failure_duplicate`.
- `adjustment_suggestion_allowed`: `false` for automatic geometry adjustment.
- `allowed_adjustment_type`: `none`. `duplicate_merge_candidate` is reserved for a future diagnostic-only message after a separate compatibility rule is specified; it is not an allowed adjustment suggestion in this failure fixture.

### 3.4 `odd_keypoint_count`

Purpose: odd number of keypoints leaves one point unpaired under current preview assumptions.

`input_keypoints_percent`:

| point_id | x | y | role |
|---|---:|---:|---|
| p1 | 20.0 | 25.0 | ceiling |
| p2 | 20.0 | 78.0 | floor |
| p3 | 40.0 | 22.0 | ceiling |
| p4 | 40.0 | 80.0 | floor |
| p5 | 60.0 | 22.0 | ceiling |
| p6 | 60.0 | 80.0 | floor |
| p7 | 80.0 | 25.0 | ceiling |

`expected_pixel_points`:

| point_id | px | py |
|---|---:|---:|
| p1 | 204.8 | 128.0 |
| p2 | 204.8 | 399.36 |
| p3 | 409.6 | 112.64 |
| p4 | 409.6 | 409.6 |
| p5 | 614.4 | 112.64 |
| p6 | 614.4 | 409.6 |
| p7 | 819.2 | 128.0 |

Expected outcomes:

- `expected_pairing_behavior`: three pairs can be formed and one keypoint remains unpaired.
- `expected_corner_order`: incomplete; no full current-preview-compatible corner list.
- `expected_compatibility_status`: `compatibility_failure_odd_keypoint`.
- `adjustment_suggestion_allowed`: `false`.
- `allowed_adjustment_type`: `none`.

### 3.5 `wrong_order_self_intersecting`

Purpose: same number of paired corners as a valid layout, but preserve-order semantics would create a crossing / wrong-order polygon.

`input_keypoints_percent`:

| point_id | x | y | role |
|---|---:|---:|---|
| p1 | 20.0 | 25.0 | ceiling |
| p2 | 20.0 | 78.0 | floor |
| p3 | 80.0 | 25.0 | ceiling |
| p4 | 80.0 | 78.0 | floor |
| p5 | 40.0 | 22.0 | ceiling |
| p6 | 40.0 | 80.0 | floor |
| p7 | 60.0 | 22.0 | ceiling |
| p8 | 60.0 | 80.0 | floor |

`expected_pixel_points`:

| point_id | px | py |
|---|---:|---:|
| p1 | 204.8 | 128.0 |
| p2 | 204.8 | 399.36 |
| p3 | 819.2 | 128.0 |
| p4 | 819.2 | 399.36 |
| p5 | 409.6 | 112.64 |
| p6 | 409.6 | 409.6 |
| p7 | 614.4 | 112.64 |
| p8 | 614.4 | 409.6 |

Expected outcomes:

- `expected_pairing_behavior`: four same-x pairs are recoverable.
- `expected_corner_order`: if `preserveOrder=true`, the pair order is `[20%, 80%, 40%, 60%]`, which is incompatible with the x-sorted current-preview geometry and may self-intersect. If current preview ignores preserve order, x-sort would produce `[20%, 40%, 60%, 80%]`; this mismatch must be treated as a compatibility issue for assistant suggestions.
- `expected_compatibility_status`: `compatibility_failure_wrong_order`.
- `adjustment_suggestion_allowed`: `false`.
- `allowed_adjustment_type`: `none`.

## 4. Fixture Use Rules

- Fixtures are synthetic only and must not be copied from real worker export.
- These fixtures may become future unit-test inputs for deterministic compatibility checks, but this document itself does not add executable tests.
- A compatible fixture may allow a preview-only suggestion, but never an automatic annotation overwrite.
- A compatibility failure must suppress adjustment suggestions unless a future spec separately defines an explicit diagnostic-only message such as `duplicate_merge_candidate`.
- Fixture results must not feed current experiment routing, formal `g_t`, worker tiering, admission, `w_max`, `tau_d`, Score, stop rules, or any Validation routing contract.
- Fixture results must not be written back to Label Studio export or shown in the current worker-facing experiment.
