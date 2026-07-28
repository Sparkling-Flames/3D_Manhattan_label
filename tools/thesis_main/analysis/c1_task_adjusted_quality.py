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
from collections import Counter, defaultdict
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.optimize import minimize_scalar


MODEL_VERSION = "c1_worker_fe_task_random_intercept_cluster_bootstrap_v3"


def normal_normal_empirical_bayes(
    estimates: list[float], standard_errors: list[float], *, confidence_level: float = 0.95,
) -> tuple[list[dict[str, float]], dict[str, Any]]:
    """MLE normal-normal shrinkage with hyper-mean uncertainty retained."""
    theta = np.asarray(estimates, dtype=float); se = np.asarray(standard_errors, dtype=float)
    if len(theta) < 2 or theta.shape != se.shape or not np.isfinite(theta).all() or not np.isfinite(se).all() or np.any(se <= 0):
        raise ValueError("empirical Bayes requires at least two finite estimates with positive SE")
    s2 = se ** 2
    def profile(tau2: float) -> tuple[float, float]:
        variance = s2 + tau2
        weights = 1 / variance
        mu = float(np.sum(weights * theta) / np.sum(weights))
        nll = .5 * float(np.sum(np.log(variance) + (theta - mu) ** 2 / variance))
        return nll, mu
    upper = max(float(np.var(theta, ddof=1)) * 100, float(np.max(s2)) * 100, 1e-6)
    fitted = minimize_scalar(lambda value: profile(float(value))[0], bounds=(0.0, upper), method="bounded")
    if not fitted.success or not math.isfinite(float(fitted.fun)):
        raise ValueError("empirical Bayes marginal likelihood did not converge")
    tau2 = max(0.0, float(fitted.x)); _, mu = profile(tau2)
    hyper_variance = 1.0 / float(np.sum(1.0 / (s2 + tau2)))
    z = NormalDist().inv_cdf(.5 + confidence_level / 2)
    rows = []
    for estimate, variance in zip(theta, s2):
        shrinkage = tau2 / (tau2 + variance)
        posterior = mu + shrinkage * (float(estimate) - mu)
        posterior_variance = shrinkage * variance + (1 - shrinkage) ** 2 * hyper_variance
        posterior_se = math.sqrt(max(posterior_variance, np.finfo(float).eps))
        rows.append({"estimate": posterior, "standard_error": posterior_se, "lower": posterior - z * posterior_se, "upper": posterior + z * posterior_se, "shrinkage_factor": shrinkage})
    return rows, {"eb_model_status": "estimated", "eb_mu": float(mu), "eb_tau_squared": float(tau2), "likelihood_converged": True, "workers_shrunk": int(sum(bool(row["shrinkage_factor"] < 1) for row in rows)), "maximum_shrinkage": float(max(row["shrinkage_factor"] for row in rows)), "minimum_shrinkage": float(min(row["shrinkage_factor"] for row in rows))}


class _FitFailure(ValueError):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


class _BootstrapSupportFailure(ValueError):
    """Fail closed while preserving replicate-level diagnostics for the runner."""

    def __init__(self, audit: dict[str, Any]) -> None:
        super().__init__(
            "insufficient successful task/building bootstrap fits:"
            f"{audit['bootstrap_replicates_successful']}/{audit['bootstrap_replicates_requested']}"
        )
        self.audit = audit


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
        if any("LinAlgError" in error for error in errors):
            reason = "singular"
        elif any("not_converged" in error for error in errors):
            reason = "model_not_converged"
        else:
            reason = "model_fit_error"
        raise _FitFailure(reason, "task-adjusted mixed model failed:" + ";".join(errors))
    fixed_names = list(fitted.fe_params.index)
    fixed_cov = fitted.cov_params().loc[fixed_names, fixed_names]
    if not fitted.converged or not np.isfinite(fitted.fe_params.to_numpy()).all() or not np.isfinite(fixed_cov.to_numpy()).all():
        reason = "model_not_converged" if not fitted.converged else "nonfinite"
        raise _FitFailure(reason, "task-adjusted mixed model did not converge to finite fixed effects/covariance")
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
    failure_reasons: Counter[str] = Counter()
    resampling = ""
    for _ in range(draws):
        sampled, resampling = _resample_frame(frame, rng)
        try:
            fitted = _fit_once(sampled, contract)
            missing_workers = [worker for worker in workers if worker not in fitted["estimates"]]
            if missing_workers:
                failure_reasons["missing_worker_level"] += 1
                continue
            values = [fitted["estimates"][worker] for worker in workers]
            if np.isfinite(values).all():
                bootstrap.append(values)
            else:
                failure_reasons["nonfinite"] += 1
        except _FitFailure as exc:
            failure_reasons[exc.reason] += 1
        except np.linalg.LinAlgError:
            failure_reasons["singular"] += 1
        except (KeyError, ValueError):
            # A malformed or support-limited replicate is auditable but must
            # never abort the whole model before the frozen success threshold.
            failure_reasons["model_fit_error"] += 1
    minimum = max(20, math.ceil(draws * float(contract["minimum_successful_bootstrap_fraction"])))
    if len(bootstrap) < minimum:
        raise _BootstrapSupportFailure({
            "reason": "insufficient_successful_bootstrap_fraction",
            "bootstrap_replicates_requested": draws,
            "bootstrap_replicates_successful": len(bootstrap),
            "bootstrap_failures": sum(failure_reasons.values()),
            "bootstrap_failure_reasons": dict(sorted(failure_reasons.items())),
            "bootstrap_minimum_successful_replicates": minimum,
            "bootstrap_successful_fraction": len(bootstrap) / draws,
            "bootstrap_seed": int(contract["bootstrap_seed"]),
        })
    samples = np.asarray(bootstrap, dtype=float)
    covariance = np.cov(samples, rowvar=False, ddof=1)
    if covariance.ndim == 0:
        covariance = np.asarray([[float(covariance)]])
    if covariance.shape != (len(workers), len(workers)) or not np.isfinite(covariance).all():
        raise ValueError("invalid worker contrast covariance")
    confidence = float(contract["confidence_level"])
    alpha = (1 - confidence) / 2
    worker_rows: list[dict[str, Any]] = []
    fe_estimates = [point["estimates"][worker] for worker in workers]
    fe_ses = [float(math.sqrt(max(0.0, covariance[index, index]))) for index in range(len(workers))]
    eb_rows, eb_audit = normal_normal_empirical_bayes(fe_estimates, fe_ses, confidence_level=confidence)
    for index, worker in enumerate(workers):
        distribution = samples[:, index]
        estimate = point["estimates"][worker]
        lower, upper = float(np.quantile(distribution, alpha)), float(np.quantile(distribution, 1 - alpha))
        covariance_row = {other: float(covariance[index, other_index]) for other_index, other in enumerate(workers)}
        subset = frame[frame.worker_id == worker]
        eb = eb_rows[index]
        worker_rows.append({
            "worker_id": worker,
            "Q_GT_raw": float(subset.quality.mean()),
            "Q_GT_task_adjusted": estimate,
            "Q_GT_task_adjusted_FE": estimate,
            "Q_GT_standard_error": float(math.sqrt(max(0.0, covariance[index, index]))),
            "Q_GT_FE_standard_error": float(math.sqrt(max(0.0, covariance[index, index]))),
            "Q_GT_CI_lower": lower,
            "Q_GT_CI_upper": upper,
            "Q_GT_LCB": lower,
            "Q_GT_FE_CI_lower": lower, "Q_GT_FE_CI_upper": upper, "Q_GT_FE_LCB": lower,
            "Q_GT_EB": eb["estimate"], "Q_GT_EB_standard_error": eb["standard_error"],
            "Q_GT_EB_CI_lower": eb["lower"], "Q_GT_EB_CI_upper": eb["upper"], "Q_GT_EB_LCB": eb["lower"],
            "Q_GT_shrinkage_factor": eb["shrinkage_factor"],
            "Q_GT_support": len(subset),
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
        "bootstrap_failures": sum(failure_reasons.values()),
        "bootstrap_failure_reasons": dict(sorted(failure_reasons.items())),
        "bootstrap_minimum_successful_replicates": minimum,
        "bootstrap_successful_fraction": len(bootstrap) / draws,
        "bootstrap_seed": int(contract["bootstrap_seed"]),
        "confidence_level": confidence,
        "worker_order": workers,
        "worker_contrast_covariance": covariance.tolist(),
        "residual_variance": point["residual_variance"],
        "task_intercept_variance": point["task_intercept_variance"],
        "warnings": point["warnings"],
        "ranking_materialized": False,
        **eb_audit,
    }
    return worker_rows, task_rows, audit
