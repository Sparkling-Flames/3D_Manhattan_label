"""Produce frozen Strong Global and validated Full component tables from calibration artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any


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


def build_global(
    submissions: list[dict[str, str]], worker_state: list[dict[str, str]], *, profile_version: str
) -> list[dict[str, Any]]:
    usable = [
        row for row in submissions
        if row.get("quality_evaluable", "").lower() in {"true", "1"}
        and row.get("condition", "").lower() == "manual"
    ]
    if not usable:
        raise ValueError("no evaluable Manual GT submissions")
    task_values: dict[str, list[float]] = defaultdict(list)
    for row in usable:
        task_values[row["task_id"]].append(float(row["iou_to_gt"]))
    task_mean = {task: fmean(values) for task, values in task_values.items()}
    grand = fmean([float(row["iou_to_gt"]) for row in usable])
    by_worker: dict[str, list[float]] = defaultdict(list)
    raw: dict[str, list[float]] = defaultdict(list)
    for row in usable:
        worker, value = row["worker_id"], float(row["iou_to_gt"])
        raw[worker].append(value)
        by_worker[worker].append(value - task_mean[row["task_id"]] + grand)
    states = {row["worker_id"]: row for row in worker_state}
    output = []
    for worker, values in sorted(by_worker.items()):
        state = states.get(worker, {})
        adjusted = fmean(values)
        se = math.sqrt(sum((value - adjusted) ** 2 for value in values) / (len(values) * (len(values) - 1))) if len(values) > 1 else math.inf
        process = state.get("process_eligible", "").lower() in {"true", "1"}
        independence = state.get("independence_eligible", "").lower() in {"true", "1"}
        struct = float(state.get("F_struct") or 0)
        eligible = process and independence and math.isfinite(se)
        output.append({
            "worker_id": worker, "Q_GT_raw": fmean(raw[worker]),
            "Q_GT_task_adjusted": adjusted, "Q_GT_standard_error": se,
            "Q_GT_LCB": adjusted - 1.96 * se if math.isfinite(se) else "",
            "R_LOO_compatible": state.get("R_LOO_compatible", ""),
            "F_struct": struct, "GT_support": len(values),
            "LOO_support": state.get("LOO_support", ""),
            "process_eligible": process, "independence_eligible": independence,
            "global_eligible": eligible, "exclusion_reason": "" if eligible else "process_independence_or_support",
            "profile_version": profile_version,
        })
    ranked = sorted((row for row in output if row["global_eligible"]), key=lambda row: (-float(row["Q_GT_LCB"]), row["worker_id"]))
    ranks = {row["worker_id"]: index + 1 for index, row in enumerate(ranked)}
    for row in output:
        row["global_rank"] = ranks.get(row["worker_id"], "")
    return output


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
    freeze_manifest: Path, output_dir: Path,
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
    global_rows = build_global(_read(submissions_csv), _read(worker_state_csv), profile_version=version)
    components = build_full_components(_read(component_evidence_csv), profile_version=version)
    _write(output_dir / "strong_global_worker_table.csv", global_rows)
    _write(output_dir / "full_component_table.csv", components)
    summary = {
        "profile_version": version,
        "freeze_manifest_sha256": _sha(freeze_manifest),
        "input_sha256": {name: _sha(path) for name, path in inputs.items()},
        "n_global_eligible": sum(bool(row["global_eligible"]) for row in global_rows),
        "n_full_components": sum(bool(row["full_component_eligible"]) for row in components),
        "formal_ready": bool(global_rows),
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
    args = parser.parse_args()
    print(json.dumps(materialize(
        args.submissions_csv, args.worker_state_csv, args.component_evidence_csv,
        args.freeze_manifest, args.output_dir,
    ), indent=2))


if __name__ == "__main__":
    main()
