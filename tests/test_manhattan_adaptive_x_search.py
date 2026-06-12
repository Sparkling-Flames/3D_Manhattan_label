import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_verified_3d_local_assist import (
    ADAPTIVE_X_SEARCH_VERSION,
    TRANSLATE_PAIR_CLUSTER_X_ADAPTIVE_SEARCH,
    TRANSLATE_SINGLE_PAIR_X_ADAPTIVE_SEARCH,
    build_verified_3d_local_assist,
)


VERIFIED_TOPOLOGY = {
    "preview_order_override_active": True,
    "order_verified_by_expert": True,
    "topology_source": "expert_verified_preview_order",
}


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


def _distinct_dense_pairs():
    return [
        {"top": {"x": 10.0, "y": 30.0}, "bottom": {"x": 10.0, "y": 70.0}},
        {"top": {"x": 10.4, "y": 20.0}, "bottom": {"x": 10.4, "y": 88.0}},
        {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
    ]


def _crossing_pairs():
    return [
        {"top": {"x": 10.0, "y": 30.0}, "bottom": {"x": 10.0, "y": 70.0}},
        {"top": {"x": 10.2, "y": 30.0}, "bottom": {"x": 10.2, "y": 70.0}},
        {"top": {"x": 50.0, "y": 30.0}, "bottom": {"x": 50.0, "y": 70.0}},
        {"top": {"x": 80.0, "y": 30.0}, "bottom": {"x": 80.0, "y": 70.0}},
    ]


def test_explicit_target_generates_adaptive_x_search_row_with_curve():
    result = build_verified_3d_local_assist(_task238_pairs(), target_pair_indices=[4])

    rows = result["adaptive_x_search_rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["search_schema_version"] == ADAPTIVE_X_SEARCH_VERSION
    assert row["search_family"] == TRANSLATE_SINGLE_PAIR_X_ADAPTIVE_SEARCH
    assert row["target_pair_indices"] == [4]
    assert row["search_range"] == [-0.75, 0.75]
    assert -0.75 <= row["best_dx"] <= 0.75
    curve_dx = {point["dx"] for point in row["score_curve"]}
    assert set(row["coarse_grid"]).issubset(curve_dx)
    assert set(row["fine_grid"]).issubset(curve_dx)
    assert len(row["score_curve"]) > len(row["coarse_grid"])
    assert row["y_change_allowed"] is False
    assert row["writeback_allowed"] is False
    assert row["expert_action_allowed"] is False
    assert row["annotation_patch_allowed"] is False
    assert "candidate_pairs" not in row
    assert "annotation" not in row
    assert "writeback" not in row
    assert "apply" not in row


def test_task238_adaptive_x_search_is_no_improvement_not_height_solution():
    result = build_verified_3d_local_assist(_task238_pairs(), target_pair_indices=[4])
    row = result["adaptive_x_search_rows"][0]

    assert row["confidence_label"] == "no_improvement"
    assert row["best_score"] >= row["baseline_score"]
    assert "best_score_not_better_than_baseline" in row["decision_reasons"]


def test_flat_score_region_marks_flat_uncertain():
    result = build_verified_3d_local_assist(_crossing_pairs(), target_pair_indices=[1])
    row = result["adaptive_x_search_rows"][0]

    assert row["confidence_label"] == "flat_uncertain"
    assert row["flat_score_region"] is True
    assert row["flat_score_dx_min"] is not None
    assert row["flat_score_dx_max"] is not None


def test_x_order_crossing_is_score_curve_warning_not_topology_rewrite():
    result = build_verified_3d_local_assist(_crossing_pairs(), target_pair_indices=[1])
    row = result["adaptive_x_search_rows"][0]

    assert any(point["x_order_crossing_after_translation"] for point in row["score_curve"])
    assert result["local_3d_diagnostics"][0]["pair_index"] == 1
    assert result["local_3d_diagnostics"][1]["pair_index"] == 2
    assert row["writeback_allowed"] is False
    assert row["annotation_patch_allowed"] is False


def test_dense_case_generates_adaptive_rows_and_keeps_fixed_grid_candidates():
    result = build_verified_3d_local_assist(
        _distinct_dense_pairs(),
        topology_override=VERIFIED_TOPOLOGY,
    )

    adaptive_rows = result["adaptive_x_search_rows"]
    assert adaptive_rows
    assert result["candidate_rows"]
    assert {row["search_family"] for row in adaptive_rows} == {
        TRANSLATE_SINGLE_PAIR_X_ADAPTIVE_SEARCH,
        TRANSLATE_PAIR_CLUSTER_X_ADAPTIVE_SEARCH,
    }
    assert all(row["writeback_allowed"] is False for row in adaptive_rows)
    assert all(row["annotation_patch_allowed"] is False for row in adaptive_rows)


def test_adaptive_output_is_json_serializable():
    result = build_verified_3d_local_assist(_task238_pairs(), target_pair_indices=[4])

    json.dumps(result["adaptive_x_search_rows"])


def test_string_override_field_is_not_reintroduced():
    forbidden = "preview_order_override" + "_string"
    roots = [
        Path("tools/paper_a_manhattan"),
        Path("tests"),
        Path("docs/paper_a_manhattan"),
        Path("docs/README_INDEX.md"),
    ]
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for path in paths:
            if path.is_file() and path.suffix in {".py", ".md"}:
                assert forbidden not in path.read_text(encoding="utf-8")
