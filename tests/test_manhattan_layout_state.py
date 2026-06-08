import copy
import json
import math

from tools.paper_a_manhattan.manhattan_constrained_fit import ls_x_to_u
from tools.paper_a_manhattan.manhattan_layout_state import build_room_layout_state


TOP_Y_FOR_THREE_METER_HEIGHT = 32.0
BOTTOM_Y = 70.0


def _pairs(xs, top_y=TOP_Y_FOR_THREE_METER_HEIGHT, bottom_y=BOTTOM_Y):
    return [
        {"x": x, "y_ceiling": top_y, "y_floor": bottom_y}
        for x in xs
    ]


def test_supports_four_ordered_pair_input_shapes():
    cases = [
        [
            {"top": {"x": x, "y": TOP_Y_FOR_THREE_METER_HEIGHT}, "bottom": {"x": x, "y": BOTTOM_Y}}
            for x in (10, 30, 60, 80)
        ],
        [
            {
                "ceiling": {"x": x, "y": TOP_Y_FOR_THREE_METER_HEIGHT},
                "floor": {"x": x, "y": BOTTOM_Y},
            }
            for x in (10, 30, 60, 80)
        ],
        [
            {
                "top_x": x,
                "top_y": TOP_Y_FOR_THREE_METER_HEIGHT,
                "bottom_x": x,
                "bottom_y": BOTTOM_Y,
            }
            for x in (10, 30, 60, 80)
        ],
        _pairs((10, 30, 60, 80)),
    ]

    for rows in cases:
        state = build_room_layout_state(rows)
        assert state["state_status"] == "ok"
        assert len(state["corners"]) == 4
        assert len(state["walls"]) == 4
        assert len(state["pair_diagnostics"]) == 4
        json.dumps(state)


def test_out_of_range_coordinate_returns_failed_state():
    state = build_room_layout_state(_pairs((10, 30, 60, 101)))

    assert state["state_status"] == "failed"
    assert state["corners"] == []
    assert "point_outside_label_studio_0_100" in state["state_warnings"]


def test_clean_rectangle_builds_room_layout_state():
    state = build_room_layout_state(_pairs((10, 30, 60, 80)))

    assert state["state_status"] == "ok"
    assert state["state_version"] == "manhattan_layout_state_m14_4_v1"
    assert state["state_warnings"] == []
    assert all(diagnostic["is_anchor_candidate"] for diagnostic in state["pair_diagnostics"])
    assert all(wall["length"] > 0 for wall in state["walls"])


def test_top_bottom_x_mismatch_is_pair_diagnostic_not_writeback():
    rows = _pairs((10, 30, 60, 80))
    rows[1] = {
        "top": {"x": 33.0, "y": TOP_Y_FOR_THREE_METER_HEIGHT},
        "bottom": {"x": 30.0, "y": BOTTOM_Y},
    }
    before = copy.deepcopy(rows)

    state = build_room_layout_state(rows)

    diagnostic = state["pair_diagnostics"][1]
    assert diagnostic["vertical_x_residual"] == 3.0
    assert "vertical_corner_x_mismatch" in diagnostic["warnings"]
    assert diagnostic["is_anchor_candidate"] is False
    assert rows == before


def test_height_outlier_increases_layout_height_spread():
    rows = _pairs((10, 30, 60, 80))
    rows[-1]["y_ceiling"] = 10.0

    state = build_room_layout_state(rows)

    assert state["state_status"] == "ok"
    assert state["layout_height_spread"] > 0.5
    assert "layout_height_spread_high" in state["state_warnings"]
    assert any(
        "height_residual_high" in diagnostic["warnings"]
        for diagnostic in state["pair_diagnostics"]
    )


def test_median_layout_height_resists_single_outlier():
    baseline = build_room_layout_state(_pairs((10, 20, 30, 60, 70, 80)))
    rows = _pairs((10, 20, 30, 60, 70, 80))
    rows[-1]["y_ceiling"] = 10.0

    state = build_room_layout_state(rows)

    assert math.isclose(
        state["layout_height_candidate"],
        baseline["layout_height_candidate"],
        abs_tol=0.05,
    )


def test_pair_count_lt_4_returns_failed_without_normal_state():
    state = build_room_layout_state(_pairs((10, 30, 60)))

    assert state["state_status"] == "failed"
    assert state["corners"] == []
    assert state["pair_diagnostics"] == []
    assert "pair_count_lt_4" in state["state_warnings"]


def test_odd_pair_count_returns_failed_without_normal_state():
    state = build_room_layout_state(_pairs((10, 20, 30, 60, 80)))

    assert state["state_status"] == "failed"
    assert state["corners"] == []
    assert state["walls"] == []
    assert "odd_pair_count" in state["state_warnings"]


def test_metadata_exclusions_return_excluded_state():
    exclusion_values = [
        "oos_open_boundary",
        "oos_split_level",
        "oos_geometry",
        "oos_insufficient",
        "open_boundary",
        "split_level",
        "non_manhattan",
    ]

    for value in exclusion_values:
        state = build_room_layout_state(_pairs((10, 30, 60, 80)), metadata={"scope": value})
        assert state["state_status"] == "excluded"
        assert value in state["state_warnings"]

    keyed_state = build_room_layout_state(
        _pairs((10, 30, 60, 80)),
        metadata={"oos_open_boundary": True},
    )
    assert keyed_state["state_status"] == "excluded"
    assert "oos_open_boundary" in keyed_state["state_warnings"]


def test_manhattan_assumable_false_like_metadata_is_excluded():
    for value in (False, "false", "0", "no", 0):
        state = build_room_layout_state(
            _pairs((10, 30, 60, 80)),
            metadata={"manhattan_assumable": value},
        )
        assert state["state_status"] == "excluded"
        assert "not_manhattan_assumable" in state["state_warnings"]


def test_label_studio_projection_is_numerically_stable():
    state = build_room_layout_state(_pairs((25, 35, 65, 75)))
    first_corner = state["corners"][0]

    assert state["state_status"] == "ok"
    assert math.isclose(first_corner["u_rad"], ls_x_to_u(25.0), abs_tol=1e-12)
    assert first_corner["floor_distance"] > 0
    assert math.isclose(state["layout_height_candidate"], 3.0, abs_tol=0.05)


def test_wrap_seam_unresolved_returns_failed_state():
    state = build_room_layout_state(_pairs((2, 30, 60, 98)))

    assert state["state_status"] == "failed"
    assert "wrap_seam_unresolved" in state["state_warnings"]
