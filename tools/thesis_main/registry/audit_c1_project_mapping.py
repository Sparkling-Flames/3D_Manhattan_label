from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

try:
    from tools.thesis_main.registry.calibration_launch_common import load_csv, load_ls_import_tasks, safe, write_csv, write_json
except ModuleNotFoundError:  # direct `python tools/...py`
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from tools.thesis_main.registry.calibration_launch_common import load_csv, load_ls_import_tasks, safe, write_csv, write_json


DETAIL_FIELDS = [
    "project_name",
    "interface_language",
    "assignment_batch",
    "import_json",
    "expected_task_count",
    "imported_task_count",
    "missing_task_count",
    "extra_task_count",
    "reserve_task_count",
    "wrong_group_count",
    "passed",
]


def audit_project_mapping(assignment_manifest: Path, project_mapping_csv: Path) -> dict:
    assignment_rows = load_csv(assignment_manifest)
    mapping_rows = load_csv(project_mapping_csv)
    expected_by_batch: dict[str, set[str]] = defaultdict(set)
    group_by_task: dict[str, str] = {}
    for row in assignment_rows:
        task_id = safe(row.get("task_id"))
        batch = safe(row.get("assignment_batch"))
        if task_id and batch:
            expected_by_batch[batch].add(task_id)
            group_by_task[task_id] = safe(row.get("dataset_group"))

    errors: list[str] = []
    detail_rows: list[dict[str, object]] = []
    imported_by_batch: dict[str, list[set[str]]] = defaultdict(list)
    reserve_total = 0
    mismatch_total = 0
    if not mapping_rows:
        errors.append("missing_project_mapping_rows")

    for row in mapping_rows:
        batch = safe(row.get("assignment_batch"))
        project_name = safe(row.get("project_name"))
        import_json = Path(safe(row.get("import_json")))
        if not batch or batch not in expected_by_batch:
            errors.append("unknown_assignment_batch")
            expected = set()
        else:
            expected = expected_by_batch[batch]
        imported_rows = load_ls_import_tasks(import_json)
        imported = {safe(task.get("task_id")) for task in imported_rows if safe(task.get("task_id"))}
        imported_by_batch[batch].append(imported)
        missing = expected.difference(imported)
        extra = imported.difference(expected)
        reserve = [task for task in imported_rows if safe(task.get("dataset_group")) == "Calibration_reserve"]
        wrong_group = [
            task
            for task in imported_rows
            if safe(task.get("task_id")) in group_by_task
            and safe(task.get("dataset_group"))
            and safe(task.get("dataset_group")) != group_by_task[safe(task.get("task_id"))]
        ]
        reserve_total += len(reserve)
        mismatch_total += len(missing) + len(extra) + len(wrong_group)
        detail_rows.append(
            {
                "project_name": project_name,
                "interface_language": safe(row.get("interface_language")),
                "assignment_batch": batch,
                "import_json": str(import_json),
                "expected_task_count": len(expected),
                "imported_task_count": len(imported),
                "missing_task_count": len(missing),
                "extra_task_count": len(extra),
                "reserve_task_count": len(reserve),
                "wrong_group_count": len(wrong_group),
                "passed": not (missing or extra or reserve or wrong_group),
            }
        )

    language_mismatch_count = 0
    for batch, imported_sets in imported_by_batch.items():
        if len(imported_sets) > 1 and any(task_set != imported_sets[0] for task_set in imported_sets[1:]):
            language_mismatch_count += 1

    blockers = []
    if errors:
        blockers.extend(sorted(set(errors)))
    if reserve_total:
        blockers.append("reserve_task_imported_into_c1_project")
    if mismatch_total:
        blockers.append("project_task_mismatch")
    if language_mismatch_count:
        blockers.append("language_entry_task_mismatch")
    return {
        "passed": not blockers,
        "blockers": blockers,
        "counts": {
            "projects": len(mapping_rows),
            "assignment_batches": len(expected_by_batch),
            "reserve_task_imports": reserve_total,
            "project_task_mismatches": mismatch_total,
            "language_entry_mismatches": language_mismatch_count,
        },
        "project_audit_rows": detail_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit C1 LS project imports against assignment_manifest_C1.csv.")
    parser.add_argument("--assignment-manifest", required=True, type=Path)
    parser.add_argument("--project-mapping", required=True, type=Path)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args()

    summary = audit_project_mapping(args.assignment_manifest, args.project_mapping)
    if args.output_json:
        write_json(args.output_json, summary)
    else:
        print(summary)
    if args.output_csv:
        write_csv(args.output_csv, DETAIL_FIELDS, summary["project_audit_rows"])
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
