import json

import pytest

from tools.paper_a_manhattan.manhattan_candidate_source_interface import (
    OUTPUT_SCHEMA_VERSION,
    validate_candidate_source,
)
from tools.paper_a_manhattan.manhattan_constrained_v0_candidate_source import (
    build_column_x_alignment_shadow_source,
    build_constrained_v0_shadow_source,
)
from tools.paper_a_manhattan.manhattan_legacy_m1528_candidate_source import (
    load_legacy_m1528_candidates,
)
from tools.paper_a_manhattan.manhattan_m1528_semantic_action_library import run_action_library
from tools.paper_a_manhattan.run_m1528_semantic_action_library import (
    DEFAULT_ASSERTION,
    DEFAULT_PROJECTION,
)


def test_legacy_wrapper_preserves_m1528_candidate_ids():
    assertion = json.loads(DEFAULT_ASSERTION.read_text(encoding="utf-8"))
    projection = json.loads(DEFAULT_PROJECTION.read_text(encoding="utf-8"))
    original = next(row for row in projection["variants"] if row["name"] == "original")
    config = {
        "width": projection["width"],
        "height": projection["height"],
        "coordinate_mode": projection["coordinate_mode_requested"],
        "camera_height": projection["camera_height"],
    }
    direct = run_action_library(
        original["ordered_pairs"],
        expert_assertion=assertion,
        projection_config=config,
    )
    wrapped = load_legacy_m1528_candidates(
        original["ordered_pairs"],
        expert_assertion=assertion,
        projection_config=config,
    )

    direct_ids = {row["candidate_id"] for row in direct["candidate_set"]}
    wrapped_ids = {row["candidate_id"] for row in wrapped["candidate_set"]}
    assert wrapped_ids == direct_ids
    assert wrapped["candidate_count"] == len(direct_ids) > 0
    assert wrapped["candidate_generation_allowed"] is False
    assert wrapped["no_new_candidate_strategy_introduced"] is True
    assert wrapped["generator_role"] == "legacy_wrapper"


def test_constrained_v0_shadow_skeleton_is_explicitly_empty():
    payload = build_constrained_v0_shadow_source({"case_id": "shadow"})

    assert validate_candidate_source(payload) is payload
    assert payload["candidate_count"] == 0
    assert payload["candidate_set"] == []
    assert payload["candidate_generation_allowed"] is False
    assert payload["no_new_candidate_strategy_introduced"] is True
    assert "coordinate_changes" not in payload


def test_non_shadow_source_cannot_be_empty():
    payload = {
        "source_id": "invalid_empty",
        "source_type": "legacy_m1528_action_library",
        "source_version": "test",
        "generator_role": "legacy_wrapper",
        "candidate_generation_allowed": False,
        "candidate_count": 0,
        "candidate_set": [],
        "case_contract": {},
        "source_provenance": {},
        "source_limitations": [],
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
    }
    with pytest.raises(ValueError, match="must be non-empty"):
        validate_candidate_source(payload)


def _column_source(*, protected=False, movable=True, conflict=False):
    return build_column_x_alignment_shadow_source(
        [
            {
                "effective_pair_index": 1,
                "top": {"x": 10.0, "y": 20.0},
                "bottom": {"x": 12.0, "y": 80.0},
            },
            {
                "effective_pair_index": 2,
                "top": {"x": 30.0, "y": 25.0},
                "bottom": {"x": 30.0, "y": 75.0},
            },
        ],
        {
            "protected_pairs": [1] if protected else [],
            "movable_fields_by_pair": {"1": ["x"]} if movable else {},
            "keep_distinct_pairs": [[1, 2]],
        },
        {
            "evidence_status": "available",
            "visual_conflict_flags": ["corner_conflict"] if conflict else [],
            "column_identity_conflicts": [],
            "seam_ambiguous_pairs": [],
        },
        {"coordinate_mode": "ls_percent", "width": 1024, "height": 512},
    )


def test_column_x_alignment_emits_shadow_only_x_changes():
    payload = _column_source()
    assert payload["candidate_count"] == 1
    candidate = payload["candidate_set"][0]
    assert candidate["shadow_only"] is True
    assert candidate["accepted"] is False
    assert candidate["downstream_recommendation"] is False
    fields = candidate["coordinate_changes"][0]["fields"]
    assert set(fields) == {"top_x", "bottom_x"}
    assert fields["top_x"]["after"] == fields["bottom_x"]["after"] == 11.0


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"protected": True}, "protected_pair_mutation"),
        ({"movable": False}, "x_permission_missing"),
        ({"conflict": True}, "evidence_conflict"),
    ],
)
def test_column_x_alignment_rejects_ineligible_inputs(kwargs, reason):
    payload = _column_source(**kwargs)
    assert payload["candidate_set"] == []
    assert any(reason in value for value in payload["unavailable_summary"]["reasons"])
