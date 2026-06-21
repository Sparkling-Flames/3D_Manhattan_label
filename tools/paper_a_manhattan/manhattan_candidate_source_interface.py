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
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidate source candidate_set must be a non-empty list")
    if payload["candidate_count"] != len(candidates):
        raise ValueError("candidate source candidate_count mismatch")
    if payload["output_schema_version"] != OUTPUT_SCHEMA_VERSION:
        raise ValueError("unsupported candidate source output_schema_version")
    return payload
