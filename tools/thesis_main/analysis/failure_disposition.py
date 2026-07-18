"""Frozen failure attribution for C1, T1, and V1.

The row-level helpers stay deterministic; external attribution is accepted
only after ``validate_external_incident`` verifies the immutable registry.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ATTRIBUTIONS = {
    "none",
    "worker_caused_structural_failure",
    "policy_caused_failure",
    "external_system_failure",
    "not_evaluable",
}
EXTERNAL_EVIDENCE_STATUSES = {"not_applicable", "verified", "not_evaluable"}
DISPOSITIONS = {"included", "rerun", "administrative_censor", "not_evaluable"}


def text(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return text(value).lower() in {"1", "true", "yes", "y"}


def as_float(value: Any) -> float | None:
    try:
        return float(text(value))
    except ValueError:
        return None


def parse_timestamp(value: Any) -> datetime | None:
    value = text(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_set(value: Any) -> set[str]:
    value = text(value)
    if not value:
        return set()
    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError("incident scope must be a JSON list")
        return {text(item) for item in parsed if text(item)}
    return {item.strip() for item in value.replace(";", ",").split(",") if item.strip()}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_external_incident(
    annotation: dict[str, Any],
    incident: dict[str, Any] | None,
    *,
    evidence_base_dir: Path,
) -> tuple[bool, str]:
    """Validate immutable incident evidence against one annotation."""
    if not incident:
        return False, "incident_not_found"
    required = (
        "incident_id", "incident_type", "occurred_at", "recovered_at",
        "affected_project_ids", "evidence_path", "evidence_sha256", "recorded_at",
        "recorded_before_outcome_review",
    )
    if any(not text(incident.get(field)) for field in required):
        return False, "incident_required_field_missing"
    if not truthy(incident.get("recorded_before_outcome_review")):
        return False, "incident_recorded_after_outcome_review"

    occurred = parse_timestamp(incident.get("occurred_at"))
    recovered = parse_timestamp(incident.get("recovered_at"))
    recorded = parse_timestamp(incident.get("recorded_at"))
    annotated = parse_timestamp(
        annotation.get("annotation_timestamp")
        or annotation.get("completed_at")
        or annotation.get("updated_at")
        or annotation.get("created_at")
    )
    if None in {occurred, recovered, recorded, annotated}:
        return False, "incident_timestamp_invalid"
    assert occurred is not None and recovered is not None and recorded is not None and annotated is not None
    try:
        if occurred > recovered or not occurred <= annotated <= recovered:
            return False, "annotation_outside_incident_window"
    except TypeError:
        return False, "incident_timestamp_timezone_mismatch"
    reviewed = parse_timestamp(annotation.get("outcome_reviewed_at"))
    if text(annotation.get("outcome_reviewed_at")):
        if reviewed is None:
            return False, "outcome_review_timestamp_invalid"
        try:
            if recorded >= reviewed:
                return False, "incident_recorded_after_outcome_review"
        except TypeError:
            return False, "incident_timestamp_timezone_mismatch"

    project_id = text(annotation.get("project_id"))
    task_id = text(annotation.get("ls_runtime_task_id") or annotation.get("task_id"))
    try:
        projects = parse_set(incident.get("affected_project_ids"))
        tasks = parse_set(incident.get("affected_task_ids"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False, "incident_scope_invalid"
    scope_rule = text(incident.get("affected_scope_rule"))
    if not tasks and not scope_rule:
        return False, "incident_scope_missing"
    if projects and project_id not in projects:
        return False, "project_outside_incident_scope"
    if tasks and task_id not in tasks:
        return False, "task_outside_incident_scope"
    if not tasks and scope_rule not in {"all_tasks_in_affected_projects", "all_tasks"}:
        return False, "unsupported_incident_scope_rule"

    evidence_path = Path(text(incident.get("evidence_path")))
    if not evidence_path.is_absolute():
        evidence_path = evidence_base_dir / evidence_path
    if not evidence_path.is_file():
        return False, "incident_evidence_missing"
    try:
        actual_sha256 = sha256_file(evidence_path).lower()
    except OSError:
        return False, "incident_evidence_unreadable"
    if actual_sha256 != text(incident.get("evidence_sha256")).lower():
        return False, "incident_evidence_sha256_mismatch"
    return True, "verified"


def normalize_attribution(value: Any) -> str:
    attribution = text(value) or "none"
    if attribution == "policy_failure":  # legacy input spelling; artifacts emit policy_caused_failure.
        attribution = "policy_caused_failure"
    if attribution not in ATTRIBUTIONS:
        raise ValueError(f"unknown failure_attribution: {attribution}")
    return attribution


def incident_evidence_status(attribution: Any, evidence_status: Any, incident_id: Any) -> str:
    """Return the evidence state without ever guessing that an incident is external."""
    normalized = normalize_attribution(attribution)
    status = text(evidence_status) or ("not_applicable" if normalized != "external_system_failure" else "not_evaluable")
    if status not in EXTERNAL_EVIDENCE_STATUSES:
        raise ValueError(f"unknown incident_evidence_status: {status}")
    if normalized == "external_system_failure" and (status != "verified" or not text(incident_id)):
        return "not_evaluable"
    return status


def normalize_disposition(value: Any, *, attribution: Any, evidence_status: Any, incident_id: Any) -> str:
    """Validate an analysis disposition against its frozen attribution evidence."""
    normalized_attribution = normalize_attribution(attribution)
    status = incident_evidence_status(normalized_attribution, evidence_status, incident_id)
    disposition = text(value) or "included"
    if normalized_attribution == "external_system_failure" and status == "not_evaluable":
        return "not_evaluable"
    if disposition not in DISPOSITIONS:
        raise ValueError(f"unknown analysis_disposition: {disposition}")
    if normalized_attribution != "external_system_failure" and disposition in {"rerun", "administrative_censor"}:
        raise ValueError("only verified external_system_failure may rerun or administratively censor")
    if normalized_attribution == "external_system_failure" and disposition == "included":
        raise ValueError("verified external_system_failure requires rerun or administrative_censor")
    return disposition


def c1_failure_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Derive additive C1 fields; never infer a missing incident as no incident."""
    attribution = normalize_attribution(row.get("failure_attribution"))
    evidence_status = incident_evidence_status(attribution, row.get("incident_evidence_status"), row.get("incident_id"))
    if attribution == "external_system_failure" and evidence_status == "not_evaluable":
        attribution = "not_evaluable"
    return {
        "failure_attribution": attribution,
        "incident_id": text(row.get("incident_id")),
        "incident_evidence_status": evidence_status,
        "worker_caused_structural_failure": attribution == "worker_caused_structural_failure",
        "policy_failure": attribution == "policy_caused_failure",
        "external_system_failure": attribution == "external_system_failure",
        "structural_failure_evaluable": attribution != "not_evaluable",
        "worker_reliability_eligible": attribution not in {"external_system_failure", "policy_caused_failure", "not_evaluable"},
    }


def t1_outcome_fields(row: dict[str, Any]) -> dict[str, Any]:
    attribution = normalize_attribution(row.get("failure_attribution"))
    disposition = normalize_disposition(
        row.get("analysis_disposition"),
        attribution=attribution,
        evidence_status=row.get("incident_evidence_status"),
        incident_id=row.get("incident_id"),
    )
    iou = as_float(row.get("iou_to_gt"))
    if disposition != "included":
        return {"analysis_disposition": disposition, "structurally_valid": "", "delivery_adjusted_quality": "", "quality_evaluable": False}
    if attribution == "worker_caused_structural_failure":
        return {"analysis_disposition": disposition, "structurally_valid": False, "delivery_adjusted_quality": 0.0, "quality_evaluable": True}
    if attribution == "policy_caused_failure":
        return {"analysis_disposition": disposition, "structurally_valid": False, "delivery_adjusted_quality": 0.0, "quality_evaluable": True}
    if attribution == "not_evaluable" or iou is None:
        return {"analysis_disposition": "not_evaluable", "structurally_valid": "", "delivery_adjusted_quality": "", "quality_evaluable": False}
    return {"analysis_disposition": disposition, "structurally_valid": True, "delivery_adjusted_quality": iou, "quality_evaluable": True}


def v1_outcome_fields(row: dict[str, Any]) -> dict[str, Any]:
    attribution = normalize_attribution(row.get("failure_attribution"))
    disposition = normalize_disposition(
        row.get("analysis_disposition"),
        attribution=attribution,
        evidence_status=row.get("incident_evidence_status"),
        incident_id=row.get("incident_id"),
    )
    terminal = text(row.get("policy_terminal_status"))
    if terminal not in {"resolved", "unresolved", "severe_failure", ""}:
        raise ValueError(f"unknown policy_terminal_status: {terminal}")
    if disposition != "included":
        return {"analysis_disposition": disposition, "itt_included": False, "non_delivery": False, "policy_failure": False, "delivery_adjusted_quality": ""}
    non_delivery = terminal in {"unresolved", "severe_failure"}
    policy_failure = attribution == "policy_caused_failure"
    if non_delivery:
        return {"analysis_disposition": disposition, "itt_included": True, "non_delivery": True, "policy_failure": policy_failure, "delivery_adjusted_quality": 0.0}
    iou = as_float(row.get("iou_to_gt"))
    if terminal != "resolved" or iou is None:
        return {"analysis_disposition": "not_evaluable", "itt_included": False, "non_delivery": False, "policy_failure": False, "delivery_adjusted_quality": ""}
    return {"analysis_disposition": disposition, "itt_included": True, "non_delivery": False, "policy_failure": policy_failure, "delivery_adjusted_quality": iou}
