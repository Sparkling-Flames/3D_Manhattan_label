"""Prediction-valid diagnostic-only Calibration processor (v3).

Consumes frozen/raw inputs, leaves v1/v2 untouched, and deliberately keeps
association models separate from deployable, train-fold-only predictions.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import warnings
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis import process_calibration_dual_track as base
from tools.thesis_main.analysis import process_calibration_dual_track_v2 as v2
from tools.thesis_main.analysis.c1_task_adjusted_quality import normal_normal_empirical_bayes


SEED = 20260815
BOOTSTRAP_REPLICATES = 1000
ROLE = {**v2.ROLE_FIELDS, "analysis_role": "exploratory_diagnostic_pre_stage3"}
CORE_SPECS = ("P0", "P1", "P2", *(f"P3_{channel}" for channel in v2.CHANNELS), "worker_x_risk_diagnostic", "worker_x_stratum_diagnostic")


def tagged(row: dict[str, Any]) -> dict[str, Any]:
    return {**ROLE, **row}


def prediction_specs() -> list[dict[str, str]]:
    """All formulas intentionally exclude C(stage) and C(building_id)."""
    rows = [
        {"model_name": "P0", "kind": "ols", "formula": "quality ~ C(worker_id)", "variant": "core"},
        {"model_name": "P1", "kind": "ols", "formula": "quality ~ C(worker_id) + risk_z", "variant": "core"},
        {"model_name": "P2", "kind": "mixed", "formula": "quality ~ risk_z", "variant": "core"},
    ]
    for channel in v2.CHANNELS:
        rows += [
            {"model_name": f"P3_{channel}", "kind": "ols", "formula": f"quality ~ C(worker_id) + risk_z + {channel}_z + C(worker_id):{channel}_z", "channel": channel, "variant": "raw_channel_exploratory"},
            {"model_name": f"P3_{channel}_residualized_sensitivity", "kind": "ols", "formula": f"quality ~ C(worker_id) + risk_z + {channel}_resid_z + C(worker_id):{channel}_resid_z", "channel": channel, "variant": "train_only_residualized_channel_sensitivity"},
        ]
    rows += [
        {"model_name": "worker_x_risk_diagnostic", "kind": "ols", "formula": "quality ~ C(worker_id) + risk_z + C(worker_id):risk_z", "variant": "diagnostic"},
        {"model_name": "worker_x_stratum_diagnostic", "kind": "ols", "formula": "quality ~ C(worker_id) + risk_z + C(worker_id):C(task_stratum)", "variant": "risk_bucket_diagnostic_not_independent_condition"},
    ]
    return rows


def train_transform(train: pd.DataFrame, test: pd.DataFrame, channel: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Fit all centering/scaling and channel residualization on train only."""
    tr, te = train.copy(), test.copy()
    fields = ["risk"] + ([channel] if channel else [])
    transform: dict[str, Any] = {"scaling_source": "train_fold_only", "fields": {}, "channel_residualization": {}}
    for field in fields:
        values = pd.to_numeric(tr[field], errors="coerce")
        mean, scale = float(values.mean()), float(values.std(ddof=0))
        if not math.isfinite(mean) or not math.isfinite(scale) or scale <= 0:
            raise ValueError(f"unusable_train_only_scaling:{field}")
        tr[f"{field}_z"] = (values - mean) / scale
        te[f"{field}_z"] = (pd.to_numeric(te[field], errors="coerce") - mean) / scale
        transform["fields"][field] = {"mean": mean, "scale": scale}
    if channel:
        x, y = tr["risk"].to_numpy(dtype=float), tr[channel].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        tr[f"{channel}_resid"] = tr[channel] - (intercept + slope * tr["risk"])
        te[f"{channel}_resid"] = te[channel] - (intercept + slope * te["risk"])
        rmean, rscale = float(tr[f"{channel}_resid"].mean()), float(tr[f"{channel}_resid"].std(ddof=0))
        if not math.isfinite(rscale) or rscale <= 0:
            raise ValueError(f"unusable_train_only_residualization:{channel}")
        tr[f"{channel}_resid_z"] = (tr[f"{channel}_resid"] - rmean) / rscale
        te[f"{channel}_resid_z"] = (te[f"{channel}_resid"] - rmean) / rscale
        transform["channel_residualization"] = {"channel": channel, "intercept": float(intercept), "risk_slope": float(slope), "residual_mean": rmean, "residual_scale": rscale, "fit_source": "train_fold_only"}
    return tr, te, transform


def design_diagnostics(formula: str, frame: pd.DataFrame) -> tuple[int, int, float]:
    matrix = smf.ols(formula, frame).exog
    rank, columns = int(np.linalg.matrix_rank(matrix)), int(matrix.shape[1])
    return rank, columns, float(np.linalg.cond(matrix)) if rank else math.inf


def _mixed_prediction(fit: Any, test: pd.DataFrame) -> tuple[np.ndarray, list[str], list[bool]]:
    """Statsmodels MixedLM.predict is fixed-only; add seen-worker BLUPs here."""
    fixed = np.asarray(fit.predict(test), dtype=float)
    values, source, fallback = [], [], []
    effects = fit.random_effects
    for index, (_, row) in enumerate(test.iterrows()):
        worker = str(row["worker_id"])
        if worker not in effects:
            values.append(fixed[index]); source.append("fixed_only_unseen_worker_fallback"); fallback.append(True); continue
        effect = np.asarray(effects[worker], dtype=float)
        values.append(fixed[index] + float(effect[0]) + float(effect[-1]) * float(row["risk_z"]))
        source.append("fixed_plus_worker_random_intercept_and_risk_slope_blup"); fallback.append(False)
    return np.asarray(values), source, fallback


def _interval(fit: Any, test: pd.DataFrame, predicted: np.ndarray, mixed: bool) -> tuple[np.ndarray, np.ndarray]:
    if mixed:
        width = 1.96 * math.sqrt(float(fit.scale)); return predicted - width, predicted + width
    interval = fit.get_prediction(test).summary_frame(alpha=.05)
    return interval["obs_ci_lower"].to_numpy(dtype=float), interval["obs_ci_upper"].to_numpy(dtype=float)


def _fit_predict(spec: dict[str, str], train: pd.DataFrame, test: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    channel = spec.get("channel")
    try:
        tr, te, transform = train_transform(train, test, channel)
        rank, columns, condition = design_diagnostics(spec["formula"], tr)
        common = {"model_name": spec["model_name"], "model_variant": spec["variant"], "formula": spec["formula"], "n_train": len(tr), "n_test": len(te), "train_workers": tr.worker_id.nunique(), "test_workers": te.worker_id.nunique(), "train_tasks": tr.base_task_id.nunique(), "test_tasks": te.base_task_id.nunique(), "train_buildings": tr.building_id.nunique(), "test_buildings": te.building_id.nunique(), "new_worker_categories": len(set(te.worker_id.astype(str)) - set(tr.worker_id.astype(str))), "new_building_categories": len(set(te.building_id.astype(str)) - set(tr.building_id.astype(str))), "new_stage_categories": len(set(te.stage.astype(str)) - set(tr.stage.astype(str))), "model_rank": rank, "design_columns": columns, "condition_number": condition, "transform_json": json.dumps(transform, sort_keys=True), "risk_channel_correlation_train": float(tr[["risk", channel]].corr().iloc[0, 1]) if channel else "", "analysis_role": ROLE["analysis_role"]}
        if rank < columns:
            return tagged({**common, "status": "not_evaluable_rank_deficient", "failure_reason": "train_design_matrix_rank_deficient"}), []
        if spec["kind"] == "mixed":
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                fit = smf.mixedlm(spec["formula"], tr, groups=tr.worker_id.astype(str), re_formula="1 + risk_z").fit(reml=True, method="lbfgs", maxiter=500, disp=False)
            covariance = np.asarray(fit.cov_re, dtype=float); boundary = v2.mixed_is_boundary(covariance)
            predicted, sources, fallback = _mixed_prediction(fit, te)
            model_status = "boundary_singular" if boundary else "estimated"
            extras = {"convergence": bool(fit.converged), "singular": boundary, "boundary": boundary, "optimizer": "lbfgs", "random_effect_eigenvalues_json": json.dumps(np.linalg.eigvalsh(covariance).tolist()), "warnings": ";".join(str(item.message) for item in caught)}
        else:
            fit = smf.ols(spec["formula"], tr).fit(); predicted = np.asarray(fit.predict(te), dtype=float)
            sources, fallback, model_status = ["fixed_effect_prediction"] * len(te), [False] * len(te), "estimated"
            extras = {"convergence": True, "singular": False, "boundary": False, "optimizer": "ols"}
        lower, upper = _interval(fit, te, predicted, spec["kind"] == "mixed")
        actual = te.quality.to_numpy(dtype=float); error = actual - predicted
        unstable = condition > 1e8
        status = "numerically_unstable_exploratory" if unstable else model_status
        summary = tagged({**common, **extras, "status": status, "mixed_model_status": model_status if spec["kind"] == "mixed" else "", "rmse": float(np.sqrt(np.mean(error ** 2))), "mae": float(np.mean(np.abs(error))), "spearman": base.corr(actual.tolist(), predicted.tolist(), "spearman"), "prediction_interval_coverage": float(np.mean((actual >= lower) & (actual <= upper))), "prediction_unseen_worker_fallback_rows": int(sum(fallback))})
        rows = [tagged({**common, "status": status, "canonical_submission_id": row.canonical_submission_id, "worker_id": str(row.worker_id), "base_task_id": row.base_task_id, "building_id": row.building_id, "stage": row.stage, "actual_quality": float(row.quality), "predicted_quality": float(predicted[index]), "prediction_interval_lower": float(lower[index]), "prediction_interval_upper": float(upper[index]), "prediction_source": sources[index], "unseen_worker_fixed_only_fallback": fallback[index]}) for index, (_, row) in enumerate(te.iterrows())]
        return summary, rows
    except Exception as exc:
        return tagged({"model_name": spec["model_name"], "model_variant": spec["variant"], "status": "failed", "failure_reason": f"{type(exc).__name__}:{exc}", "n_train": len(train), "n_test": len(test)}), []


def _folds(frame: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame, pd.DataFrame]]:
    result = [("temporal", "C2B_to_Block1", frame[frame.stage == "C2B_C2-B"], frame[frame.stage == "C2A_RP_Block1"]), ("temporal", "C2B_Block1_to_Block2", frame[frame.stage.isin(["C2B_C2-B", "C2A_RP_Block1"])], frame[frame.stage == "C2A_RP_Block2"])]
    for kind, field in (("leave_one_building_out", "building_id"), ("leave_one_base_task_out", "base_task_id")):
        for value in sorted(frame[field].astype(str).unique()):
            result.append((kind, value, frame[frame[field].astype(str) != value], frame[frame[field].astype(str) == value]))
    return result


def conditional_validation(frame: pd.DataFrame, output: Path) -> pd.DataFrame:
    summaries: list[dict[str, Any]] = []; predictions: list[dict[str, Any]] = []
    for kind, fold, train, test in _folds(frame):
        for spec in prediction_specs():
            summary, rows = _fit_predict(spec, train, test)
            summary.update(validation_kind=kind, fold=fold); summaries.append(summary)
            for row in rows: row.update(validation_kind=kind, fold=fold)
            predictions.extend(rows)
    by_key = {(row["validation_kind"], row["fold"], row["model_name"]): row for row in summaries}
    for row in summaries:
        for reference in ("P0", "P1"):
            other = by_key.get((row["validation_kind"], row["fold"], reference))
            row[f"rmse_change_vs_{reference}"] = row["rmse"] - other["rmse"] if other and isinstance(row.get("rmse"), float) and isinstance(other.get("rmse"), float) else ""
            row[f"mae_change_vs_{reference}"] = row["mae"] - other["mae"] if other and isinstance(row.get("mae"), float) and isinstance(other.get("mae"), float) else ""
    base.write_csv(output / "conditional_validation_all_models.csv", summaries)
    base.write_csv(output / "conditional_temporal_validation.csv", [row for row in summaries if row["validation_kind"] == "temporal"])
    base.write_csv(output / "conditional_leave_building_out.csv", [row for row in summaries if row["validation_kind"] == "leave_one_building_out"])
    base.write_csv(output / "conditional_leave_base_task_out.csv", [row for row in summaries if row["validation_kind"] == "leave_one_base_task_out"])
    base.write_csv(output / "conditional_out_of_fold_predictions.csv", predictions)
    pooled = []
    pred_frame = pd.DataFrame(predictions)
    for (kind, name), group in pred_frame.groupby(["validation_kind", "model_name"]):
        actual, predicted = group.actual_quality.to_numpy(dtype=float), group.predicted_quality.to_numpy(dtype=float)
        fold_rows = [row for row in summaries if row["validation_kind"] == kind and row["model_name"] == name]
        pooled.append(tagged({"validation_kind": kind, "model_name": name, "model_variant": group.model_variant.iloc[0], "successful_folds": sum(row["status"] != "failed" for row in fold_rows), "failed_folds": sum(row["status"] == "failed" for row in fold_rows), "pooled_out_of_fold_rows": len(group), "pooled_rmse": float(np.sqrt(np.mean((actual-predicted)**2)),), "pooled_mae": float(np.mean(np.abs(actual-predicted))), "pooled_spearman": base.corr(actual.tolist(), predicted.tolist(), "spearman"), "pooled_interval_coverage": float(np.mean((actual >= group.prediction_interval_lower.to_numpy()) & (actual <= group.prediction_interval_upper.to_numpy()))) }))
    base.write_csv(output / "conditional_validation_summary.csv", pooled)
    return pred_frame


def _metric_bootstrap(predictions: pd.DataFrame, output: Path) -> None:
    """Cluster-resample LOTO out-of-fold predictions; no fitted result is promoted."""
    source = predictions[predictions.validation_kind == "leave_one_base_task_out"].copy(); rng = random.Random(SEED); rows = []
    for unit in ("building_id", "base_task_id", "worker_id"):
        units = sorted(source[unit].astype(str).unique())
        for model, group in source[source.model_name.isin(CORE_SPECS)].groupby("model_name"):
            draw_values: list[float] = []; failures = 0
            # This resamples already out-of-fold errors, not fitted models.
            # ponytail: metric bootstrap only; refit bootstrap belongs in a future estimand-specific analysis.
            groups = {key: ((group[group[unit].astype(str) == key].actual_quality - group[group[unit].astype(str) == key].predicted_quality).to_numpy(dtype=float)) for key in units}
            for _ in range(BOOTSTRAP_REPLICATES):
                errors = np.concatenate([groups[rng.choice(units)] for _ in units])
                if not len(errors): failures += 1; continue
                draw_values.append(float(np.sqrt(np.mean(errors ** 2))))
            rows.append(tagged({"model_name": model, "cluster_unit": unit, "metric": "out_of_fold_rmse", "requested_replicates": BOOTSTRAP_REPLICATES, "successful_replicates": len(draw_values), "failed_replicates": failures, "seed": SEED, "ci_lower": float(np.quantile(draw_values, .025)), "ci_upper": float(np.quantile(draw_values, .975)), "resampling_scope": "leave_one_base_task_out_predictions"}))
    base.write_csv(output / "conditional_cluster_bootstrap_sensitivity.csv", rows)


def qgt_validation(inputs: dict[str, Path | list[Path]], frame: pd.DataFrame, output: Path) -> None:
    profile = [row for row in base.csv_rows(inputs["profile"]) if base.number(row.get("Q_GT_EB")) is not None]  # type: ignore[arg-type]
    values = {base.worker_id(row.get("worker_id")): float(base.number(row.get("Q_GT_EB"))) for row in profile}
    workers = list(values); adjusted = np.asarray([base.number(row.get("Q_GT_task_adjusted")) for row in profile], dtype=float)
    covariance = np.asarray([[json.loads(row["Q_GT_contrast_covariance_row_json"]).get(other, 0.0) for other in workers] for row in profile], dtype=float); covariance = (covariance + covariance.T)/2 + np.eye(len(workers))*1e-12
    ses = np.sqrt(np.diag(covariance)); draws = np.random.default_rng(SEED).multivariate_normal(adjusted, covariance, size=BOOTSTRAP_REPLICATES)
    ranks = defaultdict(list)
    for draw in draws:
        eb, _ = normal_normal_empirical_bayes(draw.tolist(), ses.tolist())
        for rank, (worker, _) in enumerate(sorted(zip(workers, (item["estimate"] for item in eb)), key=lambda item: (-item[1], item[0])), 1): ranks[worker].append(rank)
    base.write_json(output / "qgt_rank_bootstrap.json", tagged({"seed": SEED, "replicates": BOOTSTRAP_REPLICATES, "producer": "frozen_covariance_plus_official_normal_normal_empirical_bayes", "rank_distribution": {worker: values_ for worker, values_ in ranks.items()}}))
    train = frame[frame.stage.isin(["C2B_C2-B", "C2A_RP_Block1"])].copy(); test = frame[frame.stage == "C2A_RP_Block2"].copy()
    train["qgt"] = train.worker_id.astype(str).map(values); test["qgt"] = test.worker_id.astype(str).map(values)
    if train.qgt.isna().any() or test.qgt.isna().any():
        raise ValueError("missing pre_Block2 frozen Q_GT worker")
    qmean, qscale = float(train.qgt.mean()), float(train.qgt.std(ddof=0)); rmean, rscale = float(train.risk.mean()), float(train.risk.std(ddof=0))
    for data in (train, test): data["qgt_z"] = (data.qgt-qmean)/qscale; data["risk_z"] = (data.risk-rmean)/rscale
    results = []
    for name, formula in (("baseline_risk_deployable_composition", "quality ~ risk_z"), ("continuous_Q_GT_EB", "quality ~ risk_z + qgt_z")):
        fit = smf.ols(formula, train).fit(); pred = fit.predict(test).to_numpy(); actual = test.quality.to_numpy(); results.append(tagged({"model_name": name, "formula": formula, "deployment_building_id": "not_used", "train_only_qgt_scaling": json.dumps({"mean":qmean,"scale":qscale}), "rows":len(test), "workers":test.worker_id.nunique(), "rmse":float(np.sqrt(np.mean((actual-pred)**2))), "mae":float(np.mean(np.abs(actual-pred))), "spearman":base.corr(actual.tolist(), pred.tolist(), "spearman")}))
    baseline = results[0]
    results[1]["rmse_change_vs_baseline"] = results[1]["rmse"]-baseline["rmse"]; results[1]["mae_change_vs_baseline"] = results[1]["mae"]-baseline["mae"]
    base.write_csv(output / "qgt_block2_temporal_validation.csv", results)
    tiers, support = [], []
    for k in (3, 5, 10):
        top = set(sorted(values, key=lambda worker: (-values[worker], worker))[:k]); train["tier"] = train.worker_id.astype(str).isin(top).astype(int); test["tier"] = test.worker_id.astype(str).isin(top).astype(int)
        fit = smf.ols("quality ~ risk_z + tier", train).fit(); pred = fit.predict(test).to_numpy(); actual = test.quality.to_numpy()
        tiers.append(tagged({"model_name": f"top_{k}_indicator", "k_predefined_before_Block2": k, "formula":"quality ~ risk_z + tier", "deployment_building_id":"not_used", "rmse":float(np.sqrt(np.mean((actual-pred)**2))), "mae":float(np.mean(np.abs(actual-pred))), "spearman":base.corr(actual.tolist(), pred.tolist(), "spearman"), "rmse_change_vs_baseline":float(np.sqrt(np.mean((actual-pred)**2)))-baseline["rmse"], "mae_change_vs_baseline":float(np.mean(np.abs(actual-pred)))-baseline["mae"], "role":"diagnostic_not_formal_tier"}))
        for value, group in test.groupby("tier"):
            support.append(tagged({"k":k, "tier_member":bool(value), "actual_workers":group.worker_id.nunique(), "actual_rows":len(group), "source":"pre_Block2_frozen_Q_GT_EB"}))
    base.write_csv(output / "tier_block2_temporal_validation.csv", tiers); base.write_csv(output / "tier_block2_support.csv", support)


def run(output: Path) -> dict[str, Any]:
    if output.exists(): raise FileExistsError(f"v3 output exists:{output}")
    inputs = base.load_inputs(); contract = json.loads(inputs["contract"].read_text(encoding="utf-8"))  # type: ignore[union-attr]
    if contract.get("contract_version") != base.EXPECTED_CONTRACT_VERSION or base.sha256_file(inputs["contract"]) != base.EXPECTED_CONTRACT_SHA: raise RuntimeError("method contract mismatch")  # type: ignore[arg-type]
    output.mkdir(parents=True); sources = base.build_source_manifest(inputs, output, base.EXPECTED_CONTRACT_SHA)
    source_manifest = json.loads((output / "source_manifest.json").read_text(encoding="utf-8")); source_manifest["inputs"].append(base.manifest_record("risk_design_contract", ROOT / "docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json", truth_level="generated_subordinate", role="frozen vector contract", formal_input=True, diagnostic_only=True, contract_sha=base.EXPECTED_CONTRACT_SHA)); base.write_json(output / "source_manifest.json", source_manifest)
    base.reconciliation(inputs, output); evidence, meta = base.build_long_evidence(inputs, output); evidence = v2.enrich_c2_evidence(evidence, inputs, output); base.write_csv(output / "calibration_evidence_long.csv", evidence); base.identity_audit(evidence, output); base.write_csv(output / "worker_stage_profile.csv", base.profile_rows(evidence, inputs["profile"]))  # type: ignore[arg-type]
    base.write_csv(output / "task_feature_matrix.csv", base.task_matrix(evidence)); base.quality_outputs(evidence, meta, output); base.posttask_diagnostics(meta, evidence, output); base.readiness(output)
    frame = pd.DataFrame([row for row in evidence if base.truth(row.get("risk_evidence_eligible")) and base.number(row.get("risk")) is not None and base.number(row.get("iou_to_reference")) is not None])
    frame["risk"] = pd.to_numeric(frame.risk); frame["quality"] = pd.to_numeric(frame.iou_to_reference); frame["stage"] = frame.apply(lambda row: base.analysis_stage(row.to_dict()), axis=1)
    for channel in v2.CHANNELS: frame[channel] = pd.to_numeric(frame[channel])
    if len(frame) != 225 or not v2.exact_duplicate_feature(frame, "risk_design_score_A"): raise ValueError("eligible vector/risk duplicate audit failed")
    v2.reference_sensitivity(inputs, output); v2.stratum_diagnostics(frame, output)
    associations=[]; coefficients=[]; fits={}
    for spec in v2.specs(frame):
        summary, coef, fit = v2.fit_spec(spec, frame); associations.append(summary); coefficients += coef; fits[spec["model_name"]]=fit
    associations.append(tagged({"model_name":"M3_risk_design_score_A","status":"not_evaluable_exact_duplicate_of_formal_risk","reason":"exact duplicate of formal risk; rejected from same model"}))
    base.write_csv(output / "conditional_model_summary.csv", associations); base.write_csv(output / "conditional_model_coefficients.csv", coefficients); base.write_csv(output / "global_risk_models.csv", [next(row for row in associations if row["model_name"]=="M1")]); variance, blups=v2.m2_details(next(row for row in associations if row["model_name"]=="M2"), fits["M2"], frame); base.write_csv(output / "m2_variance_components.csv", variance); base.write_csv(output / "m2_worker_blup_slopes.csv", blups)
    pred = conditional_validation(frame, output); _metric_bootstrap(pred, output); qgt_validation(inputs, frame, output)
    report = "# Calibration 双线 v3 计算验证报告\n\n- 角色：`exploratory_diagnostic_pre_stage3`。\n- 关联推断模型保留 building/stage fixed effects；预测模型不含测试不可识别的 stage/building 类别。\n- 所有中心化、标准化和 channel residualization 均在训练折拟合。\n- P2 对已见 worker 显式使用 BLUP intercept 与 risk slope；新 worker 才回退 fixed-only。\n- Bootstrap 均为固定 seed 的 1,000 次诊断。\n- 不生成正式 profile/policy freeze 或 Block 3。\n"
    (output / "COMPUTATION_VALIDATION_REPORT.md").write_text(report, encoding="utf-8")
    outputs=[{"path":str(path.relative_to(output)),"sha256":base.sha256_file(path),"bytes":path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()]
    base.write_json(output / "analysis_manifest.json", tagged({"schema_version":"calibration_dual_track_processing_v3","method_contract_version":base.EXPECTED_CONTRACT_VERSION,"method_contract_sha256":base.EXPECTED_CONTRACT_SHA,"seed":SEED,"bootstrap_replicates":BOOTSTRAP_REPLICATES,"inputs":len(sources)+1,"source_manifest_sha256":base.sha256_file(output / "source_manifest.json"),"outputs":outputs,"executed_commands":["python tools/thesis_main/analysis/process_calibration_dual_track_v3.py --output-dir analysis_results/calibration_dual_track_processing_20260815_v3"],"warnings":["C2A Block1 38->32 provenance difference retained unresolved","no scientific conclusion, policy selection, formal profile/policy freeze, or Block3"]}))
    return {"output_dir":str(output),"eligible_rows":len(frame),"prediction_rows":len(pred)}


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--output-dir",type=Path,required=True); args=parser.parse_args(argv); print(json.dumps(run(args.output_dir),ensure_ascii=False,indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
