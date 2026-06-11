import copy
import json

from tools.paper_a_manhattan.manhattan_height_reproject_gate import (
    ELIGIBLE,
    REVIEW_ONLY,
    SUPPRESS,
    diagnose_height_reproject_applicability,
    gate_height_y_delta,
)


TOP_Y = 32.0
BOTTOM_Y = 70.0


def _clean_pairs():
    return [
        {"top": {"x": 10.0, "y": TOP_Y}, "bottom": {"x": 10.0, "y": BOTTOM_Y}},
        {"top": {"x": 30.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
        {"top": {"x": 60.0, "y": TOP_Y}, "bottom": {"x": 60.0, "y": BOTTOM_Y}},
        {"top": {"x": 80.0, "y": TOP_Y}, "bottom": {"x": 80.0, "y": BOTTOM_Y}},
    ]


def test_clean_state_with_enough_anchors_is_eligible():
    result = diagnose_height_reproject_applicability(_clean_pairs(), 2)

    assert result["state_status"] == "ok"
    assert result["target_pair_index"] == 2
    assert result["height_reproject_status"] == ELIGIBLE
    assert result["height_reproject_applicable"] is True
    assert result["height_reproject_blocking_reasons"] == []
    assert result["height_reproject_reasons"] == ["height_reproject_applicable"]
    assert result["estimated_layout_height"] is not None
    assert result["layout_height_spread"] == 0.0
    assert result["target_height_residual_before"] == 0.0
    assert result["max_y_delta"] is None
    assert result["y_delta_gate_status"] == "not_evaluated_no_candidate"
    assert result["gate_version"] == "manhattan_height_reproject_gate_m15_8_v1"


def test_oos_metadata_suppresses():
    result = diagnose_height_reproject_applicability(
        _clean_pairs(),
        2,
        metadata={"scope": "oos_open_boundary"},
    )

    assert result["height_reproject_status"] == SUPPRESS
    assert result["height_reproject_applicable"] is False
    assert "metadata_oos_open_boundary" in result["height_reproject_blocking_reasons"]


def test_oos_insufficient_suppresses():
    result = diagnose_height_reproject_applicability(
        _clean_pairs(),
        2,
        metadata={"scope": "oos_insufficient"},
    )

    assert result["height_reproject_status"] == SUPPRESS
    assert "metadata_oos_insufficient" in result["height_reproject_blocking_reasons"]


def test_false_metadata_flag_does_not_suppress_but_true_flag_does():
    false_result = diagnose_height_reproject_applicability(
        _clean_pairs(),
        2,
        metadata={"oos_insufficient": False},
    )
    true_result = diagnose_height_reproject_applicability(
        _clean_pairs(),
        2,
        metadata={"oos_insufficient": True},
    )

    assert false_result["height_reproject_status"] == ELIGIBLE
    assert false_result["height_reproject_blocking_reasons"] == []
    assert true_result["height_reproject_status"] == SUPPRESS
    assert "metadata_oos_insufficient" in true_result["height_reproject_blocking_reasons"]


def test_scope_vote_oos_open_boundary_suppresses():
    result = diagnose_height_reproject_applicability(
        _clean_pairs(),
        2,
        metadata={"scope_vote": "oos_open_boundary"},
    )

    assert result["height_reproject_status"] == SUPPRESS
    assert "metadata_oos_open_boundary" in result["height_reproject_blocking_reasons"]


def test_nested_metadata_oos_insufficient_suppresses():
    result = diagnose_height_reproject_applicability(
        _clean_pairs(),
        2,
        metadata={"review": {"tokens": ["normal", {"scope": "oos_insufficient"}]}},
    )

    assert result["height_reproject_status"] == SUPPRESS
    assert "metadata_oos_insufficient" in result["height_reproject_blocking_reasons"]


def test_false_like_manhattan_assumable_suppresses():
    for value in (False, "false", "0", "no", 0):
        result = diagnose_height_reproject_applicability(
            _clean_pairs(),
            2,
            metadata={"manhattan_assumable": value},
        )

        assert result["height_reproject_status"] == SUPPRESS
        assert "metadata_not_manhattan_assumable" in result["height_reproject_blocking_reasons"]


def test_layout_height_spread_high_is_review_only():
    rows = _clean_pairs()
    rows[3]["top"]["y"] = 10.0

    result = diagnose_height_reproject_applicability(rows, 2)

    assert result["height_reproject_status"] == REVIEW_ONLY
    assert "state_warning_layout_height_spread_high" in result["height_reproject_blocking_reasons"]


def test_floor_not_below_horizon_fallback_is_review_only():
    rows = [
        {"top": {"x": 10.0, "y": 20.0}, "bottom": {"x": 10.0, "y": 40.0}},
        {"top": {"x": 30.0, "y": 20.0}, "bottom": {"x": 30.0, "y": 40.0}},
        {"top": {"x": 60.0, "y": 20.0}, "bottom": {"x": 60.0, "y": 40.0}},
        {"top": {"x": 80.0, "y": 20.0}, "bottom": {"x": 80.0, "y": 40.0}},
    ]

    result = diagnose_height_reproject_applicability(rows, 2)

    assert result["height_reproject_status"] == REVIEW_ONLY
    assert (
        "state_warning_floor_not_below_horizon_distance_fallback"
        in result["height_reproject_blocking_reasons"]
    )


def test_target_height_residual_high_is_review_only():
    rows = _clean_pairs()
    rows[1]["top"]["y"] = 10.0

    result = diagnose_height_reproject_applicability(rows, 2)

    assert result["height_reproject_status"] == REVIEW_ONLY
    assert "target_warning_height_residual_high" in result["height_reproject_blocking_reasons"]
    assert result["target_height_residual_before"] > 0.5


def test_target_vertical_corner_x_mismatch_is_review_only():
    rows = _clean_pairs()
    rows[1]["top"]["x"] = 32.0

    result = diagnose_height_reproject_applicability(rows, 2)

    assert result["height_reproject_status"] == REVIEW_ONLY
    assert (
        "target_warning_vertical_corner_x_mismatch"
        in result["height_reproject_blocking_reasons"]
    )


def test_target_top_not_above_bottom_suppresses():
    rows = _clean_pairs()
    rows[1]["top"]["y"] = 75.0

    result = diagnose_height_reproject_applicability(rows, 2)

    assert result["height_reproject_status"] == SUPPRESS
    assert "target_warning_top_not_above_bottom" in result["height_reproject_blocking_reasons"]


def test_target_pair_missing_suppresses():
    result = diagnose_height_reproject_applicability(_clean_pairs(), 8)

    assert result["height_reproject_status"] == SUPPRESS
    assert "target_pair_missing" in result["height_reproject_blocking_reasons"]


def test_insufficient_non_target_anchors_is_review_only():
    rows = _clean_pairs()
    rows[0]["top"]["x"] = 13.0
    rows[2]["top"]["x"] = 63.0

    result = diagnose_height_reproject_applicability(rows, 2)

    assert result["height_reproject_status"] == REVIEW_ONLY
    assert "insufficient_non_target_anchor_candidates" in result["height_reproject_blocking_reasons"]


def test_gate_height_y_delta_unavailable_large_hard_fail_and_small():
    unavailable = gate_height_y_delta(None, 4.0, 10.0)
    unparseable = gate_height_y_delta("bad", 4.0, 10.0)
    large = gate_height_y_delta(4.0, 4.0, 10.0)
    hard_fail = gate_height_y_delta(10.5, 4.0, 10.0)
    small = gate_height_y_delta(3.9, 4.0, 10.0)

    assert unavailable["height_reproject_status"] == REVIEW_ONLY
    assert unavailable["height_reproject_blocking_reasons"] == ["max_y_delta_unavailable"]
    assert unparseable["height_reproject_status"] == REVIEW_ONLY
    assert large["height_reproject_status"] == REVIEW_ONLY
    assert large["height_reproject_blocking_reasons"] == ["max_y_delta_large"]
    assert hard_fail["height_reproject_status"] == SUPPRESS
    assert hard_fail["height_reproject_blocking_reasons"] == [
        "max_y_delta_exceeds_hard_fail_threshold"
    ]
    assert small["height_reproject_status"] == ELIGIBLE
    assert small["height_reproject_blocking_reasons"] == []


def test_gate_height_y_delta_invalid_thresholds_are_review_only():
    for expert_threshold, hard_threshold in (
        (None, 10.0),
        ("bad", 10.0),
        (float("inf"), 10.0),
        (-1.0, 10.0),
        (4.0, 0.0),
        (10.0, 4.0),
    ):
        result = gate_height_y_delta(3.0, expert_threshold, hard_threshold)

        assert result["height_reproject_status"] == REVIEW_ONLY
        assert result["height_reproject_blocking_reasons"] == ["invalid_y_delta_thresholds"]


def test_gate_height_y_delta_negative_delta_is_review_only():
    result = gate_height_y_delta(-1.0, 4.0, 10.0)

    assert result["height_reproject_status"] == REVIEW_ONLY
    assert result["height_reproject_blocking_reasons"] == ["invalid_max_y_delta"]
    assert result["y_delta_gate_status"] == "review_only_invalid_max_y_delta"


def test_output_is_json_serializable_and_has_no_candidate_or_writeback_fields():
    result = diagnose_height_reproject_applicability(_clean_pairs(), 2)

    json.dumps(result)
    assert "candidate_pairs" not in result
    assert "annotation" not in result
    assert "writeback" not in result
    assert "apply" not in result


def test_input_object_is_not_modified():
    rows = _clean_pairs()
    before = copy.deepcopy(rows)

    diagnose_height_reproject_applicability(rows, 2)

    assert rows == before
