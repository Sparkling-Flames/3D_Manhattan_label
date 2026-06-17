import copy

from tools.paper_a_manhattan.manhattan_local_floorprint_probe import (
    BOTTOM_Y_PERTURBATIONS,
    FLOORPRINT_SENSITIVITY_VERSION,
    LOCAL_DENSE_CORNER_PROBE_VERSION,
    build_floorprint_sensitivity_rows,
    build_local_dense_corner_probe_rows,
)
from tools.paper_a_manhattan.manhattan_verified_3d_local_assist import (
    build_verified_3d_local_assist,
)


def _unresolved_dense_pairs():
    return [
        {"top": {"x": 9.4, "y": 30.2}, "bottom": {"x": 11.4, "y": 70.2}},
        {"top": {"x": 9.0, "y": 30.0}, "bottom": {"x": 11.0, "y": 70.0}},
        {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
    ]


def _distinct_dense_pairs():
    return [
        {"top": {"x": 10.0, "y": 30.0}, "bottom": {"x": 10.0, "y": 70.0}},
        {"top": {"x": 10.4, "y": 20.0}, "bottom": {"x": 10.4, "y": 88.0}},
        {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
    ]


def test_floorprint_sensitivity_has_six_bottom_y_rows_per_pair():
    pairs = _unresolved_dense_pairs()
    rows = build_floorprint_sensitivity_rows(pairs)

    assert len(rows) == len(pairs) * len(BOTTOM_Y_PERTURBATIONS)
    assert {row["schema_version"] for row in rows} == {
        FLOORPRINT_SENSITIVITY_VERSION
    }
    for pair_index in range(1, len(pairs) + 1):
        pair_rows = [row for row in rows if row["target_pair_index"] == pair_index]
        assert {row["bottom_y_delta"] for row in pair_rows} == set(
            BOTTOM_Y_PERTURBATIONS
        )


def test_floorprint_sensitivity_changes_only_target_bottom_y():
    pairs = _unresolved_dense_pairs()
    original = copy.deepcopy(pairs)
    row = build_floorprint_sensitivity_rows(pairs)[0]

    assert pairs == original
    assert row["top_x_before"] == row["top_x_after"]
    assert row["top_y_before"] == row["top_y_after"]
    assert row["bottom_x_before"] == row["bottom_x_after"]
    assert row["pair_order_before"] == row["pair_order_after"]
    assert row["bottom_y_after"] - row["bottom_y_before"] == row["bottom_y_delta"]
    assert row["x_order_crossing_after_translation"] is False


def test_floorprint_rows_report_wall_corner_and_height_deltas_without_permissions():
    rows = build_floorprint_sensitivity_rows(_unresolved_dense_pairs())

    for row in rows:
        assert "wall_angle_residual_sum_delta" in row
        assert "wall_angle_residual_max_delta" in row
        assert "corner_angle_residual_sum_delta" in row
        assert "height_residual_delta" in row
        assert row["writeback_allowed"] is False
        assert row["expert_action_allowed"] is False
        assert row["annotation_patch_allowed"] is False


def test_unresolved_dense_corner_emits_all_five_local_hypotheses():
    result = build_verified_3d_local_assist(_unresolved_dense_pairs())
    rows = result["local_dense_corner_probe_rows"]

    assert result["dense_corner_reclassification"][0]["classification"] == (
        "unresolved_dense_corner"
    )
    assert {row["hypothesis_id"] for row in rows} == {
        "keep_local_order",
        "local_dense_pair_order_flip",
        "allow_short_wall_between_dense_pair",
        "keep_order_with_bottom_xy_micro_probe",
        "short_wall_with_bottom_xy_micro_probe",
    }
    assert all(row["schema_version"] == LOCAL_DENSE_CORNER_PROBE_VERSION for row in rows)
    assert all(row["confidence_label"] for row in rows)
    assert all(row["writeback_allowed"] is False for row in rows)
    assert all(row["expert_action_allowed"] is False for row in rows)
    assert all(row["annotation_patch_allowed"] is False for row in rows)
    flip = next(row for row in rows if row["hypothesis_id"] == "local_dense_pair_order_flip")
    assert flip["confidence_label"] == "neutral_review"
    assert flip["local_geometry_score_delta"] < 0
    assert "score_improved_but_topology_variant_remains_neutral_review" in flip[
        "decision_reasons"
    ]
    assert "local_geometry_score_is_plausibility_not_correctness" in flip[
        "decision_reasons"
    ]


def test_dense_but_distinct_corner_does_not_trigger_topology_probe():
    result = build_verified_3d_local_assist(_distinct_dense_pairs())

    assert result["dense_corner_reclassification"][0]["classification"] == (
        "dense_but_distinct_3d_corner"
    )
    assert result["local_dense_corner_probe_rows"] == []


def test_direct_probe_returns_nonempty_suppressed_or_no_improvement_rows():
    pairs = _unresolved_dense_pairs()
    rows = build_local_dense_corner_probe_rows(
        pairs,
        [
            {
                "left_pair_index": 1,
                "right_pair_index": 2,
                "classification": "unresolved_dense_corner",
            }
        ],
    )

    assert rows
    assert any(
        row["confidence_label"] in {"suppressed", "no_improvement"}
        for row in rows
    )
    flip = next(row for row in rows if row["hypothesis_id"] == "local_dense_pair_order_flip")
    assert flip["confidence_label"] != "directional"
    assert flip["evaluation_pair_order"] != list(range(1, len(pairs) + 1))
