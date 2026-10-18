# Independent personnel-model audit

## Outcome
The delivered continuous Q/T/difficulty calculations reproduce. This is an audit of statistical models on frozen audited inputs, not reconstruction of original collection/cleaning, a new blind test, or validation of interchangeable personnel categories.

- Frozen input replay: inventory 10,439; usable Q 7,302; ordinary manual 5,719 answers / 177 images / 22 buildings. Exact source-flat table reproduced.
- Q task identity is image, condition, reference ID, reference version. No duplicate task-worker rows. All ordinary-main references match current difficulty reference.
- Full profiles: 60 workers, 59 Q-supported, 57 source-T-supported, 54 supported at all three difficulties. Support means >=6 distinct tasks and >=3 buildings, applied separately by difficulty. Unsupported estimates must not be promoted to known classes or zeros.
- Independent matrix solver, using projected pseudoinverse rather than the delivered bordered-system solver, reproduces all 22-fold FE and joint20 B8L2/D10 coefficients within 2.29e-12.
- Independent source/target T fits reproduce all fold effects within 5.68e-14, with zero support mismatches.
- Delivered core run, fine-type augmentation, all 231 nested double-exclusion sets (27,720 rows), formal audit checks, and class-information controls were actually rerun in replay/. Ten relevant output tables match delivered tables within 1e-9, including labels and memberships exactly. Core replay intentionally skipped the old-version LOBO prediction series; original historical fixed-score/effect and separate-difficulty checks were rerun. Other report/efficiency/room weighting scripts were inspected where relevant but were not all executed. No full-nine-step or geometry/collection-pipeline claim.

## Verified performance
Relative squared error is computed against same-task other-person mean outcomes, after pairing exact common workers. The target is legitimate for relative peer prediction; it is not a prospective absolute score. Images are equally weighted within building, buildings equally weighted.

Independent results, using 20,000 paired building bootstrap draws:
- B8L2 FE -> joint20 overall: 1.264282748% improvement; CI [0.4393, 2.0985]%; 5,717 answers, 177 images, 22 buildings; 15 buildings improve.
- Hard B8L2: 2.456134259%; CI [0.0995, 4.5510]%; 980 answers, 31 images, 15 buildings; 10 buildings improve.
- Easy B8L2: -0.19765%; CI crosses zero.
- Hard D10: 2.41918%; CI [-0.0851, 4.7187]%; uncertainty crosses zero.
The larger bootstrap is an independent numerical sensitivity, not new independent data. Bootstrap resamples fixed LOBO building errors; it does not refit all models for each draw, and cross-validation training sets overlap. Intervals are conditional and do not cover adaptive model development, all multiple comparisons, or external-population transport uncertainty.

## Regularization control
FE versus joint20 is a clean zero-global-ridge comparison. Joint20 penalizes difficulty deviations, not a global worker mean. The optional ridge5_joint20 uses a ridge penalty on three coefficients per worker: writing theta_d=mu+delta_d yields 5*sum(theta_d^2)=15*mu^2+5*sum(delta_d^2). Therefore ridge5 versus ridge5_joint20 does not match the global shrinkage strength.
I independently fitted the appropriate no-difficulty ridge15 control. Against ridge15, ridge5_joint20 still improves B8L2 overall 1.04362% (CI [0.35355,1.78225]%) and hard 2.25185% (CI [0.14077,4.13370]%). This caveat does not invalidate the main FE/joint20 comparison or eliminate the modest difficulty signal. It should be corrected if presenting equal-regularization ablations.

## Classification conclusions
- Continuous global Q and partially pooled per-difficulty effects, their contrasts, support counts, and uncertainty remain defensible historical features for subsequent research.
- Keep absolute observed quality separately from relative task-adjusted Q. Treat Q3/QT as communication bins rather than natural types.
- Fine phenotype classes do not demonstrate incremental overall value over the finer Q3 x T3 control: B8L2 fine_dtype gain -0.01917%, CI [-0.98683,0.91069]%; merged fine classes -0.86739%, CI crosses zero. Their larger gain against coarser Q2 x T2 partly restores Q amplitude discarded by coarse bins.
- Adding class difficulty deviations while retaining continuous Q gives small gains, but these controls do not beat individual joint20. Fine classes can remain exploratory composition hypotheses, not established replacements for continuous profiles.
- Some fine classes have one or two workers. Apparent label stability (mean 94.8% over leave-building folds) is descriptive, not proof of worker interchangeability or out-of-sample type discovery.
- Difficulty specialist / relative-lift labels are historical comparisons, not absolute low-quality labels or causal adaptation claims.

## Time caveats
Source T uses 6,250 ordinary eligible time rows / 58 workers; target T uses 418 / 23 workers. Q eligibility is separate, appropriately allowing usable time when geometric Q is missing. Source T uses image/condition keys; target T uses exact reference-qualified keys.
All 440 available target-time inventory records are exactly the source time, so they are not independent replication. Each worker belongs to only one provenance cohort; origin-centering cannot identify a cross-source calibration. Keep T source provenance, support and missingness explicit, and never equate fastness with quality or causal efficiency. Do not combine Semi/scope/exclusion evidence into an invented overall score.

## Recommended next research design
Carry continuous Q, source-stratified T, per-difficulty theta/contrasts and support flags forward. Use single-building-out features at test time and double-building-excluded features for training rows in reverse classification, as already implemented and reproduced. Preserve no-difficulty and equal-global-regularization baselines, common-worker evaluation, building-cluster uncertainty, and unknown/sparse categories. Evaluate proposed classes through held-out composition/replacement outcomes before claiming class utility. Freeze any revised classification before evaluating on genuinely new outcomes; the present registration files alone do not establish independently timestamped preregistration.

## Files and reproducibility
- independent_model_audit.py: independently assembles model matrices and evaluates FE/joint, ridge5, ridge15 and ridge5_joint20; outputs INDEPENDENT_MODEL_AUDIT.json, independent_predictions.csv.gz, independent_comparisons.csv.
- check_time_nested.py: independent all-fold T solver plus five direct nested Q/theta refits; TIME_NESTED_CHECKS.json.
- compare_replay.py: delivered-versus-replay table comparison; REPLAY_COMPARISON.json.
- replay/: actual fresh outputs and original script receipts, including AUDIT_CHECKS.json and NESTED_FEATURE_RECEIPT.json.
- replay.log, nested_replay.log, independent_audit.log, time_nested.log: execution logs.
Original delivered outputs were not modified. All work stayed local in the independent/models directory; no external writes or new Work/Codex tasks were used.
