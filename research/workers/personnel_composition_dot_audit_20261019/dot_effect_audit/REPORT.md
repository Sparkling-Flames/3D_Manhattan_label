# Independent composition-effect audit

Date: 2026-10-19. Audited package: personnel_composition_study_20261019. No original author summary function was executed to generate the independent numerical results below. Inputs are retained per-image/endpoint/event evidence, historical worker features, and independently reconstructed exact block requests. This is not a rerun of all 583,261 unique fusions; fusion and geometry correctness require the separate replay audit.

## 中文结论摘要

这轮结果的核心数值可信：六条主结果、897行构成汇总、1,064个保留的同背景换人事件、234行来源/Q控制结果及2,086条删人结果均通过独立重算，未发现汇总算错或分母偷换。

对当前这批人员，最值得保留的是“历史高Q类优于低Q类”的平均收益与小规模可互换性。即使限定同图、实际换1人或2人，高Q纯类的类内波动仍较低。但不能把混类的总体波动较大理解成混类天生不稳定：同图且同换2人时，7张可比图上混类的分数波动反而更小。

困难角色替换有正平均收益，也有明确反例：n17/m2的H1→H2为−2.445；现有来源/Q重叠不足，不能仅凭类别名称认定H2具有独立的“困难专长”。固定4名H2、8→9人的−6.509均值只覆盖26/30条可评分链；极端缺失分数敏感性区间为[−12.360,+0.140]，个别实际阈值损害可以确认，但整体下降需保留可评分条件。

近期优先继续用现有人员与图片，把同图、同公共成员、同实际换人数的比较做齐，再形成有限人员范围内可用的选人规则；新人员/外部新图验证属于以后扩大适用范围时的工作，不是当前发现必须先满足的门槛。

## Verdict

The reported composition-effect arithmetic and its denominators are unusually well preserved. I found no headline-effect, stable-flag, matched-swap, source/Q-flag, mixture-baseline, or highlighted leave-one-worker-out arithmetic error. The appropriately limited conclusions survive. The results do **not** establish unknown-worker generalization, category causality beyond the specific members, H2 specialization rather than general quality, a universally beneficial replacement, or an intrinsically less stable mixture.

### Independently verified

- All six headline effects reconstructed from side-specific per-image means; maximum discrepancy 6.3×10⁻⁹.
- All 897 frozen contrast aggregate rows reconstructed from 8,902 per-image contrasts, including image/building counts and signs. No repeated actual image within a stage/contrast.
- 1,064 selected block events checked against regenerated actual member sets: same actual core, exact A→B and A→C replacement m. No violations.
- All retained net and absolute score-difference arithmetic and main stable flags reproduce. C→B turnover is less than m in 24 events, correctly distinguished from A→B/A→C.
- All 234 control-subset rows independently reproduce from events. Historical-Q closeness and source flags independently recomputed from actual workers and historical features for all 1,064 events; no errors.
- All 574 mixture-best-pure rows independently checked against both original pure baselines; no errors or substitution of a single surviving baseline.
- All 2,086 selected leave-one-worker rows independently reconstructed by removing every actual event involving that person. Counts and means reproduce, including reversals.
- Both phases' nested chains: exact one-member set inclusion, endpoint Q difference, threshold difference and group means reproduce. All critical 2m→2m+1 transitions increase the recorded threshold by one.
- All 131 single-team within-composition cells retain missing variation rather than zero.

## 1. Headline means and uncertainty

| Comparison | Images/buildings | Recomputed building-equal ΔB8L2 | Exact empirical building-bootstrap 95% interval |
|---|---:|---:|---:|
| Q pure-high vs pure-low, n5 |43/6|9.871632479|[4.0185,15.1582]|
| Q pure-high vs pure-low, n9 |35/6|7.980031093|[0.9462,13.4205]|
| G2 vs G1 pure, n9 |42/6|6.404983541|[3.3527,9.7538]|
| R5 vs R2 pure, n5 |28/6|10.114092004|[5.8580,15.8734]|
| Hard H2 count2→3, n5 |6/5|12.691000130|[5.2605,25.7499]|
| Hard H2 count3→6, n9 |5/4|13.708526884|[1.7595,25.6575]|

The report's 2,000-resample intervals differ slightly from exact enumeration, as expected from Monte Carlo. This is not an arithmetic defect. Six or fewer buildings yield coarse, descriptive uncertainty; the bootstrap conditions on the chosen classes, rules, image support and finite worker cohort. It does not account for all historical exploration, labeling uncertainty or unseen-worker recruitment.

Heterogeneity remains material. Q n9 is −8.148 on X7HyMhZNoso but positive on the other five supported buildings. Hard n9 has building effects 3.520, 28.698, −0.00104 and 22.617. The negative hard image counted in the report is effectively a tie of −0.001 rather than a practically large reversal. Conversely, Q n9 includes an image loss of −16.838, so a positive average is not an individual safety guarantee.

### Missing-score sensitivity, not an imputation policy

The frozen scorer’s [0,100] range was verified directly in restored `research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py`, `checked()` lines38–45 and `score()` lines69–75: valid IoU I∈[0,1], the other inputs are nonnegative, and score=100I/(I+nonnegative terms), with I=0 mapped to0. A failed geometry has no defined score; only a hypothetical defined score can be bounded this way.

For the same attempted sampled teams and paired image support, allow every missing score to range adversarially over [0,100]. Retain image→building equal weights. This is a hypothetical sensitivity bound, not a definition that failed fusion has Q=0, and it does not repair missing structure.

| Comparison | Worst/best bound on average score difference |
|---|---:|
|Q n5|[8.033,10.699]|
|Q n9|[5.709,8.903]|
|G n9|[4.448,7.920]|
|R5 n5|[9.687,10.480]|
|Hard n5 count2→3|[9.795,15.795]|
|Hard n9 count3→6|[13.709,13.709]|

Thus missing scores alone, under that bounded-score hypothetical, cannot reverse these six supported means. It says nothing about excluded infeasible pools, unknown classes or unsampled actual teams.

## 2. Matched blocks: real evidence, conditional directions

Code design is sound for its stated estimand: A=core+outgoing, B=the same core+different same-class people, C=the same core+different-category people. A→B and A→C have equal real m. Net signed utility is C−B. B and C may overlap; they are not asserted to differ by m.

Independent validation results:

- Q low→high, n5/m2: +5.325 across 74 finite events/43 images/6 buildings. 54 events improve, 20 worsen; event p10 −5.752. Of 72 comparable A/B/C triplets, cross-class absolute Q change is greater in 45 and smaller in 27; paired building-equal excess is +2.920. Main stability is actually 25.14% within vs30.28% across: larger mean distance does not imply every stability functional worsens.
- Hard H1→H2, n5/m2: +14.135 across13/7/5. Eight improve and five worsen; event p10 −5.425. Cross-class absolute Q distance is larger in11/13; paired mean excess +13.110. Main stability5% within vs0% across.
- Hard H1→H2, n9/m4: +9.681 across10/5/4, eight improvements/two losses, p10 −6.478. Within main stability0%, changed12.5%, again demonstrating that means and thresholded rates are different statements.

Do not subtract separately available marginal means to obtain a paired effect when missingness differs. For example, Q n5/m2 marginal absolute changes are5.263 and8.256, but the correctly paired excess is2.920, not2.993. The code correctly computes per-triplet excess first. The same caveat applies to floor distances.

### Larger replacements and counterexamples outside selected highlights

The complete exact-stratum summary contains meaningful non-headline tests (these are retained summary evidence, not freshly fused events):

- Q low→high n13/m6: +6.307,38 events/28 images/6 buildings, p10+0.184; source matched+11.376 but only24/18/5.
- Hard H1→H2 n13/m6: +17.921,9/5/4, p10−8.520. Large mean does not eliminate severe tail losses.
- Q low→high n13/m2: −0.317,39/28/6; source matched−0.810,33/26/6.
- Hard H1→H2 n17/m2: −2.445,10/5/4; same result source-matched, p10−12.825.
- Q n9/m3 cross-minus-within absolute Q change is−4.227, and hard n9/m2 is−5.571. A changed class can produce less variation than a within-class replacement.

These invalidate universal monotonic replacement and universal “cross-class is less stable” claims. They do not contradict the package's more qualified average claims. Results at different n/m have different cores, sampled draws and sometimes image support, so they are not a controlled dose-response curve.

## 3. Within-composition stability and actual turnover

The report correctly gives finite-capacity warnings: R5 has only six historically supported members, so two pure five-member R5 teams can differ by at most one person. Sixteen of its28 validation cells contain just one team; the88.2% main stability pertains to the12 cells where distinct-member comparison exists.

I added an independent same-m, same-image comparison for Q n9 (building-equal):

| Comparison | m | Common images/buildings | High-class absΔQ / other absΔQ | High / other main stability |
|---|---:|---:|---:|---:|
|high vs low|1|31/6|1.525 /3.529|75.85% /58.01%|
|high vs low|2|19/6|1.808 /4.778|81.31% /48.94%|
|high vs3low+6high|2|7/5|3.593 /1.898|64.29% /63.33%|
|high vs3low+6high|3|9/5|2.172 /2.192|66.39% /63.33%|

The high-vs-low stability finding therefore survives stronger turnover/support alignment. But pure-high's overall |ΔQ|2.01 against mixture4.45 cannot be read as inherent mixture instability: the mixture turns over far more people on average, and the same-m common-image m2 absolute-Q ordering reverses. This secondary analysis is descriptive and post hoc. Same m and image still do not create matched exact cores; the separate block design addresses that question.

## 4. Source, Q and individual identity

G1→G2 n5/m2 validation falls from+1.531 (93 finite events/45 images/6 buildings) to−0.0788 source-matched (72/45/6), and−4.759 source-and-incoming-Q-close (5/5/4). This establishes weak evidence for a broadly useful incremental effect under these controls, not proof that the category has no utility.

No highlighted hard or R5 direction has any source-and-Q-close validation events. The historical hard Q used here is theta_hard, not simultaneous balancing of q_beta and theta_hard. The freeze mentions controls of both where supported, but the actual block implementation selects one domain-specific Q. Consequently there is no demonstrated quality-independent H2 specialization. Low support is a failed identifiability opportunity, not a negative estimate.

Verified person sensitivities:

- R1→R5 n9/m4: +8.426 before deletion; removing all W129 events leaves7 events/6 images/4 buildings, mean−0.4553.
- R5→R2 n5/m2: −5.992 before deletion; removing W126 leaves9 attempted events (8 scored)/7 images/4 buildings, mean+1.0875.

The deletion removes entire events and changes image/core support. It is a cohort-sensitivity test, not retraining or a controlled same-image causal effect of the omitted person. All2086 retained per-person results check numerically.

## 5. Mixture claims and exploratory selection

Both pure endpoints must be present and scored before defining the stronger per-image pure baseline. It is an outcome oracle rather than a prospectively implementable rule; this is clearly disclosed and correctly coded.

Validation mixed-minus-best-pure means independently reproduce: R5×4+R2×1 −1.452 (28/6); R5×3+R2×2 −3.709 (28/6); hard G1×3+G2×10 −6.100 (3/3); R1×3+R2×6 −3.116 and R1×4+R2×5 −3.737 (31/6 each); semi-old−1.972 (5/4); doorway−6.635 (2/2). All three supported G mixture images are negative. Positive local examples do not establish a general recipe.

Leakage assessment: I found no target-outcome adaptation in these summarization/design modules. Labels and validation specifications are fixed; breadth selection and13 highlighted block directions are post-discovery selections. The source code and freeze explicitly acknowledge repeatedly studied v2 data. A self-recorded freeze timestamp is not an externally certified preregistration, and building holdout with recurring workers is not external blindness. Numerous sizes, directions and difficulty slices must not be transformed into a collection of confirmatory significance claims. Package language is largely appropriately limited.

## 6. Nested threshold result has a distinct missingness caveat

Fixed four H2, adding H1 from8→9: mean−6.5094,5 images/4 buildings. Thirty chains were attempted;26 have paired scores, with18 negative and8 positive. Four lack a paired score: one loses evaluability and three regain evaluability. The reported mean is conditional on paired scores. On the same [0,100] sensitivity exercise, the overall bound is[−12.360,+0.140], so the negative mean is not fully robust to unknown score values. This does not invalidate concrete harmful native-vote mechanisms, but it limits aggregate language.

All tested critical chains increase the recorded support threshold by one, but adding a new person's geometry also changes the candidate geometry and votes. This is not a pure randomized intervention on threshold alone. Global R5 fixed6 has a positive validation mean+1.043 at12→13, further excluding a universal threshold-harm rule.

## Reproducibility artifacts

- `recompute.py`, `results.json`: headline arithmetic, exact bootstrap, missing-score bounds, block controls, mixture arithmetic, within-composition summaries.
- `check_full_tables.py`, `full_table_checks.json`: all897 aggregate checks and both phases' nested endpoint checks.
- `recompute_loow.py`, `loow_checks.json`, `independent_loow.csv`: actual-member deletion recomputation.
- `check_control_members.py`, `control_members_checks.json`: source/Q checks from actual members and historical features.
- `extra_sensitivities.py`: reproducible same-m/common-image, same-m event, large-stratum and nested missing-score sensitivity tables.
- `recomputed_block_controls.csv`, `same_m_comparisons.csv`, `larger_replacement_strata.csv`.
- `recomputed_mixtures.csv`, `recomputed_within.csv`, `same_m_common_image_stability.csv`, `loow_reversals.csv`.

Scope boundaries: raw full-grid cell means, non-highlight block aggregate means and non-case fusion geometry have not been independently re-fused here. Their support tables are evidence, not substitutes for a full fusion rerun. Derived sensitivities are explicitly post hoc and should not be relabeled as frozen validation.

## Recommended next experiments

1. **Prioritize existing-data, finite-cohort selection:** complete same-image, same-core and actual-m comparisons for the current supported workers. Freeze a practical rule within this finite cohort and compare its average utility, severe-loss rate and completion against a usable baseline. No new-worker study is needed merely to make bounded discoveries about this cohort.
2. **Same-core dose-response and mixture checks:** at several n, preselect common target images and core/member pools, and vary actual m under balanced sampling. Compare signed quality, paired absolute change, floor change, completion and harmful-tail frequency separately. Avoid reading unrelated n/m strata as a trajectory or treating the larger all-m mixture variance as an intrinsic mixture effect.
3. **Test specialization as an interaction where overlap permits:** evaluate H classes on matched easy/medium/hard conditions, controlling historical general quality and condition-specific quality where real overlap exists. Specify what would establish a condition interaction; if overlap remains absent, report non-identifiability rather than fit an extrapolating regression.
4. **Missing-outcome and threshold accounting:** report all attempted nested transitions, loss/restoration of complete output and paired-score means together. To isolate the threshold mechanism, use a separate diagnostic rerun that holds candidates/coordinates fixed and varies only the threshold; keep this distinct from the frozen main score.
5. **Later generalization validation, if desired:** after a finite-cohort rule is useful, freeze its classification/recruitment procedure before collecting new outputs, then hold out genuinely new workers and buildings. This addresses a broader generalization claim, not a prerequisite for current-cohort utility. Avoid selecting the better pure endpoint after seeing the target's outcomes when evaluating a prospective policy.

The primary study claims and the audit's new matched-m and missingness analyses should remain separately labeled. New analyses are useful falsification/sensitivity work, not new preregistered confirmation.
