"""唯一的 C1 task-adjusted Q_GT 估计器。

点估计使用 worker 固定效应与 task 随机截距。置信区间与 worker 对比
协方差来自按 building/task 聚类的非参数 bootstrap。该模块只产生测量证据，
不拥有 Strong Global eligibility、阈值或排名。
"""

from __future__ import annotations

import json
import math
import random
import warnings
from collections import defaultdict
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


MODEL_VERSION = "c1_worker_fe_task_random_intercept_cluster_bootstrap_v2"


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _prepare_frame(rows: list[dict[str, Any]], contract: dict[str, Any]) -> pd.DataFrame:
    usable: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("condition", "")).lower() != "manual":
            continue
        if "quality_evaluable" in row and not _truth(row.get("quality_evaluable")):
            continue
        if "global_analysis_eligible" in row and not _truth(row.get("global_analysis_eligible")):
            continue
        quality = next(
            (value for field in ("Q_GT_raw", "iou_to_gt", "iou_2d", "iou") if (value := _number(row.get(field))) is not None),
            None,
        )
        worker = str(row.get("worker_id", "")).strip()
        task = str(row.get("base_task_id") or row.get("task_id") or "").strip()
        building = str(row.get("building_id") or "").strip()
        stage = str(row.get("stage") or "C1").strip()
        if quality is None or not worker or not task:
            continue
        usable.append({"worker_id": worker, "base_task_id": task, "building_id": building, "stage": stage, "quality": quality})
    frame = pd.DataFrame(usable)
    if frame.empty or frame.worker_id.nunique() < 2 or frame.base_task_id.nunique() < 2:
        raise ValueError("task-adjusted Q_GT requires at least two workers and two base tasks")
    if contract.get("adjust_building") and (frame.building_id.eq("").any() or frame.building_id.nunique() < 2):
        raise ValueError("frozen building adjustment requires complete multi-building support")
    if contract.get("adjust_stage") and frame.stage.nunique() < 2:
        raise ValueError("frozen stage adjustment requires at least two stages")
    return frame


def _formula(contract: dict[str, Any]) -> str:
    terms = ["0 + C(worker_id)"]
    if contract.get("adjust_stage"):
        terms.append("C(stage)")
    if contract.get("adjust_building"):
        terms.append("C(building_id)")
    return "quality ~ " + " + ".join(terms)


def _fit_once(frame: pd.DataFrame, contract: dict[str, Any]) -> dict[str, Any]:
    formula = _formula(contract)
    caught_all: list[warnings.WarningMessage] = []
    fitted = None
    optimizer = ""
    errors: list[str] = []
    for method in ("lbfgs", "powell"):
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                candidate = smf.mixedlm(formula, frame, groups=frame["base_task_id"], re_formula="1").fit(
                    reml=True, method=method, maxiter=1000, disp=False,
                )
            caught_all.extend(caught)
            if candidate.converged:
                fitted, optimizer = candidate, method
                break
            errors.append(f"{method}:not_converged")
        except (ValueError, np.linalg.LinAlgError) as exc:
            errors.append(f"{method}:{type(exc).__name__}")
    if fitted is None:
        raise ValueError("task-adjusted mixed model failed:" + ";".join(errors))
    fixed_names = list(fitted.fe_params.index)
    fixed_cov = fitted.cov_params().loc[fixed_names, fixed_names]
    if not fitted.converged or not np.isfinite(fitted.fe_params.to_numpy()).all() or not np.isfinite(fixed_cov.to_numpy()).all():
        raise ValueError("task-adjusted mixed model did not converge to finite fixed effects/covariance")
    from patsy import build_design_matrices

    design_info = fitted.model.data.design_info
    reference = frame.copy()
    workers = sorted(frame.worker_id.unique())
    estimates: dict[str, float] = {}
    contrasts: dict[str, np.ndarray] = {}
    for worker in workers:
        reference["worker_id"] = worker
        matrix = build_design_matrices([design_info], reference, return_type="dataframe")[0]
        contrast = matrix.mean(axis=0).reindex(fixed_names, fill_value=0.0).to_numpy(dtype=float)
        estimates[worker] = float(contrast @ fitted.fe_params.to_numpy())
        contrasts[worker] = contrast
    task_effects = {
        str(task): float(np.asarray(effect).reshape(-1)[0])
        for task, effect in fitted.random_effects.items()
    }
    warning_text = [f"{item.category.__name__}:{item.message}" for item in caught_all]
    return {
        "formula": formula,
        "optimizer": optimizer,
        "fitted": fitted,
        "estimates": estimates,
        "contrasts": contrasts,
        "fixed_covariance": fixed_cov.to_numpy(dtype=float),
        "task_effects": task_effects,
        "warnings": warning_text,
        "residual_variance": float(fitted.scale),
        "task_intercept_variance": float(np.asarray(fitted.cov_re).reshape(-1)[0]),
    }


def _resample_frame(frame: pd.DataFrame, rng: random.Random) -> tuple[pd.DataFrame, str]:
    complete_buildings = not frame.building_id.eq("").any() and frame.building_id.nunique() >= 2
    cluster_field = "building_id" if complete_buildings else "base_task_id"
    clusters = sorted(frame[cluster_field].unique())
    # A mixed model cannot identify a random intercept from an outer-cluster
    # resample containing only one distinct cluster. Draw from the ordinary
    # cluster bootstrap conditional on retaining identifiable support; do not
    # replace the frozen model with a simpler fallback.
    sampled: list[str] = []
    while len(set(sampled)) < 2:
        sampled = [rng.choice(clusters) for _ in clusters]
    pieces: list[pd.DataFrame] = []
    for cluster_index, cluster in enumerate(sampled):
        cluster_frame = frame[frame[cluster_field] == cluster]
        tasks = sorted(cluster_frame.base_task_id.unique())
        sampled_tasks = [rng.choice(tasks) for _ in tasks] if cluster_field == "building_id" else tasks
        for task_index, task in enumerate(sampled_tasks):
            piece = cluster_frame[cluster_frame.base_task_id == task].copy()
            piece["base_task_id"] = f"bootstrap_cluster_{cluster_index}_task_{task_index}"
            if cluster_field == "building_id":
                piece["building_id"] = f"bootstrap_building_{cluster_index}"
            pieces.append(piece)
    method = "building_then_task" if complete_buildings else "task"
    return pd.concat(pieces, ignore_index=True), f"{method}_conditioned_on_two_outer_clusters"


def estimate_task_adjusted_qgt(
    rows: list[dict[str, Any]], *, estimator_contract: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return worker evidence, task effects and a fail-closed model audit."""
    contract = {
        "adjust_stage": False,
        "adjust_building": False,
        "bootstrap_replicates": 200,
        "bootstrap_seed": 20260726,
        "confidence_level": 0.95,
        "minimum_successful_bootstrap_fraction": 0.75,
        **(estimator_contract or {}),
    }
    frame = _prepare_frame(rows, contract)
    point = _fit_once(frame, contract)
    workers = sorted(point["estimates"])
    draws = int(contract["bootstrap_replicates"])
    if draws < 20:
        raise ValueError("task/building cluster bootstrap requires at least 20 replicates")
    rng = random.Random(int(contract["bootstrap_seed"]))
    bootstrap: list[list[float]] = []
    failed = 0
    resampling = ""
    for _ in range(draws):
        sampled, resampling = _resample_frame(frame, rng)
        try:
            fitted = _fit_once(sampled, contract)
            values = [fitted["estimates"][worker] for worker in workers]
            if np.isfinite(values).all():
                bootstrap.append(values)
            else:
                failed += 1
        except (ValueError, np.linalg.LinAlgError):
            failed += 1
    minimum = max(20, math.ceil(draws * float(contract["minimum_successful_bootstrap_fraction"])))
    if len(bootstrap) < minimum:
        raise ValueError(f"insufficient successful task/building bootstrap fits:{len(bootstrap)}/{draws}")
    samples = np.asarray(bootstrap, dtype=float)
    covariance = np.cov(samples, rowvar=False, ddof=1)
    if covariance.ndim == 0:
        covariance = np.asarray([[float(covariance)]])
    if covariance.shape != (len(workers), len(workers)) or not np.isfinite(covariance).all():
        raise ValueError("invalid worker contrast covariance")
    confidence = float(contract["confidence_level"])
    alpha = (1 - confidence) / 2
    worker_rows: list[dict[str, Any]] = []
    for index, worker in enumerate(workers):
        distribution = samples[:, index]
        estimate = point["estimates"][worker]
        lower, upper = float(np.quantile(distribution, alpha)), float(np.quantile(distribution, 1 - alpha))
        covariance_row = {other: float(covariance[index, other_index]) for other_index, other in enumerate(workers)}
        subset = frame[frame.worker_id == worker]
        worker_rows.append({
            "worker_id": worker,
            "Q_GT_raw": float(subset.quality.mean()),
            "Q_GT_task_adjusted": estimate,
            "Q_GT_standard_error": float(math.sqrt(max(0.0, covariance[index, index]))),
            "Q_GT_CI_lower": lower,
            "Q_GT_CI_upper": upper,
            "Q_GT_LCB": lower,
            "GT_support": len(subset),
            "task_support": int(subset.base_task_id.nunique()),
            "building_support": int(subset.loc[subset.building_id.ne(""), "building_id"].nunique()),
            "Q_GT_contrast_covariance_row_json": json.dumps(covariance_row, sort_keys=True, separators=(",", ":")),
            "global_rank": "",
            "provisional_rank": "",
            "model_version": MODEL_VERSION,
            "evidence_role": "c1_measurement_only",
        })
    task_rows = [
        {"base_task_id": task, "task_random_intercept": value, "model_version": MODEL_VERSION}
        for task, value in sorted(point["task_effects"].items())
    ]
    audit = {
        "status": "estimated",
        "model_version": MODEL_VERSION,
        "formula": point["formula"],
        "optimizer": point["optimizer"],
        "worker_effect": "fixed",
        "task_effect": "random_intercept",
        "stage_adjustment": bool(contract["adjust_stage"]),
        "building_adjustment": bool(contract["adjust_building"]),
        "bootstrap_cluster": resampling,
        "bootstrap_identifiability_condition": "at_least_two_distinct_outer_clusters",
        "bootstrap_replicates_requested": draws,
        "bootstrap_replicates_successful": len(bootstrap),
        "bootstrap_failures": failed,
        "bootstrap_seed": int(contract["bootstrap_seed"]),
        "confidence_level": confidence,
        "worker_order": workers,
        "worker_contrast_covariance": covariance.tolist(),
        "residual_variance": point["residual_variance"],
        "task_intercept_variance": point["task_intercept_variance"],
        "warnings": point["warnings"],
        "ranking_materialized": False,
    }
    return worker_rows, task_rows, audit
