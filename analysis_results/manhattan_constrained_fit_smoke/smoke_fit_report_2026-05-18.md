# Manhattan constrained fit smoke report

This is smoke-only / dev-only. Candidate deltas are not correction instructions. There is no annotation writeback, no formal g_t, no routing, no worker quality metric, and no P1/C1/C2/T1/V1 artifact role.

- source_export: `export_label\project-23-at-2026-05-18-02-56-ac500410.json`
- n_tasks: 5
- n_annotations: 37
- n_scope_vote_normal: 32
- n_scope_vote_oos: 5
- scope_vote_distribution: `{'normal': 32, 'oos_geometry': 1, 'oos_split_level': 4}`
- n_preview_compatible: 29
- n_preview_excluded: 3
- n_fit_ok: 29
- n_fit_failed: 0
- n_large_move_candidates: 2

## Main counts

- audit_ineligibility_counts: `{'oos_geometry': 1, 'oos_split_level': 4}`
- preview_incompatibility_counts: `{'compatibility_failure_duplicate': 2, 'compatibility_failure_odd_keypoint': 1}`
- fit_failure_counts: `{}`
- direction_label_counts: `{'no_action': 26, 'review_manhattan_wall_directions': 3}`
- fit_confidence_counts: `{'high': 25, 'low': 2, 'medium': 2}`

## Movement statistics

- fit_residual_summary: `{'count': 29, 'median': 0.0012169891441367242, 'p90': 0.028542656343239794, 'max': 0.09410975256952664}`
- yaw_deg_summary: `{'count': 29, 'median': 89.65196948670105, 'p90': 89.79150427830609, 'max': 89.94147532628507}`
- layout_height_candidate_summary: `{'count': 29, 'median': 2.724274059310864, 'p90': 3.005467273500611, 'max': 3.1121332611327266}`
- layout_height_spread_summary: `{'count': 29, 'median': 0.010940704016596747, 'p90': 0.07241087706604668, 'max': 0.9538006365859815}`
- abs_delta_summary: `{'count': 29, 'median': 0.1059687221955592, 'p90': 1.7977471258590767, 'max': 11.367745006426773}`

## Candidate examples

- `{'task_id': 2949, 'annotation_id': 2652, 'annotator_id': 8, 'review_priority': 'high', 'direction_label': 'review_manhattan_wall_directions', 'fit_residual': 0.09410975256952664, 'max_abs_delta': 11.367745006426773, 'warnings': ['layout_height_spread_high']}`
- `{'task_id': 2949, 'annotation_id': 2615, 'annotator_id': 9, 'review_priority': 'high', 'direction_label': 'review_manhattan_wall_directions', 'fit_residual': 0.07613659862840115, 'max_abs_delta': 9.203673990471728, 'warnings': ['layout_height_spread_high']}`
- `{'task_id': 2951, 'annotation_id': 2634, 'annotator_id': 10, 'review_priority': 'medium', 'direction_label': 'review_manhattan_wall_directions', 'fit_residual': 0.037027746799550176, 'max_abs_delta': 1.0305854812275754, 'warnings': []}`
