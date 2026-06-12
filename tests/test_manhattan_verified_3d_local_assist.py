import copy
import json

from tools.paper_a_manhattan.manhattan_verified_3d_local_assist import (
    SEPARATE_DENSE_PAIR_X_DRYRUN,
    TRANSLATE_SINGLE_PAIR_X_DRYRUN,
    TRANSLATE_PAIR_CLUSTER_X_DRYRUN,
    VERIFIED_3D_LOCAL_ASSIST_VERSION,
    build_verified_3d_local_assist,
)


VERIFIED_TOPOLOGY = {
    "preview_order_override_active": True,
    "order_verified_by_expert": True,
    "topology_source": "expert_verified_preview_order",
}


def _distinct_dense_pairs():
    return [
        {"top": {"x": 10.0, "y": 30.0}, "bottom": {"x": 10.0, "y": 70.0}},
        {"top": {"x": 10.4, "y": 20.0}, "bottom": {"x": 10.4, "y": 88.0}},
        {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
    ]


def _true_duplicate_pairs():
    return [
        {"top": {"x": 10.0, "y": 30.0}, "bottom": {"x": 10.0, "y": 70.0}},
        {"top": {"x": 10.4, "y": 30.1}, "bottom": {"x": 10.4, "y": 70.1}},
        {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
    ]


def test_dense_2d_but_distinct_3d_corner_is_reclassified():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    assert result["schema_version"] == VERIFIED_3D_LOCAL_ASSIST_VERSION
    row = result["dense_corner_reclassification"][0]
    assert row["classification"] == "dense_but_distinct_3d_corner"
    assert "bev_distance_separates_dense_pair" in row["reason_tokens"]
    assert result["local_3d_diagnostics"][0]["bev_x"] is not None


def test_dense_2d_and_3d_duplicate_is_reclassified_true_duplicate_or_unresolved():
    result = build_verified_3d_local_assist(
        _true_duplicate_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    row = result["dense_corner_reclassification"][0]
    assert row["classification"] in {"true_duplicate_2d_3d", "unresolved_dense_corner"}
    assert row["bev_distance"] < 0.1


def test_verified_order_active_generates_x_only_translation_dryrun_candidates():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    candidates = result["candidate_rows"]
    assert candidates
    families = {candidate["candidate_family"] for candidate in candidates}
    assert TRANSLATE_SINGLE_PAIR_X_DRYRUN in families
    assert TRANSLATE_PAIR_CLUSTER_X_DRYRUN in families
    assert SEPARATE_DENSE_PAIR_X_DRYRUN in families
    first = candidates[0]
    assert first["candidate_rank"] == 1
    assert first["y_change_allowed"] is False
    assert first["writeback_allowed"] is False
    assert first["expert_action_allowed"] is False
    assert "before_metrics" in first
    assert "after_metrics" in first
    assert "before_local_geometry_metrics" in first
    assert "after_local_geometry_metrics" in first
    assert "geometry_metric_deltas" in first
    assert "local_geometry_score_delta" in first
    assert "decision_reasons" in first
    assert "candidate_pairs" not in first
    assert "apply" not in first
    assert "writeback" not in first


def test_angle_tables_are_reported_with_order_provenance():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
        pair_index_mapping=[
            {"effective_pair_index": 1, "source_preview_order_index": 3},
            {"effective_pair_index": 2, "source_preview_order_index": 1},
            {"effective_pair_index": 3, "source_preview_order_index": 4},
            {"effective_pair_index": 4, "source_preview_order_index": 2},
        ],
    )

    wall = result["wall_angle_table"][0]
    for field_name in (
        "wall_index",
        "from_pair_index",
        "to_pair_index",
        "from_source_preview_order_index",
        "to_source_preview_order_index",
        "direction_deg",
        "nearest_manhattan_axis_deg",
        "angle_residual_deg",
        "length",
    ):
        assert field_name in wall
    assert wall["from_source_preview_order_index"] == 3

    corner = result["corner_angle_table"][0]
    assert "turn_angle_deg" in corner
    assert "angle_to_90_residual_deg" in corner
    assert "local_angle_warning" in corner
    assert corner["corner_source_preview_order_index"] == 3


def test_candidate_rows_include_angle_delta_and_affected_indices():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    candidate = result["candidate_rows"][0]
    for field_name in (
        "before_local_wall_angle_summary",
        "after_local_wall_angle_summary",
        "wall_angle_residual_sum_delta_deg",
        "wall_angle_residual_max_delta_deg",
        "affected_wall_indices",
        "affected_corner_indices",
    ):
        assert field_name in candidate
    assert isinstance(candidate["affected_wall_indices"], list)
    assert isinstance(candidate["affected_corner_indices"], list)


def test_x_order_crossing_is_warning_only_and_no_apply_permission():
    result = build_verified_3d_local_assist(
        [
            {"top": {"x": 10.0, "y": 30.0}, "bottom": {"x": 10.0, "y": 70.0}},
            {"top": {"x": 10.2, "y": 30.0}, "bottom": {"x": 10.2, "y": 70.0}},
            {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
            {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
        ],
        topology_override=VERIFIED_TOPOLOGY,
        target_pair_indices=[1],
    )

    crossing_candidate = next(
        candidate
        for candidate in result["candidate_rows"]
        if candidate["target_pair_indices"] == [1] and candidate["dx"] == 0.25
    )
    assert crossing_candidate["x_order_crossing_after_translation"] is True
    assert crossing_candidate["crossed_pair_indices"] == [2]
    assert crossing_candidate["crossing_scope"] == "2d_x_only_not_topology"
    assert "x_order_crossing_after_translation" in crossing_candidate["decision_reasons"]
    assert crossing_candidate["expert_action_allowed"] is False
    assert crossing_candidate["writeback_allowed"] is False
    assert crossing_candidate["y_change_allowed"] is False
    assert "candidate_pairs" not in crossing_candidate
    assert "apply" not in crossing_candidate


def test_translation_dryrun_does_not_mutate_input_or_pair_order():
    pairs = _distinct_dense_pairs()
    before = copy.deepcopy(pairs)

    result = build_verified_3d_local_assist(
        pairs,
        topology_override=VERIFIED_TOPOLOGY,
    )

    assert pairs == before
    assert result["candidate_rows"]
    assert result["local_3d_diagnostics"][0]["pair_index"] == 1
    assert result["local_3d_diagnostics"][1]["pair_index"] == 2


def test_order_not_verified_does_not_generate_translation_candidate():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override={
            "preview_order_override_active": True,
            "order_verified_by_expert": False,
            "topology_source": "expert_verified_preview_order",
        },
    )

    assert result["dense_corner_reclassification"][0]["classification"] == (
        "dense_but_distinct_3d_corner"
    )
    assert result["candidate_rows"] == []


def test_explicit_target_pair_indices_can_generate_dryrun_when_verified():
    result = build_verified_3d_local_assist(
        _true_duplicate_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
        target_pair_indices=[3],
    )

    assert result["candidate_rows"]
    assert result["candidate_rows"][0]["target_pair_indices"] == [3]


def test_output_is_json_serializable_and_has_no_annotation_patch_fields():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    json.dumps(result)
    assert "annotation" not in result
    assert "candidate_pairs" not in result
    assert "apply" not in result
    assert "writeback" not in result


def test_candidate_can_be_suggested_review_when_local_geometry_score_improves():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    assert any(
        candidate["candidate_decision"] == "suggested_review"
        and candidate["local_geometry_score_delta"] < 0
        for candidate in result["candidate_rows"]
    )


def test_candidate_can_be_suppressed_for_short_wall_or_self_intersection():
    result = build_verified_3d_local_assist(
        _true_duplicate_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
        target_pair_indices=[1],
    )

    suppressed = [
        candidate
        for candidate in result["candidate_rows"]
        if candidate["candidate_decision"] == "suppress"
    ]
    assert suppressed
    assert any(
        "local_wall_too_short" in candidate["decision_reasons"]
        or "local_fold_or_self_intersection" in candidate["decision_reasons"]
        for candidate in suppressed
    )
