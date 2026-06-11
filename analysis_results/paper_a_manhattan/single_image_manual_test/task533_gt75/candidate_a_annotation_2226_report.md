# Single-image Manhattan Assist Report

Expert-side diagnostic only: no UI, no apply/writeback, no routing, no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact.

## Preview Compatibility

- status: `compatible`
- input_mode: `label_studio_result`
- reason: `current_preview_pairing_and_order_compatible`
- preserve_order: `False`

## Pair Diagnostics

| pair_index | vertical_x_residual | height_residual | top_bottom_delta_y | warnings |
| --- | --- | --- | --- | --- |
| 1 | 0.000 | 0.000 | 15.627 | [] |
| 2 | 0.000 | 0.000 | 76.127 | [] |
| 3 | 0.000 | 0.000 | 10.482 | [] |
| 4 | 0.000 | 0.000 | 12.633 | [] |
| 5 | 0.000 | 0.000 | 60.656 | [] |
| 6 | 0.000 | 0.000 | 27.840 | [] |
| 7 | 0.000 | 0.000 | 57.701 | [] |
| 8 | 0.000 | 0.000 | 64.414 | [] |

## Manual Edit Table

| pair_index | action | from_top_x | to_top_x | from_bottom_x | to_bottom_x | top_dx | bottom_dx | y_change_allowed | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | manual_review_only | 0.681 |  | 0.681 |  |  |  | False | vertical_x_residual_zero |
| 2 | manual_review_only | 7.160 |  | 7.160 |  |  |  | False | vertical_x_residual_zero |
| 3 | manual_review_only | 13.473 |  | 13.473 |  |  |  | False | vertical_x_residual_zero |
| 4 | manual_review_only | 31.941 |  | 31.941 |  |  |  | False | vertical_x_residual_zero |
| 5 | manual_review_only | 40.576 |  | 40.576 |  |  |  | False | vertical_x_residual_zero |
| 6 | manual_review_only | 47.036 |  | 47.036 |  |  |  | False | vertical_x_residual_zero |
| 7 | manual_review_only | 61.430 |  | 61.430 |  |  |  | False | vertical_x_residual_zero |
| 8 | manual_review_only | 84.582 |  | 84.582 |  |  |  | False | vertical_x_residual_zero |

## Height Applicability Summary

- applicable: `8`
- review_only: `0`
- suppressed: `0`

