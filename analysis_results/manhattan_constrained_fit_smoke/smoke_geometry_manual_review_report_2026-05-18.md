# Manhattan geometry manual review summary

This M15.5 summary is smoke-only / expert-side review evidence. It does not write annotations, does not change formal `g_t`, has no routing role, is no worker quality metric, and is not a `P1/C1/C2/T1/V1` artifact.

Candidate is useful for expert-side review.
Candidate is not stable enough for UI ghost candidate.
Task 2948 is mostly stable except a few geometry-structure failures.
Task 2949 shows mixed behavior and is the main blocker.
M16 remains blocked until candidate gating is designed and validated.

## Counts

- source_csv: `analysis_results\manhattan_constrained_fit_smoke\smoke_geometry_debug_manual_review_template_2026-05-18.csv`
- n_review_rows: 16
- n_review_completed: 16
- n_review_missing: 0
- plausible_candidate_counts: `{'yes': 9, 'no': 4, 'unsure': 3}`
- likely_issue_counts: `{'annotation_geometry': 6, 'algorithm_overfit': 3, 'scope_disagreement': 0, 'unclear': 7}`
- no_and_algorithm_overfit_count: 0
- unsure_and_algorithm_overfit_count: 3
- m16_decision_recommendation: `m16_blocked`

## Task 2948

- summary: `{'task_id': '2948', 'n_review_rows': 9, 'n_review_completed': 9, 'n_review_missing': 0, 'plausible_candidate_counts': {'yes': 6, 'no': 3, 'unsure': 0}, 'likely_issue_counts': {'annotation_geometry': 2, 'algorithm_overfit': 0, 'scope_disagreement': 0, 'unclear': 7}, 'no_and_algorithm_overfit_count': 0, 'unsure_and_algorithm_overfit_count': 0, 'high_risk_algorithm_overfit_rows': [], 'interpretation': 'Task 2948 is mostly stable except a few geometry-structure failures.'}`

## Task 2949

- summary: `{'task_id': '2949', 'n_review_rows': 7, 'n_review_completed': 7, 'n_review_missing': 0, 'plausible_candidate_counts': {'yes': 3, 'no': 1, 'unsure': 3}, 'likely_issue_counts': {'annotation_geometry': 4, 'algorithm_overfit': 3, 'scope_disagreement': 0, 'unclear': 0}, 'no_and_algorithm_overfit_count': 0, 'unsure_and_algorithm_overfit_count': 3, 'high_risk_algorithm_overfit_rows': [{'task_id': '2949', 'annotation_id': '2615', 'plausible_candidate': 'unsure', 'likely_issue': 'algorithm_overfit', 'problem_reason': 'large_candidate_delta', 'max_abs_delta': '9.203673990471728'}, {'task_id': '2949', 'annotation_id': '2642', 'plausible_candidate': 'unsure', 'likely_issue': 'algorithm_overfit', 'problem_reason': 'large_candidate_delta', 'max_abs_delta': '9.31758225251582'}, {'task_id': '2949', 'annotation_id': '2652', 'plausible_candidate': 'unsure', 'likely_issue': 'algorithm_overfit', 'problem_reason': 'large_candidate_delta', 'max_abs_delta': '11.367745006426773'}], 'interpretation': 'Task 2949 shows mixed behavior and is the main blocker.'}`

## M16 Decision

M16 ghost candidate UI remains blocked. The only acceptable next step is offline or expert-side discussion of candidate gating; no annotator-facing UI, no writeback, no routing, and no worker quality use.
