from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


REQUIRED_FIELDS = {
    "round_id",
    "worker_id",
    "task_id",
    "base_task_id",
    "dataset_group",
    "assignment_batch",
    "assignment_reason",
    "is_common_anchor",
    "expected_completion_order",
    "manifest_version",
}


def load_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = sorted(REQUIRED_FIELDS.difference(fieldnames))
        if missing:
            raise ValueError(f"assignment manifest missing required fields: {', '.join(missing)}")
        return list(reader), fieldnames


def _is_anchor(row: dict[str, str]) -> bool:
    return row.get("dataset_group") == "Calibration_anchor" or row.get("assignment_reason") == "common_anchor"


def _is_core(row: dict[str, str]) -> bool:
    return row.get("dataset_group") == "Calibration_core" or row.get("assignment_reason") == "balanced_core"


def audit_rows(
    rows: list[dict[str, str]],
    *,
    core_target_k: int,
    core_min_accepted_k: int,
    min_worker_calibration_tasks: int,
) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if core_target_k < core_min_accepted_k:
        raise ValueError("core_target_k must be >= core_min_accepted_k")
    if not rows:
        errors.append("assignment_manifest_C1.csv has no rows")

    workers = sorted({row["worker_id"] for row in rows if row.get("worker_id")})
    anchor_rows = [row for row in rows if _is_anchor(row)]
    core_rows = [row for row in rows if _is_core(row)]
    reserve_rows = [row for row in rows if row.get("dataset_group") == "Calibration_reserve"]

    if reserve_rows:
        errors.append(f"C1 manifest contains Calibration_reserve rows: {len(reserve_rows)}")

    rows_by_worker_task = Counter((row["worker_id"], row["task_id"]) for row in rows)
    duplicate_assignments = [key for key, count in rows_by_worker_task.items() if count > 1]
    if duplicate_assignments:
        errors.append(f"duplicate worker/task assignments found: {len(duplicate_assignments)}")

    all_worker_set = set(workers)
    anchor_by_task: dict[str, set[str]] = defaultdict(set)
    for row in anchor_rows:
        anchor_by_task[row["task_id"]].add(row["worker_id"])
    for task_id, assigned_workers in sorted(anchor_by_task.items()):
        if assigned_workers != all_worker_set:
            missing = sorted(all_worker_set.difference(assigned_workers))
            extra = sorted(assigned_workers.difference(all_worker_set))
            errors.append(f"anchor task {task_id} is not assigned to all workers; missing={missing}, extra={extra}")

    core_by_task: dict[str, list[str]] = defaultdict(list)
    for row in core_rows:
        core_by_task[row["task_id"]].append(row["worker_id"])
    for task_id, assigned_workers in sorted(core_by_task.items()):
        unique_workers = set(assigned_workers)
        if len(assigned_workers) != len(unique_workers):
            errors.append(f"core task {task_id} has duplicate worker assignments")
        if len(unique_workers) != core_target_k:
            errors.append(f"core task {task_id} assigned_count={len(unique_workers)}, target_k={core_target_k}")
        if len(unique_workers) < core_min_accepted_k:
            errors.append(f"core task {task_id} assigned_count={len(unique_workers)}, min_k={core_min_accepted_k}")

    worker_counts = Counter(row["worker_id"] for row in rows)
    underfilled_workers = {
        worker: count for worker, count in sorted(worker_counts.items()) if count < min_worker_calibration_tasks
    }
    if underfilled_workers:
        errors.append(f"workers below min calibration tasks: {underfilled_workers}")

    base_by_worker: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        base_task_id = (row.get("base_task_id") or "").strip()
        if base_task_id:
            base_by_worker[row["worker_id"]].append(base_task_id)
    repeated_base_by_worker = {
        worker: sorted(base for base, count in Counter(base_ids).items() if count > 1)
        for worker, base_ids in base_by_worker.items()
    }
    repeated_base_by_worker = {worker: bases for worker, bases in repeated_base_by_worker.items() if bases}
    if repeated_base_by_worker:
        errors.append(f"worker/base_task_id repeats found: {repeated_base_by_worker}")

    if not anchor_rows:
        warnings.append("no Calibration_anchor rows found")
    if not core_rows:
        warnings.append("no Calibration_core rows found")

    return {
        "meta": {
            "core_target_k": core_target_k,
            "core_min_accepted_k": core_min_accepted_k,
            "reserve_policy": "unchanged_C2_only",
            "c1_status": "provisional_only",
        },
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "workers": len(workers),
            "anchor_tasks": len(anchor_by_task),
            "core_tasks": len(core_by_task),
            "anchor_assignments": len(anchor_rows),
            "core_assignments": len(core_rows),
            "reserve_assignments": len(reserve_rows),
            "total_assignments": len(rows),
            "min_worker_assignments": min(worker_counts.values()) if worker_counts else 0,
            "max_worker_assignments": max(worker_counts.values()) if worker_counts else 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit assignment_manifest_C1.csv target/min k and reserve exclusion.")
    parser.add_argument("--assignment-manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--core-target-k", default=5, type=int)
    parser.add_argument("--core-min-accepted-k", default=4, type=int)
    parser.add_argument("--min-worker-calibration-tasks", default=25, type=int)
    args = parser.parse_args()

    rows, _fieldnames = load_rows(args.assignment_manifest)
    summary = audit_rows(
        rows,
        core_target_k=args.core_target_k,
        core_min_accepted_k=args.core_min_accepted_k,
        min_worker_calibration_tasks=args.min_worker_calibration_tasks,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
