import json
from pathlib import Path
import subprocess

from tools.paper_a_manhattan.run_single_image_manhattan_assist import (
    build_single_image_assist,
    main,
    render_markdown_report,
    run_single_image_assist,
)


FIXTURE_PATH = Path("tests/fixtures/paper_a_manhattan/single_image_assist_pack_v1.json")
README_INDEX_PATH = Path("docs/README_INDEX.md")
HEIGHT_CANDIDATE_SPEC_PATH = Path(
    "docs/paper_a_manhattan/CONSERVATIVE_HEIGHT_REPROJECT_CANDIDATE_SPEC_v1.md"
)
M1518_3_3741_INPUT_PATH = Path(
    "analysis_results/paper_a_manhattan/single_image_manual_test/"
    "latest_gt_checked/task218_ann3741_m1516_stabilized_input.json"
)
M1518_3_2369_INPUT_PATH = Path(
    "analysis_results/paper_a_manhattan/single_image_manual_test/"
    "latest_gt_checked/task218_ann2369_m1516_stabilized_input.json"
)
FORBIDDEN_TOP_LEVEL_FIELDS = {"annotation", "writeback", "apply", "candidate_pairs"}


def _fixture_case(case_id):
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[case_id]


def _raw_duplicate_payload(n_pairs, order):
    centers = [10.0, 10.4, *[20.0 + index * 10.0 for index in range(n_pairs - 2)]]
    keypoints = []
    for center in centers:
        keypoints.append({"x": center, "y": 32.0})
        keypoints.append({"x": center, "y": 70.0})
    return {
        "task_id": "218",
        "annotation_id": f"synthetic-{n_pairs}",
        "order_verified_by_expert": True,
        "preview_order_override": order,
        "keypoints": keypoints,
        "metadata": {"scope": "normal", "manhattan_assumable": True},
    }


def _task238_payload():
    return {
        "task_id": "238",
        "annotation_id": "2389",
        "target_pair_indices": [4],
        "metadata": {"scope": "normal", "manhattan_assumable": True},
        "result": [
            {"type": "keypointlabels", "value": {"x": 74.3810546875, "y": 40.470703125}},
            {"type": "keypointlabels", "value": {"x": 74.3810546875, "y": 67.003125}},
            {"type": "keypointlabels", "value": {"x": 90.6126953125, "y": 44.287109375}},
            {"type": "keypointlabels", "value": {"x": 90.6126953125, "y": 60.2421875}},
            {"type": "keypointlabels", "value": {"x": 2.4635470266948207, "y": 44.124096109784276}},
            {"type": "keypointlabels", "value": {"x": 2.4635470266948207, "y": 59.80567030166545}},
            {"type": "keypointlabels", "value": {"x": 45.023411241281494, "y": 34.07355598298071}},
            {"type": "keypointlabels", "value": {"x": 45.023411241281494, "y": 73.94455130073246}},
            {"type": "keypointlabels", "value": {"x": 53.508771929824576, "y": 33.583959899749374}},
            {"type": "keypointlabels", "value": {"x": 53.508771929824576, "y": 74.43609022556392}},
            {"type": "keypointlabels", "value": {"x": 66.16541353383458, "y": 8.270676691729323}},
            {"type": "keypointlabels", "value": {"x": 66.16541353383458, "y": 92.73182957393483}},
        ],
    }


def test_simplified_ordered_pairs_outputs_diagnostics_proposals_and_height_rows():
    result = build_single_image_assist(_fixture_case("simplified_ordered_pairs"))

    assert result["input_mode"] == "simplified_ordered_pairs"
    assert result["preview_compatibility"]["status"] == "not_run_simplified_ordered_pairs"
    assert len(result["ordered_pairs"]) == 4
    assert result["room_layout_state"]["state_status"] == "ok"
    assert len(result["pair_diagnostics"]) == 4
    assert len(result["align_pair_x_proposals"]) == 4
    assert len(result["height_reproject_applicability_rows"]) == 4
    assert len(result["height_reproject_candidate_rows"]) == 4
    assert result["verified_3d_local_assist"]["schema_version"] == (
        "verified_3d_local_assist_m15_15_v1"
    )
    assert len(result["manual_edit_table"]) == 4
    assert result["summary"]["n_ordered_pairs"] == 4
    assert result["tool_version"] == "single_image_manhattan_assist_m15_18_3_v1"


def test_raw_keypoints_compatible_converts_to_ordered_pairs_and_outputs_results():
    result = build_single_image_assist(_fixture_case("raw_keypoints_compatible"))

    assert result["input_mode"] == "raw_keypoints"
    assert result["preview_compatibility"]["status"] == "compatible"
    assert len(result["ordered_pairs"]) == 4
    assert result["ordered_pairs"][1]["top"]["x"] == 34.0
    assert result["ordered_pairs"][1]["bottom"]["x"] == 30.0
    assert len(result["align_pair_x_proposals"]) == 4
    assert len(result["height_reproject_applicability_rows"]) == 4


def test_raw_keypoints_odd_unpaired_is_incompatible_without_suggestions():
    result = build_single_image_assist(_fixture_case("raw_keypoints_odd"))

    assert result["input_mode"] == "raw_keypoints"
    assert result["preview_compatibility"]["status"] == "compatibility_failure_odd_keypoint"
    assert result["ordered_pairs"] == []
    assert result["room_layout_state"] is None
    assert result["align_pair_x_proposals"] == []
    assert result["height_reproject_applicability_rows"] == []
    assert result["verified_3d_local_assist"] is None
    assert result["manual_edit_table"] == []


def test_raw_keypoints_preserve_order_true_can_trigger_wrong_order_failure():
    result = build_single_image_assist(_fixture_case("raw_keypoints_preserve_order_wrong_order"))

    assert result["input_mode"] == "raw_keypoints"
    assert result["preview_compatibility"]["preserve_order"] is True
    assert result["preview_compatibility"]["status"] == "compatibility_failure_wrong_order"
    assert result["ordered_pairs"] == []
    assert result["manual_edit_table"] == []


def test_label_studio_result_input_extracts_keypoints_and_outputs_results():
    result = build_single_image_assist(_fixture_case("label_studio_result"))

    assert result["input_mode"] == "label_studio_result"
    assert result["preview_compatibility"]["status"] == "compatible"
    assert len(result["ordered_pairs"]) == 4
    assert len(result["manual_edit_table"]) == 4


def test_label_studio_result_alias_extracts_keypoints_and_outputs_results():
    result = build_single_image_assist(_fixture_case("label_studio_result_alias"))

    assert result["input_mode"] == "label_studio_result"
    assert result["preview_compatibility"]["status"] == "compatible"
    assert len(result["ordered_pairs"]) == 4
    assert len(result["height_reproject_applicability_rows"]) == 4


def test_label_studio_result_odd_keypoints_short_circuits_without_suggestions():
    result = build_single_image_assist(_fixture_case("label_studio_result_odd"))

    assert result["input_mode"] == "label_studio_result"
    assert result["preview_compatibility"]["status"] == "compatibility_failure_odd_keypoint"
    assert result["ordered_pairs"] == []
    assert result["pair_diagnostics"] == []
    assert result["align_pair_x_proposals"] == []
    assert result["manual_edit_table"] == []


def test_align_pair_x_eligible_outputs_suggested_x_and_no_y_change():
    result = build_single_image_assist(_fixture_case("simplified_ordered_pairs"))
    proposal = next(row for row in result["align_pair_x_proposals"] if row["pair_index"] == 2)
    edit_row = next(row for row in result["manual_edit_table"] if row["pair_index"] == 2)

    assert proposal["assist_status"] == "eligible"
    assert proposal["suggested_top_x"] == 32.0
    assert proposal["suggested_bottom_x"] == 32.0
    assert proposal["y_change_allowed"] is False
    assert edit_row["action"] == "align_pair_x"
    assert edit_row["to_top_x"] == 32.0
    assert edit_row["to_bottom_x"] == 32.0
    assert "to_top_y" not in edit_row
    assert "to_bottom_y" not in edit_row
    assert edit_row["y_change_allowed"] is False


def test_review_only_case_does_not_output_suggested_x():
    result = build_single_image_assist(_fixture_case("review_only_large_delta"))
    proposal = next(row for row in result["align_pair_x_proposals"] if row["pair_index"] == 2)
    edit_row = next(row for row in result["manual_edit_table"] if row["pair_index"] == 2)

    assert proposal["assist_status"] == "review_only"
    assert "max_abs_delta_large" in proposal["assist_reasons"]
    assert "suggested_top_x" not in proposal
    assert "suggested_bottom_x" not in proposal
    assert edit_row["action"] == "manual_review_only"
    assert edit_row["to_top_x"] is None
    assert edit_row["to_bottom_x"] is None
    assert edit_row["reason"] == "max_abs_delta_large"
    assert edit_row["y_change_allowed"] is False


def test_output_has_no_forbidden_top_level_fields():
    result = build_single_image_assist(_fixture_case("simplified_ordered_pairs"))

    assert FORBIDDEN_TOP_LEVEL_FIELDS.isdisjoint(result)


def test_readme_referenced_height_candidate_spec_exists_and_is_git_visible():
    text = README_INDEX_PATH.read_text(encoding="utf-8")

    assert "CONSERVATIVE_HEIGHT_REPROJECT_CANDIDATE_SPEC_v1.md" in text
    assert HEIGHT_CANDIDATE_SPEC_PATH.exists()
    git_result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(HEIGHT_CANDIDATE_SPEC_PATH)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert git_result.returncode == 0


def test_recommended_review_order_prioritizes_obvious_x_mismatch_pair():
    result = build_single_image_assist(_fixture_case("simplified_ordered_pairs"))

    first = result["recommended_review_order"][0]
    assert first["rank"] == 1
    assert first["pair_index"] == 2
    assert first["review_priority"] == "align_x_first"
    assert first["primary_action"] == "align_pair_x"
    assert first["reason"] == "align_pair_x_candidate_available"
    assert first["manual_only"] is False


def test_recommended_review_order_is_object_list_with_required_fields():
    result = build_single_image_assist(_fixture_case("review_only_large_delta"))
    first = result["recommended_review_order"][0]

    for field_name in (
        "rank",
        "pair_index",
        "review_priority",
        "primary_action",
        "assist_status",
        "height_reproject_status",
        "vertical_x_residual",
        "height_residual",
        "max_abs_delta",
        "reason",
        "manual_only",
    ):
        assert field_name in first


def test_raw_keypoints_duplicate_failure_outputs_duplicate_diagnostics():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate"))

    assert result["preview_compatibility"]["status"] == "compatibility_failure_duplicate"
    assert result["ordered_pairs"] == []
    assert result["manual_edit_table"] == []
    assert result["duplicate_diagnostics"]
    assert result["preview_pair_table"]
    assert result["near_duplicate_pair_table"]
    assert result["override_pack"]["override_needed"] is True
    assert result["override_pack"]["writeback_allowed"] is False
    diagnostic = result["duplicate_diagnostics"][0]
    assert diagnostic["reason"] == "near_duplicate_corner_pair"
    assert diagnostic["manual_only"] is True
    assert diagnostic["index_source"] == "preview_ordered_corners"


def test_simplified_dense_corner_outputs_duplicate_diagnostics_without_crashing():
    result = build_single_image_assist(_fixture_case("simplified_dense_corner"))

    assert result["input_mode"] == "simplified_ordered_pairs"
    assert result["summary"]["n_ordered_pairs"] == 4
    assert result["duplicate_diagnostics"]
    diagnostic = result["duplicate_diagnostics"][0]
    assert diagnostic["left_pair_index"] == 1
    assert diagnostic["right_pair_index"] == 2
    assert diagnostic["reason"] == "near_duplicate_corner_pair"


def test_order_zigzag_fixture_outputs_local_order_zigzag():
    result = build_single_image_assist(_fixture_case("simplified_order_zigzag"))

    assert result["order_diagnostics"]["is_x_monotonic"] is False
    assert result["order_diagnostics"]["manual_only_reason"] == "local_order_zigzag"
    assert result["order_diagnostics"]["n_direction_changes"] > 0


def test_duplicate_or_order_manual_only_pairs_do_not_get_align_pair_x_suggestions():
    dense = build_single_image_assist(_fixture_case("simplified_dense_corner"))
    dense_edit = next(row for row in dense["manual_edit_table"] if row["pair_index"] == 1)
    dense_review = next(row for row in dense["recommended_review_order"] if row["pair_index"] == 1)
    zigzag = build_single_image_assist(_fixture_case("simplified_order_zigzag"))
    zigzag_edit = next(row for row in zigzag["manual_edit_table"] if row["pair_index"] == 1)
    zigzag_review = next(row for row in zigzag["recommended_review_order"] if row["pair_index"] == 1)

    assert dense_edit["action"] == "manual_review_only"
    assert dense_edit["to_top_x"] is None
    assert dense_edit["to_bottom_x"] is None
    assert dense_review["manual_only"] is True
    assert dense_review["primary_action"] == "manual_review_only"
    assert dense_review["reason"] == "near_duplicate_corner_pair"
    assert zigzag_edit["action"] == "manual_review_only"
    assert zigzag_edit["to_top_x"] is None
    assert zigzag_edit["to_bottom_x"] is None
    assert zigzag_review["manual_only"] is True
    assert zigzag_review["reason"] == "local_order_zigzag"


def test_verified_preview_order_override_allows_duplicate_raw_input_to_continue():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_with_verified_order"))

    assert result["preview_compatibility"]["status"] == "compatibility_failure_duplicate"
    assert result["preview_order_override_active"] is True
    assert result["topology_source"] == "expert_verified_preview_order"
    assert (
        result["topology_override"]["topology_override_schema_version"]
        == "verified_preview_order_m15_13_v1"
    )
    assert result["default_preview_status"] == "compatibility_failure_duplicate"
    assert result["default_preview_reason"] == "near_duplicate_corner_pair"
    assert len(result["ordered_pairs"]) == 10
    assert len(result["pair_diagnostics"]) == 10
    assert len(result["manual_edit_table"]) == 10


def test_verified_preview_order_override_reorders_ordered_pairs():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_with_verified_order"))
    centers = [
        (pair["top"]["x"] + pair["bottom"]["x"]) / 2.0
        for pair in result["ordered_pairs"]
    ]

    assert centers[:4] == [20.0, 10.0, 30.0, 10.4]


def test_pair_index_mapping_preserves_verified_order_source_indices():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_with_verified_order"))
    mapping = result["pair_index_mapping"]

    assert mapping[1]["effective_pair_index"] == 2
    assert mapping[1]["source_preview_order_index"] == 1
    assert mapping[3]["effective_pair_index"] == 4
    assert mapping[3]["source_preview_order_index"] == 2
    assert mapping[1]["center_x"] == 10.0
    assert mapping[3]["center_x"] == 10.4


def test_verified_preview_order_override_allows_wrong_order_raw_input_to_continue():
    result = build_single_image_assist(_fixture_case("raw_keypoints_wrong_order_with_verified_order"))

    assert result["preview_compatibility"]["status"] == "compatibility_failure_wrong_order"
    assert result["preview_order_override_active"] is True
    assert result["topology_source"] == "expert_verified_preview_order"
    assert result["effective_preview_compatibility"]["status"] == "compatible_with_expert_verified_order"
    assert len(result["ordered_pairs"]) == 4
    assert len(result["manual_edit_table"]) == 4


def test_verified_preview_order_override_does_not_bypass_odd_unpaired_failure():
    result = build_single_image_assist(_fixture_case("raw_keypoints_odd_with_verified_order"))

    assert result["preview_compatibility"]["status"] == "compatibility_failure_odd_keypoint"
    assert result["preview_order_override_active"] is False
    assert result["topology_source"] == "preview_order_override_not_allowed_for_status"
    assert result["effective_preview_compatibility"]["status"] == (
        "preview_order_override_not_allowed_for_status"
    )
    assert result["ordered_pairs"] == []
    assert result["manual_edit_table"] == []
    assert result["align_pair_x_proposals"] == []


def test_verified_preview_order_override_does_not_bypass_wraparound_failure():
    result = build_single_image_assist(_fixture_case("raw_keypoints_wraparound_with_verified_order"))

    assert result["preview_compatibility"]["status"] == "compatibility_failure_wraparound_unresolved"
    assert result["topology_source"] == "preview_order_override_not_allowed_for_status"
    assert result["effective_preview_compatibility"]["status"] == (
        "preview_order_override_not_allowed_for_status"
    )
    assert result["ordered_pairs"] == []
    assert result["manual_edit_table"] == []


def test_invalid_preview_order_override_returns_invalid_without_suggestions():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_with_invalid_order"))

    assert result["topology_source"] == "invalid_preview_order_override"
    assert result["effective_preview_compatibility"]["status"] == "invalid_preview_order_override"
    assert result["topology_override"]["invalid_reason"] == "preview_order_override_duplicate_index"
    assert result["ordered_pairs"] == []
    assert result["manual_edit_table"] == []
    assert result["align_pair_x_proposals"] == []


def test_invalid_preview_order_override_non_list_length_and_out_of_range_do_not_materialize():
    non_list_result = build_single_image_assist(_raw_duplicate_payload(8, {"order": [2, 1]}))
    length_result = build_single_image_assist(_raw_duplicate_payload(8, [2, 1, 3, 4, 6, 5, 7]))
    range_payload = _raw_duplicate_payload(8, [2, 1, 3, 4, 6, 5, 7, 9])
    range_result = build_single_image_assist(range_payload)

    assert non_list_result["topology_override"]["invalid_reason"] == (
        "preview_order_override_not_list"
    )
    assert non_list_result["ordered_pairs"] == []
    assert non_list_result["room_layout_state"] is None
    assert length_result["topology_override"]["invalid_reason"] == (
        "preview_order_override_length_mismatch"
    )
    assert length_result["ordered_pairs"] == []
    assert length_result["room_layout_state"] is None
    assert range_result["topology_override"]["invalid_reason"] == (
        "preview_order_override_out_of_range"
    )
    assert range_result["ordered_pairs"] == []
    assert range_result["room_layout_state"] is None


def test_unverified_preview_order_override_does_not_bypass_duplicate_stop():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_unverified_order"))

    assert result["preview_order_override_active"] is False
    assert result["preview_compatibility"]["status"] == "compatibility_failure_duplicate"
    assert result["ordered_pairs"] == []
    assert result["manual_edit_table"] == []


def test_task218_ann2369_list_override_materializes_verified_assist():
    result = build_single_image_assist(
        _raw_duplicate_payload(8, [2, 1, 3, 4, 6, 5, 7, 8])
    )

    assert result["preview_compatibility"]["status"] == "compatibility_failure_duplicate"
    assert result["topology_override"]["preview_order_override"] == [2, 1, 3, 4, 6, 5, 7, 8]
    assert result["override_pack"]["override_validation_status"] == "valid"
    assert result["ordered_pairs"]
    assert result["pair_index_mapping"]
    assert result["room_layout_state"]["state_status"] == "ok"
    assert result["verified_3d_local_assist"]["schema_version"] == (
        "verified_3d_local_assist_m15_15_v1"
    )


def test_task218_ann3741_list_override_with_ten_materializes_verified_assist():
    result = build_single_image_assist(
        _raw_duplicate_payload(10, [2, 1, 3, 4, 6, 5, 8, 7, 9, 10])
    )

    assert result["topology_override"]["preview_order_override"] == [
        2,
        1,
        3,
        4,
        6,
        5,
        8,
        7,
        9,
        10,
    ]
    assert result["ordered_pairs"]
    assert result["pair_index_mapping"]
    assert result["room_layout_state"]["state_status"] == "ok"
    assert result["verified_3d_local_assist"]["schema_version"] == (
        "verified_3d_local_assist_m15_15_v1"
    )
    assert result["verified_3d_local_assist"]["floorprint_sensitivity_rows"]


def test_task238_explicit_target_pair_generates_x_only_dryrun_without_writeback():
    result = build_single_image_assist(_task238_payload())
    candidates = result["verified_3d_local_assist"]["candidate_rows"]
    adaptive_rows = result["verified_3d_local_assist"]["adaptive_x_search_rows"]

    assert candidates
    assert adaptive_rows
    assert adaptive_rows[0]["target_pair_indices"] == [4]
    assert adaptive_rows[0]["confidence_label"] == "no_improvement"
    assert {tuple(row["target_pair_indices"]) for row in candidates} == {(4,)}
    assert {row["candidate_family"] for row in candidates} == {
        "translate_single_pair_x_dryrun"
    }
    assert {row["candidate_source"] for row in candidates} == {
        "explicit_target_pair_indices"
    }
    assert all(row["y_change_allowed"] is False for row in candidates)
    assert all(row["writeback_allowed"] is False for row in candidates)
    assert all("candidate_pairs" not in row for row in candidates)
    assert any(row["candidate_decision"] == "neutral_review" for row in candidates)


def test_task238_outputs_conservative_height_candidate_for_pair_four():
    result = build_single_image_assist(_task238_payload())
    rows = result["height_reproject_candidate_rows"]
    pair_four = next(row for row in rows if row["target_pair_index"] == 4)

    assert rows[0]["target_pair_index"] == 4
    assert pair_four["candidate_decision"] == "suggested_review"
    assert pair_four["height_residual_before"] > 0.45
    assert pair_four["height_residual_after"] < pair_four["height_residual_before"]
    assert pair_four["height_residual_delta"] < 0
    assert pair_four["top_x_before"] == pair_four["top_x_after"]
    assert pair_four["bottom_x_before"] == pair_four["bottom_x_after"]
    assert pair_four["writeback_allowed"] is False
    assert pair_four["annotation_patch_allowed"] is False


def test_override_dense_pairs_remain_manual_only_but_non_dense_pair_can_align_x():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_with_verified_order"))
    dense_edit = next(row for row in result["manual_edit_table"] if row["pair_index"] == 2)
    dense_review = next(row for row in result["recommended_review_order"] if row["pair_index"] == 2)
    align_edit = next(row for row in result["manual_edit_table"] if row["pair_index"] == 10)
    align_review = next(row for row in result["recommended_review_order"] if row["pair_index"] == 10)

    assert dense_edit["action"] == "manual_review_only"
    assert dense_edit["to_top_x"] is None
    assert dense_edit["to_bottom_x"] is None
    assert dense_review["manual_only"] is True
    assert dense_review["reason"] == "near_duplicate_corner_pair"
    assert result["default_order_diagnostics"]["manual_only_reason"] is None
    assert (
        result["effective_order_diagnostics"]["diagnostic_reason"]
        == "expert_verified_non_x_monotonic_order"
    )
    assert result["effective_order_diagnostics"]["manual_only_reason"] is None
    assert result["order_diagnostics"] == result["effective_order_diagnostics"]
    assert align_edit["action"] == "align_pair_x"
    assert align_edit["to_top_x"] == 90.0
    assert align_edit["to_bottom_x"] == 90.0
    assert align_review["primary_action"] == "align_pair_x"
    assert align_review["manual_only"] is False


def test_cli_output_is_json_serializable(tmp_path):
    input_path = tmp_path / "single_input.json"
    output_path = tmp_path / "single_output.json"
    input_path.write_text(
        json.dumps(_fixture_case("simplified_ordered_pairs")),
        encoding="utf-8",
    )

    exit_code = main(["--input", str(input_path), "--output", str(output_path), "--pretty"])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    json.dumps(payload)
    assert payload["tool_version"] == "single_image_manhattan_assist_m15_18_3_v1"


def test_markdown_output_is_written_with_no_writeback_disclaimer(tmp_path):
    input_path = tmp_path / "single_input.json"
    output_path = tmp_path / "single_output.json"
    markdown_path = tmp_path / "single_report.md"
    input_path.write_text(
        json.dumps(_fixture_case("simplified_ordered_pairs")),
        encoding="utf-8",
    )

    exit_code = main([
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--markdown-output",
        str(markdown_path),
        "--pretty",
    ])

    assert exit_code == 0
    text = markdown_path.read_text(encoding="utf-8")
    assert "Preview Compatibility" in text
    assert "Topology Override" in text
    assert "Pair Diagnostics" in text
    assert "Manual Edit Table" in text
    assert "Recommended Review Order" in text
    assert "align_x_first" in text
    assert "Conservative Height Reproject rows are review-level dry-runs" in text
    assert "Duplicate / Dense Corner Diagnostics" in text
    assert "Order Diagnostics" in text
    assert "Height Applicability Summary" in text
    assert "Verified 3D Local Assist" in text
    assert "Pair Index Mapping" in text
    assert "Wall Angle Diagnostics" in text
    assert "Corner Angle Diagnostics" in text
    assert "Dense Corner Reclassification" in text
    assert "Local X Translation Dry-run Candidates" in text
    assert "Adaptive Local X Search" in text
    assert "Adaptive search is a review-level bounded dry-run" in text
    assert "2D x-order crossing is not topology reordering" in text
    assert "candidate_rank" in text
    assert "candidate_decision" in text
    assert "These candidates are review-level dry-runs" in text
    assert "no UI, no apply/writeback" in text


def test_markdown_includes_hard_stop_override_and_height_sections():
    hard_stop = build_single_image_assist(_fixture_case("raw_keypoints_duplicate"))
    explicit = build_single_image_assist(_task238_payload())
    hard_stop_text = render_markdown_report(hard_stop)
    explicit_text = render_markdown_report(explicit)

    assert "## Preview Pair Table" in hard_stop_text
    assert "## Override Pack" in hard_stop_text
    assert "override pack only helps expert prepare a verified order".lower() in hard_stop_text.lower()
    assert "## Conservative Height Reproject Candidates" in explicit_text
    assert "## Verified 3D Local Assist" in explicit_text
    assert "### Adaptive Local X Search" in explicit_text
    assert "### Floor-Footprint Sensitivity" in explicit_text
    assert "### Local Dense-Corner Hypothesis Probe" in explicit_text
    assert "floorprint_sensitivity_m15_18_v1" in explicit_text
    assert "local_dense_corner_probe_m15_18_3_v1" in explicit_text
    assert "Bottom-only hypothesis rows are sensitivity-only" in explicit_text
    assert "final_top_bottom_x_aligned" in explicit_text
    assert "dense_separation_gate_passed" in explicit_text
    assert "expert_action_allowed" in explicit_text
    assert "annotation_patch_allowed" in explicit_text
    assert "No writeback / no patch." in explicit_text
    assert "Explicit target pair mode is an exploratory x-only dry-run" in explicit_text


def test_3741_human_action_summary_reports_aligned_ls_coordinates_first():
    payload = json.loads(M1518_3_3741_INPUT_PATH.read_text(encoding="utf-8"))
    result = build_single_image_assist(payload)
    text = render_markdown_report(result)
    eligible = [
        row
        for row in result["verified_3d_local_assist"]["local_dense_corner_probe_rows"]
        if row["recommendation_eligible"]
    ]

    assert eligible
    assert all(row["probe_mode"] == "align_then_translate_column" for row in eligible)
    assert all(row["top_x_after"] == row["bottom_x_after"] for row in eligible)
    assert text.index("## Human Action Summary (LS Coordinates)") < text.index(
        "## Preview Compatibility"
    )
    assert "### Candidate 1: align-then-translate column" in text
    assert "- LS coordinate change:" in text
    assert "- effective_pair_index: 5" in text
    assert "- source_preview_order_index: 6" in text
    assert "bottom_only_sensitivity" not in text.split("## Preview Compatibility")[0]


def test_2369_and_task238_human_summary_has_no_dense_edit_suggestion():
    payload_2369 = json.loads(M1518_3_2369_INPUT_PATH.read_text(encoding="utf-8"))
    text_2369 = render_markdown_report(build_single_image_assist(payload_2369))
    text_238 = render_markdown_report(build_single_image_assist(_task238_payload()))

    for text in (text_2369, text_238):
        summary = text.split("## Preview Compatibility")[0]
        assert "No direct LS-coordinate edit suggestion." in summary
        assert "Only diagnostic/sensitivity rows are available." in summary
        assert "align-then-translate column" not in summary


def test_verified_3d_local_assist_generates_dryrun_rows_for_verified_dense_case():
    result = build_single_image_assist(_fixture_case("raw_keypoints_duplicate_with_verified_order"))

    assist = result["verified_3d_local_assist"]
    assert assist["schema_version"] == "verified_3d_local_assist_m15_15_v1"
    assert assist["dense_corner_reclassification"]
    assert assist["dense_corner_reclassification"][0]["classification"] == (
        "dense_but_distinct_3d_corner"
    )
    assert assist["wall_angle_table"]
    assert assist["corner_angle_table"]
    assert assist["candidate_rows"]
    assert any(
        (candidate["local_geometry_score_delta"] or 0) != 0
        for candidate in assist["candidate_rows"]
    )
    for candidate in assist["candidate_rows"]:
        assert "candidate_rank" in candidate
        assert "candidate_family" in candidate
        assert "candidate_decision" in candidate
        assert "decision_reasons" in candidate
        assert "before_local_geometry_metrics" in candidate
        assert "after_local_geometry_metrics" in candidate
        assert "before_local_wall_angle_summary" in candidate
        assert "after_local_wall_angle_summary" in candidate
        assert "affected_wall_indices" in candidate
        assert "affected_corner_indices" in candidate
        assert "x_order_crossing_after_translation" in candidate
        assert "crossing_scope" in candidate
        assert candidate["y_change_allowed"] is False
        assert candidate["writeback_allowed"] is False
        assert "candidate_pairs" not in candidate
        assert "apply" not in candidate
        assert "writeback" not in candidate


def test_markdown_reports_topology_override_when_active(tmp_path):
    input_path = tmp_path / "single_input.json"
    markdown_path = tmp_path / "single_report.md"
    input_path.write_text(
        json.dumps(_fixture_case("raw_keypoints_duplicate_with_verified_order")),
        encoding="utf-8",
    )

    main(["--input", str(input_path), "--markdown-output", str(markdown_path), "--pretty"])

    text = markdown_path.read_text(encoding="utf-8")
    assert "Topology Override" in text
    assert "expert_verified_preview_order" in text
    assert "Manual preview order selected" in text


def test_run_single_image_assist_returns_payload_without_stdout_requirement(tmp_path):
    input_path = tmp_path / "single_input.json"
    output_path = tmp_path / "single_output.json"
    input_path.write_text(
        json.dumps(_fixture_case("raw_keypoints_compatible")),
        encoding="utf-8",
    )

    payload = run_single_image_assist(input_path, output_path, pretty=True)

    assert payload["preview_compatibility"]["status"] == "compatible"
    assert output_path.exists()
