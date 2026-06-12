import copy
import json

from tools.paper_a_manhattan.manhattan_verified_3d_local_assist import (
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
    assert candidates[0]["operation"] == TRANSLATE_PAIR_CLUSTER_X_DRYRUN
    assert candidates[0]["target_pair_indices"] == [1, 2]
    assert candidates[0]["y_change_allowed"] is False
    assert candidates[0]["writeback_allowed"] is False
    assert "before_metrics" in candidates[0]
    assert "after_metrics" in candidates[0]
    assert "candidate_pairs" not in candidates[0]
    assert "apply" not in candidates[0]
    assert "writeback" not in candidates[0]


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
