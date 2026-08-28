import json
from pathlib import Path

from PIL import Image

from tools.thesis_main.data_prep.build_annotation_uncertainty_batch1_review import (
    DEFECTS,
    HEIGHT,
    OPTION_LABELS,
    REPAIR_ACTIONS,
    SCREEN_STRATA,
    WIDTH,
    _render_preview,
    _reference_pairs,
    _supported_split,
    _supported_gt_source,
    _write_html,
    classify_screen_stratum,
    select_broad_review_range,
    select_balanced,
)


def test_screen_accepts_both_verified_hybrid_gt_sources() -> None:
    assert _supported_split("test")
    assert _supported_split("validation")
    assert not _supported_split("train")
    assert _supported_gt_source("official_mp3d_layout_label_cor_raw_not_no_occ")
    assert _supported_gt_source("confirmed_user_manual_gt_correction")
    assert not _supported_gt_source("unknown_or_unverified")


def test_manual_gt_reference_is_read_from_label_studio_export(tmp_path) -> None:
    source = tmp_path / "manual_gt.json"
    source.write_text(json.dumps([{
        "data": {"title": "sample.png"},
        "annotations": [{"result": [
            {"type": "keypointlabels", "value": {"x": 10, "y": 20}},
            {"type": "keypointlabels", "value": {"x": 10, "y": 80}},
            {"type": "keypointlabels", "value": {"x": 60, "y": 25}},
            {"type": "keypointlabels", "value": {"x": 60, "y": 75}},
        ]}],
    }]), encoding="utf-8")

    pairs = _reference_pairs({
        "image_id": "sample",
        "gt_source_type": "confirmed_user_manual_gt_correction",
    }, source)

    assert sorted(round(pair["x"] % WIDTH, 1) for pair in pairs) == [102.4, 614.4]


def test_mechanical_screen_stratum_is_not_a_semantic_truth_family() -> None:
    assert classify_screen_stratum(pair_delta=1, false_negative_ratio=.01, false_positive_ratio=.01) == "pair_count_changed"
    assert classify_screen_stratum(pair_delta=0, false_negative_ratio=.05, false_positive_ratio=.01) == "reference_region_missing_dominant"
    assert classify_screen_stratum(pair_delta=0, false_negative_ratio=.01, false_positive_ratio=.05) == "model_region_extra_dominant"
    assert classify_screen_stratum(pair_delta=0, false_negative_ratio=.02, false_positive_ratio=.02) == "balanced_boundary_difference"
    assert all(OPTION_LABELS[value] != value for value in SCREEN_STRATA)
    assert "duplicate_redundant_corner" in DEFECTS
    assert "spurious_nonlayout_structure" in DEFECTS
    assert "topology_or_overparsing" not in DEFECTS
    assert set(DEFECTS).isdisjoint(REPAIR_ACTIONS)


def test_balanced_selection_limits_main_building_reuse() -> None:
    rows = []
    for stratum_index, stratum in enumerate(SCREEN_STRATA):
        for index in range(5):
            rows.append({
                "image_id": f"{stratum_index}-{index}",
                "building_id": f"b{stratum_index}-{index}",
                "screen_stratum": stratum,
                "score": index / 10,
            })
    selected = select_balanced(rows, main_per_stratum=2, reserve_per_stratum=1)
    main = [row for row in selected if row["candidate_role"] == "main"]
    reserve = [row for row in selected if row["candidate_role"] == "reserve"]
    assert len(main) == 8
    assert len(reserve) == 4
    assert {stratum: sum(row["screen_stratum"] == stratum for row in main) for stratum in SCREEN_STRATA} == {stratum: 2 for stratum in SCREEN_STRATA}


def test_selection_supports_supplement_counts_exclusions_and_prefix() -> None:
    rows = []
    for stratum_index, stratum in enumerate(SCREEN_STRATA):
        for index in range(4):
            rows.append({
                "image_id": f"{stratum_index}-{index}",
                "building_id": f"b{stratum_index}-{index}",
                "screen_stratum": stratum,
                "score": index / 10,
            })
    counts = dict.fromkeys(SCREEN_STRATA, 1)
    counts[SCREEN_STRATA[0]] = 2
    selected = select_balanced(
        rows,
        main_per_stratum=1,
        reserve_per_stratum=0,
        main_count_by_stratum=counts,
        excluded_image_ids={"0-0"},
        review_prefix="B1N",
    )
    assert len(selected) == 5
    assert "0-0" not in {row["image_id"] for row in selected}
    assert [row["review_id"] for row in selected] == [f"B1N-{index:03d}" for index in range(1, 6)]


def test_broad_review_range_uses_only_objective_limits_without_building_cap() -> None:
    base = {
        "screen_stratum": "pair_count_changed",
        "layout_mask_difference": .10,
        "boundary_rmse_px": 15.0,
        "pair_count_delta": 2,
        "score": 0.0,
    }
    rows = [
        {**base, "image_id": "keep-a", "building_id": "same"},
        {**base, "image_id": "keep-b", "building_id": "same"},
        {**base, "image_id": "keep-c", "building_id": "same"},
        {**base, "image_id": "exclude", "building_id": "other"},
        {**base, "image_id": "too-small", "building_id": "other", "layout_mask_difference": .049},
        {**base, "image_id": "too-many-pairs", "building_id": "other", "pair_count_delta": 6},
    ]

    selected = select_broad_review_range(rows, excluded_image_ids={"exclude"}, review_prefix="B1W")

    assert [row["image_id"] for row in selected] == ["keep-a", "keep-b", "keep-c"]
    assert [row["review_id"] for row in selected] == ["B1W-001", "B1W-002", "B1W-003"]


def test_preview_separates_original_correct_and_wrong_vertically(tmp_path) -> None:
    source = tmp_path / "source.png"
    output = tmp_path / "preview.jpg"
    Image.new("RGB", (WIDTH, HEIGHT), (100, 100, 100)).save(source)
    _render_preview({
        "image_path": source,
        "correct_pairs": [
            {"x": 0, "y_ceiling": 100, "y_floor": 400},
            {"x": WIDTH / 2, "y_ceiling": 100, "y_floor": 400},
        ],
        "wrong_pairs": [
            {"x": 0, "y_ceiling": 150, "y_floor": 350},
            {"x": WIDTH / 2, "y_ceiling": 150, "y_floor": 350},
        ],
    }, output)

    preview = Image.open(output)
    assert preview.size == (WIDTH, HEIGHT * 3)
    original = preview.getpixel((200, 100))
    correct = preview.getpixel((200, HEIGHT + 100))
    wrong = preview.getpixel((200, HEIGHT * 2 + 150))
    assert max(original) - min(original) < 10
    assert correct[1] > correct[0] + 100 and correct[1] > correct[2] + 80
    assert wrong[0] > wrong[1] + 100 and wrong[0] > wrong[2] + 100


def test_review_multiselect_uses_visible_checkboxes(tmp_path) -> None:
    _write_html([{
        "review_id": "B1-001",
        "preview_sha256": "a" * 64,
        "image_path": Path("data/example.jpg"),
    }], tmp_path)
    page = (tmp_path / "review.html").read_text(encoding="utf-8")
    assert 'type="checkbox"' in page
    assert "<select multiple" not in page
    assert 'id="splitFilter"' in page
    assert "card.dataset.split=x.split" in page
    assert "validation_warnings:validationWarnings" in page
    assert "if(invalid.length)" not in page
