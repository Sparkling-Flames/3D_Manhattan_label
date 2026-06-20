# M15.27 Semantic Direct Search v1 — task218_ann3741

**Manual-review candidate available: `True`.**
**Automatic fix claimed: `False`.**
**Best candidate requires visual review: `True`.**

## Semantic levers

- `x` → azimuth / column lever
- `top_y` → wall-height / ceiling-height lever
- `bottom_y` → floor-depth / radial-distance lever

## Dominant projected-height cluster

- h*: `2.993707`
- Members: `[5, 6, 7, 8]`
- MAD: `0.088306`
- Outliers: `[1, 2]`

## Top candidates

| candidate | action family | decision | primary 6-7 | changed pairs | local gate | direct trial |
|---|---|---|---:|---|---|---|
| m1527_candidate_0094 | mixed_x_bottom_y_pattern | candidate_for_manual_review | 14.170745 | [5, 6, 7] | True | True |
| m1527_candidate_0086 | floor_depth_balance_bottom_y | candidate_for_manual_review | 14.395745 | [5, 6, 7] | True | True |
| m1527_candidate_0095 | mixed_x_bottom_y_pattern | partial_diagnostic | 12.773404 | [5, 6, 7] | True | False |
| m1527_candidate_0092 | azimuth_block_shift_x | partial_diagnostic | 15.323063 | [5, 6, 7] | True | False |
| m1527_candidate_0087 | azimuth_pair_shift_x | partial_diagnostic | 15.362056 | [5, 6, 7] | True | False |

## Search trace

| round | step | exploratory | mixed | pattern | accepted | family | reason |
|---:|---:|---:|---|---|---|---|---|
| 1 | 1.0 | 22 | False | True | m1527_candidate_0023 | azimuth_pair_shift_x | accepted_local_gate_move |
| 2 | 0.5 | 23 | True | True | m1527_candidate_0047 | mixed_x_bottom_y_pattern | accepted_local_gate_move |
| 3 | 0.25 | 23 | True | True | m1527_candidate_0070 | mixed_x_bottom_y_pattern | accepted_local_gate_move |
| 4 | 0.125 | 23 | True | True | m1527_candidate_0094 | mixed_x_bottom_y_pattern | accepted_local_gate_move |

## M15.26 comparison

- M15.26 best primary residual: `15.616643467002177`
- M15.27 best primary residual: `14.170744905397669`
- Better on primary edge: `True`
- Still partial: `False`

## Safety boundary

Expert-side, offline-local, deterministic dry-run only. No annotation mutation, patch generation, automatic application, worker-facing behavior, routing input, or formal artifact is produced.
