# Independent class-learning audit (new 2026-10-20 package)

## Verdict and evidence levels

The class-learning implementation supports useful conditional personnel hypotheses. It does not establish universal interchangeability. No direct discovery/assessment outcome input into the inspected forward fits or reverse training-fold graph construction was found. The source-only explanation does not account for R_new2 because all its 35 members are new-source, but ordinary quality remains an important explanatory correlate. This audit does not upgrade the already explored assessment images into a fresh holdout.

Executed independently from the package's prior audit receipts:
- Read and imported the complete forward candidate builder after inspection; rebuilt every definition from the packaged feature table. All 188 methods, 11,280 label rows, class IDs, known flags, eligibility, reason, domain, source and train key match exactly. All partition hashes match.
- Feature table has 60 workers and 328 columns. This is column count, not 328 independent measured behavioral traits: identifiers, support counts, booleans and overlapping condition summaries are included.
- Recomputed 500 forward LOBO ARIs from raw saved per-fold labels and full labels, matching all reported fold ARIs.
- Compared every reverse manifest class membership with its labels: 768 legacy candidates (555 valid) plus 1,040 mixed candidates (752 valid), total 1,808. These are attempted algorithm/representation/K/domain definitions, not 1,808 successful or independent classifications.
- Verified history/discovery/assessment building sets are disjoint (10/6/6).
- Enumerated all 1,576 supplemental history anchors: exactly 359,916 unique physical endpoint pairs, zero within-supplement duplicate endpoint pairs. Adding 122,082 legacy exact-background training pairs gives the advertised 481,998 training pair observations. The separately loaded 7,272 nested pairs are excluded from learning by `learning_panels`. These observations share endpoints, cores, images and buildings and are not 481,998 independent experimental units.

Receipt/code: AUDIT_RECEIPT.json, audit_learning.py, forward_lobo_recomputed.csv. Raw forward features and the selected original R_new2 reverse graph/full/ten-fold fits have now been independently reconstructed from restored inputs and fresh native history geometry; see closure receipts below. The other 1,807 reverse candidate definitions were membership/manifest audited, not all refitted.

## Code audit

### Forward
`forward/audit_and_features.py` filters d/ex to history buildings before feature estimators, checks inherited features against the frozen prior table and verifies source-specific time effects against a dense constrained worker/task OLS. Conditional geometry/quality and time fields have explicit task/building gates. The fitted effect can include below-gate workers as nuisance data; below-gate estimates are not assigned as supported labels.

`forward/build_candidates.py` defines 188 candidates using history feature values; complete required opportunities are mandatory for multivariate fits. Scaling is within current eligible history cohort, robust IQR/MAD fallback, clipping, equal feature-domain weights. Scalar quantiles are engineered bins; balanced medoids imposes near-equal class capacity. These are not discoveries of intrinsically separated natural populations. Historical-Q class naming does not change membership. The candidate capacity routine reads target membership metadata, but shortlist eligibility uses history-capacity fields only; target metadata access is not target outcome fitting.

Unknown workers retain unknown labels and may appear only as fixed background. No zero-imputation of missing required behavior was found. The coarse/refine method retains low-Q workers without requiring high-branch T fields, which is deliberate and explicit.

### Reverse
`reverse/learn_swap_types.py` loads only history event files, checks actual pair identities/conditions and recomputes strict/main/wide threshold stability. The nested panel is excluded from `old` training data. Five two-building folds are deterministic building-ID hashes. Each fold graph and its empirical shrinkage center/worker/pair eligibility use only remaining training buildings. `pair_building_table` is safe to subset after aggregation because its rows never pool buildings.

Worker gate: >=4 images and >=3 buildings. Pair gate: >=3 images and >=2 buildings. Unknown pairs have zero graph weight; complete linkage uses pessimistic unit distance. Pair estimates shrink toward training supported-pair mean by one equivalent building. Minimum class size is four; known-pair coverage gates are explicit. Within-class weighted risk plus a small size-balancing penalty is heuristic, not exact partition optimization or a guarantee of transitivity.

The algorithm distinguishes original missing continuous distances from an explicitly named failed-attempt loss of one. This is acceptable for that declared loss, but it must not be described as an observed distance. New corner-distance work must preserve this distinction and report same-count opportunity separately.

Same-background evaluation is fairly matched: within/between exist on each retained core, then background -> n -> image -> building averaging. Baseline pairing further intersects anchors where BOTH candidate and baseline have within/between opportunities. This avoids obvious candidate/baseline anchor mismatch. However class-level pair opportunities vary, so a pooled advantage does not guarantee every class or member is useful.

The source-conditioned `context_joint` candidates center against the full-source background graph before filtering source. This is training-only other-source influence, not fold leakage. None of the 15 selected source-conditional paths uses that representation; package qualifications disclose it.

### Selection and uncertainty
Full-history candidate K range uses full-history support; fit checks each fold's minimum size, so held-out outcomes do not form labels. History CV is both a selection instrument and a reported result across many candidates. Thus internal CV performance is selection-biased evidence, not an independent final validation. `select_mixed_candidates.py` hard-codes the selected ten using support/diversity judgments and CV scores; it is not simply a deterministic predeclared argmax. The later discovery-direction selection and target tests must carry their own multiplicity/selection status.

## R_new2 specifics

Method: R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1.
- Classes: C01 21, C02 14; every member is new-source.
- Training observations in its source-restricted domain: 303,421; this is not the full mixed total.
- Saved LOBO ARIs: seven 1.0, two 0.8857255832, one 0.7782082707. Mean 0.9549659437. No support loss in those ten saved fits. ARI reflects label agreement under dropping a historical building, not within-class replacement stability, accuracy or target generalization.
- History inner-CV within main stability 0.65923048 vs between 0.60951115: gap 0.04971933 (4.97 percentage points). Remaining within wide-threshold bad rate 0.21431073. The partition is stable, while replacement outcomes retain substantial variation.
- Descriptive history Q means C01 +5.47597 vs C02 -6.19031, Q eta-squared 0.48091647. So 'no Q in geometry fit' does not mean 'independent of Q'. C01/C02 descriptions should state higher/lower historical Q and mild point-count tendencies without converting the labels into guaranteed ability ranks.
- Same-K Q-only benchmark on matched history anchors: main within gain +0.00613813, main gap gain +0.01256830; geometry within gain +0.00668316, geometry gap gain +0.01367991. These are modest increments over Q-only.
- Source×Q-tertile-preserving random control (40 draws): main gap increment mean +0.02002070, draw p05 +0.01133353, p95 +0.02647730. This is useful coarse-Q sensitivity, not exact adjustment for continuous Q/tails/difficulty; draw quantiles are not image/building confidence intervals or multiplicity-corrected p-values. New-source-only domains cannot yield a meaningful source-only within/between baseline, correctly recorded unavailable.

## Scope, Semi and efficiency

The packaged features show: old confirmed-error nonedit support 0; new reported-error nonedit support 28; old edit support 24; new edit support 27; scope propensity support 35. Condition-specific Semi scope support is 0 for both sources. The code retains these unavailable models as failures rather than declaring absence of behavior.

Scope is response propensity, not OOS decision accuracy. Compatible in-scope adjudication cannot estimate bidirectional OOS sensitivity/specificity. Semi old confirmed error and new reported error are different evidence levels. Editing does not prove correcting; nonediting does not prove blind trust. Final Semi quality cannot establish initialization-to-final net improvement where initial reference-compatible geometry is missing. Source-specific log-time effects must not be read as cross-source absolute speed or causal productivity.

## Recommended next experiment, frozen before fitting

Use the new same-corner continuous geometry distance on historical actual endpoint pairs and fit a bounded K=2/3/4 mean/tail family. Train only on historical buildings, retain minimum opportunity gates, exclude unknown/mismatched geometry from conditional distance rather than assigning zero, and expose structural mismatch/failure as separate outcomes. Preserve full candidate/failure ledger. Compare R_new2, fold-rebuilt Q/T and capacity-matched random labels on identical anchor support. Discovery may select a coarse or fine conditional candidate; reused assessment is explicitly internal replication. Report member influence, per-class relation coverage, n/background sensitivity and simple descriptive feature differences. Do not tune until a favorable class appears.

## Completed raw-feature rebuild update

The external sources were restored and hash-checked. Running the inspected portable forward reconstruction now reproduces all 60×328 feature values (absolute tolerance 1e-9), all 11,280 labels, all 188 method definitions, partition/member sets and metadata capacities exactly. Receipt: full_forward_rebuild/FORWARD_FULL_REBUILD_RECEIPT.json. This supersedes the earlier feature-rebuild limitation. H20 geometry reconstruction and selected R_new2 refitting have also completed. A separate five-fold Q/T rebuild matches all saved eight-building Q values and supplies leakage-free T controls (FOLD_QT_REBUILD_RECEIPT.json).

## Completed original reverse refit closure

Fresh frozen native fusion reconstructed all 31,539 H20 teams in 81 pools. Independent extraction recreated 359,916 supplemental pair metrics, then the inspected original reverse learner reproduced R_new2 full membership (ARI 1) and every one of its ten leave-one-building labelings exactly. Mean refit ARI is 0.9549659437205102. Receipt: ORIGINAL_RNEW2_FULL_REFIT_RECEIPT.json; per-fold results: original_Rnew2_lobo_refit.csv. This closes the originally pending selected-class refit, without implying all 1,808 attempted reverse definitions were independently refitted.
