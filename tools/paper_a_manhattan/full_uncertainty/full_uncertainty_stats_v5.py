"""Small, explicit statistics helpers for the Paper A v5 uncertainty lanes.

The caller owns the denominator: pass canonical and raw records separately.  This
module does not deduplicate records or infer canonical membership.
"""
from __future__ import annotations

import math
import warnings
from collections import Counter
from itertools import combinations
from typing import Any, Iterable

import numpy as np
import pandas as pd


_MISSING = {"", "na", "n/a", "nan", "none", "null"}
_TRUE = {"1", "true", "yes", "y", "passed", "valid", "eligible"}
_LANE_ALIASES = {
    "all_computable": "all-computable",
    "exclude_joint_near_zero": "exclude_joint_near_zero",
    "edited_positive": "edited-positive",
    "formal_only": "formal-only",
}


def _missing(value: Any) -> bool:
    if value is None or value is pd.NA:
        return True
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return True
    return isinstance(value, str) and value.strip().lower() in _MISSING


def _response_key(value: Any) -> Any:
    """Make scalar, mapping, and sequence responses countable without losing type."""
    if _missing(value):
        return None
    if isinstance(value, dict):
        return ("dict", tuple(sorted((str(key), _response_key(child)) for key, child in value.items())))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(_response_key(child) for child in value))
    if isinstance(value, (set, frozenset)):
        return (type(value).__name__, frozenset(_response_key(child) for child in value))
    try:
        hash(value)
    except TypeError:
        return (type(value).__name__, repr(value))
    return (type(value).__name__, value)


def _response_counts(responses: Iterable[Any]) -> Counter[Any]:
    counts: Counter[Any] = Counter()
    for response in responses:
        key = _response_key(response)
        if key is not None:
            counts[key] += 1
    return counts


def response_pattern_entropy(responses: Iterable[Any]) -> float:
    """Return natural-log Shannon entropy of complete response patterns.

    Missing/blank responses are omitted.  No observations returns ``nan``;
    canonical/raw denominator choice remains with the caller.
    """
    counts = _response_counts(responses)
    if not counts:
        return float("nan")
    total = sum(counts.values())
    return float(-sum((count / total) * math.log(count / total) for count in counts.values()))


def mean_pairwise_jaccard_disagreement(response_sets: Iterable[Iterable[Any]]) -> float | None:
    """Return mean pairwise ``1 - Jaccard`` disagreement.

    Two empty sets are identical, so their disagreement is ``0.0``.  Fewer than
    two responses has no pairwise estimand and returns ``None``.
    """
    disagreements: list[float] = []
    for left, right in combinations(response_sets, 2):
        left_set, right_set = set(left), set(right)
        union = left_set | right_set
        jaccard = 1.0 if not union else len(left_set & right_set) / len(union)
        disagreements.append(1.0 - jaccard)
    return None if not disagreements else float(sum(disagreements) / len(disagreements))


def modal_response_share(responses: Iterable[Any]) -> float:
    """Return the largest complete-response-pattern share, omitting missing values."""
    counts = _response_counts(responses)
    return float("nan") if not counts else max(counts.values()) / sum(counts.values())


def filter_structural_zero_lane(
    frame: pd.DataFrame,
    lane: str,
    *,
    rmse_col: str = "geometry_edit_rmse_px",
    delta_u_col: str = "delta_U",
    formal_col: str = "formal_assignment_eligible",
    near_zero_tolerance: float = 0.0,
) -> pd.DataFrame:
    """Filter computable rows for the requested structural-zero sensitivity lane.

    All lanes require finite, non-negative RMSE and finite ``delta_U``.  Thus a
    missing RMSE or ``delta_U`` can never become a joint zero through coercion.
    ``formal-only`` additionally requires a truthy formal eligibility flag.
    """
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("frame must be a pandas.DataFrame")
    token = str(lane).strip().lower().replace("-", "_")
    token = _LANE_ALIASES.get(token, lane.strip().lower())
    if token not in {"all-computable", "exclude_joint_near_zero", "edited-positive", "formal-only"}:
        raise ValueError(f"unknown structural-zero lane: {lane!r}")
    missing_columns = [column for column in (rmse_col, delta_u_col) if column not in frame.columns]
    resolved_formal_col = formal_col
    if token == "formal-only" and resolved_formal_col not in frame.columns and formal_col == "formal_assignment_eligible":
        resolved_formal_col = next((column for column in ("formal_use_allowed", "formal_eligible") if column in frame.columns), formal_col)
    if token == "formal-only" and resolved_formal_col not in frame.columns:
        missing_columns.append(resolved_formal_col)
    if missing_columns:
        raise KeyError(f"missing required column(s): {', '.join(missing_columns)}")

    rmse = pd.to_numeric(frame[rmse_col], errors="coerce")
    delta_u = pd.to_numeric(frame[delta_u_col], errors="coerce")
    finite = rmse.notna() & delta_u.notna() & np.isfinite(rmse) & np.isfinite(delta_u) & rmse.ge(0)
    tolerance = float(near_zero_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("near_zero_tolerance must be a finite non-negative number")
    joint_near_zero = finite & rmse.abs().le(tolerance) & delta_u.abs().le(tolerance)
    mask = finite
    if token == "exclude_joint_near_zero":
        mask &= ~joint_near_zero
    elif token == "edited-positive":
        mask &= rmse.gt(tolerance)
    elif token == "formal-only":
        formal = frame[resolved_formal_col].map(
            lambda value: isinstance(value, (bool, np.bool_)) and bool(value)
            or str(value).strip().lower() in _TRUE
        )
        mask &= formal
    return frame.loc[mask].copy()


def crossed_task_worker_variance_decomposition(
    frame: pd.DataFrame,
    *,
    outcome_col: str = "quality",
    task_col: str = "base_task_id",
    worker_col: str = "worker_id",
    maxiter: int = 200,
) -> dict[str, Any]:
    """Estimate crossed task/worker random-intercept variance components.

    This is a descriptive diagnostic, not a replacement for the frozen primary
    model.  Statsmodels uses one constant grouping factor plus variance
    components for task and worker, which gives a genuinely crossed design.
    Missing rows are excluded and reported in ``support``; insufficient or
    non-identifiable support fails closed with ``None`` variance values.
    """
    warnings_out: list[str] = []
    empty_support = {"n_rows": 0, "n_tasks": 0, "n_workers": 0, "n_task_worker_cells": 0, "n_rows_dropped": 0}
    if not isinstance(frame, pd.DataFrame):
        return {"task_variance": None, "worker_variance": None, "residual_variance": None, "status": "not_evaluable_frame_type", "converged": False, "warnings": ["frame must be a pandas.DataFrame"], "support": empty_support}
    required = (outcome_col, task_col, worker_col)
    missing_columns = [column for column in required if column not in frame.columns]
    if missing_columns:
        return {"task_variance": None, "worker_variance": None, "residual_variance": None, "status": "not_evaluable_missing_columns", "converged": False, "warnings": [f"missing required column(s): {', '.join(missing_columns)}"], "support": empty_support}

    data = pd.DataFrame(
        {
            "_v5_y": pd.to_numeric(frame[outcome_col], errors="coerce"),
            "_v5_task": frame[task_col],
            "_v5_worker": frame[worker_col],
        }
    )
    valid_groups = data["_v5_task"].notna() & data["_v5_worker"].notna()
    valid_groups &= ~data["_v5_task"].astype(str).str.strip().str.lower().isin(_MISSING)
    valid_groups &= ~data["_v5_worker"].astype(str).str.strip().str.lower().isin(_MISSING)
    valid = valid_groups & data["_v5_y"].notna() & np.isfinite(data["_v5_y"])
    dropped = int((~valid).sum())
    data = data.loc[valid].copy()
    data["_v5_task"] = data["_v5_task"].astype(str)
    data["_v5_worker"] = data["_v5_worker"].astype(str)
    support = {
        "n_rows": int(len(data)),
        "n_tasks": int(data["_v5_task"].nunique()),
        "n_workers": int(data["_v5_worker"].nunique()),
        "n_task_worker_cells": int(data[["_v5_task", "_v5_worker"]].drop_duplicates().shape[0]),
        "n_rows_dropped": dropped,
    }
    if dropped:
        warnings_out.append(f"dropped_invalid_rows:{dropped}")

    def result(status: str, *, converged: bool = False, task: float | None = None, worker: float | None = None, residual: float | None = None) -> dict[str, Any]:
        return {"task_variance": task, "worker_variance": worker, "residual_variance": residual, "status": status, "converged": converged, "warnings": warnings_out, "support": support}

    if support["n_tasks"] < 2:
        return result("not_evaluable_insufficient_tasks")
    if support["n_workers"] < 2:
        return result("not_evaluable_insufficient_workers")
    if support["n_rows"] <= support["n_tasks"] + support["n_workers"] - 1:
        return result("not_evaluable_unidentifiable_support")
    try:
        import statsmodels.formula.api as smf
    except Exception as exc:
        warnings_out.append(f"statsmodels_import:{type(exc).__name__}:{exc}")
        return result("not_evaluable_statsmodels_unavailable")

    fit = None
    for method in ("lbfgs", "powell"):
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                candidate = smf.mixedlm(
                    "_v5_y ~ 1", data, groups=np.ones(len(data)), re_formula="0",
                    vc_formula={"task": "0 + C(_v5_task)", "worker": "0 + C(_v5_worker)"},
                ).fit(reml=True, method=method, maxiter=maxiter, disp=False)
            warnings_out.extend(str(item.message) for item in caught)
            if bool(getattr(candidate, "converged", False)):
                fit = candidate
                break
            warnings_out.append(f"{method}:not_converged")
        except Exception as exc:
            warnings_out.append(f"{method}:{type(exc).__name__}:{exc}")
    if fit is None:
        return result("not_evaluable_not_converged")

    names = list(getattr(getattr(fit, "model", None), "exog_vc", None).names)
    values = np.asarray(getattr(fit, "vcomp", []), dtype=float)
    if len(names) != len(values) or not np.isfinite(values).all() or not math.isfinite(float(fit.scale)):
        return result("not_evaluable_nonfinite_fit", converged=True)
    components = dict(zip(names, values))
    task_variance, worker_variance, residual_variance = (float(components.get("task", np.nan)), float(components.get("worker", np.nan)), float(fit.scale))
    if not all(math.isfinite(value) and value >= 0 for value in (task_variance, worker_variance, residual_variance)):
        return result("not_evaluable_nonfinite_fit", converged=True)
    boundary = [name for name, value in (("task", task_variance), ("worker", worker_variance), ("residual", residual_variance)) if value <= 1e-6]
    if boundary:
        warnings_out.append("boundary_components:" + ",".join(boundary))
        status = "boundary_zero_component"
    else:
        status = "estimated"
    return result(status, converged=True, task=task_variance, worker=worker_variance, residual=residual_variance)
