# Independent Part A assessment: estimands, calibration and policy

Read: full REPORT_ZH.md (384 lines), assessment registration and evaluation/calibration/policy code. This note does not certify every input, original fusion or all statistical results; parallel numerical audit owns those checks. Source root: extracted/work_personnel_typing_A_20261019.

## Main judgment

The new work delivers real forward/reverse partitions, and properly limits their use. Its cautious conclusion is defensible: no reliable interchangeable personnel classes yet. This is more than the prior pair-relation table. It does not establish that every future multivariable classification is futile.

Three substantive methodological qualifications:

1. **Prediction objective is not interchangeability.** `reverse/selection_common.py` calibrates arbitrary within/between probabilities, without requiring within-class stability to exceed between-class. `assessment/evaluate_common.py` selects/evaluates Brier risk on this bit. A class can score better by predicting that its members are less interchangeable. Independent inspection of saved calibration found main reverse within < between in 65/264 outer-fold × k × difficulty cells (264 = 22 × 4 × 3); forward42, swap12, oldQT28. Main reverse k16 hard is negative in11/22 folds, mean within−between −0.0395; k24 hard18/22, mean−0.0390. These overlapping-fold counts are descriptive diagnostics, not independent trials. Consequently the +0.000725 Brier improvement does not prove the user's desired class property.

2. **Class-count search starts at four.** Only K=4/6/8/10 are candidates; all28forward/64reverse candidates lie within oneSE. The code's standard error is absolute building-risk variability, not the paired candidate-risk difference. This is a legitimate predeclared conservative selection heuristic, not a demonstration that all candidates are equivalent or four is optimal. Minimum4 plus simplicity preference makes four the default. Main reverse1/39/18/1 suggests that two/three groups and abstaining outliers deserve a prospectively defined comparison; not retroactive reclassification of test cases.

3. **Intervals condition on the fitted crossvalidation outputs.** unit_summary bootstraps fixed per-building heldout scores and does not refit models in bootstrap replicates. It accounts for within-building repeated events but not all uncertainty of learning future labels from a new training sample; training folds overlap heavily. It should be described as a building-resampling uncertainty summary for the frozen retrospective procedure, not universal guarantees for future workers or cohorts. Many exploratory k/domain/method comparisons are unadjusted. Tiny isolated positive intervals are signals, not acceptance gates.

## Calibration and training isolation

`assessment/evaluate_common.py:reproduce_predictions` excludes heldout building from calibration and uses only Pro_exact_fixed_background_v1 training events. New A_nested_even_v1 events are never calibration input. Priors in selection_common are formed from that passed training frame. No target-building calibration leak found in these functions.

The same outer-training labels are applied to their own training events for calibration; there is no additional cross-fitting of relation labels inside calibration. Reverse swap labels were learned using those same training outcomes, so training calibration separation can be optimistic. The actual outer heldout evaluation is nevertheless legitimate for this whole fitted pipeline; this is not test leakage or a reason to discard all results. A bounded diagnostic is to compare cross-fitted relation calibration, preserving outer isolation and fixed methods, before blaming non-transfer solely on the class structure.

## Direct matched effect versus Brier

The new nested panel has one entrant pair per exact background; it permits identical-event paired method prediction comparison, but not a within-versus-between class contrast under the identical new background. That contrast exists in the original panel where multiple candidate pairs share backgrounds. Thus new-background predictive transfer and new-background interchangeable-class separation are distinct claims. Report correctly says this in NESTED_INTERPRETATION. Future controlled background design should freeze common background first, then include both relation types without selecting on test outcomes.

The source/cohort confound is substantial but not proven causal. Overall class performance and Q-near incremental performance answer different estimands; retain both. A zero-crossing Q-near or cohort-adjusted interval is inconclusive, not proof that every class signal is merely Q/cohort. Pair coassignment sensitivity is meaningful, whereas stable algorithm/K alone says little about stable members. 22 overlapping folds are not 22 independent confirmations.

## Independent QT-versus-Q policy calculation

Using identical event IDs in COMMON_EVENT_ANALYSIS_INPUT.csv.gz and LAST_SEAT_CHOICES.csv.gz, new k16 panel has4080events. QT vs Q supports4062decisions, changes650choices; Q difference available4001, source-time difference3464. The published +0.00360775Q and−13.42281889seconds building-equal means and intervals reproduce.

A joint known-Q-and-source-time subset has3410events. Building-equal ΔQ=+0.02696195, 2000-bootstrap interval[-0.09062002,+0.14922512]; Δtime=−13.44197597seconds[-18.16087093,−8.99182519]. Different separate denominators therefore do not reverse the mean tradeoff.

Among650changed choices,636have both Q available:62lose >2Q,75gain >2Q; maximum loss38.43319355Q. Three changed choices lose completeness and three restore it. On557changed choices with joint quality/time, ΔQ=+0.05830[-.44584,.55612] and Δtime=−86.17425[-126.76126,−54.12206]. These are different conditional estimands, not a replacement for all-policy opportunities. The policy is an average observed source-cost tradeoff, not per-case safety or verified same-target total cost.

Worst observed policy Q-loss event: Aevt_83f471d12f5b752e62683bd5, image zsNo4HB9uLZ_faad06c7cb2b4a6f9220e7f6f87c800b; ΔQ−38.43319, Δsource seconds−79.273. This is a retrospective diagnostic, not a new personal error judgment.

## Bounded next step

Do not respond by expanding features/K indefinitely. Keep continuous Q/T portraits and clearly exploratory partitions. Finish Part B's already planned common-background, adjacent odd/even and vote/connection mechanism acceptance; no redundant new task. A subsequent predeclared type-selection criterion should prioritize coverage plus upper-bounded class-internal failure/large-change risk and a matched cross-minus-within effect, with Brier secondary. Include K2/K3/no useful partition and unknown/outlier abstention. Define acceptable risk before testing, keep overall and Q-near/cohort controls separate, and use a genuinely new holdout or plainly label another use of current data exploratory. Current records cannot support universal scope accuracy or new-Semi error-correction quality without initialization geometry.
