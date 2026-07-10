import copy
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_m_anchor_4_1_human_guidance_bound_footprint_shadow_probe import (
    FEEDBACK_PATH,
    GUIDANCE_PATH,
    TOP_K,
    _load,
    _validate_guidance,
    run,
)


def test_m_anchor_4_1_binds_feedback_and_stays_footprint_only(tmp_path: Path) -> None:
    paths = run(tmp_path / "m4_1", tmp_path / "review")
    payload = json.loads(paths["audit"].read_text(encoding="utf-8"))
    cards = [json.loads(line) for line in paths["cards"].read_text(encoding="utf-8").splitlines()]
    ledger = json.loads(paths["ledger"].read_text(encoding="utf-8"))

    provenance = payload["input_provenance"]
    assert provenance["m_anchor_4_human_feedback"]["path"] == FEEDBACK_PATH.as_posix()
    assert provenance["m_anchor_4_human_feedback"]["schema_version"] == "m_anchor_4_human_feedback_v1"
    assert len(provenance["m_anchor_4_human_feedback"]["sha256"]) == 64
    assert provenance["m_anchor_4_1_human_guidance_constraints"]["path"] == GUIDANCE_PATH.as_posix()
    assert len(provenance["m_anchor_4_1_human_guidance_constraints"]["sha256"]) == 64
    assert payload["allowed_variables"] == ["x", "bottom_y"]
    assert "top_y" in payload["forbidden_variables"]
    assert payload["raw_candidates_evaluated"] == 51
    assert len(cards) == payload["candidate_count"] == TOP_K
    assert payload["m_anchor_4_2_height_completion_authorized"] is False
    assert ledger["m_anchor_4_2_height_completion_authorized"] is False
    for field in (
        "accepted",
        "accepted_as_final_fix",
        "downstream_recommendation",
        "candidate_preference_authorized",
        "annotation_writeback",
        "annotation_patch_generated",
        "active_runner_role",
    ):
        assert payload[field] is False
        assert ledger[field] is False

    previous_key = None
    for card in cards:
        moves = {int(key): value for key, value in card["movement_by_axis"].items()}
        assert -0.30 <= moves[4]["x"] <= -0.05
        assert -0.30 <= moves[9]["x"] <= -0.05
        assert 0.05 <= moves[10]["x"] <= 0.15
        assert all(card["hard_gate"].values())
        assert card["top_y_changed"] is False
        assert card["height_not_entered"] is True
        assert card["decision"] == "review_available"
        assert card["accepted"] is False
        assert card["downstream_recommendation"] is False
        assert card["annotation_writeback"] is False
        key = tuple(card["ranking_layers"][name] for name in (
            "L0_human_guidance_adherence",
            "L1_visual_anchor_movement_cost",
            "L2_local_worst_wall_residual",
            "L3_local_residual_sum",
            "L3_global_residual_sum",
            "L4_topology_preservation_cost",
        ))
        if previous_key is not None:
            assert previous_key <= key
        previous_key = key

    manifest = json.loads(paths["review_manifest"].read_text(encoding="utf-8"))
    assert len(manifest["candidates"]) == TOP_K
    assert manifest["safety_boundary"]["annotation_writeback"] is False


def test_m_anchor_4_1_rejects_guidance_that_disagrees_with_feedback() -> None:
    guidance = copy.deepcopy(_load(GUIDANCE_PATH))
    guidance["directional_pair_ranges"][0]["direction"] = "right"
    with pytest.raises(ValueError, match="feedback mismatch"):
        _validate_guidance(guidance, _load(FEEDBACK_PATH))
