from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.audit_annotation_research_data_20260905 import (
    classify_export_source,
    _d_mask,
    dense42_denominators,
    parse_alternating_corner_file,
    pairwise_cluster_payload,
    summarize_comparisons,
)


def test_d_mask_uses_true_interval_union_for_overlap_and_disjoint_columns() -> None:
    left = (np.array([1, 1]), np.array([3, 3]))
    right = (np.array([2, 5]), np.array([4, 6]))
    # column 0: intersection=2, union=4; column 1: intersection=0, union=5
    assert _d_mask(left, right) == 1 - 2 / 9


def test_pairwise_payload_keeps_correspondence_compatibility_for_clustering() -> None:
    assert pairwise_cluster_payload({
        "boundary_similarity": "0.96", "wallwall_similarity": "0.97",
        "metric_compatible": "true", "pointwise_correspondence_compatible": "True",
    }) == {
        "boundary_similarity": 0.96, "wallwall_similarity": 0.97,
        "metric_compatible": True, "pointwise_correspondence_compatible": True,
    }


def test_export_classification_separates_formal_reference_development_and_unknown() -> None:
    formal = {"export_label/stage1_chinese/project-28-current.json"}
    assert classify_export_source(
        "export_label/stage1_chinese/project-28-current.json", {"28"}, set(), formal
    )[0] == "formal_experiment_export"
    assert classify_export_source(
        "export_label/stage1_chinese/legacy/project-28-old.json", {"28"}, set(), formal
    )[0] == "duplicate_or_revision_export"
    assert classify_export_source(
        "export_label/groudTruth.json", {"70"}, set(), formal
    )[0] == "reference_export"
    assert classify_export_source(
        "export_label/project-23-smoke.json", {"23"}, {"smoke_test"}, formal
    )[0] == "development_export"
    assert classify_export_source(
        "export_label/project-999.json", {"999"}, set(), formal
    )[0] == "unresolved_export"
    assert classify_export_source(
        "export_label/empty.json", set(), set(), formal
    )[0] == "unresolved_export"
    assert classify_export_source(
        "export_label/RAW_DATA_PACKAGE_MANIFEST_20260817.json", set(), set(), formal
    )[0] == "package_manifest"


def test_bilayout_corner_parser_preserves_alternating_ceiling_floor_order(tmp_path: Path) -> None:
    path = tmp_path / "corners.txt"
    path.write_text("10 20\n10 400\n500 30\n500 390\n", encoding="utf-8")
    points, pairs = parse_alternating_corner_file(path)
    assert points == [[10.0, 20.0], [10.0, 400.0], [500.0, 30.0], [500.0, 390.0]]
    assert pairs == [
        {"x": 10.0, "y_ceiling": 20.0, "y_floor": 400.0},
        {"x": 500.0, "y_ceiling": 30.0, "y_floor": 390.0},
    ]


def test_comparison_summary_reports_real_image_building_worker_denominators() -> None:
    rows = [
        {"comparison": "human_gt", "d_mask": 0.1, "base_task_id": "b1_i1", "building_id": "b1", "worker_id": "1"},
        {"comparison": "human_gt", "d_mask": 0.3, "base_task_id": "b1_i1", "building_id": "b1", "worker_id": "2"},
        {"comparison": "human_gt", "d_mask": 0.2, "base_task_id": "b2_i2", "building_id": "b2", "worker_id": "1"},
    ]
    summary = summarize_comparisons(rows)
    assert summary == [{
        "comparison": "human_gt",
        "stratum": "pooled",
        "comparison_count": 3,
        "image_count": 2,
        "building_count": 2,
        "worker_count": 2,
        "d_mask_mean": 0.2,
        "d_mask_median": 0.2,
        "d_mask_q25": 0.15,
        "d_mask_q75": 0.25,
    }]


def test_dense42_denominators_reproduce_old_labels_without_filling_unknown() -> None:
    audit = dense42_denominators()
    assert audit["row_count"] == 1055
    assert audit["strict_geometry_valid_count"] == 1013
    assert audit["old_reference_quality_eligible_count"] == 770
    assert Counter(audit["independence_counts"]) == Counter({
        "independent": 840,
        "non_independent_confirmed": 88,
        "non_independent_suspected": 115,
        "unknown": 12,
    })
