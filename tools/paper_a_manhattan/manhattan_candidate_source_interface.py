"""Minimal contract validation for HRC candidate sources."""

from __future__ import annotations

from typing import Any, Mapping


OUTPUT_SCHEMA_VERSION = "manhattan_candidate_source_v1"
REQUIRED_FIELDS = {
    "source_id",
    "source_type",
    "source_version",
    "generator_role",
    "candidate_generation_allowed",
    "candidate_count",
    "candidate_set",
    "case_contract",
    "source_provenance",
    "source_limitations",
    "output_schema_version",
}


def validate_candidate_source(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    missing = sorted(REQUIRED_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"candidate source missing fields: {missing}")
    candidates = payload["candidate_set"]
    if not isinstance(candidates, list):
        raise ValueError("candidate source candidate_set must be a list")
    if payload["candidate_count"] != len(candidates):
        raise ValueError("candidate source candidate_count mismatch")
    shadow_status = payload.get("constrained_v0_implementation_status")
    shadow_empty = (
        not candidates
        and payload["source_type"] == "constrained_v0_candidate_source"
        and payload["generator_role"] == "shadow_constrained_generator"
        and shadow_status
        in {
            "skeleton_only",
            "column_x_alignment_shadow_only",
            "height_target_reproject_shadow_only",
        }
        and payload.get("source_provenance", {}).get("implementation_status")
        == shadow_status
        and all(
            payload.get(field) is False
            for field in (
                "accepted",
                "downstream_recommendation",
                "active_runner_role",
                "annotation_writeback",
            )
        )
    )
    if not candidates and not shadow_empty:
        raise ValueError("candidate source candidate_set must be non-empty unless shadow skeleton")
    if payload["output_schema_version"] != OUTPUT_SCHEMA_VERSION:
        raise ValueError("unsupported candidate source output_schema_version")
    return payload
