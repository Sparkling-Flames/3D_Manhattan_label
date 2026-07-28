"""Produce frozen Strong Global and validated Full component tables from calibration artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_task_adjusted_quality import MODEL_VERSION, estimate_task_adjusted_qgt


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
    config = estimator or {}
    evidence_rows, task_rows, audit = estimate_task_adjusted_qgt(submissions, estimator_contract=config)
    min_gt = int(config.get("min_gt_support", 1))
    min_tasks = int(config.get("min_task_support", 1))
    max_struct = float(config.get("max_f_struct", float("inf")))
    quality_floor = float(config.get("quality_lcb_floor", float("-inf")))
    states = {row["worker_id"]: row for row in worker_state}
    output = []
    for evidence in evidence_rows:
        worker = evidence["worker_id"]
        state = states.get(worker, {})
        process, independence = _truth(state.get("process_eligible")), _truth(state.get("independence_eligible"))
        reference_ok = _truth(state.get("reference_evaluable", "true"))
        struct = _number(state.get("F_struct"))
        support, task_support = int(evidence["GT_support"]), int(evidence["task_support"])
        subset = [row for row in submissions if str(row.get("worker_id", "")) == worker and str(row.get("condition", "")).lower() == "manual"]
        gates = {
            "process": process,
            "independence": independence,
            "minimum_gt_support": support >= min_gt,
            "minimum_task_support": task_support >= min_tasks,
            "reference_evaluable": reference_ok,
            "structural_failure": struct is not None and struct <= max_struct,
            "quality_eb": float(evidence["Q_GT_EB"]) >= quality_floor,
        }
        eligible = all(gates.values())
        output.append({
            **evidence,
            "R_peer_median": state.get("R_peer_median", ""), "R_LOO_medoid": state.get("R_LOO_medoid", ""),
            "R_LOO_compatible": state.get("R_LOO_compatible", ""),
            "F_struct": "" if struct is None else struct, "GT_support": support,
            "task_support": task_support,
            "anchor_support": sum("anchor" in str(row.get("dataset_group", "")).lower() for row in subset),
            "core_support": sum("core" in str(row.get("dataset_group", "")).lower() for row in subset),
            "LOO_support": state.get("LOO_support", ""),
            "process_eligible": process, "independence_eligible": independence,
            "reference_evaluable": reference_ok,
            "global_eligible": eligible, "exclusion_reason": "" if eligible else ";".join(name for name, passed in gates.items() if not passed),
            "profile_version": profile_version,
        })
    ranked = sorted(
        (row for row in output if row["global_eligible"] or input_status != "formal"),
        key=lambda row: (-float(row["Q_GT_EB"]), -float(row.get("R_LOO_medoid") or -1), -float(row.get("R_peer_median") or -1), row["worker_id"]),
    )
    ranks = {row["worker_id"]: index + 1 for index, row in enumerate(ranked)}
    for row in output:
        row["global_rank_EB"] = ranks.get(row["worker_id"], "") if input_status == "formal" else ""
        row["global_rank"] = row["global_rank_EB"]
        row["provisional_rank"] = ranks.get(row["worker_id"], "") if input_status != "formal" else ""
    audit = {**audit, "ranking_materialized": input_status == "formal", "ranking_owner": "routing_profile_freeze"}
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
    global_thresholds_path = Path("docs/thesis_main/GLOBAL_POLICY_THRESHOLDS.json")
    global_thresholds = json.loads(global_thresholds_path.read_text(encoding="utf-8"))
    if input_status == "formal" and not (
        global_thresholds.get("status") == "approved"
        and global_thresholds.get("interpretation_allowed") is True
        and global_thresholds.get("approved_by") and global_thresholds.get("approved_at")
    ):
        raise ValueError("candidate GLOBAL_POLICY_THRESHOLDS cannot produce formal routing profile")
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
        "global_policy_threshold_manifest_sha256": _sha(global_thresholds_path),
        "formal_ready": input_status == "formal" and model_audit.get("eb_model_status") == "estimated" and sum(bool(row["global_eligible"]) for row in global_rows) >= int(estimator["min_global_eligible_workers"]),
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
