import json
from pathlib import Path

from tools.thesis_main.data_prep.inventory_annotation_research_assets_20260905 import (
    PRESCREEN,
    _candidate_key,
    _find_refs,
    _parse_points,
    _reference_rows,
    _split_reference_suffix,
    run,
)


ROOT = Path(__file__).resolve().parents[1]


def test_reference_parser_keeps_repo_and_remote_refs():
    refs = _find_refs("see analysis_results/foo/bar.csv and https://example.com/data/x.jpg")
    assert ("repo_path", "analysis_results/foo/bar.csv") in refs
    assert ("remote_url", "https://example.com/data/x.jpg") in refs


def test_reference_parser_splits_backtick_and_chinese_delimiters():
    refs = _find_refs("export_label/`、`active_logs/`、`import_json/")
    assert refs == [
        ("repo_path", "export_label/"),
        ("repo_path", "active_logs/"),
        ("repo_path", "import_json/"),
    ]


def test_composite_key_is_used_when_base_task_id_repeats():
    fields = ["stage", "condition", "dataset_group", "base_task_id", "threshold"]
    rows = [
        {"stage": "P1", "condition": "manual", "dataset_group": "g", "base_task_id": "x", "threshold": "0.95"},
        {"stage": "C1", "condition": "manual", "dataset_group": "g", "base_task_id": "x", "threshold": "0.95"},
    ]
    result = _candidate_key(rows, fields)
    assert result["key_status"] == "pass_composite_unique"


def test_parse_points_rejects_odd_or_short_geometry(tmp_path):
    path = tmp_path / "points.txt"
    path.write_text("1 2\n1 4\n3 2\n", encoding="utf-8")
    ok, reason, count = _parse_points(path)
    assert not ok
    assert reason == "point_count_not_even_ge4"
    assert count == 3


def test_reference_field_suffix_is_not_a_physical_filename():
    path, field = _split_reference_suffix("analysis_results/pkg/records.csv:formal_assignment_eligible")
    assert path.endswith("/records.csv")
    assert field == "formal_assignment_eligible"


def test_reference_audit_resolves_field_suffix_to_existing_file():
    rows = _reference_rows(ROOT, ["full_uncertainty_data_mining_20260821_v5"])
    row = next(item for item in rows if item["reference_text"].endswith(":formal_assignment_eligible"))
    assert row["physical_reference_path"].endswith("ROW_INCLUSION_CLASSIFICATION.csv")
    assert row["reference_field"] == "formal_assignment_eligible"
    assert row["existence_status"] == "exists"


def test_full_inventory_contract(tmp_path):
    qa = run(ROOT, tmp_path)
    assert qa["status"] == "pass_with_known_gaps"
    assert qa["count_checks"]["machine_manifest_items"] == 314
    assert qa["count_checks"]["history_existing_148"] == 148
    assert qa["count_checks"]["no_existing_annotation_166"] == 166
    assert qa["count_checks"]["human_review_30"] == 30
    assert qa["count_checks"]["remaining_candidate_136"] == 136
    assert qa["count_checks"]["old_registry_214"] == 214
    assert qa["count_checks"]["dense42"] == 42
    assert qa["count_checks"]["dense42_is_subset_of_old_registry"] is True
    assert qa["count_checks"]["dense42_equals_old_registry_membership"] is False
    assert qa["human_scope_counts"] == {"in_scope": 26, "out_of_scope": 4}
    assert qa["room_region_mapping"]["mapping_status"] == "found_region_class_only"
    assert qa["count_checks"]["selected50"] == 50
    assert qa["room_region_mapping"]["detail_rows"] > 0
    assert qa["bi_manifest"]["test"]["rows"] == 458
    assert qa["bi_manifest"]["val"]["rows"] == 190
    assert (tmp_path / "human_review_export_20260905_raw.json").read_bytes() == (
        PRESCREEN / "human_review_export_20260905.json"
    ).read_bytes()
    raw = json.loads((tmp_path / "human_review_export_20260905_raw.json").read_text(encoding="utf-8-sig"))
    assert raw["items"][6]["review"]["notes"] == "机器的是对的,gt那个标注反而是错的"
    assert (tmp_path / "building_asset_coverage.csv").is_file()
    assert (tmp_path / "room_region_mapping_audit.csv").is_file()
    assert (tmp_path / "room_region_mapping_records.csv").is_file()
    assert (tmp_path / "model_asset_summary.csv").is_file()
