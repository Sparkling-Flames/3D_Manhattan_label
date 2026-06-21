import json

import pytest

from tools.paper_a_manhattan.manhattan_candidate_source_interface import (
    OUTPUT_SCHEMA_VERSION,
    validate_candidate_source,
)
from tools.paper_a_manhattan.manhattan_constrained_v0_candidate_source import (
    build_column_x_alignment_shadow_source,
    build_constrained_v0_shadow_source,
    build_height_target_reproject_shadow_source,
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


def _column_source(
    *,
    protected=False,
    movable=True,
    conflict=False,
    identity=True,
    second_center=30.0,
    keep_distinct=True,
    top_x=10.0,
    bottom_x=12.0,
    seam_safe=False,
    projection_config=None,
):
    return build_column_x_alignment_shadow_source(
        [
            {
                "effective_pair_index": 1,
                "top": {"x": top_x, "y": 20.0},
                "bottom": {"x": bottom_x, "y": 80.0},
            },
            {
                "effective_pair_index": 2,
                "top": {"x": second_center, "y": 25.0},
                "bottom": {"x": second_center, "y": 75.0},
            },
        ],
        {
            "protected_pairs": [1] if protected else [],
            "movable_fields_by_pair": {"1": ["x"]} if movable else {},
            "keep_distinct_pairs": [[1, 2]] if keep_distinct else [],
        },
        {
            "evidence_status": "available",
            "visual_conflict_flags": ["corner_conflict"] if conflict else [],
            "column_identity_conflicts": [],
            "seam_ambiguous_pairs": [],
            **({"column_identity_status": "available"} if identity else {}),
            "seam_safe": seam_safe,
        },
        projection_config
        if projection_config is not None
        else {"coordinate_mode": "ls_percent", "width": 1024, "height": 512},
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
    assert candidate["eligibility_trace"]["default_margin_used"] is True


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


def test_column_identity_must_be_explicitly_available():
    payload = _column_source(identity=False)
    assert payload["candidate_set"] == []
    assert "column_identity_unavailable" in payload["unavailable_summary"]["reasons"]


def test_source_level_missing_evidence_records_evidence_and_identity_reasons():
    payload = build_column_x_alignment_shadow_source(
        [
            {
                "effective_pair_index": 1,
                "top": {"x": 10.0, "y": 20.0},
                "bottom": {"x": 12.0, "y": 80.0},
            }
        ],
        {"movable_fields_by_pair": {"1": ["x"]}},
        None,
        {"coordinate_mode": "ls_percent", "width": 1024, "height": 512},
    )
    assert payload["candidate_count"] == 0
    assert set(payload["unavailable_summary"]["reasons"]) >= {
        "evidence_unavailable",
        "column_identity_unavailable",
    }


def test_order_merge_uses_separation_margin():
    payload = _column_source(second_center=11.2, keep_distinct=False)
    assert payload["candidate_set"] == []
    assert "pair_1:order_mutation_or_pair_merge_risk" in payload["unavailable_summary"]["reasons"]


def test_keep_distinct_uses_separation_margin():
    payload = _column_source(second_center=11.2)
    assert payload["candidate_set"] == []
    assert "pair_1:keep_distinct_collapse_risk" in payload["unavailable_summary"]["reasons"]


def test_near_seam_requires_explicit_safe_flag():
    blocked = _column_source(top_x=0.1, bottom_x=0.3)
    allowed = _column_source(top_x=0.1, bottom_x=0.3, seam_safe=True)
    assert blocked["candidate_set"] == []
    assert "pair_1:seam_margin_risk" in blocked["unavailable_summary"]["reasons"]
    assert allowed["candidate_count"] == 1


@pytest.mark.parametrize(
    "config,reason",
    [
        ({"coordinate_mode": "ls_percent", "width": 1024}, "projection_config_missing"),
        ({"coordinate_mode": "ls_percent", "width": 0, "height": 512}, "projection_config_invalid"),
    ],
)
def test_projection_config_minimum_contract(config, reason):
    payload = _column_source(projection_config=config)
    assert payload["candidate_set"] == []
    assert reason in payload["unavailable_summary"]["reasons"]


def _height_source(
    *, protected=False, movable=True, status="available", split=False, after=True
):
    summary = {
        "height_target_status": status,
        "dominant_height_target": 3.0,
        "height_outlier_pairs": [1],
        "formula_status": "explicit_after_y",
    }
    if split:
        summary["multi_height"] = True
    if after:
        summary["after_y_by_pair"] = {"1": {"top_y": 18.0}}
    return build_height_target_reproject_shadow_source(
        [
            {
                "effective_pair_index": 1,
                "top": {"x": 10.0, "y": 20.0},
                "bottom": {"x": 10.0, "y": 80.0},
            }
        ],
        {
            "protected_pairs": [1] if protected else [],
            "movable_fields_by_pair": {"1": ["top_y"]} if movable else {},
            "inferred_height_target_pairs": [],
        },
        summary,
        {},
        {
            "coordinate_mode": "ls_percent",
            "width": 1024,
            "height": 512,
            "camera_height": 1.6,
        },
    )


def test_height_target_reproject_emits_shadow_only_y_change():
    payload = _height_source()
    assert payload["candidate_count"] == 1
    assert (
        payload["source_provenance"]["implementation_status"]
        == "height_target_reproject_shadow_only"
    )
    assert (
        payload["constrained_v0_implementation_status"]
        == "height_target_reproject_shadow_only"
    )
    candidate = payload["candidate_set"][0]
    assert candidate["shadow_only"] is True
    assert candidate["accepted"] is False
    assert candidate["downstream_recommendation"] is False
    fields = candidate["coordinate_changes"][0]["fields"]
    assert set(fields) == {"top_y"}
    assert all(not field.endswith("_x") for field in fields)


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        ({"protected": True}, "protected_pair_mutation"),
        ({"movable": False}, "y_permission_missing"),
        ({"status": "unavailable"}, "height_target_unavailable"),
        ({"split": True}, "split_level_or_multi_height"),
        ({"after": False}, "height_reproject_formula_unavailable"),
    ],
)
def test_height_target_reproject_fails_closed(kwargs, reason):
    payload = _height_source(**kwargs)
    assert payload["candidate_set"] == []
    assert any(reason in value for value in payload["unavailable_summary"]["reasons"])
