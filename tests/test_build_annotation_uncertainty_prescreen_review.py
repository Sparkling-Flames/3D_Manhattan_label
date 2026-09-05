import json
from collections import Counter
from pathlib import Path

from tools.thesis_main.data_prep.build_annotation_uncertainty_prescreen_review import (
    ROOT,
    _id_set_sha256,
    apply_visual_review,
    build_inventory,
    diagnose_pair_order,
    select_human_batch,
    write_review_html,
)


def _pairs(order: list[int], *, seam_equivalent: bool = False) -> list[dict[str, float]]:
    xs = [100.0, 700.0, 300.0, 900.0]
    rows = []
    for index in order:
        x = xs[index]
        if seam_equivalent and index == 0:
            x = 1024.0
        rows.append({
            "x": x,
            "y_ceiling": 80.0 + index * 11.0,
            "y_floor": 420.0 - index * 13.0,
        })
    return rows


def test_pair_order_diagnostics_ignore_rotation_and_seam_equivalence() -> None:
    reference = _pairs([0, 1, 2, 3])
    rotated = _pairs([2, 3, 0, 1])
    result = diagnose_pair_order(reference, rotated)
    assert result["warnings"] == []
    assert result["best_orientation"] == "forward"
    assert result["best_rmse_px"] == 0.0

    seam_reference = [
        {"x": 0.0, "y_ceiling": 100.0, "y_floor": 400.0},
        {"x": 512.0, "y_ceiling": 120.0, "y_floor": 380.0},
    ]
    seam_candidate = [
        {"x": 1024.0, "y_ceiling": 100.0, "y_floor": 400.0},
        {"x": 512.0, "y_ceiling": 120.0, "y_floor": 380.0},
    ]
    assert diagnose_pair_order(seam_reference, seam_candidate)["warnings"] == []


def test_pair_order_diagnostics_separate_winding_from_non_cyclic_reorder() -> None:
    reference = _pairs([0, 1, 2, 3])
    reversed_result = diagnose_pair_order(reference, _pairs([3, 2, 1, 0]))
    assert reversed_result["warnings"] == ["reversed_winding"]
    assert reversed_result["best_orientation"] == "reversed"

    sorted_x_result = diagnose_pair_order(reference, _pairs([0, 2, 1, 3]))
    assert "non_cyclic_reordering" in sorted_x_result["warnings"]


def test_real_inventory_has_expected_closed_sets_and_assets() -> None:
    rows, summary = build_inventory(ROOT)
    assert summary["test_total"] == 458
    assert summary["formal_exposed"] == 144
    assert summary["formal_unsubmitted"] == 314
    assert summary["history_layer_counts"] == {
        "no_existing_annotation_record": 166,
        "historical_annotation_record_exists": 148,
    }
    assert summary["reference_source_counts"] == {
        "official_mp3d_layout_label_cor_raw_not_no_occ": 312,
        "confirmed_user_manual_gt_correction": 2,
    }
    assert len(rows) == len({row["image_id"] for row in rows}) == 314
    assert sum(
        "order_provenance_unavailable" in row["ordering_diagnostic"]["warnings"]
        for row in rows
    ) == 1
    for row in rows:
        for asset in row["assets"].values():
            assert (ROOT / asset["path"]).is_file()
            assert len(asset["sha256"]) == 64


def test_selection_is_exact_reproducible_and_building_bounded() -> None:
    rows = []
    for building_index in range(15):
        building = f"building-{building_index:02d}"
        for index in range(4):
            rows.append({
                "image_id": f"{building}-core-{index}",
                "building_id": building,
                "history_layer": "no_existing_annotation_record",
                "machine": {
                    "scope_hint": "core",
                    "risk_families": [],
                    "reference_flags": [],
                    "prelabel_flags": [] if index == 0 else [{"code": "visible_boundary_difference"}],
                },
            })
        for index in range(2):
            rows.append({
                "image_id": f"{building}-boundary-{index}",
                "building_id": building,
                "history_layer": "no_existing_annotation_record",
                "machine": {
                    "scope_hint": "boundary",
                    "risk_families": [["open_or_multiroom", "seam"][index]],
                    "reference_flags": [],
                    "prelabel_flags": [],
                },
            })

    selected, summary = select_human_batch(rows)
    assert len(selected) == 30
    assert Counter(row["machine"]["scope_hint"] for row in selected) == {"core": 24, "boundary": 6}
    assert {row["building_id"] for row in selected} == {f"building-{index:02d}" for index in range(15)}
    assert max(Counter(row["building_id"] for row in selected).values()) <= 3
    assert all(row["history_layer"] == "no_existing_annotation_record" for row in selected)
    assert [row["image_id"] for row in selected] == [row["image_id"] for row in select_human_batch(rows)[0]]
    assert summary["composition_deviation"] == []


def test_visual_review_groups_use_stable_machine_ids(tmp_path: Path) -> None:
    rows = [{
        "machine_id": "M001",
        "image_id": "building_00000000000000000000000000000000",
        "machine": {
            "scope_hint": "core",
            "scope_reason": "pending",
            "risk_families": [],
            "reference_flags": [],
            "prelabel_flags": [],
        },
    }]
    review = tmp_path / "review.json"
    review.write_text(json.dumps({
        "reviewed_all_contact_sheets": True,
        "reviewed_image_ids_sha256": _id_set_sha256({rows[0]["image_id"]}),
        "default": {"scope_hint": "core", "scope_reason": "default"},
        "groups": [{
            "machine_ids": ["M001"],
            "scope_hint": "boundary",
            "scope_reason": "开放空间。",
            "risk_families": ["open_or_multiroom"],
        }],
        "overrides": {},
    }), encoding="utf-8")
    apply_visual_review(rows, review)
    assert rows[0]["machine"]["scope_hint"] == "boundary"
    assert rows[0]["machine"]["risk_families"] == ["open_or_multiroom"]


def test_selection_records_adjacent_category_fallback() -> None:
    rows = []
    for building_index in range(15):
        for image_index in range(3):
            rows.append({
                "image_id": f"b{building_index:02d}-core-{image_index}",
                "building_id": f"b{building_index:02d}",
                "history_layer": "no_existing_annotation_record",
                "machine": {
                    "scope_hint": "core",
                    "risk_families": [],
                    "reference_flags": [],
                    "prelabel_flags": [],
                },
            })
    selected, summary = select_human_batch(rows)
    assert len(selected) == 30
    assert summary["core_count"] == 30 and summary["boundary_count"] == 0
    assert summary["composition_deviation"]


def test_review_page_is_minimal_and_uses_conditional_verdicts(tmp_path: Path) -> None:
    rows = [
        {
            "review_id": "P30-001",
            "image_id": "plain",
            "building_id": "b1",
            "preview_sha256": "a" * 64,
            "assets": {"image": {"path": "data/plain.png"}},
            "machine": {
                "scope_hint": "core",
                "scope_reason": "单一主导空间。",
                "risk_families": [],
                "reference_flags": [],
                "prelabel_flags": [],
            },
        },
        {
            "review_id": "P30-002",
            "image_id": "flagged",
            "building_id": "b2",
            "preview_sha256": "b" * 64,
            "assets": {"image": {"path": "data/flagged.png"}},
            "machine": {
                "scope_hint": "boundary",
                "scope_reason": "开放空间边界需人工确认。",
                "risk_families": ["open_or_multiroom"],
                "reference_flags": [{"code": "visible_geometry_question"}],
                "prelabel_flags": [{"code": "pair_count_difference"}],
            },
        },
    ]
    write_review_html(rows, tmp_path)
    page = (tmp_path / "review.html").read_text(encoding="utf-8")
    assert "范围内" in page and "范围外" in page and "不确定" in page
    assert "仅表示/顺序问题" in page and "存在实质几何问题" in page
    assert "x.machine.reference_flags.length" in page
    assert "x.machine.prelabel_flags.length" in page
    for old_term in ("Correct-Semi", "Wrong-Semi", "缺陷分类", "修复动作", "严重度", "实验角色"):
        assert old_term not in page
    payload = json.loads((tmp_path / "human_review_template.json").read_text(encoding="utf-8"))
    assert payload["items"][0]["required_fields"] == ["scope"]
    assert payload["items"][1]["required_fields"] == ["scope", "reference_verdict", "prelabel_verdict"]
