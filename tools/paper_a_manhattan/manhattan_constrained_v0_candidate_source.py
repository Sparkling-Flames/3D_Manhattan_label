"""Contract-only constrained_v0 shadow source; emits no candidates."""

from __future__ import annotations

from typing import Any, Mapping

from tools.paper_a_manhattan.manhattan_candidate_source_interface import (
    OUTPUT_SCHEMA_VERSION,
    validate_candidate_source,
)


SOURCE_VERSION = "hrc_c3_2_constrained_v0_source_contract_v1"
CONTRACT_PATH = "docs/paper_a_manhattan/HRC_C3_2_CONSTRAINED_V0_SOURCE_CONTRACT_v1.md"


def build_constrained_v0_shadow_source(
    case_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "source_id": "constrained_v0",
        "source_type": "constrained_v0_candidate_source",
        "source_version": SOURCE_VERSION,
        "generator_role": "shadow_constrained_generator",
        "candidate_generation_allowed": False,
        "candidate_count": 0,
        "candidate_set": [],
        "case_contract": dict(case_contract or {}),
        "source_provenance": {
            "contract_doc_path": CONTRACT_PATH,
            "implementation_status": "skeleton_only",
            "active_runner_role": False,
        },
        "source_limitations": [
            "skeleton only",
            "no candidate families implemented",
            "no coordinate changes emitted",
            "no active selection role",
        ],
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "no_new_candidate_strategy_introduced": True,
        "constrained_v0_implementation_status": "skeleton_only",
    }
    validate_candidate_source(payload)
    return payload
