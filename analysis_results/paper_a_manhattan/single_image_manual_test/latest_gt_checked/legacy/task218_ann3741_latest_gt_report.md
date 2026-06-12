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
| False | default_preview_order_unusable | compatibility_failure_duplicate | near_duplicate_corner_pair |  |  |

## Pair Index Mapping

Report `pair_index` values refer to the effective ordered_pairs position. `source_preview_order_index` is the original default preview pair number. Candidate `target_pair_indices` use `effective_pair_index`.

| effective_pair_index | source_preview_order_index | top_x | bottom_x | center_x | top_y | bottom_y |
| --- | --- | --- | --- | --- | --- | --- |

## Pair Diagnostics

| pair_index | vertical_x_residual | height_residual | top_bottom_delta_y | warnings |
| --- | --- | --- | --- | --- |

## Recommended Review Order

| rank | pair_index | review_priority | primary_action | assist_status | height_reproject_status | vertical_x_residual | height_residual | max_abs_delta | reason | manual_only |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Manual Edit Table

| pair_index | action | from_top_x | to_top_x | from_bottom_x | to_bottom_x | top_dx | bottom_dx | y_change_allowed | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

## Duplicate / Dense Corner Diagnostics

| left_pair_index | right_pair_index | left_center_x | right_center_x | delta_center_x | duplicate_threshold_percent | reason | manual_only | index_source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 6 | 43.860 | 44.799 | 0.940 | 1.000 | near_duplicate_corner_pair | True | preview_ordered_corners |

## Order Diagnostics

| is_x_monotonic | n_direction_changes | direction_change_pairs | manual_only_reason |
| --- | --- | --- | --- |
| True | 0 | [] |  |

## Height Applicability Summary

- applicable: `0`
- review_only: `0`
- suppressed: `0`

## Verified 3D Local Assist

- schema_version: `None`
- operation_family: `None`
- state_status: `None`
- writeback_allowed: `None`
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

### Corner Angle Diagnostics

`turn_angle_deg` is the BEV angle between the previous and next wall vectors at the current corner; residual is measured from 90 degrees.

| corner_pair_index | corner_source_preview_order_index | prev_wall_index | next_wall_index | turn_angle_deg | angle_to_90_residual_deg | local_angle_warning |
| --- | --- | --- | --- | --- | --- | --- |

### Local X Translation Dry-run Candidates

2D x-order crossing is not topology reordering.

| candidate_rank | candidate_id | candidate_family | operation | target_pair_indices | dx | status | local_geometry_score_delta | wall_angle_residual_sum_delta_deg | wall_angle_residual_max_delta_deg | affected_wall_indices | affected_corner_indices | x_order_crossing_after_translation | crossed_pair_indices | crossing_scope | candidate_decision | decision_reasons | improved_metrics | risk_reasons | y_change_allowed | writeback_allowed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

