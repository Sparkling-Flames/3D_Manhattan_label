from __future__ import annotations

from pathlib import Path

from tools.thesis_main.registry.freeze_trap_collection import (
    CLASS_ACCEPTABLE,
    DEFAULT_SYNTHETIC_PRESET,
    LAYOUT_COORD_CONTRACT,
    build_family_policy,
    build_final_selection_v4,
    build_legacy_disjoint_source_pool,
    build_summary,
    build_synthetic_backfill,
    build_synthetic_backfill_v4,
    build_synthetic_candidate_bank,
    load_label_studio_import_lookup,
    read_layout_txt_as_corners,
)


def test_read_layout_txt_as_corners(tmp_path: Path) -> None:
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("512 128 384\n768 100 400\n", encoding="utf-8")

    corners = read_layout_txt_as_corners(txt_path)

    assert len(corners) == 2
    assert corners[0]["x_pct"] == 50.0
    assert corners[0]["y_top_pct"] == 25.0
    assert corners[0]["y_bottom_pct"] == 75.0


def test_read_layout_txt_as_corners_from_keypoint_pairs(tmp_path: Path) -> None:
    txt_path = tmp_path / "sample_pairs.txt"
    txt_path.write_text("100 100\n100 400\n300 110\n300 390\n", encoding="utf-8")

    corners = read_layout_txt_as_corners(txt_path)

    assert len(corners) == 2
    assert round(corners[0]["x_pct"], 6) == round(100.0 * 100 / 1024, 6)
    assert round(corners[0]["y_top_pct"], 6) == round(100.0 * 100 / 512, 6)
    assert round(corners[0]["y_bottom_pct"], 6) == round(100.0 * 400 / 512, 6)


def test_build_synthetic_candidate_bank_generates_default_family_grid(tmp_path: Path) -> None:
    trap_root = tmp_path / "trapset"
    task_dir = trap_root / "semi" / CLASS_ACCEPTABLE / "task492"
    task_dir.mkdir(parents=True)
    txt_path = task_dir / "seed_base.txt"
    txt_path.write_text(
        "100 100 400\n"
        "300 110 390\n"
        "700 120 380\n"
        "900 115 385\n",
        encoding="utf-8",
    )

    seed_rows = [
        {
            "task_id": "492",
            "base_task_id": "seed_base",
            "priority_annotation": "",
            "layout_txt_path": str(txt_path.relative_to(trap_root)),
        }
    ]

    detail_rows, status_counts = build_synthetic_candidate_bank(trap_root, seed_rows)

    assert len(detail_rows) == len(DEFAULT_SYNTHETIC_PRESET)
    assert status_counts["success"] == len(DEFAULT_SYNTHETIC_PRESET)
    assert {row["family"] for row in detail_rows} == {
        preset["family"] for preset in DEFAULT_SYNTHETIC_PRESET
    }


def test_build_synthetic_candidate_bank_is_deterministic(tmp_path: Path) -> None:
    trap_root = tmp_path / "trapset"
    task_dir = trap_root / "semi" / CLASS_ACCEPTABLE / "task572"
    task_dir.mkdir(parents=True)
    txt_path = task_dir / "seed_base.txt"
    txt_path.write_text("100 100\n100 400\n300 110\n300 390\n", encoding="utf-8")

    seed_rows = [
        {
            "task_id": "572",
            "base_task_id": "seed_base",
            "priority_annotation": "",
            "layout_txt_path": str(txt_path.relative_to(trap_root)),
        }
    ]

    rows_a, _ = build_synthetic_candidate_bank(trap_root, seed_rows)
    rows_b, _ = build_synthetic_candidate_bank(trap_root, seed_rows)

    assert [row["audit_hash"] for row in rows_a] == [row["audit_hash"] for row in rows_b]


def test_build_summary_marks_manual_collection_count_as_sufficient() -> None:
    phase1_manifest = {
        "items": [
            {
                "item_id": "stage1_prescreen_manual_expert_anchor",
                "thesis_target": {"min": 20, "max": 22},
            },
            {"item_id": "stage1_prescreen_semi", "thesis_target": {"target": 18}},
        ]
    }
    manual_rows = [{"collection_class": "very_easy"} for _ in range(26)]
    seed_rows = [
        {
            "task_id": "492",
            "base_task_id": "seed",
            "priority_annotation": "",
            "layout_coord_contract": LAYOUT_COORD_CONTRACT,
        }
        for _ in range(6)
    ]
    synthetic_rows = [{"candidate_id": f"c{i}"} for i in range(24)]

    summary = build_summary(
        manual_rows=manual_rows,
        seed_rows=seed_rows,
        synthetic_detail_rows=synthetic_rows,
        synthetic_status_counts={"success": 24},
        phase1_manifest=phase1_manifest,
        semi_family_target={"family_target_allocations": [{"family": "acceptable", "target_count": 6}]},
    )

    assert summary["manual"]["collection_count_satisfies_anchor_target"] is True
    assert summary["semi"]["acceptable_seed_count_satisfies_control_target"] is True


def test_build_family_policy_keeps_underextend_as_extension() -> None:
    policy = build_family_policy(
        {
            "family_target_allocations": [
                {"family": "acceptable", "target_count": 6},
                {"family": "overextend_adjacent", "target_count": 3},
                {"family": "underextend", "target_count": 0},
                {"family": "over_parsing", "target_count": 3},
                {"family": "corner_drift", "target_count": 3},
                {"family": "corner_duplicate", "target_count": 3},
                {"family": "topology_failure", "target_count": 0},
                {"family": "fail", "target_count": 0},
            ]
        }
    )

    policy_by_family = {row["family"]: row for row in policy["families"]}
    assert policy_by_family["underextend"]["is_prescreen_core_family"] is False
    assert policy_by_family["topology_failure"]["synthetic_only_if_absent"] is True


def test_build_synthetic_backfill_blocks_when_all_sources_overlap_controls() -> None:
    control_freeze = {
        "selected_control_rows": [
            {"base_task_id": "seed_a"},
            {"base_task_id": "seed_b"},
        ],
        "synthetic_source_overlap_count": 2,
    }
    natural_preselection = {
        "family_gap_after_natural_selection": {
            "over_parsing": 2,
            "corner_drift": 2,
        }
    }
    synthetic_rows = [
        {
            "candidate_id": "seed_a_over_parsing",
            "seed_task_id": "1",
            "seed_base_task_id": "seed_a",
            "family": "over_parsing",
            "lambda_level": "weak",
            "seed_priority_annotation": "",
            "status": "success",
        },
        {
            "candidate_id": "seed_b_corner_drift",
            "seed_task_id": "2",
            "seed_base_task_id": "seed_b",
            "family": "corner_drift",
            "lambda_level": "weak",
            "seed_priority_annotation": "",
            "status": "success",
        },
    ]

    backfill = build_synthetic_backfill(
        synthetic_detail_rows=synthetic_rows,
        family_policy={},
        control_freeze=control_freeze,
        natural_preselection=natural_preselection,
    )

    assert backfill["selected_synthetic_backfill"] == []
    assert backfill["remaining_gap_after_backfill"]["over_parsing"] == 2
    assert backfill["blocked_reasons"]


def test_build_legacy_disjoint_source_pool_filters_manual_and_oos_overlap(tmp_path: Path) -> None:
    semi_import_path = tmp_path / "stage1_prescreen_semi_import.json"
    semi_import_path.write_text(
        """
[
  {
    "data": {"title": "source_ok.jpg", "image": "https://example.com/source_ok.jpg"},
    "predictions": [
      {
        "score": 0.99,
        "result": [
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 10, "y": 20}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 10, "y": 80}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 40, "y": 25}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 40, "y": 75}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 70, "y": 22}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 70, "y": 78}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 90, "y": 21}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 90, "y": 79}}
        ]
      }
    ]
  },
  {
    "data": {"title": "manual_overlap.jpg", "image": "https://example.com/manual_overlap.jpg"},
    "predictions": [
      {
        "score": 0.99,
        "result": [
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 10, "y": 20}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 10, "y": 80}}
        ]
      }
    ]
  },
  {
    "data": {"title": "oos_overlap.jpg", "image": "https://example.com/oos_overlap.jpg"},
    "predictions": [
      {
        "score": 0.99,
        "result": [
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 10, "y": 20}},
          {"type": "keypointlabels", "original_width": 1024, "original_height": 512, "value": {"x": 10, "y": 80}}
        ]
      }
    ]
  }
]
""".strip(),
        encoding="utf-8",
    )

    source_pool = build_legacy_disjoint_source_pool(
        legacy_perturbation_plan={
            "perturbations": [
                {"base_task_id": "source_ok", "title": "source_ok.jpg", "manifest_row_id": "ctrap_001", "operator_id": "corner_drift"},
                {"base_task_id": "manual_overlap", "title": "manual_overlap.jpg", "manifest_row_id": "ctrap_002", "operator_id": "corner_drift"},
                {"base_task_id": "oos_overlap", "title": "oos_overlap.jpg", "manifest_row_id": "ctrap_003", "operator_id": "corner_drift"},
            ]
        },
        semi_import_lookup=load_label_studio_import_lookup(semi_import_path),
        manual_rows=[{"base_task_id": "manual_overlap"}],
        control_freeze={"selected_control_rows": []},
        oos_rows=[{"base_task_id": "oos_overlap"}],
        natural_preselection={"selected_natural_cases": []},
    )

    assert source_pool["source_candidate_count"] == 1
    assert source_pool["source_base_task_ids"] == ["source_ok"]
    assert source_pool["manual_overlap_count"] == 1
    assert source_pool["oos_overlap_count"] == 1


def test_build_final_selection_v4_stays_blocked_on_control_priority_flag() -> None:
    family_policy = build_family_policy(
        {
            "family_target_allocations": [
                {"family": "acceptable", "target_count": 6},
                {"family": "overextend_adjacent", "target_count": 3},
                {"family": "underextend", "target_count": 0},
                {"family": "over_parsing", "target_count": 3},
                {"family": "corner_drift", "target_count": 3},
                {"family": "corner_duplicate", "target_count": 3},
                {"family": "topology_failure", "target_count": 0},
                {"family": "fail", "target_count": 0},
            ]
        }
    )
    control_freeze = {
        "selected_control_rows": [
            {"candidate_id": f"control_{i}", "task_id": str(i), "base_task_id": f"control_{i}", "priority_annotation": ""}
            for i in range(1, 6)
        ]
        + [
            {
                "candidate_id": "control_6",
                "task_id": "6",
                "base_task_id": "control_6",
                "priority_annotation": "低优先",
            }
        ]
    }
    natural_preselection = {
        "selected_natural_cases": [
            {"candidate_id": "n1", "base_task_id": "nat_overextend", "family": "overextend_adjacent"},
            {"candidate_id": "n2", "base_task_id": "nat_overparsing", "family": "over_parsing"},
            {"candidate_id": "n3", "base_task_id": "nat_cornerdrift", "family": "corner_drift"},
            {"candidate_id": "n4", "base_task_id": "nat_cornerdup", "family": "corner_duplicate"},
        ]
    }
    synthetic_backfill_v4 = {
        "selected_synthetic_backfill": [
            {"candidate_id": "s1", "base_task_id": "syn_overextend_1", "family": "overextend_adjacent", "lambda_level": "medium"},
            {"candidate_id": "s2", "base_task_id": "syn_overextend_2", "family": "overextend_adjacent", "lambda_level": "medium"},
            {"candidate_id": "s3", "base_task_id": "syn_overparsing_1", "family": "over_parsing", "lambda_level": "weak"},
            {"candidate_id": "s4", "base_task_id": "syn_overparsing_2", "family": "over_parsing", "lambda_level": "weak"},
            {"candidate_id": "s5", "base_task_id": "syn_cornerdrift_1", "family": "corner_drift", "lambda_level": "weak"},
            {"candidate_id": "s6", "base_task_id": "syn_cornerdrift_2", "family": "corner_drift", "lambda_level": "weak"},
            {"candidate_id": "s7", "base_task_id": "syn_cornerdup_1", "family": "corner_duplicate", "lambda_level": "weak"},
            {"candidate_id": "s8", "base_task_id": "syn_cornerdup_2", "family": "corner_duplicate", "lambda_level": "weak"},
        ]
    }

    final_selection = build_final_selection_v4(
        control_freeze=control_freeze,
        natural_preselection=natural_preselection,
        synthetic_backfill_v4=synthetic_backfill_v4,
        family_policy=family_policy,
        manual_rows=[],
        oos_rows=[],
    )

    assert final_selection["current_selected_trap_count"] == 12
    assert final_selection["trap_binding_ready"] is True
    assert final_selection["control_binding_ready"] is False
    assert final_selection["selection_ready"] is False
    assert any("priority flags" in reason for reason in final_selection["blocked_reasons"])


def test_build_synthetic_backfill_v4_prefers_unique_source_base_task_ids() -> None:
    control_freeze = {
        "selected_control_rows": [
            {"base_task_id": "control_a"},
        ]
    }
    natural_preselection = {
        "family_gap_after_natural_selection": {
            "corner_drift": 2,
            "corner_duplicate": 2,
        },
        "selected_natural_cases": [
            {"base_task_id": "natural_a", "family": "corner_drift"},
            {"base_task_id": "natural_b", "family": "corner_duplicate"},
        ],
    }
    synthetic_detail_rows = [
        {
            "candidate_id": f"candidate_{index:02d}_corner_drift",
            "source_candidate_id": f"source_{index:02d}",
            "source_base_task_id": f"source_{index:02d}",
            "family": "corner_drift",
            "lambda_level": "weak",
            "status": "success",
        }
        for index in range(1, 5)
    ] + [
        {
            "candidate_id": f"candidate_{index:02d}_corner_duplicate",
            "source_candidate_id": f"source_{index:02d}",
            "source_base_task_id": f"source_{index:02d}",
            "family": "corner_duplicate",
            "lambda_level": "weak",
            "status": "success",
        }
        for index in range(1, 5)
    ]

    backfill = build_synthetic_backfill_v4(
        synthetic_detail_rows=synthetic_detail_rows,
        control_freeze=control_freeze,
        natural_preselection=natural_preselection,
    )

    assert len(backfill["selected_synthetic_backfill"]) == 4
    assert backfill["remaining_gap_after_backfill"] == {
        "corner_drift": 0,
        "corner_duplicate": 0,
    }
    selected_base_task_ids = [
        row["base_task_id"] for row in backfill["selected_synthetic_backfill"]
    ]
    assert len(selected_base_task_ids) == len(set(selected_base_task_ids))
