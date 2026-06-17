# Single-image Manhattan Assist Report

Expert-side diagnostic only: no UI, no apply/writeback, no routing, no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact.
Legacy Manual Edit Table only covers align_pair_x. Verified 3D Local Assist and Conservative Height Reproject rows are review-level dry-runs, not edit instructions. Do not apply without visual confirmation.

## Preview Compatibility

- status: `compatibility_failure_duplicate`
- input_mode: `label_studio_result`
- reason: `near_duplicate_corner_pair`
- preserve_order: `False`

## Preview Pair Table

| preview_pair_index | top_id | bottom_id | top_x | bottom_x | center_x | top_y | bottom_y | pairing_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | kp_6 | kp_7 | 1.363 | 1.363 | 1.363 | 44.675 | 61.867 | default_preview_order |
| 2 | kp_4 | kp_5 | 5.990 | 6.250 | 6.120 | 16.134 | 91.231 | default_preview_order |
| 3 | kp_8 | kp_9 | 8.981 | 8.981 | 8.981 | 43.602 | 55.834 | default_preview_order |
| 4 | kp_10 | kp_11 | 27.722 | 27.722 | 27.722 | 38.568 | 60.477 | default_preview_order |
| 5 | 9Tiplq2Pvq | zGbQgzhVWW | 43.860 | 43.860 | 43.860 | 12.283 | 90.476 | default_preview_order |
| 6 | -4TzkLtjeO | 7R_vYvj4bN | 44.612 | 44.987 | 44.799 | 14.787 | 86.466 | default_preview_order |
| 7 | kp_14 | kp_15 | 50.586 | 50.586 | 50.586 | 25.911 | 76.886 | default_preview_order |
| 8 | kp_12 | kp_13 | 51.660 | 51.660 | 51.660 | 12.695 | 87.891 | default_preview_order |
| 9 | kp_0 | kp_1 | 63.869 | 64.169 | 64.019 | 32.617 | 68.359 | default_preview_order |
| 10 | kp_2 | kp_3 | 83.984 | 83.984 | 83.984 | 31.445 | 69.531 | default_preview_order |

## Near Duplicate Pair Table

| left_preview_pair_index | right_preview_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_override_required |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 6 | 43.860 | 44.799 | 0.940 | 1.000 | near_duplicate_corner_pair | True |

## Override Pack

Override pack only helps expert prepare a verified order; it is not automatic reorder.

| override_needed | hard_stop_reason | default_n_pairs | default_preview_status | default_preview_reason | accepted_override_formats | example_preview_order_override | override_validation_status | override_validation_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | near_duplicate_corner_pair | 10 | compatibility_failure_duplicate | near_duplicate_corner_pair | ['preview_order_override=[2,1,3,4]'] | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] | valid | ['order_verified_by_expert'] | False |

## Topology Override

| preview_order_override_active | topology_source | default_preview_status | default_preview_reason | preview_order_override | order_override_note | override_validation_status | override_validation_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| True | expert_verified_preview_order | compatibility_failure_duplicate | near_duplicate_corner_pair | [2, 1, 3, 4, 6, 5, 8, 7, 9, 10] |  | valid | ['order_verified_by_expert'] |

## Pair Index Mapping

Report `pair_index` values refer to the effective ordered_pairs position. `source_preview_order_index` is the original default preview pair number. Candidate `target_pair_indices` use `effective_pair_index`.

| effective_pair_index | source_preview_order_index | top_x | bottom_x | center_x | top_y | bottom_y |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 5.990 | 6.250 | 6.120 | 16.134 | 91.231 |
| 2 | 1 | 1.363 | 1.363 | 1.363 | 44.675 | 61.867 |
| 3 | 3 | 8.981 | 8.981 | 8.981 | 43.602 | 55.834 |
| 4 | 4 | 27.722 | 27.722 | 27.722 | 38.568 | 60.477 |
| 5 | 6 | 44.612 | 44.987 | 44.799 | 14.787 | 86.466 |
| 6 | 5 | 43.860 | 43.860 | 43.860 | 12.283 | 90.476 |
| 7 | 8 | 51.660 | 51.660 | 51.660 | 12.695 | 87.891 |
| 8 | 7 | 50.586 | 50.586 | 50.586 | 25.911 | 76.886 |
| 9 | 9 | 63.869 | 64.169 | 64.019 | 32.617 | 68.359 |
| 10 | 10 | 83.984 | 83.984 | 83.984 | 31.445 | 69.531 |

## Pair Diagnostics

| pair_index | vertical_x_residual | height_residual | top_bottom_delta_y | warnings |
| --- | --- | --- | --- | --- |
| 1 | 0.260 | 0.656 | 75.097 | ['height_residual_high'] |
| 2 | 0.000 | 0.779 | 17.193 | ['height_residual_high'] |
| 3 | 0.000 | 0.289 | 12.232 | [] |
| 4 | 0.000 | 0.288 | 21.908 | [] |
| 5 | 0.376 | 0.024 | 71.679 | [] |
| 6 | 0.000 | 0.255 | 78.193 | [] |
| 7 | 0.000 | 0.048 | 75.195 | [] |
| 8 | 0.000 | 0.128 | 50.976 | [] |
| 9 | 0.300 | 0.024 | 35.742 | [] |
| 10 | 0.000 | 0.028 | 38.086 | [] |

## Recommended Review Order

| rank | pair_index | review_priority | primary_action | assist_status | height_reproject_status | vertical_x_residual | height_residual | max_abs_delta | reason | manual_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 9 | align_x_first | align_pair_x | eligible | eligible | 0.300 | 0.024 | 0.150 | align_pair_x_candidate_available | False |
| 2 | 2 | diagnostic_review | manual_review_only | review_only | review_only | 0.000 | 0.779 |  | vertical_x_residual_zero | False |
| 3 | 1 | diagnostic_review | manual_review_only | review_only | review_only | 0.260 | 0.656 |  | pair_warning_height_residual_high | False |
| 4 | 3 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.289 |  | vertical_x_residual_zero | False |
| 5 | 4 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.288 |  | vertical_x_residual_zero | False |
| 6 | 8 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.128 |  | vertical_x_residual_zero | False |
| 7 | 7 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.048 |  | vertical_x_residual_zero | False |
| 8 | 10 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.028 |  | vertical_x_residual_zero | False |
| 9 | 5 | manual_only_dense_or_order | manual_review_only | eligible | eligible | 0.376 | 0.024 | 0.188 | near_duplicate_corner_pair | True |
| 10 | 6 | manual_only_dense_or_order | manual_review_only | review_only | eligible | 0.000 | 0.255 |  | near_duplicate_corner_pair | True |

## Manual Edit Table

| pair_index | action | from_top_x | to_top_x | from_bottom_x | to_bottom_x | top_dx | bottom_dx | y_change_allowed | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | manual_review_only | 5.990 |  | 6.250 |  |  |  | False | pair_warning_height_residual_high |
| 2 | manual_review_only | 1.363 |  | 1.363 |  |  |  | False | vertical_x_residual_zero |
| 3 | manual_review_only | 8.981 |  | 8.981 |  |  |  | False | vertical_x_residual_zero |
| 4 | manual_review_only | 27.722 |  | 27.722 |  |  |  | False | vertical_x_residual_zero |
| 5 | manual_review_only | 44.612 |  | 44.987 |  | 0.188 | -0.188 | False | near_duplicate_corner_pair |
| 6 | manual_review_only | 43.860 |  | 43.860 |  |  |  | False | near_duplicate_corner_pair |
| 7 | manual_review_only | 51.660 |  | 51.660 |  |  |  | False | vertical_x_residual_zero |
| 8 | manual_review_only | 50.586 |  | 50.586 |  |  |  | False | vertical_x_residual_zero |
| 9 | align_pair_x | 63.869 | 64.019 | 64.169 | 64.019 | 0.150 | -0.150 | False |  |
| 10 | manual_review_only | 83.984 |  | 83.984 |  |  |  | False | vertical_x_residual_zero |

## Duplicate / Dense Corner Diagnostics

| left_pair_index | right_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_only | index_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | 5 | 43.860 | 44.799 | 0.940 | 1.000 | near_duplicate_corner_pair | True | expert_verified_preview_order |

## Order Diagnostics

| is_x_monotonic | n_direction_changes | direction_change_pairs | manual_only_reason |
| --- | --- | --- | --- |
| False | 5 | [{'left_pair_index': 1, 'middle_pair_index': 2, 'right_pair_index': 3, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 4, 'middle_pair_index': 5, 'right_pair_index': 6, 'from_direction': 'increasing', 'to_direction': 'decreasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 5, 'middle_pair_index': 6, 'right_pair_index': 7, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 6, 'middle_pair_index': 7, 'right_pair_index': 8, 'from_direction': 'increasing', 'to_direction': 'decreasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 7, 'middle_pair_index': 8, 'right_pair_index': 9, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}] |  |

## Height Applicability Summary

- applicable: `8`
- review_only: `2`
- suppressed: `0`

## Conservative Height Reproject Candidates

| candidate_rank | target_pair_index | operation | top_y_before | top_y_after | top_y_delta | height_residual_before | height_residual_after | height_residual_delta | candidate_decision | gate_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | fixed_bottom_top_y_reproject | 44.675 | 39.018 | -5.656 | 0.779 | 0.012 | -0.767 | suggested_review | [] | False |
| 2 | 1 | fixed_bottom_top_y_reproject | 16.134 | 9.499 | -6.635 | 0.656 | 0.012 | -0.643 | suggested_review | [] | False |
| 3 | 3 | fixed_bottom_top_y_reproject | 43.602 | 44.630 | 1.028 | 0.289 | 0.012 | -0.276 | suggested_review | [] | False |
| 4 | 4 | fixed_bottom_top_y_reproject | 38.568 | 40.320 | 1.752 | 0.288 | 0.012 | -0.276 | suggested_review | [] | False |
| 5 | 6 | fixed_bottom_top_y_reproject | 12.283 | 10.309 | -1.974 | 0.255 | 0.012 | -0.243 | suggested_review | [] | False |
| 6 | 8 | fixed_bottom_top_y_reproject | 25.911 | 24.456 | -1.455 | 0.128 | 0.012 | -0.116 | suggested_review | [] | False |
| 7 | 7 | fixed_bottom_top_y_reproject | 12.695 | 13.066 | 0.371 | 0.048 | 0.012 | -0.036 | neutral_review | [] | False |
| 8 | 10 | fixed_bottom_top_y_reproject | 31.445 | 31.717 | 0.272 | 0.028 | 0.012 | -0.015 | neutral_review | [] | False |
| 9 | 5 | fixed_bottom_top_y_reproject | 14.787 | 14.574 | -0.213 | 0.024 | 0.012 | -0.012 | neutral_review | [] | False |
| 10 | 9 | fixed_bottom_top_y_reproject | 32.617 | 32.850 | 0.232 | 0.024 | 0.012 | -0.012 | neutral_review | [] | False |

## Verified 3D Local Assist

- schema_version: `verified_3d_local_assist_m15_15_v1`
- operation_family: `verified_3d_local_assist`
- state_status: `ok`
- writeback_allowed: `False`
- These candidates are review-level dry-runs, not edit instructions.
- Use them to inspect directionality; do not apply without visual confirmation.
- Existing x-only rows leave y unchanged; M15.18 changes bottom-y only inside sensitivity/hypothesis dry-runs.

### Dense Corner Reclassification

| left_pair_index | right_pair_index | delta_center_x | bev_distance | floor_distance_delta | min_adjacent_wall_length | classification | reason_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | 5 | 0.940 | 0.234 | 0.231 | 0.234 | unresolved_dense_corner | [] |

### Pair Index Mapping

See the global Pair Index Mapping table above. Inside verified 3D local assist, candidate `target_pair_indices` refer to `effective_pair_index`; source preview order is provenance only.


### Wall Angle Diagnostics

| wall_index | from_pair_index | to_pair_index | from_source_preview_order_index | to_source_preview_order_index | direction_deg | nearest_manhattan_axis_deg | angle_residual_deg | length |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 2 | 1 | -177.177 | -180.000 | 2.823 | 3.661 |
| 2 | 2 | 3 | 1 | 3 | -127.020 | -90.000 | 37.020 | 5.344 |
| 3 | 3 | 4 | 3 | 4 | 0.004 | 0.000 | 0.004 | 8.091 |
| 4 | 4 | 5 | 4 | 6 | 91.451 | 90.000 | 1.451 | 4.385 |
| 5 | 5 | 6 | 6 | 5 | 168.440 | 180.000 | 11.560 | 0.234 |
| 6 | 6 | 7 | 5 | 8 | 54.632 | 90.000 | 35.368 | 0.309 |
| 7 | 7 | 8 | 8 | 7 | -1.048 | 0.000 | 1.048 | 0.784 |
| 8 | 8 | 9 | 7 | 9 | 85.486 | 90.000 | 4.514 | 1.850 |
| 9 | 9 | 10 | 9 | 10 | 179.535 | 180.000 | 0.465 | 2.781 |
| 10 | 10 | 1 | 10 | 2 | -69.137 | -90.000 | 20.863 | 2.236 |

### Corner Angle Diagnostics

`turn_angle_deg` is the BEV angle between the previous and next wall vectors at the current corner; residual is measured from 90 degrees.

| corner_pair_index | corner_source_preview_order_index | prev_wall_index | next_wall_index | turn_angle_deg | angle_to_90_residual_deg | local_angle_warning |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 10 | 1 | 71.960 | 18.040 | turn_angle_far_from_90 |
| 2 | 1 | 1 | 2 | 129.844 | 39.844 | turn_angle_far_from_90 |
| 3 | 3 | 2 | 3 | 52.976 | 37.024 | turn_angle_far_from_90 |
| 4 | 4 | 3 | 4 | 88.553 | 1.447 |  |
| 5 | 6 | 4 | 5 | 103.011 | 13.011 |  |
| 6 | 5 | 5 | 6 | 66.192 | 23.808 | turn_angle_far_from_90 |
| 7 | 8 | 6 | 7 | 124.320 | 34.320 | turn_angle_far_from_90 |
| 8 | 7 | 7 | 8 | 93.467 | 3.467 |  |
| 9 | 9 | 8 | 9 | 85.950 | 4.050 |  |
| 10 | 10 | 9 | 10 | 68.672 | 21.328 | turn_angle_far_from_90 |

### Local X Translation Dry-run Candidates

2D x-order crossing is not topology reordering.


| candidate_rank | candidate_id | candidate_family | operation | target_pair_indices | dx | status | local_geometry_score_delta | wall_angle_residual_sum_delta_deg | wall_angle_residual_max_delta_deg | affected_wall_indices | affected_corner_indices | x_order_crossing_after_translation | crossed_pair_indices | crossing_scope | candidate_decision | decision_reasons | improved_metrics | risk_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Adaptive Local X Search

Adaptive search is a review-level bounded dry-run, not an edit instruction.
A flat region means the exact dx is not reliable; use it only as directionality.
Y coordinates remain unchanged.

| search_rank | search_family | target_pair_indices | best_dx | score_delta | confidence_label | flat_score_region | x_order_crossing_at_best | decision_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

### Floor-Footprint Sensitivity

Bottom-y changes alter the floor footprint and may change BEV wall/corner angles.
This is sensitivity analysis only, not an edit instruction.

| target_pair_index | bottom_y_delta | wall_angle_residual_sum_delta | corner_angle_residual_sum_delta | height_residual_delta | state_status_after | x_order_crossing_after_translation | decision_label | decision_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | -3.000 | -5.188 | -8.571 | -0.302 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 1 | -2.000 | -3.417 | -5.661 | -0.199 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 1 | -1.000 | -1.689 | -2.806 | -0.099 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 1 | 1.000 | 1.653 | 2.759 | 0.097 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 1 | 2.000 | 3.273 | 5.475 | 0.192 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 1 | 3.000 | 4.862 | 8.150 | 0.286 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 2 | -3.000 | -13.846 | -28.906 | -0.254 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 2 | -2.000 | -7.665 | -16.156 | -0.153 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 2 | -1.000 | -3.251 | -6.923 | -0.070 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 2 | 1.000 | 2.458 | 5.358 | 0.059 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 2 | 2.000 | 4.356 | 9.617 | 0.110 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 2 | 3.000 | 5.843 | 13.081 | 0.155 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 3 | -3.000 | 20.135 | 58.001 | 1.893 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 3 | -2.000 | 18.016 | 39.334 | 0.935 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 3 | -1.000 | 10.989 | 19.083 | 0.371 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 3 | 1.000 | -0.659 | -12.603 | -0.264 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 3 | 2.000 | -2.815 | -27.775 | -0.193 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 3 | 3.000 | -6.644 | -41.604 | -0.039 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 4 | -3.000 | 15.774 | 5.227 | 0.751 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 4 | -2.000 | 9.751 | 3.537 | 0.443 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 4 | -1.000 | 4.544 | 1.796 | 0.199 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 4 | 1.000 | 2.173 | 3.308 | -0.165 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 4 | 2.000 | 4.745 | 8.621 | -0.285 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 4 | 3.000 | 8.038 | 13.211 | -0.228 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 5 | -3.000 | 2.683 | -2.895 | 0.305 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 5 | -2.000 | 1.137 | -2.895 | 0.174 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 5 | -1.000 | 0.733 | -1.515 | 0.048 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 5 | 1.000 | -1.717 | 1.458 | 0.067 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 5 | 2.000 | -5.755 | 2.866 | 0.183 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 5 | 3.000 | -1.112 | 13.766 | 0.297 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 6 | -3.000 | -29.329 | -38.441 | -0.117 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 6 | -2.000 | -30.583 | -42.189 | -0.254 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 6 | -1.000 | -13.593 | -20.676 | -0.137 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 6 | 1.000 | 11.352 | 18.725 | 0.134 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 6 | 2.000 | 5.117 | 34.958 | 0.266 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 6 | 3.000 | -0.772 | 48.670 | 0.396 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 7 | -3.000 | 3.722 | 31.086 | 0.433 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 7 | -2.000 | 7.497 | 23.535 | 0.284 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 7 | -1.000 | 7.823 | 13.362 | 0.140 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 7 | 1.000 | -9.533 | -17.146 | -0.016 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 7 | 2.000 | -20.946 | -38.333 | 0.098 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 7 | 3.000 | -33.537 | -45.127 | 0.228 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 8 | -3.000 | -0.719 | 3.315 | -0.004 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 8 | -2.000 | -3.732 | -3.203 | -0.103 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 8 | -1.000 | -3.193 | -5.053 | -0.087 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 8 | 1.000 | 3.071 | 4.556 | 0.083 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 8 | 2.000 | 6.053 | 8.597 | 0.161 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 8 | 3.000 | 8.989 | 12.084 | 0.236 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 9 | -3.000 | 15.710 | 16.622 | 0.360 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 9 | -2.000 | 10.272 | 11.386 | 0.226 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 9 | -1.000 | 4.725 | 5.849 | 0.106 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 9 | 1.000 | -0.408 | -2.748 | 0.000 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 9 | 2.000 | 2.591 | 8.207 | 0.062 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 9 | 3.000 | 8.547 | 20.118 | 0.144 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 10 | -3.000 | 10.400 | 12.700 | 0.347 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 10 | -2.000 | 6.888 | 5.677 | 0.220 | ok | False | suppress | ['state_warnings_worsened'] | False |
| 10 | -1.000 | 3.421 | 1.514 | 0.105 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False |
| 10 | 1.000 | 0.866 | -1.582 | -0.006 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 10 | 2.000 | 2.542 | -3.238 | 0.052 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |
| 10 | 3.000 | 4.095 | -4.978 | 0.133 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False |

### Local Dense-Corner Hypothesis Probe

Only triggered for unresolved dense corners.
Hypotheses are local dry-runs.
Topology variants are not automatic reorder.
No writeback / no patch.

| hypothesis_id | topology_variant | local_window_pair_indices | bottom_xy_offsets | local_geometry_score_delta | wall_angle_residual_sum_delta | corner_angle_residual_sum_delta | confidence_label | risk_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| keep_local_order | keep_local_order | [3, 4, 5, 6, 7, 8] | {} | 0.000 | 0.000 | 0.000 | no_improvement | [] | False |
| local_dense_pair_order_flip | local_dense_pair_order_flip | [3, 4, 5, 6, 7, 8] | {} | -43.744 | -22.986 | -20.758 | neutral_review | [] | False |
| allow_short_wall_between_dense_pair | allow_short_wall_between_dense_pair | [3, 4, 5, 6, 7, 8] | {} | 0.000 | 0.000 | 0.000 | neutral_review | [] | False |
| keep_order_with_bottom_xy_micro_probe | keep_local_order | [3, 4, 5, 6, 7, 8] | {'6': {'bottom_x_delta': 0.5, 'bottom_y_delta': -3.0}} | -92.718 | -37.168 | -54.120 | directional | [] | False |
| short_wall_with_bottom_xy_micro_probe | allow_short_wall_between_dense_pair | [3, 4, 5, 6, 7, 8] | {'6': {'bottom_x_delta': 0.5, 'bottom_y_delta': -3.0}} | -92.718 | -37.168 | -54.120 | neutral_review | [] | False |
