import json
from pathlib import Path

from tools.paper_a_manhattan.run_single_image_manhattan_assist import (
    build_single_image_assist,
    main,
    run_single_image_assist,
)


FIXTURE_PATH = Path("tests/fixtures/paper_a_manhattan/single_image_assist_pack_v1.json")
FORBIDDEN_TOP_LEVEL_FIELDS = {"annotation", "writeback", "apply", "candidate_pairs"}


def _fixture_case(case_id):
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[case_id]


def test_simplified_ordered_pairs_outputs_diagnostics_proposals_and_height_rows():
    result = build_single_image_assist(_fixture_case("simplified_ordered_pairs"))

    assert result["input_mode"] == "simplified_ordered_pairs"
    assert result["preview_compatibility"]["status"] == "not_run_simplified_ordered_pairs"
    assert len(result["ordered_pairs"]) == 4
    assert result["room_layout_state"]["state_status"] == "ok"
    assert len(result["pair_diagnostics"]) == 4
    assert len(result["align_pair_x_proposals"]) == 4
    assert len(result["height_reproject_applicability_rows"]) == 4
    assert len(result["manual_edit_table"]) == 4
    assert result["summary"]["n_ordered_pairs"] == 4


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
    assert payload["tool_version"] == "single_image_manhattan_assist_m15_11_v1"


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
    assert "Pair Diagnostics" in text
    assert "Manual Edit Table" in text
    assert "Recommended Review Order" in text
    assert "align_x_first" in text
    assert "Do not edit y from this report" in text
    assert "Duplicate / Dense Corner Diagnostics" in text
    assert "Order Diagnostics" in text
    assert "Height Applicability Summary" in text
    assert "no UI, no apply/writeback" in text


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
