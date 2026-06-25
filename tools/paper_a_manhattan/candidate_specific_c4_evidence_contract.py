"""Fail-closed contract for candidate-specific C4 evidence inputs."""

from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "hrc_candidate_specific_c4_evidence_v1"
STATUSES = {"available", "unavailable", "unknown", "not_applicable"}
REQUIRED_IMAGE_INPUTS = (
    "image_edge_support",
    "candidate_image_boundary_alignment_delta",
    "manual_image_evidence_note",
)


def validate_candidate_specific_c4(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "case_name",
        "candidate_id",
        "baseline_only",
        "candidate_specific_projection_delta",
        "candidate_specific_image_evidence",
        "manual_visual_note",
        "safety_boundary",
    }
    missing = sorted(required - payload.keys())
    errors = [f"missing_field:{field}" for field in missing]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")

    for field in (
        "candidate_specific_projection_delta",
        "candidate_specific_image_evidence",
        "manual_visual_note",
    ):
        value = payload.get(field)
        if not isinstance(value, Mapping) or value.get("status") not in STATUSES:
            errors.append(f"invalid_status:{field}")

    image = payload.get("candidate_specific_image_evidence", {})
    missing_image_inputs = [
        field for field in REQUIRED_IMAGE_INPUTS if not image.get(field)
    ]
    projection_available = (
        payload.get("candidate_specific_projection_delta", {}).get("status")
        == "available"
    )
    image_available = (
        image.get("status") == "available" and not missing_image_inputs
    )
    complete = not errors and projection_available and image_available
    return {
        "valid_schema": not errors,
        "validation_errors": errors,
        "baseline_only_available": bool(payload.get("baseline_only", {}).get("available")),
        "candidate_specific_projection_delta_available": projection_available,
        "candidate_specific_image_evidence_available": image_available,
        "manual_visual_note_available": (
            payload.get("manual_visual_note", {}).get("status") == "available"
        ),
        "manual_image_evidence_note_available": bool(
            image.get("manual_image_evidence_note")
        ),
        "missing_candidate_specific_image_inputs": missing_image_inputs,
        "candidate_specific_c4_contract_complete": complete,
        "candidate_preference_authorized": False,
        "fail_closed": not complete,
    }
