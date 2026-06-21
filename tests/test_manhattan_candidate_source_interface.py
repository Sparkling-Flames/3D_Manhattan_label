import json

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
