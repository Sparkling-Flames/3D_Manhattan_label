"""Frozen failure attribution for C1, T1, and V1.

This module deliberately contains only deterministic row-level rules.  It
does not read Label Studio exports or decide whether an incident happened;
callers must supply the immutable incident evidence they joined to a row.
"""

from __future__ import annotations

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
        return {"analysis_disposition": disposition, "itt_included": False, "policy_failure": False, "delivery_adjusted_quality": ""}
    policy_failure = attribution == "policy_caused_failure" or terminal in {"unresolved", "severe_failure"}
    if policy_failure:
        return {"analysis_disposition": disposition, "itt_included": True, "policy_failure": True, "delivery_adjusted_quality": 0.0}
    iou = as_float(row.get("iou_to_gt"))
    if terminal != "resolved" or iou is None:
        return {"analysis_disposition": "not_evaluable", "itt_included": False, "policy_failure": False, "delivery_adjusted_quality": ""}
    return {"analysis_disposition": disposition, "itt_included": True, "policy_failure": False, "delivery_adjusted_quality": iou}
