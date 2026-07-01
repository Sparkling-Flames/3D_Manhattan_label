from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

try:
    from tools.thesis_main.registry.calibration_launch_common import load_csv, load_json, safe, task_record, write_json
except ModuleNotFoundError:  # direct `python tools/...py`
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from tools.thesis_main.registry.calibration_launch_common import load_csv, load_json, safe, task_record, write_json


def _completed_by(annotation: dict) -> str:
    value = annotation.get("completed_by") or annotation.get("created_by") or annotation.get("user")
    if isinstance(value, dict):
        return safe(value.get("id") or value.get("username") or value.get("email"))
    return safe(value)


def _realized_pairs(export_paths: list[Path]) -> tuple[Counter[tuple[str, str]], int]:
    pairs: Counter[tuple[str, str]] = Counter()
    reserve_count = 0
    for path in export_paths:
        payload = load_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"{path} must be a Label Studio export JSON array")
        for task in payload:
            if not isinstance(task, dict):
                continue
            record = task_record(task, source_path=path)
            task_id = record["task_id"]
            if record["dataset_group"] == "Calibration_reserve":
                reserve_count += 1
            for annotation in task.get("annotations") or []:
                if not isinstance(annotation, dict):
                    continue
                worker_id = _completed_by(annotation)
                if worker_id and task_id:
                    pairs[(worker_id, task_id)] += 1
    return pairs, reserve_count


def audit_realized_vs_assigned(assignment_manifest: Path, export_jsons: list[Path], *, allow_incomplete: bool = False) -> dict:
    assignment_rows = load_csv(assignment_manifest)
    assigned = {(safe(row.get("worker_id")), safe(row.get("task_id"))) for row in assignment_rows if safe(row.get("worker_id")) and safe(row.get("task_id"))}
    realized_counts, reserve_count = _realized_pairs(export_jsons)
    realized = set(realized_counts)
    unassigned = realized.difference(assigned)
    missing = assigned.difference(realized)
    duplicates = {pair: count for pair, count in realized_counts.items() if count > 1}
    blockers = []
    if unassigned:
        blockers.append("unassigned_realized_submission")
    if reserve_count:
        blockers.append("reserve_realized_in_c1_export")
    if duplicates:
        blockers.append("duplicate_realized_submission")
    if missing and not allow_incomplete:
        blockers.append("assigned_submission_missing")
    return {
        "passed": not blockers,
        "blockers": blockers,
        "counts": {
            "assigned_pairs": len(assigned),
            "realized_pairs": len(realized),
            "unassigned_realized_pairs": len(unassigned),
            "missing_assigned_pairs": len(missing),
            "duplicate_realized_pairs": len(duplicates),
            "reserve_export_tasks": reserve_count,
        },
        "unassigned_realized_pairs": [{"worker_id": worker, "task_id": task} for worker, task in sorted(unassigned)],
        "missing_assigned_pairs": [{"worker_id": worker, "task_id": task} for worker, task in sorted(missing)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit C1 Label Studio export submissions against assignment_manifest_C1.csv.")
    parser.add_argument("--assignment-manifest", required=True, type=Path)
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()

    summary = audit_realized_vs_assigned(args.assignment_manifest, args.export_json, allow_incomplete=args.allow_incomplete)
    if args.output_json:
        write_json(args.output_json, summary)
    else:
        print(summary)
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
