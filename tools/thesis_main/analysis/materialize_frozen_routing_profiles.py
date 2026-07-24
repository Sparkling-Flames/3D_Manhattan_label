"""Produce frozen Strong Global and validated Full component tables from calibration artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from statistics import NormalDist
from typing import Any

import pandas as pd
import statsmodels.formula.api as smf


MODEL_VERSION = "two_way_worker_task_fe_task_cluster_v2"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_global(
    submissions: list[dict[str, str]], worker_state: list[dict[str, str]], *, profile_version: str,
    estimator: dict[str, Any] | None = None, input_status: str = "dry_run",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    usable = [
        row for row in submissions
        if row.get("quality_evaluable", "").lower() in {"true", "1"}
        and row.get("condition", "").lower() == "manual"
    ]
    if not usable:
        raise ValueError("no evaluable Manual GT submissions")
    frame = pd.DataFrame(usable).copy()
    for field in ("worker_id", "task_id"):
        if frame[field].fillna("").astype(str).eq("").any():
            raise ValueError(f"evaluable Manual rows require {field}")
        frame[field] = frame[field].astype(str)
    frame["iou_to_gt"] = pd.to_numeric(frame["iou_to_gt"], errors="raise")
    if frame.worker_id.nunique() < 2 or frame.task_id.nunique() < 2:
        raise ValueError("task-adjusted Global requires at least two workers and two tasks")
    formula = "iou_to_gt ~ C(worker_id) + C(task_id)"
    fitted = smf.ols(formula, frame).fit(
        cov_type="cluster", cov_kwds={"groups": frame["task_id"], "use_correction": True}
    )
    workers = sorted(frame.worker_id.unique())
    reference = frame.copy()
    adjusted: dict[str, float] = {}
    adjusted_se: dict[str, float] = {}
    design_info = fitted.model.data.design_info
    from patsy import build_design_matrices
    for worker in workers:
        reference["worker_id"] = worker
        matrix = build_design_matrices([design_info], reference, return_type="dataframe")[0]
        contrast = matrix.mean(axis=0).to_numpy()
        adjusted[worker] = float(contrast @ fitted.params.to_numpy())
        adjusted_se[worker] = float((contrast @ fitted.cov_params().to_numpy() @ contrast) ** .5)
    task_mean = frame.groupby("task_id")["iou_to_gt"].mean().to_dict()
    grand = float(frame["iou_to_gt"].mean())
    centered: dict[str, list[float]] = defaultdict(list)
    for row in frame.to_dict("records"):
        centered[row["worker_id"]].append(float(row["iou_to_gt"]) - task_mean[row["task_id"]] + grand)
    config = estimator or {}
    confidence = float(config.get("confidence_level", .95))
    if not 0 < confidence < 1:
        raise ValueError("confidence_level must be between zero and one")
    z = NormalDist().inv_cdf((1 + confidence) / 2)
    min_gt = int(config.get("min_gt_support", 1))
    min_tasks = int(config.get("min_task_support", 1))
    max_struct = float(config.get("max_f_struct", float("inf")))
    quality_floor = float(config.get("quality_lcb_floor", float("-inf")))
    states = {row["worker_id"]: row for row in worker_state}
    output = []
    for worker in workers:
        state = states.get(worker, {})
        estimate, se = adjusted[worker], adjusted_se[worker]
        lower, upper = estimate - z * se, estimate + z * se
        process, independence = _truth(state.get("process_eligible")), _truth(state.get("independence_eligible"))
        reference_ok = _truth(state.get("reference_evaluable", "true"))
        struct = _number(state.get("F_struct"))
        subset = frame[frame.worker_id == worker]
        support, task_support = len(subset), subset.task_id.nunique()
        groups = subset.get("dataset_group", pd.Series([], dtype=str)).astype(str) if "dataset_group" in subset else pd.Series([], dtype=str)
        gates = {
            "process": process,
            "independence": independence,
            "minimum_gt_support": support >= min_gt,
            "minimum_task_support": task_support >= min_tasks,
            "reference_evaluable": reference_ok,
            "structural_failure": struct is not None and struct <= max_struct,
            "quality_lcb": lower >= quality_floor,
        }
        eligible = all(gates.values())
        output.append({
            "worker_id": worker, "Q_GT_raw": float(subset.iou_to_gt.mean()),
            "Q_GT_task_adjusted": estimate, "Q_GT_standard_error": se,
            "Q_GT_CI_lower": lower, "Q_GT_CI_upper": upper, "Q_GT_LCB": lower,
            "Q_GT_centering_sensitivity": fmean(centered[worker]),
            "R_LOO_compatible": state.get("R_LOO_compatible", ""),
            "F_struct": "" if struct is None else struct, "GT_support": support,
            "task_support": task_support,
            "anchor_support": int(groups.str.contains("anchor", case=False).sum()),
            "core_support": int(groups.str.contains("core", case=False).sum()),
            "LOO_support": state.get("LOO_support", ""),
            "process_eligible": process, "independence_eligible": independence,
            "reference_evaluable": reference_ok,
            "global_eligible": eligible, "exclusion_reason": "" if eligible else ";".join(name for name, passed in gates.items() if not passed),
            "model_version": MODEL_VERSION,
            "profile_version": profile_version,
        })
    ranked = sorted(
        (row for row in output if row["global_eligible"] or input_status != "formal"),
        key=lambda row: (-float(row["Q_GT_LCB"]), row["worker_id"]),
    )
    ranks = {row["worker_id"]: index + 1 for index, row in enumerate(ranked)}
    for row in output:
        row["global_rank"] = ranks.get(row["worker_id"], "") if input_status == "formal" else ""
        row["provisional_rank"] = ranks.get(row["worker_id"], "") if input_status != "formal" else ""
    task_rows = [{"task_id": task, "task_fixed_effect": task_mean[task] - grand, "model_version": MODEL_VERSION} for task in sorted(task_mean)]
    audit = {
        "model_version": MODEL_VERSION, "formula": formula, "covariance": "task_cluster_robust",
        "same_task_rows_independent": False, "n_rows": len(frame), "n_workers": len(workers),
        "n_tasks": frame.task_id.nunique(),
        "confidence_level": confidence, "normal_quantile": z,
        "optional_context_adjustment": "absorbed_by_task_fixed_effect",
    }
    return output, task_rows, audit


def build_full_components(rows: list[dict[str, str]], *, profile_version: str) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        gates = {
            "p1_integrity": row.get("p1_integrity_eligible", "").lower() in {"true", "1"},
            "c1_predictive": row.get("c1_predictive_validated", "").lower() in {"true", "1"},
            "c2b_confirmed": row.get("c2b_confirmed", "").lower() in {"true", "1"},
            "direction": row.get("direction_consistent", "").lower() in {"true", "1"},
            "loo_task": row.get("leave_one_task_out_stable", "").lower() in {"true", "1"},
            "loo_block": row.get("leave_one_block_out_stable", "").lower() in {"true", "1"},
            "activation": row.get("routing_activation_allowed", "").lower() in {"true", "1"},
        }
        enabled = all(gates.values())
        output.append({
            **row,
            "evidence_stage": "validated_routing_component" if enabled else "predictive_or_diagnostic_only",
            "full_component_eligible": enabled,
            "disable_reason": "" if enabled else ";".join(name for name, passed in gates.items() if not passed),
            "profile_version": profile_version,
        })
    return output


def materialize(
    submissions_csv: Path, worker_state_csv: Path, component_evidence_csv: Path,
    freeze_manifest: Path, output_dir: Path, *, input_status: str = "dry_run",
) -> dict[str, Any]:
    manifest = json.loads(freeze_manifest.read_text(encoding="utf-8"))
    expected = manifest.get("input_sha256") or {}
    inputs = {
        "submissions_csv": submissions_csv,
        "worker_state_csv": worker_state_csv,
        "component_evidence_csv": component_evidence_csv,
    }
    for name, path in inputs.items():
        if expected.get(name) != _sha(path):
            raise ValueError(f"stale_or_unbound:{name}")
    version = str(manifest["profile_version"])
    estimator = manifest.get("global_estimator") or {}
    required_gates = {"min_gt_support", "min_task_support", "max_f_struct", "quality_lcb_floor", "confidence_level", "min_global_eligible_workers"}
    if input_status == "formal" and not required_gates.issubset(estimator):
        raise ValueError("formal Strong Global requires frozen estimator gates")
    global_rows, task_rows, model_audit = build_global(
        _read(submissions_csv), _read(worker_state_csv), profile_version=version,
        estimator=estimator, input_status=input_status,
    )
    components = build_full_components(_read(component_evidence_csv), profile_version=version)
    _write(output_dir / "strong_global_worker_table.csv", global_rows)
    _write(output_dir / "strong_global_task_effects.csv", task_rows)
    _write(output_dir / "full_component_table.csv", components)
    summary = {
        "profile_version": version,
        "freeze_manifest_sha256": _sha(freeze_manifest),
        "input_sha256": {name: _sha(path) for name, path in inputs.items()},
        "n_global_eligible": sum(bool(row["global_eligible"]) for row in global_rows),
        "n_full_components": sum(bool(row["full_component_eligible"]) for row in components),
        "input_status": input_status,
        "model_audit": model_audit,
        "formal_ready": input_status == "formal" and sum(bool(row["global_eligible"]) for row in global_rows) >= int(estimator["min_global_eligible_workers"]),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "routing_profile_freeze_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--submissions-csv", type=Path, required=True)
    parser.add_argument("--worker-state-csv", type=Path, required=True)
    parser.add_argument("--component-evidence-csv", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-status", choices=("dry_run", "precloseout_rehearsal", "formal"), default="dry_run")
    args = parser.parse_args()
    print(json.dumps(materialize(
        args.submissions_csv, args.worker_state_csv, args.component_evidence_csv,
        args.freeze_manifest, args.output_dir, input_status=args.input_status,
    ), indent=2))


if __name__ == "__main__":
    main()
