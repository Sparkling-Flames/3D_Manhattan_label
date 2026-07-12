from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.audit_p1_exact_copy_low_time import canonical_geometry_hash
from tools.thesis_main.analysis.analyze_quality import extract_data
from tools.thesis_main.analysis.quality_core.choice_parser import (
    _normalize_model_issue_values,
    _pick_primary_model_issue,
)


RULE_VERSION = "p1_post_closeout_evidence_correction_v1"
TASK_FIELDS = [
    "worker_id",
    "project_id",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "stage",
    "pool",
    "annotation_id",
    "parent_annotation_id",
    "parent_owner_id",
    "parent_same_task",
    "parent_same_owner",
    "parent_cross_owner",
    "parent_precedes_child",
    "geometry_relation",
    "independence_status",
    "independence_reason",
    "adjudication_status",
    "active_time_source",
    "active_time_match_status",
    "primary_active_time_eligible",
    "active_time_seconds",
    "lead_time_seconds",
    "timing_evidence_status",
    "active_time_integrity_status",
    "system_collection_issue",
    "unassigned_active_time_seconds",
    "unknown_annotation_event_count",
    "unknown_annotation_session_count",
    "known_unknown_oscillation_flag",
    "unassigned_audit_present",
    "unassigned_active_time_exclusion_reason",
    "sensitivity_active_time_eligible",
    "forensic_timing_audit_eligible",
    "audit_only",
    "long_open_draft_flag",
    "capability_evidence_eligible",
    "geometry_capability_candidate",
    "geometry_score_status",
    "process_evaluable",
    "process_failure_observed",
    "process_failure_subfamily",
    "task_final_scope",
    "task_oos_subtype",
    "worker_scope_response",
    "scope_evidence_status",
    "model_issue",
    "model_issue_primary",
    "semi_response_type",
    "semi_evidence_status",
    "semi_issue_recognition_ready",
    "semi_geometry_correction_evidence_status",
    "semi_issue_recognition_evaluable",
    "semi_geometry_correction_evaluable",
    "semi_correction_failure_observed",
    "coverage_response",
    "undercoverage_response",
    "undercoverage_subfamily",
    "undercoverage_evidence_status",
    "undercoverage_failure_observed",
    "undercoverage_risk_level",
    "undercoverage_proxy_reason",
    "undercoverage_manual_review_required",
    "undercoverage_expert_verdict",
    "undercoverage_interpretation_allowed",
    "included_in_r_u_calib",
    "included_in_r_geometry",
    "included_in_r_scope",
    "included_in_T_u",
    "included_in_U_u",
    "included_in_p1_predictive_capability",
    "included_in_process_reliability",
    "exclusion_reason",
    "interpretation_allowed",
    "source_export",
    "source_sha256",
    "source_canonical_sha256",
    "source_scope_artifact",
    "source_scope_sha256",
    "source_semi_artifact",
    "source_semi_sha256",
    "source_undercoverage_artifact",
    "source_undercoverage_sha256",
    "rule_version",
]
WORKER_FIELDS = [
    "worker_id",
    "original_admission_status",
    "operational_c1_assignment_status",
    "n_p1_tasks",
    "n_independent_tasks",
    "n_non_independent_confirmed",
    "n_non_independent_suspected",
    "p1_capability_evidence_status",
    "p1_timing_evidence_status",
    "p1_r0_analysis_eligible",
    "p1_geometry_profile_eligible",
    "p1_scope_profile_eligible",
    "p1_T_u_eligible",
    "p1_U_u_eligible",
    "p1_predictive_capability_eligible",
    "p1_process_warning",
    "c1_r_u_calib_status",
    "routing_watch_status",
    "notes",
    "rule_version",
    "source_canonical_sha256",
]


def _safe(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            normalized = {}
            for field in fields:
                value = row.get(field, "")
                normalized[field] = str(value).lower() if isinstance(value, bool) else value
            writer.writerow(normalized)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_time(value: Any) -> datetime | None:
    text = _safe(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _task_data(task: dict[str, Any]) -> dict[str, Any]:
    value = task.get("data")
    return value if isinstance(value, dict) else {}


def _raw_task_id(task: dict[str, Any], index: int) -> str:
    return _safe(task.get("id") or task.get("task_id") or _task_data(task).get("task_id") or f"task_index_{index}")


def _project_id(task: dict[str, Any]) -> str:
    return _safe(task.get("project") or task.get("project_id"))


def _worker_id(annotation: dict[str, Any]) -> str:
    owner = annotation.get("completed_by")
    if isinstance(owner, dict):
        for key in ("id", "email", "username", "pk"):
            if _safe(owner.get(key)):
                return _safe(owner[key])
    return _safe(owner)


def _annotation_id(annotation: dict[str, Any], index: int) -> str:
    return _safe(annotation.get("id") or f"annotation_index_{index}")


def _parent_id(annotation: dict[str, Any]) -> str:
    value = annotation.get("parent_annotation")
    if isinstance(value, dict):
        return _safe(value.get("id") or value.get("annotation_id"))
    return _safe(value)


def _raw_annotation_data(annotation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    try:
        corners, _polygon, choices, _quality = extract_data(annotation.get("result") or [])
        return canonical_geometry_hash(corners)[0], choices
    except Exception:
        return "", {}


def _load_exports(paths: list[Path]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]], dict[str, str]]:
    annotations: dict[tuple[str, str, str], dict[str, Any]] = {}
    tasks: dict[tuple[str, str], dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for path in paths:
        hashes[str(path)] = _sha256(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("tasks") or payload.get("data") or []
        if not isinstance(payload, list):
            raise ValueError(f"P1 export must be a task list: {path}")
        for task_index, task in enumerate(payload, start=1):
            if not isinstance(task, dict):
                continue
            project_id = _project_id(task)
            task_id = _raw_task_id(task, task_index)
            tasks[(project_id, task_id)] = {"task": task, "source_export": str(path), "source_sha256": hashes[str(path)]}
            for ann_index, annotation in enumerate(task.get("annotations") or [], start=1):
                if not isinstance(annotation, dict):
                    continue
                annotation_id = _annotation_id(annotation, ann_index)
                geometry_hash, choice_map = _raw_annotation_data(annotation)
                annotations[(project_id, task_id, annotation_id)] = {
                    "annotation": annotation,
                    "project_id": project_id,
                    "task_id": task_id,
                    "source_export": str(path),
                    "source_sha256": hashes[str(path)],
                    "geometry_hash": geometry_hash,
                    "choice_map": choice_map,
                }
    return annotations, tasks, hashes


def _relative_outlier(values: list[float], candidate: float) -> bool:
    if len(values) < 5 or candidate <= 0:
        return False
    ordered = sorted(values)
    q1 = ordered[(len(ordered) - 1) // 4]
    q3 = ordered[(3 * (len(ordered) - 1)) // 4]
    iqr = q3 - q1
    center = median(values)
    return candidate >= q3 + 3 * iqr and center > 0 and candidate >= 3 * center


def _status_for_parent(
    child: dict[str, Any],
    parent: dict[str, Any] | None,
    child_geometry_hash: str,
    child_project_id: str,
    child_task_id: str,
) -> tuple[str, str, str, bool, bool, bool, bool, str]:
    child_worker = _worker_id(child)
    parent_id = _parent_id(child)
    if not parent_id:
        return "independent", "no_parent_annotation", "", False, False, False, False, "not_required"
    if parent is None:
        return "not_evaluable", "parent_annotation_not_found", "", False, False, False, False, "source_review_required"
    parent_annotation = parent["annotation"]
    parent_worker = _worker_id(parent_annotation)
    same_owner = bool(child_worker and parent_worker and child_worker == parent_worker)
    same_task = bool(parent.get("project_id") == child_project_id and parent.get("task_id") == child_task_id)
    parent_time = _parse_time(parent_annotation.get("created_at"))
    child_time = _parse_time(child.get("created_at"))
    precedes = bool(parent_time and child_time and parent_time < child_time)
    parent_hash = _safe(parent.get("geometry_hash"))
    identical = bool(child_geometry_hash and parent_hash and child_geometry_hash == parent_hash)
    relation = "identical" if identical else "different" if child_geometry_hash and parent_hash else "unavailable"
    if same_owner:
        return "independent", "same_worker_revision", parent_worker, same_task, True, False, precedes, "not_required"
    if not parent_worker:
        return "not_evaluable", "parent_owner_missing", "", same_task, False, False, precedes, "source_review_required"
    if precedes and identical:
        return "non_independent_confirmed", "cross_worker_prior_parent_exact_geometry", parent_worker, same_task, False, True, True, "auto_confirmed"
    return "non_independent_suspected", "cross_worker_parent_evidence_incomplete", parent_worker, same_task, False, True, precedes, "pending_review"


def _timing(row: dict[str, str], independence_status: str, raw_owner: str) -> tuple[str, bool, str]:
    source = _safe(row.get("active_time_source")).lower()
    match = _safe(row.get("active_time_match_status")).lower()
    worker_id = _safe(row.get("worker_id"))
    annotator_id = _safe(row.get("annotator_id"))
    worker = worker_id or annotator_id
    alias_conflict = bool(worker_id and annotator_id and worker_id != annotator_id)
    owner_valid = bool(worker and raw_owner and worker == raw_owner and not alias_conflict)
    exact = source == "log" and match in {
        "project+task+annotator+annotation",
        "annotation_exact",
        "exact_annotation_valid",
    } and _safe(row.get("active_time")) and owner_valid
    if independence_status != "independent":
        return "parent_derived_forensic_only", False, "parent_derived_timing"
    if exact:
        return "primary_exact_owner_valid", True, ""
    if source == "log":
        return "task_log_sensitivity_only", False, "task_level_log_fallback"
    if source == "lead_time_fallback":
        return "lead_time_fallback_sensitivity_only", False, "lead_time_fallback_not_primary"
    return "unavailable", False, "active_time_unavailable"


def _timing_integrity_status(row: dict[str, str], timing_status: str, primary: bool, raw_owner: str) -> str:
    source = _safe(row.get("active_time_source")).lower()
    match = _safe(row.get("active_time_match_status")).lower()
    worker = _safe(row.get("worker_id") or row.get("annotator_id"))
    aliases_conflict = bool(_safe(row.get("worker_id")) and _safe(row.get("annotator_id")) and _safe(row.get("worker_id")) != _safe(row.get("annotator_id")))
    exact_match = source == "log" and match in {"project+task+annotator+annotation", "annotation_exact", "exact_annotation_valid"}
    if timing_status == "parent_derived_forensic_only":
        return "parent_derived_forensic_only"
    if exact_match and not primary:
        return "owner_mismatch" if aliases_conflict or (worker and raw_owner and worker != raw_owner) else "ambiguous"
    explicit = _safe(row.get("active_time_integrity_status"))
    if explicit:
        return explicit
    if primary:
        return "exact_annotation_valid"
    if timing_status == "task_log_sensitivity_only":
        return "task_level_fallback"
    if timing_status in {"lead_time_fallback_sensitivity_only", "parent_derived_forensic_only"}:
        return "lead_time_fallback"
    return "missing" if timing_status == "unavailable" else "ambiguous"


def _stage(row: dict[str, str]) -> str:
    group = _safe(row.get("dataset_group"))
    return "P1" if group.startswith("PreScreen_") else _safe(row.get("stage")) or "P1"


def _process_flags(row: dict[str, str], independence_status: str) -> tuple[bool, bool, str]:
    explicit = _truthy(row.get("process_invalid")) or _truthy(row.get("outside_assignment_submission")) or _truthy(row.get("duplicate_worker_task_submission")) or _truthy(row.get("active_time_worker_process_failure")) or _truthy(row.get("worker_attributable_active_time_failure"))
    if independence_status == "non_independent_confirmed":
        return True, True, "non_independent_submission"
    if explicit:
        if _truthy(row.get("outside_assignment_submission")):
            reason = "outside_manifest_submission"
        elif _truthy(row.get("duplicate_worker_task_submission")):
            reason = "duplicate_same_geometry"
        elif _truthy(row.get("process_invalid")):
            reason = "schema_invalid"
        else:
            reason = "active_time_missing_or_ineligible"
        return True, True, reason
    if independence_status == "non_independent_suspected":
        return False, False, ""
    if _truthy(row.get("system_collection_issue")) or _safe(row.get("active_time_integrity_status")) in {"unknown_audit_only", "missing", "owner_mismatch", "ambiguous"}:
        return False, False, ""
    if _safe(row.get("active_time_source")).lower() in {"", "missing"} and not _safe(row.get("lead_time_seconds")):
        return False, False, ""
    return True, False, ""


def _optional_rows(path: Path | None) -> tuple[list[dict[str, str]], str]:
    if not path or not path.exists():
        return [], ""
    return _read_csv(path), _sha256(path)


def _scope_evidence(row: dict[str, str] | None) -> dict[str, Any]:
    if not row:
        return {"scope_evidence_status": "not_evaluable_missing_artifact"}
    final_scope = _safe(row.get("task_final_scope")).lower()
    response = _safe(row.get("worker_scope_response")).lower()
    eligible = _truthy(row.get("scope_response_primary_eligible"))
    evaluable = eligible and final_scope in {"in_scope", "oos", "out_of_scope"} and bool(response)
    return {
        "task_final_scope": "oos" if final_scope in {"oos", "out_of_scope"} else final_scope,
        "task_oos_subtype": _safe(row.get("task_oos_subtype")) or (final_scope if final_scope.startswith("oos_") else ""),
        "worker_scope_response": response,
        "scope_evidence_status": "evaluable" if evaluable else "not_evaluable_incomplete_response",
    }


def _semi_evidence(row: dict[str, str] | None, choice_map: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {"semi_evidence_status": "not_evaluable_missing_artifact"}
    selected = _normalize_model_issue_values(choice_map.get("model_issue") or [])
    selected_primary = _pick_primary_model_issue([value for value in selected if value != "acceptable"])
    explicit_response = _safe(row.get("semi_response_type"))
    explicit_failure = _safe(row.get("semi_correction_failure_observed"))
    expected = _safe(row.get("expert_realized_model_issue_primary") or row.get("model_issue_primary") or row.get("reviewed_primary_issue"))
    secondary = {
        value
        for value in _safe(row.get("expert_realized_model_issue_secondary") or row.get("reviewed_secondary_issue")).split(";")
        if value
    }
    response = explicit_response
    failure: bool | str = _truthy(explicit_failure) if explicit_failure else ""
    if not response and selected and expected:
        selected_set = set(selected)
        if selected_set == {"acceptable"}:
            response, failure = "blind_trust", True
        elif expected in selected_set or bool(secondary & selected_set):
            response, failure = "issue_recognized", False
    return {
        "model_issue": ";".join(selected),
        "model_issue_primary": selected_primary,
        "semi_response_type": response,
        "semi_evidence_status": "evaluable" if response and failure != "" else "not_evaluable_incomplete_response",
        "semi_issue_recognition_ready": bool(response and failure != ""),
        "semi_geometry_correction_evidence_status": _safe(row.get("semi_geometry_correction_evidence_status")) or "not_evaluable_missing_geometry_comparison",
        "semi_issue_recognition_evaluable": bool(response and failure != ""),
        "semi_geometry_correction_evaluable": _safe(row.get("semi_geometry_correction_evidence_status")) == "evaluable",
        "semi_correction_failure_observed": failure,
    }


def _undercoverage_evidence(row: dict[str, str] | None) -> dict[str, Any]:
    if not row:
        return {"undercoverage_evidence_status": "not_evaluable_missing_artifact"}
    level = _safe(row.get("undercoverage_risk_level")).lower()
    verdict = _safe(row.get("undercoverage_expert_verdict") or row.get("expert_undercoverage_verdict")).lower()
    values: dict[str, Any] = {
        "coverage_response": "",
        "undercoverage_response": "",
        "undercoverage_subfamily": "",
        "undercoverage_risk_level": level,
        "undercoverage_proxy_reason": _safe(row.get("undercoverage_reason")),
        "undercoverage_manual_review_required": _truthy(row.get("manual_review_required")),
        "undercoverage_expert_verdict": verdict,
        "undercoverage_evidence_status": "candidate_only_pending_adjudication" if level else "not_evaluable_incomplete_response",
        "undercoverage_failure_observed": "",
        "undercoverage_interpretation_allowed": False,
    }
    verdict_map = {
        "confirmed_full_room_attempt": ("full_room_attempt", "", False),
        "confirmed_partial_undercoverage": ("partial_undercoverage", "partial_undercoverage", True),
        "confirmed_inner_space_only": ("inner_space_only", "inner_space_only", True),
        "confirmed_minimal_space_bias": ("minimal_space_bias", "minimal_space_bias", True),
        "confirmed_overextended_adjacent": ("overextended_adjacent_when_in_scope", "overextended_adjacent_when_in_scope", True),
        "rejected_proxy_false_positive": ("full_room_attempt", "", False),
    }
    if verdict in verdict_map:
        response, subfamily, failure = verdict_map[verdict]
        values.update(
            coverage_response="undercoverage" if failure else "full_room_attempt",
            undercoverage_response=response,
            undercoverage_subfamily=subfamily,
            undercoverage_failure_observed=failure,
            undercoverage_evidence_status="evaluable_expert_adjudicated",
            undercoverage_interpretation_allowed=True,
        )
    elif verdict in {"pending_review", "not_evaluable"}:
        values["undercoverage_evidence_status"] = verdict
    return values


def build_correction(
    canonical_csv: Path,
    export_json: list[Path],
    admission_csv: Path,
    c1_assignment_csv: Path | None = None,
    fallback_audit: list[Path] | None = None,
    scope_evidence_csv: Path | None = None,
    semi_evidence_csv: Path | None = None,
    undercoverage_evidence_csv: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    canonical = _read_csv(canonical_csv)
    annotations, _tasks, source_hashes = _load_exports(export_json)
    canonical_sha = _sha256(canonical_csv)
    scope_rows, scope_sha = _optional_rows(scope_evidence_csv)
    semi_rows, semi_sha = _optional_rows(semi_evidence_csv)
    under_rows, under_sha = _optional_rows(undercoverage_evidence_csv)
    scope_lookup = {
        (_safe(item.get("annotator_id") or item.get("worker_id")), _safe(item.get("project_id")), _safe(item.get("task_id"))): item
        for item in scope_rows
    }
    semi_lookup: dict[tuple[str, str], dict[str, str]] = {}
    for item in semi_rows:
        worker_key = _safe(item.get("annotator_id") or item.get("worker_id"))
        for task_key in (item.get("task_id"), item.get("runtime_task_id"), item.get("en_task_id"), item.get("zh_task_id")):
            if _safe(task_key):
                semi_lookup[(worker_key, _safe(task_key))] = item
                semi_lookup[("", _safe(task_key))] = item
    under_lookup = {
        (_safe(item.get("annotator_id") or item.get("worker_id")), _safe(item.get("task_id"))): item
        for item in under_rows
    }
    admissions = {(_safe(row.get("worker_id") or row.get("annotator_id"))): row for row in _read_csv(admission_csv)} if admission_csv.exists() else {}
    assigned_workers = set()
    if c1_assignment_csv and c1_assignment_csv.exists():
        assigned_workers = {_safe(row.get("worker_id")) for row in _read_csv(c1_assignment_csv) if _safe(row.get("worker_id"))}

    lead_by_worker: dict[str, list[float]] = defaultdict(list)
    for row in canonical:
        worker = _safe(row.get("worker_id") or row.get("annotator_id"))
        try:
            lead = float(_safe(row.get("lead_time_seconds")) or 0)
        except ValueError:
            lead = 0.0
        if worker and lead > 0:
            lead_by_worker[worker].append(lead)

    task_rows: list[dict[str, Any]] = []
    for row in canonical:
        worker = _safe(row.get("worker_id") or row.get("annotator_id"))
        project = _safe(row.get("project_id"))
        task_id = _safe(row.get("task_id"))
        annotation_id = _safe(row.get("annotation_id"))
        raw = annotations.get((project, task_id, annotation_id))
        annotation = raw["annotation"] if raw else {}
        raw_owner = _worker_id(annotation)
        choice_map = raw.get("choice_map", {}) if raw else {}
        parent = None
        parent_id = _parent_id(annotation)
        if raw and parent_id:
            parent = annotations.get((project, task_id, parent_id))
        child_hash = _safe(row.get("geometry_hash")) or _safe(raw.get("geometry_hash") if raw else "")
        independence, reason, parent_owner, parent_same_task, parent_same_owner, parent_cross_owner, parent_precedes, adjudication = _status_for_parent(annotation, parent, child_hash, project, task_id) if raw else ("not_evaluable", "raw_annotation_not_found", "", False, False, False, False, "source_review_required")
        timing_status, primary, timing_reason = _timing(row, independence, raw_owner)
        try:
            lead = float(_safe(row.get("lead_time_seconds")) or 0)
        except ValueError:
            lead = 0.0
        process_evaluable, process_failure, process_subfamily = _process_flags(row, independence)
        capable = independence == "independent" and not process_failure
        scope_values = _scope_evidence(scope_lookup.get((worker, project, task_id)))
        semi_values = _semi_evidence(semi_lookup.get((worker, task_id)) or semi_lookup.get(("", task_id)), choice_map)
        under_values = _undercoverage_evidence(under_lookup.get((worker, task_id)))
        scope_evaluable = scope_values.get("scope_evidence_status") == "evaluable"
        semi_evaluable = semi_values.get("semi_evidence_status") == "evaluable"
        under_evaluable = under_values.get("undercoverage_evidence_status") == "evaluable"
        long_flag = _relative_outlier(lead_by_worker[worker], lead)
        exclusion = []
        if independence != "independent":
            exclusion.append(reason)
        if timing_reason:
            exclusion.append(timing_reason)
        if not capable:
            exclusion.append("not_capability_evidence")
        source_export = raw["source_export"] if raw else _safe(row.get("source_export"))
        source_sha = raw["source_sha256"] if raw else (source_hashes.get(source_export, "") if source_export else "")
        task_rows.append(
            {
                "worker_id": worker,
                "project_id": project,
                "task_id": task_id,
                "base_task_id": _safe(row.get("base_task_id")),
                "dataset_group": _safe(row.get("dataset_group")),
                "condition": _safe(row.get("condition")),
                "stage": _stage(row),
                "pool": _safe(row.get("dataset_group")),
                "annotation_id": annotation_id,
                "parent_annotation_id": parent_id,
                "parent_owner_id": parent_owner,
                "parent_same_task": parent_same_task,
                "parent_same_owner": parent_same_owner,
                "parent_cross_owner": parent_cross_owner,
                "parent_precedes_child": parent_precedes,
                "geometry_relation": "identical" if parent and child_hash and child_hash == _safe(parent.get("geometry_hash")) else "different" if parent else "unavailable",
                "independence_status": independence,
                "independence_reason": reason,
                "adjudication_status": adjudication,
                "active_time_source": _safe(row.get("active_time_source")),
                "active_time_match_status": _safe(row.get("active_time_match_status")),
                "primary_active_time_eligible": primary,
                "active_time_seconds": _safe(row.get("active_time")) if _safe(row.get("active_time_source")).lower() == "log" else "",
                "lead_time_seconds": lead if lead else "",
                "timing_evidence_status": timing_status,
                "active_time_integrity_status": _timing_integrity_status(row, timing_status, primary, raw_owner),
                "system_collection_issue": _truthy(row.get("system_collection_issue")),
                "unassigned_active_time_seconds": _safe(row.get("unassigned_active_time_seconds")),
                "unknown_annotation_event_count": _safe(row.get("unknown_annotation_event_count")),
                "unknown_annotation_session_count": _safe(row.get("unknown_annotation_session_count")),
                "known_unknown_oscillation_flag": _truthy(row.get("known_unknown_oscillation_flag")),
                "unassigned_audit_present": _truthy(row.get("unassigned_audit_present")) or any(_safe(row.get(field)) for field in ("unassigned_active_time_seconds", "unknown_annotation_event_count", "unknown_annotation_session_count")),
                "unassigned_active_time_exclusion_reason": _safe(row.get("unassigned_active_time_exclusion_reason")),
                "sensitivity_active_time_eligible": timing_status in {"task_log_sensitivity_only", "lead_time_fallback_sensitivity_only"},
                "forensic_timing_audit_eligible": timing_status == "parent_derived_forensic_only",
                "audit_only": _truthy(row.get("audit_only")) or independence != "independent",
                "long_open_draft_flag": long_flag,
                "capability_evidence_eligible": capable,
                "geometry_capability_candidate": capable and _safe(row.get("condition")).lower() == "manual",
                "geometry_score_status": "pending_geometry_scorer" if capable and _safe(row.get("condition")).lower() == "manual" else "not_eligible",
                "process_evaluable": process_evaluable,
                "process_failure_observed": process_failure,
                "process_failure_subfamily": process_subfamily,
                **scope_values,
                **semi_values,
                **under_values,
                "included_in_r_u_calib": False,
                "included_in_r_geometry": False,
                "included_in_r_scope": capable and scope_evaluable,
                "included_in_T_u": capable and _safe(row.get("dataset_group")) == "PreScreen_semi" and _truthy(semi_values.get("semi_geometry_correction_evaluable")),
                "included_in_U_u": capable and _safe(row.get("condition")).lower() == "manual" and scope_values.get("task_final_scope") == "in_scope" and under_values.get("undercoverage_evidence_status") == "evaluable_expert_adjudicated",
                "included_in_p1_predictive_capability": capable,
                "included_in_process_reliability": process_evaluable,
                "exclusion_reason": ";".join(exclusion),
                "interpretation_allowed": capable,
                "source_export": source_export,
                "source_sha256": source_sha,
                "source_canonical_sha256": canonical_sha,
                "source_scope_artifact": str(scope_evidence_csv) if scope_rows else "",
                "source_scope_sha256": scope_sha,
                "source_semi_artifact": str(semi_evidence_csv) if semi_rows else "",
                "source_semi_sha256": semi_sha,
                "source_undercoverage_artifact": str(undercoverage_evidence_csv) if under_rows else "",
                "source_undercoverage_sha256": under_sha,
                "rule_version": RULE_VERSION,
            }
        )

    worker_ids = sorted({row["worker_id"] for row in task_rows if row["worker_id"]} | set(admissions))
    worker_rows: list[dict[str, Any]] = []
    for worker in worker_ids:
        rows = [row for row in task_rows if row["worker_id"] == worker]
        confirmed = sum(row["independence_status"] == "non_independent_confirmed" for row in rows)
        suspected = sum(row["independence_status"] == "non_independent_suspected" for row in rows)
        independent = sum(row["independence_status"] == "independent" for row in rows)
        capable = sum(_truthy(row["capability_evidence_eligible"]) for row in rows)
        timing = [row for row in rows if row["primary_active_time_eligible"]]
        if (confirmed or suspected) and not timing:
            timing_status = "contaminated_by_non_independence"
        elif timing:
            timing_status = "primary_sufficient" if len(timing) == len(rows) else "primary_partial"
        elif any(row["timing_evidence_status"].endswith("sensitivity_only") for row in rows):
            timing_status = "fallback_only"
        else:
            timing_status = "unavailable"
        if confirmed and not capable:
            capability_status = "invalid_non_independent_submission"
        elif confirmed or suspected:
            capability_status = "partial_non_independent_evidence"
        else:
            capability_status = "eligible"
        admission = admissions.get(worker, {})
        admitted = _safe(admission.get("admission_status")).lower() in {"pass", "pass_with_watch", "admitted"} or _truthy(admission.get("eligible_for_C1"))
        r0_available = bool(_safe(admission.get("r_u_0") or admission.get("r0_prescreen")))
        worker_rows.append(
            {
                "worker_id": worker,
                "original_admission_status": _safe(admission.get("admission_status")),
                "operational_c1_assignment_status": "unchanged_existing_assignment" if worker in assigned_workers else "not_present_in_assignment_input",
                "n_p1_tasks": len(rows),
                "n_independent_tasks": independent,
                "n_non_independent_confirmed": confirmed,
                "n_non_independent_suspected": suspected,
                "p1_capability_evidence_status": capability_status,
                "p1_timing_evidence_status": timing_status,
                "p1_r0_analysis_eligible": admitted and r0_available and bool(capable),
                "p1_geometry_profile_eligible": bool(capable),
                "p1_scope_profile_eligible": bool(capable),
                "p1_T_u_eligible": any(_truthy(row["included_in_T_u"]) for row in rows),
                "p1_U_u_eligible": any(_truthy(row["included_in_U_u"]) for row in rows),
                "p1_predictive_capability_eligible": bool(capable),
                "p1_process_warning": bool(confirmed or suspected or any(row["process_failure_observed"] for row in rows)),
                "c1_r_u_calib_status": "pending_c1_calibration_evidence",
                "routing_watch_status": "watch_only" if confirmed or suspected else "none",
                "notes": "post_closeout_correction_only;admission_and_c1_assignment_unchanged",
                "rule_version": RULE_VERSION,
                "source_canonical_sha256": canonical_sha,
            }
        )
    summary = {
        "rule_version": RULE_VERSION,
        "n_task_rows": len(task_rows),
        "n_workers": len(worker_rows),
        "n_workers_audited": len({row["worker_id"] for row in task_rows if row["worker_id"]}),
        "n_annotations_audited": len(task_rows),
        "n_independent": sum(row["independence_status"] == "independent" for row in task_rows),
        "n_non_independent_confirmed": sum(row["independence_status"] == "non_independent_confirmed" for row in task_rows),
        "n_non_independent_suspected": sum(row["independence_status"] == "non_independent_suspected" for row in task_rows),
        "n_parent_not_evaluable": sum(row["independence_status"] == "not_evaluable" for row in task_rows),
        "workers_with_confirmed_non_independence": sorted({row["worker_id"] for row in task_rows if row["independence_status"] == "non_independent_confirmed"}),
        "workers_with_suspected_non_independence": sorted({row["worker_id"] for row in task_rows if row["independence_status"] == "non_independent_suspected"}),
        "n_process_evaluable": sum(_truthy(row["process_evaluable"]) for row in task_rows),
        "n_process_failures": sum(_truthy(row["process_failure_observed"]) for row in task_rows),
        "n_primary_active_time": sum(_truthy(row["primary_active_time_eligible"]) for row in task_rows),
        "n_sensitivity_active_time": sum(_truthy(row["sensitivity_active_time_eligible"]) for row in task_rows),
        "forensic_timing_audit_count": sum(_truthy(row["forensic_timing_audit_eligible"]) for row in task_rows),
        "n_long_open_draft_flags": sum(_truthy(row["long_open_draft_flag"]) for row in task_rows),
        "source_exports": source_hashes,
        "source_canonical_sha256": canonical_sha,
        "scope_evidence_sha256": scope_sha,
        "semi_evidence_sha256": semi_sha,
        "undercoverage_evidence_sha256": under_sha,
        "warnings": [
            name
            for name, present in (
                ("p1_scope_evidence_missing", bool(scope_rows)),
                ("p1_semi_evidence_missing", bool(semi_rows)),
                ("p1_undercoverage_evidence_missing", bool(under_rows)),
            )
            if not present
        ],
        "fallback_audit_provenance": {
            str(path): _sha256(path)
            for path in (fallback_audit or [])
            if path.exists()
        },
        "non_blocking_audit": True,
        "admission_writeback": False,
        "assignment_writeback": False,
    }
    return task_rows, worker_rows, summary


def materialize(
    canonical_csv: Path,
    export_json: list[Path],
    admission_csv: Path,
    output_dir: Path,
    c1_assignment_csv: Path | None = None,
    fallback_audit: list[Path] | None = None,
    scope_evidence_csv: Path | None = None,
    semi_evidence_csv: Path | None = None,
    undercoverage_evidence_csv: Path | None = None,
) -> dict[str, Any]:
    task_rows, worker_rows, summary = build_correction(
        canonical_csv,
        export_json,
        admission_csv,
        c1_assignment_csv,
        fallback_audit,
        scope_evidence_csv,
        semi_evidence_csv,
        undercoverage_evidence_csv,
    )
    task_path = output_dir / "p1_task_evidence_correction_v1.csv"
    worker_path = output_dir / "p1_worker_evidence_status_v1.csv"
    summary_path = output_dir / "p1_post_closeout_correction_summary_v1.json"
    report_path = output_dir / "p1_post_closeout_correction_report_v1.md"
    _write_csv(task_path, task_rows, TASK_FIELDS)
    _write_csv(worker_path, worker_rows, WORKER_FIELDS)
    summary.update({"task_evidence_csv": str(task_path), "worker_status_csv": str(worker_path)})
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        "\n".join(
            [
                "# P1 Post-Closeout Evidence Correction",
                "",
                f"Rule version: `{RULE_VERSION}`.",
                "",
                "This is a read-only post-closeout correction layer. It does not rewrite P1 admission or C1 assignment.",
                "",
                f"Task evidence rows: {len(task_rows)}",
                f"Workers: {len(worker_rows)}",
                f"Confirmed non-independent rows: {summary['n_non_independent_confirmed']}",
                f"Suspected rows pending adjudication: {summary['n_non_independent_suspected']}",
                f"Process-evaluable rows: {summary['n_process_evaluable']}",
                f"Process failures: {summary['n_process_failures']}",
                f"Primary exact-time rows: {summary['n_primary_active_time']}",
                f"Long-open review flags: {summary['n_long_open_draft_flags']}",
                "",
                "Long-open flags are relative worker-level audit candidates and require human review; they are not process failures.",
                "",
                "## Long-open candidates",
                "",
                *[
                    f"- worker `{row['worker_id']}` task `{row['task_id']}` annotation `{row['annotation_id']}` lead_time_seconds=`{row['lead_time_seconds']}`"
                    for row in task_rows
                    if _truthy(row.get("long_open_draft_flag"))
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    summary.update({"summary_json": str(summary_path), "report_md": str(report_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize read-only P1 post-closeout evidence correction.")
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--export-json", type=Path, action="append", required=True)
    parser.add_argument("--admission-csv", type=Path, required=True)
    parser.add_argument("--c1-assignment-csv", type=Path)
    parser.add_argument("--fallback-audit", type=Path, action="append", default=[])
    parser.add_argument("--scope-evidence-csv", type=Path)
    parser.add_argument("--semi-evidence-csv", type=Path)
    parser.add_argument("--undercoverage-evidence-csv", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.canonical_csv,
        args.export_json,
        args.admission_csv,
        args.output_dir,
        args.c1_assignment_csv,
        args.fallback_audit,
        args.scope_evidence_csv,
        args.semi_evidence_csv,
        args.undercoverage_evidence_csv,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
