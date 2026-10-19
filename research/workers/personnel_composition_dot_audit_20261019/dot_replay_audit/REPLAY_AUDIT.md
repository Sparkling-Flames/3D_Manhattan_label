# Independent restoration and numerical replay audit

## Result

No score, frozen-input, request-membership, or showcased geometry discrepancies were found in the completed checks. This is a newly executed replay, not acceptance of the package's pre-existing receipts.

- Frozen main: e572eb73bedc4fe9056df838e458bab83c3fa423.
- Scientific source: 82c6164b0d4630de5316199c92aa405930973168.
- Official bootstrap verified 824 source files and 519 retained archive files, then smoke-verified historical profile inputs. No old full experiment was executed.
- Python 3.12.14 with all requested numeric package versions. Missing Shapely 2.1.2 installed into a separate venv; initial default installation failed because the user-library location was read-only, and was not bypassed.
- Frozen snapshot SHA256: 83179b9842d06916b105d80ff181918c223e4fee2073f425f9825db124ec11d7.

## Completed tests and evidence

1. `quick/REPLAY_SUMMARY.json`: all seven cases and 21 distinct teams passed. Exact final geometry sequences; B8L2 and D10 deltas exactly zero. All 15 same-size pair diagnostics and saved mechanism transitions reproduced. Source and case files unchanged.
2. `requests/REQUEST_REBUILD_RECEIPT.json`: all 13 main manifests physically regenerated with byte-identical SHA256, exact per-request membership signatures, class counts and support. Ordered FINAL concatenation also byte-identical. Main totals: 589,990 request IDs, 583,261 distinct actual teams, 126 pools, 106 images, 12 buildings and 59 workers. FINAL is not added again.
3. `extra_team_replay.json`: 36 nonshowcase teams independently fused and scored, all tests pass at 1e-9. Maximum score difference 1.4210854715202004e-14. Includes 27 complete_conditional, four below_four, four no_connection and one invalid_floor; both phases and all three difficulty tiers. Deterministic SHA256(team_key) sample, first two per phase/difficulty/status stratum then fill to 36. Selection universe is the compact highlight-event arm table, not all 583,261 teams. This guards against showcase-only parity but is not an unbiased full-population audit.
4. `case_snapshot_and_full_chains.json`: every embedded frozen member record and reference field equals the restored full snapshot; full pool digests also match. Both complete displayed addition chains, 18 points in total, independently fused.
5. `chain_table_comparison.json`: all six chain transitions retained in the summary plot table match recomputed Q, D10, node, wall-coverage, corner-recall and IoU3D changes within 1e-9.
6. `actual_case_matching_comparison.json`: actual-case sensitivity check of raw angular node/adjacency diagnostics described below.

## Mechanism findings

C03 n8→9: fixed 4-vote identity group loses selection when minimum support rises 4→5. Old-observation coidentity partition unchanged (zero changed pairs), same group center and support. Node count 6→5, B8L2 94.6889845615→51.4037130105. n9→10 has no threshold increase or additional unchanged-group loss.

C04 n12→13: three unchanged 6-vote groups lose selection as minimum support rises 6→7; no old-observation coidentity changes. Nodes 7→4, while B8L2 rises 44.9069633116→64.6309808883. This is real local vote-threshold behavior and real divergence between the chosen quality score and reference-relative geometric retention. It does not establish semantic necessity or that every dropped node was correct.

The full C04 chain is nonmonotone: n6–10 have ten nodes, n11 has four, n12 recovers seven, and n13–15 have four. Thus the evidence supports particular local transitions, not a universal monotone rule that more people always remove detail. Entire C03 n4–11 chain also shows fluctuating quality before the n8→9 drop.

## Angular diagnostic sensitivity

`fusion_runner.reference_structure` uses a minimum-total-angular-cost Hungarian assignment and then applies 5° or 9° thresholds. This need not maximize threshold-qualified node matches. The newer footprint corner matcher in `geometry_diagnostics.py` correctly prioritizes admissible match count before distance.

On the actual 21 showcased teams (42 threshold comparisons), replacing the angular assignment with a maximum-cardinality-then-minimum-distance matcher changes no node-recall count. It changes three mappings. Two 9° adjacency recalls differ:
- C04 n12 team `...__b124e2d4dcddec411b86`: 5/10 edges becomes 4/10.
- C05 team `...__0fb4ae773cabb66670b7`: 4/8 edges becomes 3/8.

These are sensitivity results, not proof that the alternative adjacency score is correct: neither matching objective optimizes cyclic adjacency. Main B8L2, geometry and the footprint wall/corner diagnostics are unaffected. Do not describe raw adjacency recall as a uniquely established structural truth.

## Diagnostic interpretation boundaries

Code inspection confirms wall coverage unions projected segment intervals within a direction/tolerance slab, so collinear subdivision does not artificially improve coverage. It is recall-like and does not penalize extra walls. Corner recall is location-only with a >10° turn criterion; it does not require matching convex/reflex type or incident directions. Invalid/self-intersecting/degenerate rings produce missing diagnostics rather than zero. These are transparent reference-relative diagnostics, not semantic necessary-structure accuracy and not N1.

## Additional screen replay

The entire 14,187-team discovery screen was freshly fused successfully with five workers into `screen_runs/pools`: 51/51 pools, 14,187 new fusions, 134 seconds. Completion receipt: `screen_runs/RUN_SCREEN_REQUESTS.json`. Basic counts: `screen_basic_counts.json`. The class-learning audit is independently recomputing headline regressions and the eight-field finite mask from these fresh outputs. No full 583,261-team fusion is claimed.

## Reproduction paths and logs

- Source checkout: `../source_repository`.
- Full restored root: `../restored`.
- Numeric interpreter: `../replay_env/bin/python`.
- Restoration: `bootstrap.log` and restored `BOOTSTRAP_RECEIPT.json`.
- Numeric replay: `quick.log`; extra sample: `extra_replay.py`, `extra_replay.log`.
- Requests: `requests.log`; chain checks: `check_case_snapshot.py`, `compare_chain_table.py`.

Source scripts were inspected before execution. No upstream repository files, branches, commits, or remote state were changed. Local sparse-checkout metadata was expanded to restore dependencies. A direct bulk-blob fetch attempt failed; normal sparse checkout succeeded and subsequent full hashes verified all consumed source bytes.
