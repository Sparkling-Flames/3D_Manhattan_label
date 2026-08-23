from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis.materialize_model_initialization_audit import (
    _metric_row,
    _topology_primary_report,
    classify_initialization,
    exclusive_corner_match,
    identify_confirmed_manual_gt,
    is_initialization_acceptable,
)
from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import _ordered_pairs


def _pairs(*xs: float) -> list[dict[str, float]]:
    return [{"x": x, "y_ceiling": 100.0, "y_floor": 400.0} for x in xs]


def test_corner_match_is_exclusive_and_panorama_seam_aware() -> None:
    result = exclusive_corner_match(_pairs(1022.0, 500.0), _pairs(2.0, 500.0))
    assert result["tp"] == 4
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["f1"] == 1.0
    assert exclusive_corner_match(_pairs(1284.0), _pairs(260.0))["f1"] == 1.0

    with pytest.raises(ValueError, match="NaN or Inf"):
        _ordered_pairs(
            np.asarray([(0.0, 100.0), (0.0, 400.0), (500.0, np.nan), (500.0, 400.0)]),
            source=Path("invalid.txt"),
        )


def test_hybrid_gt_selects_only_geometry_changes(tmp_path: Path) -> None:
    official = {
        "same": tmp_path / "same.txt",
        "changed": tmp_path / "changed.txt",
    }
    for path in official.values():
        path.write_text("100 100\n100 400\n600 100\n600 400\n", encoding="utf-8")
    manual = {
        "same": np.asarray([(100.2, 100.0), (100.2, 400.0), (600.2, 100.0), (600.2, 400.0)]),
        "changed": np.asarray([(100.0, 120.0), (100.0, 400.0), (600.0, 100.0), (600.0, 400.0)]),
    }
    changed, _ = identify_confirmed_manual_gt(
        manual, official, tmp_path / "manual.json", expected_count=1,
    )
    assert changed == {"changed"}


def test_topology_mismatch_is_wrong_even_if_geometry_iou_is_high() -> None:
    result = classify_initialization(
        pair_encoding_valid=True,
        model_pair_count=5,
        gt_pair_count=4,
        corner_all_matched=True,
        geometry_acceptable=True,
        max_corner_error_px=0.0,
        layout_mask_difference=0.001,
    )
    assert result["initialization_correct"] is False
    assert result["initialization_class"] == "wrong_initialization_topology"
    assert result["difference_band"] == "large_difference_topology"

    geometry_fail = classify_initialization(
        pair_encoding_valid=True,
        model_pair_count=4,
        gt_pair_count=4,
        corner_all_matched=True,
        geometry_acceptable=False,
        max_corner_error_px=2.0,
        layout_mask_difference=0.06,
    )
    assert geometry_fail["structural_localization_correct"] is True
    assert geometry_fail["initialization_correct"] is False
    assert geometry_fail["initialization_class"] == "wrong_initialization_geometry"
    assert is_initialization_acceptable(
        pair_encoding_valid=True,
        topology_exact=True,
        topdown_2d_iou=0.75,
        derived_3d_iou=0.65,
        corner_error_percent_diagonal=2.0,
    )
    assert not is_initialization_acceptable(
        pair_encoding_valid=True,
        topology_exact=False,
        topdown_2d_iou=0.99,
        derived_3d_iou=0.99,
        corner_error_percent_diagonal=0.1,
    )


def test_layout_iou_preserves_official_cyclic_corner_order(tmp_path: Path) -> None:
    model = tmp_path / "sample.txt"
    gt = tmp_path / "sample_gt.txt"
    model.write_text(
        "15 96\n15 450\n3 200\n3 344\n113 212\n113 326\n"
        "339 198\n339 347\n513 150\n513 404\n536 20\n536 499\n"
        "710 57\n710 476\n561 140\n561 413\n746 236\n746 287\n"
        "780 236\n780 287\n",
        encoding="utf-8",
    )
    gt.write_text(
        "747.88 240.31\n747.88 282.83\n779.31 240.22\n779.31 282.97\n"
        "16.11 101.41\n16.11 447.60\n3.99 201.68\n3.99 343.53\n"
        "109.95 212.95\n109.95 326.95\n338.21 196.95\n338.21 350.16\n",
        encoding="utf-8",
    )

    row = _metric_row("test", "sample", model, gt, tmp_path / "sample.png")

    assert row["topdown_2d_iou"] == pytest.approx(0.837931, abs=1e-6)


def test_topology_primary_report_keeps_other_metrics_as_sensitivity() -> None:
    def row(split: str, topology_exact: bool) -> dict[str, object]:
        return {
            "split": split,
            "topology_exact": topology_exact,
            "official_gt_sensitivity_initialization_class": "",
            "topdown_2d_iou": .9,
            "layoutnetv2_style_3d_iou": .8,
            "layout_depth_rmse_proxy": .1,
            "layout_depth_delta1_proxy": .95,
            "corner_error_percent_diagonal": 1.0,
            "layout_mask_difference": .05,
        }

    report = _topology_primary_report(
        [row("test", True), row("test", False), row("validation", True)],
        {
            "outputs": {"csv": "shared.csv"},
            "output_dir": "out",
            "evidence": {},
            "checkpoint_sha256": "checkpoint",
        },
    )

    assert "Test 混合 GT 的角点数量主结果是 **1/2（50.00%）**" in report
    assert "各行仅单独应用一个阈值" in report
    assert "旧版 `.90/.80/.05` 联合门" in report
