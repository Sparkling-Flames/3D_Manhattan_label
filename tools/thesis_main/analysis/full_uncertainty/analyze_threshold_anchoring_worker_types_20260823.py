"""Independent follow-up audit for annotation uncertainty.

This analysis re-computes threshold results from frozen pairwise evidence and
performs follow-up audits from hash-recorded v5 materializations.  It does not
consume the prose conclusions in the v5 report as data, and the v5 tables remain
derived evidence rather than primary input truth.

Outputs:
- geometry threshold sensitivity, including q >= 0.90;
- k-prefix replay sensitivity for the frozen k=22 C1 tasks;
- proposal correctness / human response / shared-initialization analysis;
- exploratory latent annotator structure with split-half stability checks;
- robust empirical multimodality candidates for blind expert review.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import warnings
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import RobustScaler

from tools.thesis_main.analysis import materialize_annotation_uncertainty_manual_semi as ms
from tools.thesis_main.analysis import run_topology_sequential_preflight as topology
from tools.thesis_main.analysis.full_uncertainty import full_uncertainty_prefix_replay_v5 as prefix


ROOT = Path(__file__).resolve().parents[4]
V5 = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"
OUT = ROOT / "analysis_results" / "uncertainty_threshold_anchoring_worker_types_20260823"
SEED = 20260823
THRESHOLDS = (0.90, 0.925, 0.93, 0.95, 0.97, 0.98)
PREFIX_THRESHOLDS = (0.90, 0.925, 0.95, 0.98)
PREFIX_REPLICATES = int(os.environ.get("PREFIX_REPLICATES", "100"))
BOOTSTRAP_REPLICATES = int(os.environ.get("BOOTSTRAP_REPLICATES", "4000"))
SPLIT_REPEATS = int(os.environ.get("SPLIT_REPEATS", "300"))


# ---------------------------------------------------------------------------
# Basic IO / audit helpers
# ---------------------------------------------------------------------------

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def read_csv(name: str) -> pd.DataFrame:
    path = V5 / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def write_csv(name: str, frame: pd.DataFrame) -> None:
    frame.to_csv(OUT / name, index=False, encoding="utf-8-sig", lineterminator="\n")


def write_text(name: str, value: str) -> None:
    with (OUT / name).open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def write_json(name: str, value: Any) -> None:
    write_text(
        name,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=json_default) + "\n",
    )


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(type(value).__name__)


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {
        "1", "true", "yes", "y", "passed", "valid", "eligible", "matched",
    }


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def norm_worker(value: Any) -> str:
    text = str(value).strip().upper()
    if text.startswith("W"):
        text = text[1:]
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def safe_rate(numerator: float | int, denominator: float | int) -> float | None:
    return float(numerator) / float(denominator) if denominator else None


def jeffreys_rate(success: float, total: float) -> float | None:
    return (float(success) + 0.5) / (float(total) + 1.0) if total > 0 else None


def classify_change(value: Any, tol: float = 0.01) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "not_computable"
    if not math.isfinite(x):
        return "not_computable"
    if x < -tol:
        return "decrease"
    if x > tol:
        return "increase"
    return "near_zero"


def bh_adjust(values: Sequence[float | None]) -> list[float | None]:
    pairs = [(i, float(v)) for i, v in enumerate(values) if v is not None and math.isfinite(float(v))]
    result: list[float | None] = [None] * len(values)
    if not pairs:
        return result
    ordered = sorted(pairs, key=lambda p: p[1])
    m = len(ordered)
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m - 1, -1, -1):
        value = ordered[rank][1] * m / (rank + 1)
        running = min(running, value)
        adjusted[rank] = min(1.0, running)
    for (idx, _), adj in zip(ordered, adjusted):
        result[idx] = adj
    return result


def holm_adjust(values: Sequence[float | None]) -> list[float | None]:
    pairs = sorted((float(v), i) for i, v in enumerate(values) if v is not None and math.isfinite(float(v)))
    result: list[float | None] = [None] * len(values)
    running = 0.0
    m = len(pairs)
    for rank, (value, idx) in enumerate(pairs):
        running = max(running, min(1.0, value * (m - rank)))
        result[idx] = running
    return result


def exact_sign_flip_task_weighted(frame: pd.DataFrame, value: str, cluster: str = "building_id") -> float | None:
    data = frame[[cluster, value]].dropna().copy()
    clusters = sorted(data[cluster].astype(str).unique())
    if len(clusters) < 3 or len(clusters) > 20:
        return None
    x = numeric(data[value]).to_numpy(float)
    observed = abs(float(np.mean(x)))
    ids = data[cluster].astype(str).to_numpy()
    permuted: list[float] = []
    for mask in range(1 << len(clusters)):
        signed = x.copy()
        for j, cid in enumerate(clusters):
            signed[ids == cid] *= 1.0 if ((mask >> j) & 1) else -1.0
        permuted.append(abs(float(np.mean(signed))))
    return float(np.mean(np.asarray(permuted) >= observed - 1e-15))


def cluster_bootstrap_mean(
    frame: pd.DataFrame,
    value: str,
    cluster: str = "building_id",
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> tuple[float | None, float | None, float | None]:
    data = frame[[cluster, value]].dropna().copy()
    if len(data) < 3 or data[cluster].nunique() < 2:
        return None, None, None
    groups = {
        str(cid): numeric(group[value]).dropna().to_numpy(float)
        for cid, group in data.groupby(cluster, sort=True)
    }
    groups = {k: v for k, v in groups.items() if len(v)}
    ids = sorted(groups)
    observed = float(numeric(data[value]).mean())
    rng = np.random.default_rng(seed)
    draws = np.empty(replicates, dtype=float)
    for b in range(replicates):
        sampled = rng.choice(ids, size=len(ids), replace=True)
        draws[b] = float(np.concatenate([groups[cid] for cid in sampled]).mean())
    return observed, float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def cluster_bootstrap_proportion(
    frame: pd.DataFrame,
    flag: str,
    cluster: str = "building_id",
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> tuple[float | None, float | None, float | None]:
    data = frame[[cluster, flag]].dropna().copy()
    if len(data) < 3 or data[cluster].nunique() < 2:
        return None, None, None
    data[flag] = numeric(data[flag])
    return cluster_bootstrap_mean(data, flag, cluster, replicates, seed)


def cluster_bootstrap_spearman(
    frame: pd.DataFrame,
    x: str,
    y: str,
    cluster: str = "building_id",
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> dict[str, Any]:
    data = frame[[cluster, x, y]].dropna().copy()
    data[x] = numeric(data[x])
    data[y] = numeric(data[y])
    data = data.dropna()
    if len(data) < 5 or data[x].nunique() < 3 or data[y].nunique() < 3:
        return {
            "n": len(data), "n_clusters": data[cluster].nunique(), "rho": None,
            "p_naive": None, "ci_lower": None, "ci_upper": None,
            "status": "not_identifiable",
        }
    rho, p = stats.spearmanr(data[x], data[y])
    groups = {str(cid): group.copy() for cid, group in data.groupby(cluster, sort=True)}
    ids = sorted(groups)
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    for _ in range(replicates):
        sampled = rng.choice(ids, size=len(ids), replace=True)
        boot = pd.concat([groups[cid] for cid in sampled], ignore_index=True)
        if boot[x].nunique() >= 3 and boot[y].nunique() >= 3:
            value = stats.spearmanr(boot[x], boot[y]).statistic
            if math.isfinite(float(value)):
                draws.append(float(value))
    return {
        "n": len(data),
        "n_clusters": len(ids),
        "rho": float(rho),
        "p_naive": float(p),
        "ci_lower": float(np.quantile(draws, 0.025)) if draws else None,
        "ci_upper": float(np.quantile(draws, 0.975)) if draws else None,
        "status": "estimated" if draws else "bootstrap_failed",
    }


def input_audit(paths: Sequence[Path]) -> pd.DataFrame:
    rows = []
    frozen_c1_root = topology.c1_root(ROOT)
    for path in paths:
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "exists": path.is_file(),
            "size_bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
            "source_layer": (
                "frozen_c1_evidence" if path.is_relative_to(frozen_c1_root)
                else "derived_materialization" if path.is_relative_to(ROOT / "analysis_results")
                else "repository_input"
            ),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1) Threshold sensitivity re-computation
# ---------------------------------------------------------------------------

def recompute_formal_threshold_grid() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original = ms.THRESHOLDS
    try:
        ms.THRESHOLDS = THRESHOLDS
        tasks, buildings, _, nodes, pair_map = ms.sample_and_pairs()
        reclustered = ms.exhaustive_reclustering(tasks, nodes, pair_map)
        metrics = ms.aggregate_task_metrics(reclustered, buildings)
    finally:
        ms.THRESHOLDS = original

    # Add partition-failure co-outcome and stable direction coding.
    for condition in ("manual", "semi"):
        metrics[f"{condition}_partition_failure_rate"] = (
            numeric(metrics[f"{condition}_nonunique_or_not_evaluable_count"])
            / numeric(metrics[f"{condition}_subset_count"])
        )
    metrics["delta_partition_failure_rate"] = (
        metrics["semi_partition_failure_rate"] - metrics["manual_partition_failure_rate"]
    )
    metrics["entropy_direction_tol_001"] = metrics["delta_shannon_entropy"].map(lambda x: classify_change(x, 0.01))
    metrics["entropy_direction_tol_005"] = metrics["delta_shannon_entropy"].map(lambda x: classify_change(x, 0.05))
    metrics["quality_direction_tol_001"] = metrics.get("delta_quality_iou", pd.Series(index=metrics.index, dtype=float)).map(
        lambda x: classify_change(x, 0.01)
    )

    metric_names = [
        "delta_shannon_entropy", "delta_gini_simpson", "delta_largest_mode_share",
        "delta_supported_multimodality", "delta_mode_count",
        "delta_pairwise_correspondence_disagreement", "delta_pairwise_metric_dissimilarity_all",
        "delta_partition_failure_rate",
    ]
    summary_rows: list[dict[str, Any]] = []
    for ti, threshold in enumerate(THRESHOLDS):
        subset = metrics[np.isclose(numeric(metrics["threshold"]), threshold)].copy()
        for mi, metric in enumerate(metric_names):
            observed, lo, hi = cluster_bootstrap_mean(
                subset, metric, seed=SEED + 1000 * ti + mi,
            )
            summary_rows.append({
                "population": "formal22_recomputed_from_frozen_pairwise",
                "threshold": threshold,
                "metric": metric,
                "n_tasks": int(subset[metric].notna().sum()),
                "n_buildings": int(subset.loc[subset[metric].notna(), "building_id"].nunique()),
                "mean_difference": observed,
                "cluster_bootstrap_ci_lower": lo,
                "cluster_bootstrap_ci_upper": hi,
                "building_exact_sign_flip_p": exact_sign_flip_task_weighted(subset, metric),
            })
    summary = pd.DataFrame(summary_rows)
    summary["holm_p_within_threshold"] = None
    for threshold, idx in summary.groupby("threshold").groups.items():
        values = summary.loc[idx, "building_exact_sign_flip_p"].tolist()
        summary.loc[idx, "holm_p_within_threshold"] = holm_adjust(values)

    status_rows: list[dict[str, Any]] = []
    for threshold, subset in metrics.groupby("threshold", sort=True):
        for tol_col in ("entropy_direction_tol_001", "entropy_direction_tol_005"):
            counts = subset[tol_col].value_counts(dropna=False)
            status_rows.append({
                "population": "formal22_recomputed_from_frozen_pairwise",
                "threshold": threshold,
                "direction_rule": tol_col,
                "n_tasks": len(subset),
                "decrease_count": int(counts.get("decrease", 0)),
                "near_zero_count": int(counts.get("near_zero", 0)),
                "increase_count": int(counts.get("increase", 0)),
                "not_computable_count": int(counts.get("not_computable", 0)),
            })
    status = pd.DataFrame(status_rows)

    # Per-task robustness over q>=0.90.
    robust_rows: list[dict[str, Any]] = []
    for task, group in metrics.groupby("base_task_id", sort=True):
        vals = numeric(group["delta_shannon_entropy"]).dropna()
        dirs_001 = group["entropy_direction_tol_001"].tolist()
        dirs_005 = group["entropy_direction_tol_005"].tolist()
        robust_rows.append({
            "base_task_id": task,
            "building_id": str(group["building_id"].iloc[0]),
            "threshold_count": len(group),
            "evaluable_threshold_count": len(vals),
            "delta_entropy_min": float(vals.min()) if len(vals) else None,
            "delta_entropy_max": float(vals.max()) if len(vals) else None,
            "delta_entropy_range": float(vals.max() - vals.min()) if len(vals) else None,
            "sign_stable_tol_001": len(dirs_001) == len(THRESHOLDS) and "not_computable" not in dirs_001 and len(set(dirs_001)) == 1,
            "sign_stable_tol_005": len(dirs_005) == len(THRESHOLDS) and "not_computable" not in dirs_005 and len(set(dirs_005)) == 1,
            "directions_tol_001": ";".join(dirs_001),
            "directions_tol_005": ";".join(dirs_005),
            "manual_partition_failure_min": float(group["manual_partition_failure_rate"].min()),
            "manual_partition_failure_max": float(group["manual_partition_failure_rate"].max()),
            "semi_partition_failure_min": float(group["semi_partition_failure_rate"].min()),
            "semi_partition_failure_max": float(group["semi_partition_failure_rate"].max()),
            "delta_supported_multimodality_min": float(numeric(group["delta_supported_multimodality"]).min()),
            "delta_supported_multimodality_max": float(numeric(group["delta_supported_multimodality"]).max()),
        })
    robustness = pd.DataFrame(robust_rows)

    transitions: list[dict[str, Any]] = []
    reference = metrics[np.isclose(numeric(metrics["threshold"]), 0.95)][
        ["base_task_id", "entropy_direction_tol_005"]
    ].rename(columns={"entropy_direction_tol_005": "direction_q095"})
    for threshold in THRESHOLDS:
        comparison = metrics[np.isclose(numeric(metrics["threshold"]), threshold)][
            ["base_task_id", "entropy_direction_tol_005"]
        ].rename(columns={"entropy_direction_tol_005": "direction_other"})
        joined = reference.merge(comparison, on="base_task_id", how="inner")
        for (left, right), count in joined.groupby(["direction_q095", "direction_other"]).size().items():
            transitions.append({
                "reference_threshold": 0.95,
                "comparison_threshold": threshold,
                "direction_q095": left,
                "direction_comparison": right,
                "task_count": int(count),
            })
    transition_frame = pd.DataFrame(transitions)
    return reclustered, metrics, summary, status, robustness, transition_frame


def reaggregate_inclusive25_existing_thresholds() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = read_csv("TASK_SUBSET_RECLUSTERING.CSV")
    raw["threshold"] = numeric(raw["threshold"])
    rows: list[dict[str, Any]] = []
    metrics_list = [
        "shannon_entropy", "gini_simpson", "largest_mode_share", "supported_multimodality",
        "mode_count", "pairwise_correspondence_disagreement", "pairwise_metric_dissimilarity_all",
    ]
    for (threshold, task), group in raw.groupby(["threshold", "base_task_id"], sort=True):
        row: dict[str, Any] = {
            "threshold": float(threshold),
            "base_task_id": str(task),
            "common_k": int(numeric(group["common_k"]).iloc[0]),
        }
        for condition in ("manual", "semi"):
            part = group[group["condition"].astype(str).str.lower().eq(condition)]
            row[f"{condition}_subset_count"] = len(part)
            unique = part["partition_status"].astype(str).eq("unique")
            row[f"{condition}_partition_failure_rate"] = float((~unique).mean()) if len(part) else None
            for metric in metrics_list:
                values = numeric(part[metric])
                row[f"{condition}_{metric}"] = float(values.mean()) if values.notna().any() else None
        for metric in metrics_list:
            a, b = row.get(f"manual_{metric}"), row.get(f"semi_{metric}")
            row[f"delta_{metric}"] = b - a if a is not None and b is not None else None
        a, b = row.get("manual_partition_failure_rate"), row.get("semi_partition_failure_rate")
        row["delta_partition_failure_rate"] = b - a if a is not None and b is not None else None
        rows.append(row)
    task = pd.DataFrame(rows)
    # Building binding comes from the 25-task table.
    binding = read_csv("SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv")[["base_task_id", "building_id"]].drop_duplicates()
    task = task.merge(binding, on="base_task_id", how="left", validate="many_to_one")
    task["entropy_direction_tol_005"] = task["delta_shannon_entropy"].map(lambda x: classify_change(x, 0.05))

    out: list[dict[str, Any]] = []
    for ti, (threshold, subset) in enumerate(task.groupby("threshold", sort=True)):
        for mi, metric in enumerate([f"delta_{m}" for m in metrics_list] + ["delta_partition_failure_rate"]):
            observed, lo, hi = cluster_bootstrap_mean(subset, metric, seed=SEED + 3000 + 100 * ti + mi)
            out.append({
                "population": "inclusive25_reaggregated_from_v5_subset_reclustering",
                "threshold": threshold,
                "metric": metric,
                "n_tasks": int(subset[metric].notna().sum()),
                "n_buildings": int(subset.loc[subset[metric].notna(), "building_id"].nunique()),
                "mean_difference": observed,
                "cluster_bootstrap_ci_lower": lo,
                "cluster_bootstrap_ci_upper": hi,
                "building_exact_sign_flip_p": exact_sign_flip_task_weighted(subset, metric),
            })
    summary = pd.DataFrame(out)
    return task, summary


def replay_k22_across_thresholds() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = prefix.load_frozen_c1_k22_tasks(ROOT)
    old_b, old_w = topology.Q_BOUNDARY, topology.Q_WALLWALL
    all_rows: list[dict[str, Any]] = []
    try:
        for threshold in PREFIX_THRESHOLDS:
            topology.Q_BOUNDARY = threshold
            topology.Q_WALLWALL = threshold
            rows = prefix.replay_frozen_c1_k22_prefixes(
                candidates,
                cluster_fn=topology._cluster,
                seed=SEED,
                replicates=PREFIX_REPLICATES,
            )
            for row in rows:
                item = dict(row)
                item["threshold"] = threshold
                all_rows.append(item)
    finally:
        topology.Q_BOUNDARY, topology.Q_WALLWALL = old_b, old_w

    raw = pd.DataFrame(all_rows)
    summary_rows: list[dict[str, Any]] = []
    per_task_rows: list[dict[str, Any]] = []
    status_values = ["unimodal", "dominant_with_dissent", "supported_multimodal", "not_evaluable"]
    for (threshold, k), group in raw.groupby(["threshold", "k"], sort=True):
        counts = group["task_crowd_structure_status"].value_counts()
        row = {
            "threshold": threshold,
            "k": int(k),
            "task_count": group["base_task_id"].nunique(),
            "row_count": len(group),
            "replicates_per_task": int(group.groupby("base_task_id").size().iloc[0]),
        }
        for status in status_values:
            row[f"{status}_count"] = int(counts.get(status, 0))
            row[f"{status}_rate"] = float(counts.get(status, 0) / len(group))
        summary_rows.append(row)
        for task, task_group in group.groupby("base_task_id", sort=True):
            task_counts = task_group["task_crowd_structure_status"].value_counts()
            task_row = {
                "threshold": threshold,
                "k": int(k),
                "base_task_id": task,
                "replicate_count": len(task_group),
            }
            for status in status_values:
                task_row[f"{status}_rate"] = float(task_counts.get(status, 0) / len(task_group))
            if int(k) == 22 and len(task_group) == 1:
                cluster_json = str(task_group["cluster_membership_json"].iloc[0] or "")
                try:
                    clusters = json.loads(cluster_json)
                    sizes = sorted((len(c) for c in clusters), reverse=True)
                except Exception:
                    sizes = []
                task_row["full_status"] = str(task_group["task_crowd_structure_status"].iloc[0])
                task_row["full_cluster_sizes"] = ";".join(map(str, sizes))
                task_row["full_largest_support"] = sizes[0] if sizes else None
                task_row["full_second_support"] = sizes[1] if len(sizes) > 1 else 0 if sizes else None
            per_task_rows.append(task_row)
    summary = pd.DataFrame(summary_rows)
    per_task = pd.DataFrame(per_task_rows)

    # Detection curves conditional on the full k=22 status under the same threshold.
    full = per_task[per_task["k"].eq(22)][
        ["threshold", "base_task_id", "full_status", "full_cluster_sizes", "full_largest_support", "full_second_support"]
    ]
    conditional = per_task.merge(full, on=["threshold", "base_task_id"], how="left", suffixes=("", "_full"))
    conditional_summary: list[dict[str, Any]] = []
    for (threshold, full_status, k), group in conditional.groupby(["threshold", "full_status", "k"], dropna=False, sort=True):
        conditional_summary.append({
            "threshold": threshold,
            "full_k22_status": full_status,
            "k": int(k),
            "task_count": group["base_task_id"].nunique(),
            "mean_prefix_supported_multimodal_rate": float(group["supported_multimodal_rate"].mean()),
            "mean_prefix_not_evaluable_rate": float(group["not_evaluable_rate"].mean()),
            "mean_prefix_unimodal_rate": float(group["unimodal_rate"].mean()),
        })
    return summary, per_task, pd.DataFrame(conditional_summary)


# ---------------------------------------------------------------------------
# 2) Proposal correctness, response, anchoring, and false-consensus candidates
# ---------------------------------------------------------------------------

def task_mechanism_label(row: pd.Series) -> str:
    uncertainty = classify_change(row.get("delta_shannon_entropy"), 0.05)
    quality = classify_change(row.get("delta_iou_to_gt"), 0.01)
    if uncertainty == "decrease" and quality == "increase":
        return "agreement_gain_with_quality_gain"
    if uncertainty == "decrease" and quality in {"near_zero", "decrease"}:
        return "consensus_inflation_candidate"
    if uncertainty == "increase" and quality == "increase":
        return "productive_diversification_candidate"
    if uncertainty == "increase" and quality in {"near_zero", "decrease"}:
        return "dispersion_without_quality_gain_candidate"
    if uncertainty == "near_zero" and quality == "increase":
        return "quality_gain_without_distribution_change"
    if uncertainty == "near_zero" and quality in {"near_zero", "decrease"}:
        return "near_zero_or_tradeoff"
    return "not_evaluable"


def mantel_haenszel_or(rows: pd.DataFrame, correct_col: str, condition_col: str = "condition") -> dict[str, Any]:
    # a=semi correct, b=semi incorrect, c=manual correct, d=manual incorrect.
    numerator = 0.0
    denominator = 0.0
    informative = 0
    tables = []
    for task, group in rows.groupby("base_task_id", sort=True):
        semi = group[group[condition_col].astype(str).str.lower().eq("semi")]
        manual = group[group[condition_col].astype(str).str.lower().eq("manual")]
        if semi.empty or manual.empty:
            continue
        a = int(semi[correct_col].sum())
        b = int(len(semi) - a)
        c = int(manual[correct_col].sum())
        d = int(len(manual) - c)
        n = a + b + c + d
        if n == 0:
            continue
        numerator += a * d / n
        denominator += b * c / n
        informative += int((a + b) > 0 and (c + d) > 0)
        tables.append((a, b, c, d))
    estimate = numerator / denominator if denominator > 0 else (math.inf if numerator > 0 else None)
    # Approximate Robins-Breslow-Greenland-style log OR SE using score information.
    # For small data we also bootstrap tasks below in the caller.
    return {
        "task_strata": informative,
        "or_mh": estimate,
        "numerator": numerator,
        "denominator": denominator,
        "tables": tables,
    }


def bootstrap_mh_or_by_building(rows: pd.DataFrame, correct_col: str, reps: int = BOOTSTRAP_REPLICATES) -> tuple[float | None, float | None]:
    buildings = sorted(rows["building_id"].dropna().astype(str).unique())
    if len(buildings) < 4:
        return None, None
    contributions = [
        mantel_haenszel_or(rows[rows["building_id"].astype(str).eq(building)], correct_col)
        for building in buildings
    ]
    numerators = np.asarray([result["numerator"] for result in contributions], dtype=float)
    denominators = np.asarray([result["denominator"] for result in contributions], dtype=float)
    rng = np.random.default_rng(SEED + 4400)
    sampled = rng.integers(0, len(buildings), size=(reps, len(buildings)))
    numerator_draws = numerators[sampled].sum(axis=1)
    denominator_draws = denominators[sampled].sum(axis=1)
    valid = (numerator_draws > 0) & (denominator_draws > 0)
    if not valid.any():
        return None, None
    draws = np.log(numerator_draws[valid] / denominator_draws[valid])
    return float(math.exp(np.quantile(draws, 0.025))), float(math.exp(np.quantile(draws, 0.975)))


def proposal_correctness_and_anchoring() -> dict[str, pd.DataFrame]:
    task = read_csv("SEMI_PROPOSAL_TASK_TABLE.CSV")
    paired = read_csv("SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv")
    review = read_csv("SEMI_REVIEW_FACT.CSV")
    quality = read_csv("QUALITY_DATA_MINING_CONTEXTS.CSV")
    model_pairs = read_csv("PROPOSAL_MANUAL_SEMI_GEOMETRY_PAIRS.csv")

    task = task.merge(
        paired[[
            "base_task_id", "delta_largest_mode_share", "delta_supported_multimodality",
            "delta_pairwise_correspondence_disagreement", "delta_pairwise_metric_dissimilarity_all",
            "manual_nonunique_or_not_evaluable_count", "manual_subset_count",
            "semi_nonunique_or_not_evaluable_count", "semi_subset_count", "image_reference",
        ]],
        on="base_task_id", how="left", validate="one_to_one",
    )
    task["manual_partition_failure_rate"] = numeric(task["manual_nonunique_or_not_evaluable_count"]) / numeric(task["manual_subset_count"])
    task["semi_partition_failure_rate"] = numeric(task["semi_nonunique_or_not_evaluable_count"]) / numeric(task["semi_subset_count"])
    task["delta_partition_failure_rate"] = task["semi_partition_failure_rate"] - task["manual_partition_failure_rate"]
    task["mechanism_quadrant"] = task.apply(task_mechanism_label, axis=1)
    task["consensus_inflation_flag"] = (
        (numeric(task["delta_shannon_entropy"]) < -0.05)
        & (numeric(task["delta_iou_to_gt"]).fillna(-np.inf) <= 0.01)
    )
    task["shared_error_convergence_strict"] = (
        task["consensus_inflation_flag"]
        & (numeric(task["delta_iou_to_gt"]).fillna(np.inf) < -0.01)
    )
    task["proposal_quality_stratum"] = pd.cut(
        numeric(task["initial_quality_mean"]),
        bins=[-np.inf, 0.90, 0.95, 0.99, np.inf],
        labels=["below_0_90", "0_90_to_0_95", "0_95_to_0_99", "at_least_0_99"],
        right=False,
    ).astype("object").fillna("missing")

    # Quadrant counts with building-cluster proportion intervals.
    quadrant_rows = []
    for name in sorted(task["mechanism_quadrant"].unique()):
        temp = task.copy()
        temp["flag"] = temp["mechanism_quadrant"].eq(name).astype(float)
        observed, lo, hi = cluster_bootstrap_proportion(temp, "flag", seed=SEED + 5000 + len(quadrant_rows))
        quadrant_rows.append({
            "mechanism_quadrant": name,
            "task_count": int(temp["flag"].sum()),
            "total_task_count": len(temp),
            "task_rate": float(temp["flag"].mean()),
            "building_cluster_ci_lower": lo,
            "building_cluster_ci_upper": hi,
            "building_count": temp["building_id"].nunique(),
        })
    quadrant = pd.DataFrame(quadrant_rows)

    # Association table recomputed with building-cluster bootstrap.
    assoc_specs = [
        ("initial_quality_mean", "delta_shannon_entropy"),
        ("initial_quality_mean", "delta_iou_to_gt"),
        ("edit_rate", "delta_shannon_entropy"),
        ("edit_rate", "delta_iou_to_gt"),
        ("negative_metric_change_rate_001", "delta_shannon_entropy"),
        ("issue_report_rate", "delta_shannon_entropy"),
        ("delta_shannon_entropy", "delta_iou_to_gt"),
        ("delta_largest_mode_share", "delta_iou_to_gt"),
        ("delta_partition_failure_rate", "delta_iou_to_gt"),
    ]
    assoc_rows = []
    for i, (x, y) in enumerate(assoc_specs):
        result = cluster_bootstrap_spearman(task, x, y, seed=SEED + 5200 + i)
        assoc_rows.append({"predictor": x, "outcome": y, **result})
    assoc = pd.DataFrame(assoc_rows)
    assoc["q_bh_global_naive_task_rows"] = bh_adjust(assoc["p_naive"].tolist())

    # Row-level correctness response for P1/C1 proposal exposure.
    review["worker_id"] = review["worker_id"].map(norm_worker)
    for col in ("U_initial", "U_final", "delta_U", "geometry_edit_rmse_panorama_diagonal_normalized"):
        review[col] = numeric(review[col])
    review["exact_geometry_equal_bool"] = review["exact_geometry_equal"].map(truth)
    review["proposal_failure_bool"] = review["proposal_failure_binary"].map(truth) if "proposal_failure_binary" in review else review["proposal_failure"].map(truth)
    review["issue_reported_bool"] = review["issue_reported"].map(truth)
    review["current20_bool"] = review["current20_worker"].map(truth)
    review["analysis_eligible_bool"] = review["analysis_eligible"].map(truth)
    review["stage"] = review["stage"].astype(str)

    correctness_rows: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for stage_name, stage_group in [("P1", review[review["stage"].eq("P1")]), ("C1", review[review["stage"].eq("C1")]), ("P1_C1", review[review["stage"].isin(["P1", "C1"])])]:
        stage_group = stage_group[stage_group["analysis_eligible_bool"]].copy()
        for cutoff in (0.90, 0.95, 0.99):
            group = stage_group.dropna(subset=["U_initial", "U_final"]).copy()
            group["initial_correct"] = group["U_initial"] >= cutoff
            group["final_correct"] = group["U_final"] >= cutoff
            a = int(((group["initial_correct"]) & (group["final_correct"])).sum())
            b = int(((group["initial_correct"]) & (~group["final_correct"])).sum())
            c = int(((~group["initial_correct"]) & (group["final_correct"])).sum())
            d = int(((~group["initial_correct"]) & (~group["final_correct"])).sum())
            # Haldane-Anscombe stabilized association OR; this is not a causal assistance OR.
            or_assoc = ((a + 0.5) * (d + 0.5)) / ((b + 0.5) * (c + 0.5))
            correctness_rows.append({
                "stage_population": stage_name,
                "correctness_cutoff": cutoff,
                "row_count": len(group),
                "task_count": group["base_task_id"].nunique(),
                "worker_count": group["worker_id"].nunique(),
                "initial_correct_final_correct": a,
                "initial_correct_final_incorrect": b,
                "initial_incorrect_final_correct": c,
                "initial_incorrect_final_incorrect": d,
                "retention_rate_given_initial_correct": safe_rate(a, a + b),
                "degradation_rate_given_initial_correct": safe_rate(b, a + b),
                "correction_rate_given_initial_incorrect": safe_rate(c, c + d),
                "persistent_error_rate_given_initial_incorrect": safe_rate(d, c + d),
                "proposal_correctness_final_correctness_association_or": or_assoc,
                "causal_interpretation_allowed": False,
                "inference_status": "descriptive_only_repeated_worker_task_rows",
            })
            for initial_state, subset in group.groupby("initial_correct", sort=True):
                transitions.append({
                    "stage_population": stage_name,
                    "correctness_cutoff": cutoff,
                    "initial_correct": bool(initial_state),
                    "n": len(subset),
                    "exact_proposal_retention_rate": float(subset["exact_geometry_equal_bool"].mean()),
                    "mean_delta_U": float(subset["delta_U"].mean()),
                    "median_delta_U": float(subset["delta_U"].median()),
                    "issue_report_rate": float(subset["issue_reported_bool"].mean()),
                })
    correctness = pd.DataFrame(correctness_rows)
    transition_frame = pd.DataFrame(transitions)

    # Kiani-style comparison possible only if task-level proposal correctness has both strata.
    quality["condition"] = quality["condition"].astype(str).str.lower()
    quality["worker_id"] = quality["worker_id"].map(norm_worker)
    quality["iou_to_gt"] = numeric(quality["iou_to_gt"])
    quality = quality[
        quality["base_task_id"].isin(task["base_task_id"])
        & quality["iou_to_gt"].notna()
        & quality["quality_data_mining_included"].map(truth)
    ].copy()
    task_quality = task[["base_task_id", "initial_quality_mean"]].copy()
    quality = quality.merge(task_quality, on="base_task_id", how="left", validate="many_to_one")
    mh_rows = []
    for proposal_cutoff in (0.90, 0.95, 0.99):
        quality["proposal_correctness_observed"] = numeric(quality["initial_quality_mean"]).notna()
        quality["proposal_correct_stratum"] = numeric(quality["initial_quality_mean"]) >= proposal_cutoff
        for final_cutoff in (0.90, 0.95):
            quality["final_correct"] = quality["iou_to_gt"] >= final_cutoff
            for stratum in (True, False):
                sub = quality[quality["proposal_correctness_observed"] & quality["proposal_correct_stratum"].eq(stratum)].copy()
                result = mantel_haenszel_or(sub, "final_correct")
                lo, hi = bootstrap_mh_or_by_building(sub, "final_correct")
                mh_rows.append({
                    "proposal_correctness_cutoff": proposal_cutoff,
                    "proposal_correct_stratum": stratum,
                    "final_annotation_correctness_cutoff": final_cutoff,
                    "task_count": sub["base_task_id"].nunique(),
                    "building_count": sub["building_id"].nunique(),
                    "manual_row_count": int(sub["condition"].eq("manual").sum()),
                    "semi_row_count": int(sub["condition"].eq("semi").sum()),
                    "mantel_haenszel_or_semi_vs_manual": result["or_mh"],
                    "building_cluster_bootstrap_ci_lower": lo,
                    "building_cluster_bootstrap_ci_upper": hi,
                    "status": "estimated" if result["task_strata"] >= 3 and result["or_mh"] is not None and lo is not None else "not_identifiable",
                    "independence_unit": "building",
                    "causal_interpretation_allowed": False,
                })
    mh = pd.DataFrame(mh_rows)

    # Distance to shared proposal relative to independent Manual outputs.
    for col in (
        "model_to_manual_rmse_diagonal_normalized", "model_to_semi_rmse_diagonal_normalized",
        "manual_to_semi_rmse_diagonal_normalized", "model_gt_residual", "semi_gt_residual",
    ):
        model_pairs[col] = numeric(model_pairs[col])
    attraction_rows = []
    for task_id, group in model_pairs.groupby("base_task_id", sort=True):
        mm = group["model_to_manual_rmse_diagonal_normalized"].dropna()
        msd = group["model_to_semi_rmse_diagonal_normalized"].dropna()
        attraction_rows.append({
            "base_task_id": task_id,
            "pair_row_count": len(group),
            "model_to_manual_n": len(mm),
            "model_to_semi_n": len(msd),
            "model_to_manual_median": float(mm.median()) if len(mm) else None,
            "model_to_semi_median": float(msd.median()) if len(msd) else None,
            "proposal_attraction_ratio_median": (
                float(msd.median() / mm.median()) if len(msd) and len(mm) and mm.median() > 0 else None
            ),
            "reference_availability": ";".join(sorted(group["reference_availability"].dropna().astype(str).unique())),
        })
    attraction = pd.DataFrame(attraction_rows).merge(task[["base_task_id", "building_id", "delta_shannon_entropy", "delta_iou_to_gt"]], on="base_task_id", how="left")

    # Row-level task/worker response table for downstream worker typology.
    response_cols = [
        "stage", "base_task_id", "building_id", "worker_id", "U_initial", "U_final", "delta_U",
        "exact_geometry_equal_bool", "proposal_failure_bool", "issue_reported_bool",
        "geometry_edit_rmse_panorama_diagonal_normalized", "current20_bool", "analysis_eligible_bool",
        "model_issue_choice", "planned_trap_family", "trap_family", "semi_role",
    ]
    response = review[response_cols].copy()
    response["proposal_correctness_observed_095"] = response["U_initial"].notna() & response["U_final"].notna()
    response["initial_correct_095"] = response["proposal_correctness_observed_095"] & (response["U_initial"] >= 0.95)
    response["final_correct_095"] = response["proposal_correctness_observed_095"] & (response["U_final"] >= 0.95)
    response["correct_proposal_degraded_095"] = response["proposal_correctness_observed_095"] & response["initial_correct_095"] & (~response["final_correct_095"])
    response["wrong_proposal_corrected_095"] = response["proposal_correctness_observed_095"] & (~response["initial_correct_095"]) & response["final_correct_095"]
    response["wrong_proposal_retained_exact"] = response["proposal_correctness_observed_095"] & (~response["initial_correct_095"]) & response["exact_geometry_equal_bool"]

    return {
        "proposal_task_mechanism": task,
        "proposal_mechanism_quadrants": quadrant,
        "proposal_associations_building_clustered": assoc,
        "proposal_correctness_transitions": correctness,
        "proposal_correctness_response_summary": transition_frame,
        "proposal_correctness_mh_manual_semi": mh,
        "proposal_attraction_by_task": attraction,
        "proposal_response_rows_for_worker_analysis": response,
    }


# ---------------------------------------------------------------------------
# 3) Exploratory latent annotator structure (not the frozen Paper A profile)
# ---------------------------------------------------------------------------

def residualize_within_task(frame: pd.DataFrame, value: str) -> pd.Series:
    x = numeric(frame[value])
    return x - x.groupby(frame["base_task_id"]).transform("mean")


def aggregate_worker_features(response: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    quality = read_csv("QUALITY_DATA_MINING_CONTEXTS.CSV")
    mode = read_csv("WORKER_MODE_MEMBERSHIP_LANES.csv")
    time = read_csv("ACTIVE_TIME_TASK_WORKER.CSV")
    worker_fact = read_csv("WORKER_FACT.CSV")
    inventory = pd.read_csv(
        ROOT / "analysis_results" / "annotator_image_inventory_20260822_v1" / "annotator_summary.csv",
        encoding="utf-8-sig", low_memory=False,
    )

    # Quality: task-centered, C1 contexts, computable rows; includes special workers descriptively.
    quality["worker_id"] = quality["worker_id"].map(norm_worker)
    quality["iou_to_gt"] = numeric(quality["iou_to_gt"])
    quality = quality[
        quality["quality_data_mining_included"].map(truth)
        & quality["iou_to_gt"].notna()
        & quality["dataset_group"].astype(str).str.contains("Calibration", case=False, na=False)
    ].copy()
    quality["quality_task_resid"] = residualize_within_task(quality, "iou_to_gt")
    quality_worker = quality.groupby("worker_id", as_index=False).agg(
        quality_n=("iou_to_gt", "size"),
        quality_task_count=("base_task_id", "nunique"),
        quality_mean=("iou_to_gt", "mean"),
        quality_task_resid_mean=("quality_task_resid", "mean"),
        quality_task_resid_sd=("quality_task_resid", "std"),
    )

    # Mode membership: current broad C1 lane, task-centered.
    mode["worker_id"] = mode["worker_id"].map(norm_worker)
    lane = "current_all_computable_c1"
    mode = mode[mode["analysis_lane"].astype(str).eq(lane)].copy()
    mode["is_largest_mode_num"] = mode["is_largest_mode"].map(truth).astype(float)
    mode["is_supported_minority_num"] = mode["is_supported_minority_mode"].map(truth).astype(float)
    mode["largest_mode_task_resid"] = mode["is_largest_mode_num"] - mode.groupby("base_task_id")["is_largest_mode_num"].transform("mean")
    mode["minority_mode_task_resid"] = mode["is_supported_minority_num"] - mode.groupby("base_task_id")["is_supported_minority_num"].transform("mean")
    mode["n_pairs"] = numeric(mode["n_pairs"])
    if "task_centered_n_pairs" not in mode or numeric(mode["task_centered_n_pairs"]).notna().sum() == 0:
        mode["task_centered_n_pairs"] = mode["n_pairs"] - mode.groupby("base_task_id")["n_pairs"].transform("mean")
    else:
        mode["task_centered_n_pairs"] = numeric(mode["task_centered_n_pairs"])
    mode_worker = mode.groupby("worker_id", as_index=False).agg(
        mode_n=("base_task_id", "size"),
        mode_task_count=("base_task_id", "nunique"),
        largest_mode_rate=("is_largest_mode_num", "mean"),
        largest_mode_task_resid_mean=("largest_mode_task_resid", "mean"),
        supported_minority_mode_rate=("is_supported_minority_num", "mean"),
        minority_mode_task_resid_mean=("minority_mode_task_resid", "mean"),
        task_centered_n_pairs_mean=("task_centered_n_pairs", "mean"),
    )

    # Active time: task- and condition-centered log time.
    time["worker_id"] = time["worker_id"].map(norm_worker)
    time["task_worker_active_seconds"] = numeric(time["task_worker_active_seconds"])
    time = time[
        time["task_worker_time_analysis_eligible"].map(truth)
        & time["task_worker_active_seconds"].notna()
        & time["dataset_group"].astype(str).str.contains("Calibration", case=False, na=False)
    ].copy()
    time["log_active"] = np.log1p(time["task_worker_active_seconds"].clip(lower=0))
    time["time_group"] = time["base_task_id"].astype(str) + "|" + time["condition"].astype(str)
    time["log_time_task_resid"] = time["log_active"] - time.groupby("time_group")["log_active"].transform("mean")
    time_worker = time.groupby("worker_id", as_index=False).agg(
        time_n=("log_active", "size"),
        time_task_count=("base_task_id", "nunique"),
        log_time_median=("log_active", "median"),
        log_time_task_resid_mean=("log_time_task_resid", "mean"),
    )

    # Proposal response: task-centered continuous/binary behavior, all P1/C1 and C1-only sensitivity.
    response = response[response["analysis_eligible_bool"]].copy()
    response["worker_id"] = response["worker_id"].map(norm_worker)
    response["edited"] = (~response["exact_geometry_equal_bool"]).astype(float)
    response["delta_U"] = numeric(response["delta_U"])
    response["edit_rmse"] = numeric(response["geometry_edit_rmse_panorama_diagonal_normalized"])
    for value in ("edited", "delta_U", "edit_rmse", "issue_reported_bool", "correct_proposal_degraded_095", "wrong_proposal_corrected_095", "wrong_proposal_retained_exact"):
        if value in response:
            response[f"{value}_task_resid"] = numeric(response[value]) - numeric(response[value]).groupby(response["base_task_id"]).transform("mean")

    semi_worker_rows = []
    for worker_id, group in response.groupby("worker_id", sort=True):
        correct = group[group["proposal_correctness_observed_095"] & group["initial_correct_095"]]
        wrong = group[group["proposal_correctness_observed_095"] & (~group["initial_correct_095"])]
        c1 = group[group["stage"].eq("C1")]
        semi_worker_rows.append({
            "worker_id": worker_id,
            "proposal_n": len(group),
            "proposal_task_count": group["base_task_id"].nunique(),
            "proposal_edit_rate": float(group["edited"].mean()),
            "proposal_edit_task_resid_mean": float(group["edited_task_resid"].mean()),
            "proposal_delta_U_mean": float(group["delta_U"].mean()) if group["delta_U"].notna().any() else None,
            "proposal_delta_U_task_resid_mean": float(group["delta_U_task_resid"].mean()) if group["delta_U_task_resid"].notna().any() else None,
            "proposal_issue_rate": float(group["issue_reported_bool"].mean()),
            "correct_proposal_n": len(correct),
            "correct_proposal_retention_rate_jeffreys": jeffreys_rate(correct["exact_geometry_equal_bool"].sum(), len(correct)),
            "correct_proposal_degradation_rate_jeffreys": jeffreys_rate(correct["correct_proposal_degraded_095"].sum(), len(correct)),
            "wrong_proposal_n": len(wrong),
            "wrong_proposal_correction_rate_jeffreys": jeffreys_rate(wrong["wrong_proposal_corrected_095"].sum(), len(wrong)),
            "wrong_proposal_exact_retention_rate_jeffreys": jeffreys_rate(wrong["wrong_proposal_retained_exact"].sum(), len(wrong)),
            "c1_proposal_n": len(c1),
            "c1_edit_rate": float(c1["edited"].mean()) if len(c1) else None,
            "c1_delta_U_mean": float(c1["delta_U"].mean()) if c1["delta_U"].notna().any() else None,
        })
    proposal_worker = pd.DataFrame(semi_worker_rows)

    worker_fact["worker_id"] = worker_fact["worker_id"].map(norm_worker)
    fact_cols = [
        "worker_id", "Q_GT_EB", "R_peer_stable", "F_struct_EB", "administratively_eligible",
        "process_eligible", "independence_eligible", "T_active_task_adjusted",
    ]
    worker_fact = worker_fact[[c for c in fact_cols if c in worker_fact]].drop_duplicates("worker_id")

    inventory["worker_id"] = inventory["worker_id"].map(norm_worker)
    inventory = inventory[[
        "worker_id", "language_group", "current_20", "lifecycle_status", "canonical_submission_count",
        "unique_image_count", "prescreen_exclude_from_primary_candidate",
    ]].drop_duplicates("worker_id")

    worker = quality_worker.merge(mode_worker, on="worker_id", how="outer")
    worker = worker.merge(time_worker, on="worker_id", how="outer")
    worker = worker.merge(proposal_worker, on="worker_id", how="outer")
    worker = worker.merge(worker_fact, on="worker_id", how="left")
    worker = worker.merge(inventory, on="worker_id", how="left")
    worker["current_20_bool"] = worker["current_20"].map(truth)
    worker["admin_eligible_bool"] = worker["administratively_eligible"].map(truth)
    worker["analysis_population"] = np.where(
        worker["current_20_bool"], "current20",
        np.where(worker["quality_n"].fillna(0) >= 20, "historical_supported", "insufficient_support"),
    )

    row_sources = {
        "quality_rows": quality,
        "mode_rows": mode,
        "time_rows": time,
        "proposal_rows": response,
    }
    return worker.sort_values("worker_id").reset_index(drop=True), row_sources


CORE_FEATURES = [
    "quality_task_resid_mean",
    "largest_mode_task_resid_mean",
    "minority_mode_task_resid_mean",
    "task_centered_n_pairs_mean",
    "log_time_task_resid_mean",
    "proposal_edit_task_resid_mean",
    "proposal_delta_U_task_resid_mean",
    "correct_proposal_degradation_rate_jeffreys",
    "wrong_proposal_correction_rate_jeffreys",
    "wrong_proposal_exact_retention_rate_jeffreys",
]

PROPOSAL_FEATURE_SUPPORT = {
    "correct_proposal_degradation_rate_jeffreys": "correct_proposal_n",
    "wrong_proposal_correction_rate_jeffreys": "wrong_proposal_n",
    "wrong_proposal_exact_retention_rate_jeffreys": "wrong_proposal_n",
}


def mask_sparse_proposal_features(frame: pd.DataFrame) -> pd.DataFrame:
    for feature, support in PROPOSAL_FEATURE_SUPPORT.items():
        if feature in frame and support in frame:
            frame.loc[numeric(frame[support]).fillna(0) < 3, feature] = np.nan
    return frame


def prepare_feature_matrix(worker: pd.DataFrame, population: str = "current20") -> tuple[pd.DataFrame, np.ndarray, list[str]]:
    if population == "current20":
        subset = worker[worker["current_20_bool"]].copy()
    elif population == "supported_all":
        subset = worker[worker["quality_n"].fillna(0) >= 20].copy()
    else:
        raise ValueError(population)
    subset = mask_sparse_proposal_features(subset)
    available = []
    for feature in CORE_FEATURES:
        if feature in subset and numeric(subset[feature]).notna().sum() >= max(8, int(0.5 * len(subset))) and numeric(subset[feature]).nunique(dropna=True) >= 3:
            available.append(feature)
    if len(available) < 4:
        raise RuntimeError(f"too few usable worker features: {available}")
    matrix = subset[available].apply(numeric)
    imputed = SimpleImputer(strategy="median").fit_transform(matrix)
    scaled = RobustScaler(quantile_range=(25, 75)).fit_transform(imputed)
    return subset.reset_index(drop=True), scaled, available


def clustering_diagnostics(worker: pd.DataFrame, population: str = "current20") -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    subset, X, features = prepare_feature_matrix(worker, population)
    n = len(subset)
    diagnostics = []
    labels_by_k: dict[int, np.ndarray] = {}
    for k in range(2, min(6, n - 1)):
        agg = AgglomerativeClustering(n_clusters=k, linkage="ward").fit(X)
        labels = agg.labels_
        labels_by_k[k] = labels
        diagnostics.append({
            "population": population,
            "method": "ward",
            "k": k,
            "n_workers": n,
            "n_features": len(features),
            "silhouette": float(silhouette_score(X, labels)) if len(set(labels)) > 1 else None,
            "bic": None,
            "cluster_sizes": ";".join(map(str, sorted(Counter(labels).values(), reverse=True))),
        })
        try:
            gmm = GaussianMixture(n_components=k, covariance_type="diag", random_state=SEED, n_init=20, reg_covar=1e-5).fit(X)
            g_labels = gmm.predict(X)
            diagnostics.append({
                "population": population,
                "method": "gmm_diag",
                "k": k,
                "n_workers": n,
                "n_features": len(features),
                "silhouette": float(silhouette_score(X, g_labels)) if len(set(g_labels)) > 1 else None,
                "bic": float(gmm.bic(X)),
                "cluster_sizes": ";".join(map(str, sorted(Counter(g_labels).values(), reverse=True))),
            })
        except Exception as exc:
            diagnostics.append({
                "population": population, "method": "gmm_diag", "k": k,
                "n_workers": n, "n_features": len(features), "silhouette": None,
                "bic": None, "cluster_sizes": "", "error": repr(exc),
            })
    diag = pd.DataFrame(diagnostics)

    # Exploratory k selection by Ward silhouette; require no singleton cluster.
    ward = diag[diag["method"].eq("ward")].copy()
    ward["has_singleton"] = ward["cluster_sizes"].map(lambda s: "1" in str(s).split(";"))
    candidates = ward[~ward["has_singleton"] & ward["silhouette"].notna()]
    chosen_k = int(candidates.sort_values("silhouette", ascending=False).iloc[0]["k"]) if len(candidates) else 2
    full_labels = labels_by_k[chosen_k]

    # PCA axes are often more defensible than discrete classes at n≈20.
    pca = PCA(n_components=min(5, X.shape[0] - 1, X.shape[1]), random_state=SEED).fit(X)
    scores = pca.transform(X)
    loadings = pd.DataFrame(
        pca.components_.T,
        index=features,
        columns=[f"PC{i+1}" for i in range(pca.n_components_)],
    ).reset_index().rename(columns={"index": "feature"})
    loadings["population"] = population
    pca_info = {
        "population": population,
        "features": features,
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "exploratory_chosen_k": chosen_k,
        "chosen_k": chosen_k,
        "minimum_proposal_feature_support": 3,
    }

    assignments = subset[["worker_id", "language_group", "current_20", "lifecycle_status"]].copy()
    assignments["chosen_k"] = chosen_k
    assignments["latent_cluster"] = full_labels
    for i in range(scores.shape[1]):
        assignments[f"PC{i+1}_score"] = scores[:, i]
    assignments = assignments.merge(worker, on=["worker_id", "language_group", "current_20", "lifecycle_status"], how="left")
    return diag, assignments, loadings, pca_info


def recompute_half_features(
    workers: Sequence[str],
    source_rows: dict[str, pd.DataFrame],
    selected_tasks: dict[str, set[str]],
) -> pd.DataFrame:
    # Recompute the core residualized feature subset on one task half.
    out = pd.DataFrame({"worker_id": list(workers)})

    q = source_rows["quality_rows"]
    q = q[q["base_task_id"].astype(str).isin(selected_tasks["quality"])].copy()
    q["resid"] = residualize_within_task(q, "iou_to_gt")
    qa = q.groupby("worker_id", as_index=False)["resid"].mean().rename(columns={"resid": "quality_task_resid_mean"})
    out = out.merge(qa, on="worker_id", how="left")

    m = source_rows["mode_rows"]
    m = m[m["base_task_id"].astype(str).isin(selected_tasks["mode"])].copy()
    m["largest_resid"] = m["is_largest_mode_num"] - m.groupby("base_task_id")["is_largest_mode_num"].transform("mean")
    m["minority_resid"] = m["is_supported_minority_num"] - m.groupby("base_task_id")["is_supported_minority_num"].transform("mean")
    ma = m.groupby("worker_id", as_index=False).agg(
        largest_mode_task_resid_mean=("largest_resid", "mean"),
        minority_mode_task_resid_mean=("minority_resid", "mean"),
        task_centered_n_pairs_mean=("task_centered_n_pairs", "mean"),
    )
    out = out.merge(ma, on="worker_id", how="left")

    t = source_rows["time_rows"]
    t = t[t["base_task_id"].astype(str).isin(selected_tasks["time"])].copy()
    t["resid"] = t["log_active"] - t.groupby("time_group")["log_active"].transform("mean")
    ta = t.groupby("worker_id", as_index=False)["resid"].mean().rename(columns={"resid": "log_time_task_resid_mean"})
    out = out.merge(ta, on="worker_id", how="left")

    p = source_rows["proposal_rows"]
    p = p[p["base_task_id"].astype(str).isin(selected_tasks["proposal"])].copy()
    p["edited_resid"] = p["edited"] - p.groupby("base_task_id")["edited"].transform("mean")
    p["delta_resid"] = p["delta_U"] - p.groupby("base_task_id")["delta_U"].transform("mean")
    pa = p.groupby("worker_id", as_index=False).agg(
        proposal_edit_task_resid_mean=("edited_resid", "mean"),
        proposal_delta_U_task_resid_mean=("delta_resid", "mean"),
    )
    correctness_rows = []
    for worker_id, group in p.groupby("worker_id", sort=True):
        observed = group[group["proposal_correctness_observed_095"]]
        correct = observed[observed["initial_correct_095"]]
        wrong = observed[~observed["initial_correct_095"]]
        correctness_rows.append({
            "worker_id": worker_id,
            "correct_proposal_n": len(correct),
            "wrong_proposal_n": len(wrong),
            "correct_proposal_degradation_rate_jeffreys": jeffreys_rate(
                correct["correct_proposal_degraded_095"].sum(), len(correct),
            ),
            "wrong_proposal_correction_rate_jeffreys": jeffreys_rate(
                wrong["wrong_proposal_corrected_095"].sum(), len(wrong),
            ),
            "wrong_proposal_exact_retention_rate_jeffreys": jeffreys_rate(
                wrong["wrong_proposal_retained_exact"].sum(), len(wrong),
            ),
        })
    if correctness_rows:
        pa = pa.merge(pd.DataFrame(correctness_rows), on="worker_id", how="outer")
    out = out.merge(pa, on="worker_id", how="left")
    return out


def split_half_cluster_stability(
    worker: pd.DataFrame,
    source_rows: dict[str, pd.DataFrame],
    assignments: pd.DataFrame,
    features: Sequence[str],
    population: str = "current20",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    workers = assignments["worker_id"].astype(str).tolist()
    chosen_k = int(assignments["chosen_k"].iloc[0])
    domains = {
        "quality": sorted(source_rows["quality_rows"]["base_task_id"].astype(str).unique()),
        "mode": sorted(source_rows["mode_rows"]["base_task_id"].astype(str).unique()),
        "time": sorted(source_rows["time_rows"]["base_task_id"].astype(str).unique()),
        "proposal": sorted(source_rows["proposal_rows"]["base_task_id"].astype(str).unique()),
    }
    rng = np.random.default_rng(SEED + 7000)
    stability_rows = []
    pair_counts = defaultdict(int)
    pair_same = defaultdict(int)
    for repeat in range(SPLIT_REPEATS):
        halves: list[dict[str, set[str]]] = [dict(), dict()]
        for domain, tasks in domains.items():
            perm = np.asarray(tasks, dtype=object).copy()
            rng.shuffle(perm)
            cut = max(1, len(perm) // 2)
            halves[0][domain] = set(map(str, perm[:cut]))
            halves[1][domain] = set(map(str, perm[cut:]))
        labels = []
        valid_workers = []
        for half in halves:
            feat = recompute_half_features(workers, source_rows, half).set_index("worker_id")
            feat = mask_sparse_proposal_features(feat)
            use = list(features)
            if any(
                c not in feat
                or feat[c].notna().sum() < max(8, int(0.5 * len(feat)))
                or feat[c].nunique(dropna=True) < 3
                for c in use
            ):
                labels.append(None)
                continue
            matrix = feat[use]
            X = SimpleImputer(strategy="median").fit_transform(matrix)
            X = RobustScaler(quantile_range=(25, 75)).fit_transform(X)
            try:
                lab = AgglomerativeClustering(n_clusters=chosen_k, linkage="ward").fit_predict(X)
            except Exception:
                labels.append(None)
                continue
            labels.append(lab)
            valid_workers = feat.index.astype(str).tolist()
        if len(labels) != 2 or labels[0] is None or labels[1] is None:
            stability_rows.append({"repeat": repeat, "ari": None, "status": "not_evaluable"})
            continue
        ari = adjusted_rand_score(labels[0], labels[1])
        stability_rows.append({"repeat": repeat, "ari": float(ari), "status": "estimated"})
        # Co-clustering stability pooled over both halves.
        for lab in labels:
            for i in range(len(valid_workers)):
                for j in range(i + 1, len(valid_workers)):
                    key = tuple(sorted((valid_workers[i], valid_workers[j])))
                    pair_counts[key] += 1
                    pair_same[key] += int(lab[i] == lab[j])
    pair_rows = [
        {"worker_left": a, "worker_right": b, "co_cluster_count": pair_same[(a, b)], "comparison_count": n, "co_cluster_rate": pair_same[(a, b)] / n}
        for (a, b), n in sorted(pair_counts.items())
    ]
    return pd.DataFrame(stability_rows), pd.DataFrame(pair_rows)


def cluster_type_uncertainty_associations(
    assignments: pd.DataFrame,
    source_rows: dict[str, pd.DataFrame],
    proposal_response: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = assignments[["worker_id", "latent_cluster"]].copy()
    labels["worker_id"] = labels["worker_id"].astype(str)
    mode = source_rows["mode_rows"].merge(labels, on="worker_id", how="inner")
    # Task uncertainty: main-mode share across workers and observed supported minority.
    task_unc = mode.groupby("base_task_id", as_index=False).agg(
        task_main_mode_rate=("is_largest_mode_num", "mean"),
        task_supported_minority_rate=("is_supported_minority_num", "mean"),
        task_n=("worker_id", "size"),
    )
    task_unc["high_uncertainty"] = (
        (task_unc["task_main_mode_rate"] < task_unc["task_main_mode_rate"].median())
        | (task_unc["task_supported_minority_rate"] > 0)
    )
    mode = mode.merge(task_unc[["base_task_id", "high_uncertainty"]], on="base_task_id", how="left")
    mode_rows = []
    for (cluster, high), group in mode.groupby(["latent_cluster", "high_uncertainty"], sort=True):
        mode_rows.append({
            "latent_cluster": int(cluster),
            "high_uncertainty_task": bool(high),
            "row_count": len(group),
            "task_count": group["base_task_id"].nunique(),
            "worker_count": group["worker_id"].nunique(),
            "largest_mode_rate": float(group["is_largest_mode_num"].mean()),
            "supported_minority_mode_rate": float(group["is_supported_minority_num"].mean()),
            "mean_task_centered_n_pairs": float(numeric(group["task_centered_n_pairs"]).mean()),
            "analysis_role": "posthoc_descriptive_same_rows_define_uncertainty_and_outcome",
        })
    mode_summary = pd.DataFrame(mode_rows)

    proposal_response = proposal_response.merge(labels, on="worker_id", how="inner")
    prop_rows = []
    for cluster, group in proposal_response.groupby("latent_cluster", sort=True):
        wrong = group[group["proposal_correctness_observed_095"] & (~group["initial_correct_095"])]
        correct = group[group["proposal_correctness_observed_095"] & group["initial_correct_095"]]
        prop_rows.append({
            "latent_cluster": int(cluster),
            "row_count": len(group),
            "worker_count": group["worker_id"].nunique(),
            "proposal_edit_rate": float((~group["exact_geometry_equal_bool"]).mean()),
            "mean_delta_U": float(group["delta_U"].mean()),
            "correct_proposal_n": len(correct),
            "correct_proposal_degradation_rate": safe_rate(correct["correct_proposal_degraded_095"].sum(), len(correct)),
            "wrong_proposal_n": len(wrong),
            "wrong_proposal_correction_rate": safe_rate(wrong["wrong_proposal_corrected_095"].sum(), len(wrong)),
            "wrong_proposal_exact_retention_rate": safe_rate(wrong["wrong_proposal_retained_exact"].sum(), len(wrong)),
            "analysis_role": "posthoc_descriptive_no_routing_or_causal_use",
        })
    return mode_summary, pd.DataFrame(prop_rows)


# ---------------------------------------------------------------------------
# 4) Robust observed multimodality candidates
# ---------------------------------------------------------------------------

def multimodality_candidates(prefix_task: pd.DataFrame) -> pd.DataFrame:
    full = prefix_task[prefix_task["k"].eq(22)].copy()
    # One row per task-threshold at full k.
    rows = []
    for task, group in full.groupby("base_task_id", sort=True):
        statuses = group["full_status"].fillna("").astype(str)
        supported = int(statuses.eq("supported_multimodal").sum())
        not_eval = int(statuses.eq("not_evaluable").sum())
        second = numeric(group["full_second_support"])
        rows.append({
            "base_task_id": task,
            "threshold_count": len(group),
            "supported_multimodal_threshold_count": supported,
            "not_evaluable_threshold_count": not_eval,
            "dominant_with_dissent_threshold_count": int(statuses.eq("dominant_with_dissent").sum()),
            "unimodal_threshold_count": int(statuses.eq("unimodal").sum()),
            "min_second_mode_support": float(second.min()) if second.notna().any() else None,
            "max_second_mode_support": float(second.max()) if second.notna().any() else None,
            "robust_observed_multimodality_candidate": supported >= max(4, len(group) - 2) and not_eval <= 1,
            "requires_blind_expert_reasonableness_audit": True,
            "inherent_ambiguity_claim_allowed": False,
        })
    result = pd.DataFrame(rows)
    # Attach observable cause-code audit where available; do not convert it into causal truth.
    cause = read_csv("CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv")
    cause_field = (
        "observable_geometric_difference_codes"
        if "observable_geometric_difference_codes" in cause.columns
        else "cause_code" if "cause_code" in cause.columns else None
    )
    if cause_field is not None and "base_task_id" in cause.columns:
        agg = cause[["base_task_id", cause_field]].groupby("base_task_id", as_index=False).agg(
            observable_cause_codes=(cause_field, lambda s: ";".join(sorted({code for value in s.dropna().astype(str) for code in value.split(";") if code}))),
            cause_audit_rows=(cause_field, "size"),
        )
        result = result.merge(agg, on="base_task_id", how="left")
    return result.sort_values(
        ["robust_observed_multimodality_candidate", "supported_multimodal_threshold_count", "max_second_mode_support"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Reporting / validation
# ---------------------------------------------------------------------------

def fmt(value: Any, digits: int = 3) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not math.isfinite(x):
        return "NA"
    return f"{x:.{digits}f}"


def build_report(
    threshold_summary: pd.DataFrame,
    threshold_robustness: pd.DataFrame,
    prefix_summary: pd.DataFrame,
    proposal: dict[str, pd.DataFrame],
    worker_diag: pd.DataFrame,
    worker_assignments: pd.DataFrame,
    stability: pd.DataFrame,
    candidates: pd.DataFrame,
    pca_info: dict[str, Any],
) -> str:
    q95 = threshold_summary[
        (np.isclose(numeric(threshold_summary["threshold"]), 0.95))
        & threshold_summary["metric"].eq("delta_shannon_entropy")
    ].iloc[0]
    grid_entropy = threshold_summary[threshold_summary["metric"].eq("delta_shannon_entropy")]
    stable_001 = int(threshold_robustness["sign_stable_tol_001"].sum())
    stable_005 = int(threshold_robustness["sign_stable_tol_005"].sum())

    prefix_multi = prefix_summary[prefix_summary["supported_multimodal_rate"].notna()].copy()
    q95_prefix = prefix_multi[np.isclose(numeric(prefix_multi["threshold"]), 0.95)]

    quadrants = proposal["proposal_mechanism_quadrants"].set_index("mechanism_quadrant")
    correctness = proposal["proposal_correctness_transitions"]
    p1_95 = correctness[(correctness["stage_population"].eq("P1")) & np.isclose(correctness["correctness_cutoff"], 0.95)]
    c1_95 = correctness[(correctness["stage_population"].eq("C1")) & np.isclose(correctness["correctness_cutoff"], 0.95)]

    ward = worker_diag[worker_diag["method"].eq("ward")].sort_values("silhouette", ascending=False)
    best = ward.iloc[0] if len(ward) else None
    ari = numeric(stability["ari"]).dropna()
    candidate_n = int(candidates["robust_observed_multimodality_candidate"].sum())

    lines = [
        "# 标注不确定性复算：阈值、共享初始化与标注者潜在结构",
        "",
        "## 核心裁决",
        "",
        "1. **‘加人经常是在发现模式’不能作为无条件总体结论。**本次从冻结 pairwise geometry 重新聚类，并将阈值扩展至 0.90–0.98。应只在高支持、经过富集的任务中表述为：增加支持量会提高受支持少数模式的可检测性；同时也会增加聚类非唯一的机会。",
        "2. **0.95 不是唯一产生该现象的阈值。**需要同时看跨阈值方向稳定性、分区失败率和高支持 prefix replay，不能只报告单一 q。",
        "3. **现有数据观察到与共享初始化相伴的输出分布差异，但没有随机化反事实，不能断言共享初始化造成了这些差异，也不能把更高一致性自动解释为更正确或自动命名为锚定。**",
        "4. **现有 P1 提供了正确与错误 proposal 的自然机制样本；C1 的 proposal 几乎全部接近 reference 上限，因此 C1 本身不能识别 Kiani 式的‘正确 AI 与错误 AI 方向相反’交互。**",
        "5. **潜在标注者结构首先应被当作连续行为轴，而不是强行命名离散类型。**只有 split-half clustering 稳定性足够高时，离散类型才可进入后续验证。",
        "6. **跨阈值稳定多峰仍只表示‘稳定观察到多个模式’；是否为多个合理解释必须经过不显示工人身份、支持人数和 GT 分数的专家盲审。**",
        "",
        "## 1. 阈值敏感性",
        "",
        f"正式 22 个配对任务在 q=0.95 的 task-equal 熵差为 `{fmt(q95['mean_difference'])}`，building-cluster 95% CI 为 `[{fmt(q95['cluster_bootstrap_ci_lower'])}, {fmt(q95['cluster_bootstrap_ci_upper'])}]`，exact building sign-flip p=`{fmt(q95['building_exact_sign_flip_p'])}`。",
        f"在 {len(THRESHOLDS)} 个 q≥0.90 阈值上，22 个任务中有 {stable_001} 个在 ±0.01 规则下方向完全稳定，{stable_005} 个在 ±0.05 规则下方向完全稳定。完整逐任务结果见 `THRESHOLD_TASK_ROBUSTNESS_FORMAL22.csv`。",
        "",
        "熵差随阈值：",
        "",
        "| q | n tasks | mean ΔH | 95% CI | p |",
        "|---:|---:|---:|---:|---:|",
    ]
    for row in grid_entropy.sort_values("threshold").itertuples(index=False):
        lines.append(
            f"| {row.threshold:g} | {row.n_tasks} | {fmt(row.mean_difference)} | "
            f"[{fmt(row.cluster_bootstrap_ci_lower)}, {fmt(row.cluster_bootstrap_ci_upper)}] | {fmt(row.building_exact_sign_flip_p)} |"
        )
    lines += [
        "",
        "高支持 k=22 富集样本的 prefix replay：",
        "",
        "| q | k | supported-multimodal rate | not-evaluable rate |",
        "|---:|---:|---:|---:|",
    ]
    for row in q95_prefix.sort_values("k").itertuples(index=False):
        lines.append(f"| {row.threshold:g} | {int(row.k)} | {fmt(row.supported_multimodal_rate)} | {fmt(row.not_evaluable_rate)} |")
    lines += [
        "",
        "这里的分母是 12 张高支持富集任务及其随机前缀，不是自然任务总体。q=0.95 的支持多峰检出率从 k=5 到 k=12 上升，之后约在 0.50 附近平台，同时 not-evaluable 增加；这既可能包含低频模式被发现，也包含 support≥2 判据和分区失败的机械性质，不能解读为单调的人数效应。",
        "",
        "## 2. 共享初始化、proposal 正确性与结果分布",
        "",
    ]
    for name in [
        "agreement_gain_with_quality_gain", "consensus_inflation_candidate",
        "productive_diversification_candidate", "dispersion_without_quality_gain_candidate",
    ]:
        if name in quadrants.index:
            r = quadrants.loc[name]
            lines.append(f"- `{name}`: {int(r['task_count'])}/{int(r['total_task_count'])} tasks; building-cluster interval [{fmt(r['building_cluster_ci_lower'])}, {fmt(r['building_cluster_ci_upper'])}].")
    if len(p1_95):
        r = p1_95.iloc[0]
        lines.append(
            f"- P1、correctness cutoff 0.95：正确 proposal 后跌破阈值 {int(r['initial_correct_final_incorrect'])} 条；错误 proposal 被修正到阈值以上 {int(r['initial_incorrect_final_correct'])} 条；错误 proposal 支持量为 {int(r['initial_incorrect_final_correct'] + r['initial_incorrect_final_incorrect'])}。"
        )
    if len(c1_95):
        r = c1_95.iloc[0]
        lines.append(
            f"- C1、correctness cutoff 0.95：错误 proposal 支持量为 {int(r['initial_incorrect_final_correct'] + r['initial_incorrect_final_incorrect'])}；若该值接近零，则 C1 无法估计错误 proposal 条件效应。"
        )
    lines += [
        "",
        "`proposal_correctness_final_correctness_association_or` 是 proposal 正确性与最终正确性的观察性关联，不是 assistance treatment OR；`PROPOSAL_CORRECTNESS_MH_MANUAL_SEMI.csv` 只有在正确和错误 proposal 两层都有足够独立 building 时才允许解释。",
        "",
        "## 3. 标注者潜在结构",
        "",
    ]
    if best is not None:
        lines.append(f"Ward clustering 的最高 silhouette 为 {fmt(best['silhouette'])}（k={int(best['k'])}）。探索性选择的 k 记录在 `WORKER_LATENT_ASSIGNMENTS_CURRENT20.csv`，不构成正式工人类型。")
    lines.append(
        f"任务 split-half 的 median ARI={fmt(ari.median()) if len(ari) else 'NA'}，IQR=[{fmt(ari.quantile(.25)) if len(ari) else 'NA'}, {fmt(ari.quantile(.75)) if len(ari) else 'NA'}]。"
    )
    lines.append("若 median ARI 较低或跨过零，离散 cluster 只能作为探索性描述；应优先解释 PCA 连续轴及每个指标的支持量。")
    lines.append(f"PCA 前两轴解释比例为 {', '.join(fmt(x) for x in pca_info.get('explained_variance_ratio', [])[:2])}。")
    lines += [
        "",
        "## 4. 多峰合理性边界",
        "",
        f"跨 prefix q={', '.join(f'{q:g}' for q in PREFIX_THRESHOLDS)} 满足稳定经验多峰筛选的任务有 {candidate_n} 张。它们进入 `ROBUST_OBSERVED_MULTIMODALITY_CANDIDATES.csv`。",
        "",
        "该表只做审查优先级，不把稳定簇自动称为合理、多真值或固有 aleatoric uncertainty。正式 reasonableness audit 必须：隐藏 worker ID、模式人数、Manual/Semi 条件和 GT 质量；专家分别判定 protocol difference、legitimate alternative topology、continuous variation、clear error、representation mismatch、cluster artifact 或 reference issue。",
        "",
        "## 5. 对后续实验的直接含义",
        "",
        "- 下一轮 Semi 不应只增加同一 25 张图的重复人数；需要增加独立 building，并主动构造 proposal-correct / proposal-wrong 的可比反事实。",
        "- 最强的下一步是 Protocol × Proposal 的因子实验，而不是把当前观察性数据包装成因果 anchoring 结论。",
        "- 工人类型不能直接用于路由。先在 held-out tasks 验证：wrong-proposal correction、correct-proposal degradation、mode tendency 和 active-time residual 是否跨任务稳定。",
        "- 稳定多峰任务应保留全部原始独立标注；不要把受到共享 proposal 影响的 Semi 输出作为额外独立票。",
        "",
        "## 复现",
        "",
        "运行：",
        "",
        "```bash",
        "python -m tools.thesis_main.analysis.full_uncertainty.analyze_threshold_anchoring_worker_types_20260823",
        "```",
        "",
        f"源 commit（运行前）：`{git_head()}`；分析源码 SHA-256：`{sha256(Path(__file__))}`。随机种子：`{SEED}`；prefix replicates：`{PREFIX_REPLICATES}`；cluster bootstrap：`{BOOTSTRAP_REPLICATES}`。",
    ]
    return "\n".join(lines) + "\n"


def validate_outputs() -> dict[str, Any]:
    files_before_validation = sorted(
        path for path in OUT.iterdir()
        if path.is_file() and path.name not in {"OUTPUT_MANIFEST.csv", "VALIDATION.json"}
    )
    checks = {
        "source_commit": git_head(),
        "analysis_source_sha256": sha256(Path(__file__)),
        "thresholds": THRESHOLDS,
        "prefix_replicates": PREFIX_REPLICATES,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "split_repeats": SPLIT_REPEATS,
        "output_file_count_excluding_manifest": len(files_before_validation) + 1,
        "all_outputs_nonempty": bool(all(path.stat().st_size > 0 for path in files_before_validation)),
        "required_outputs_present": all((OUT / name).is_file() for name in [
            "ANALYSIS_REPORT_ZH.md", "THRESHOLD_SUMMARY_FORMAL22.csv",
            "PROPOSAL_CORRECTNESS_TRANSITIONS.csv", "WORKER_LATENT_ASSIGNMENTS_CURRENT20.csv",
            "ROBUST_OBSERVED_MULTIMODALITY_CANDIDATES.csv",
        ]),
    }
    write_json("VALIDATION.json", checks)
    files = sorted(
        path for path in OUT.iterdir()
        if path.is_file() and path.name != "OUTPUT_MANIFEST.csv"
    )
    manifest = pd.DataFrame([
        {"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in files
    ])
    write_csv("OUTPUT_MANIFEST.csv", manifest)
    return checks


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    frozen_input_validation = ms.validate_inputs()
    OUT.mkdir(parents=True, exist_ok=True)
    for path in OUT.iterdir():
        if path.is_file():
            path.unlink()
    write_csv("FROZEN_INPUT_VALIDATION.csv", frozen_input_validation)

    # Threshold re-computation.
    reclustered, formal_task, formal_summary, formal_direction_counts, formal_robust, transitions = recompute_formal_threshold_grid()
    write_csv("THRESHOLD_RECLUSTERED_SUBSETS_FORMAL22.csv", reclustered)
    write_csv("THRESHOLD_TASK_METRICS_FORMAL22.csv", formal_task)
    write_csv("THRESHOLD_SUMMARY_FORMAL22.csv", formal_summary)
    write_csv("THRESHOLD_DIRECTION_COUNTS_FORMAL22.csv", formal_direction_counts)
    write_csv("THRESHOLD_TASK_ROBUSTNESS_FORMAL22.csv", formal_robust)
    write_csv("THRESHOLD_DIRECTION_TRANSITIONS_FORMAL22.csv", transitions)

    inclusive_task, inclusive_summary = reaggregate_inclusive25_existing_thresholds()
    write_csv("THRESHOLD_TASK_METRICS_INCLUSIVE25_EXISTING_GRID.csv", inclusive_task)
    write_csv("THRESHOLD_SUMMARY_INCLUSIVE25_EXISTING_GRID.csv", inclusive_summary)

    prefix_summary, prefix_task, prefix_conditional = replay_k22_across_thresholds()
    write_csv("K22_PREFIX_THRESHOLD_SUMMARY.csv", prefix_summary)
    write_csv("K22_PREFIX_THRESHOLD_TASK_RATES.csv", prefix_task)
    write_csv("K22_PREFIX_DETECTION_CONDITIONAL_ON_FULL_STATUS.csv", prefix_conditional)

    # Proposal / anchoring.
    proposal = proposal_correctness_and_anchoring()
    proposal_output_names = {
        "proposal_task_mechanism": "PROPOSAL_TASK_MECHANISM_QUADRANTS.csv",
        "proposal_mechanism_quadrants": "PROPOSAL_MECHANISM_QUADRANT_SUMMARY.csv",
        "proposal_associations_building_clustered": "PROPOSAL_ASSOCIATIONS_BUILDING_CLUSTERED.csv",
        "proposal_correctness_transitions": "PROPOSAL_CORRECTNESS_TRANSITIONS.csv",
        "proposal_correctness_response_summary": "PROPOSAL_CORRECTNESS_RESPONSE_SUMMARY.csv",
        "proposal_correctness_mh_manual_semi": "PROPOSAL_CORRECTNESS_MH_MANUAL_SEMI.csv",
        "proposal_attraction_by_task": "PROPOSAL_ATTRACTION_BY_TASK.csv",
        "proposal_response_rows_for_worker_analysis": "PROPOSAL_RESPONSE_ROWS_FOR_WORKER_ANALYSIS.csv",
    }
    for key, name in proposal_output_names.items():
        write_csv(name, proposal[key])

    # Worker latent structure.
    worker, sources = aggregate_worker_features(proposal["proposal_response_rows_for_worker_analysis"])
    write_csv("WORKER_EXPLORATORY_FEATURES_ALL_SUPPORTED.csv", worker)
    diag, assignments, loadings, pca_info = clustering_diagnostics(worker, "current20")
    write_csv("WORKER_CLUSTERING_DIAGNOSTICS_CURRENT20.csv", diag)
    write_csv("WORKER_LATENT_ASSIGNMENTS_CURRENT20.csv", assignments)
    write_csv("WORKER_PCA_LOADINGS_CURRENT20.csv", loadings)
    write_json("WORKER_PCA_AND_CLUSTER_SELECTION_CURRENT20.json", pca_info)
    stability, co_cluster = split_half_cluster_stability(
        worker, sources, assignments, pca_info["features"], "current20",
    )
    write_csv("WORKER_CLUSTER_SPLIT_HALF_STABILITY.csv", stability)
    write_csv("WORKER_CLUSTER_COCUSTERING_MATRIX_LONG.csv", co_cluster)
    mode_type, proposal_type = cluster_type_uncertainty_associations(
        assignments, sources, proposal["proposal_response_rows_for_worker_analysis"],
    )
    write_csv("WORKER_TYPE_BY_TASK_UNCERTAINTY.csv", mode_type)
    write_csv("WORKER_TYPE_BY_PROPOSAL_RESPONSE.csv", proposal_type)

    # Robust observed multimodality candidates.
    candidates = multimodality_candidates(prefix_task)
    write_csv("ROBUST_OBSERVED_MULTIMODALITY_CANDIDATES.csv", candidates)

    # Input audit.
    audit_paths = [
        V5 / "TASK_SUBSET_RECLUSTERING.CSV",
        V5 / "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv",
        V5 / "SEMI_PROPOSAL_TASK_TABLE.CSV",
        V5 / "SEMI_REVIEW_FACT.CSV",
        V5 / "QUALITY_DATA_MINING_CONTEXTS.CSV",
        V5 / "PROPOSAL_MANUAL_SEMI_GEOMETRY_PAIRS.csv",
        V5 / "WORKER_MODE_MEMBERSHIP_LANES.csv",
        V5 / "ACTIVE_TIME_TASK_WORKER.CSV",
        V5 / "WORKER_FACT.CSV",
        ROOT / "analysis_results" / "annotator_image_inventory_20260822_v1" / "annotator_summary.csv",
        ROOT / ms.INPUTS["pairwise_geometry"][0],
        ROOT / ms.INPUTS["canonical_geometry"][0],
        topology.c1_root(ROOT) / "geometry_task_crowd_structure_C1.csv",
        topology.c1_root(ROOT) / "c1_task_building_binding.csv",
        topology.c1_root(ROOT) / "c1_gt_quality_evidence.csv",
        topology.c1_root(ROOT) / "structural_validation_analysis.csv",
        topology.c1_root(ROOT) / "c1_operational_reference_audit.json",
        topology.c1_root(ROOT) / "c1_gt_conflict_review_queue.csv",
        topology.c1_root(ROOT) / "c1_geometry_pool_eligibility.csv",
        topology.c1_root(ROOT) / "c1_geometry_repair_audit.csv",
    ]
    write_csv("INPUT_AUDIT.csv", input_audit(audit_paths))

    report = build_report(
        formal_summary, formal_robust, prefix_summary,
        proposal, diag, assignments, stability, candidates, pca_info,
    )
    write_text("ANALYSIS_REPORT_ZH.md", report)
    write_text(
        "README.md",
        "# 2026-08-23 uncertainty follow-up audit\n\n"
        "Start with `ANALYSIS_REPORT_ZH.md`. All tables are regenerated by the script in `tools/thesis_main/analysis/full_uncertainty/`.\n",
    )
    checks = validate_outputs()
    if not checks["all_outputs_nonempty"] or not checks["required_outputs_present"]:
        raise AssertionError(checks)
    print(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
