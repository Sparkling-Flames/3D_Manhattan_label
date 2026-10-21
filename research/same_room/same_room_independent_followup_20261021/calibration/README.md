# Independent personal-Q calibration on frozen same-room supports

## Result

This is an independent repository-input calculation, **not an exact reproduction of the inaccessible newPro 47 MiB package**. Its reported 11.116 is not adopted as a verified result.

Primary matched-history comparison: Manual ordinary-room B8L2, all origins, maximum history, equal-building MAE **11.144709** versus same-person source **12.363659**, an improvement of **1.218950**. This uses exactly the source images on which that person contributed for both predictors.

A distinct expanded-source variant uses additional peer-only history images where that person is absent and obtains **11.125810**. That is a different information budget, not an exact matched-observed-history or newPro protocol reproduction.

Full comparison:

| Method | MAE |
|---|---:|
| Same person's source Q | 12.363659 |
| Person's out-of-building Q | 15.402337 |
| Fixed 50:50 blend of those two | 12.589613 |
| Source peer mean only | 12.694743 |
| Expanded-source peer mean + out-of-building task-relative Q, clipped | 11.125810 |
| Same calibration without clipping | 11.126112 |
| Matched-history calibration using personally observed source images | **11.144709** |

Support is 7 buildings and 44 distinct target images, not 140,357 independent observations. Those 140,357 B8L2/all rows are repeated split/person/target observations. All 480,632 frozen feature rows across B8L2/D10 and all/v1/new are retained before fixed-across-m aggregation; no missing residuals occurred on this support. Reconstructed legacy target, source, and out-of-building personal baselines agree within 5.7e-14.

At minimum-majority history the matched-history calibrated MAE is 11.169614 versus 12.494621 for same-person source. The expanded-source MAE is 11.140405. D10 matched-history maximum-history sensitivity is 10.401782 versus 11.550118 (expanded-source: 10.362987). New-origin-only matched-history B8L2 is 10.876998 versus 12.501551 (expanded-source: 10.750084); v1-only matched-history is 11.400525 versus 11.718293 (expanded-source: 11.493596) (v1 has 6 buildings/33 images). Origins are separate evaluations, not independent replicates.

The following expanded-source figures are labeled separately from the primary matched-history comparison. Both variants are retained in every summary, including paired and leave-one-building-out summaries.

## Important limitations and adverse sensitivity

- Primary matched-history calibration improves in 6/7 buildings; VFuaQ6m2Qom worsens by 0.362127. Its leave-one-building-out aggregate differences remain favorable, from -1.482463 to -0.928984.

- Expanded-source calibration improves versus own-source in 6/7 buildings. VFuaQ6m2Qom worsens from 10.011160 to 11.160733. It is not a universal building-level improvement. Omitting each building in turn leaves the overall calibration-minus-own-source MAE difference between -1.635752 and -0.894129; the average advantage is not attributable to one building alone.
- Bottom-quartile persons by **external task-relative Q** improve from 13.677849 to 11.860874 for matched-history calibration (11.813780 expanded-source) at maximum history. This subgroup uses no target outcome to identify persons.
- For the retrospective **actual target Q < 50** subgroup, matched-history calibration instead worsens from 23.442895 to 25.718757 (expanded-source: 25.985473); out-of-building personal baseline is 21.735271 and half-blend 22.337303. Matched-history calibration's signed bias is +25.643323 (expanded-source: +25.985473): this method substantially overpredicts genuinely low-Q targets. This subgroup is an evaluation diagnostic, never a predictor or admission rule.
- Clipping accounts for only 0.000302 of the B8L2/all aggregate improvement. It is not the explanation for the result.
- Reference-evaluated source Q is required. This is not a no-ground-truth deployment predictor. Stable person effects plus source-room average level do not identify a particular target-view failure.
- No fitted coefficients, hyperparameter selection, fusion recomputation, personnel reclassification, production changes, or Semi transfer were performed. The frozen personal-Q supports are Manual only.
- Seven buildings are a small, selected support; no population-wide significance or causal claim is justified. Leave-one-building-out **summary sensitivity**, not model training, is supplied.

## Definition and anti-leakage checks

The source feature averages peer Q equally across the exact strict-majority history images from the saved splits. On each image the predicted person is excluded from the peer mean. If that person is absent on a source image, the complete eligible peer mean is used. The primary matched-history observed-source variant averages only source images on which that person contributed. The expanded all-source variant has extra peer-only information whenever the person did not contribute to all history images; it must not be described as an equal observed-source budget.

For the person offset, select only saved training-admitted, Manual, ordinary-room, current-binding, quality-usable records **outside the target building**, within the selected origin. On every such image subtract the other admitted persons' mean Q from the person's Q, then average those residuals over that person's supported outside-building tasks. A singleton has an unknown residual, not zero. Prediction is source peer mean plus this offset, with a fixed [0,100] clip in the principal variant.

Evaluation follows the existing order: average repeated splits per target/person/group/m; retain persons available at every eligible m in that group/target; average persons within target/group; average overlapping groups within image; average images within building; average buildings. All methods use identical paired rows. The target is excluded from history, and the target building is excluded from the offset and personal baseline. Missing values are never filled with zero.

## Reproduction and artifacts

Run from repository root:

    python -m tools.thesis_main.analysis.same_room_calibration_review_20261021
    python -m unittest tests.test_same_room_calibration_review_20261021

- `METHOD.json`: definitions, exact input hashes, numerical source-reconstruction checks
- `support_checks.csv`: row support, reconstruction differences, clipping counts
- `worker_targets.csv.gz`: auditable repeated-split-aggregated personal errors
- `summary.csv`: all origin/metric/history/subgroup summaries
- `building_metrics.csv`: per-building errors and bias
- `paired_building_comparisons.csv`: paired per-building MAE differences
- `leave_one_building_out_sensitivity.csv`: robustness of aggregate difference to omitting one building

The five critical unit tests cover exclusion of self from peer means, observed-source versus expanded-source budgets, outside-building history and target-score perturbation invariance, singleton missingness, saved admission exclusion, and building-equal aggregation. Actual-data assertions additionally verify every split is strict-majority, history/target disjoint and complete for its group, unique image/person rows, complete saved admission, and exact numerical agreement with the frozen legacy features.

