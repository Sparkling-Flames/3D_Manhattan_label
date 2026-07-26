"""Fit the frozen C1 risk-resilience inputs consumed by C2-B design."""

from __future__ import annotations

import csv
import json
import math
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


def _read(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _number(row: dict[str, Any], *fields: str) -> float | None:
    for field in fields:
        try:
            value = float(row.get(field, ""))
            if np.isfinite(value):
                return value
        except (TypeError, ValueError):
            pass
    return None


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _completion_usable(row: dict[str, str]) -> bool:
    status = row.get("completion_status", "")
    return (
        status in {"completed", "partial_noncompletion", "closed_partial_usable"}
        and status not in {"nonstarter", "closed_partial_insufficient", "administrative_exclusion"}
        and not _truth(row.get("administrative_exclusion"))
    )


def _variance_boundary_decision(
    components: dict[str, float], residual_variance: float,
) -> tuple[str, list[str], float]:
    """Return the sole permitted nested-model decision at a numeric variance boundary."""
    tolerance = max(1e-10, 1e-6 * residual_variance) if math.isfinite(residual_variance) and residual_variance >= 0 else math.nan
    boundary = sorted(
        name for name, value in components.items()
        if math.isfinite(value) and math.isfinite(tolerance) and value <= tolerance
    )
    if not boundary:
        decision = "crossed_random_worker_slope"
    elif boundary == ["worker_slope"]:
        decision = "refit_crossed_common_worker_slope"
    else:
        decision = "fail_unsupported_non_slope_boundary"
    return decision, boundary, tolerance


def _fit_crossed_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit the frozen crossed model and its one allowed nested boundary form."""
    support = {
        "worker_id": len({row["worker_id"] for row in records}),
        "base_task_id": len({row["base_task_id"] for row in records}),
        "building_id": len({row["building_id"] for row in records if row["building_id"]}),
        "risk": len({row["risk"] for row in records}),
    }
    if len(records) < 12 or support["worker_id"] < 3 or support["base_task_id"] < 4 or support["building_id"] < 2 or support["risk"] < 3:
        return {"status": "insufficient_support", "support": support}
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
        from statsmodels.tools.sm_exceptions import ConvergenceWarning

        frame = pd.DataFrame(records)
        frame["risk_centered"] = frame["risk"] - frame["risk"].mean()
        frame["all_group"] = "all"
        formula = "quality ~ risk_centered + C(stage)"
        random_slope_variance = {
            "worker_intercept": "0 + C(worker_id)",
            "worker_slope": "0 + C(worker_id):risk_centered",
            "task": "0 + C(base_task_id)",
            "building": "0 + C(building_id)",
        }
        common_slope_variance = {name: value for name, value in random_slope_variance.items() if name != "worker_slope"}

        def fit(variance: dict[str, str]):
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = smf.mixedlm(
                    formula, frame, groups=frame["all_group"], re_formula="0", vc_formula=variance,
                ).fit(reml=True, method="lbfgs", maxiter=1000, disp=False)
            return result, [str(item.message) for item in caught if issubclass(item.category, ConvergenceWarning)]

        result, convergence_warnings = fit(random_slope_variance)
        names = list(result.model.exog_vc.names)
        components = {name: float(value) for name, value in zip(names, result.vcomp)}
        fixed = float(result.fe_params["risk_centered"])
        try:
            fixed_variance = float(result.cov_params().loc["risk_centered", "risk_centered"])
        except (KeyError, TypeError, ValueError):
            fixed_variance = math.nan
        residual_variance = float(result.scale)
        boundary_decision, boundary, tolerance = _variance_boundary_decision(components, residual_variance)
        identifiable = math.isfinite(fixed) and math.isfinite(fixed_variance) and fixed_variance >= 0
        if not bool(result.converged) or not identifiable or not math.isfinite(residual_variance) or residual_variance <= 0:
            return {
                "status": "not_converged_or_unidentifiable", "support": support,
                "converged": bool(result.converged), "warnings": convergence_warnings,
                "boundary_components": boundary, "boundary_tolerance": tolerance,
            }
        slope_model_form = "crossed_random_worker_slope"
        if boundary_decision == "refit_crossed_common_worker_slope":
            result, nested_warnings = fit(common_slope_variance)
            convergence_warnings.extend(nested_warnings)
            names = list(result.model.exog_vc.names)
            components = {name: float(value) for name, value in zip(names, result.vcomp)}
            fixed = float(result.fe_params["risk_centered"])
            residual_variance = float(result.scale)
            _nested_decision, nested_boundary, tolerance = _variance_boundary_decision(components, residual_variance)
            try:
                fixed_variance = float(result.cov_params().loc["risk_centered", "risk_centered"])
            except (KeyError, TypeError, ValueError):
                fixed_variance = math.nan
            if not bool(result.converged) or nested_boundary or not math.isfinite(fixed_variance) or fixed_variance < 0:
                return {
                    "status": "nested_common_slope_not_converged_or_singular", "support": support,
                    "converged": bool(result.converged), "warnings": convergence_warnings,
                    "boundary_components": nested_boundary, "boundary_tolerance": tolerance,
                }
            slope_model_form = "crossed_common_worker_slope"
            boundary = ["worker_slope"]
        elif boundary_decision == "fail_unsupported_non_slope_boundary":
            return {
                "status": "unsupported_non_slope_boundary", "support": support,
                "converged": bool(result.converged), "warnings": convergence_warnings,
                "boundary_components": boundary, "boundary_tolerance": tolerance,
            }
        random_effects = result.random_effects.get("all", {})
        random_effect_cov = result.random_effects_cov.get("all")
        worker_slopes: dict[str, float] = {}
        worker_slope_ses: dict[str, float] = {}
        for worker in sorted({row["worker_id"] for row in records}):
            if slope_model_form == "crossed_common_worker_slope":
                worker_slopes[worker] = fixed
                worker_slope_ses[worker] = math.sqrt(fixed_variance)
                continue
            suffix = f"[C(worker_id)[{worker}]:risk_centered]"
            coefficient_name = next((name for name in random_effects.index if str(name).endswith(suffix)), None)
            deviation = float(random_effects[coefficient_name]) if coefficient_name is not None else 0.0
            worker_slopes[worker] = fixed + deviation
            if coefficient_name is not None and random_effect_cov is not None:
                posterior_variance = float(random_effect_cov.loc[coefficient_name, coefficient_name])
                if math.isfinite(posterior_variance) and posterior_variance >= 0:
                    worker_slope_ses[worker] = math.sqrt(posterior_variance)
        values = [*components.values(), float(result.scale), fixed, fixed_variance]
        finite = all(math.isfinite(value) and (value >= 0 or value == fixed) for value in values)
        status = "estimated" if bool(result.converged) and finite else "not_converged_or_singular"
        return {
            "status": status,
            "formula": formula,
            "optimizer": "lbfgs",
            "converged": bool(result.converged),
            "warnings": convergence_warnings,
            "support": support,
            "group_slope_mean": fixed,
            "group_slope_se": math.sqrt(fixed_variance),
            "between_worker_slope_sd": 0.0 if slope_model_form == "crossed_common_worker_slope" else math.sqrt(max(0.0, components.get("worker_slope", math.nan))),
            "worker_intercept_sd": math.sqrt(max(0.0, components.get("worker_intercept", math.nan))),
            "task_sd": math.sqrt(max(0.0, components.get("task", math.nan))),
            "building_sd": math.sqrt(max(0.0, components.get("building", math.nan))),
            "outcome_residual_sd": math.sqrt(max(0.0, float(result.scale))),
            "worker_slopes": worker_slopes,
            "worker_slope_ses": worker_slope_ses,
            "slope_model_form": slope_model_form,
            "boundary_components": boundary,
            "boundary_tolerance": tolerance,
            "boundary_rule_version": "worker_slope_numeric_boundary_v1",
        }
    except Exception as exc:
        return {"status": "model_error", "support": support, "error": f"{type(exc).__name__}:{exc}"}


def materialize(
    quality_csv: Path,
    risk_csv: Path,
    structural_csv: Path,
    completion_csv: Path,
    output_dir: Path,
    *,
    worker_state_csv: Path | None = None,
) -> dict[str, Any]:
    risk = {row.get("base_task_id", ""): row for row in _read(risk_csv)}
    completion = {row.get("worker_id", ""): row for row in _read(completion_csv)}
    state = {row.get("worker_id", ""): row for row in _read(worker_state_csv)}
    by_worker: dict[str, list[tuple[float, float, str, str]]] = defaultdict(list)
    qgt_support: dict[str, int] = defaultdict(int)
    records: list[dict[str, Any]] = []
    for row in _read(quality_csv):
        worker, task = row.get("worker_id", ""), row.get("base_task_id", "")
        if not worker or not task or not _truth(row.get("global_analysis_eligible")) or not _completion_usable(completion.get(worker, {})):
            continue
        qgt_support[worker] += 1
        risk_row = risk.get(task, {})
        x = _number(risk_row, "risk_design_score_A")
        y = _number(row, "Q_GT_raw", "iou_to_gt", "iou_2d", "iou")
        building = str(risk_row.get("building_id", ""))
        if x is None or y is None or not building:
            continue
        by_worker[worker].append((x, y, task, building))
        records.append({"worker_id": worker, "base_task_id": task, "building_id": building, "stage": row.get("stage") or "C1", "risk": x, "quality": y})

    failures, opportunities = defaultdict(int), defaultdict(int)
    for row in _read(structural_csv):
        if _truth(row.get("structural_opportunity_eligible")):
            worker = row.get("worker_id", "")
            opportunities[worker] += 1
            failures[worker] += row.get("failure_attribution") == "worker_caused_structural_failure"

    model = _fit_crossed_model(records)
    model_workers = sorted(by_worker)
    group_slope = model.get("group_slope_mean", "")
    group_sd = model.get("between_worker_slope_sd", "")
    rows: list[dict[str, Any]] = []
    for worker in sorted(completion):
        observations = by_worker[worker]
        baseline = _number(state.get(worker, {}), "Q_GT_task_adjusted")
        baseline_se = _number(state.get(worker, {}), "standard_error", "Q_GT_task_adjusted_se", "Q_GT_SE", "SE")
        direct_slope = direct_se = ""
        if len(observations) >= 3 and len({item[0] for item in observations}) >= 2:
            x = np.asarray([item[0] for item in observations]); y = np.asarray([item[1] for item in observations])
            design = np.column_stack([np.ones(len(x)), x]); beta = np.linalg.lstsq(design, y, rcond=None)[0]
            residual = y - design @ beta
            variance = float(residual @ residual / max(1, len(x) - 2))
            direct_slope = float(beta[1])
            try:
                direct_se = float(np.sqrt(variance * np.linalg.inv(design.T @ design)[1, 1]))
            except np.linalg.LinAlgError:
                direct_se = ""
        eligible = worker in model_workers and baseline is not None and baseline_se is not None
        slope = model.get("worker_slopes", {}).get(worker, direct_slope)
        slope_se = model.get("worker_slope_ses", {}).get(worker, "")
        slope_status = "estimated_crossed_model" if worker in model.get("worker_slopes", {}) else "direct_diagnostic_only" if direct_slope != "" else "group_prior_only" if eligible else "not_eligible"
        assigned = int(float(completion[worker].get("assigned_total_count") or 0)); observed = int(float(completion[worker].get("observed_total_count") or 0))
        rows.append({
            "worker_id": worker, "completion_status": completion[worker].get("completion_status", ""), "c2b_baseline_eligible": eligible,
            "Q_GT_task_adjusted": "" if baseline is None else baseline, "Q_GT_baseline_se": "" if baseline_se is None else baseline_se,
            "Q_GT_contrast_covariance_row_json": state.get(worker, {}).get("Q_GT_contrast_covariance_row_json", ""),
            "Q_GT_baseline_source": "strong_global_task_adjusted" if baseline is not None and baseline_se is not None else "not_evaluable",
            "risk_slope": slope, "risk_slope_se": slope_se, "risk_support": len(observations),
            "risk_slope_direct_diagnostic": direct_slope, "risk_slope_direct_diagnostic_se": direct_se,
            "Q_GT_support_for_slope": qgt_support[worker], "building_support": len({item[3] for item in observations if item[3]}),
            "group_prior_slope": group_slope, "group_prior_scale": group_sd, "group_slope_mean": group_slope,
            "group_slope_se": model.get("group_slope_se", ""), "group_slope_sd": "",
            "between_worker_slope_sd": group_sd, "outcome_residual_sd": model.get("outcome_residual_sd", ""),
            "worker_intercept_sd": model.get("worker_intercept_sd", ""), "task_sd": model.get("task_sd", ""), "building_sd": model.get("building_sd", ""),
            "risk_slope_for_simulation": slope if eligible and slope != "" else group_slope if eligible else "",
            "risk_slope_scale_for_simulation": slope_se if eligible and slope_se != "" else group_sd if eligible else "",
            "c1_risk_slope_status": slope_status, "missing_rate": (assigned - observed) / assigned if assigned else "",
            "F_struct": failures[worker] / opportunities[worker] if opportunities[worker] else "", "F_struct_numerator": failures[worker], "F_struct_denominator": opportunities[worker],
            "slope_model_form": model.get("slope_model_form", ""),
            "slope_boundary_components": ";".join(model.get("boundary_components", [])),
            "slope_boundary_rule_version": model.get("boundary_rule_version", ""),
            "parameter_status": "estimated" if eligible and model.get("status") == "estimated" else "audit_only_or_insufficient",
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "c1_c2_design_parameters.csv"
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["worker_id"]); writer.writeheader(); writer.writerows(rows)
    eligible_rows = [row for row in rows if row["c2b_baseline_eligible"]]
    formal_ready = (
        bool(eligible_rows)
        and model.get("status") == "estimated"
        and model.get("group_slope_se", "") != ""
        and all(row["Q_GT_baseline_se"] != "" and row["Q_GT_contrast_covariance_row_json"] for row in eligible_rows)
    )
    summary = {
        "n_workers": len(rows), "n_model_workers": len(model_workers), "n_c2b_baseline_eligible": len(eligible_rows),
        "n_estimated": sum(row["risk_slope"] != "" for row in rows), "model_status": model.get("status"),
        "model_audit": {key: value for key, value in model.items() if key not in {"worker_slopes", "worker_slope_ses"}},
        "group_prior_available": group_slope != "" and group_sd != "", "formal_design_input_ready": formal_ready,
        "variance_status": "estimated" if model.get("status") == "estimated" else "insufficient",
        "slope_model_form": model.get("slope_model_form", ""),
        "variance_components": {name: model.get(name, "") for name in ("group_slope_se", "between_worker_slope_sd", "outcome_residual_sd", "worker_intercept_sd", "task_sd", "building_sd")},
    }
    (output_dir / "c1_c2_design_parameters.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
