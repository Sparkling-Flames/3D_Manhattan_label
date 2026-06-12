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
| 1 | kp_6 | kp_7 | 0.737 | 0.737 | 0.737 | 42.475 | 56.867 | default_preview_order |
| 2 | kp_4 | kp_5 | 5.990 | 6.250 | 6.120 | 16.134 | 91.231 | default_preview_order |
| 3 | kp_8 | kp_9 | 8.981 | 8.981 | 8.981 | 43.602 | 55.834 | default_preview_order |
| 4 | kp_10 | kp_11 | 27.722 | 27.722 | 27.722 | 38.568 | 60.477 | default_preview_order |
| 5 | kp_14 | kp_15 | 50.497 | 50.497 | 50.497 | 26.025 | 72.479 | default_preview_order |
| 6 | kp_12 | kp_13 | 51.167 | 51.167 | 51.167 | 13.580 | 85.250 | default_preview_order |
| 7 | kp_0 | kp_1 | 63.869 | 64.169 | 64.019 | 32.617 | 68.359 | default_preview_order |
| 8 | kp_2 | kp_3 | 83.984 | 83.984 | 83.984 | 31.445 | 69.531 | default_preview_order |

## Near Duplicate Pair Table

| left_preview_pair_index | right_preview_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_override_required |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 6 | 50.497 | 51.167 | 0.670 | 1.000 | near_duplicate_corner_pair | True |

## Override Pack

Override pack only helps expert prepare a verified order; it is not automatic reorder.

| override_needed | hard_stop_reason | default_n_pairs | default_preview_status | default_preview_reason | accepted_override_formats | example_preview_order_override | override_validation_status | override_validation_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | near_duplicate_corner_pair | 8 | compatibility_failure_duplicate | near_duplicate_corner_pair | ['preview_order_override=[2,1,3,4]'] | [1, 2, 3, 4, 5, 6, 7, 8] | valid | ['order_verified_by_expert'] | False |

## Topology Override

| preview_order_override_active | topology_source | default_preview_status | default_preview_reason | preview_order_override | order_override_note | override_validation_status | override_validation_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| True | expert_verified_preview_order | compatibility_failure_duplicate | near_duplicate_corner_pair | [2, 1, 3, 4, 6, 5, 7, 8] |  | valid | ['order_verified_by_expert'] |

## Pair Index Mapping

Report `pair_index` values refer to the effective ordered_pairs position. `source_preview_order_index` is the original default preview pair number. Candidate `target_pair_indices` use `effective_pair_index`.

| effective_pair_index | source_preview_order_index | top_x | bottom_x | center_x | top_y | bottom_y |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 5.990 | 6.250 | 6.120 | 16.134 | 91.231 |
| 2 | 1 | 0.737 | 0.737 | 0.737 | 42.475 | 56.867 |
| 3 | 3 | 8.981 | 8.981 | 8.981 | 43.602 | 55.834 |
| 4 | 4 | 27.722 | 27.722 | 27.722 | 38.568 | 60.477 |
| 5 | 6 | 51.167 | 51.167 | 51.167 | 13.580 | 85.250 |
| 6 | 5 | 50.497 | 50.497 | 50.497 | 26.025 | 72.479 |
| 7 | 7 | 63.869 | 64.169 | 64.019 | 32.617 | 68.359 |
| 8 | 8 | 83.984 | 83.984 | 83.984 | 31.445 | 69.531 |

## Pair Diagnostics

| pair_index | vertical_x_residual | height_residual | top_bottom_delta_y | warnings |
| --- | --- | --- | --- | --- |
| 1 | 0.260 | 0.944 | 75.097 | ['height_residual_high'] |
| 2 | 0.000 | 0.000 | 14.393 | [] |
| 3 | 0.000 | 0.000 | 12.232 | [] |
| 4 | 0.000 | 0.000 | 21.908 | [] |
| 5 | 0.000 | 0.000 | 71.670 | [] |
| 6 | 0.000 | 0.000 | 46.454 | [] |
| 7 | 0.300 | 0.264 | 35.742 | [] |
| 8 | 0.000 | 0.261 | 38.086 | [] |

## Recommended Review Order

| rank | pair_index | review_priority | primary_action | assist_status | height_reproject_status | vertical_x_residual | height_residual | max_abs_delta | reason | manual_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7 | align_x_first | align_pair_x | eligible | eligible | 0.300 | 0.264 | 0.150 | align_pair_x_candidate_available | False |
| 2 | 1 | diagnostic_review | manual_review_only | review_only | review_only | 0.260 | 0.944 |  | pair_warning_height_residual_high | False |
| 3 | 8 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.261 |  | vertical_x_residual_zero | False |
| 4 | 3 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 5 | 2 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 6 | 4 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | vertical_x_residual_zero | False |
| 7 | 5 | manual_only_dense_or_order | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | near_duplicate_corner_pair | True |
| 8 | 6 | manual_only_dense_or_order | manual_review_only | review_only | eligible | 0.000 | 0.000 |  | near_duplicate_corner_pair | True |

## Manual Edit Table

| pair_index | action | from_top_x | to_top_x | from_bottom_x | to_bottom_x | top_dx | bottom_dx | y_change_allowed | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | manual_review_only | 5.990 |  | 6.250 |  |  |  | False | pair_warning_height_residual_high |
| 2 | manual_review_only | 0.737 |  | 0.737 |  |  |  | False | vertical_x_residual_zero |
| 3 | manual_review_only | 8.981 |  | 8.981 |  |  |  | False | vertical_x_residual_zero |
| 4 | manual_review_only | 27.722 |  | 27.722 |  |  |  | False | vertical_x_residual_zero |
| 5 | manual_review_only | 51.167 |  | 51.167 |  |  |  | False | near_duplicate_corner_pair |
| 6 | manual_review_only | 50.497 |  | 50.497 |  |  |  | False | near_duplicate_corner_pair |
| 7 | align_pair_x | 63.869 | 64.019 | 64.169 | 64.019 | 0.150 | -0.150 | False |  |
| 8 | manual_review_only | 83.984 |  | 83.984 |  |  |  | False | vertical_x_residual_zero |

## Duplicate / Dense Corner Diagnostics

| left_pair_index | right_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_only | index_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | 5 | 50.497 | 51.167 | 0.670 | 1.000 | near_duplicate_corner_pair | True | expert_verified_preview_order |

## Order Diagnostics

| is_x_monotonic | n_direction_changes | direction_change_pairs | manual_only_reason |
| --- | --- | --- | --- |
| False | 3 | [{'left_pair_index': 1, 'middle_pair_index': 2, 'right_pair_index': 3, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 4, 'middle_pair_index': 5, 'right_pair_index': 6, 'from_direction': 'increasing', 'to_direction': 'decreasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}, {'left_pair_index': 5, 'middle_pair_index': 6, 'right_pair_index': 7, 'from_direction': 'decreasing', 'to_direction': 'increasing', 'reason': 'expert_verified_non_x_monotonic_order', 'manual_only': False}] |  |

## Height Applicability Summary

- applicable: `7`
- review_only: `1`
- suppressed: `0`

## Conservative Height Reproject Candidates

| candidate_rank | target_pair_index | operation | top_y_before | top_y_after | top_y_delta | height_residual_before | height_residual_after | height_residual_delta | candidate_decision | gate_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7 | fixed_bottom_top_y_reproject | 32.617 | 30.239 | -2.378 | 0.264 | 0.000 | -0.264 | suggested_review | [] | False |
| 2 | 8 | fixed_bottom_top_y_reproject | 31.445 | 29.030 | -2.415 | 0.261 | 0.000 | -0.261 | suggested_review | [] | False |
| 3 | 3 | fixed_bottom_top_y_reproject | 43.602 | 43.602 | 0.000 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 4 | 5 | fixed_bottom_top_y_reproject | 13.580 | 13.581 | 0.001 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 5 | 6 | fixed_bottom_top_y_reproject | 26.025 | 26.026 | 0.001 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 6 | 2 | fixed_bottom_top_y_reproject | 42.475 | 42.475 | 0.000 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 7 | 4 | fixed_bottom_top_y_reproject | 38.568 | 38.568 | -0.001 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 8 | 1 | fixed_bottom_top_y_reproject | 16.134 | 8.012 | -8.122 | 0.944 | 0.000 | -0.944 | suppress | ['top_y_delta_exceeds_threshold'] | False |

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
| 6 | 5 | 0.670 | 1.078 | 1.076 | 1.078 | dense_but_distinct_3d_corner | ['bev_distance_separates_dense_pair', 'floor_distance_delta_separates_dense_pair'] |

### Pair Index Mapping

See the global Pair Index Mapping table above. Inside verified 3D local assist, candidate `target_pair_indices` refer to `effective_pair_index`; source preview order is provenance only.


### Wall Angle Diagnostics

| wall_index | from_pair_index | to_pair_index | from_source_preview_order_index | to_source_preview_order_index | direction_deg | nearest_manhattan_axis_deg | angle_residual_deg | length |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 2 | 1 | -178.599 | -180.000 | 1.401 | 6.876 |
| 2 | 2 | 3 | 1 | 3 | -90.009 | -90.000 | 0.009 | 4.279 |
| 3 | 3 | 4 | 3 | 4 | 0.004 | 0.000 | 0.004 | 8.091 |
| 4 | 4 | 5 | 4 | 6 | 89.998 | 90.000 | 0.002 | 4.675 |
| 5 | 5 | 6 | 6 | 5 | 0.000 | 0.000 | 0.000 | 1.078 |
| 6 | 6 | 7 | 5 | 7 | 99.559 | 90.000 | 9.559 | 1.864 |
| 7 | 7 | 8 | 7 | 8 | 179.535 | 180.000 | 0.465 | 2.781 |
| 8 | 8 | 1 | 8 | 2 | -69.137 | -90.000 | 20.863 | 2.236 |

### Corner Angle Diagnostics

`turn_angle_deg` is the BEV angle between the previous and next wall vectors at the current corner; residual is measured from 90 degrees.

| corner_pair_index | corner_source_preview_order_index | prev_wall_index | next_wall_index | turn_angle_deg | angle_to_90_residual_deg | local_angle_warning |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 8 | 1 | 70.538 | 19.462 | turn_angle_far_from_90 |
| 2 | 1 | 1 | 2 | 91.410 | 1.410 |  |
| 3 | 3 | 2 | 3 | 89.988 | 0.012 |  |
| 4 | 4 | 3 | 4 | 90.006 | 0.006 |  |
| 5 | 6 | 4 | 5 | 90.002 | 0.002 |  |
| 6 | 5 | 5 | 6 | 80.441 | 9.559 |  |
| 7 | 7 | 6 | 7 | 100.023 | 10.023 |  |
| 8 | 8 | 7 | 8 | 68.672 | 21.328 | turn_angle_far_from_90 |

### Local X Translation Dry-run Candidates

2D x-order crossing is not topology reordering.


| candidate_rank | candidate_id | candidate_family | operation | target_pair_indices | dx | status | local_geometry_score_delta | wall_angle_residual_sum_delta_deg | wall_angle_residual_max_delta_deg | affected_wall_indices | affected_corner_indices | x_order_crossing_after_translation | crossed_pair_indices | crossing_scope | candidate_decision | decision_reasons | improved_metrics | risk_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | translate_single_pair_x_dryrun_5_-0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [5] | -0.250 | neutral_review | 0.018 | 0.677 | 0.665 | [4, 5] | [5] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 2 | translate_single_pair_x_dryrun_5_+0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [5] | 0.250 | neutral_review | 0.018 | 0.674 | 0.663 | [4, 5] | [5] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 3 | translate_pair_cluster_x_dryrun_6-5_-0.25 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [6, 5] | -0.250 | neutral_review | 0.022 | 0.783 | -0.127 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 4 | translate_pair_cluster_x_dryrun_6-5_+0.25 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [6, 5] | 0.250 | neutral_review | 0.026 | 1.026 | 0.117 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 5 | translate_single_pair_x_dryrun_6_-0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [6] | -0.250 | neutral_review | 0.034 | 1.437 | -0.127 | [5, 6] | [6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 6 | translate_single_pair_x_dryrun_5_-0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [5] | -0.500 | neutral_review | 0.036 | 1.352 | 1.333 | [4, 5] | [5] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 7 | translate_single_pair_x_dryrun_5_+0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [5] | 0.500 | neutral_review | 0.036 | 1.351 | 1.325 | [4, 5] | [5] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 8 | translate_single_pair_x_dryrun_6_+0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [6] | 0.250 | neutral_review | 0.036 | 1.684 | 0.117 | [5, 6] | [6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 9 | translate_pair_cluster_x_dryrun_6-5_-0.50 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [6, 5] | -0.500 | neutral_review | 0.043 | 1.553 | -0.265 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 10 | separate_dense_pair_x_dryrun_6-5_left_negative_right_positive_+0.25 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [6, 5] | 0.250 | neutral_review | 0.045 | 2.108 | -0.127 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 11 | separate_dense_pair_x_dryrun_6-5_left_positive_right_negative_+0.25 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [6, 5] | 0.250 | neutral_review | 0.049 | 2.362 | 0.117 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 12 | translate_pair_cluster_x_dryrun_6-5_+0.50 | translate_pair_cluster_x_dryrun | translate_pair_cluster_x_dryrun | [6, 5] | 0.500 | neutral_review | 0.052 | 2.047 | 0.224 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 13 | translate_single_pair_x_dryrun_6_-0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [6] | -0.500 | neutral_review | 0.067 | 2.862 | -0.265 | [5, 6] | [6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 14 | translate_single_pair_x_dryrun_6_+0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [6] | 0.500 | neutral_review | 0.073 | 3.358 | 0.224 | [5, 6] | [6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 15 | separate_dense_pair_x_dryrun_6-5_left_negative_right_positive_+0.50 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [6, 5] | 0.500 | neutral_review | 0.089 | 4.200 | -0.265 | [4, 5, 6] | [5, 6] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 16 | separate_dense_pair_x_dryrun_6-5_left_positive_right_negative_+0.50 | separate_dense_pair_x_dryrun | separate_dense_pair_x_dryrun | [6, 5] | 0.500 | neutral_review | 0.098 | 4.713 | 0.224 | [4, 5, 6] | [5, 6] | True | [5, 6] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement', 'x_order_crossing_after_translation'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |

### Adaptive Local X Search

Adaptive search is a review-level bounded dry-run, not an edit instruction.
A flat region means the exact dx is not reliable; use it only as directionality.
Y coordinates remain unchanged.

| search_rank | search_family | target_pair_indices | best_dx | score_delta | confidence_label | flat_score_region | x_order_crossing_at_best | decision_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | translate_pair_cluster_x_adaptive_search | [6, 5] | 0.000 | 0.000 | no_improvement | True | False | ['best_score_not_better_than_baseline'] | False | False |
| 2 | translate_single_pair_x_adaptive_search | [6] | 0.000 | 0.000 | no_improvement | True | False | ['best_score_not_better_than_baseline'] | False | False |
| 3 | translate_single_pair_x_adaptive_search | [5] | 0.000 | 0.000 | no_improvement | True | False | ['best_score_not_better_than_baseline'] | False | False |
