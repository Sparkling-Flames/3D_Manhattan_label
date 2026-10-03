# Lee fixed-panel exact finite-pool benchmark

Read `REPORT_zh.md` first. This independent exploration adds exact finite-pool
expectations and bounded exact-IoU slices to the frozen 12-image equal-weight BEV
study. It does not replace or mutate upstream prefix geometry, eligibility, GT,
source files, or source warnings.

## Reproduce

Tested: Python 3.12.14, NumPy 2.3.5, Shapely 2.1.2 / GEOS 3.13.1.
Matplotlib 3.10.8 is used only for figures; the numerical script does not need it.

From this directory, with these packages installed:

```sh
python -B src/explore.py --published-summary inputs/published_summary.csv
python -B src/test_formulas.py
MPLCONFIGDIR=/tmp/lee-exploration-mpl python -B src/make_report.py
```

The first script verifies the exact SHA-256 of `inputs/fixed_input.json` before
doing any work. It is the unmodified source input from commit
`b1ebab888fe8ac736548897f126a8bce7292c114`, path
`research/lee_tile_stage1_20261002/input.json`, Git blob
`9fdb7ba918cdffad23a24bf8ca017cf7c2e9f74b`. It contains the supplied anonymous
research records, not a new private identity export. The original source README
defines the original condition/gate strata and the fixed 16-permutation design.

## Scope and output

- All 12 groups, 177 original eligible independent votes, 15 fixed references
- Every nonempty subset of all six N<=9 groups (1,180 distinct member sets)
- Every k=1,2,N-2,N-1,N subset of the six larger groups
- 4,554 bounded exact member sets; 166 exact method/reference/k IoU summaries
- 492 all-k method/reference rows of exact analytic expected area, overlap,
  omission and extension, plus expected adjacent and member-pair *area* differences
- All 492 published 16-permutation means reproduced through an independent
  offline integration implementation (max difference 7.77e-16)
- 1,522 fresh current-member-only partitions checked against offline refinement
- 660 combinatorial formula tests; the first 8-person group's complete
  member-pair area comparisons also checked at all k

Full-pool cells are used only as an offline common integration refinement of a
known finite panel. Future votes never enter the current subset majority mask.
This is not a claim about predictive use of future geometry or generalization to
unseen people. No unconditional missing-geometry fallback drops failed members:
the program fails explicitly if an eligible footprint is invalid/unavailable.

`expected_...` area columns are exact combinatorial expectations up to geometry
and floating-point precision. `exact_iou_mean_when_enumerated` is blank for
unexhausted intermediate k. The conspicuously named
`ratio_of_expected_intersection_union_NOT_expected_iou` is **not** E[IoU].
Fixed-GT-area and fixed-full-pool-union normalizations are kept distinct.
Area-based member/adjacent differences are **not** the original Jaccard fields.

`inputs/upstream_warnings.json` preserves the original warning record unchanged.
`results/warnings.json` records this independent path's warnings. Their counts
need not agree because geometry operations and environments differ; zero warnings
on this path does not clear the upstream warnings.

`results/group_findings.csv` has the concise 12-group sampling error, reference-
independent D_U, and exact full-pool 50%-support area table. `figures/` contains two
visually inspected plots. `initial_results/`, if present in a working directory,
is superseded exploratory output and is not part of this final deliverable.

No original photographs were available. OOS and disputed-reference distances
remain reference agreement, not labels of human error or ability.
