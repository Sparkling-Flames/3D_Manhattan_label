# Manhattan Smoke Probe Report

## Guardrails

Compatibility failure is not correctness. Residual values are preview geometry stability diagnostics, not worker quality. Suggestion counts are preview-only review prompts. This report does not enter formal g_t, does not enter routing, is not a P1/C1/C2/T1/V1 artifact, and is not used in the current worker-facing experiment.

## Source

- `source_export`: export_label\project-23-at-2026-05-07-06-06-980da9dc.json
- `probe_version`: manhattan_smoke_export_probe_v1
- `legacy_keypoint_only`: false
- `meta_labels_trusted`: true

## Counts

- `n_tasks`: 5
- `n_annotations`: 26
- `n_keypoint_results`: 236
- `n_results`: 314
- `parse_error_count`: 0

## Scope Alias Counts

- `normal`: 22
- `oos_geometry`: 1
- `oos_split_level`: 3

## Compatibility Status Counts

- `compatibility_failure_duplicate`: 1
- `compatibility_failure_odd_keypoint`: 1
- `compatible`: 24

## Preview Residual Summary

- `residual_enabled`: true
- `n_residual_valid`: 24
- `n_residual_excluded`: 2

### Preview Residual Numeric Summary

| field | count | median | p90 | max |
| --- | ---: | ---: | ---: | ---: |
| ceiling_y_range | 24 | 28 | 138.292 | 149.246 |
| floor_y_range | 24 | 24.4305 | 163.956 | 173.916 |
| vertical_pair_x_residual | 24 | 0 | 0.00104448 | 0.00335008 |
| wall_height_range | 24 | 49.7456 | 296.883 | 318.642 |
| x_spacing_cv | 24 | 0.213031 | 1.2234 | 1.22534 |

## Audit Eligibility Summary

- `audit_eligibility_enabled`: true
- `n_audit_eligible`: 22
- `n_audit_ineligible`: 4

### Audit Ineligibility Counts

- `oos_geometry`: 1
- `oos_split_level`: 3

## Audit Residual Summary

- `n_audit_residual_valid`: 20
- `n_audit_residual_excluded`: 2

### Audit Residual Exclusion Counts

- `compatibility_failure_duplicate`: 1
- `compatibility_failure_odd_keypoint`: 1

### Audit Residual Numeric Summary

| field | count | median | p90 | max |
| --- | ---: | ---: | ---: | ---: |
| ceiling_y_range | 20 | 28 | 43.5 | 142.275 |
| floor_y_range | 20 | 18.6316 | 43.3082 | 173.453 |
| vertical_pair_x_residual | 20 | 0 | 0.000965492 | 0.00335008 |
| wall_height_range | 20 | 45.431 | 86.7082 | 314.728 |
| x_spacing_cv | 20 | 0.207414 | 1.22534 | 1.22534 |

## Suggestion Summary

- `suggestions_enabled`: true
- `n_suggestion_annotations`: 20

### Suggestion Type Counts

- `no_action`: 10
- `review_ceiling_alignment`: 6
- `review_floor_alignment`: 2
- `review_spacing_irregularity`: 6
- `review_wall_height_inconsistency`: 2

### Suggestion Severity Counts

- `high`: 10
- `low`: 10
- `medium`: 6

### Suggestion Source Field Counts

- `ceiling_y_range`: 6
- `floor_y_range`: 2
- `none`: 10
- `wall_height_range`: 2
- `x_spacing_cv`: 6

Note: suggestion events can exceed suggestion annotations because one annotation can trigger multiple preview-only review prompts.

## Audit Warnings

- none

## Candidate Task Examples

- 1. annotation_id=2614, compatibility_status=compatibility_failure_odd_keypoint, completed_by=9, issue=compatibility_failure, n_keypoints=16, n_pairs=6, n_unpaired_points=4, task_id=2948
- 2. annotation_id=2626, compatibility_status=compatibility_failure_duplicate, completed_by=11, issue=compatibility_failure, n_keypoints=8, n_pairs=4, n_unpaired_points=0, task_id=2948
