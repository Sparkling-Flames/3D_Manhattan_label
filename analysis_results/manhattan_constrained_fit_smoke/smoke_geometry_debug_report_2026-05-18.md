# Manhattan constrained fit geometry debug report

This report is smoke-only / dev-only. A scope vote is not adjudicated OOS. Majority OOS is scope_distribution / disagreement evidence only. Geometry debug runs on parseable keypoints regardless of scope. Candidate deltas are not correction instructions; no writeback, no formal g_t, no routing, and no P1/C1/C2/T1/V1 artifact role.

- source_export: `export_label\project-23-at-2026-05-18-02-56-ac500410.json`
- audit_ineligibility_counts: `{'oos_geometry': 1, 'oos_split_level': 4}`
- preview_incompatibility_counts: `{'compatibility_failure_duplicate': 2, 'compatibility_failure_odd_keypoint': 1}`
- fit_failure_counts: `{}`

## Focus: task 2948

| annotator_id | annotation_id | scope vote | preview status | geometry_debug fit status | max delta | problem reason |
| --- | --- | --- | --- | --- | ---: | --- |
| 9 | 2614 | normal | compatibility_failure_odd_keypoint | None | None | compatibility_failure_odd_keypoint |
| 2 | 2624 | normal | compatible | ok | 0.031964234553065296 | None |
| 11 | 2626 | normal | compatibility_failure_duplicate | None | None | compatibility_failure_duplicate |
| 10 | 2631 | normal | compatible | ok | 0.031964234553065296 | None |
| 13 | 2641 | normal | compatible | ok | 0.21438356141885606 | None |
| 8 | 2651 | normal | compatible | ok | 0.031964234553065296 | None |
| 6 | 2656 | normal | compatibility_failure_duplicate | None | None | compatibility_failure_duplicate |
| 15 | 2661 | normal | compatible | ok | 0.037701474487796816 | None |
| 17 | 2667 | normal | compatible | ok | 0.0895972284430826 | None |

Note: task-level scope votes here are not OOS adjudication.

## Focus: task 2949

| annotator_id | annotation_id | scope vote | preview status | geometry_debug fit status | max delta | problem reason |
| --- | --- | --- | --- | --- | ---: | --- |
| 9 | 2615 | normal | compatible | ok | 9.203673990471728 | large_candidate_delta |
| 11 | 2627 | oos_split_level | compatible | ok | 2.236346792284138 | None |
| 10 | 2632 | oos_split_level | compatible | ok | 0.1814756855336448 | None |
| 13 | 2642 | oos_split_level | compatible | ok | 9.31758225251582 | large_candidate_delta |
| 8 | 2652 | normal | compatible | ok | 11.367745006426773 | large_candidate_delta |
| 6 | 2657 | oos_split_level | compatible | failed | None | self_crossing_candidate |
| 15 | 2662 | normal | compatible | ok | 0.1814756855336448 | None |

Note: task-level scope votes here are not OOS adjudication.
