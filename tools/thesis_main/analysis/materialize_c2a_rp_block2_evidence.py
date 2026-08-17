"""Materialize C2-A-RP Block 2 quality/risk evidence from frozen raw inputs."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


ROOT = Path(__file__).resolve().parents[3]


def _base_task(task: dict[str, Any]) -> str:
    data = task.get("data") if isinstance(task.get("data"), dict) else {}
    value = str(data.get("base_task_id") or data.get("task_id") or "").strip()
    if value:
        return value
    title = str(data.get("title") or data.get("image") or "").rsplit("/", 1)[-1]
    for suffix in (".jpg", ".jpeg", ".png"):
        if title.lower().endswith(suffix):
            return title[: -len(suffix)]
    return title


def bind_gt_predictions(
    raw_tasks: list[dict[str, Any]], gt_tasks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    gt_by_task: dict[str, list[dict[str, Any]]] = {}
    for task in gt_tasks:
        key = _base_task(task)
        if not key:
            continue
        if key in gt_by_task:
            raise ValueError(f"duplicate GT task identity:{key}")
        predictions = task.get("predictions") or []
        if not predictions:
            raise ValueError(f"GT task lacks predictions:{key}")
        gt_by_task[key] = predictions
    bound = deepcopy(raw_tasks)
    missing: list[str] = []
    for task in bound:
        key = _base_task(task)
        if key not in gt_by_task:
            missing.append(key)
            continue
        task["predictions"] = deepcopy(gt_by_task[key])
    if missing:
        raise ValueError(f"missing GT for raw tasks:{','.join(sorted(missing))}")
    return bound, {
        "raw_tasks": len(raw_tasks),
        "gt_tasks": len(gt_by_task),
        "matched_tasks": len(raw_tasks),
        "unmatched_task_ids": [],
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("refusing to write empty Block 2 evidence")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _worker(annotation: dict[str, Any]) -> str:
    value = annotation.get("completed_by")
    if isinstance(value, dict):
        value = value.get("id")
    return str(value or "").strip()


def materialize(
    *,
    exports: list[Path],
    gt_import: Path,
    assignment: Path,
    task_pool: Path,
    active_logs: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise ValueError(f"output directory already exists:{output_dir}")
    inputs = [*exports, gt_import, assignment, task_pool, active_logs / "ACTIVE_TIME_FREEZE_MANIFEST.json"]
    if any(not path.is_file() for path in inputs):
        raise ValueError("Block 2 evidence input is missing")
    raw_tasks: list[dict[str, Any]] = []
    for path in exports:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_tasks.extend(payload if isinstance(payload, list) else [payload])
    gt_payload = json.loads(gt_import.read_text(encoding="utf-8"))
    gt_tasks = gt_payload if isinstance(gt_payload, list) else [gt_payload]
    bound, binding_audit = bind_gt_predictions(raw_tasks, gt_tasks)

    output_dir.mkdir(parents=True)
    bound_path = output_dir / "c2a_rp_block2_gt_bound_export.json"
    bound_path.write_text(json.dumps(bound, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quality_path = output_dir / "c2a_rp_block2_quality_report.csv"
    subprocess.run([
        sys.executable,
        str(ROOT / "tools/thesis_main/analysis/analyze_quality.py"),
        str(bound_path),
        "--active-logs", str(active_logs),
        "--output_dir", str(output_dir),
        "--output", str(quality_path),
        "--dataset_group", "C2A_RP_BLOCK2",
        "--project_version", load_method_contract()["contract_version"],
        "--metric", "corner",
    ], cwd=ROOT, check=True)

    assignments = _read_csv(assignment)
    pool = {row["base_task_id"]: row for row in _read_csv(task_pool)}
    assigned = {(row["worker_id"], row["base_task_id"]): row for row in assignments}
    annotation_ids: dict[tuple[str, str], str] = {}
    for task in raw_tasks:
        base = _base_task(task)
        for annotation in task.get("annotations") or []:
            annotation_ids[(_worker(annotation), base)] = str(annotation.get("id") or "")
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in _read_csv(quality_path):
        worker = row["annotator_id"]
        title = row.get("title", "")
        base = next((value for value in pool if value in title), "")
        key = (worker, base)
        if not base or key not in assigned or key in seen:
            raise ValueError(f"Block 2 quality row does not uniquely match assignment:{worker}:{title}")
        seen.add(key)
        plan, task = assigned[key], pool[base]
        canonical_valid = int(float(row.get("n_corners") or 0)) > 0
        eligible = canonical_valid and str(task.get("c2a_rp_eligible", "")).lower() == "true" and str(task.get("formal_use_blocked_until_review", "")).lower() != "true"
        quality = float(row["iou"])
        risk = float(task["risk_design_score_A"])
        evidence.append({
            "schema_version": "c2a_rp_block2_risk_slope_evidence_v1",
            "evidence_stage": "C2A_RP_BLOCK2",
            "risk_model_scope": "C2B_PLUS_C2A_RP_TERMINAL_REESTIMATE",
            "canonical_annotation_id": annotation_ids[key],
            "deployment_id": "",
            "project_id": row.get("export_project_id", ""),
            "runtime_task_id": row.get("task_id", ""),
            "planned_task_id": base,
            "worker_id": worker,
            "task_id": base,
            "base_task_id": base,
            "image_id": task.get("image_id", base),
            "building_id": task["building_id"],
            "task_stratum": plan["task_stratum"],
            "risk": risk,
            "quality": quality,
            "canonical_valid": str(canonical_valid),
            "risk_slope_estimand_eligible": str(eligible),
            "eligibility_status": "eligible" if eligible else "not_evaluable",
            "ineligibility_reason": "" if eligible else "canonical_invalid_or_formal_task_block",
            "reference_registry_sha256": sha256_file(gt_import),
            "task_pool_sha256": sha256_file(task_pool),
            "assignment_batch_id": "C2A_RP_BLOCK2",
            "design_manifest_sha256": plan.get("design_manifest_sha256", ""),
            "formal_assignment_eligible": "true",
            "routing_feature_analysis_eligible": str(eligible).lower(),
            "risk_design_score_A": risk,
            "Q_GT_raw": quality,
            "block_index": "2",
        })
    if seen != set(assigned):
        missing = sorted(set(assigned) - seen)
        raise ValueError(f"Block 2 assigned rows are missing quality evidence:{missing}")
    evidence_path = output_dir / "c2a_rp_block2_risk_slope_evidence.csv"
    _write_csv(evidence_path, evidence)
    summary = {
        "schema_version": "c2a_rp_block2_evidence_materialization_v1",
        "artifact_role": "C2A_RP_BLOCK2_EVIDENCE_FROZEN",
        "formal_ready": True,
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "n_assignments": len(assignments),
        "n_quality_rows": len(evidence),
        "n_risk_eligible": sum(str(row["risk_slope_estimand_eligible"]).lower() == "true" for row in evidence),
        "gt_binding": binding_audit,
        "input_sha256": {str(path.resolve().relative_to(ROOT.resolve())): sha256_file(path) for path in inputs},
        "output_sha256": {
            bound_path.name: sha256_file(bound_path),
            quality_path.name: sha256_file(quality_path),
            evidence_path.name: sha256_file(evidence_path),
        },
    }
    summary_path = output_dir / "c2a_rp_block2_evidence_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="append", type=Path, required=True)
    parser.add_argument("--gt-import", type=Path, required=True)
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--task-pool", type=Path, required=True)
    parser.add_argument("--active-logs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(
        exports=args.export, gt_import=args.gt_import, assignment=args.assignment,
        task_pool=args.task_pool, active_logs=args.active_logs, output_dir=args.output_dir,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
