"""Audit supplement for full uncertainty data-mining v5.

This script does not overwrite v5. It materializes:
1. multiplicity-corrected image-feature association screening;
2. explicit feature-alias diagnostics;
3. task-level / building-cluster bootstrap quality-risk sensitivity;
4. power under the currently observed Semi entropy effect;
5. a machine-readable calculation-mode audit.

Run:
python -m tools.paper_a_manhattan.full_uncertainty.audit_v5_calculation_modes
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"
DEFAULT_OUTPUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5_audit_20260822"
SEED = 20260822


def holm_adjust(values: pd.Series) -> pd.Series:
    p = pd.to_numeric(values, errors="coerce")
    result = pd.Series(np.nan, index=p.index, dtype=float)
    valid = p.dropna().sort_values()
    m = len(valid)
    running = 0.0
    for rank, (idx, value) in enumerate(valid.items(), start=1):
        adjusted = min(1.0, (m - rank + 1) * float(value))
        running = max(running, adjusted)
        result.loc[idx] = running
    return result


def bh_adjust(values: pd.Series) -> pd.Series:
    p = pd.to_numeric(values, errors="coerce")
    result = pd.Series(np.nan, index=p.index, dtype=float)
    valid = p.dropna().sort_values()
    m = len(valid)
    running = 1.0
    for rank, (idx, value) in reversed(list(enumerate(valid.items(), start=1))):
        adjusted = min(1.0, float(value) * m / rank)
        running = min(running, adjusted)
        result.loc[idx] = running
    return result


def two_sided_normal_power(effect: float, standard_error: float, alpha: float = 0.05) -> float:
    critical = stats.norm.ppf(1 - alpha / 2)
    noncentrality = abs(effect) / standard_error
    return float(stats.norm.sf(critical - noncentrality) + stats.norm.cdf(-critical - noncentrality))


def multiplicity_audit(source: Path) -> pd.DataFrame:
    frame = pd.read_csv(source)
    frame["p_holm_global"] = holm_adjust(frame["permutation_p"])
    frame["q_bh_global"] = bh_adjust(frame["permutation_p"])
    frame["p_holm_within_outcome"] = (
        frame.groupby("outcome", group_keys=False)["permutation_p"].apply(holm_adjust)
    )
    frame["q_bh_within_outcome"] = (
        frame.groupby("outcome", group_keys=False)["permutation_p"].apply(bh_adjust)
    )
    frame["inference_note"] = (
        "exploratory task-level scan; global multiplicity and building clustering must be considered"
    )
    return frame


def feature_alias_audit(source: Path) -> pd.DataFrame:
    frame = pd.read_csv(source)
    candidates = [
        "horizontal_gradient_mean_wrap",
        "horizontal_gradient_mean_no_seam",
        "vertical_edge_mean",
        "boundary_gradient_mean",
        "edge_density_proxy",
    ]
    candidates = [column for column in candidates if column in frame]
    rows: list[dict[str, object]] = []
    for left_index, left in enumerate(candidates):
        for right in candidates[left_index + 1 :]:
            data = frame[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
            rho = float(stats.spearmanr(data[left], data[right]).statistic) if len(data) >= 3 else np.nan
            exact = bool(np.allclose(data[left], data[right], rtol=0, atol=0)) if len(data) else False
            rows.append(
                {
                    "feature_left": left,
                    "feature_right": right,
                    "row_count": len(data),
                    "spearman_rho": rho,
                    "exact_value_identity": exact,
                    "independent_signal_allowed": not (exact or (math.isfinite(rho) and abs(rho) >= 0.999999)),
                    "note": (
                        "vertical_edge_mean is an x-gradient/vertical-edge response alias, not an independent "
                        "y-gradient measure; boundary_gradient_mean is the y-gradient summary"
                        if {left, right} & {"vertical_edge_mean"}
                        else "feature redundancy audit"
                    ),
                }
            )
    return pd.DataFrame(rows)


def semi_power_audit(summary_path: Path, projection_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(summary_path)
    projection = pd.read_csv(projection_path)
    entropy = summary.loc[summary["metric"].eq("shannon_entropy")].iloc[0]
    observed_effect = abs(float(entropy["task_weighted_mean_delta"]))
    observed_building_sd = float(projection["observed_building_level_sd"].dropna().iloc[0])

    scenarios = projection[
        ["future_total_buildings", "future_total_paired_tasks"]
    ].drop_duplicates().sort_values("future_total_buildings")
    rows = []
    effects = [observed_effect, 0.05, 0.10, 0.15, 0.20]
    for item in scenarios.itertuples(index=False):
        buildings = int(item.future_total_buildings)
        tasks = int(item.future_total_paired_tasks)
        se = observed_building_sd / math.sqrt(buildings)
        row: dict[str, object] = {
            "future_total_buildings": buildings,
            "future_total_paired_tasks": tasks,
            "observed_building_level_sd": observed_building_sd,
            "standard_error": se,
            "normal_95_ci_half_width": 1.96 * se,
        }
        for effect in effects:
            row[f"power_if_abs_true_effect_{effect:.6f}"] = two_sided_normal_power(effect, se)
        rows.append(row)

    required = []
    z_total = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
    task_per_building = 25 / 9
    for effect in effects:
        buildings = math.ceil((z_total * observed_building_sd / effect) ** 2)
        required.append(
            {
                "assumed_abs_true_effect": effect,
                "required_total_buildings_80_power": buildings,
                "required_total_paired_tasks_at_current_density": math.ceil(buildings * task_per_building),
                "additional_buildings_from_current_9": max(0, buildings - 9),
                "additional_tasks_from_current_25": max(0, math.ceil(buildings * task_per_building) - 25),
                "note": "normal approximation using current observed building-level SD; not a guarantee",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(required)


def task_level_risk_audit(source: Path, repetitions: int = 5000) -> pd.DataFrame:
    frame = pd.read_csv(source)
    frame = frame.loc[frame["eligibility_status"].eq("eligible")].copy()
    frame["risk"] = pd.to_numeric(frame["risk"], errors="coerce")
    frame["quality"] = pd.to_numeric(frame["quality"], errors="coerce")
    frame = frame.dropna(subset=["risk", "quality", "base_task_id", "building_id"])
    task = (
        frame.groupby(["base_task_id", "building_id"], as_index=False)
        .agg(risk=("risk", "first"), quality=("quality", "mean"), worker_support=("worker_id", "nunique"))
    )
    fit = stats.linregress(task["risk"], task["quality"])
    rng = np.random.default_rng(SEED)
    buildings = task["building_id"].astype(str).unique()
    slopes = []
    for _ in range(repetitions):
        sampled = rng.choice(buildings, len(buildings), replace=True)
        pieces = []
        for copy_index, building in enumerate(sampled):
            part = task.loc[task["building_id"].astype(str).eq(building)].copy()
            part["_cluster_copy"] = copy_index
            pieces.append(part)
        sample = pd.concat(pieces, ignore_index=True)
        if sample["risk"].nunique() >= 2:
            slopes.append(float(stats.linregress(sample["risk"], sample["quality"]).slope))
    return pd.DataFrame(
        [
            {
                "analysis_unit": "base_task_id",
                "eligible_row_count_before_task_aggregation": len(frame),
                "task_count": task["base_task_id"].nunique(),
                "building_count": len(buildings),
                "task_level_slope": fit.slope,
                "task_level_naive_standard_error": fit.stderr,
                "building_cluster_bootstrap_repetitions": len(slopes),
                "building_cluster_bootstrap_ci_lower": np.quantile(slopes, 0.025),
                "building_cluster_bootstrap_ci_upper": np.quantile(slopes, 0.975),
                "formal_p_value_reported": False,
                "note": (
                    "v5 row-level scipy.stats.linregress p-values ignore repeated task/worker/building dependence; "
                    "this audit keeps the slope descriptive and clusters uncertainty by building"
                ),
            }
        ]
    )


def calculation_mode_audit() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "component": "Manual/Semi overall uncertainty",
                "v5_status": "usable",
                "issue": "none identified in primary building-level sign-flip summary",
                "required_action": "retain continuous effect, building support, CI and exact sign-flip p",
            },
            {
                "component": "image-feature association scan",
                "v5_status": "exploratory_only",
                "issue": "many predictor-outcome tests; no global multiplicity adjustment; task bootstrap ignores building clusters",
                "required_action": "use corrected p/q, building-cluster sensitivity and pre-specified feature families",
            },
            {
                "component": "vertical_edge_mean",
                "v5_status": "alias_not_independent",
                "issue": "x-gradient vertical-edge response duplicates the horizontal-gradient family; name can be misread as y-gradient",
                "required_action": "rename to x_gradient_vertical_edge_mean or exclude as an independent predictor",
            },
            {
                "component": "quality-risk population slopes",
                "v5_status": "descriptive_slope_only",
                "issue": "row-level linregress SE/CI/p ignore repeated task, worker and building dependence",
                "required_action": "aggregate by task and cluster uncertainty by building; do not use v5 row-level p as formal evidence",
            },
            {
                "component": "edit RMSE versus delta_U",
                "v5_status": "joint_geometry_derived_association",
                "issue": "both variables derive from the same initial/final geometry; worker/task mean analyses remain assignment-composition sensitive",
                "required_action": "do not call an independent behavioral mechanism; use task-centered or experimental proposal-response design",
            },
            {
                "component": "client_server_lag_seconds",
                "v5_status": "clock_offset_indicator",
                "issue": "median is approximately 28,800 seconds, consistent with an 8-hour clock/time-zone offset",
                "required_action": "do not interpret as network/process latency until clock normalization is established",
            },
            {
                "component": "coverage gaps",
                "v5_status": "explicitly_not_materialized",
                "issue": "missingness model, reference trajectory, expert reclustering, task mechanism clustering and event phenotype absent",
                "required_action": "materialize only where source fields/independent expert labels exist; otherwise report not computable",
            },
        ]
    )


def materialize(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    multiplicity = multiplicity_audit(input_dir / "IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv")
    aliases = feature_alias_audit(input_dir / "IMAGE_FEATURES_ALL_214.csv")
    power, required = semi_power_audit(
        input_dir / "CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.CSV",
        input_dir / "SEMI_DATA_PRECISION_PROJECTION.CSV",
    )
    risk = task_level_risk_audit(input_dir / "C2_TERMINAL_RISK_EVIDENCE_240.csv")

    multiplicity.to_csv(output_dir / "IMAGE_FEATURE_MULTIPLICITY_AUDIT.csv", index=False)
    aliases.to_csv(output_dir / "IMAGE_FEATURE_ALIAS_AUDIT.csv", index=False)
    power.to_csv(output_dir / "SEMI_OBSERVED_EFFECT_POWER_PROJECTION.csv", index=False)
    required.to_csv(output_dir / "SEMI_REQUIRED_SAMPLE_BY_EFFECT_AUDIT.csv", index=False)
    risk.to_csv(output_dir / "QUALITY_RISK_TASK_BUILDING_CLUSTER_AUDIT.csv", index=False)
    calculation_mode_audit().to_csv(output_dir / "CALCULATION_MODE_AUDIT.csv", index=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    materialize(args.input_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
