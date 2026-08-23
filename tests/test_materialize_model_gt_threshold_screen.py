from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.materialize_model_gt_threshold_screen import _ordered_pairs, materialize


def _txt(path: Path, points: list[tuple[int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{x} {y}\n" for x, y in points), encoding="utf-8")


def test_materialize_filters_thresholds_and_excludes_unavailable_reference(tmp_path: Path) -> None:
    seam = _ordered_pairs(np.asarray([(1024, 100), (0, 400), (500, 100), (500, 400)]), source=tmp_path / "seam.txt")
    assert seam[0]["x"] == 0.0
    base = [(100, 100), (100, 400), (600, 100), (600, 400)]
    shifted = [(100, 140), (100, 360), (600, 140), (600, 360)]
    test_gt = tmp_path / "test_gt.json"
    test_gt.write_text(json.dumps([{
        "id": 1, "data": {"title": "test_a.jpg"}, "annotations": [{"result": [
            {"type": "keypointlabels", "value": {"x": x / 10.24, "y": y / 5.12}}
            for x, y in base
        ]}],
    }]), encoding="utf-8")
    _txt(tmp_path / "test_model/test_a.txt", shifted)
    _txt(tmp_path / "validation_gt/valid_a.txt", base)
    _txt(tmp_path / "validation_gt/valid_bad.txt", base)
    _txt(tmp_path / "validation_model/valid_a.txt", base)
    _txt(tmp_path / "validation_model/valid_bad.txt", shifted)
    registry = tmp_path / "registry.csv"
    registry.write_text(
        "image_id,geometry_reference_ready\nvalid_a,true\nvalid_bad,false\n",
        encoding="utf-8",
    )

    manifest = materialize(
        test_gt=test_gt,
        test_model_dir=tmp_path / "test_model",
        test_image_dir=tmp_path / "test_images",
        validation_gt_dir=tmp_path / "validation_gt",
        validation_model_dir=tmp_path / "validation_model",
        validation_image_dir=tmp_path / "validation_images",
        validation_registry=registry,
        output_dir=tmp_path / "out",
        mask_thresholds=(0.05,),
        rmse_thresholds=(10.0,),
    )

    assert manifest["counts"] == {
        "test_total": 1,
        "validation_total": 2,
        "validation_evaluable": 1,
        "reference_unavailable": 1,
        "metric_not_evaluable": 1,
    }
    rows = list(csv.DictReader((tmp_path / "out/model_gt_metrics.csv").open(encoding="utf-8-sig")))
    by_id = {row["image_id"]: row for row in rows}
    assert float(by_id["test_a"]["layout_mask_difference"]) >= 0.05
    assert by_id["valid_a"]["layout_mask_difference"] == "0.0"
    assert by_id["valid_bad"]["metric_status"] == "not_evaluable"
    selected = list(csv.DictReader((tmp_path / "out/threshold_membership.csv").open(encoding="utf-8-sig")))
    assert {row["image_id"] for row in selected} == {"test_a"}
