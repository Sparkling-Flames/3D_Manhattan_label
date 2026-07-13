from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
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
    RUNTIME_COLLISION_FIELDS,
    active_time_policy,
    active_time_for_annotation,
    assignment_key,
    assignment_sets,
    bool_text,
    _active_counts,
    active_time_audit_summary,
    build_annotation_owner_map,
    build_runtime_task_mapping,
    is_reserve,
    read_csv,
    safe,
    sha256_file,
    write_csv,
    write_json,
)
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.quality_core.active_time import load_active_logs
from tools.thesis_main.analysis.prescreen_canonicalize_export import build_canonical_tables
from tools.thesis_main.analysis.materialize_c1_canonical_evidence_sidecars import materialize_canonical_evidence
from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.materialize_model_issue_harmonization import materialize_model_issue_harmonization

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
    "planned_mapping_status",
    "runtime_binding_status",
    "assigned_expected",
    "appears_in_internal_distribution",
    "outside_assignment_submission",
    "missing_submission",
    "duplicate_worker_task_submission",
    "source_export",
    "raw_canonical_annotation_id",
    "duplicate_annotation_ids",
    "duplicate_group_size",
    "duplicate_geometry_type",
    "active_time_source_file",
    "active_time_session_count",
    "active_time_event_count",
    "unassigned_active_time_seconds",
    "unknown_annotation_event_count",
    "unknown_annotation_session_count",
    "known_unknown_oscillation_flag",
    "unassigned_audit_present",
    "unassigned_active_time_exclusion_reason",
    "active_time_integrity_status",
    "system_collection_issue",
    "active_time_exclusion_reason",
    "audit_only",
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
    "unassigned_active_time_seconds",
    "unknown_annotation_event_count",
    "unknown_annotation_session_count",
    "known_unknown_oscillation_flag",
    "unassigned_audit_present",
    "unassigned_active_time_exclusion_reason",
    "active_time_integrity_status",
    "system_collection_issue",
    "active_time_exclusion_reason",
    "audit_only",
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
    "missing_submission",
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


def snapshot_inputs_unique(paths: list[Path], output_dir: Path, completion_basis: str) -> Path:
    raw_dir = output_dir / "raw_inputs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    def add_file(path: Path, source_kind: str) -> None:
        exists = path.exists() and path.is_file()
        digest = sha256_file(path) if exists else ""
        snapshot_path = ""
        size = ""
        if exists:
            snapshot_path = str(raw_dir / f"{len(rows) + 1:03d}_{digest[:12]}_{path.name}")
            shutil.copy2(path, snapshot_path)
            size = str(Path(snapshot_path).stat().st_size)
        rows.append(
            {
                "source_path": str(path),
                "snapshot_path": snapshot_path,
                "source_kind": source_kind,
                "exists": bool_text(exists),
                "bytes": size,
                "sha256": digest,
                "completion_basis": completion_basis,
            }
        )

    for path in paths:
        if path.is_dir():
            _resolved, files = resolve_active_log_files(path)
            if files:
                for file_path in files:
                    add_file(file_path, "active_log_snapshot")
            else:
                add_file(path, "active_log_snapshot")
        else:
            add_file(path, "raw_input_snapshot")

    manifest_path = raw_dir / "raw_input_snapshot_manifest.csv"
    write_csv(manifest_path, rows)
    return manifest_path


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
    require_complete: bool = False,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assigned, internal = assignment_sets(manual_assignment, semi_assignment, worker_distribution)
    runtime_rows, runtime_lookup, collision_rows = build_runtime_task_mapping(export_paths, planned_task_mapping)
    canonical_base, duplicate_base, base_summary = build_canonical_tables(export_paths, active_log)
    active_times = load_active_logs(str(active_log), annotation_owner_map=build_annotation_owner_map(export_paths), policy="calibration") if active_log else {}

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
        duplicate_time_ambiguous = str(row.get("duplicate_time_ambiguous", "")).lower() == "true" or row.get("duplicate_time_ambiguous") is True
        active_override = active_time_for_annotation(active_times, project_id, runtime_task_id, worker_id, raw_annotation_id, float(row.get("lead_time_seconds") or 0))
        primary, sensitivity = active_time_policy(
            safe(active_override.get("active_time_source")), safe(active_override.get("active_time_match_status")),
            int(active_override.get("active_time_session_count") or 0), duplicate_time_ambiguous=duplicate_time_ambiguous,
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
            "active_time": active_override.get("active_time", row.get("active_time", "")),
            "active_time_source": active_override.get("active_time_source", row.get("active_time_source", "")),
            "active_time_match_status": active_override.get("active_time_match_status", row.get("active_time_match_status", "")),
            "primary_active_time_eligible": bool_text(primary),
            "sensitivity_active_time_eligible": bool_text(sensitivity),
            "geometry_hash": row.get("geometry_hash", ""),
            "n_corners": row.get("n_corners", ""),
            "parse_error": row.get("parse_error", ""),
            "planned_mapping_status": info.get("planned_mapping_status", ""),
            "runtime_binding_status": info.get("runtime_binding_status", ""),
            "assigned_expected": bool_text(key in assigned),
            "appears_in_internal_distribution": bool_text(key in internal),
            "outside_assignment_submission": bool_text(key not in assigned),
            "missing_submission": "false",
            "duplicate_worker_task_submission": bool_text(
                duplicate_group_size > 1 or worker_task_counts[(project_id, runtime_task_id, worker_id)] > 1
            ),
            "source_export": row.get("source_export", ""),
            "raw_canonical_annotation_id": raw_annotation_id,
            "duplicate_annotation_ids": row.get("duplicate_annotation_ids", ""),
            "duplicate_group_size": row.get("duplicate_group_size", ""),
            "duplicate_geometry_type": row.get("duplicate_geometry_type", ""),
            "active_time_source_file": active_override.get("active_time_source_file", row.get("active_time_source_file", "")),
            "active_time_session_count": active_override.get("active_time_session_count", row.get("active_time_session_count", "")),
            "active_time_event_count": active_override.get("active_time_event_count", row.get("active_time_event_count", "")),
            "unassigned_active_time_seconds": active_override.get("unassigned_active_time_seconds", 0),
            "unknown_annotation_event_count": active_override.get("unknown_annotation_event_count", 0),
            "unknown_annotation_session_count": active_override.get("unknown_annotation_session_count", 0),
            "known_unknown_oscillation_flag": bool_text(bool(active_override.get("known_unknown_oscillation_flag"))),
            "unassigned_audit_present": bool_text(bool(active_override.get("unassigned_audit_present"))),
            "unassigned_active_time_exclusion_reason": active_override.get("unassigned_active_time_exclusion_reason", ""),
            "active_time_integrity_status": active_override.get("active_time_integrity_status", "missing"),
            "system_collection_issue": bool_text(bool(active_override.get("system_collection_issue"))),
            "active_time_exclusion_reason": active_override.get("active_time_exclusion_reason", ""),
            "audit_only": bool_text(bool(active_override.get("audit_only"))),
            "reserve_realized_submission": bool_text(is_reserve(info)),
        }
        canonical_rows.append(c_row)
        active_rows.append({field: c_row.get(field, "") for field in ACTIVE_AUDIT_FIELDS})
        realized_rows.append({field: c_row.get(field, "") for field in REALIZED_AUDIT_FIELDS})

    realized_assigned_keys = {assignment_key(row) for row in realized_rows if assignment_key(row) in assigned}
    for worker, task_id, base_task_id, dataset_group in sorted(assigned - realized_assigned_keys):
        key = (worker, task_id, base_task_id, dataset_group)
        realized_rows.append(
            {
                "round_id": round_id,
                "planned_project_name": "",
                "project_id": "",
                "ls_runtime_task_id": "",
                "planned_inner_id": "",
                "task_code": "",
                "task_id": task_id,
                "base_task_id": base_task_id,
                "dataset_group": dataset_group,
                "worker_id": worker,
                "annotation_id": "",
                "canonical_annotation_id": "",
                "assigned_expected": "true",
                "appears_in_internal_distribution": bool_text(key in internal),
                "outside_assignment_submission": "false",
                "missing_submission": "true",
                "duplicate_worker_task_submission": "false",
                "reserve_realized_submission": "false",
            }
        )

    duplicate_rows = _enhance_duplicate_rows(duplicate_base, runtime_lookup, round_id)
    raw_manifest = snapshot_inputs_unique(
        export_paths + ([active_log] if active_log else []) + [manual_assignment, semi_assignment, worker_distribution, planned_task_mapping],
        output_dir,
        completion_basis="c1_closeout_canonicalization_snapshot",
    )

    write_csv(output_dir / "c1_runtime_task_mapping.csv", runtime_rows, RUNTIME_MAPPING_FIELDS)
    write_csv(output_dir / "c1_runtime_key_collision_audit.csv", collision_rows, RUNTIME_COLLISION_FIELDS)
    write_csv(output_dir / "c1_canonical_annotations.csv", canonical_rows, CANONICAL_FIELDS)
    write_csv(output_dir / "c1_duplicate_annotation_audit.csv", duplicate_rows)
    write_csv(output_dir / "c1_active_time_binding_audit.csv", active_rows, ACTIVE_AUDIT_FIELDS)
    write_csv(output_dir / "c1_realized_vs_assigned_audit.csv", realized_rows, REALIZED_AUDIT_FIELDS)
    write_csv(output_dir / "c1_export_merge_manifest.csv", _merge_manifest(export_paths, runtime_rows))
    canonical_evidence_summary = materialize_canonical_evidence(
        export_paths,
        output_dir / "c1_canonical_annotations.csv",
        output_dir,
        stage=round_id,
        input_status=input_status,
    )
    geometry_summary = materialize_geometry_consensus(
        output_dir / "c1_canonical_geometry.jsonl",
        output_dir,
        input_status=input_status,
    )
    harmonization_summary = materialize_model_issue_harmonization(
        export_paths,
        output_dir / "c1_canonical_geometry.jsonl",
        output_dir,
        input_status=input_status,
    )

    outside_count = sum(row["outside_assignment_submission"] == "true" for row in canonical_rows)
    duplicate_count = sum(row["duplicate_worker_task_submission"] == "true" for row in canonical_rows)
    reserve_count = sum(row["reserve_realized_submission"] == "true" for row in canonical_rows)
    active_counts = _active_counts(canonical_rows)
    active_audit_counts = active_time_audit_summary(canonical_rows)
    planned_missing_count = sum(row["planned_mapping_status"] == "planned_mapping_missing" for row in runtime_rows)
    missing_submission_count = sum(row["missing_submission"] == "true" for row in realized_rows)
    structural_integrity_passed = outside_count == 0 and duplicate_count == 0 and reserve_count == 0 and not collision_rows and not planned_missing_count
    collection_completeness_passed = missing_submission_count == 0
    passed = structural_integrity_passed and (collection_completeness_passed if require_complete else True)
    summary = {
        **base_summary,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "round_id": round_id,
        "runtime_task_count": len(runtime_rows),
        "n_canonical_rows": len(canonical_rows),
        "outside_assignment_submission_count": outside_count,
        "duplicate_worker_task_submission_count": duplicate_count,
        "reserve_realized_submission_count": reserve_count,
        "missing_submission_count": missing_submission_count,
        "runtime_key_collision_count": len(collision_rows),
        "planned_mapping_missing_count": planned_missing_count,
        **active_counts,
        **active_audit_counts,
        "active_log_primary_missing_count": active_counts["active_time_primary_ineligible_count"],
        "active_log_missing_count": active_counts["active_time_log_missing_count"],
        "active_log_missing_rate": round(active_counts["active_time_log_missing_count"] / len(canonical_rows), 6) if canonical_rows else 0.0,
        "canonical_csv": str(output_dir / "c1_canonical_annotations.csv"),
        "raw_input_manifest": str(raw_manifest),
        "primary_active_time_policy": "owner-validated project+task+worker+annotation exact log match only; task fallback and lead_time never primary",
        "structural_integrity_passed": structural_integrity_passed,
        "collection_completeness_passed": collection_completeness_passed,
        "require_complete": require_complete,
        "passed": passed,
        "passed_semantics": "structural_only_not_collection_complete" if not require_complete else "structural_and_collection_complete",
        "collision_output_use": "debug_only_do_not_use_downstream" if collision_rows else "downstream_eligible_if_other_blockers_absent",
        "canonical_evidence_sidecars": canonical_evidence_summary,
        "geometry_sidecars": geometry_summary,
        "model_issue_harmonization": harmonization_summary,
        "formal_c1_annotation_data_present": bool(input_status == "formal" and canonical_rows),
        "interpretation_allowed": False,
        "blockers": [
            name
            for name, count in (
                ("outside_assignment_submission_detected", outside_count),
                ("duplicate_worker_task_submission_detected", duplicate_count),
                ("reserve_realized_submission_detected", reserve_count),
                ("runtime_key_collision_detected", len(collision_rows)),
                ("planned_mapping_missing", planned_missing_count),
            )
            if count
        ],
        "warnings": ["unknown_annotation_audit_present"] if active_audit_counts["rows_with_unknown_audit_count"] else [],
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
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--input-status", choices=["dry_run", "formal"], default="dry_run")
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
        require_complete=args.require_complete,
        input_status=args.input_status,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
