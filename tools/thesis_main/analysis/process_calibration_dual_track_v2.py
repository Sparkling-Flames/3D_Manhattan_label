"""Corrected diagnostic-only Calibration processor (v2).

This is a fresh consumer of frozen/raw inputs.  It never consumes v1 outputs,
freezes a profile/policy, or produces a Stage-3 artifact.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import random
import subprocess
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis import process_calibration_dual_track as base
from tools.thesis_main.analysis.c1_task_adjusted_quality import normal_normal_empirical_bayes
from tools.thesis_main.analysis.materialize_c2_task_risk import RISK_VECTOR_FIELDS, _score


ROOT = base.ROOT
SEED = 20260815
BOOTSTRAP_REPLICATES = 50
ROLE_FIELDS = {**base.ROLE_FIELDS, "analysis_role": "exploratory_diagnostic_pre_stage3"}
CHANNELS = tuple(RISK_VECTOR_FIELDS)


def role(row: dict[str, Any]) -> dict[str, Any]:
    return {**ROLE_FIELDS, **row}


def vector_channels(value: Any) -> dict[str, float]:
    """Parse the only contract-authorized vector ordering."""
    try:
        values = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid risk_design_vector_A") from exc
    if not isinstance(values, list) or len(values) != len(CHANNELS):
        raise ValueError("risk_design_vector_A must have four ordered channels")
    parsed = [base.number(item) for item in values]
    if any(item is None for item in parsed):
        raise ValueError("risk_design_vector_A contains nonfinite channel")
    return dict(zip(CHANNELS, parsed))  # type: ignore[arg-type]


def exact_duplicate_feature(frame: pd.DataFrame, field: str) -> bool:
    values = pd.to_numeric(frame[field], errors="coerce")
    return bool(values.notna().all() and np.allclose(values.to_numpy(), frame.risk.to_numpy(), rtol=1e-12, atol=1e-12))


def c2_stage(row: dict[str, Any]) -> str:
    return "C2B" if row["stage"] == "C2B" else f"C2A_RP_{row['substage_block'].upper()}"


def enrich_c2_evidence(evidence: list[dict[str, Any]], inputs: dict[str, Path | list[Path]], output: Path) -> list[dict[str, Any]]:
    contract_path = ROOT / "docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = "[d_model_feat, d_model_feat_local_max, g_model_struct, d_cal_A]"
    if contract.get("risk_channels", {}).get("risk_design_vector_A") != f"ordered frozen vector {expected}":
        raise ValueError("risk design contract vector order mismatch")
    pool = {base.clean(row.get("base_task_id")): row for row in base.csv_rows(inputs["feature_pool"])}  # type: ignore[arg-type]
    crosswalk = {(base.clean(row.get("evidence_stage")), base.clean(row.get("base_task_id"))): row for row in base.csv_rows(inputs["crosswalk"])}  # type: ignore[arg-type]
    audit: list[dict[str, Any]] = []
    for row in evidence:
        if row["stage"] not in {"C2B", "C2A_RP"}:
            continue
        key = base.clean(row["base_task_id"]); feature = pool.get(key)
        cross = crosswalk.get((c2_stage(row), key))
        row["reference_crosswalk_join_status"] = "joined" if cross else "not_joined_in_this_processing_package"
        row["reference_status"] = base.clean(cross.get("reference_status")) if cross else ""
        row["reference_version"] = base.clean(cross.get("reference_registry_sha256")) if cross else row.get("reference_version", "")
        row["active_time_join_status"] = "joined_from_canonical_submission" if base.number(row.get("active_time")) is not None else "not_joined_in_this_processing_package"
        if not base.truth(row.get("risk_evidence_eligible")):
            continue
        if feature is None:
            raise ValueError(f"eligible C2 task absent from frozen feature pool:{key}")
        channels = vector_channels(feature.get("risk_design_vector_A"))
        score = _score([channels[name] for name in CHANNELS])
        stored = base.number(feature.get("risk_design_score_A")); formal = base.number(row.get("risk"))
        if score is None or stored is None or formal is None:
            raise ValueError(f"eligible C2 task has unavailable frozen score:{key}")
        if not math.isclose(score, stored, rel_tol=1e-12, abs_tol=1e-12) or not math.isclose(stored, formal, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError(f"frozen production score mismatch:{key}")
        row.update(channels)
        row.update({
            "risk_design_vector_A": feature["risk_design_vector_A"], "risk_design_score_A": stored,
            "feature_manifest_sha256": base.clean(feature.get("feature_manifest_sha256")),
            "task_risk_sha256": base.clean(feature.get("task_risk_sha256")),
            "risk_contract_sha256": base.clean(feature.get("risk_contract_sha256")),
            "risk_score_recompute_status": "recomputed_by_materialize_c2_task_risk._score",
            "risk_score_recomputed": score,
            "channel_analysis_role": "exploratory_diagnostic_not_new_formal_profile",
        })
        audit.append(role({"canonical_submission_id": row["canonical_submission_id"], "base_task_id": key, "stage": c2_stage(row), "risk": formal, "risk_design_score_A": stored, "risk_design_vector_A": feature["risk_design_vector_A"], **channels, "feature_manifest_sha256": row["feature_manifest_sha256"], "task_risk_sha256": row["task_risk_sha256"], "risk_contract_sha256": row["risk_contract_sha256"], "score_recompute_status": row["risk_score_recompute_status"], "reference_crosswalk_join_status": row["reference_crosswalk_join_status"], "active_time_join_status": row["active_time_join_status"]}))
    base.write_csv(output / "risk_vector_channel_audit.csv", audit)
    if len(audit) != 225:
        raise ValueError(f"expected 225 eligible risk rows, found {len(audit)}")
    return evidence


def model_matrix(formula: str, frame: pd.DataFrame) -> tuple[int, int, float]:
    design = smf.ols(formula, frame).exog
    rank = int(np.linalg.matrix_rank(design)); columns = int(design.shape[1])
    condition = float(np.linalg.cond(design)) if rank else math.inf
    return rank, columns, condition


def mixed_is_boundary(covariance: np.ndarray) -> bool:
    eigen = np.linalg.eigvalsh(covariance)
    intercept, slope, cross = float(covariance[0, 0]), float(covariance[1, 1]), float(covariance[0, 1])
    correlation = cross / math.sqrt(intercept * slope) if intercept > 0 and slope > 0 else math.inf
    return bool(np.min(eigen) <= 1e-8 or np.min(eigen) / np.max(eigen) <= 1e-4 or abs(correlation) >= .99)


def _cluster_result(fit: Any, frame: pd.DataFrame) -> Any | None:
    try:
        return fit.get_robustcov_results(cov_type="cluster", groups=frame.base_task_id.astype(str))
    except Exception:
        return None


def fit_spec(spec: dict[str, str], frame: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]], Any | None]:
    formula, name, kind = spec["formula"], spec["model_name"], spec["kind"]
    rank, columns, condition = model_matrix(formula, frame)
    summary = role({"model_name": name, "formula": formula, "kind": kind, "analysis_subrole": spec.get("analysis_subrole", "exploratory_diagnostic"), "included_rows": len(frame), "workers": frame.worker_id.nunique(), "tasks": frame.base_task_id.nunique(), "buildings": frame.building_id.nunique(), "model_rank": rank, "design_columns": columns, "condition_number": condition, "rank_deficient": rank < columns, "residual_df": "", "convergence": False, "singular": False, "boundary": False, "hessian": "", "optimizer": "", "status": ""})
    if rank < columns:
        summary.update(status="not_evaluable_rank_deficient", failure_reason="design_matrix_rank_deficient")
        return summary, [], None
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if kind == "mixed":
                fit = smf.mixedlm(formula, frame, groups=frame.worker_id, re_formula="1 + risk").fit(reml=True, method="lbfgs", maxiter=500, disp=False)
            else:
                fit = smf.ols(formula, frame).fit()
        warning_text = ";".join(str(item.message) for item in caught)
        summary.update(residual_df=float(fit.df_resid), convergence=bool(getattr(fit, "converged", True)), optimizer="lbfgs" if kind == "mixed" else "ols", warnings=warning_text)
        if kind == "mixed":
            covariance = np.asarray(fit.cov_re, dtype=float); eigen = np.linalg.eigvalsh(covariance)
            boundary = mixed_is_boundary(covariance)
            summary.update(boundary=boundary, singular=boundary, hessian="not_exposed_by_statsmodels_mixedlm", random_effect_eigenvalues_json=json.dumps(eigen.tolist()), status="boundary_singular" if boundary else "estimated")
            params, ses = fit.fe_params, fit.bse_fe
            robust = None
        else:
            robust = _cluster_result(fit, frame); params, ses = fit.params, fit.bse
            summary.update(status="estimated" if bool(getattr(fit, "converged", True)) else "not_converged")
        coefficients = []
        robust_params = np.asarray(robust.params) if robust is not None else None
        robust_ses = np.asarray(robust.bse) if robust is not None else None
        for index, term in enumerate(params.index):
            estimate, se = float(params[term]), float(ses[term])
            cse = float(robust_ses[index]) if robust_ses is not None and math.isfinite(float(robust_ses[index])) else ""
            coefficients.append(role({"model_name": name, "term": term, "estimate": estimate, "model_se": se, "base_task_cluster_se": cse, "base_task_cluster_ci_lower": estimate - 1.96 * cse if cse != "" else "", "base_task_cluster_ci_upper": estimate + 1.96 * cse if cse != "" else "", "is_worker_channel_interaction": bool(spec.get("channel") and term.startswith("C(worker_id)") and ":" in term), "status": summary["status"]}))
        interactions = [index for index, term in enumerate(params.index) if spec.get("channel") and term.startswith("C(worker_id)") and ":" in term]
        if interactions and robust is not None:
            try:
                matrix = np.zeros((len(interactions), len(params))); matrix[np.arange(len(interactions)), interactions] = 1
                test = robust.wald_test(matrix, scalar=True)
                summary.update(interaction_joint_test_status="estimated", interaction_joint_statistic=float(test.statistic), interaction_joint_pvalue=float(test.pvalue), interaction_joint_df=len(interactions))
            except Exception as exc:
                summary.update(interaction_joint_test_status="failed", interaction_joint_failure=f"{type(exc).__name__}:{exc}")
        elif spec.get("channel"):
            summary.update(interaction_joint_test_status="not_evaluable_no_worker_channel_terms")
        return summary, coefficients, fit
    except Exception as exc:
        summary.update(status="failed", failure_reason=f"{type(exc).__name__}:{exc}")
        return summary, [], None


def m2_details(summary: dict[str, Any], fit: Any, frame: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if fit is None:
        return [role({"model_name": "M2", "status": summary["status"], "reason": summary.get("failure_reason", "")})], []
    cov = np.asarray(fit.cov_re, dtype=float); eigen = np.linalg.eigvalsh(cov); intercept, slope = float(cov[0, 0]), float(cov[1, 1]); cross = float(cov[0, 1])
    variance = [role({"model_name": "M2", "status": summary["status"], "random_intercept_variance": intercept, "worker_risk_slope_variance": slope, "intercept_slope_covariance": cross, "intercept_slope_correlation": cross / math.sqrt(intercept * slope) if intercept > 0 and slope > 0 else "", "residual_variance": float(fit.scale), "optimizer": summary["optimizer"], "convergence": summary["convergence"], "singular": summary["singular"], "boundary": summary["boundary"], "hessian": summary["hessian"], "eigenvalues_json": json.dumps(eigen.tolist())})]
    workers = []
    for worker, random_effect in fit.random_effects.items():
        values = np.asarray(random_effect, dtype=float); random_slope = float(values[-1]); total = float(fit.fe_params.get("risk", 0.0) + random_slope)
        conditional_cov = np.asarray(fit.random_effects_cov.get(worker, np.full((2, 2), np.nan)), dtype=float); se = math.sqrt(max(0.0, float(conditional_cov[-1, -1]))) if conditional_cov.shape == (2, 2) and math.isfinite(float(conditional_cov[-1, -1])) else ""
        group = frame[frame.worker_id.astype(str) == str(worker)]; unpooled = smf.ols("quality ~ risk", group).fit().params.get("risk", np.nan) if len(group) > 2 and group.risk.nunique() > 1 else np.nan
        workers.append(role({"model_name": "M2", "worker_id": worker, "worker_specific_blup_slope": total, "random_slope_blup": random_slope, "interval_lower": total - 1.96 * se if se != "" else "", "interval_upper": total + 1.96 * se if se != "" else "", "conditional_slope_se": se, "unpooled_slope": float(unpooled) if math.isfinite(float(unpooled)) else "", "shrinkage": float(unpooled - total) if math.isfinite(float(unpooled)) else "", "status": summary["status"]}))
    return variance, workers


def specs(frame: pd.DataFrame) -> list[dict[str, str]]:
    common = "C(worker_id) + C(building_id) + C(stage)"
    result = [
        {"model_name": "M0", "formula": f"quality ~ {common}", "kind": "ols"},
        {"model_name": "M1", "formula": f"quality ~ {common} + risk", "kind": "ols"},
        {"model_name": "M2", "formula": "quality ~ C(building_id) + C(stage) + risk", "kind": "mixed"},
    ]
    for channel in CHANNELS:
        result.append({"model_name": f"M3_{channel}", "formula": f"quality ~ {common} + risk + {channel} + C(worker_id):{channel}", "kind": "ols", "channel": channel, "analysis_subrole": "exploratory_diagnostic_risk_vector_component"})
    result.extend([
        {"model_name": "worker_x_risk_diagnostic", "formula": f"quality ~ {common} + risk + C(worker_id):risk", "kind": "ols", "channel": "risk", "analysis_subrole": "exploratory_diagnostic"},
        {"model_name": "worker_x_stratum_diagnostic", "formula": f"quality ~ {common} + risk + C(worker_id):C(task_stratum)", "kind": "ols", "channel": "task_stratum", "analysis_subrole": "risk_bucket_diagnostic_not_independent_condition"},
    ])
    return result


def prediction(spec: dict[str, str], train: pd.DataFrame, test: pd.DataFrame) -> dict[str, Any]:
    summary, _, fit = fit_spec(spec, train)
    base_row = {"model_name": spec["model_name"], "status": summary["status"], "n_train": len(train), "n_test": len(test), "train_tasks": train.base_task_id.nunique(), "test_tasks": test.base_task_id.nunique(), "model_rank": summary["model_rank"], "condition_number": summary["condition_number"], "residual_df": summary["residual_df"], "new_worker_categories": len(set(test.worker_id) - set(train.worker_id)), "new_building_categories": len(set(test.building_id) - set(train.building_id)), "new_stage_categories": len(set(test.stage) - set(train.stage)), "new_stratum_categories": len(set(test.task_stratum) - set(train.task_stratum)), "rmse": "", "mae": "", "spearman": "", "prediction_interval_coverage": ""}
    if fit is None or summary["status"] not in {"estimated", "boundary_singular"}:
        return role(base_row)
    try:
        predicted = np.asarray(fit.predict(test), dtype=float); actual = test.quality.to_numpy(dtype=float); error = actual - predicted
        if spec["kind"] == "mixed":
            lower, upper = predicted - 1.96 * math.sqrt(float(fit.scale)), predicted + 1.96 * math.sqrt(float(fit.scale))
        else:
            interval = fit.get_prediction(test).summary_frame(alpha=.05); lower, upper = interval["obs_ci_lower"].to_numpy(), interval["obs_ci_upper"].to_numpy()
        base_row.update(status=summary["status"], rmse=float(np.sqrt(np.mean(error ** 2))), mae=float(np.mean(np.abs(error))), spearman=base.corr(actual.tolist(), predicted.tolist(), "spearman"), prediction_interval_coverage=float(np.mean((actual >= lower) & (actual <= upper))))
    except Exception as exc:
        base_row.update(status="not_predictable_new_category_or_design_failure", failure_reason=f"{type(exc).__name__}:{exc}")
    return role(base_row)


def validation(frame: pd.DataFrame, model_specs: list[dict[str, str]], output: Path) -> None:
    folds = [("C2B_to_Block1", frame[frame.stage == "C2B_C2-B"], frame[frame.stage == "C2A_RP_Block1"]), ("C2B_Block1_to_Block2", frame[frame.stage.isin(["C2B_C2-B", "C2A_RP_Block1"])], frame[frame.stage == "C2A_RP_Block2"])]
    rows = []
    for fold, train, test in folds:
        rows.extend(role({"validation_kind": "temporal", "fold": fold, **prediction(spec, train, test)}) for spec in model_specs)
    for unit, field in (("leave_one_building_out", "building_id"), ("leave_one_base_task_out", "base_task_id")):
        for value in sorted(frame[field].astype(str).unique()):
            train, test = frame[frame[field].astype(str) != value], frame[frame[field].astype(str) == value]
            rows.extend(role({"validation_kind": unit, "fold": value, **prediction(spec, train, test)}) for spec in model_specs)
    by_key = {(row["validation_kind"], row["fold"], row["model_name"]): row for row in rows}
    for row in rows:
        for reference in ("M0", "M1"):
            ref = by_key.get((row["validation_kind"], row["fold"], reference)); row[f"rmse_change_vs_{reference}"] = float(row["rmse"]) - float(ref["rmse"]) if ref and row["rmse"] != "" and ref["rmse"] != "" else ""
    base.write_csv(output / "conditional_validation_all_models.csv", rows)
    base.write_csv(output / "conditional_temporal_validation.csv", [row for row in rows if row["validation_kind"] == "temporal"])
    base.write_csv(output / "conditional_leave_building_out.csv", [row for row in rows if row["validation_kind"] == "leave_one_building_out"])
    base.write_csv(output / "conditional_leave_base_task_out.csv", [row for row in rows if row["validation_kind"] == "leave_one_base_task_out"])


def building_bootstrap_sensitivity(frame: pd.DataFrame, model_specs: list[dict[str, str]], output: Path) -> None:
    rng = random.Random(SEED); buildings = sorted(frame.building_id.astype(str).unique()); rows = []
    for spec in [item for item in model_specs if item["model_name"] == "M1" or item["model_name"].startswith("M3_")]:
        draws: dict[str, list[float]] = {}
        failures = 0
        for _ in range(BOOTSTRAP_REPLICATES):
            sample = pd.concat([frame[frame.building_id.astype(str) == rng.choice(buildings)] for _ in buildings], ignore_index=True)
            summary, coefficients, _ = fit_spec(spec, sample)
            if summary["status"] != "estimated":
                failures += 1; continue
            for coefficient in coefficients:
                if coefficient["term"] == "risk" or coefficient["term"] == spec.get("channel", ""):
                    draws.setdefault(coefficient["term"], []).append(float(coefficient["estimate"]))
        for term, values in draws.items():
            rows.append(role({"model_name": spec["model_name"], "term": term, "cluster_unit": "building", "requested": BOOTSTRAP_REPLICATES, "successful": len(values), "failed": failures, "median": float(np.median(values)), "ci_lower": float(np.quantile(values, .025)), "ci_upper": float(np.quantile(values, .975)), "seed": SEED, "status": "estimated" if values else "not_evaluable_no_successful_bootstrap"}))
    base.write_csv(output / "conditional_building_bootstrap_sensitivity.csv", rows)


def reference_sensitivity(inputs: dict[str, Path | list[Path]], output: Path) -> None:
    rows = base.csv_rows(inputs["risk"])  # type: ignore[arg-type]
    counts = Counter(base.clean(row.get("eligibility_status")) or "missing" for row in rows)
    report = [role({"row_type": "formal_denominator", "source_rows": len(rows), "formal_eligible_rows": counts["eligible"], "canonical_invalid_rows": counts["canonical_invalid"], "not_evaluable_rows": counts["not_evaluable"], "sensitivity_status": "not_evaluable_already_excluded_by_formal_eligibility", "reason": "formal 225-row model already excludes reference/canonical ineligible records"})]
    categories = Counter((base.clean(row.get("eligibility_status")), base.clean(row.get("ineligibility_reason"))) for row in rows)
    for (status, reason), excluded_rows in sorted(categories.items()):
        if status == "eligible":
            continue
        report.append(role({"row_type": "exclusion_category", "eligibility_status": status, "ineligibility_reason": reason or "unspecified", "excluded_rows": excluded_rows, "source_rows": len(rows), "formal_eligible_rows": counts["eligible"], "denominator_fraction": excluded_rows / len(rows), "sensitivity_status": "not_evaluable_already_excluded_by_formal_eligibility"}))
    base.write_csv(output / "reference_sensitivity_denominators.csv", report)


def stratum_diagnostics(frame: pd.DataFrame, output: Path) -> None:
    rows = []
    for stratum, group in frame.groupby("task_stratum"):
        rows.append(role({"stratum": stratum, "rows": len(group), "risk_min": float(group.risk.min()), "risk_max": float(group.risk.max()), "status": "risk_bucket_diagnostic_not_independent_condition", "reason": "stratum is frozen risk-score q75 bucket"}))
    base.write_csv(output / "risk_stratum_diagnostics.csv", rows)


def qgt_validation(inputs: dict[str, Path | list[Path]], frame: pd.DataFrame, output: Path) -> None:
    profile = base.csv_rows(inputs["profile"])  # type: ignore[arg-type]
    workers = [base.worker_id(row.get("worker_id")) for row in profile if base.number(row.get("Q_GT_EB")) is not None]
    adjusted = np.asarray([base.number(row.get("Q_GT_task_adjusted")) for row in profile if base.number(row.get("Q_GT_EB")) is not None], dtype=float)
    covariance = np.asarray([[json.loads(row["Q_GT_contrast_covariance_row_json"]).get(other, 0.0) for other in workers] for row in profile if base.number(row.get("Q_GT_EB")) is not None], dtype=float)
    covariance = (covariance + covariance.T) / 2; covariance += np.eye(len(workers)) * 1e-12
    ses = np.sqrt(np.diag(covariance)); rng = np.random.default_rng(SEED); draws = rng.multivariate_normal(adjusted, covariance, size=BOOTSTRAP_REPLICATES)
    ranks: dict[str, list[int]] = {worker: [] for worker in workers}
    for draw in draws:
        eb, _ = normal_normal_empirical_bayes(draw.tolist(), ses.tolist())
        ordered = sorted(zip(workers, (row["estimate"] for row in eb)), key=lambda item: (-item[1], item[0]))
        for index, (worker, _) in enumerate(ordered, 1): ranks[worker].append(index)
    table = []
    for worker, row in zip(workers, (item for item in profile if base.number(item.get("Q_GT_EB")) is not None)):
        values = ranks[worker]; frozen_rank = base.rank({base.worker_id(item.get("worker_id")): base.number(item.get("Q_GT_EB")) for item in profile if base.number(item.get("Q_GT_EB")) is not None})[worker]
        table.append(role({"worker_id": worker, "Q_GT_EB": base.number(row.get("Q_GT_EB")), "frozen_rank": frozen_rank, "rank_q025": float(np.quantile(values, .025)), "rank_q975": float(np.quantile(values, .975)), "rank_displacement_mean": float(np.mean(np.abs(np.asarray(values) - frozen_rank)),), "top3_membership_probability": float(np.mean(np.asarray(values) <= 3)), "top5_membership_probability": float(np.mean(np.asarray(values) <= 5)), "top10_membership_probability": float(np.mean(np.asarray(values) <= 10)), "boundary_worker": bool(np.quantile(values, .025) <= 5 <= np.quantile(values, .975)), "rank_distribution_source": "frozen_Q_GT_contrast_covariance_plus_official_EB_materializer"}))
    base.write_csv(output / "qgt_rank_stability.csv", table)
    ordering = [{"worker_left": left, "worker_right": right, "p_left_ranked_above_right": float(np.mean(np.asarray(ranks[left]) < np.asarray(ranks[right])))} for index, left in enumerate(workers) for right in workers[index + 1:]]
    base.write_json(output / "qgt_rank_bootstrap.json", role({"seed": SEED, "replicates": BOOTSTRAP_REPLICATES, "rank_statistic": "frozen_covariance_plus_official_normal_normal_EB", "pairwise_ordering": ordering, "leave_one_building_status": "not_evaluable_missing_frozen_cluster_delete_draws", "leave_one_task_status": "not_evaluable_missing_frozen_cluster_delete_draws"}))
    frozen = {base.worker_id(row.get("worker_id")): base.number(row.get("Q_GT_EB")) for row in profile if base.number(row.get("Q_GT_EB")) is not None}
    definitions = [role({"definition": f"top_{k}", "worker_id": worker, "member": worker in set(sorted(frozen, key=lambda key: (-frozen[key], key))[:k]), "source": "pre_Block2_frozen_Q_GT_EB", "status": "diagnostic_not_formal_tier"}) for k in (3, 5, 10) for worker in frozen]
    base.write_csv(output / "candidate_tier_definitions.csv", definitions)
    test = frame[frame.stage == "C2A_RP_Block2"].copy(); test["Q_GT_EB"] = test.worker_id.map(frozen)
    if len(test) and test.Q_GT_EB.notna().all():
        row = prediction({"model_name": "preblock2_QGT_profile", "formula": "quality ~ Q_GT_EB + risk + C(building_id)", "kind": "ols"}, frame[frame.stage.isin(["C2B_C2-B", "C2A_RP_Block1"])].assign(Q_GT_EB=lambda item: item.worker_id.map(frozen)).dropna(subset=["Q_GT_EB"]), test)
        base.write_csv(output / "qgt_block2_temporal_validation.csv", [role({"validation_target": "Block2_composition_adjusted_quality", "tier_role": "diagnostic_not_formal_tier", **row})])
    else:
        base.write_csv(output / "qgt_block2_temporal_validation.csv", [role({"validation_target": "Block2_composition_adjusted_quality", "status": "not_evaluable_missing_preblock2_profile_worker"})])


def run(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"v2 output already exists:{output}")
    inputs = base.load_inputs(); contract = json.loads(inputs["contract"].read_text(encoding="utf-8"))  # type: ignore[union-attr]
    if base.sha256_file(inputs["contract"]) != base.EXPECTED_CONTRACT_SHA or contract.get("contract_version") != base.EXPECTED_CONTRACT_VERSION:  # type: ignore[arg-type]
        raise RuntimeError("current method contract binding mismatch")
    output.mkdir(parents=True); sources = base.build_source_manifest(inputs, output, base.EXPECTED_CONTRACT_SHA)
    source_manifest = json.loads((output / "source_manifest.json").read_text(encoding="utf-8")); risk_contract = ROOT / "docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json"; source_manifest["inputs"].append(base.manifest_record("risk_design_contract", risk_contract, truth_level="generated_subordinate", role="frozen vector channel contract", formal_input=True, diagnostic_only=True, contract_sha=base.EXPECTED_CONTRACT_SHA)); base.write_json(output / "source_manifest.json", source_manifest)
    base.reconciliation(inputs, output); evidence, meta = base.build_long_evidence(inputs, output); evidence = enrich_c2_evidence(evidence, inputs, output); base.write_csv(output / "calibration_evidence_long.csv", evidence)
    base.identity_audit(evidence, output); base.write_csv(output / "worker_stage_profile.csv", base.profile_rows(evidence, inputs["profile"]))  # type: ignore[arg-type]
    base.write_csv(output / "task_feature_matrix.csv", base.task_matrix(evidence)); summary = base.quality_outputs(evidence, meta, output); base.posttask_diagnostics(meta, evidence, output); base.readiness(output)
    frame = pd.DataFrame([row for row in evidence if base.truth(row.get("risk_evidence_eligible")) and base.number(row.get("risk")) is not None and base.number(row.get("iou_to_reference")) is not None])
    frame["risk"] = pd.to_numeric(frame.risk); frame["quality"] = pd.to_numeric(frame.iou_to_reference); frame["stage"] = frame.apply(lambda row: base.analysis_stage(row.to_dict()), axis=1)
    for channel in CHANNELS: frame[channel] = pd.to_numeric(frame[channel])
    if len(frame) != 225 or not exact_duplicate_feature(frame, "risk_design_score_A"):
        raise ValueError("formal risk duplicate / eligible coverage audit failed")
    dictionary = [role({"feature": "risk_design_score_A", "coverage": len(frame), "qualified": False, "status": "not_evaluable_exact_duplicate_of_formal_risk", "reason": "exactly identical to formal risk"})] + [role({"feature": channel, "coverage": int(frame[channel].notna().sum()), "qualified": bool(frame[channel].nunique() > 1), "status": "qualified_exploratory_channel", "analysis_subrole": "exploratory_diagnostic_not_new_formal_profile"}) for channel in CHANNELS]
    base.write_csv(output / "conditional_feature_dictionary.csv", dictionary); reference_sensitivity(inputs, output); stratum_diagnostics(frame, output)
    summaries = []; coefficients = []; fits: dict[str, Any] = {}
    for spec in specs(frame):
        summary_row, coefficient_rows, fitted = fit_spec(spec, frame); summaries.append(summary_row); coefficients.extend(coefficient_rows); fits[spec["model_name"]] = fitted
    summaries.append(role({"model_name": "M3_risk_design_score_A", "status": "not_evaluable_exact_duplicate_of_formal_risk", "reason": "exact duplicate of formal risk; never entered same model", "analysis_subrole": "exploratory_diagnostic"}))
    base.write_csv(output / "conditional_model_summary.csv", summaries); base.write_csv(output / "conditional_model_coefficients.csv", coefficients)
    base.write_csv(output / "global_risk_models.csv", [next(row for row in summaries if row["model_name"] == "M1")])
    variance, blups = m2_details(next(row for row in summaries if row["model_name"] == "M2"), fits["M2"], frame); base.write_csv(output / "m2_variance_components.csv", variance); base.write_csv(output / "m2_worker_blup_slopes.csv", blups)
    failed = [row for row in summaries if row["status"] not in {"estimated", "boundary_singular", "not_evaluable_exact_duplicate_of_formal_risk"}]; base.write_json(output / "conditional_model_failures.json", role({"failed_models": failed}))
    model_specs = specs(frame); validation(frame, model_specs, output); building_bootstrap_sensitivity(frame, model_specs, output); qgt_validation(inputs, frame, output)
    report = "# Calibration 双线 v2 纠正计算报告\n\n- 角色：`exploratory_diagnostic_pre_stage3`。\n- `formal_profile_frozen=false`；`formal_policy_frozen=false`；`scientific_conclusion_prohibited=true`；`block3_generated=false`。\n- v1 保持只读；v2 直接消费冻结/原始输入。\n- 风险向量以 C2B contract 的四通道确定顺序解析，并通过正式生产工具 `_score` 回算。\n- `risk_design_score_A` 与 formal risk 完全重复，M3 score 已显式拒绝。\n- 所有 channel、stratum 与 tier 输出仅为 exploratory/diagnostic；不构成正式新画像、tier 或政策。\n"
    (output / "COMPUTATION_CORRECTION_REPORT.md").write_text(report, encoding="utf-8")
    outputs = [{"path": str(path.relative_to(output)), "sha256": base.sha256_file(path), "bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()]
    manifest = role({"schema_version": "calibration_dual_track_processing_v2", "method_contract_version": base.EXPECTED_CONTRACT_VERSION, "method_contract_sha256": base.EXPECTED_CONTRACT_SHA, "seed": SEED, "bootstrap_replicates": BOOTSTRAP_REPLICATES, "inputs": len(sources) + 1, "source_manifest_sha256": base.sha256_file(output / "source_manifest.json"), "outputs": outputs, "executed_commands": ["python tools/thesis_main/analysis/process_calibration_dual_track_v2.py --output-dir analysis_results/calibration_dual_track_processing_20260815_v2"], "warnings": ["C2A Block1 38->32 provenance difference retained unresolved", "no formal profile/policy/Stage3 artifact created"]})
    base.write_json(output / "analysis_manifest.json", manifest)
    return {"output_dir": str(output), "evidence_rows": len(evidence), "eligible_rows": len(frame), "outputs": len(outputs)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, required=True)
    print(json.dumps(run(parser.parse_args(argv).output_dir), ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
