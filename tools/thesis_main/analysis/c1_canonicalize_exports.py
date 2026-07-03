from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import (
    ACTIVE_LOG_DEFAULT,
    MANUAL_ASSIGNMENT_DEFAULT,
    PLANNED_TASK_MAPPING_DEFAULT,
    SEMI_ASSIGNMENT_DEFAULT,
    WORKER_DISTRIBUTION_DEFAULT,
    RUNTIME_MAPPING_FIELDS,
    active_time_policy,
    assignment_sets,
    bool_text,
    build_runtime_task_mapping,
    is_reserve,
    read_csv,
    safe,
    write_csv,
    write_json,
)
from tools.thesis_main.analysis.prescreen_canonicalize_export import build_canonical_tables, snapshot_inputs

DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c1_closeout")

CANONICAL_FIELDS = [
    "round_id",
    "planned_project_name",
    "project_id",
    "ls_runtime_task_id",
    "planned_inner_id",
    "task_code",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "worker_id",
    "annotation_id",
    "canonical_annotation_id",
    "active_time",
    "active_time_source",
    "active_time_match_status",
    "primary_active_time_eligible",
    "sensitivity_active_time_eligible",
    "geometry_hash",
    "n_corners",
    "parse_error",
    "assigned_expected",
    "appears_in_internal_distribution",
    "outside_assignment_submission",
    "duplicate_worker_task_submission",
    "source_export",
    "raw_canonical_annotation_id",
    "duplicate_annotation_ids",
    "duplicate_group_size",
    "duplicate_geometry_type",
    "active_time_source_file",
    "active_time_session_count",
    "active_time_event_count",
    "reserve_realized_submission",
]

ACTIVE_AUDIT_FIELDS = [
    "round_id",
    "project_id",
    "ls_runtime_task_id",
    "worker_id",
    "annotation_id",
    "canonical_annotation_id",
    "active_time",
    "active_time_source",
    "active_time_match_status",
    "active_time_source_file",
    "active_time_session_count",
    "active_time_event_count",
    "primary_active_time_eligible",
    "sensitivity_active_time_eligible",
]

REALIZED_AUDIT_FIELDS = [
    "round_id",
    "planned_project_name",
    "project_id",
    "ls_runtime_task_id",
    "planned_inner_id",
    "task_code",
    "task_id",
    "base_task_id",
    "dataset_group",
    "worker_id",
    "annotation_id",
    "canonical_annotation_id",
    "assigned_expected",
    "appears_in_internal_distribution",
    "outside_assignment_submission",
    "duplicate_worker_task_submission",
    "reserve_realized_submission",
]


def _canonical_id(round_id: str, project_id: str, runtime_task_id: str, worker_id: str, annotation_id: str) -> str:
    payload = f"{round_id}|{project_id}|{runtime_task_id}|{worker_id}|{annotation_id}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:20]


def _merge_manifest(export_paths: list[Path], runtime_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_export = Counter(row["source_export"] for row in runtime_rows)
    rows = []
    for path in export_paths:
        rows.append(
            {
                "source_export": str(path),
                "runtime_task_count": by_export[str(path)],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "",
                "bytes": path.stat().st_size if path.exists() else "",
            }
        )
    return rows


def _enhance_duplicate_rows(
    duplicate_rows: list[dict[str, Any]],
    runtime_lookup: dict[tuple[str, str], dict[str, str]],
    round_id: str,
) -> list[dict[str, Any]]:
    out = []
    for row in duplicate_rows:
        project_id = safe(row.get("project_id"))
        runtime_task_id = safe(row.get("task_id"))
        info = runtime_lookup.get((project_id, runtime_task_id), {})
        worker_id = safe(row.get("annotator_id"))
        annotation_id = safe(row.get("raw_canonical_annotation_id"))
        out.append(
            {
                **row,
                "round_id": round_id,
                "ls_runtime_task_id": runtime_task_id,
                "task_id": info.get("task_id", ""),
                "base_task_id": info.get("base_task_id", ""),
                "dataset_group": info.get("dataset_group", ""),
                "worker_id": worker_id,
                "canonical_annotation_id": _canonical_id(round_id, project_id, runtime_task_id, worker_id, annotation_id),
            }
        )
    return out


def build_canonicalization(
    export_paths: list[Path],
    manual_assignment: Path = MANUAL_ASSIGNMENT_DEFAULT,
    semi_assignment: Path = SEMI_ASSIGNMENT_DEFAULT,
    worker_distribution: Path = WORKER_DISTRIBUTION_DEFAULT,
    planned_task_mapping: Path = PLANNED_TASK_MAPPING_DEFAULT,
    active_log: Path | None = ACTIVE_LOG_DEFAULT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    round_id: str = "C1",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assigned, internal = assignment_sets(manual_assignment, semi_assignment, worker_distribution)
    runtime_rows, runtime_lookup = build_runtime_task_mapping(export_paths, planned_task_mapping)
    canonical_base, duplicate_base, base_summary = build_canonical_tables(export_paths, active_log)

    worker_task_counts = Counter(
        (
            safe(row.get("project_id")),
            safe(row.get("task_id")),
            safe(row.get("annotator_id")),
        )
        for row in canonical_base
    )

    canonical_rows: list[dict[str, Any]] = []
    active_rows: list[dict[str, Any]] = []
    realized_rows: list[dict[str, Any]] = []

    for row in canonical_base:
        project_id = safe(row.get("project_id"))
        runtime_task_id = safe(row.get("task_id"))
        worker_id = safe(row.get("annotator_id"))
        raw_annotation_id = safe(row.get("raw_canonical_annotation_id") or row.get("annotation_id"))
        info = runtime_lookup.get((project_id, runtime_task_id), {})
        key = (worker_id, safe(info.get("task_id")), safe(info.get("base_task_id")), safe(info.get("dataset_group")))
        try:
            session_count = int(row.get("active_time_session_count") or 0)
        except (TypeError, ValueError):
            session_count = 0
        primary, sensitivity = active_time_policy(
            safe(row.get("active_time_source")),
            safe(row.get("active_time_match_status")),
            session_count,
        )
        try:
            duplicate_group_size = int(row.get("duplicate_group_size") or 1)
        except (TypeError, ValueError):
            duplicate_group_size = 1
        c_row = {
            "round_id": round_id,
            "planned_project_name": info.get("planned_project_name", ""),
            "project_id": project_id,
            "ls_runtime_task_id": runtime_task_id,
            "planned_inner_id": info.get("planned_inner_id", ""),
            "task_code": info.get("task_code", ""),
            "task_id": info.get("task_id", ""),
            "base_task_id": info.get("base_task_id", ""),
            "dataset_group": info.get("dataset_group", ""),
            "condition": info.get("condition", safe(row.get("condition"))),
            "worker_id": worker_id,
            "annotation_id": raw_annotation_id,
            "canonical_annotation_id": _canonical_id(round_id, project_id, runtime_task_id, worker_id, raw_annotation_id),
            "active_time": row.get("active_time", ""),
            "active_time_source": row.get("active_time_source", ""),
            "active_time_match_status": row.get("active_time_match_status", ""),
            "primary_active_time_eligible": bool_text(primary),
            "sensitivity_active_time_eligible": bool_text(sensitivity),
            "geometry_hash": row.get("geometry_hash", ""),
            "n_corners": row.get("n_corners", ""),
            "parse_error": row.get("parse_error", ""),
            "assigned_expected": bool_text(key in assigned),
            "appears_in_internal_distribution": bool_text(key in internal),
            "outside_assignment_submission": bool_text(key not in assigned),
            "duplicate_worker_task_submission": bool_text(
                duplicate_group_size > 1 or worker_task_counts[(project_id, runtime_task_id, worker_id)] > 1
            ),
            "source_export": row.get("source_export", ""),
            "raw_canonical_annotation_id": raw_annotation_id,
            "duplicate_annotation_ids": row.get("duplicate_annotation_ids", ""),
            "duplicate_group_size": row.get("duplicate_group_size", ""),
            "duplicate_geometry_type": row.get("duplicate_geometry_type", ""),
            "active_time_source_file": row.get("active_time_source_file", ""),
            "active_time_session_count": row.get("active_time_session_count", ""),
            "active_time_event_count": row.get("active_time_event_count", ""),
            "reserve_realized_submission": bool_text(is_reserve(info)),
        }
        canonical_rows.append(c_row)
        active_rows.append({field: c_row.get(field, "") for field in ACTIVE_AUDIT_FIELDS})
        realized_rows.append({field: c_row.get(field, "") for field in REALIZED_AUDIT_FIELDS})

    duplicate_rows = _enhance_duplicate_rows(duplicate_base, runtime_lookup, round_id)
    raw_manifest = snapshot_inputs(
        export_paths + ([active_log] if active_log else []) + [manual_assignment, semi_assignment, worker_distribution, planned_task_mapping],
        output_dir,
        completion_basis="c1_closeout_canonicalization_snapshot",
    )

    write_csv(output_dir / "c1_runtime_task_mapping.csv", runtime_rows, RUNTIME_MAPPING_FIELDS)
    write_csv(output_dir / "c1_canonical_annotations.csv", canonical_rows, CANONICAL_FIELDS)
    write_csv(output_dir / "c1_duplicate_annotation_audit.csv", duplicate_rows)
    write_csv(output_dir / "c1_active_time_binding_audit.csv", active_rows, ACTIVE_AUDIT_FIELDS)
    write_csv(output_dir / "c1_realized_vs_assigned_audit.csv", realized_rows, REALIZED_AUDIT_FIELDS)
    write_csv(output_dir / "c1_export_merge_manifest.csv", _merge_manifest(export_paths, runtime_rows))

    outside_count = sum(row["outside_assignment_submission"] == "true" for row in canonical_rows)
    duplicate_count = sum(row["duplicate_worker_task_submission"] == "true" for row in canonical_rows)
    reserve_count = sum(row["reserve_realized_submission"] == "true" for row in canonical_rows)
    primary_missing = sum(row["primary_active_time_eligible"] != "true" for row in canonical_rows)
    summary = {
        **base_summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "round_id": round_id,
        "runtime_task_count": len(runtime_rows),
        "n_canonical_rows": len(canonical_rows),
        "outside_assignment_submission_count": outside_count,
        "duplicate_worker_task_submission_count": duplicate_count,
        "reserve_realized_submission_count": reserve_count,
        "active_log_primary_missing_count": primary_missing,
        "active_log_missing_rate": round(primary_missing / len(canonical_rows), 6) if canonical_rows else 0.0,
        "canonical_csv": str(output_dir / "c1_canonical_annotations.csv"),
        "raw_input_manifest": str(raw_manifest),
        "primary_active_time_policy": "log with project+task+worker+annotation or unambiguous project+task+worker direct match; lead_time never primary",
        "passed": outside_count == 0 and duplicate_count == 0 and reserve_count == 0,
        "blockers": [
            name
            for name, count in (
                ("outside_assignment_submission_detected", outside_count),
                ("duplicate_worker_task_submission_detected", duplicate_count),
                ("reserve_realized_submission_detected", reserve_count),
            )
            if count
        ],
    }
    write_json(output_dir / "c1_canonicalization_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Canonicalize C1 Label Studio exports for formal closeout.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--manual-assignment", type=Path, default=MANUAL_ASSIGNMENT_DEFAULT)
    parser.add_argument("--semi-assignment", type=Path, default=SEMI_ASSIGNMENT_DEFAULT)
    parser.add_argument("--worker-distribution", type=Path, default=WORKER_DISTRIBUTION_DEFAULT)
    parser.add_argument("--planned-task-mapping", type=Path, default=PLANNED_TASK_MAPPING_DEFAULT)
    parser.add_argument("--active-log", type=Path, default=ACTIVE_LOG_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--round-id", default="C1")
    args = parser.parse_args(argv)
    summary = build_canonicalization(
        args.export_json,
        manual_assignment=args.manual_assignment,
        semi_assignment=args.semi_assignment,
        worker_distribution=args.worker_distribution,
        planned_task_mapping=args.planned_task_mapping,
        active_log=args.active_log,
        output_dir=args.output_dir,
        round_id=args.round_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
