# Single-image Manhattan Assist Report

Expert-side diagnostic only: no UI, no apply/writeback, no routing, no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact.
Legacy Manual Edit Table only covers align_pair_x. Verified 3D Local Assist and Conservative Height Reproject rows are review-level dry-runs, not edit instructions. Do not apply without visual confirmation.

## Preview Compatibility

- status: `compatible`
- input_mode: `label_studio_result`
- reason: `current_preview_pairing_and_order_compatible`
- preserve_order: `False`

## Preview Pair Table

| preview_pair_index | top_id | bottom_id | top_x | bottom_x | center_x | top_y | bottom_y | pairing_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | kp_12 | kp_13 | 2.464 | 2.464 | 2.464 | 44.124 | 59.806 | default_preview_order |
| 2 | MxrLFT_IAB | T3J_mph9cG | 45.023 | 45.023 | 45.023 | 34.074 | 73.945 | default_preview_order |
| 3 | 2YvFb9uYeN | 48YGRj6Ski | 53.509 | 53.509 | 53.509 | 33.584 | 74.436 | default_preview_order |
| 4 | 8GAQETpqg7 | kvkB0PTayl | 66.165 | 66.165 | 66.165 | 8.271 | 92.732 | default_preview_order |
| 5 | kp_4 | kp_5 | 74.381 | 74.381 | 74.381 | 40.471 | 67.003 | default_preview_order |
| 6 | kp_6 | kp_7 | 90.613 | 90.613 | 90.613 | 44.287 | 60.242 | default_preview_order |

## Near Duplicate Pair Table

| left_preview_pair_index | right_preview_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_override_required |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Override Pack

Override pack only helps expert prepare a verified order; it is not automatic reorder.

| override_needed | hard_stop_reason | default_n_pairs | default_preview_status | default_preview_reason | accepted_override_formats | example_preview_order_override | override_validation_status | override_validation_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| False |  | 6 | compatible | current_preview_pairing_and_order_compatible | ['preview_order_override=[2,1,3,4]'] | [1, 2, 3, 4, 5, 6] | not_requested | [] | False |

## Topology Override

| preview_order_override_active | topology_source | default_preview_status | default_preview_reason | preview_order_override | order_override_note | override_validation_status | override_validation_reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| False | default_preview_order | compatible | current_preview_pairing_and_order_compatible |  |  | not_requested | [] |

## Pair Index Mapping

Report `pair_index` values refer to the effective ordered_pairs position. `source_preview_order_index` is the original default preview pair number. Candidate `target_pair_indices` use `effective_pair_index`.

| effective_pair_index | source_preview_order_index | top_x | bottom_x | center_x | top_y | bottom_y |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2.464 | 2.464 | 2.464 | 44.124 | 59.806 |
| 2 | 2 | 45.023 | 45.023 | 45.023 | 34.074 | 73.945 |
| 3 | 3 | 53.509 | 53.509 | 53.509 | 33.584 | 74.436 |
| 4 | 4 | 66.165 | 66.165 | 66.165 | 8.271 | 92.732 |
| 5 | 5 | 74.381 | 74.381 | 74.381 | 40.471 | 67.003 |
| 6 | 6 | 90.613 | 90.613 | 90.613 | 44.287 | 60.242 |

## Pair Diagnostics

| pair_index | vertical_x_residual | height_residual | top_bottom_delta_y | warnings |
| --- | --- | --- | --- | --- |
| 1 | 0.000 | 0.002 | 15.682 | [] |
| 2 | 0.000 | 0.002 | 39.871 | [] |
| 3 | 0.000 | 0.003 | 40.852 | [] |
| 4 | 0.000 | 0.462 | 84.461 | [] |
| 5 | 0.000 | 0.102 | 26.532 | [] |
| 6 | 0.000 | 0.066 | 15.955 | [] |

## Recommended Review Order

| rank | pair_index | review_priority | primary_action | assist_status | height_reproject_status | vertical_x_residual | height_residual | max_abs_delta | reason | manual_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.462 |  | vertical_x_residual_zero | False |
| 2 | 5 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.102 |  | vertical_x_residual_zero | False |
| 3 | 6 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.066 |  | vertical_x_residual_zero | False |
| 4 | 3 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.003 |  | vertical_x_residual_zero | False |
| 5 | 1 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.002 |  | vertical_x_residual_zero | False |
| 6 | 2 | diagnostic_review | manual_review_only | review_only | eligible | 0.000 | 0.002 |  | vertical_x_residual_zero | False |

## Manual Edit Table

| pair_index | action | from_top_x | to_top_x | from_bottom_x | to_bottom_x | top_dx | bottom_dx | y_change_allowed | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | manual_review_only | 2.464 |  | 2.464 |  |  |  | False | vertical_x_residual_zero |
| 2 | manual_review_only | 45.023 |  | 45.023 |  |  |  | False | vertical_x_residual_zero |
| 3 | manual_review_only | 53.509 |  | 53.509 |  |  |  | False | vertical_x_residual_zero |
| 4 | manual_review_only | 66.165 |  | 66.165 |  |  |  | False | vertical_x_residual_zero |
| 5 | manual_review_only | 74.381 |  | 74.381 |  |  |  | False | vertical_x_residual_zero |
| 6 | manual_review_only | 90.613 |  | 90.613 |  |  |  | False | vertical_x_residual_zero |

## Duplicate / Dense Corner Diagnostics

| left_pair_index | right_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_only | index_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Order Diagnostics

| is_x_monotonic | n_direction_changes | direction_change_pairs | manual_only_reason |
| --- | --- | --- | --- |
| True | 0 | [] |  |

## Height Applicability Summary

- applicable: `6`
- review_only: `0`
- suppressed: `0`

## Conservative Height Reproject Candidates

| candidate_rank | target_pair_index | operation | top_y_before | top_y_after | top_y_delta | height_residual_before | height_residual_after | height_residual_delta | candidate_decision | gate_reasons | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 | fixed_bottom_top_y_reproject | 8.271 | 12.026 | 3.755 | 0.462 | 0.001 | -0.461 | suggested_review | [] | False |
| 2 | 5 | fixed_bottom_top_y_reproject | 40.471 | 39.386 | -1.084 | 0.102 | 0.001 | -0.101 | suggested_review | [] | False |
| 3 | 6 | fixed_bottom_top_y_reproject | 44.287 | 43.864 | -0.423 | 0.066 | 0.001 | -0.065 | suggested_review | [] | False |
| 4 | 3 | fixed_bottom_top_y_reproject | 33.584 | 33.626 | 0.042 | 0.003 | 0.001 | -0.002 | neutral_review | [] | False |
| 5 | 1 | fixed_bottom_top_y_reproject | 44.124 | 44.137 | 0.013 | 0.002 | 0.001 | -0.001 | neutral_review | [] | False |
| 6 | 2 | fixed_bottom_top_y_reproject | 34.074 | 34.044 | -0.030 | 0.002 | 0.001 | -0.001 | neutral_review | [] | False |

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

### Pair Index Mapping

See the global Pair Index Mapping table above. Inside verified 3D local assist, candidate `target_pair_indices` refer to `effective_pair_index`; source preview order is provenance only.


### Wall Angle Diagnostics

| wall_index | from_pair_index | to_pair_index | from_source_preview_order_index | to_source_preview_order_index | direction_deg | nearest_manhattan_axis_deg | angle_residual_deg | length |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 1 | 2 | 2.165 | 0.000 | 2.165 | 6.600 |
| 2 | 2 | 3 | 2 | 3 | 90.599 | 90.000 | 0.599 | 0.889 |
| 3 | 3 | 4 | 3 | 4 | -178.126 | -180.000 | 1.874 | 1.422 |
| 4 | 4 | 5 | 4 | 5 | 92.179 | 90.000 | 2.179 | 2.389 |
| 5 | 5 | 6 | 5 | 6 | -179.536 | -180.000 | 0.464 | 4.094 |
| 6 | 6 | 1 | 6 | 1 | -105.875 | -90.000 | 15.875 | 3.582 |

### Corner Angle Diagnostics

`turn_angle_deg` is the BEV angle between the previous and next wall vectors at the current corner; residual is measured from 90 degrees.

| corner_pair_index | corner_source_preview_order_index | prev_wall_index | next_wall_index | turn_angle_deg | angle_to_90_residual_deg | local_angle_warning |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 6 | 1 | 71.961 | 18.039 | turn_angle_far_from_90 |
| 2 | 2 | 1 | 2 | 91.566 | 1.566 |  |
| 3 | 3 | 2 | 3 | 88.724 | 1.276 |  |
| 4 | 4 | 3 | 4 | 90.304 | 0.304 |  |
| 5 | 5 | 4 | 5 | 91.715 | 1.715 |  |
| 6 | 6 | 5 | 6 | 106.338 | 16.338 | turn_angle_far_from_90 |

### Local X Translation Dry-run Candidates

2D x-order crossing is not topology reordering.
Explicit target pair mode is an exploratory x-only dry-run; it does not claim to solve y/height residuals.

| candidate_rank | candidate_id | candidate_family | operation | target_pair_indices | dx | status | local_geometry_score_delta | wall_angle_residual_sum_delta_deg | wall_angle_residual_max_delta_deg | affected_wall_indices | affected_corner_indices | x_order_crossing_after_translation | crossed_pair_indices | crossing_scope | candidate_decision | decision_reasons | improved_metrics | risk_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | translate_single_pair_x_dryrun_4_+0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | 0.250 | neutral_review | 0.001 | -0.245 | -0.117 | [3, 4] | [4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 2 | translate_single_pair_x_dryrun_4_+0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | 0.500 | neutral_review | 0.002 | -0.488 | -0.235 | [3, 4] | [4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 3 | translate_single_pair_x_dryrun_4_-0.25 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | -0.250 | neutral_review | 0.010 | 0.248 | 0.115 | [3, 4] | [4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |
| 4 | translate_single_pair_x_dryrun_4_-0.50 | translate_single_pair_x_dryrun | translate_single_pair_x_dryrun | [4] | -0.500 | neutral_review | 0.020 | 0.498 | 0.229 | [3, 4] | [4] | False | [] | 2d_x_only_not_topology | neutral_review | ['no_clear_local_geometry_score_improvement'] | {'layout_height_spread_delta': 0.0, 'target_height_residual_sum_delta': 0.0} | [] | False | False |

### Adaptive Local X Search

Adaptive search is a review-level bounded dry-run, not an edit instruction.
A flat region means the exact dx is not reliable; use it only as directionality.
Y coordinates remain unchanged.

| search_rank | search_family | target_pair_indices | best_dx | score_delta | confidence_label | flat_score_region | x_order_crossing_at_best | decision_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | translate_single_pair_x_adaptive_search | [4] | 0.000 | 0.000 | no_improvement | True | False | ['best_score_not_better_than_baseline'] | False | False |

### Floor-Footprint Sensitivity

- schema_version: `floorprint_sensitivity_m15_18_v1`
- writeback_allowed: `false`
- expert_action_allowed: `false`
- annotation_patch_allowed: `false`
Bottom-y changes alter the floor footprint and may change BEV wall/corner angles.
This is sensitivity analysis only, not an edit instruction.

| target_pair_index | bottom_y_delta | wall_angle_residual_sum_delta | corner_angle_residual_sum_delta | height_residual_delta | state_status_after | x_order_crossing_after_translation | decision_label | decision_reasons | writeback_allowed | expert_action_allowed | annotation_patch_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | -3.000 | 26.740 | 53.481 | 0.437 | ok | False | suppress | ['state_warnings_worsened'] | False | False | False |
| 1 | -2.000 | 17.767 | 35.534 | 0.254 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | -1.000 | 8.741 | 17.482 | 0.113 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 1 | 1.000 | -8.179 | -16.357 | 0.055 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False | False | False |
| 1 | 2.000 | -15.624 | -31.248 | 0.133 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False | False | False |
| 1 | 3.000 | -12.651 | -27.339 | 0.199 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False | False | False |
| 2 | -3.000 | 17.793 | 31.945 | 0.190 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | -2.000 | 12.170 | 19.990 | 0.120 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | -1.000 | 6.198 | 7.367 | 0.054 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | 1.000 | 5.707 | 13.808 | 0.028 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | 2.000 | 12.506 | 27.406 | 0.078 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 2 | 3.000 | 19.055 | 40.504 | 0.129 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | -3.000 | 20.394 | 42.573 | 0.197 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | -2.000 | 13.402 | 28.589 | 0.127 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | -1.000 | 6.157 | 14.099 | 0.061 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | 1.000 | 5.678 | 8.938 | 0.023 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | 2.000 | 11.036 | 23.202 | 0.071 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 3 | 3.000 | 17.548 | 36.909 | 0.122 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | -3.000 | 4.381 | 13.708 | 0.613 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | -2.000 | 1.513 | 7.972 | 0.405 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | -1.000 | -1.098 | 2.561 | 0.201 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | 1.000 | 1.035 | 2.847 | -0.198 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | 2.000 | 2.011 | 6.119 | -0.393 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 4 | 3.000 | 2.934 | 9.762 | -0.371 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | -3.000 | 8.550 | 17.030 | 0.008 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | -2.000 | 5.345 | 9.363 | -0.072 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | -1.000 | 2.507 | 2.367 | -0.063 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | 1.000 | 2.019 | 0.736 | 0.057 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | 2.000 | 4.745 | 1.516 | 0.108 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 5 | 3.000 | 7.284 | 2.347 | 0.155 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | -3.000 | 4.220 | 5.039 | 0.248 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | -2.000 | -8.321 | -17.140 | 0.090 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False | False | False |
| 6 | -1.000 | -5.013 | -16.024 | -0.034 | ok | False | improves | ['local_diagnostic_residuals_decrease'] | False | False | False |
| 6 | 1.000 | 11.225 | 19.021 | 0.083 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | 2.000 | 21.630 | 39.830 | 0.154 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |
| 6 | 3.000 | 31.201 | 58.972 | 0.214 | ok | False | worsens | ['local_diagnostic_residuals_increase'] | False | False | False |

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
