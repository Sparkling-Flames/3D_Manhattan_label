"""Materialise an advisor-facing, all-stage annotation-uncertainty report.

The analysis is intentionally broader than the historical Paper A estimands:
records are retained whenever the requested variable is computable.  Legacy
eligibility, administrative status, assignment provenance and later-stage status
are descriptors and sensitivity dimensions, not blanket deletion rules.
"""
from __future__ import annotations

import argparse
import json
import math
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_common import (
    C1,
    PACKAGE,
    PERSISTENT,
    ROOT,
    STAGE_SOURCES,
    V2,
    clean,
    git_head,
    load_raw_annotation_fact,
    load_unified_stage_submissions,
    manifest_for_directory,
    number,
    read_csv,
    sha256_file,
    truth,
    write_csv,
    write_json,
)
from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_geometry import (
    c1_crowd_gt_conflict,
    cross_stage_geometry_uncertainty,
    meta_label_uncertainty,
    persistent_disagreement_catalog,
    worker_viewpoint_stability,
)

warnings.filterwarnings("ignore", category=RuntimeWarning)
SEED = 20260821
DEFAULT_OUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v1"


def coverage_summary(unified: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (stage, condition), group in unified.groupby(["stage", "condition"], dropna=False):
        rows.append({
            "stage": stage,
            "condition": condition,
            "selected_or_auditable_record_count": len(group),
            "worker_count": int(group["worker_id"].nunique()),
            "base_task_count": int(group["base_task_id"].nunique()),
            "building_count": int(group["building_id"].nunique()),
            "geometry_computable_count": int(group["geometry_computable"].map(truth).sum()),
            "active_time_observed_count": int(pd.to_numeric(group["active_time_observed_seconds"], errors="coerce").notna().sum()),
            "active_time_formal_eligible_count": int(group["active_time_formal_eligible"].map(truth).sum()),
            "lead_time_observed_count": int(pd.to_numeric(group["lead_time_seconds"], errors="coerce").notna().sum()),
            "administrative_exclusion_record_count": int(group["worker_status_class"].eq("administrative_exclusion").sum()),
            "historical_retained_record_count": int(group["worker_status_class"].eq("historical_retained").sum()),
            "outside_assignment_record_count": int(group["assignment_provenance"].astype(str).eq("outside_assignment_submission").sum()),
        })
    result = pd.DataFrame(rows)
    if not raw.empty:
        raw_counts = raw.groupby(["stage", "condition"], dropna=False).agg(
            raw_annotation_version_count=("annotation_id", "size"),
            raw_worker_count=("worker_id", "nunique"),
            raw_base_task_count=("base_task_id", "nunique"),
            raw_lead_time_observed_count=("lead_time_seconds", lambda values: pd.to_numeric(values, errors="coerce").notna().sum()),
        ).reset_index()
        result = result.merge(raw_counts, how="outer", on=["stage", "condition"])
    return result.sort_values(["stage", "condition"]).reset_index(drop=True)


def _describe_time(values: pd.Series) -> dict[str, Any]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    numeric = numeric[np.isfinite(numeric)]
    if numeric.empty:
        return {
            "observed_count": 0, "mean_seconds": np.nan, "median_seconds": np.nan,
            "q25_seconds": np.nan, "q75_seconds": np.nan, "q90_seconds": np.nan,
            "q95_seconds": np.nan, "maximum_seconds": np.nan, "geometric_mean_seconds": np.nan,
        }
    return {
        "observed_count": len(numeric),
        "mean_seconds": float(numeric.mean()),
        "median_seconds": float(numeric.median()),
        "q25_seconds": float(numeric.quantile(0.25)),
        "q75_seconds": float(numeric.quantile(0.75)),
        "q90_seconds": float(numeric.quantile(0.90)),
        "q95_seconds": float(numeric.quantile(0.95)),
        "maximum_seconds": float(numeric.max()),
        "geometric_mean_seconds": float(np.expm1(np.log1p(np.clip(numeric, 0, None)).mean())),
    }


def _time_model(frame: pd.DataFrame, outcome: str, lane: str) -> pd.DataFrame:
    try:
        import statsmodels.formula.api as smf
    except Exception:
        return pd.DataFrame([{"model_lane": lane, "status": "statsmodels_unavailable"}])
    work = frame.copy()
    work[outcome] = pd.to_numeric(work[outcome], errors="coerce")
    work = work[work[outcome].notna() & work["condition"].isin(["manual", "semi"])].copy()
    work = work[work[outcome] >= 0]
    if len(work) < 30 or work["condition"].nunique() < 2:
        return pd.DataFrame([{"model_lane": lane, "status": "not_evaluable_support", "n_rows": len(work)}])
    work["log_time"] = np.log1p(work[outcome].astype(float))
    # Task and worker fixed effects protect the mode coefficient from the largest
    # observed composition differences.  This remains an association, not a
    # randomized causal estimate.
    formula = "log_time ~ C(stage) + C(condition) + C(stage):C(condition) + C(worker_id) + C(base_task_id)"
    try:
        model = smf.ols(formula, data=work).fit()
        if work["building_id"].nunique() >= 5:
            robust = model.get_robustcov_results(cov_type="cluster", groups=work["building_id"])
            names = list(model.params.index)
            params = pd.Series(robust.params, index=names)
            ses = pd.Series(robust.bse, index=names)
            pvalues = pd.Series(robust.pvalues, index=names)
            covariance = "building_cluster"
        else:
            params, ses, pvalues = model.params, model.bse, model.pvalues
            covariance = "classical"
        rows = []
        for name in params.index:
            if "condition" not in name:
                continue
            estimate = float(params[name])
            se = float(ses[name])
            rows.append({
                "model_lane": lane,
                "status": "estimated",
                "outcome": outcome,
                "term": name,
                "log_scale_estimate": estimate,
                "standard_error": se,
                "ci_lower": estimate - 1.96 * se,
                "ci_upper": estimate + 1.96 * se,
                "multiplicative_ratio_exp_beta": math.exp(estimate),
                "p_value": float(pvalues[name]),
                "n_rows": len(work),
                "worker_count": int(work["worker_id"].nunique()),
                "task_count": int(work["base_task_id"].nunique()),
                "building_count": int(work["building_id"].nunique()),
                "covariance": covariance,
                "formula": formula,
                "interpretation": "adjusted_association_not_randomized_causal_effect",
            })
        return pd.DataFrame(rows) if rows else pd.DataFrame([{"model_lane": lane, "status": "mode_terms_not_identifiable", "n_rows": len(work)}])
    except Exception as error:
        return pd.DataFrame([{"model_lane": lane, "status": "model_failure", "reason": str(error), "n_rows": len(work)}])


def time_analysis(unified: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = unified.copy()
    frame["active_time_observed_seconds"] = pd.to_numeric(frame["active_time_observed_seconds"], errors="coerce")
    frame["lead_time_seconds"] = pd.to_numeric(frame["lead_time_seconds"], errors="coerce")
    frame["active_time_lane"] = np.where(
        frame["active_time_observed_seconds"].isna(), "missing",
        np.where(frame["active_time_formal_eligible"].map(truth), "formal_frozen", "observed_nonformal"),
    )
    frame["lead_time_lane"] = np.where(frame["lead_time_seconds"].isna(), "missing", "label_studio_elapsed_observed")
    frame["active_to_lead_ratio"] = np.where(
        frame["active_time_observed_seconds"].notna() & frame["lead_time_seconds"].gt(0),
        frame["active_time_observed_seconds"] / frame["lead_time_seconds"], np.nan,
    )
    frame["active_minus_lead_seconds"] = frame["active_time_observed_seconds"] - frame["lead_time_seconds"]

    summary_rows: list[dict[str, Any]] = []
    for (stage, condition), group in frame.groupby(["stage", "condition"], dropna=False):
        for metric, column, lane_note in (
            ("active_time", "active_time_observed_seconds", "active engagement from stage-specific active-time evidence"),
            ("lead_time", "lead_time_seconds", "Label Studio elapsed lead_time analysed separately"),
        ):
            description = _describe_time(group[column])
            summary_rows.append({
                "stage": stage, "condition": condition, "metric": metric,
                "total_record_count": len(group),
                "missing_rate": 1 - description["observed_count"] / len(group) if len(group) else np.nan,
                "formal_eligible_count": int(group["active_time_formal_eligible"].map(truth).sum()) if metric == "active_time" else np.nan,
                "measurement_note": lane_note,
                **description,
            })
    summary = pd.DataFrame(summary_rows)

    paired_rows: list[dict[str, Any]] = []
    task_condition = frame.groupby(["stage", "base_task_id", "building_id", "condition"], dropna=False).agg(
        active_time_median=("active_time_observed_seconds", "median"),
        active_time_mean=("active_time_observed_seconds", "mean"),
        lead_time_median=("lead_time_seconds", "median"),
        lead_time_mean=("lead_time_seconds", "mean"),
        active_n=("active_time_observed_seconds", "count"),
        lead_n=("lead_time_seconds", "count"),
    ).reset_index()
    for stage, stage_group in task_condition.groupby("stage"):
        for metric in ("active_time_median", "lead_time_median"):
            pivot = stage_group.pivot_table(index=["base_task_id", "building_id"], columns="condition", values=metric, aggfunc="first")
            if "manual" not in pivot or "semi" not in pivot:
                continue
            usable = pivot.dropna(subset=["manual", "semi"])
            for (task, building), row in usable.iterrows():
                paired_rows.append({
                    "stage": stage, "base_task_id": task, "building_id": building,
                    "metric": metric.replace("_median", ""),
                    "manual_task_median_seconds": float(row["manual"]),
                    "semi_task_median_seconds": float(row["semi"]),
                    "semi_minus_manual_seconds": float(row["semi"] - row["manual"]),
                    "semi_to_manual_ratio": float(row["semi"] / row["manual"]) if row["manual"] > 0 else np.nan,
                    "analysis_unit": "task_within_stage_condition_medians",
                })
    paired = pd.DataFrame(paired_rows)

    relation_rows: list[dict[str, Any]] = []
    for (stage, condition), group in frame.dropna(subset=["active_time_observed_seconds", "lead_time_seconds"]).groupby(["stage", "condition"]):
        if len(group) >= 3 and group["active_time_observed_seconds"].nunique() > 1 and group["lead_time_seconds"].nunique() > 1:
            spearman = stats.spearmanr(group["active_time_observed_seconds"], group["lead_time_seconds"])
            pearson = stats.pearsonr(np.log1p(group["active_time_observed_seconds"]), np.log1p(group["lead_time_seconds"]))
            relation_rows.append({
                "stage": stage, "condition": condition, "paired_record_count": len(group),
                "spearman_rho": float(spearman.statistic), "spearman_p": float(spearman.pvalue),
                "log_scale_pearson_r": float(pearson.statistic), "log_scale_pearson_p": float(pearson.pvalue),
                "median_active_to_lead_ratio": float(group["active_to_lead_ratio"].median()),
                "q25_active_to_lead_ratio": float(group["active_to_lead_ratio"].quantile(0.25)),
                "q75_active_to_lead_ratio": float(group["active_to_lead_ratio"].quantile(0.75)),
                "interpretation": "active_and_elapsed_time_measure_different_constructs",
            })
    relation = pd.DataFrame(relation_rows)

    outlier_parts = []
    for metric, column in (("active_time", "active_time_observed_seconds"), ("lead_time", "lead_time_seconds")):
        usable = frame.dropna(subset=[column]).copy()
        if usable.empty:
            continue
        usable["within_stage_mode_percentile"] = usable.groupby(["stage", "condition"])[column].rank(pct=True, method="average")
        selected = usable.sort_values(column, ascending=False).head(30).copy()
        selected["time_metric"] = metric
        selected["time_value_seconds"] = selected[column]
        outlier_parts.append(selected[[
            "time_metric", "time_value_seconds", "within_stage_mode_percentile", "stage", "condition", "base_task_id", "building_id",
            "worker_id", "annotation_id", "canonical_annotation_id", "active_time_lane", "lead_time_lane", "active_time_source",
            "active_time_source_file", "timing_status", "active_to_lead_ratio", "assignment_provenance", "worker_status_class", "source_artifact",
        ]])
    outliers = pd.concat(outlier_parts, ignore_index=True, sort=False) if outlier_parts else pd.DataFrame()

    formal_model = _time_model(frame[frame["active_time_formal_eligible"].map(truth)], "active_time_observed_seconds", "active_time_formal_frozen")
    observed_model = _time_model(frame, "active_time_observed_seconds", "active_time_all_observed")
    lead_model = _time_model(frame, "lead_time_seconds", "lead_time_all_observed_separate")
    models = pd.concat([formal_model, observed_model, lead_model], ignore_index=True, sort=False)
    return frame, summary, paired, relation, pd.concat([outliers, models.assign(time_metric="model")], ignore_index=True, sort=False)


def semi_precision_projection() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    population_tasks = read_csv(V2 / "POPULATION_TASK_METRICS.csv")
    population_summary = read_csv(V2 / "POPULATION_SENSITIVITY.csv")
    if population_tasks.empty:
        population_tasks = read_csv(V2 / "TASK_METRICS.csv")
        population_tasks["population"] = "fallback_task_metrics"
    for column in ("threshold", "delta_shannon_entropy"):
        if column in population_tasks:
            population_tasks[column] = pd.to_numeric(population_tasks[column], errors="coerce")
    target_population = "all_canonical_planned" if "all_canonical_planned" in set(population_tasks.get("population", [])) else population_tasks["population"].iloc[0]
    tasks = population_tasks[
        population_tasks["population"].eq(target_population)
        & np.isclose(population_tasks["threshold"], 0.95)
    ].copy()
    if tasks.empty:
        tasks = population_tasks[np.isclose(population_tasks["threshold"], 0.95)].copy()
    tasks["delta_shannon_entropy"] = pd.to_numeric(tasks["delta_shannon_entropy"], errors="coerce")
    tasks = tasks.dropna(subset=["delta_shannon_entropy", "building_id"])
    building = tasks.groupby("building_id", as_index=False)["delta_shannon_entropy"].mean()
    current_buildings = len(building)
    current_tasks = len(tasks)
    current_mean = float(tasks["delta_shannon_entropy"].mean()) if len(tasks) else np.nan
    building_sd = float(building["delta_shannon_entropy"].std(ddof=1)) if current_buildings >= 2 else np.nan
    z_alpha = stats.norm.ppf(0.975)
    z_power = stats.norm.ppf(0.80)
    projection_rows: list[dict[str, Any]] = []
    for building_count in (current_buildings, 18, 27, 36, 54, 72):
        if building_count <= 0 or not math.isfinite(building_sd):
            continue
        standard_error = building_sd / math.sqrt(building_count)
        half_width = z_alpha * standard_error
        mde80 = (z_alpha + z_power) * standard_error
        for effect in (0.0, 0.05, 0.10, 0.15, 0.20):
            noncentral = abs(effect) / standard_error if standard_error > 0 else np.inf
            power = stats.norm.cdf(-z_alpha - noncentral) + 1 - stats.norm.cdf(z_alpha - noncentral)
            projection_rows.append({
                "projected_independent_building_count": building_count,
                "projected_paired_task_count_if_current_tasks_per_building": round(current_tasks * building_count / current_buildings) if current_buildings else np.nan,
                "observed_building_mean_sd": building_sd,
                "projected_standard_error": standard_error,
                "projected_95ci_half_width": half_width,
                "approximate_80pct_minimum_detectable_absolute_effect": mde80,
                "assumed_true_absolute_effect": effect,
                "approximate_two_sided_power": float(power),
                "current_task_mean_effect": current_mean,
                "assumption": "independent_future_buildings_with_current_building_level_variance_and_comparable_design",
                "warning": "projection_not_guarantee;more_labels_on_same_image_do_not_create_independent_buildings",
            })
    projection = pd.DataFrame(projection_rows)

    rare_rows = []
    for minority_share in (0.05, 0.10, 0.20, 0.30, 0.40):
        for k in (4, 5, 8, 10, 12, 20, 22):
            p0 = (1 - minority_share) ** k
            p1 = k * minority_share * (1 - minority_share) ** (k - 1)
            rare_rows.append({
                "true_minority_mode_share": minority_share,
                "annotation_count_k": k,
                "probability_observe_at_least_one_minority": 1 - p0,
                "probability_observe_at_least_two_minority": 1 - p0 - p1,
                "interpretation": "second_mode_support_at_least_two_detection_under_independent_sampling",
            })
    rare = pd.DataFrame(rare_rows)

    current = population_summary.copy()
    for column in ("threshold", "mean_difference", "ci_lower", "ci_upper", "building_exact_sign_flip_p", "n_tasks", "n_buildings"):
        if column in current:
            current[column] = pd.to_numeric(current[column], errors="coerce")
    current = current[
        current.get("population", pd.Series([""] * len(current))).eq(target_population)
        & np.isclose(current.get("threshold", pd.Series([np.nan] * len(current))), 0.95)
    ]
    return projection, rare, current


def _cluster_bootstrap_spearman(frame: pd.DataFrame, x: str, y: str, *, cluster: str = "building_id", replicates: int = 2000) -> tuple[float | None, float | None, float | None, int, int]:
    work = frame[[x, y, cluster]].copy()
    work[x] = pd.to_numeric(work[x], errors="coerce")
    work[y] = pd.to_numeric(work[y], errors="coerce")
    work = work.dropna()
    if len(work) < 5 or work[x].nunique() < 2 or work[y].nunique() < 2:
        return None, None, None, len(work), work[cluster].nunique()
    estimate = float(stats.spearmanr(work[x], work[y]).statistic)
    clusters = sorted(work[cluster].astype(str).unique())
    if len(clusters) < 3:
        return estimate, None, None, len(work), len(clusters)
    rng = np.random.default_rng(SEED + sum(map(ord, x + y)))
    draws = []
    by_cluster = {value: work[work[cluster].astype(str).eq(value)] for value in clusters}
    for _ in range(replicates):
        sampled = [by_cluster[rng.choice(clusters)].assign(_boot_cluster=index) for index in range(len(clusters))]
        draw = pd.concat(sampled, ignore_index=True)
        if draw[x].nunique() > 1 and draw[y].nunique() > 1:
            draws.append(float(stats.spearmanr(draw[x], draw[y]).statistic))
    if not draws:
        return estimate, None, None, len(work), len(clusters)
    lower, upper = np.quantile(draws, [0.025, 0.975])
    return estimate, float(lower), float(upper), len(work), len(clusters)


def semi_mechanism_analysis() -> tuple[pd.DataFrame, pd.DataFrame]:
    path = PACKAGE / "semi_review_fact.csv"
    frame = read_csv(path)
    if frame.empty:
        return pd.DataFrame(), pd.DataFrame()
    for column in ("geometry_edit_rmse_px", "geometry_edit_rmse_panorama_diagonal_normalized", "U_initial", "U_final", "delta_U"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["worker_id"] = frame.get("worker_id", "").map(lambda value: clean(value).upper().lstrip("W0") or clean(value))
    frame["base_task_id"] = frame.get("base_task_id", "").map(clean)
    rmse = frame.get("geometry_edit_rmse_px", pd.Series([np.nan] * len(frame), index=frame.index))
    delta_u = frame.get("delta_U", pd.Series([np.nan] * len(frame), index=frame.index))
    frame["edited_binary_calc"] = rmse.gt(0)
    frame["structural_zero"] = rmse.notna() & delta_u.notna() & rmse.eq(0) & delta_u.eq(0)
    computable = frame.dropna(subset=["geometry_edit_rmse_px", "delta_U"])
    rows = []
    for population, subset in (
        ("all_delta_u_computable", computable),
        ("exclude_structural_zero", computable[~computable["structural_zero"]]),
        ("edited_only", computable[computable["edited_binary_calc"]]),
    ):
        if len(subset) >= 3 and subset["geometry_edit_rmse_px"].nunique() > 1 and subset["delta_U"].nunique() > 1:
            row_rho = float(stats.spearmanr(subset["geometry_edit_rmse_px"], subset["delta_U"]).statistic)
        else:
            row_rho = np.nan
        task = subset.groupby("base_task_id", as_index=False).agg(edit=("geometry_edit_rmse_px", "mean"), delta=("delta_U", "mean"))
        worker = subset.groupby("worker_id", as_index=False).agg(edit=("geometry_edit_rmse_px", "mean"), delta=("delta_U", "mean"))
        task_rho = float(stats.spearmanr(task["edit"], task["delta"]).statistic) if len(task) >= 3 and task["edit"].nunique() > 1 and task["delta"].nunique() > 1 else np.nan
        worker_rho = float(stats.spearmanr(worker["edit"], worker["delta"]).statistic) if len(worker) >= 3 and worker["edit"].nunique() > 1 and worker["delta"].nunique() > 1 else np.nan
        rows.append({
            "population": population, "row_count": len(subset), "task_count": subset["base_task_id"].nunique(),
            "worker_count": subset["worker_id"].nunique(), "row_axis_spearman_edit_vs_delta_u": row_rho,
            "task_axis_spearman_edit_vs_delta_u": task_rho, "worker_axis_spearman_edit_vs_delta_u": worker_rho,
            "structural_zero_count": int(subset["structural_zero"].sum()),
            "interpretation": "descriptive_axis_sensitivity_not_independent_causal_effect",
        })
    bins = frame.dropna(subset=["U_initial", "delta_U"]).copy()
    if len(bins) >= 4:
        bins["initial_quality_quartile"] = pd.qcut(bins["U_initial"], q=4, duplicates="drop")
        bin_summary = bins.groupby("initial_quality_quartile", observed=True).agg(
            row_count=("delta_U", "size"), initial_quality_mean=("U_initial", "mean"),
            delta_u_mean=("delta_U", "mean"), delta_u_median=("delta_U", "median"),
            edited_rate=("edited_binary_calc", "mean"),
            harmful_rate=("delta_U", lambda values: np.mean(pd.to_numeric(values, errors="coerce") < -0.01)),
            improving_rate=("delta_U", lambda values: np.mean(pd.to_numeric(values, errors="coerce") > 0.01)),
        ).reset_index()
        bin_summary["initial_quality_quartile"] = bin_summary["initial_quality_quartile"].astype(str)
    else:
        bin_summary = pd.DataFrame()
    return pd.DataFrame(rows), bin_summary


def deep_associations(
    unified: pd.DataFrame,
    meta_tasks: pd.DataFrame,
    gt_conflict: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    manual = read_csv(V2 / "MANUAL_TASK_UNCERTAINTY_CATALOG.csv")
    for column in ("threshold", "all_canonical_shannon_entropy", "all_canonical_mode_count"):
        if column in manual:
            manual[column] = pd.to_numeric(manual[column], errors="coerce")
    task = manual[np.isclose(manual.get("threshold", pd.Series([np.nan] * len(manual))), 0.95)].copy()
    task = task.rename(columns={"all_canonical_shannon_entropy": "geometry_entropy", "all_canonical_mode_count": "geometry_mode_count"})

    c1 = unified[unified["stage"].eq("C1")].copy()
    c1["active_time_observed_seconds"] = pd.to_numeric(c1["active_time_observed_seconds"], errors="coerce")
    c1["lead_time_seconds"] = pd.to_numeric(c1["lead_time_seconds"], errors="coerce")
    timing = c1.groupby("base_task_id", as_index=False).agg(
        active_time_task_median=("active_time_observed_seconds", "median"),
        lead_time_task_median=("lead_time_seconds", "median"),
        n_corners_task_median=("n_corners", "median"),
    )
    evidence = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    if not evidence.empty:
        evidence["iou_to_gt"] = pd.to_numeric(evidence["iou_to_gt"], errors="coerce")
        evidence["worker_caused_structural_failure_bool"] = evidence["worker_caused_structural_failure"].map(truth)
        quality = evidence.groupby("base_task_id", as_index=False).agg(
            task_iou_mean=("iou_to_gt", "mean"), task_iou_median=("iou_to_gt", "median"),
            structural_failure_rate=("worker_caused_structural_failure_bool", "mean"),
            quality_computable_count=("iou_to_gt", "count"),
        )
    else:
        quality = pd.DataFrame()
    task = task.merge(timing, how="left", on="base_task_id")
    if not quality.empty:
        task = task.merge(quality, how="left", on="base_task_id")
    if not gt_conflict.empty:
        gt_manual = gt_conflict[gt_conflict["condition"].eq("manual")][["base_task_id", "crowd_gt_gap_best_minus_largest", "largest_cluster_median_iou", "best_cluster_median_iou"]]
        task = task.merge(gt_manual, how="left", on="base_task_id")
    if not meta_tasks.empty:
        meta = meta_tasks.groupby(["base_task_id", "meta_group"], as_index=False)["mean_label_entropy"].mean()
        meta = meta.pivot(index="base_task_id", columns="meta_group", values="mean_label_entropy").reset_index()
        meta = meta.rename(columns={column: f"meta_entropy_{column}" for column in meta.columns if column != "base_task_id"})
        task = task.merge(meta, how="left", on="base_task_id")

    pairs = [
        ("geometry_entropy", "active_time_task_median"),
        ("geometry_entropy", "lead_time_task_median"),
        ("geometry_entropy", "task_iou_mean"),
        ("geometry_entropy", "structural_failure_rate"),
        ("geometry_entropy", "n_corners_task_median"),
        ("geometry_entropy", "meta_entropy_difficulty"),
        ("geometry_entropy", "meta_entropy_scope"),
        ("geometry_entropy", "meta_entropy_model_issue"),
        ("geometry_entropy", "crowd_gt_gap_best_minus_largest"),
    ]
    rows = []
    for x, y in pairs:
        if x not in task or y not in task:
            continue
        estimate, lower, upper, n, buildings = _cluster_bootstrap_spearman(task, x, y)
        rows.append({
            "analysis_level": "task", "predictor": x, "outcome": y,
            "spearman_rho": estimate, "building_bootstrap_ci_lower": lower, "building_bootstrap_ci_upper": upper,
            "row_count": n, "building_count": buildings,
            "status": "descriptive_association" if estimate is not None else "not_evaluable",
            "interpretation_boundary": "association_not_causation;task_selection_and_measurement_differ_by_lane",
        })

    # Worker-level quality/time/structure table includes every worker with any
    # computable component; components are not collapsed into a rank.
    if not evidence.empty:
        evidence["worker_id"] = evidence["worker_id"].astype(str)
        worker_quality = evidence.groupby("worker_id", as_index=False).agg(
            quality_count=("iou_to_gt", "count"), quality_mean=("iou_to_gt", "mean"), quality_median=("iou_to_gt", "median"),
            structural_opportunity_count=("worker_caused_structural_failure_bool", "count"),
            structural_failure_rate=("worker_caused_structural_failure_bool", "mean"),
        )
        worker_time = c1.groupby("worker_id", as_index=False).agg(
            active_time_count=("active_time_observed_seconds", "count"), active_time_median=("active_time_observed_seconds", "median"),
            lead_time_count=("lead_time_seconds", "count"), lead_time_median=("lead_time_seconds", "median"),
        )
        worker_table = worker_quality.merge(worker_time, how="outer", on="worker_id")
    else:
        worker_table = pd.DataFrame()
    worker_pairs = [("quality_mean", "active_time_median"), ("quality_mean", "lead_time_median"), ("structural_failure_rate", "active_time_median"), ("active_time_median", "lead_time_median")]
    for x, y in worker_pairs:
        if worker_table.empty or x not in worker_table or y not in worker_table:
            continue
        usable = worker_table[[x, y]].dropna()
        rho = float(stats.spearmanr(usable[x], usable[y]).statistic) if len(usable) >= 3 and usable[x].nunique() > 1 and usable[y].nunique() > 1 else np.nan
        rows.append({
            "analysis_level": "worker", "predictor": x, "outcome": y, "spearman_rho": rho,
            "row_count": len(usable), "building_count": np.nan,
            "status": "descriptive_association" if pd.notna(rho) else "not_evaluable",
            "interpretation_boundary": "worker_aggregate_ecological_association;support_unequal",
        })
    mechanism, mechanism_bins = semi_mechanism_analysis()
    return pd.DataFrame(rows), task, pd.concat([worker_table.assign(table="worker_components"), mechanism.assign(table="semi_mechanism_axis"), mechanism_bins.assign(table="semi_initial_quality_bins")], ignore_index=True, sort=False)


def data_dictionary() -> pd.DataFrame:
    rows = [
        ("computable", "可计算", "该记录具有计算该变量所需的数值/几何；不等于原论文正式资格", "required fields are present and numerically valid"),
        ("formal_use_allowed", "原论文正式使用允许", "旧方法合同下是否可进入正式 estimand；本报告不把它作为全局删除条件", "legacy/formal eligibility flag"),
        ("shannon_entropy", "Shannon 模式熵", "模式分布越分散，值越大", "-sum_m p_m * ln(p_m)"),
        ("gini_simpson", "Gini–Simpson 分歧", "随机抽两份标注落入不同模式的概率型指标", "1 - sum_m p_m^2"),
        ("largest_mode_share", "最大模式占比", "最大几何/拓扑模式的支持人数除以有效人数", "max_m n_m / sum_m n_m"),
        ("topology_shannon_entropy", "拓扑熵", "以角点数量/点数签名作为类别计算的跨阶段描述性熵", "-sum_j p_j * ln(p_j), j indexes n_corners signatures"),
        ("same_topology_cyclic_rmse_median", "同拓扑循环对齐 RMSE 中位数", "相同角点数标注经循环位移/反向对齐后的坐标差，除以全景对角线", "median min_shift sqrt(mean(dx_circular^2+dy^2))/sqrt(1024^2+512^2)"),
        ("pairwise_jaccard_mean", "元标签集合平均 Jaccard", "两名工人选择集合的交集/并集，再对工人对取均值", "mean_{u<v} |S_u∩S_v|/|S_u∪S_v|"),
        ("mean_label_entropy", "平均元标签熵", "对每个二元标签计算 Bernoulli 熵，再在标签上取均值", "mean_l[-p_l ln p_l-(1-p_l)ln(1-p_l)]"),
        ("active_time_observed_seconds", "活跃操作时间（秒）", "各阶段脚本记录的活跃交互时间；C1 按 task-worker-session 正式规则重建", "within session max cumulative seconds; sum eligible sessions for C1"),
        ("lead_time_seconds", "Label Studio 经过时间（秒）", "从界面开始到提交的 elapsed time；与 active time 分开分析", "Label Studio annotation.lead_time"),
        ("active_to_lead_ratio", "活跃/经过时间比", "活跃操作时间除以 lead time；仅两者均有值且 lead time>0时定义", "active_time / lead_time"),
        ("delta_shannon_entropy", "Semi−Manual 熵差", "同图、等支持量下 Semi 的模式熵减 Manual 的模式熵；负值表示 Semi 更集中", "H_semi - H_manual"),
        ("delta_iou_to_gt", "Semi−Manual GT IoU 差", "同图任务均值质量之差；资格口径需另行说明", "mean_u IoU_semi - mean_u IoU_manual"),
        ("crowd_gt_gap_best_minus_largest", "最佳 GT 对齐簇与最大簇差", "与 GT 最接近簇的中位 IoU减最大人群簇的中位 IoU", "max_m median(IoU_m) - median(IoU_largest)"),
        ("largest_mode_rate", "工人进入最大模式比例", "工人在具有唯一分区的重复任务中落入最大簇的比例", "count(is_largest_mode)/task_count"),
        ("task_centered_n_pairs", "任务中心化角点对偏差", "工人角点对数减同任务条件中位数；正值表示相对更细分", "n_pairs_worker - median_task(n_pairs)"),
        ("probability_observe_at_least_two_minority", "至少观察到两名少数模式的概率", "假设独立抽样且真实少数模式比例为 p，在 k 人中出现至少两次", "1-(1-p)^k-k*p*(1-p)^(k-1)"),
        ("projected_95ci_half_width", "预计 95% 区间半宽", "按当前 building-level 方差和独立建筑数近似投影", "1.96 * sd_building / sqrt(B)"),
        ("minimum_detectable_effect", "约 80% 功效最小可检出效应", "正态近似、双侧 alpha=.05", "(z_.975+z_.80)*sd_building/sqrt(B)"),
    ]
    return pd.DataFrame(rows, columns=["variable_en", "variable_zh", "meaning_zh", "approximate_formula"])


def source_provenance() -> pd.DataFrame:
    paths = [path for _stage, path in STAGE_SOURCES] + [
        C1 / "c1_canonical_geometry.jsonl", C1 / "geometry_pairwise_similarity_C1.csv",
        C1 / "geometry_task_crowd_structure_C1.csv", V2 / "TASK_METRICS.csv",
        V2 / "POPULATION_SENSITIVITY.csv", V2 / "ROW_INCLUSION_CLASSIFICATION.csv",
        V2 / "ACTIVE_TIME_TASK_WORKER.csv", PACKAGE / "raw_annotation_fact.csv",
        PACKAGE / "semi_review_fact.csv", PERSISTENT / "PERSISTENT_DISAGREEMENT_TASKS.csv",
    ]
    rows = []
    for path in paths:
        rows.append({
            "path": path.relative_to(ROOT).as_posix(), "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else np.nan,
            "sha256": sha256_file(path) if path.is_file() else "",
        })
    return pd.DataFrame(rows)


def _image_map(raw: pd.DataFrame) -> dict[str, str]:
    result: dict[str, str] = {}
    if raw.empty:
        return result
    for row in raw.itertuples(index=False):
        task = clean(getattr(row, "base_task_id", ""))
        image = clean(getattr(row, "image_reference", ""))
        if task and image and task not in result:
            result[task] = image
    return result


def task_case_catalog(
    raw: pd.DataFrame,
    geometry_tasks: pd.DataFrame,
    meta_tasks: pd.DataFrame,
    gt_conflict: pd.DataFrame,
    memberships: pd.DataFrame,
    time_frame: pd.DataFrame,
) -> pd.DataFrame:
    image_map = _image_map(raw)
    rows: list[dict[str, Any]] = []

    def add(category: str, task: str, stage: str, condition: str, values: dict[str, Any], detail: str) -> None:
        rows.append({
            "case_category": category, "base_task_id": task, "image_reference": image_map.get(task, ""),
            "stage": stage, "condition": condition, "detail_zh": detail,
            "evidence_values_json": json.dumps(values, ensure_ascii=False, default=str, sort_keys=True),
        })

    population = read_csv(V2 / "POPULATION_TASK_METRICS.csv")
    if not population.empty:
        population["threshold"] = pd.to_numeric(population["threshold"], errors="coerce")
        population["delta_shannon_entropy"] = pd.to_numeric(population["delta_shannon_entropy"], errors="coerce")
        target = population[population["population"].eq("all_canonical_planned") & np.isclose(population["threshold"], 0.95)].dropna(subset=["delta_shannon_entropy"])
        for _, row in target.nsmallest(5, "delta_shannon_entropy").iterrows():
            add("semi_uncertainty_compression", row.base_task_id, "C1", "manual_vs_semi", row.to_dict(), "Semi 模式熵低于 Manual；表示分布更集中，不自动等同于更正确。")
        for _, row in target.nlargest(5, "delta_shannon_entropy").iterrows():
            add("semi_uncertainty_expansion", row.base_task_id, "C1", "manual_vs_semi", row.to_dict(), "Semi 模式熵高于 Manual；表示分布更分散，需结合 proposal 与质量。")

    persistent = persistent_disagreement_catalog()
    if not persistent.empty:
        selected = persistent[np.isclose(persistent["similarity_threshold"], 0.95) & persistent["strong_persistent_split"]]
        selected = selected.sort_values(["valid_k", "largest_cluster_share"], ascending=[False, True]).head(10)
        for _, row in selected.iterrows():
            add("persistent_geometry_split", row.base_task_id, row.stage, "manual", row.to_dict(), "在最大已观察支持量下仍有至少两个受支持模式；该状态不证明无限增加工人仍不会变化。")

    if not gt_conflict.empty:
        selected = gt_conflict[gt_conflict["crowd_gt_relationship"].isin([
            "multimodal_minority_cluster_better_gt_alignment", "unimodal_low_gt_alignment", "multimodal_multiple_gt_aligned_clusters"
        ])].copy()
        selected["abs_gap"] = pd.to_numeric(selected["crowd_gt_gap_best_minus_largest"], errors="coerce").abs()
        for _, row in selected.sort_values("abs_gap", ascending=False).head(12).iterrows():
            add("crowd_gt_relationship_case", row.base_task_id, "C1", row.condition, row.to_dict(), "先形成 GT-blind crowd 簇，再比较各簇与 GT；多数簇不自动替换 GT。")

    if not meta_tasks.empty:
        selected = meta_tasks[meta_tasks["response_count"] >= 3].sort_values("mean_label_entropy", ascending=False).head(12)
        for _, row in selected.iterrows():
            add("meta_label_high_uncertainty", row.base_task_id, row.stage, row.condition, row.to_dict(), f"{row.meta_group} 元标签在工人之间选择分散。")

    if not geometry_tasks.empty:
        selected = geometry_tasks[geometry_tasks["geometry_computable_worker_count"] >= 3].sort_values(
            ["topology_shannon_entropy", "same_topology_cyclic_rmse_median"], ascending=False
        ).head(12)
        for _, row in selected.iterrows():
            add("cross_stage_geometry_uncertainty", row.base_task_id, row.stage, row.condition, row.to_dict(), "跨阶段描述性拓扑分布或同拓扑坐标离散较高。")

    if not time_frame.empty:
        for metric, column in (("active_time_outlier", "active_time_observed_seconds"), ("lead_time_outlier", "lead_time_seconds")):
            selected = time_frame.dropna(subset=[column]).sort_values(column, ascending=False).head(8)
            for _, row in selected.iterrows():
                add(metric, row.base_task_id, row.stage, row.condition, {
                    "worker_id": row.worker_id, column: row[column], "active_to_lead_ratio": row.active_to_lead_ratio,
                    "timing_status": row.timing_status, "active_time_source": row.active_time_source,
                }, "时间长尾案例；active time 与 lead time 分别保留，不互相替代。")
        both = time_frame.dropna(subset=["active_to_lead_ratio"]).copy()
        both["ratio_log_abs"] = np.abs(np.log(np.clip(both["active_to_lead_ratio"], 1e-9, None)))
        for _, row in both.sort_values("ratio_log_abs", ascending=False).head(10).iterrows():
            add("active_lead_divergence", row.base_task_id, row.stage, row.condition, {
                "worker_id": row.worker_id, "active_time": row.active_time_observed_seconds,
                "lead_time": row.lead_time_seconds, "ratio": row.active_to_lead_ratio,
            }, "活跃交互时间与界面经过时间明显不同，说明二者不能混用。")

    if not memberships.empty:
        selected = memberships[memberships["is_supported_minority_mode"]].groupby(["base_task_id", "building_id", "condition"]).agg(
            minority_worker_ids=("worker_id", lambda values: ";".join(sorted(set(values)))),
            minority_member_count=("worker_id", "size"), cluster_count=("cluster_count", "max"),
        ).reset_index().sort_values("minority_member_count", ascending=False).head(10)
        for _, row in selected.iterrows():
            add("supported_minority_viewpoint", row.base_task_id, "C1", row.condition, row.to_dict(), "同任务中存在由至少两名工人支持的非最大模式；这里只描述观点结构，不判断对错。")

    for task, detail in (
        ("q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d", "高质量模型初始结果被四名工人全部修改，最终形成分散模式；用于 over-correction 检查。"),
        ("B6ByNegPMKs_5b5bd1eac4e6462d8c6677b90a4cf9a9", "Semi 总体仍单峰，但单名工人大幅编辑造成明显质量下降；低熵不排除个体伤害。"),
        ("wc2JMjhGNzB_55b45b0f19c2460bbcd1fb1c86c6610d", "Manual 分散而 Semi 集中到共享初始化附近；模式压缩可能包含锚定。"),
    ):
        add("proposal_conditioned_revision", task, "C1", "semi", {}, detail)
    return pd.DataFrame(rows).drop_duplicates(["case_category", "base_task_id", "stage", "condition"]).reset_index(drop=True)


def _fmt(value: Any, digits: int = 3) -> str:
    try:
        numeric = float(value)
        return "NA" if not math.isfinite(numeric) else f"{numeric:.{digits}f}"
    except Exception:
        return str(value)


def generate_report(
    coverage: pd.DataFrame,
    current_semi: pd.DataFrame,
    projection: pd.DataFrame,
    rare: pd.DataFrame,
    meta_tasks: pd.DataFrame,
    geometry_tasks: pd.DataFrame,
    persistent: pd.DataFrame,
    time_summary: pd.DataFrame,
    time_paired: pd.DataFrame,
    time_relation: pd.DataFrame,
    gt_conflict: pd.DataFrame,
    worker_view: pd.DataFrame,
    viewpoint_test: pd.DataFrame,
    associations: pd.DataFrame,
    mechanism: pd.DataFrame,
    cases: pd.DataFrame,
    provenance: pd.DataFrame,
) -> str:
    q95 = current_semi[(current_semi.get("metric", "") == "shannon_entropy")]
    q95_row = q95.iloc[0] if not q95.empty else None
    projected_core = projection[projection["assumed_true_absolute_effect"].eq(0.10)].copy() if not projection.empty else pd.DataFrame()
    persistent_q95 = persistent[np.isclose(persistent.get("similarity_threshold", pd.Series(dtype=float)), 0.95)] if not persistent.empty else pd.DataFrame()
    persistent_summary = persistent_q95.groupby("stage").agg(
        task_count=("base_task_id", "nunique"), strong_split_count=("strong_persistent_split", "sum"),
        non_evaluable_count=("not_evaluable_partition", "sum"),
    ).reset_index() if not persistent_q95.empty else pd.DataFrame()
    meta_summary = meta_tasks.groupby("meta_group").agg(
        task_condition_count=("base_task_id", "size"), response_count=("response_count", "sum"),
        mean_pairwise_jaccard=("pairwise_jaccard_mean", "mean"), mean_label_entropy=("mean_label_entropy", "mean"),
    ).reset_index() if not meta_tasks.empty else pd.DataFrame()
    conflict_summary = gt_conflict["crowd_gt_relationship"].value_counts().rename_axis("crowd_gt_relationship").reset_index(name="task_condition_count") if not gt_conflict.empty else pd.DataFrame()
    view_test = viewpoint_test[viewpoint_test.get("test", pd.Series(dtype=str)).eq("task_stratified_worker_largest_mode_rate_heterogeneity")] if not viewpoint_test.empty else pd.DataFrame()

    lines = [
        "# 360° 全景布局标注：完整数据整理与不确定性数据挖掘报告",
        "",
        "## 1. 报告范围",
        "",
        "本报告以当前 GitHub `main` 的冻结/物化数据为输入，重新建立数据挖掘层。数据挖掘层不以工人是否进入后续阶段、是否行政退出、是否属于 outside assignment、是否满足旧论文正式资格作为全局删除条件。每个结果变量单独标记是否可计算；旧资格仅作为对照字段。",
        "",
        "同一 worker–task 的多个修订版本保留在 raw 版本层，但不被当作多个独立工人。几何任务分布使用每名工人在每个 task-condition 的单一选定/可审计记录；修订数量另行保留。",
        "",
        "## 2. 数据覆盖",
        "",
        coverage.to_markdown(index=False),
        "",
        "## 3. Manual 与 Semi-Auto 的几何不确定性",
        "",
    ]
    if q95_row is not None:
        lines += [
            f"当前 25-task 全量描述性总体在 q=.95 下的任务等权 Shannon entropy 差（Semi−Manual）为 {_fmt(q95_row.get('mean_difference'), 4)}，"
            f"building-cluster 95% CI [{_fmt(q95_row.get('ci_lower'), 4)}, {_fmt(q95_row.get('ci_upper'), 4)}]，"
            f"building sign-flip p={_fmt(q95_row.get('building_exact_sign_flip_p'), 4)}。区间覆盖零；该结果不支持统一的总体不确定性下降，也不证明两种模式等效。",
            "",
        ]
    lines += [
        "现有 Semi 数据的主要限制不是只有记录总数少，而是独立信息主要集中在 9 个 building，且每图 Semi 支持通常约 4 人。增加同一图片的 Semi 工人数主要改善少数模式发现和模式比例估计；缩小总体 Manual/Semi 效应区间更依赖新增独立 task/building。",
        "",
        "### 3.1 增加 Semi 数据的近似精度投影",
        "",
        projected_core[[column for column in ["projected_independent_building_count", "projected_paired_task_count_if_current_tasks_per_building", "projected_95ci_half_width", "approximate_80pct_minimum_detectable_absolute_effect", "approximate_two_sided_power"] if column in projected_core]].to_markdown(index=False) if not projected_core.empty else "未形成可评价投影。",
        "",
        "投影假设未来 building 与当前 building-level 方差、任务构成和测量误差相近。它不是阳性结果保证；若真实总体效应接近当前点估计，样本增加只会把区间收窄到接近零的效应附近。",
        "",
        "### 3.2 少数模式的发现概率",
        "",
        rare[rare["true_minority_mode_share"].isin([0.10, 0.20, 0.30]) & rare["annotation_count_k"].isin([4, 8, 12, 20])].to_markdown(index=False),
        "",
        "## 4. 元标签不确定性",
        "",
        meta_summary.to_markdown(index=False) if not meta_summary.empty else "未检出可解析元标签。",
        "",
        "元标签分析保留 raw choice，并另外映射为 Difficulty、Scope、Model Issue 和其他选择。Pairwise Jaccard 衡量两名工人选择集合的重叠；mean label entropy 衡量每个二元标签在任务内的分散程度。raw 修订版本被保留，因此该部分是标签生成过程的全量描述，不把同一工人的修订当作独立人群抽样。",
        "",
        "## 5. 几何标注不确定性",
        "",
        geometry_tasks.groupby(["stage", "condition"]).agg(
            task_count=("base_task_id", "nunique"), geometry_computable_workers=("geometry_computable_worker_count", "sum"),
            multiple_topology_task_count=("geometry_uncertainty_class", lambda values: sum(value == "multiple_topologies" for value in values)),
            median_topology_entropy=("topology_shannon_entropy", "median"),
            median_same_topology_rmse=("same_topology_cyclic_rmse_median", "median"),
        ).reset_index().to_markdown(index=False) if not geometry_tasks.empty else "几何任务表为空。",
        "",
        "跨阶段表使用角点数量作为拓扑签名，并在相同拓扑内计算循环/反向对齐 RMSE。这是描述性公共尺度；C1 的正式几何模式仍以冻结 boundary/wall-wall similarity 与 complete-link 分区为准。",
        "",
        persistent_summary.to_markdown(index=False) if not persistent_summary.empty else "未读取持续分歧目录。",
        "",
        "## 6. Active time 与 Lead time",
        "",
        time_summary.to_markdown(index=False),
        "",
        "Active time 表示脚本记录的活跃交互；C1 使用 project×runtime task×worker、session 内最大累计秒数、跨合格 session 求和的正式规则。Lead time 是 Label Studio 的界面经过时间。二者从未相互填补。",
        "",
        "### 6.1 同图条件配对时间",
        "",
        time_paired.groupby(["stage", "metric"]).agg(
            paired_task_count=("base_task_id", "size"), mean_semi_minus_manual_seconds=("semi_minus_manual_seconds", "mean"),
            median_semi_minus_manual_seconds=("semi_minus_manual_seconds", "median"), median_ratio=("semi_to_manual_ratio", "median"),
        ).reset_index().to_markdown(index=False) if not time_paired.empty else "没有形成同阶段同图 Manual/Semi 时间配对。",
        "",
        "### 6.2 Active/Lead 关系",
        "",
        time_relation.to_markdown(index=False) if not time_relation.empty else "共同可计算记录不足。",
        "",
        "## 7. 工人共识与 GT 的关系",
        "",
        conflict_summary.to_markdown(index=False) if not conflict_summary.empty else "GT/crowd 簇关系不可计算。",
        "",
        "Crowd 簇先由 GT-blind 几何形成，再比较各簇成员与 operational GT 的 IoU。`multimodal_minority_cluster_better_gt_alignment` 只表示按显示阈值，非最大簇的中位 IoU比最大簇至少高 0.05；它不是自动改写 GT 的依据。",
        "",
        "## 8. 工人是否形成稳定不同观点",
        "",
        worker_view.sort_values("task_count", ascending=False).head(23).to_markdown(index=False) if not worker_view.empty else "工人簇成员关系不可计算。",
        "",
    ]
    if not view_test.empty:
        row = view_test.iloc[0]
        lines += [
            f"在每名工人至少 5 个可分区 task-condition 的描述性检验中，工人最大模式率的方差为 {_fmt(row.get('observed_worker_rate_variance'), 4)}，"
            f"task-stratified permutation p={_fmt(row.get('permutation_p_value'), 4)}。该检验只回答模式成员倾向是否超过任务内随机分配；不判断哪种观点正确，也不能区分协议理解、视觉策略与能力。",
            "",
        ]
    lines += [
        "## 9. 其他数据关系",
        "",
        associations.to_markdown(index=False) if not associations.empty else "没有形成可评价关联。",
        "",
        mechanism.to_markdown(index=False) if not mechanism.empty else "Semi proposal 机制数据不可计算。",
        "",
        "所有相关均标记为描述性关联。特别是 edit magnitude、active time、worker aggregate 与 geometry entropy 存在任务组成、工人组成和阶段差异，不能由相关系数推断因果。",
        "",
        "## 10. 具体任务案例",
        "",
        cases.head(60).to_markdown(index=False),
        "",
        "每一类主要结果均在 `TASK_CASE_CATALOG.csv` 中保留 task ID、图片引用、阶段、条件、相关数值和中性说明。报告正文只显示前 60 行。",
        "",
        "## 11. 不能由当前数据回答的问题",
        "",
        "1. 当前 C1 Manual/Semi 分配不是完整的图像级随机实验，因此差异是关联而非因果效应。",
        "2. 当前只有 9 个 independent building 支撑总体 Manual/Semi 不确定性比较；同一图片增加工人数不能替代新增 building。",
        "3. 多峰簇仍可能混合图像歧义、协议歧义、工人错误、表示限制和硬阈值/聚类算法效应；专家 mode audit 尚未进入本报告。",
        "4. Lead time 是 elapsed time，不是 active engagement；不同脚本版本的 active time 通过 stage/source 字段分层，不能假定完全同质。",
        "5. 工人 viewpoint 检验使用重复任务中的簇成员关系，不能自动转化为工人质量排名。",
        "6. GT 冲突表只比较已冻结 operational GT 与 crowd 簇；多数共识和 GT 均可能受到协议/参考问题影响。",
        "",
        "## 12. 文件与可复现性",
        "",
        provenance.to_markdown(index=False),
        "",
        "全部英文变量的中文解释和近似计算公式见 `DATA_DICTIONARY_ZH.csv`；所有输出 SHA-256 见 `OUTPUT_MANIFEST.csv`。",
    ]
    return "\n".join(lines) + "\n"


def make_plots(output: Path, projection: pd.DataFrame, time_summary: pd.DataFrame, geometry_tasks: pd.DataFrame) -> None:
    if not projection.empty:
        subset = projection[projection["assumed_true_absolute_effect"].eq(0.10)].drop_duplicates("projected_independent_building_count")
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(subset["projected_independent_building_count"], subset["projected_95ci_half_width"], marker="o")
        ax.set_xlabel("Projected independent building count")
        ax.set_ylabel("Projected 95% CI half-width")
        ax.set_title("Manual/Semi entropy-effect precision projection")
        fig.tight_layout()
        fig.savefig(output / "SEMI_PRECISION_PROJECTION.png", dpi=180)
        plt.close(fig)
    if not time_summary.empty:
        subset = time_summary[time_summary["metric"].eq("active_time")].copy()
        labels = subset["stage"].astype(str) + "/" + subset["condition"].astype(str)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(labels, subset["median_seconds"])
        ax.set_ylabel("Median active seconds")
        ax.set_title("Observed active time by stage and mode")
        ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        fig.savefig(output / "ACTIVE_TIME_STAGE_MODE.png", dpi=180)
        plt.close(fig)
    if not geometry_tasks.empty:
        subset = geometry_tasks[geometry_tasks["geometry_computable_worker_count"] >= 2]
        summary = subset.groupby("stage", as_index=False)["topology_shannon_entropy"].median()
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(summary["stage"], summary["topology_shannon_entropy"])
        ax.set_ylabel("Median topology entropy")
        ax.set_title("Cross-stage topology uncertainty (descriptive)")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(output / "GEOMETRY_UNCERTAINTY_BY_STAGE.png", dpi=180)
        plt.close(fig)


def materialize(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    unified = load_unified_stage_submissions()
    raw = load_raw_annotation_fact()
    coverage = coverage_summary(unified, raw)
    geometry_tasks, geometry_pairs = cross_stage_geometry_uncertainty(unified)
    meta_long, meta_responses, meta_tasks = meta_label_uncertainty(raw)
    gt_conflict, gt_clusters = c1_crowd_gt_conflict()
    memberships, worker_view, cotendency, viewpoint_test = worker_viewpoint_stability()
    persistent = persistent_disagreement_catalog()
    time_frame, time_summary, time_paired, time_relation, time_outliers_models = time_analysis(unified)
    projection, rare, current_semi = semi_precision_projection()
    associations, task_deep, mechanism = deep_associations(unified, meta_tasks, gt_conflict)
    cases = task_case_catalog(raw, geometry_tasks, meta_tasks, gt_conflict, memberships, time_frame)
    dictionary = data_dictionary()
    provenance = source_provenance()

    outputs = {
        "UNIFIED_SUBMISSION_EVIDENCE.csv": unified,
        "DATA_COVERAGE_BY_STAGE_MODE.csv": coverage,
        "RAW_META_LABEL_RESPONSE_LONG.csv": meta_long,
        "RAW_META_LABEL_RESPONSE_SETS.csv": meta_responses,
        "META_LABEL_TASK_UNCERTAINTY.csv": meta_tasks,
        "GEOMETRY_TASK_UNCERTAINTY_ALL_STAGES.csv": geometry_tasks,
        "GEOMETRY_PAIRWISE_DISPERSION_ALL_STAGES.csv": geometry_pairs,
        "PERSISTENT_DISAGREEMENT_CATALOG.csv": persistent,
        "C1_CROWD_GT_CONFLICT_TASKS.csv": gt_conflict,
        "C1_CROWD_GT_CLUSTER_METRICS.csv": gt_clusters,
        "C1_WORKER_TASK_MODE_MEMBERSHIP.csv": memberships,
        "WORKER_VIEWPOINT_STABILITY.csv": worker_view,
        "WORKER_VIEWPOINT_COTENDENCY.csv": cotendency,
        "WORKER_VIEWPOINT_TESTS_AND_EXCLUDED.csv": viewpoint_test,
        "TIME_SUBMISSION_EVIDENCE.csv": time_frame,
        "TIME_STAGE_MODE_SUMMARY.csv": time_summary,
        "TIME_MANUAL_SEMI_TASK_PAIRS.csv": time_paired,
        "TIME_ACTIVE_LEAD_RELATION.csv": time_relation,
        "TIME_OUTLIERS_AND_MODELS.csv": time_outliers_models,
        "SEMI_DATA_PRECISION_PROJECTION.csv": projection,
        "RARE_MODE_DETECTION_PROBABILITY.csv": rare,
        "CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.csv": current_semi,
        "DEEP_MINING_ASSOCIATIONS.csv": associations,
        "DEEP_MINING_TASK_TABLE.csv": task_deep,
        "DEEP_MINING_WORKER_AND_MECHANISM_TABLES.csv": mechanism,
        "TASK_CASE_CATALOG.csv": cases,
        "DATA_DICTIONARY_ZH.csv": dictionary,
        "INPUT_PROVENANCE.csv": provenance,
    }
    for name, frame in outputs.items():
        write_csv(output / name, frame)

    report = generate_report(
        coverage, current_semi, projection, rare, meta_tasks, geometry_tasks, persistent,
        time_summary, time_paired, time_relation, gt_conflict, worker_view, viewpoint_test,
        associations, mechanism[mechanism.get("table", pd.Series(dtype=str)).ne("worker_components")] if not mechanism.empty else mechanism,
        cases, provenance,
    )
    (output / "FULL_UNCERTAINTY_DATA_REPORT_ZH.md").write_text(report, encoding="utf-8")
    make_plots(output, projection, time_summary, geometry_tasks)

    run_summary = {
        "git_head": git_head(),
        "selected_or_auditable_record_count": len(unified),
        "raw_annotation_version_count": len(raw),
        "worker_count": int(unified["worker_id"].nunique()) if not unified.empty else 0,
        "base_task_count": int(unified["base_task_id"].nunique()) if not unified.empty else 0,
        "stage_count": int(unified["stage"].nunique()) if not unified.empty else 0,
        "meta_label_choice_count": len(meta_long),
        "geometry_task_condition_count": len(geometry_tasks),
        "crowd_gt_task_condition_count": len(gt_conflict),
        "worker_viewpoint_supported_worker_count": int((worker_view["task_count"] >= 5).sum()) if not worker_view.empty else 0,
        "data_mining_population_rule": "retain_all_records;exclude_only_when_requested_variable_not_computable",
        "lead_time_used_as_active_time_fallback": False,
        "later_stage_eligibility_used_as_global_filter": False,
    }
    write_json(output / "RUN_SUMMARY.json", run_summary)
    manifest = manifest_for_directory(output)
    write_csv(output / "OUTPUT_MANIFEST.csv", manifest)
    return run_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    summary = materialize(args.output_dir.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
