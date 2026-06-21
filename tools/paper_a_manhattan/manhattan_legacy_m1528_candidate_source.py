"""Expose the existing M15.28 action library through the HRC source contract."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_candidate_source_interface import (
    OUTPUT_SCHEMA_VERSION,
    validate_candidate_source,
)
from tools.paper_a_manhattan.manhattan_m1528_semantic_action_library import (
    SCHEMA_VERSION as M1528_SCHEMA_VERSION,
    run_action_library,
)


SOURCE_ID = "legacy_m1528"


def load_legacy_m1528_candidates(
    pairs: Sequence[Mapping[str, Any]],
    *,
    expert_assertion: Mapping[str, Any],
    projection_config: Mapping[str, Any],
) -> dict[str, Any]:
    legacy = run_action_library(
        pairs,
        expert_assertion=expert_assertion,
        projection_config=projection_config,
    )
    payload = {
        "source_id": SOURCE_ID,
        "source_type": "legacy_m1528_action_library",
        "source_version": M1528_SCHEMA_VERSION,
        "generator_role": "legacy_wrapper",
        "candidate_generation_allowed": False,
        "candidate_count": len(legacy["candidate_set"]),
        "candidate_set": legacy["candidate_set"],
        "case_contract": legacy["case_contract"],
        "source_provenance": {
            "legacy_source_module": "tools.paper_a_manhattan.manhattan_m1528_semantic_action_library",
            "legacy_source_function": "run_action_library",
        },
        "source_limitations": [
            "legacy candidates only",
            "no constrained_v0 generator",
            "no new candidate strategy",
        ],
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "no_new_candidate_strategy_introduced": True,
        "legacy_payload": legacy,
    }
    validate_candidate_source(payload)
    return payload
