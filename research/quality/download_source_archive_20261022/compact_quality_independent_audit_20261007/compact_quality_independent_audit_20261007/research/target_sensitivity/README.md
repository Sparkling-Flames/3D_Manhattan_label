# Validation-target sensitivity

Start with `REPORT_ZH.md` for the Chinese report. This retrospective experiment freezes the original five scores, eligibility, calibration and common-training support, then checks different held-out numerical targets. Three exploratory fixed alternatives were declared before results: normalized LC, LC+reference T, and LC+intrinsic geometry G. No new geometry, semantic labels, learned model or weight search is added.

## Inputs and dependencies

Use Python 3.10+ with NumPy and pandas:

    python -m pip install -r requirements.txt

Extract the original compact numerical ZIP. `--source` accepts either the extracted `quality_compact_20261007` directory containing `results/`, or that `results/` directory itself. Only these five source CSVs are needed:

- `manual_scored.csv`
- `broad_lobo_pairs.csv`
- `broad_lobo_scales.csv`
- `broad_lobo_summary.csv`
- `natural_3d_alerts.csv`

The numerical compact ZIP works without images, raw annotations, browser access or the full geometry pipeline. Source files remain read-only. The scripts do not download or extract the ZIP automatically.

## Reproduce

Run from this directory, replacing the example source path with your extracted package:

    python run_experiment.py --source path/to/quality_compact_20261007 --out results_out
    python check_experiment.py --source path/to/quality_compact_20261007 --out results_out
    python independent_check.py --source path/to/quality_compact_20261007 --out results_out
    python write_report.py --out results_out

All four scripts accept `--out`. It is the generation destination for the main experiment and the existing result directory for the checks/report. Both checks write their audit results there. The focused check can omit `--source` to validate existing outputs alone; the independent audit requires the original numerical source. Source root and source `results/` paths are both supported.

Defaults retain the original folder layout: source `../../unpacked/quality_compact_20261007`, outputs beside the scripts. Explicit paths are recommended when copying this folder elsewhere. `RUNTIME.json` records the execution environment used for the delivered results; its machine-local paths are historical records, not required setup.

## Outputs and interpretation

- `target_score_summary.csv`, `target_coverage.csv`: all eight scores, three fixed panels, target ties and exact denominators
- `paired_effect_summary.csv`: paired contrasts, descriptive cluster percentiles and leave-one-building ranges
- `paired_effect_per_building.csv`, `leave_one_building_influence.csv`: building-level evidence
- `all_pairs_predictions.csv`, `all_pair_targets.csv`: individual comparisons and explicit target states
- `EXECUTION.json`, `CHECKS.json`, `INDEPENDENT_CHECKS.json`: completed execution/audit checks

CSV accuracy/effect values are fractions; the Chinese report converts them to percentages/percentage points. Headline accuracy averages pairs within image, images within building, then buildings equally. Target ties are retained and excluded from ordered accuracy. Prediction ties receive one-half on ordered targets; none occurred here.

Bootstrap percentiles describe reweighting observed building effects with fixed predictions. They are not population confidence intervals or evidence that pairs, workers or buildings were independently sampled.
