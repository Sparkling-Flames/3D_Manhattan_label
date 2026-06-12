# Single-image Manhattan Assist Report

Expert-side diagnostic only: no UI, no apply/writeback, no routing, no formal g_t, no worker quality metric, no P1/C1/C2/T1/V1 artifact.
Only rows with action=align_pair_x may be used as manual x-alignment references. Do not edit y from this report.

## Preview Compatibility

- status: `compatible`
- input_mode: `label_studio_result`
- reason: `current_preview_pairing_and_order_compatible`
- preserve_order: `False`

## Topology Override

| preview_order_override_active | topology_source | default_preview_status | default_preview_reason | preview_order_override | order_override_note |
| --- | --- | --- | --- | --- | --- |
| False | default_preview_order | compatible | current_preview_pairing_and_order_compatible |  |  |

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

| candidate_rank | candidate_id | candidate_family | operation | target_pair_indices | dx | status | local_geometry_score_delta | wall_angle_residual_sum_delta_deg | wall_angle_residual_max_delta_deg | affected_wall_indices | affected_corner_indices | x_order_crossing_after_translation | crossed_pair_indices | crossing_scope | candidate_decision | decision_reasons | improved_metrics | risk_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

