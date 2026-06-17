import copy

from tools.paper_a_manhattan.manhattan_local_floorprint_probe import (
    BOTTOM_Y_PERTURBATIONS,
    FLOORPRINT_SENSITIVITY_VERSION,
    LOCAL_DENSE_CORNER_PROBE_VERSION,
    build_floorprint_sensitivity_rows,
    build_local_dense_corner_probe_rows,
    dense_separation_gate_reasons,
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


def _column_directional_pairs():
    return [
        {
            "top": {"x": 45.75871277699946, "y": 38.23417719915377},
            "bottom": {"x": 47.75871277699946, "y": 90.53830664998344},
        },
        {
            "top": {"x": 46.15871277699946, "y": 20.136888221756294},
            "bottom": {"x": 48.15871277699946, "y": 83.34597519852424},
        },
        {"top": {"x": 20.0, "y": 36.126596005302375}, "bottom": {"x": 20.0, "y": 78.14840700283406}},
        {"top": {"x": 45.0, "y": 18.304861467516353}, "bottom": {"x": 45.0, "y": 55.942787257668435}},
        {"top": {"x": 70.0, "y": 26.525133136328925}, "bottom": {"x": 70.0, "y": 81.12383186582346}},
        {"top": {"x": 90.0, "y": 22.571513025396662}, "bottom": {"x": 90.0, "y": 72.55609346988118}},
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


def test_unresolved_dense_corner_emits_legacy_sensitivity_and_column_probe():
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
        "keep_order_with_column_floor_probe",
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
    bottom_only = [
        row for row in rows if row["probe_mode"] == "bottom_only_sensitivity"
    ]
    assert len(bottom_only) == 2
    assert all(row["confidence_label"] == "sensitivity_only" for row in bottom_only)
    assert all(row["recommendation_eligible"] is False for row in bottom_only)
    assert all(row["pair_vertical_x_consistent"] is False for row in bottom_only)
    assert all("not_editable_bottom_only" in row["decision_reasons"] for row in bottom_only)

    column = next(
        row for row in rows if row["hypothesis_id"] == "keep_order_with_column_floor_probe"
    )
    assert column["probe_mode"] == "column_constrained"
    assert column["pair_vertical_x_consistent"] is True
    for offset in column["column_xy_offsets"].values():
        assert offset["top_x_delta"] == offset["bottom_x_delta"]


def test_recommendation_rows_preserve_vertical_x_and_dense_separation_gate():
    rows = build_verified_3d_local_assist(_column_directional_pairs())[
        "local_dense_corner_probe_rows"
    ]

    recommendations = [row for row in rows if row["recommendation_eligible"]]
    assert recommendations
    for row in recommendations:
        assert row["confidence_label"] == "directional"
        assert row["probe_mode"] == "column_constrained"
        assert row["pair_vertical_x_consistent"] is True
        assert row["column_x_changed"] is True
        assert row["dense_separation_gate_passed"] is True
        assert row["dense_pair_center_x_separation_after"] >= row[
            "minimum_dense_pair_center_x_separation"
        ]
        assert row["dense_pair_bev_separation_after"] >= row[
            "minimum_dense_pair_bev_separation"
        ]


def test_dense_separation_gate_rejects_further_center_and_bev_compression():
    reasons, minimum_center, minimum_bev = dense_separation_gate_reasons(
        before_center=0.4,
        after_center=0.3,
        before_bev=0.2,
        after_bev=0.1,
    )

    assert minimum_center == 0.4
    assert minimum_bev == 0.2
    assert reasons == [
        "dense_pair_center_x_separation_reduced_below_gate",
        "dense_pair_bev_separation_reduced_below_gate",
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
