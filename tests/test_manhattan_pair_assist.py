import copy
import json

from tools.paper_a_manhattan.manhattan_candidate_gate import EXPERT_REVIEW_DELTA_THRESHOLD
from tools.paper_a_manhattan.manhattan_constrained_fit import MAX_POINT_MOVE_FAIL_THRESHOLD
from tools.paper_a_manhattan.manhattan_pair_assist import (
    ELIGIBLE,
    REVIEW_ONLY,
    SUPPRESS,
    diagnose_pair_alignment,
    propose_align_pair_x,
)


TOP_Y = 32.0
BOTTOM_Y = 70.0


def _pairs_with_mismatch():
    return [
        {"top": {"x": 10.0, "y": TOP_Y}, "bottom": {"x": 10.0, "y": BOTTOM_Y}},
        {"top": {"x": 34.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
        {"top": {"x": 60.0, "y": TOP_Y}, "bottom": {"x": 60.0, "y": BOTTOM_Y}},
        {"top": {"x": 80.0, "y": TOP_Y}, "bottom": {"x": 80.0, "y": BOTTOM_Y}},
    ]


def _clean_pairs():
    return [
        {"top": {"x": 10.0, "y": TOP_Y}, "bottom": {"x": 10.0, "y": BOTTOM_Y}},
        {"top": {"x": 30.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
        {"top": {"x": 60.0, "y": TOP_Y}, "bottom": {"x": 60.0, "y": BOTTOM_Y}},
        {"top": {"x": 80.0, "y": TOP_Y}, "bottom": {"x": 80.0, "y": BOTTOM_Y}},
    ]


def _rows_for_shape(target_row):
    return [
        {"top": {"x": 10.0, "y": TOP_Y}, "bottom": {"x": 10.0, "y": BOTTOM_Y}},
        target_row,
        {"top": {"x": 60.0, "y": TOP_Y}, "bottom": {"x": 60.0, "y": BOTTOM_Y}},
        {"top": {"x": 80.0, "y": TOP_Y}, "bottom": {"x": 80.0, "y": BOTTOM_Y}},
    ]


def test_clean_pair_with_x_mismatch_generates_candidate_for_current_pair_only():
    rows = _pairs_with_mismatch()

    diagnosis = diagnose_pair_alignment(rows, 2)
    proposal = propose_align_pair_x(rows, 2)

    assert diagnosis["assist_status"] == ELIGIBLE
    assert diagnosis["vertical_x_residual"] == 4.0
    assert proposal["assist_status"] == ELIGIBLE
    assert proposal["candidate_pairs"][1]["top"]["x"] == 32.0
    assert proposal["candidate_pairs"][1]["bottom"]["x"] == 32.0
    assert proposal["candidate_pairs"][0] == rows[0]
    assert proposal["candidate_pairs"][2] == rows[2]
    assert proposal["candidate_pairs"][3] == rows[3]
    assert proposal["per_point_delta"] == [
        {
            "pair_index": 2,
            "top_dx": -2.0,
            "top_dy": 0.0,
            "bottom_dx": 2.0,
            "bottom_dy": 0.0,
        }
    ]
    assert proposal["max_abs_delta"] == 2.0


def test_small_x_mismatch_is_eligible_and_returns_candidate():
    proposal = propose_align_pair_x(_pairs_with_mismatch(), 2)

    assert proposal["assist_status"] == ELIGIBLE
    assert proposal["candidate_pairs"]
    assert proposal["max_abs_delta"] < EXPERT_REVIEW_DELTA_THRESHOLD


def test_max_abs_delta_at_expert_review_threshold_is_review_only_without_candidate():
    rows = _rows_for_shape(
        {"top": {"x": 40.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}}
    )

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["max_abs_delta"] == EXPERT_REVIEW_DELTA_THRESHOLD
    assert proposal["assist_status"] == REVIEW_ONLY
    assert proposal["assist_reasons"] == ["max_abs_delta_large"]
    assert proposal["candidate_pairs"] == []
    assert proposal["per_point_delta"] == []


def test_max_abs_delta_above_hard_move_threshold_suppresses_without_candidate():
    rows = _rows_for_shape(
        {"top": {"x": 56.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}}
    )

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["max_abs_delta"] > MAX_POINT_MOVE_FAIL_THRESHOLD
    assert proposal["assist_status"] == SUPPRESS
    assert proposal["assist_reasons"] == ["max_abs_delta_exceeds_fit_fail_threshold"]
    assert proposal["candidate_pairs"] == []
    assert proposal["per_point_delta"] == []


def test_candidate_movement_gate_does_not_modify_input_object():
    rows = _rows_for_shape(
        {"top": {"x": 40.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}}
    )
    before = copy.deepcopy(rows)

    propose_align_pair_x(rows, 2)

    assert rows == before


def test_y_values_are_unchanged():
    rows = _pairs_with_mismatch()

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["candidate_pairs"][1]["top"]["y"] == rows[1]["top"]["y"]
    assert proposal["candidate_pairs"][1]["bottom"]["y"] == rows[1]["bottom"]["y"]


def test_other_pairs_are_unchanged():
    rows = _pairs_with_mismatch()

    proposal = propose_align_pair_x(rows, 2)

    for index in (0, 2, 3):
        assert proposal["candidate_pairs"][index] == rows[index]


def test_input_object_is_not_modified():
    rows = _pairs_with_mismatch()
    before = copy.deepcopy(rows)

    propose_align_pair_x(rows, 2)

    assert rows == before


def test_missing_pair_index_suppresses():
    result = diagnose_pair_alignment(_pairs_with_mismatch(), 8)
    proposal = propose_align_pair_x(_pairs_with_mismatch(), 8)

    assert result["assist_status"] == SUPPRESS
    assert "target_pair_missing" in result["assist_reasons"]
    assert proposal["candidate_pairs"] == []
    assert proposal["assist_status"] == SUPPRESS


def test_failed_room_layout_state_suppresses():
    rows = _pairs_with_mismatch()[:3]

    result = diagnose_pair_alignment(rows, 2)
    proposal = propose_align_pair_x(rows, 2)

    assert result["assist_status"] == SUPPRESS
    assert "state_failed" in result["assist_reasons"]
    assert proposal["candidate_pairs"] == []


def test_excluded_room_layout_state_suppresses():
    result = diagnose_pair_alignment(
        _pairs_with_mismatch(),
        2,
        metadata={"scope": "oos_insufficient"},
    )
    proposal = propose_align_pair_x(
        _pairs_with_mismatch(),
        2,
        metadata={"scope": "oos_insufficient"},
    )

    assert result["assist_status"] == SUPPRESS
    assert "state_excluded" in result["assist_reasons"]
    assert proposal["candidate_pairs"] == []


def test_layout_height_spread_high_is_not_eligible():
    rows = _pairs_with_mismatch()
    rows[3]["top"]["y"] = 10.0

    result = diagnose_pair_alignment(rows, 2)
    proposal = propose_align_pair_x(rows, 2)

    assert result["assist_status"] == REVIEW_ONLY
    assert "state_warning_layout_height_spread_high" in result["assist_reasons"]
    assert proposal["candidate_pairs"] == []


def test_no_x_mismatch_is_review_only():
    result = diagnose_pair_alignment(_clean_pairs(), 2)
    proposal = propose_align_pair_x(_clean_pairs(), 2)

    assert result["assist_status"] == REVIEW_ONLY
    assert "vertical_x_residual_zero" in result["assist_reasons"]
    assert proposal["candidate_pairs"] == []


def test_candidate_is_json_serializable():
    proposal = propose_align_pair_x(_pairs_with_mismatch(), 2)

    json.dumps(proposal)


def test_no_apply_or_writeback_payload_is_produced():
    proposal = propose_align_pair_x(_pairs_with_mismatch(), 2)

    assert "annotation" not in proposal
    assert "writeback" not in proposal
    assert "apply" not in proposal


def test_only_center_strategy_is_supported():
    proposal = propose_align_pair_x(_pairs_with_mismatch(), 2, strategy="snap")

    assert proposal["assist_status"] == SUPPRESS
    assert proposal["assist_reasons"] == ["unsupported_strategy"]
    assert proposal["candidate_pairs"] == []


def test_top_bottom_shape_updates_corresponding_x_fields_for_small_mismatch():
    rows = _rows_for_shape(
        {"top": {"x": 34.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}}
    )

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["assist_status"] == ELIGIBLE
    assert proposal["candidate_pairs"][1]["top"]["x"] == 32.0
    assert proposal["candidate_pairs"][1]["bottom"]["x"] == 32.0


def test_ceiling_floor_shape_updates_corresponding_x_fields_for_small_mismatch():
    rows = _rows_for_shape(
        {"ceiling": {"x": 34.0, "y": TOP_Y}, "floor": {"x": 30.0, "y": BOTTOM_Y}}
    )

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["assist_status"] == ELIGIBLE
    assert proposal["candidate_pairs"][1]["ceiling"]["x"] == 32.0
    assert proposal["candidate_pairs"][1]["floor"]["x"] == 32.0


def test_flat_top_bottom_shape_updates_corresponding_x_fields_for_small_mismatch():
    rows = _rows_for_shape(
        {"top_x": 34.0, "top_y": TOP_Y, "bottom_x": 30.0, "bottom_y": BOTTOM_Y}
    )

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["assist_status"] == ELIGIBLE
    assert proposal["candidate_pairs"][1]["top_x"] == 32.0
    assert proposal["candidate_pairs"][1]["bottom_x"] == 32.0


def test_single_x_shape_has_no_separate_top_bottom_x_mismatch_to_candidate():
    rows = _rows_for_shape({"x": 30.0, "y_ceiling": TOP_Y, "y_floor": BOTTOM_Y})

    proposal = propose_align_pair_x(rows, 2)

    assert proposal["assist_status"] == REVIEW_ONLY
    assert proposal["assist_reasons"] == ["vertical_x_residual_zero"]
    assert proposal["candidate_pairs"] == []
