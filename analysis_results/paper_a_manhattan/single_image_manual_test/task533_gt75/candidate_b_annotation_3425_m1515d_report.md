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

## Pair Index Mapping

Report `pair_index` values refer to the effective ordered_pairs position. `source_preview_order_index` is the original default preview pair number. Candidate `target_pair_indices` use `effective_pair_index`.

| effective_pair_index | source_preview_order_index | top_x | bottom_x | center_x | top_y | bottom_y |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 7.160 | 7.160 | 7.160 | 12.598 | 88.725 |
| 2 | 1 | 3.341 | 3.341 | 3.341 | 26.788 | 75.443 |
| 3 | 4 | 10.788 | 10.788 | 10.788 | 30.389 | 72.207 |
| 4 | 2 | 3.381 | 3.381 | 3.381 | 42.045 | 58.271 |
| 5 | 5 | 13.473 | 13.473 | 13.473 | 45.072 | 55.555 |
| 6 | 6 | 31.941 | 31.941 | 31.941 | 44.059 | 56.691 |
| 7 | 8 | 47.036 | 47.036 | 47.036 | 36.824 | 64.664 |
| 8 | 7 | 40.576 | 40.576 | 40.576 | 20.590 | 81.246 |
| 9 | 9 | 61.430 | 61.430 | 61.430 | 22.092 | 79.793 |
| 10 | 10 | 84.582 | 84.582 | 84.582 | 18.666 | 83.080 |

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

## Verified 3D Local Assist

- schema_version: `verified_3d_local_assist_m15_15_v1`
- operation_family: `verified_3d_local_assist`
- state_status: `ok`
- writeback_allowed: `False`
- These candidates are review-level dry-runs, not edit instructions.
- Use them to inspect directionality; do not apply without visual confirmation.
- Y coordinates remain unchanged in this report.

### Dense Corner Reclassification

| left_pair_index | right_pair_index | delta_center_x | bev_distance | floor_distance_delta | min_adjacent_wall_length | classification | reason_tokens |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 4 | 0.040 | 4.462 | 4.462 | 0.873 | dense_but_distinct_3d_corner | ['bev_distance_separates_dense_pair', 'floor_distance_delta_separates_dense_pair'] |

### Pair Index Mapping

See the global Pair Index Mapping table above. Inside verified 3D local assist, candidate `target_pair_indices` refer to `effective_pair_index`; source preview order is provenance only.


### Wall Angle Diagnostics

| wall_index | from_pair_index | to_pair_index | from_source_preview_order_index | to_source_preview_order_index | direction_deg | nearest_manhattan_axis_deg | angle_residual_deg | length |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 3 | 1 | -176.127 | -180.000 | 3.873 | 0.991 |
| 2 | 2 | 3 | 1 | 4 | -87.692 | -90.000 | 2.308 | 0.873 |
| 3 | 3 | 4 | 4 | 2 | -179.065 | -180.000 | 0.935 | 4.397 |
| 4 | 4 | 5 | 2 | 5 | -91.354 | -90.000 | 1.354 | 5.530 |
| 5 | 5 | 6 | 5 | 6 | 0.003 | 0.000 | 0.003 | 9.181 |
| 6 | 6 | 7 | 6 | 8 | 89.997 | 90.000 | 0.003 | 6.200 |
| 7 | 7 | 8 | 8 | 7 | 179.998 | 180.000 | 0.002 | 2.281 |
| 8 | 8 | 9 | 7 | 9 | 89.997 | 90.000 | 0.003 | 1.372 |
| 9 | 9 | 10 | 9 | 10 | -179.999 | -180.000 | 0.001 | 1.420 |
| 10 | 10 | 1 | 10 | 3 | -90.001 | -90.000 | 0.001 | 1.033 |

### Corner Angle Diagnostics

`turn_angle_deg` is the BEV angle between the previous and next wall vectors at the current corner; residual is measured from 90 degrees.

| corner_pair_index | corner_source_preview_order_index | prev_wall_index | next_wall_index | turn_angle_deg | angle_to_90_residual_deg | local_angle_warning |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 10 | 1 | 93.874 | 3.874 |  |
| 2 | 1 | 1 | 2 | 91.565 | 1.565 |  |
| 3 | 4 | 2 | 3 | 88.627 | 1.373 |  |
| 4 | 2 | 3 | 4 | 92.289 | 2.289 |  |
| 5 | 5 | 4 | 5 | 88.643 | 1.357 |  |
| 6 | 6 | 5 | 6 | 90.006 | 0.006 |  |
| 7 | 8 | 6 | 7 | 89.999 | 0.001 |  |
| 8 | 7 | 7 | 8 | 89.998 | 0.002 |  |
| 9 | 9 | 8 | 9 | 89.996 | 0.004 |  |
| 10 | 10 | 9 | 10 | 90.002 | 0.002 |  |

### Local X Translation Dry-run Candidates

2D x-order crossing is not topology reordering.

| candidate_rank | candidate_id | candidate_family | operation | target_pair_indices | dx | status | local_geometry_score_delta | wall_angle_residual_sum_delta_deg | wall_angle_residual_max_delta_deg | affected_wall_indices | affected_corner_indices | x_order_crossing_after_translation | crossed_pair_indices | crossing_scope | candidate_decision | decision_reasons | improved_metrics | risk_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | translate_single_pair_x_dryrun_2_-0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [2] | -0.500 | suggested_review | -0.030 | -2.317 | -1.099 | [1, 2] | [2] | False | [] | 2d_x_only_not_topology | suggested_review | ['local_geometry_score_improved'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 2 | translate_pair_cluster_x_dryrun_2-4_-0.25 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [2, 4] | -0.250 | suggested_review | -0.021 | -2.027 | -1.313 | [1, 2, 3, 4] | [2, 4] | False | [] | 2d_x_only_not_topology | suggested_review | ['local_geometry_score_improved'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 3 | translate_single_pair_x_dryrun_2_-0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [2] | -0.250 | suggested_review | -0.015 | -1.144 | -1.313 | [1, 2] | [2] | False | [] | 2d_x_only_not_topology | suggested_review | ['local_geometry_score_improved'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 4 | translate_pair_cluster_x_dryrun_2-4_-0.50 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [2, 4] | -0.500 | suggested_review | -0.010 | -2.198 | -1.099 | [1, 2, 3, 4] | [2, 4] | False | [] | 2d_x_only_not_topology | suggested_review | ['local_geometry_score_improved'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 5 | translate_single_pair_x_dryrun_4_-0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | -0.250 | neutral_review | -0.000 | -0.883 | -0.218 | [3, 4] | [4] | True | [2] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 6 | separate_dense_pair_x_dryrun_2-4_left_negative_right_positive_+0.25 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [2, 4] | 0.250 | neutral_review | 0.019 | 0.308 | -1.313 | [1, 2, 3, 4] | [2, 4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 7 | separate_dense_pair_x_dryrun_2-4_left_positive_right_negative_+0.25 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [2, 4] | 0.250 | neutral_review | 0.019 | 0.227 | 1.402 | [1, 2, 3, 4] | [2, 4] | True | [2, 4] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 8 | translate_single_pair_x_dryrun_2_+0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [2] | 0.250 | neutral_review | 0.029 | 1.111 | 1.402 | [1, 2] | [2] | True | [4] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 9 | translate_single_pair_x_dryrun_4_-0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | -0.500 | neutral_review | 0.032 | 0.119 | 0.115 | [3, 4] | [4] | True | [2] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 10 | separate_dense_pair_x_dryrun_2-4_left_negative_right_positive_+0.50 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [2, 4] | 0.500 | neutral_review | 0.038 | 0.617 | -0.508 | [1, 2, 3, 4] | [2, 4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 11 | translate_single_pair_x_dryrun_4_+0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | 0.250 | neutral_review | 0.039 | 1.452 | 0.793 | [3, 4] | [4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 12 | translate_single_pair_x_dryrun_2_+0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [2] | 0.500 | neutral_review | 0.057 | 2.184 | 2.810 | [1, 2] | [2] | True | [4] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 13 | translate_pair_cluster_x_dryrun_2-4_+0.25 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [2, 4] | 0.250 | neutral_review | 0.059 | 2.562 | 1.402 | [1, 2, 3, 4] | [2, 4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 14 | separate_dense_pair_x_dryrun_2-4_left_positive_right_negative_+0.50 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [2, 4] | 0.500 | neutral_review | 0.070 | 2.303 | 2.810 | [1, 2, 3, 4] | [2, 4] | True | [2, 4] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 15 | translate_single_pair_x_dryrun_4_+0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | 0.500 | neutral_review | 0.077 | 2.934 | 2.011 | [3, 4] | [4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 16 | translate_pair_cluster_x_dryrun_2-4_+0.50 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [2, 4] | 0.500 | neutral_review | 0.118 | 5.118 | 2.810 | [1, 2, 3, 4] | [2, 4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |

