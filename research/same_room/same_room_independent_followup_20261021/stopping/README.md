# Independent source-only stopping review

This is an independent analysis of the repository's **124,924 actual replay nodes**, not a reproduction or refutation of the inaccessible newPro package. In particular, this rule has **no target-completion fallback**; it differs from the reported newPro geometry-completion fallback. The archived `complete_evaluable` flag is a quality-evaluability gate, not an established pure-geometry deployment contract, so it is never used to choose or revise the selected prefix. No fusion was approximated and no target quality was used to choose a prefix. Ordered prefix membership was checked against `REPLAY_ORDERS.json.gz` for every node.

## Design and limits

- Primary: full available worker pool; `cap16` is a separately labeled sensitivity. The six whole groups have mean full pool size **16**, not universally 16 workers.
- For each strict-majority source-view combination and held-out target, choose the earliest evaluable prefix whose source mean quality is within **0, 1, 2 or 5 points** of the maximum source mean quality over that source curve. All selected source views must be evaluable at a candidate prefix. No available source prefix means no choice, not a target-informed fallback.
- These are **retrospective source-reference-informed rules**, not online no-ground-truth stopping. They inspect the entire source curve. The cost is target prefix workers only; **source reference establishment, source curve acquisition and their time are not counted**.
- Fixed budgets are prespecified at 1, 3, 5, 7, 9, 12, 16, 20 and 30, plus terminal pool. Each budget is capped to the available pool and horizon, so all policies use the exact same groups and attempted cases. k=2 is excluded because the source replay defers two-person sorting.
- `minimum_majority` and `maximum_history` are reported separately. `all_m_pooled` is a combination-weighted sensitivity, not an equivalent history budget. Actual source-view counts appear in `target_summary.csv.gz` and `support.csv`.
- `all_attempts` preserves missing outcomes and reports completeness. Its mean Q is available-case, so a quality difference alone is not a fully paired comparison. `common_complete` requires every candidate prefix on **all group views** to be complete, invariant across policies and history budgets. It is a conditional diagnostic, not an estimate for discarded paths.
- Equal-group estimates first average target-level summaries equally within group. Equal-building estimates then average groups equally within each building, then buildings equally. Weighted `target_q10` is an **average of target-level 10th percentiles**, not a pooled 10th percentile. Case-weighted summaries are also retained.
- Split-target-path cases are repeated evaluations of the same paths; they are not independent rooms. Coverage subsets overlap and are not additional independently discovered rooms. Thresholds were not selected by held-out target outcomes; all four are reported. Pareto flags are descriptive on the prespecified comparison set, not held-out policy optimization.

## B8L2 primary result: all attempted paths

The main coverage-aware result uses every attempted path, retaining missing target outcomes. Whole-group, full-pool, minimum-majority, equal-building: **31,232 split-target-path evaluations from 1,536 replay paths / 6 groups / 6 buildings**. Within-2 uses mean n6.703, available-case Q87.522, completeness98.44%; fixed7 uses n7, Q87.055, completeness98.77%; terminal pool uses n16, Q88.268, completeness100%. Mean quality favors within-2 over fixed7, but missingness is slightly higher, and quality averages use available outcomes rather than a missing-outcome penalty. This is not proof of uniform improvement.

## Conditional common-complete diagnostic

Whole-group, full-pool, minimum-majority, equal-building (each group here is in a separate building):

| Policy | Mean target workers | Mean target Q | Mean target q10 | Fraction losing >5 Q vs terminal |
|---|---:|---:|---:|---:|
| Within 0 | 11.512 | 89.921 | 84.219 | 7.61% |
| Within 1 | 8.088 | 89.270 | 82.698 | 12.34% |
| Within 2 | 6.580 | 88.587 | 80.101 | 17.06% |
| Within 5 | 4.708 | 87.026 | 76.488 | 26.37% |
| Fixed 7 | 7.000 | 87.433 | 81.636 | 18.20% |
| Terminal pool | 16.000 | 88.268 | 88.268 | 0.00% |

This table uses the exact same common-complete cases: **6 groups / 6 buildings / 1,160 of 1,536 original replay paths**, yielding 29,891 repeated split-target-path evaluations per policy. Attrition is concentrated in MV0001 (93/256 retained) and MV0003 (43/256); the other four retain all 256. The fixed1 anchor is mean Q75.493 at one worker. Source within-2 dominates fixed7 in mean cost/quality on this conditional support, but its lower-tail average is worse. It does not establish uniform risk improvement.

On all **31,232** attempted minimum-majority split-target-path cases, within-2 is mean n6.703 / available-case Q87.522 / completeness98.44%; fixed7 is n7 / Q87.055 / completeness98.77%; terminal is n16 / Q88.268 / completeness100%. Maximum-history conclusions are similar (common support: within-2 n6.596/Q88.613; all attempts: n6.718/Q87.548). The stronger common-complete Q result should not be generalized to discarded paths.

Coverage-subset results remain separate: **14 overlapping subsets / 3 buildings / 1,230 replay paths**, all candidate nodes complete. Minimum-majority, full-pool, equal-building: within-2 n4.350/Q89.052 versus capped fixed7 n5.275/Q88.893; however >5-point terminal loss rises to **13.40% versus 10.50%**. Terminal pool is n7.608/Q90.162. Cost savings do not imply uniformly safer target outcomes.

## D10 sensitivity

The D10 source rule is recomputed independently, with unchanged prespecified thresholds. On whole-group minimum-majority all-attempt support: within-2 n6.394 / Q89.323 / completeness98.42%, versus fixed7 n7 / Q88.757 / completeness98.77%. Mean target-level q10 is worse (81.976 versus 83.294); >5-point loss versus terminal is also slightly worse (15.66% versus 14.91%). Common-complete results are n6.205/Q90.255 versus n7/Q89.100, again with worse mean target q10 (82.975 versus 83.810). D10 therefore supports the same limited conclusion: mean cost/quality gains do not establish uniform lower-tail or completeness benefits.

## Artifacts and reproduction

- `summary.csv`: support, history budget, panel, horizon, policy and weighting summaries.
- `group_summary.csv`, `target_summary.csv.gz`: hierarchical audit details.
- `support.csv`: source-view budgets and common-complete path counts.
- `pareto.csv`: mean cost/quality dominance on common-complete supports only.
- `MANIFEST.json`: input hashes and analysis contract; `VALIDATION.json`: executed checks.
- `d10_sensitivity/`: separately recomputes policies using D10 source curves and evaluates D10 target quality. This is metric sensitivity, not cross-metric evaluation of frozen B8L2 choices.

Run from repository root:

```sh
python tools/thesis_main/analysis/same_room_stopping_review_20261021.py
python tools/thesis_main/analysis/same_room_stopping_review_20261021.py --metric D10 --output research/same_room/same_room_independent_followup_20261021/stopping/d10_sensitivity
python -m pytest tests/test_same_room_stopping_review_20261021.py -q
```

Full policy-case export is reproducible with `--save-cases` and is intentionally not published by default. Seven focused tests passed using the available recovered Python environment. An initial exhaustive baseline export exceeded memory; the final compact prespecified comparison completed successfully. Existing inputs and production code were not modified.

