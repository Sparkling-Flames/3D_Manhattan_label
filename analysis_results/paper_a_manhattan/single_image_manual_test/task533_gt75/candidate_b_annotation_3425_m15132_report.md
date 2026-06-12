# Single-image Manhattan Assist Report

Expert-side diagnostic only: no UI, no apply/writeback, no routing, no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact.
Only rows with action=align_pair_x may be used as manual x-alignment references. Do not edit y from this report.

## Preview Compatibility

- status: `compatibility_failure_duplicate`
- input_mode: `label_studio_result`
- reason: `near_duplicate_corner_pair`
- preserve_order: `False`

## Topology Override

| preview_order_override_active | topology_source | default_preview_status | default_preview_reason | preview_order_override | order_override_note |
| --- | --- | --- | --- | --- | --- |
| True | expert_verified_preview_order | compatibility_failure_duplicate | near_duplicate_corner_pair | [3, 1, 4, 2, 5, 6, 8, 7, 9, 10] | Manual preview order selected in 3D preview because default order folds near dense/occluded corners. |

## Pair Diagnostics

| pair_index | vertical_x_residual | height_residual | top_bottom_delta_y | warnings |
| --- | --- | --- | --- | --- |
| 1 | 0.000 | 0.000 | 76.127 | [] |
| 2 | 0.000 | 0.026 | 48.655 | [] |
| 3 | 0.000 | 0.065 | 41.818 | [] |
| 4 | 0.000 | 0.120 | 16.227 | [] |
| 5 | 0.000 | 0.000 | 10.482 | [] |
| 6 | 0.000 | 0.000 | 12.633 | [] |
| 7 | 0.000 | 0.000 | 27.840 | [] |
| 8 | 0.000 | 0.000 | 60.656 | [] |
| 9 | 0.000 | 0.000 | 57.701 | [] |
| 10 | 0.000 | 0.000 | 64.414 | [] |

## Recommended Review Order

| rank | pair_index | review_priority | primary_action | assist_status | height_reproject_status | vertical_x_residual | height_residual | max_abs_delta | reason | manual_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.065 |  | vertical_x_residual_zero | False |
| 2 | 8 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 3 | 5 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 4 | 7 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 5 | 1 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 6 | 10 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 7 | 9 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 8 | 6 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 9 | 2 | manual_only_dense_or_order | manual_review_only | review_only | eligible | 0.000 | 0.026 |  | near_duplicate_corner_pair | True |
| 10 | 4 | manual_only_dense_or_order | manual_review_only | review_only | eligible | 0.000 | 0.120 |  | near_duplicate_corner_pair | True |

## Manual Edit Table

| pair_index | action | from_top_x | to_top_x | from_bottom_x | to_bottom_x | top_dx | bottom_dx | y_change_allowed | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | manual_review_only | 7.160 |  | 7.160 |  |  |  | False | vertical_x_residual_zero |
| 2 | manual_review_only | 3.341 |  | 3.341 |  |  |  | False | near_duplicate_corner_pair |
| 3 | manual_review_only | 10.788 |  | 10.788 |  |  |  | False | vertical_x_residual_zero |
| 4 | manual_review_only | 3.381 |  | 3.381 |  |  |  | False | near_duplicate_corner_pair |
| 5 | manual_review_only | 13.473 |  | 13.473 |  |  |  | False | vertical_x_residual_zero |
| 6 | manual_review_only | 31.941 |  | 31.941 |  |  |  | False | vertical_x_residual_zero |
| 7 | manual_review_only | 47.036 |  | 47.036 |  |  |  | False | vertical_x_residual_zero |
| 8 | manual_review_only | 40.576 |  | 40.576 |  |  |  | False | vertical_x_residual_zero |
| 9 | manual_review_only | 61.430 |  | 61.430 |  |  |  | False | vertical_x_residual_zero |
| 10 | manual_review_only | 84.582 |  | 84.582 |  |  |  | False | vertical_x_residual_zero |

## Duplicate / Dense Corner Diagnostics

| left_pair_index | right_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_only | index_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 4 | 3.341 | 3.381 | 0.040 | 1.000 | near_duplicate_corner_pair | True | expert_verified_preview_order |

## Order Diagnostics

| is_x_monotonic | n_direction_changes | direction_change_pairs | manual_only_reason |
| --- | --- | --- | --- |
| False | 5 | [{'left_pair_index': 1, 'middle_pair_index': 2, 'right_pair_index': 3, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 2, 'middle_pair_index': 3, 'right_pair_index': 4, 'from_direction': 'increasing', 'to_direction': 'decreasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 3, 'middle_pair_index': 4, 'right_pair_index': 5, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 6, 'middle_pair_index': 7, 'right_pair_index': 8, 'from_direction': 'increasing', 'to_direction': 'decreasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 7, 'middle_pair_index': 8, 'right_pair_index': 9, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}] |  |

## Height Applicability Summary

- applicable: `10`
- review_only: `0`
- suppressed: `0`

