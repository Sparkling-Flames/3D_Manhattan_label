from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path

try:
    from tools.thesis_main.registry.calibration_launch_common import load_csv, safe, truthy, write_csv, write_json
except ModuleNotFoundError:  # direct `python tools/...py`
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[3]))
    from tools.thesis_main.registry.calibration_launch_common import load_csv, safe, truthy, write_csv, write_json


TASK_FIELDS = [
    "worker_id",
    "worker_display_name",
    "platform_id",
    "interface_language",
    "ls_endpoint",
    "project_name",
    "task_id",
    "task_url",
    "dataset_group",
    "is_common_anchor",
    "expected_completion_order",
    "assignment_reason",
    "watch_flag",
    "notes",
]

INDEX_FIELDS = ["worker_id", "task_count", "anchor_count", "core_count", "project_names", "output_csv", "watch_flag"]


def _file_safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "worker"


def _worker_meta(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    return {safe(row.get("worker_id")): row for row in load_csv(path) if safe(row.get("worker_id"))}


def _mapping(path: Path | None) -> dict[str, list[dict[str, str]]]:
    if path is None:
        return {}
    rows_by_batch: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in load_csv(path):
        rows_by_batch[safe(row.get("assignment_batch"))].append(row)
    return rows_by_batch


def _choose_project(batch_rows: list[dict[str, str]], language: str) -> dict[str, str]:
    if not batch_rows:
        return {}
    for row in batch_rows:
        if safe(row.get("interface_language")) and safe(row.get("interface_language")) == language:
            return row
    return batch_rows[0]


def _task_url(project: dict[str, str], task_id: str) -> str:
    template = safe(project.get("task_url_template"))
    if template:
        return template.format(task_id=task_id, project_name=safe(project.get("project_name")), project_id=safe(project.get("project_id")))
    return ""


def build_distribution(
    assignment_manifest: Path,
    output_dir: Path,
    project_mapping_csv: Path | None = None,
    worker_roster_csv: Path | None = None,
) -> dict:
    assignment_rows = load_csv(assignment_manifest)
    workers = _worker_meta(worker_roster_csv)
    projects = _mapping(project_mapping_csv)
    by_worker: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in assignment_rows:
        worker_id = safe(row.get("worker_id"))
        meta = workers.get(worker_id, {})
        language = safe(meta.get("interface_language") or meta.get("language"))
        project = _choose_project(projects.get(safe(row.get("assignment_batch")), []), language)
        watch_flag = truthy(meta.get("watch_flag")) or safe(meta.get("admission_status")).lower() == "pass_with_watch"
        task_id = safe(row.get("task_id"))
        by_worker[worker_id].append(
            {
                "worker_id": worker_id,
                "worker_display_name": safe(meta.get("worker_display_name") or meta.get("display_name")),
                "platform_id": safe(meta.get("platform_id")),
                "interface_language": language or safe(project.get("interface_language")),
                "ls_endpoint": safe(project.get("ls_endpoint")),
                "project_name": safe(project.get("project_name")),
                "task_id": task_id,
                "task_url": _task_url(project, task_id),
                "dataset_group": safe(row.get("dataset_group")),
                "is_common_anchor": safe(row.get("is_common_anchor")),
                "expected_completion_order": safe(row.get("expected_completion_order")),
                "assignment_reason": safe(row.get("assignment_reason")),
                "watch_flag": watch_flag,
                "notes": safe(meta.get("notes")),
            }
        )

    index_rows: list[dict[str, object]] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    for worker_id, rows in sorted(by_worker.items()):
        rows.sort(key=lambda r: (int(safe(r.get("expected_completion_order")) or 0), safe(r.get("task_id"))))
        out = output_dir / f"worker_{_file_safe(worker_id)}_C1_tasks.csv"
        write_csv(out, TASK_FIELDS, rows)
        index_rows.append(
            {
                "worker_id": worker_id,
                "task_count": len(rows),
                "anchor_count": sum(1 for row in rows if row["dataset_group"] == "Calibration_anchor"),
                "core_count": sum(1 for row in rows if row["dataset_group"] == "Calibration_core"),
                "project_names": "|".join(sorted({safe(row.get("project_name")) for row in rows if safe(row.get("project_name"))})),
                "output_csv": str(out),
                "watch_flag": any(bool(row["watch_flag"]) for row in rows),
            }
        )
    write_csv(output_dir / "worker_facing_c1_distribution_index.csv", INDEX_FIELDS, index_rows)
    blockers = [] if index_rows else ["empty_assignment_manifest"]
    return {
        "passed": not blockers,
        "blockers": blockers,
        "counts": {
            "workers": len(index_rows),
            "tasks": len(assignment_rows),
            "watch_workers": sum(1 for row in index_rows if row["watch_flag"]),
        },
        "index_rows": index_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-worker C1 task distribution CSVs from assignment_manifest_C1.csv.")
    parser.add_argument("--assignment-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--project-mapping", type=Path)
    parser.add_argument("--worker-roster", type=Path)
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()

    summary = build_distribution(args.assignment_manifest, args.output_dir, args.project_mapping, args.worker_roster)
    if args.summary_json:
        write_json(args.summary_json, summary)
    else:
        print(summary)
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
