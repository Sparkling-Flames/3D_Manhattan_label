from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.quality_core.active_time import load_active_logs, lookup_active_log_entry

DEFAULT_REBUILD_DIR = Path("analysis_results/calibration_rebuild_20260702")
DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c1_live_monitor")

MANUAL_ASSIGNMENT_DEFAULT = DEFAULT_REBUILD_DIR / "assignment_manifest_C1_manual_draft_v3_1.csv"
SEMI_ASSIGNMENT_DEFAULT = DEFAULT_REBUILD_DIR / "assignment_manifest_C1_semi_draft_v3_1.csv"
WORKER_DISTRIBUTION_DEFAULT = DEFAULT_REBUILD_DIR / "worker_distribution_internal_manifest_v3_1.csv"
PLANNED_TASK_MAPPING_DEFAULT = DEFAULT_REBUILD_DIR / "ls_project_mapping_audit_v3_1.csv"
ACTIVE_LOG_DEFAULT = Path("active_logs/new_server")

C1_GROUP_BY_SOURCE_DRAFT = {
    "anchor": ("Calibration_anchor", "C1_anchor_all", "A"),
    "core": ("Calibration_core", "C1_core_all", "B"),
    "semi": ("Calibration_semi", "C1_semi", "C"),
    "reserve": ("Calibration_reserve", "C2_reserve_draft_only", "R"),
}
C1_PROJECT_TO_GROUP = {
    "C1_anchor_all": ("Calibration_anchor", "A"),
    "C1_core_all": ("Calibration_core", "B"),
    "C1_semi": ("Calibration_semi", "C"),
    "C2_reserve_draft_only": ("Calibration_reserve", "R"),
}
PRIMARY_ACTIVE_TIME_STATUS_ANNOTATION = "project+task+annotator+annotation"
PRIMARY_ACTIVE_TIME_STATUS_TASK = "project+task+annotator"

RUNTIME_MAPPING_FIELDS = [
    "source_export",
    "project_id",
    "ls_runtime_task_id",
    "planned_project_name",
    "planned_inner_id",
    "task_code",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "image",
    "title",
    "planned_mapping_status",
    "runtime_binding_status",
]

RUNTIME_COLLISION_FIELDS = [
    "project_id",
    "ls_runtime_task_id",
    "first_source_export",
    "collision_source_export",
    "first_task_id",
    "collision_task_id",
    "first_base_task_id",
    "collision_base_task_id",
    "first_dataset_group",
    "collision_dataset_group",
    "collision_reason",
]

REALIZED_FIELDS = [
    "source_export",
    "project_id",
    "ls_runtime_task_id",
    "planned_project_name",
    "planned_inner_id",
    "task_code",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "worker_id",
    "annotation_id",
    "active_time",
    "active_time_source",
    "active_time_match_status",
    "primary_active_time_eligible",
    "sensitivity_active_time_eligible",
    "active_time_source_file",
    "active_time_session_count",
    "active_time_event_count",
    "assigned_expected",
    "appears_in_internal_distribution",
    "outside_assignment_submission",
    "duplicate_worker_task_submission",
    "missing_submission",
    "reserve_realized_submission",
]


def safe(value: Any) -> str:
    return str(value or "").strip()


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", encoding="utf-8", newline="") as f:
        if not fields:
            f.write("")
            return
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_export(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} is not a Label Studio task-list export")
    return payload


def worker_id(annotation: dict[str, Any]) -> str:
    completed_by = annotation.get("completed_by") or annotation.get("created_by") or annotation.get("user")
    if isinstance(completed_by, dict):
        for key in ("id", "username", "email", "pk"):
            value = safe(completed_by.get(key))
            if value:
                return value
    return safe(completed_by) or safe(annotation.get("worker_id")) or "unknown"


def annotation_id(annotation: dict[str, Any], index: int) -> str:
    return safe(annotation.get("id")) or f"annotation_index_{index}"


def task_data(task: dict[str, Any]) -> dict[str, Any]:
    data = task.get("data")
    return data if isinstance(data, dict) else {}


def normalize_group(data: dict[str, Any]) -> tuple[str, str, str]:
    source_draft = safe(data.get("source_draft")).lower()
    if source_draft in C1_GROUP_BY_SOURCE_DRAFT:
        return C1_GROUP_BY_SOURCE_DRAFT[source_draft]
    raw_group = safe(data.get("dataset_group"))
    if raw_group in C1_PROJECT_TO_GROUP:
        dataset_group, prefix = C1_PROJECT_TO_GROUP[raw_group]
        return dataset_group, raw_group, prefix
    return raw_group, safe(data.get("planned_project_name")) or raw_group, ""


def load_planned_mapping(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    rows = read_csv(path) if path else []
    out: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        dataset_group = safe(row.get("intended_project_group") or row.get("dataset_group"))
        base_task_id = safe(row.get("base_task_id"))
        task_id = safe(row.get("task_id"))
        for key_value in (base_task_id, task_id):
            if dataset_group and key_value:
                out[(dataset_group, key_value)] = row
    return out


def task_code(prefix: str, inner_id: str) -> str:
    if not prefix or not inner_id:
        return ""
    try:
        return f"{prefix}-{int(inner_id):03d}"
    except ValueError:
        return f"{prefix}-{inner_id}"


def assignment_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        safe(row.get("worker_id")),
        safe(row.get("task_id")),
        safe(row.get("base_task_id")),
        safe(row.get("dataset_group")),
    )


def _runtime_key(row: dict[str, Any]) -> tuple[str, str]:
    return safe(row.get("project_id")), safe(row.get("ls_runtime_task_id"))


def _runtime_collision_row(first: dict[str, str], collision: dict[str, str]) -> dict[str, str]:
    return {
        "project_id": safe(first.get("project_id")),
        "ls_runtime_task_id": safe(first.get("ls_runtime_task_id")),
        "first_source_export": safe(first.get("source_export")),
        "collision_source_export": safe(collision.get("source_export")),
        "first_task_id": safe(first.get("task_id")),
        "collision_task_id": safe(collision.get("task_id")),
        "first_base_task_id": safe(first.get("base_task_id")),
        "collision_base_task_id": safe(collision.get("base_task_id")),
        "first_dataset_group": safe(first.get("dataset_group")),
        "collision_dataset_group": safe(collision.get("dataset_group")),
        "collision_reason": "duplicate_project_runtime_task_key",
    }


def build_runtime_task_mapping(
    export_paths: list[Path],
    planned_mapping_path: Path | None = None,
) -> tuple[list[dict[str, str]], dict[tuple[str, str], dict[str, str]], list[dict[str, str]]]:
    planned = load_planned_mapping(planned_mapping_path)
    rows: list[dict[str, str]] = []
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    collisions: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for export_path in export_paths:
        for index, task in enumerate(load_export(export_path), start=1):
            data = task_data(task)
            project_id = safe(task.get("project") or task.get("project_id"))
            runtime_task_id = safe(task.get("id") or task.get("task_id")) or f"task_index_{index}"
            dataset_group, planned_project_name, prefix = normalize_group(data)
            task_id = safe(data.get("task_id") or task.get("task_id") or runtime_task_id)
            base_task_id = safe(data.get("base_task_id") or task_id)
            planned_row = planned.get((dataset_group, base_task_id)) or planned.get((dataset_group, task_id)) or {}
            inner_id = safe(planned_row.get("inner_id") or data.get("inner_id") or task.get("inner_id"))
            planned_status = safe(planned_row.get("mapping_status")) or ("planned_mapping_missing" if planned_mapping_path else "planned_mapping_not_provided")
            row = {
                "source_export": str(export_path),
                "project_id": project_id,
                "ls_runtime_task_id": runtime_task_id,
                "planned_project_name": safe(planned_row.get("planned_project_name")) or planned_project_name,
                "planned_inner_id": inner_id,
                "task_code": safe(planned_row.get("task_code")) or task_code(prefix, inner_id),
                "task_id": task_id,
                "base_task_id": base_task_id,
                "dataset_group": dataset_group,
                "condition": safe(data.get("condition")),
                "image": safe(data.get("image")),
                "title": safe(data.get("title")),
                "planned_mapping_status": planned_status,
                "runtime_binding_status": "bound_from_export_and_planned_mapping" if planned_row else "bound_from_export_planned_missing",
            }
            key = (project_id, runtime_task_id)
            if key in lookup:
                collisions.append(_runtime_collision_row(lookup[key], row))
                continue
            lookup[key] = row
            if key not in seen:
                rows.append(row)
                seen.add(key)
    return rows, lookup, collisions


def build_annotation_owner_map(export_paths: list[Path]) -> dict[Any, str]:
    owners: dict[Any, str] = {}
    for export_path in export_paths:
        for task_index, task in enumerate(load_export(export_path), start=1):
            project_id = safe(task.get("project") or task.get("project_id"))
            runtime_task_id = safe(task.get("id") or task.get("task_id")) or f"task_index_{task_index}"
            annotations = task.get("annotations") or []
            if not isinstance(annotations, list):
                continue
            for ann_index, ann in enumerate(annotations, start=1):
                if not isinstance(ann, dict):
                    continue
                ann_id = annotation_id(ann, ann_index)
                owner = worker_id(ann)
                for key in ((project_id, runtime_task_id, ann_id), (runtime_task_id, ann_id), ann_id):
                    previous = owners.get(key)
                    owners[key] = owner if previous in (None, owner) else "__ambiguous_owner__"
    return owners


def assignment_sets(manual_path: Path, semi_path: Path, internal_path: Path) -> tuple[set[tuple[str, str, str, str]], set[tuple[str, str, str, str]]]:
    assigned = {
        (safe(row.get("worker_id")), safe(row.get("task_id")), safe(row.get("base_task_id")), safe(row.get("dataset_group")))
        for row in read_csv(manual_path) + read_csv(semi_path)
        if safe(row.get("worker_id"))
    }
    internal = {
        (safe(row.get("worker_id")), safe(row.get("task_id")), safe(row.get("base_task_id")), safe(row.get("dataset_group")))
        for row in read_csv(internal_path)
        if safe(row.get("worker_id"))
    }
    return assigned, internal


def active_time_policy(source: str, status: str, session_count: int = 0, duplicate_time_ambiguous: bool = False) -> tuple[bool, bool]:
    if source == "log" and status == PRIMARY_ACTIVE_TIME_STATUS_ANNOTATION:
        return True, True
    if source == "log" and status == PRIMARY_ACTIVE_TIME_STATUS_TASK and session_count == 1 and not duplicate_time_ambiguous:
        return True, True
    if source in {"log", "lead_time_fallback"}:
        return False, True
    return False, False


def active_time_for_annotation(
    active_times: dict,
    project_id: str,
    runtime_task_id: str,
    worker: str,
    ann_id: str,
    lead_time_seconds: float,
) -> dict[str, Any]:
    entry, status = lookup_active_log_entry(active_times, project_id, runtime_task_id, worker, annotation_id=ann_id)
    source = "missing"
    value: str | float = ""
    session_count = 0
    if entry:
        source = "log"
        value = float(entry.get("active_time_value", 0.0))
        session_count = int(entry.get("active_time_session_count", 0) or 0)
        source_file = safe(entry.get("active_time_source_file"))
        event_count = int(entry.get("active_time_event_count", 0) or 0)
    elif lead_time_seconds > 0:
        source = "lead_time_fallback"
        value = float(lead_time_seconds)
        source_file = ""
        event_count = 0
    else:
        source_file = ""
        event_count = 0
    primary, sensitivity = active_time_policy(source, status, session_count)
    return {
        "active_time": value,
        "active_time_source": source,
        "active_time_match_status": status,
        "active_time_source_file": source_file,
        "active_time_session_count": session_count,
        "active_time_event_count": event_count,
        "primary_active_time_eligible": primary,
        "sensitivity_active_time_eligible": sensitivity,
    }


def lead_time(annotation: dict[str, Any]) -> float:
    try:
        return float(annotation.get("lead_time") or 0)
    except (TypeError, ValueError):
        return 0.0


def is_reserve(row: dict[str, str]) -> bool:
    return row.get("dataset_group") == "Calibration_reserve" or str(row.get("planned_project_name", "")).startswith("C2_reserve")


def build_realized_rows(
    export_paths: list[Path],
    runtime_lookup: dict[tuple[str, str], dict[str, str]],
    active_log_path: Path | None,
    assigned: set[tuple[str, str, str, str]],
    internal: set[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    active_times = load_active_logs(str(active_log_path), annotation_owner_map=build_annotation_owner_map(export_paths)) if active_log_path else {}
    rows: list[dict[str, Any]] = []
    for export_path in export_paths:
        for task_index, task in enumerate(load_export(export_path), start=1):
            project_id = safe(task.get("project") or task.get("project_id"))
            runtime_task_id = safe(task.get("id") or task.get("task_id")) or f"task_index_{task_index}"
            info = runtime_lookup.get((project_id, runtime_task_id), {})
            annotations = task.get("annotations") or []
            if not isinstance(annotations, list):
                continue
            for ann_index, ann in enumerate(annotations, start=1):
                if not isinstance(ann, dict):
                    continue
                worker = worker_id(ann)
                ann_id = annotation_id(ann, ann_index)
                key = (worker, safe(info.get("task_id")), safe(info.get("base_task_id")), safe(info.get("dataset_group")))
                active = active_time_for_annotation(active_times, project_id, runtime_task_id, worker, ann_id, lead_time(ann))
                row = {
                    **{field: info.get(field, "") for field in RUNTIME_MAPPING_FIELDS if field != "source_export"},
                    "source_export": str(export_path),
                    "worker_id": worker,
                    "annotation_id": ann_id,
                    **active,
                    "assigned_expected": key in assigned,
                    "appears_in_internal_distribution": key in internal,
                    "outside_assignment_submission": key not in assigned,
                    "duplicate_worker_task_submission": False,
                    "missing_submission": False,
                    "reserve_realized_submission": is_reserve(info),
                }
                rows.append(row)
    counts = Counter((row["project_id"], row["ls_runtime_task_id"], row["worker_id"]) for row in rows)
    for row in rows:
        duplicate = counts[(row["project_id"], row["ls_runtime_task_id"], row["worker_id"])] > 1
        row["duplicate_worker_task_submission"] = duplicate
        if duplicate and row["active_time_match_status"] == PRIMARY_ACTIVE_TIME_STATUS_TASK:
            primary, sensitivity = active_time_policy(
                safe(row.get("active_time_source")),
                safe(row.get("active_time_match_status")),
                int(row.get("active_time_session_count") or 0),
                duplicate_time_ambiguous=True,
            )
            row["primary_active_time_eligible"] = primary
            row["sensitivity_active_time_eligible"] = sensitivity
    return rows


def realized_vs_assigned_rows(
    realized_rows: list[dict[str, Any]],
    assigned: set[tuple[str, str, str, str]],
    internal: set[tuple[str, str, str, str]],
) -> list[dict[str, Any]]:
    rows = list(realized_rows)
    realized_assigned_keys = {assignment_key(row) for row in realized_rows if assignment_key(row) in assigned}
    for worker, task_id, base_task_id, dataset_group in sorted(assigned - realized_assigned_keys):
        key = (worker, task_id, base_task_id, dataset_group)
        rows.append(
            {
                "source_export": "",
                "project_id": "",
                "ls_runtime_task_id": "",
                "planned_project_name": "",
                "planned_inner_id": "",
                "task_code": "",
                "task_id": task_id,
                "base_task_id": base_task_id,
                "dataset_group": dataset_group,
                "condition": "",
                "worker_id": worker,
                "annotation_id": "",
                "active_time": "",
                "active_time_source": "",
                "active_time_match_status": "not_submitted",
                "primary_active_time_eligible": False,
                "sensitivity_active_time_eligible": False,
                "active_time_source_file": "",
                "active_time_session_count": "",
                "active_time_event_count": "",
                "assigned_expected": True,
                "appears_in_internal_distribution": key in internal,
                "outside_assignment_submission": False,
                "duplicate_worker_task_submission": False,
                "missing_submission": True,
                "reserve_realized_submission": False,
            }
        )
    return rows


def snapshot_manifest(export_paths: list[Path], active_log_path: Path | None, output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    snapshot_dir = output_dir / "raw_snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    def add_file(path: Path, source_kind: str) -> None:
        exists = path.exists() and path.is_file()
        snapshot_path = ""
        digest = ""
        size = ""
        mtime = ""
        if exists:
            digest = sha256_file(path)
            snapshot_path = str(snapshot_dir / f"{len(rows) + 1:03d}_{digest[:12]}_{path.name}")
            shutil.copy2(path, snapshot_path)
            snap = Path(snapshot_path)
            size = str(snap.stat().st_size)
            mtime = datetime.fromtimestamp(snap.stat().st_mtime, timezone.utc).isoformat()
        rows.append(
            {
                "source_path": str(path),
                "snapshot_path": snapshot_path,
                "source_kind": source_kind,
                "exists": bool_text(exists),
                "bytes": size,
                "sha256": digest,
                "mtime_utc": mtime,
            }
        )

    for path in export_paths:
        add_file(path, "label_studio_export_snapshot")
    if active_log_path:
        _resolved, files = resolve_active_log_files(active_log_path)
        if files:
            for path in files:
                add_file(path, "active_log_snapshot")
        else:
            rows.append(
                {
                    "source_path": str(active_log_path),
                    "snapshot_path": "",
                    "source_kind": "active_log_snapshot",
                    "exists": "false",
                    "bytes": "",
                    "sha256": "",
                    "mtime_utc": "",
                }
            )
    return rows


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def summarize_by_worker(rows: list[dict[str, Any]], assigned: set[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    assigned_by_worker = Counter(worker for worker, _task, _base, _group in assigned)
    realized_assigned_keys = {assignment_key(row) for row in rows if assignment_key(row) in assigned}
    realized_by_worker = Counter(row["worker_id"] for row in rows)
    completed_by_worker = Counter(worker for worker, _task, _base, _group in realized_assigned_keys)
    outside_by_worker = Counter(row["worker_id"] for row in rows if row["outside_assignment_submission"])
    duplicate_by_worker = Counter(row["worker_id"] for row in rows if row["duplicate_worker_task_submission"])
    missing_assignment_by_worker = Counter(worker for worker, _task, _base, _group in assigned - realized_assigned_keys)
    workers = sorted(set(assigned_by_worker) | set(realized_by_worker))
    return [
        {
            "worker_id": worker,
            "assigned_task_count": assigned_by_worker[worker],
            "realized_submission_count": realized_by_worker[worker],
            "completed_assigned_task_count": completed_by_worker[worker],
            "missing_assigned_task_count": missing_assignment_by_worker[worker],
            "outside_assignment_submission_count": outside_by_worker[worker],
            "duplicate_worker_task_submission_count": duplicate_by_worker[worker],
        }
        for worker in workers
    ]


def summarize_by_task(rows: list[dict[str, Any]], assigned: set[tuple[str, str, str, str]]) -> list[dict[str, Any]]:
    assigned_by_task = Counter((task, base, group) for _worker, task, base, group in assigned)
    realized_assigned_keys = {assignment_key(row) for row in rows if assignment_key(row) in assigned}
    realized_by_task = Counter((row["task_id"], row["base_task_id"], row["dataset_group"]) for row in rows)
    completed_by_task = Counter((task, base, group) for _worker, task, base, group in realized_assigned_keys)
    missing_by_task = Counter((task, base, group) for _worker, task, base, group in assigned - realized_assigned_keys)
    task_keys = sorted(set(assigned_by_task) | set(realized_by_task))
    return [
        {
            "task_id": task,
            "base_task_id": base,
            "dataset_group": group,
            "assigned_worker_count": assigned_by_task[(task, base, group)],
            "realized_submission_count": realized_by_task[(task, base, group)],
            "completed_assigned_submission_count": completed_by_task[(task, base, group)],
            "missing_assigned_submission_count": missing_by_task[(task, base, group)],
        }
        for task, base, group in task_keys
    ]


def _active_counts(group: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "active_time_primary_ineligible_count": sum(not bool(row["primary_active_time_eligible"]) for row in group),
        "active_time_log_missing_count": sum(safe(row.get("active_time_source")) == "missing" for row in group),
        "active_time_task_level_fallback_count": sum(
            safe(row.get("active_time_source")) == "log"
            and safe(row.get("active_time_match_status")) == PRIMARY_ACTIVE_TIME_STATUS_TASK
            and not bool(row.get("primary_active_time_eligible"))
            for row in group
        ),
        "active_time_lead_time_fallback_count": sum(safe(row.get("active_time_source")) == "lead_time_fallback" for row in group),
        "active_time_ambiguous_count": sum(
            "ambiguous" in safe(row.get("active_time_match_status"))
            or "mismatch" in safe(row.get("active_time_match_status"))
            or (
                bool(row.get("duplicate_worker_task_submission"))
                and safe(row.get("active_time_match_status")) == PRIMARY_ACTIVE_TIME_STATUS_TASK
            )
            for row in group
        ),
        "active_time_sensitivity_eligible_count": sum(bool(row["sensitivity_active_time_eligible"]) for row in group),
    }


def active_health(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[safe(row.get(key))].append(row)
    out = []
    for value, group in sorted(grouped.items()):
        total = len(group)
        primary = sum(bool(row["primary_active_time_eligible"]) for row in group)
        counts = _active_counts(group)
        out.append(
            {
                key: value,
                "realized_submission_count": total,
                "primary_active_time_eligible_count": primary,
                **counts,
                "active_log_missing_count": counts["active_time_log_missing_count"],
                "active_log_missing_rate": _rate(counts["active_time_log_missing_count"], total),
            }
        )
    return out


def build_monitor(
    export_paths: list[Path],
    manual_assignment: Path = MANUAL_ASSIGNMENT_DEFAULT,
    semi_assignment: Path = SEMI_ASSIGNMENT_DEFAULT,
    worker_distribution: Path = WORKER_DISTRIBUTION_DEFAULT,
    planned_task_mapping: Path = PLANNED_TASK_MAPPING_DEFAULT,
    active_log: Path | None = ACTIVE_LOG_DEFAULT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assigned, internal = assignment_sets(manual_assignment, semi_assignment, worker_distribution)
    runtime_rows, runtime_lookup, collision_rows = build_runtime_task_mapping(export_paths, planned_task_mapping)
    realized_rows = build_realized_rows(export_paths, runtime_lookup, active_log, assigned, internal)
    realized_audit_rows = realized_vs_assigned_rows(realized_rows, assigned, internal)
    snapshot_rows = snapshot_manifest(export_paths, active_log, output_dir)

    duplicate_rows = [row for row in realized_rows if row["duplicate_worker_task_submission"]]
    outside_rows = [row for row in realized_rows if row["outside_assignment_submission"]]
    reserve_rows = [row for row in realized_rows if row["reserve_realized_submission"]]
    active_counts = _active_counts(realized_rows)
    planned_missing_count = sum(row["planned_mapping_status"] == "planned_mapping_missing" for row in runtime_rows)

    write_csv(output_dir / "c1_runtime_task_mapping.csv", runtime_rows, RUNTIME_MAPPING_FIELDS)
    write_csv(output_dir / "c1_runtime_key_collision_audit.csv", collision_rows, RUNTIME_COLLISION_FIELDS)
    write_csv(output_dir / "c1_live_realized_vs_assigned_audit.csv", realized_audit_rows, REALIZED_FIELDS)
    write_csv(output_dir / "c1_live_completion_by_worker.csv", summarize_by_worker(realized_rows, assigned))
    write_csv(output_dir / "c1_live_completion_by_task.csv", summarize_by_task(realized_rows, assigned))
    write_csv(output_dir / "c1_live_outside_assignment_audit.csv", outside_rows, REALIZED_FIELDS)
    write_csv(output_dir / "c1_live_duplicate_submission_audit.csv", duplicate_rows, REALIZED_FIELDS)
    write_csv(output_dir / "c1_live_active_log_health_by_worker.csv", active_health(realized_rows, "worker_id"))
    write_csv(output_dir / "c1_live_active_log_health_by_project.csv", active_health(realized_rows, "project_id"))
    write_csv(output_dir / "c1_live_snapshot_manifest.csv", snapshot_rows)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "export_snapshot_count": len(export_paths),
        "runtime_task_count": len(runtime_rows),
        "assigned_pair_count": len(assigned),
        "realized_submission_count": len(realized_rows),
        "outside_assignment_submission_count": len(outside_rows),
        "duplicate_worker_task_submission_count": len(duplicate_rows),
        "reserve_realized_submission_count": len(reserve_rows),
        "runtime_key_collision_count": len(collision_rows),
        "planned_mapping_missing_count": planned_missing_count,
        **active_counts,
        "active_log_missing_count": active_counts["active_time_log_missing_count"],
        "active_log_missing_rate": _rate(active_counts["active_time_log_missing_count"], len(realized_rows)),
        "passed": len(outside_rows) == 0 and len(duplicate_rows) == 0 and len(reserve_rows) == 0 and not collision_rows and not planned_missing_count,
        "blockers": [
            name
            for name, count in (
                ("outside_assignment_submission_detected", len(outside_rows)),
                ("duplicate_worker_task_submission_detected", len(duplicate_rows)),
                ("reserve_realized_submission_detected", len(reserve_rows)),
                ("runtime_key_collision_detected", len(collision_rows)),
                ("planned_mapping_missing", planned_missing_count),
            )
            if count
        ],
        "primary_active_time_policy": "log with project+task+worker+annotation or unambiguous project+task+worker direct match; lead_time never primary",
    }
    write_json(output_dir / "c1_live_monitor_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor live C1 raw collection health without formal canonicalization.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--manual-assignment", type=Path, default=MANUAL_ASSIGNMENT_DEFAULT)
    parser.add_argument("--semi-assignment", type=Path, default=SEMI_ASSIGNMENT_DEFAULT)
    parser.add_argument("--worker-distribution", type=Path, default=WORKER_DISTRIBUTION_DEFAULT)
    parser.add_argument("--planned-task-mapping", type=Path, default=PLANNED_TASK_MAPPING_DEFAULT)
    parser.add_argument("--active-log", type=Path, default=ACTIVE_LOG_DEFAULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    summary = build_monitor(
        args.export_json,
        manual_assignment=args.manual_assignment,
        semi_assignment=args.semi_assignment,
        worker_distribution=args.worker_distribution,
        planned_task_mapping=args.planned_task_mapping,
        active_log=args.active_log,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
