import json

from tools.paper_a_manhattan.manhattan_height_reproject_candidate import (
    FIXED_BOTTOM_TOP_Y_REPROJECT,
    build_height_reproject_candidate_rows,
)


def _task238_pairs():
    return [
        {
            "top": {"x": 2.4635470266948207, "y": 44.124096109784276},
            "bottom": {"x": 2.4635470266948207, "y": 59.80567030166545},
        },
        {
            "top": {"x": 45.023411241281494, "y": 34.07355598298071},
            "bottom": {"x": 45.023411241281494, "y": 73.94455130073246},
        },
        {
            "top": {"x": 53.508771929824576, "y": 33.583959899749374},
            "bottom": {"x": 53.508771929824576, "y": 74.43609022556392},
        },
        {
            "top": {"x": 66.16541353383458, "y": 8.270676691729323},
            "bottom": {"x": 66.16541353383458, "y": 92.73182957393483},
        },
        {
            "top": {"x": 74.3810546875, "y": 40.470703125},
            "bottom": {"x": 74.3810546875, "y": 67.003125},
        },
        {
            "top": {"x": 90.6126953125, "y": 44.287109375},
            "bottom": {"x": 90.6126953125, "y": 60.2421875},
        },
    ]


def _unsafe_top_after_pairs():
    return [
        {"top": {"x": 10.0, "y": 60.0}, "bottom": {"x": 10.0, "y": 70.0}},
        {"top": {"x": 30.0, "y": 60.0}, "bottom": {"x": 30.0, "y": 70.0}},
        {"top": {"x": 60.0, "y": 60.0}, "bottom": {"x": 60.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 20.0}, "bottom": {"x": 80.0, "y": 45.0}},
    ]


def test_task238_pair_four_is_ranked_first_and_reduces_height_residual():
    rows = build_height_reproject_candidate_rows(_task238_pairs())
    pair_four = rows[0]

    assert pair_four["target_pair_index"] == 4
    assert pair_four["operation"] == FIXED_BOTTOM_TOP_Y_REPROJECT
    assert pair_four["candidate_decision"] == "suggested_review"
    assert pair_four["height_residual_before"] > 0.45
    assert pair_four["height_residual_after"] < pair_four["height_residual_before"]
    assert pair_four["height_residual_delta"] < 0
    assert abs(pair_four["top_y_delta"]) <= 8.0


def test_height_candidate_does_not_change_x_or_emit_writeback_payload():
    row = build_height_reproject_candidate_rows(_task238_pairs(), target_pair_indices=[4])[0]

    assert row["top_x_before"] == row["top_x_after"]
    assert row["bottom_x_before"] == row["bottom_x_after"]
    assert row["bottom_y_before"] == row["bottom_y_after"]
    assert row["bottom_y_delta"] == 0.0
    assert row["y_change_allowed"] is False
    assert row["writeback_allowed"] is False
    assert row["expert_action_allowed"] is False
    assert row["annotation_patch_allowed"] is False
    assert "candidate_pairs" not in row
    assert "annotation" not in row
    assert "writeback" not in row
    assert "apply" not in row


def test_small_residual_pairs_are_not_suggested():
    rows = build_height_reproject_candidate_rows(_task238_pairs())
    small_pairs = [row for row in rows if row["target_pair_index"] in {1, 2, 3}]

    assert small_pairs
    assert all(row["candidate_decision"] != "suggested_review" for row in small_pairs)


def test_unsafe_top_y_after_not_above_bottom_suppresses():
    row = build_height_reproject_candidate_rows(_unsafe_top_after_pairs(), target_pair_indices=[4])[0]

    assert row["candidate_decision"] == "suppress"
    assert row["gate_status"] == "suppress"
    assert "top_y_after_not_above_bottom_y" in row["gate_reasons"]
    assert row["writeback_allowed"] is False


def test_height_candidate_output_is_json_serializable():
    rows = build_height_reproject_candidate_rows(_task238_pairs())

    json.dumps(rows)
