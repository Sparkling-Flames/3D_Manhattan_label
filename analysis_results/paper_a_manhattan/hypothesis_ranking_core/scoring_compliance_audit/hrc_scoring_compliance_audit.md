# HRC C6.5a.3 Scoring Compliance Audit

- Compliance: `partial`
- C6 status: `audit_blocked`
- C6.5b authorized: `False`
- Next allowed step: `remain blocked; resolve scoring compliance findings before C6.5a.4 evaluator hardening spec`

## Layer findings

- `L0`: `complete`
- `L1`: `partial`
- `L2`: `partial`
- `L3`: `partial`
- `L4`: `partial`
- `L5`: `complete`

## Violations

- `L1_DIRECTION_PRECEDES_MULTI_METRIC_STRUCTURE` (high): direction max/median and parallel residual precede unresolved_edge_count; turn_residual and local_window_residual are absent from the global key
- `L2_AFTER_L3_IN_GLOBAL_KEY` (high): height_outlier_l1 (L3) is compared before evidence_regression (L2)
- `C5_MIXED_INTO_MANHATTAN_BUCKET_KEY` (medium): C5 plane parallel/orthogonal proxies are embedded in the best_manhattan_feasible key before unresolved/wall residual metrics
- `L2_BASELINE_ONLY_CANNOT_PREFER_CANDIDATE` (blocking): 2369/2389 C4 deltas are baseline-to-baseline zero diagnostics with no candidate projection variants; they cannot support candidate preference
- `L4_MANUAL_EVIDENCE_INCOMPLETE` (blocking): 2369 keep-distinct is projection-derived, while explicit column identity remains manual; 2389 lacks explicit column identity and keep-distinct contract
