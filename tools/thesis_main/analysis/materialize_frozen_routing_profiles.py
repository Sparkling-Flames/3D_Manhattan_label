"""Produce frozen Strong Global and validated Full component tables from calibration artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_task_adjusted_quality import MODEL_VERSION, estimate_task_adjusted_qgt
from tools.thesis_main.analysis.materialize_global_policy import build_global_policy


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
    approval_manifest: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    config = estimator or {}
    evidence_rows, task_rows, audit = estimate_task_adjusted_qgt(submissions, estimator_contract=config)
    min_gt = int(config.get("min_gt_support", 1))
    min_tasks = int(config.get("min_task_support", 1))
    max_struct = float(config.get("max_f_struct", float("inf")))
    quality_floor = float(config.get("quality_lcb_floor", float("-inf")))
    states = {row["worker_id"]: row for row in worker_state}
    candidates = []
    for evidence in evidence_rows:
        worker = evidence["worker_id"]
        state = states.get(worker, {})
        process, independence = _truth(state.get("process_eligible")), _truth(state.get("independence_eligible"))
        reference_ok = _truth(state.get("reference_evaluable"))
        administratively_eligible = _truth(state.get("administratively_eligible"))
        q_gt_estimable = _truth(state.get("Q_GT_estimable"))
        struct_raw = _number(state.get("F_struct_raw"))
        if struct_raw is None:
            struct_raw = _number(state.get("F_struct"))
        struct_eb = _number(state.get("F_struct_EB"))
        interval_lower = _number(state.get("F_struct_interval_lower"))
        interval_upper = _number(state.get("F_struct_interval_upper"))
        support, task_support = int(evidence["GT_support"]), int(evidence["task_support"])
        subset = [row for row in submissions if str(row.get("worker_id", "")) == worker and str(row.get("condition", "")).lower() == "manual"]
        candidates.append({
            **evidence,
            "R_peer_median": state.get("R_peer_median", ""), "R_LOO_medoid": state.get("R_LOO_medoid", ""),
            "R_LOO_compatible": state.get("R_LOO_compatible", ""),
            "F_struct": "" if struct_raw is None else struct_raw,
            "F_struct_raw": "" if struct_raw is None else struct_raw,
            "F_struct_EB": "" if struct_eb is None else struct_eb,
            "F_struct_interval_lower": "" if interval_lower is None else interval_lower,
            "F_struct_interval_upper": "" if interval_upper is None else interval_upper,
            "GT_support": support, "Q_GT_support": support,
            "task_support": task_support,
            "building_support": evidence.get("building_support", state.get("building_support", 0)),
            "anchor_support": sum("anchor" in str(row.get("dataset_group", "")).lower() for row in subset),
            "core_support": sum("core" in str(row.get("dataset_group", "")).lower() for row in subset),
            "LOO_support": state.get("LOO_support", ""),
            "R_peer_stable": state.get("R_peer_stable", ""),
            "R_LOO_medoid": state.get("R_LOO_medoid") or state.get("R_LOO_compatible", ""),
            "process_eligible": process, "independence_eligible": independence,
            "reference_evaluable": reference_ok,
            "administratively_eligible": administratively_eligible,
            "Q_GT_estimable": q_gt_estimable,
            "serious_recurrent_failure_flag": state.get("serious_recurrent_failure_flag", False),
            "profile_version": profile_version,
        })
    approval = approval_manifest or {}
    manifest = {
        "status": approval.get("status", "candidate"),
        "interpretation_allowed": approval.get("interpretation_allowed") is True,
        "approved_by": approval.get("approved_by", ""), "approved_at": approval.get("approved_at", ""),
        "thresholds": {
            "minimum_GT_support": min_gt, "minimum_task_support": min_tasks,
            "minimum_building_support": int(config.get("min_building_support", 0)),
            "quality_floor": quality_floor, "maximum_structural_failure_eb": max_struct,
            "require_process_eligible": True, "require_independence_eligible": True,
            "frozen_random_seed": int(config.get("frozen_random_seed", 20260728)),
        },
    }
    output = build_global_policy(candidates, manifest, formal=input_status == "formal")
    for row in output:
        row["global_eligible"] = row["global_policy_eligible"]
        row["exclusion_reason"] = row["global_exclusion_reason"]
        row["global_rank"] = row["global_rank_S_G"] if input_status == "formal" else ""
        row["provisional_rank"] = row["global_rank_S_G"] if input_status != "formal" else ""
        if input_status != "formal":
            row["global_rank_EB"] = row["global_rank_FE"] = ""
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
        manifest.get("status") == "approved"
        and manifest.get("interpretation_allowed") is True
        and manifest.get("approved_by") and manifest.get("approved_at")
        and global_thresholds.get("status") == "approved"
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
    required_gates = {"min_gt_support", "min_task_support", "min_building_support", "max_f_struct", "quality_lcb_floor", "confidence_level", "min_global_eligible_workers", "frozen_random_seed"}
    if input_status == "formal" and not required_gates.issubset(estimator):
        raise ValueError("formal Strong Global requires frozen estimator gates")
    worker_state_rows = _read(worker_state_csv)
    if input_status == "formal":
        required_structural = ("administratively_eligible", "Q_GT_estimable", "reference_evaluable", "F_struct_raw", "F_struct_EB", "F_struct_interval_lower", "F_struct_interval_upper", "serious_recurrent_failure_flag")
        missing = [f"worker_state:{index}:{field}" for index, row in enumerate(worker_state_rows) for field in required_structural if str(row.get(field, "")).strip() == ""]
        if missing:
            raise ValueError("formal routing profile requires real structural fields: " + ";".join(missing))
    global_rows, task_rows, model_audit = build_global(
        _read(submissions_csv), worker_state_rows, profile_version=version,
        estimator=estimator, input_status=input_status, approval_manifest=manifest,
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
