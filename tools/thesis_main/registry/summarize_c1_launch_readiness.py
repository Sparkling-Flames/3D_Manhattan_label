from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

try:
    from tools.thesis_main.registry.calibration_launch_common import (
        load_calibration_manifest_tasks,
        load_csv,
        load_json,
        safe,
        truthy,
        write_json,
    )
except ModuleNotFoundError:  # direct `python tools/...py`
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from tools.thesis_main.registry.calibration_launch_common import (
        load_calibration_manifest_tasks,
        load_csv,
        load_json,
        safe,
        truthy,
        write_json,
    )


def _audit_passed(path: Path) -> bool:
    payload = load_json(path)
    return isinstance(payload, dict) and payload.get("passed") is True


def summarize_launch_readiness(
    *,
    assignment_manifest: Path,
    calibration_manifest: Path,
    assignment_audit_json: Path,
    overlap_audit_json: Path,
    project_mapping_audit_json: Path,
    distribution_index: Path,
    tests_status: str,
    worker_roster_csv: Path | None = None,
) -> dict:
    assignment_rows = load_csv(assignment_manifest)
    csets = load_calibration_manifest_tasks(calibration_manifest)
    index_rows = load_csv(distribution_index)
    workers = sorted({safe(row.get("worker_id")) for row in assignment_rows if safe(row.get("worker_id"))})
    core_workers_by_task: dict[str, set[str]] = defaultdict(set)
    reserve_assignments = 0
    for row in assignment_rows:
        if safe(row.get("dataset_group")) == "Calibration_core":
            core_workers_by_task[safe(row.get("task_id"))].add(safe(row.get("worker_id")))
        if safe(row.get("dataset_group")) == "Calibration_reserve":
            reserve_assignments += 1
    roster_rows = load_csv(worker_roster_csv) if worker_roster_csv else []
    watch_ids = {
        safe(row.get("worker_id"))
        for row in roster_rows
        if safe(row.get("worker_id"))
        and (safe(row.get("admission_status")).lower() == "pass_with_watch" or truthy(row.get("watch_flag")))
    }
    clean_ids = {
        safe(row.get("worker_id"))
        for row in roster_rows
        if safe(row.get("worker_id"))
        and safe(row.get("admission_status")).lower() in {"pass", "admitted", "passed"}
        and safe(row.get("worker_id")) not in watch_ids
    }

    tests_ok = tests_status.strip().lower() in {"pass", "passed", "ok"}
    audit_status = {
        "assignment_manifest_audit": _audit_passed(assignment_audit_json),
        "p1_c1_overlap_audit": _audit_passed(overlap_audit_json),
        "project_mapping_audit": _audit_passed(project_mapping_audit_json),
        "tests": tests_ok,
    }
    distribution_workers = {safe(row.get("worker_id")) for row in index_rows if safe(row.get("worker_id"))}
    blockers = [name for name, ok in audit_status.items() if not ok]
    if len(workers) < 16:
        blockers.append("pass_count_below_full_execution_gate")
    if reserve_assignments:
        blockers.append("reserve_assigned_in_C1")
    if distribution_workers != set(workers):
        blockers.append("worker_distribution_mismatch")
    redundancy_counts = [len(worker_ids) for worker_ids in core_workers_by_task.values()]
    return {
        "passed": not blockers,
        "blockers": blockers,
        "protocol_position": "C1_launch_readiness_only_not_final_worker_tier",
        "pass_count_gate": "full_execution" if len(workers) >= 16 else "downgrade_required",
        "watch_policy": "retained_as_handoff_sidecar_not_exclusion",
        "audit_status": audit_status,
        "counts": {
            "workers": len(workers),
            "clean_pass_workers": len(clean_ids),
            "watch_pass_workers": len(watch_ids),
            "anchor_tasks": len(csets.get("Calibration_anchor", [])),
            "core_tasks": len(csets.get("Calibration_core", [])),
            "reserve_tasks": len(csets.get("Calibration_reserve", [])),
            "reserve_assignments": reserve_assignments,
            "assignment_rows": len(assignment_rows),
            "distribution_workers": len(distribution_workers),
            "core_redundancy_min": min(redundancy_counts) if redundancy_counts else 0,
            "core_redundancy_max": max(redundancy_counts) if redundancy_counts else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize C1 launch readiness audits.")
    parser.add_argument("--assignment-manifest", required=True, type=Path)
    parser.add_argument("--calibration-manifest", required=True, type=Path)
    parser.add_argument("--assignment-audit-json", required=True, type=Path)
    parser.add_argument("--overlap-audit-json", required=True, type=Path)
    parser.add_argument("--project-mapping-audit-json", required=True, type=Path)
    parser.add_argument("--distribution-index", required=True, type=Path)
    parser.add_argument("--tests-status", required=True)
    parser.add_argument("--worker-roster", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    summary = summarize_launch_readiness(
        assignment_manifest=args.assignment_manifest,
        calibration_manifest=args.calibration_manifest,
        assignment_audit_json=args.assignment_audit_json,
        overlap_audit_json=args.overlap_audit_json,
        project_mapping_audit_json=args.project_mapping_audit_json,
        distribution_index=args.distribution_index,
        tests_status=args.tests_status,
        worker_roster_csv=args.worker_roster,
    )
    if args.output_json:
        write_json(args.output_json, summary)
    else:
        print(summary)
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
