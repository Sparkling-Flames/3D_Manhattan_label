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
    "response_hash",
    "source_export_sha256",
    "annotation_version_id",
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
    "independence_status",
    "independence_audit_status",
    "independence_audit_reason",
    "independence_audit_source",
    "independence_audit_source_sha256",
    "independence_audit_snapshot_path",
    "independence_audit_snapshot_sha256",
    "independence_audit_identity",
    "parent_annotation_id",
    "parent_owner_id",
    "parent_same_task",
    "parent_cross_owner",
    "parent_precedes",
    "parent_geometry_hash_match",
    "parent_derived",
    "copy_risk_status",
    "source_export",
    "raw_canonical_annotation_id",
    "duplicate_annotation_ids",
    "duplicate_group_size",
    "duplicate_geometry_type",
    "duplicate_review_status",
    "duplicate_decision",
    "process_disposition",
    "timing_disposition",
    "reviewed_by",
    "reviewed_at",
    "selected_response_hash",
    "selected_source_export_sha256",
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


def _frozen_audit_bool(value: Any) -> str:
    """Preserve a frozen audit boolean without treating the string 'false' as truthy."""
    if isinstance(value, bool):
        return bool_text(value)
    text = safe(value).lower()
    if text in {"true", "1", "yes"}:
        return "true"
    if text in {"false", "0", "no"}:
        return "false"
    return ""


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
    independence_audit_csv: Path | None = None,
    retrospective_provenance_amendment_csv: Path | None = None,
    duplicate_adjudication_csv: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assigned, internal = assignment_sets(manual_assignment, semi_assignment, worker_distribution)
    runtime_rows, runtime_lookup, collision_rows = build_runtime_task_mapping(export_paths, planned_task_mapping)
    duplicate_decisions: dict[tuple[str, str, str], dict[str, str]] = {}
    if duplicate_adjudication_csv and duplicate_adjudication_csv.exists():
        for decision in read_csv(duplicate_adjudication_csv):
            key = (safe(decision.get("project_id")), safe(decision.get("ls_runtime_task_id") or decision.get("runtime_task_id")), safe(decision.get("worker_id")))
            if not all(key) or key in duplicate_decisions:
                raise ValueError("duplicate adjudication identity must be complete and unique")
            duplicate_decisions[key] = decision
    canonical_base, duplicate_base, base_summary = build_canonical_tables(
        export_paths, active_log, duplicate_review_mode=True, duplicate_decisions=duplicate_decisions, round_id=round_id
    )
    active_times = load_active_logs(str(active_log), annotation_owner_map=build_annotation_owner_map(export_paths), policy="calibration") if active_log else {}
    raw_manifest = snapshot_inputs_unique(
        export_paths + ([active_log] if active_log else []) + [manual_assignment, semi_assignment, worker_distribution, planned_task_mapping] + ([independence_audit_csv] if independence_audit_csv else []) + ([retrospective_provenance_amendment_csv] if retrospective_provenance_amendment_csv else []) + ([duplicate_adjudication_csv] if duplicate_adjudication_csv else []),
        output_dir,
        completion_basis="c1_closeout_canonicalization_snapshot",
    )
    snapshot_rows = read_csv(raw_manifest)
    audit_snapshot = next((item for item in snapshot_rows if independence_audit_csv and Path(item.get("source_path", "")).resolve() == independence_audit_csv.resolve()), {})
    amendment_snapshot = next((item for item in snapshot_rows if retrospective_provenance_amendment_csv and Path(item.get("source_path", "")).resolve() == retrospective_provenance_amendment_csv.resolve()), {})
    independence_audit: dict[tuple[str, str, str, str], dict[str, str]] = {}
    independence_duplicates: set[tuple[str, str, str, str]] = set()
    independence_audit_row_count = 0
    independence_audit_missing_identity_count = 0
    audit_input = Path(audit_snapshot["snapshot_path"]) if audit_snapshot.get("snapshot_path") else None
    if audit_input and audit_input.exists():
        with audit_input.open("r", newline="", encoding="utf-8-sig") as handle:
            for audit in csv.DictReader(handle):
                independence_audit_row_count += 1
                key = (safe(audit.get("project_id")), safe(audit.get("ls_runtime_task_id") or audit.get("runtime_task_id")), safe(audit.get("worker_id") or audit.get("annotator_id")), safe(audit.get("raw_annotation_id") or audit.get("raw_canonical_annotation_id") or audit.get("annotation_id")))
                if not all(key):
                    independence_audit_missing_identity_count += 1
                    continue
                if key in independence_audit:
                    independence_duplicates.add(key)
                independence_audit[key] = audit

    duplicate_group_risk: dict[tuple[str, str, str], str] = {}
    for duplicate in duplicate_base:
        group = (safe(duplicate.get("project_id")), safe(duplicate.get("task_id")), safe(duplicate.get("annotator_id")))
        audits = [independence_audit.get((*group, annotation_id), {}) for annotation_id in safe(duplicate.get("all_annotation_ids")).split(";") if annotation_id]
        if any(safe(item.get("independence_status")) == "non_independent_confirmed" for item in audits):
            duplicate_group_risk[group] = "non_independent_confirmed"
            duplicate["duplicate_geometry_type"] = "parent_copy_non_independence_related"
        elif any(_frozen_audit_bool(item.get("parent_derived")) == "true" or safe(item.get("copy_risk_status")).lower() not in {"", "cleared", "none", "no_risk"} for item in audits):
            duplicate_group_risk[group] = "not_evaluable"
            duplicate["duplicate_geometry_type"] = "parent_copy_non_independence_related"

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
        identity = (project_id, runtime_task_id, worker_id, raw_annotation_id)
        audit = independence_audit.get(identity, {})
        audit_status = safe(audit.get("independence_status")).lower()
        group_risk = duplicate_group_risk.get((project_id, runtime_task_id, worker_id))
        if group_risk:
            audit_status, audit_reason = group_risk, "duplicate_group_parent_copy_or_independence_risk"
        elif identity in independence_duplicates:
            audit_status, audit_reason = "not_evaluable", "duplicate_independence_audit_identity"
        elif audit_status in {"independent", "non_independent_confirmed"}:
            audit_reason = "audit_joined"
        else:
            audit_status, audit_reason = "not_evaluable", "missing_or_unresolved_independence_audit"
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
            "response_hash": row.get("response_hash", ""),
            "source_export_sha256": row.get("source_export_sha256", ""),
            "annotation_version_id": row.get("annotation_version_id", ""),
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
            "duplicate_worker_task_submission": bool_text(safe(row.get("duplicate_review_status")) == "pending"),
            "independence_status": audit_status,
            "independence_audit_status": audit_status,
            "independence_audit_reason": audit_reason,
            "independence_audit_source": str(independence_audit_csv) if audit else "",
            "independence_audit_source_sha256": audit_snapshot.get("sha256", ""),
            "independence_audit_snapshot_path": audit_snapshot.get("snapshot_path", ""),
            "independence_audit_snapshot_sha256": sha256_file(Path(audit_snapshot["snapshot_path"])) if audit_snapshot.get("snapshot_path") else "",
            "independence_audit_identity": "|".join(identity),
            "parent_annotation_id": safe(audit.get("parent_annotation_id")) if audit else "",
            "parent_owner_id": safe(audit.get("parent_owner_id")) if audit else "",
            "parent_same_task": _frozen_audit_bool(audit.get("parent_same_task")) if audit else "",
            "parent_cross_owner": _frozen_audit_bool(audit.get("parent_cross_owner")) if audit else "",
            "parent_precedes": _frozen_audit_bool(audit.get("parent_precedes")) if audit else "",
            "parent_geometry_hash_match": _frozen_audit_bool(audit.get("parent_geometry_hash_match")) if audit else "",
            "parent_derived": _frozen_audit_bool(audit.get("parent_derived")) if audit else "",
            "copy_risk_status": safe(audit.get("copy_risk_status")) if audit else "",
            "source_export": row.get("source_export", ""),
            "raw_canonical_annotation_id": raw_annotation_id,
            "duplicate_annotation_ids": row.get("duplicate_annotation_ids", ""),
            "duplicate_group_size": row.get("duplicate_group_size", ""),
            "duplicate_geometry_type": row.get("duplicate_geometry_type", ""),
            "duplicate_review_status": row.get("duplicate_review_status", "not_required"),
            "duplicate_decision": row.get("duplicate_decision", ""),
            "process_disposition": row.get("process_disposition", ""),
            "timing_disposition": row.get("timing_disposition", ""),
            "reviewed_by": row.get("reviewed_by", ""),
            "reviewed_at": row.get("reviewed_at", ""),
            "selected_response_hash": row.get("selected_response_hash", ""),
            "selected_source_export_sha256": row.get("selected_source_export_sha256", ""),
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

    resolved_excluded_keys = set()
    for duplicate in duplicate_base:
        if safe(duplicate.get("duplicate_review_status")) == "resolved" and safe(duplicate.get("duplicate_decision")) in {"exclude_group", "forensic_only"}:
            info = runtime_lookup.get((safe(duplicate.get("project_id")), safe(duplicate.get("task_id"))), {})
            resolved_excluded_keys.add((safe(duplicate.get("annotator_id")), safe(info.get("task_id")), safe(info.get("base_task_id")), safe(info.get("dataset_group"))))
    realized_assigned_keys = {assignment_key(row) for row in realized_rows if assignment_key(row) in assigned} | resolved_excluded_keys
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
    review_queue_rows: list[dict[str, Any]] = []
    forensic_rows: list[dict[str, Any]] = []
    for group in duplicate_rows:
        versions = json.loads(group.get("version_rows_json") or "[]")
        for version in versions:
            review_queue_rows.append({
                **version,
                "round_id": round_id,
                "ls_runtime_task_id": group.get("ls_runtime_task_id", ""),
                "task_id": group.get("task_id", ""),
                "base_task_id": group.get("base_task_id", ""),
                "dataset_group": group.get("dataset_group", ""),
                "worker_id": group.get("worker_id", ""),
                "duplicate_group_type": group.get("duplicate_geometry_type", ""),
                "current_review_status": group.get("duplicate_review_status", ""),
                "manual_review_required": "true" if group.get("duplicate_review_status") == "pending" else "false",
            })
            if group.get("duplicate_review_status") in {"resolved", "auto_resolved_input_duplicate"} and version.get("annotation_id") != group.get("raw_canonical_annotation_id"):
                forensic_rows.append({**version, "group_key": f"{group.get('project_id')}|{group.get('ls_runtime_task_id')}|{group.get('worker_id')}", "forensic_reason": "not_selected_canonical_version", "duplicate_review_status": group.get("duplicate_review_status", "")})
    duplicate_template_rows = [
        {
            "round_id": row.get("round_id", round_id), "project_id": row.get("project_id", ""), "ls_runtime_task_id": row.get("ls_runtime_task_id", ""), "worker_id": row.get("worker_id", ""),
            "all_annotation_ids": row.get("all_annotation_ids", ""), "duplicate_group_type": row.get("duplicate_geometry_type", ""),
            "current_review_status": row.get("duplicate_review_status", ""), "decision": "", "selected_annotation_id": "", "selected_response_hash": "", "selected_source_export_sha256": "", "process_disposition": "", "timing_disposition": "", "reviewed_by": "", "reviewed_at": "", "review_notes": "",
        }
        for row in duplicate_rows if safe(row.get("duplicate_review_status")) == "pending"
    ]
    write_csv(output_dir / "c1_runtime_task_mapping.csv", runtime_rows, RUNTIME_MAPPING_FIELDS)
    write_csv(output_dir / "c1_runtime_key_collision_audit.csv", collision_rows, RUNTIME_COLLISION_FIELDS)
    write_csv(output_dir / "c1_canonical_annotations.csv", canonical_rows, CANONICAL_FIELDS)
    write_csv(output_dir / "c1_duplicate_annotation_audit.csv", duplicate_rows)
    write_csv(output_dir / "c1_duplicate_annotation_review_queue.csv", review_queue_rows)
    write_csv(output_dir / "c1_duplicate_annotation_forensic_audit.csv", forensic_rows)
    write_csv(output_dir / "c1_duplicate_adjudication_template.csv", duplicate_template_rows, ["round_id", "project_id", "ls_runtime_task_id", "worker_id", "all_annotation_ids", "duplicate_group_type", "current_review_status", "decision", "selected_annotation_id", "selected_response_hash", "selected_source_export_sha256", "process_disposition", "timing_disposition", "reviewed_by", "reviewed_at", "review_notes"])
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
        retrospective_amendment_csv=Path(amendment_snapshot["snapshot_path"]) if amendment_snapshot.get("snapshot_path") else None,
    )

    outside_count = sum(row["outside_assignment_submission"] == "true" for row in canonical_rows)
    duplicate_count = sum(row["duplicate_worker_task_submission"] == "true" for row in canonical_rows)
    pending_duplicate_count = sum(safe(row.get("duplicate_review_status")) == "pending" for row in duplicate_rows)
    reserve_count = sum(row["reserve_realized_submission"] == "true" for row in canonical_rows)
    active_counts = _active_counts(canonical_rows)
    active_audit_counts = active_time_audit_summary(canonical_rows)
    planned_missing_count = sum(row["planned_mapping_status"] == "planned_mapping_missing" for row in runtime_rows)
    missing_submission_count = sum(row["missing_submission"] == "true" for row in realized_rows)
    canonical_evidence_blocked = bool(canonical_evidence_summary.get("blockers"))
    structural_integrity_passed = outside_count == 0 and pending_duplicate_count == 0 and reserve_count == 0 and not collision_rows and not planned_missing_count and not canonical_evidence_blocked
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
        "duplicate_review_pending_count": pending_duplicate_count,
        "duplicate_review_resolved_count": sum(safe(row.get("duplicate_review_status")) == "resolved" for row in duplicate_rows),
        "duplicate_input_repeat_count": sum(int(row.get("repeated_export_row_count") or 0) for row in duplicate_rows),
        "duplicate_adjudication_csv": str(duplicate_adjudication_csv or ""),
        "duplicate_review_queue_csv": str(output_dir / "c1_duplicate_annotation_review_queue.csv"),
        "duplicate_forensic_audit_csv": str(output_dir / "c1_duplicate_annotation_forensic_audit.csv"),
        "duplicate_adjudication_template_csv": str(output_dir / "c1_duplicate_adjudication_template.csv"),
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
        "raw_input_manifest_sha256": sha256_file(raw_manifest),
        "independence_audit_source_path": str(independence_audit_csv or ""),
        "independence_audit_source_sha256": audit_snapshot.get("sha256", ""),
        "independence_audit_snapshot_path": audit_snapshot.get("snapshot_path", ""),
        "independence_audit_snapshot_sha256": sha256_file(Path(audit_snapshot["snapshot_path"])) if audit_snapshot.get("snapshot_path") else "",
        "independence_audit_row_count": independence_audit_row_count,
        "independence_audit_valid_count": sum(row["independence_status"] in {"independent", "non_independent_confirmed"} for row in canonical_rows),
        "independence_audit_duplicate_count": len(independence_duplicates),
        "independence_audit_missing_identity_count": independence_audit_missing_identity_count,
        "independence_audit_unresolved_count": sum(row["independence_status"] == "not_evaluable" for row in canonical_rows),
        "retrospective_amendment_source_path": str(retrospective_provenance_amendment_csv or ""),
        "retrospective_amendment_source_sha256": amendment_snapshot.get("sha256", ""),
        "retrospective_amendment_snapshot_path": amendment_snapshot.get("snapshot_path", ""),
        "retrospective_amendment_snapshot_sha256": sha256_file(Path(amendment_snapshot["snapshot_path"])) if amendment_snapshot.get("snapshot_path") else "",
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
                ("duplicate_review_pending", pending_duplicate_count),
                ("reserve_realized_submission_detected", reserve_count),
                ("runtime_key_collision_detected", len(collision_rows)),
                ("planned_mapping_missing", planned_missing_count),
                ("duplicate_independence_audit_identity", len(independence_duplicates)),
                ("independence_audit_missing_identity", independence_audit_missing_identity_count),
                ("independence_not_evaluable", sum(row["independence_status"] == "not_evaluable" for row in canonical_rows)),
                *[(f"amendment_{key}", count) for key, count in (harmonization_summary.get("amendment_blockers") or {}).items()],
                *[(f"canonical_evidence_{blocker}", 1) for blocker in (canonical_evidence_summary.get("blockers") or [])],
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
    parser.add_argument("--independence-audit-csv", type=Path)
    parser.add_argument("--retrospective-provenance-amendment-csv", type=Path)
    parser.add_argument("--duplicate-adjudication-csv", type=Path)
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
        independence_audit_csv=args.independence_audit_csv,
        retrospective_provenance_amendment_csv=args.retrospective_provenance_amendment_csv,
        duplicate_adjudication_csv=args.duplicate_adjudication_csv,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
