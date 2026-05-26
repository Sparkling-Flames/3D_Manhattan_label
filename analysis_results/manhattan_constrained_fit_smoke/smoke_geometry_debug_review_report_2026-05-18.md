# Manhattan geometry-debug review report

This review package is smoke-only / dev-only. OOS vote is not final OOS adjudication. Candidate deltas are not correction instructions; no writeback, no formal g_t, no routing, and no P1/C1/C2/T1/V1 artifact role.

- source_export: `export_label\project-23-at-2026-05-18-02-56-ac500410.json`
- n_review_candidates: 16
- n_review_candidates_with_problem_reason: 7
- scope_vote_distribution: `{'normal': 32, 'oos_geometry': 1, 'oos_split_level': 4}`
- audit_ineligibility_counts: `{'oos_geometry': 1, 'oos_split_level': 4}`
- preview_incompatibility_counts: `{'compatibility_failure_duplicate': 2, 'compatibility_failure_odd_keypoint': 1}`
- fit_failure_counts: `{}`

## Review candidate policy

Rows are included when geometry_debug has a problem flag, max_abs_delta >= 5, self_crossing_candidate, preview incompatibility, or task_id is 2948/2949. Scope vote and geometry problem are separate columns.

## Focus: task 2948

| annotator_id | annotation_id | scope vote | preview status | geometry_debug fit status | max delta | geometry problem | problem reason |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| 9 | 2614 | normal | compatibility_failure_odd_keypoint | None | None | problem | compatibility_failure_odd_keypoint |
| 2 | 2624 | normal | compatible | ok | 0.031964234553065296 | non-problem | None |
| 11 | 2626 | normal | compatibility_failure_duplicate | None | None | problem | compatibility_failure_duplicate |
| 10 | 2631 | normal | compatible | ok | 0.031964234553065296 | non-problem | None |
| 13 | 2641 | normal | compatible | ok | 0.21438356141885606 | non-problem | None |
| 8 | 2651 | normal | compatible | ok | 0.031964234553065296 | non-problem | None |
| 6 | 2656 | normal | compatibility_failure_duplicate | None | None | problem | compatibility_failure_duplicate |
| 15 | 2661 | normal | compatible | ok | 0.037701474487796816 | non-problem | None |
| 17 | 2667 | normal | compatible | ok | 0.0895972284430826 | non-problem | None |

Note: task-level scope votes here are not OOS adjudication.

## Focus: task 2949

| annotator_id | annotation_id | scope vote | preview status | geometry_debug fit status | max delta | geometry problem | problem reason |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| 9 | 2615 | normal | compatible | ok | 9.203673990471728 | problem | large_candidate_delta |
| 11 | 2627 | oos_split_level | compatible | ok | 2.236346792284138 | non-problem | None |
| 10 | 2632 | oos_split_level | compatible | ok | 0.1814756855336448 | non-problem | None |
| 13 | 2642 | oos_split_level | compatible | ok | 9.31758225251582 | problem | large_candidate_delta |
| 8 | 2652 | normal | compatible | ok | 11.367745006426773 | problem | large_candidate_delta |
| 6 | 2657 | oos_split_level | compatible | failed | None | problem | self_crossing_candidate |
| 15 | 2662 | normal | compatible | ok | 0.1814756855336448 | non-problem | None |

Note: task-level scope votes here are not OOS adjudication.
