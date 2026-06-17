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
| 1 | Ht5GOhYmvG | _WtRNxrtum | 3.341 | 3.341 | 3.341 | 26.788 | 75.443 | default_preview_order |
| 2 | kp_6 | kp_7 | 3.381 | 3.381 | 3.381 | 42.045 | 58.271 | default_preview_order |
| 3 | kp_4 | kp_5 | 7.160 | 7.160 | 7.160 | 12.598 | 88.725 | default_preview_order |
| 4 | nyIAWcY4yO | URqPSc2T8R | 10.788 | 10.788 | 10.788 | 30.389 | 72.207 | default_preview_order |
| 5 | kp_8 | kp_9 | 13.473 | 13.473 | 13.473 | 45.072 | 55.555 | default_preview_order |
| 6 | kp_10 | kp_11 | 31.941 | 31.941 | 31.941 | 44.059 | 56.691 | default_preview_order |
| 7 | kp_14 | kp_15 | 40.576 | 40.576 | 40.576 | 20.590 | 81.246 | default_preview_order |
| 8 | kp_12 | kp_13 | 47.036 | 47.036 | 47.036 | 36.824 | 64.664 | default_preview_order |
| 9 | kp_0 | kp_1 | 61.430 | 61.430 | 61.430 | 22.092 | 79.793 | default_preview_order |
| 10 | kp_2 | kp_3 | 84.582 | 84.582 | 84.582 | 18.666 | 83.080 | default_preview_order |

## Near Duplicate Pair Table

| left_preview_pair_index | right_preview_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_override_required |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 3.341 | 3.381 | 0.040 | 1.000 | near_duplicate_corner_pair | True |

## Override Pack

Override pack only helps expert prepare a verified order; it is not automatic reorder.

| override_needed | hard_stop_reason | default_n_pairs | default_preview_status | default_preview_reason | accepted_override_formats | example_preview_order_override | override_validation_status | override_validation_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False | near_duplicate_corner_pair | 10 | compatibility_failure_duplicate | near_duplicate_corner_pair | ['preview_order_override=[2,1,3,4]'] | [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] | valid | ['order_verified_by_expert'] | False |

## Topology Override

| preview_order_override_active | topology_source | default_preview_status | default_preview_reason | preview_order_override | order_override_note | override_validation_status | override_validation_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| True | expert_verified_preview_order | compatibility_failure_duplicate | near_duplicate_corner_pair | [3, 1, 4, 2, 5, 6, 8, 7, 9, 10] | Manual preview order selected in 3D preview because default order folds near dense/occluded corners. | valid | ['order_verified_by_expert'] |

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

## Conservative Height Reproject Candidates

| candidate_rank | target_pair_index | operation | top_y_before | top_y_after | top_y_delta | height_residual_before | height_residual_after | height_residual_delta | candidate_decision | gate_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 | fixed_bottom_top_y_reproject | 42.045 | 42.643 | 0.599 | 0.120 | 0.000 | -0.120 | suggested_review | [] | False |
| 2 | 3 | fixed_bottom_top_y_reproject | 30.389 | 29.681 | -0.707 | 0.065 | 0.000 | -0.065 | suggested_review | [] | False |
| 3 | 2 | fixed_bottom_top_y_reproject | 26.788 | 26.498 | -0.291 | 0.026 | 0.000 | -0.026 | neutral_review | [] | False |
| 4 | 8 | fixed_bottom_top_y_reproject | 20.590 | 20.587 | -0.003 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 5 | 5 | fixed_bottom_top_y_reproject | 45.072 | 45.073 | 0.000 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 6 | 7 | fixed_bottom_top_y_reproject | 36.824 | 36.825 | 0.001 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 7 | 1 | fixed_bottom_top_y_reproject | 12.598 | 12.598 | 0.001 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 8 | 10 | fixed_bottom_top_y_reproject | 18.666 | 18.665 | -0.001 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 9 | 9 | fixed_bottom_top_y_reproject | 22.092 | 22.092 | -0.000 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |
| 10 | 6 | fixed_bottom_top_y_reproject | 44.059 | 44.059 | 0.000 | 0.000 | 0.000 | -0.000 | neutral_review | [] | False |

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

### Adaptive Local X Search

Adaptive search is a review-level bounded dry-run, not an edit instruction.
A flat region means the exact dx is not reliable; use it only as directionality.
Y coordinates remain unchanged.

| search_rank | search_family | target_pair_indices | best_dx | score_delta | confidence_label | flat_score_region | x_order_crossing_at_best | decision_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | translate_single_pair_x_adaptive_search | [2] | -0.500 | -0.030 | flat_uncertain | True | False | ['flat_score_region_near_best'] | False | False |
| 2 | translate_pair_cluster_x_adaptive_search | [2, 4] | -0.200 | -0.024 | flat_uncertain | True | False | ['flat_score_region_near_best'] | False | False |
| 3 | translate_single_pair_x_adaptive_search | [4] | -0.200 | -0.007 | flat_uncertain | True | True | ['flat_score_region_near_best', 'x_order_crossing_at_best'] | False | False |

### Floor-Footprint Sensitivity

- schema_version: `floorprint_sensitivity_m15_18_v1`
- writeback_allowed: `false`
- expert_action_allowed: `false`
- annotation_patch_allowed: `false`
Bottom-y changes alter the floor footprint and may change BEV wall/corner angles.
This is sensitivity analysis only, not an edit instruction.

| target_pair_index | bottom_y_delta | wall_angle_residual_sum_delta | corner_angle_residual_sum_delta | height_residual_delta | state_status_after | x_order_crossing_after_translation | decision_label | decision_reasons | writeback_allowed | expert_action_allowed | annotation_patch_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | -3.000 | 5.077 | 13.316 | 0.426 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | -2.000 | 2.726 | 7.992 | 0.280 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | -1.000 | 1.500 | 3.001 | 0.138 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | 1.000 | 4.043 | 2.310 | 0.135 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | 2.000 | 8.022 | 4.359 | 0.267 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | 3.000 | 11.947 | 9.953 | 0.397 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | -3.000 | 23.322 | 39.502 | 0.238 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | -2.000 | 15.201 | 24.442 | 0.135 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | -1.000 | 7.378 | 10.123 | 0.039 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | 1.000 | 0.530 | 7.547 | 0.085 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | 2.000 | 4.901 | 16.289 | 0.165 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | 3.000 | 8.488 | 23.462 | 0.241 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | -3.000 | 13.598 | 25.712 | 0.163 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | -2.000 | 7.350 | 16.067 | 0.057 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | -1.000 | 0.670 | 7.420 | -0.040 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | 1.000 | 7.619 | 10.268 | 0.083 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | 2.000 | 15.615 | 24.612 | 0.161 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | 3.000 | 23.829 | 39.552 | 0.233 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | -3.000 | 38.650 | 62.636 | 0.907 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | -2.000 | 21.782 | 31.934 | 0.510 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | -1.000 | 8.087 | 7.876 | 0.220 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | 1.000 | 6.807 | 13.278 | -0.066 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | 2.000 | 14.082 | 23.284 | 0.075 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | 3.000 | 20.484 | 30.999 | 0.191 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | -3.000 | 53.172 | 106.344 | 1.688 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | -2.000 | 36.537 | 73.073 | 0.810 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | -1.000 | 18.688 | 37.376 | 0.317 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | 1.000 | 16.211 | 30.547 | 0.221 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | 2.000 | 34.507 | 67.138 | 0.384 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | 3.000 | 51.272 | 100.668 | 0.509 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | -3.000 | 38.088 | 73.471 | 1.178 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | -2.000 | 24.285 | 45.865 | 0.619 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | -1.000 | 11.566 | 20.427 | 0.256 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | 1.000 | 10.546 | 21.092 | 0.190 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | 2.000 | 20.219 | 40.438 | 0.337 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | 3.000 | 29.163 | 58.327 | 0.455 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 7 | -3.000 | 11.886 | 17.528 | 0.415 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 7 | -2.000 | 7.542 | 10.747 | 0.256 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 7 | -1.000 | 3.616 | 4.967 | 0.119 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 7 | 1.000 | 3.388 | 4.299 | 0.105 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 7 | 2.000 | 6.644 | 8.073 | 0.198 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 7 | 3.000 | 9.828 | 11.404 | 0.282 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 8 | -3.000 | 10.914 | 14.688 | 0.309 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 8 | -2.000 | 7.194 | 9.885 | 0.201 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 8 | -1.000 | 3.558 | 4.984 | 0.098 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 8 | 1.000 | 3.514 | 5.079 | 0.094 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 8 | 2.000 | 6.984 | 10.238 | 0.185 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 8 | 3.000 | 10.417 | 15.466 | 0.272 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 9 | -3.000 | 12.857 | 25.714 | 0.301 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 9 | -2.000 | 8.709 | 17.419 | 0.196 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 9 | -1.000 | 4.425 | 8.850 | 0.095 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 9 | 1.000 | 4.560 | 9.120 | 0.091 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 9 | 2.000 | 9.270 | 18.541 | 0.178 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 9 | 3.000 | 14.124 | 28.248 | 0.262 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 10 | -3.000 | 12.325 | 16.898 | 0.324 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 10 | -2.000 | 8.384 | 9.016 | 0.212 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 10 | -1.000 | 4.278 | 4.448 | 0.104 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 10 | 1.000 | 4.472 | 8.943 | 0.100 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 10 | 2.000 | 9.145 | 18.291 | 0.197 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 10 | 3.000 | 14.035 | 28.071 | 0.290 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |

### Local Dense-Corner Hypothesis Probe

- schema_version: `local_dense_corner_probe_m15_18_2_v1`
- writeback_allowed: `false`
- expert_action_allowed: `false`
- annotation_patch_allowed: `false`
Only triggered for unresolved dense corners.
Hypotheses are local dry-runs.
Topology variants are not automatic reorder.
Bottom-only hypothesis rows are sensitivity-only and must not be used to edit Label Studio points.
Directional rows must be column-constrained: top_x and bottom_x move together and the dense-separation gate must pass.
No writeback / no patch.

| hypothesis_id | topology_variant | probe_mode | local_window_pair_indices | bottom_xy_offsets | column_xy_offsets | local_geometry_score_delta | wall_angle_residual_sum_delta | corner_angle_residual_sum_delta | confidence_label | pair_vertical_x_consistent | dense_pair_center_x_separation_before | dense_pair_center_x_separation_after | minimum_dense_pair_center_x_separation | dense_pair_bev_separation_before | dense_pair_bev_separation_after | minimum_dense_pair_bev_separation | dense_separation_gate_passed | recommendation_eligible | decision_reasons | risk_reasons | writeback_allowed | expert_action_allowed | annotation_patch_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
