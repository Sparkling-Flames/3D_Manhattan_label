from __future__ import annotations

import csv
import json
from pathlib import Path

from PIL import Image

from tools.compute_g_t_diagnostics import OUTPUT_COLUMNS, compute_diagnostics, parse_task, run_dryrun


def _write_image(path: Path) -> Path:
    Image.new("RGB", (256, 128), (240, 240, 240)).save(path)
    return path


def _keypoint_result(x: float, y: float, idx: int) -> dict:
    return {
        "id": f"kp_{idx}",
        "from_name": "kp",
        "to_name": "img",
        "type": "keypointlabels",
        "value": {"x": x, "y": y, "keypointlabels": ["Corner"]},
    }


def _polygon_result(points: list[tuple[float, float]]) -> dict:
    return {
        "id": "poly_1",
        "from_name": "poly",
        "to_name": "img",
        "type": "polygonlabels",
        "value": {"points": [[x, y] for x, y in points], "polygonlabels": ["Wall"]},
    }


def _task(task_id: str, image_path: Path, results: list[dict], *, extra_annotation: dict | None = None) -> dict:
    annotation = {
        "prediction": {
            "model_version": "HoHoNet_v1",
            "result": results,
        }
    }
    if extra_annotation:
        annotation.update(extra_annotation)
    return {
        "id": task_id,
        "data": {"image": str(image_path), "title": f"{task_id}.png"},
        "annotations": [annotation],
    }


def test_hard_failure_triggers_hard_flag(tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "hard.png")
    points = [(10, 10), (90, 90), (90, 10), (10, 90)]
    results = [_keypoint_result(10, 20, 0), _keypoint_result(10, 80, 1), _polygon_result(points)]

    row = compute_diagnostics(parse_task(_task("hard", image_path, results), tmp_path))

    assert row["g_bucket"] == "hard_prediction_failure"
    assert row["g_hard_failure_flag"] == "true"
    assert "self_intersection_or_invalid_polygon" in row["g_reason_codes"]


def test_soft_complexity_is_not_hard_failure(tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "soft.png")
    keypoints = []
    for idx, x in enumerate([10, 20, 30, 40, 50, 60, 70]):
        keypoints.append(_keypoint_result(x, 25, idx * 2))
        keypoints.append(_keypoint_result(x, 75, idx * 2 + 1))
    polygon = [(50 + 35 * __import__("math").cos(i), 50 + 20 * __import__("math").sin(i)) for i in [j / 130 * 6.28318 for j in range(130)]]
    results = keypoints + [_polygon_result(polygon)]

    row = compute_diagnostics(parse_task(_task("soft", image_path, results), tmp_path))

    assert row["g_bucket"] == "soft_prediction_complexity"
    assert row["g_hard_failure_flag"] == "false"
    assert row["g_complexity_flag"] == "true"
    assert "high_keypoint_count" in row["g_reason_codes"]
    assert int(row["legacy_risk_score"]) > 0


def test_missing_prediction_and_missing_polygon_policy(tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "missing.png")
    missing_prediction = {"id": "missing", "data": {"image": str(image_path), "title": "missing.png"}, "annotations": []}
    missing_prediction_row = compute_diagnostics(parse_task(missing_prediction, tmp_path))
    assert missing_prediction_row["g_bucket"] == "render_or_prediction_missing"
    assert missing_prediction_row["prediction_status"] == "missing"

    no_polygon = _task("no_polygon", image_path, [_keypoint_result(10, 20, 0), _keypoint_result(10, 80, 1)])
    no_polygon_row = compute_diagnostics(parse_task(no_polygon, tmp_path))
    assert no_polygon_row["g_bucket"] == "hard_prediction_failure"
    assert "polygon_missing" in no_polygon_row["g_reason_codes"]


def test_dryrun_ignores_forbidden_fields_and_writes_complete_schema(tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "nominal.png")
    results = [
        _keypoint_result(10, 20, 0),
        _keypoint_result(10, 80, 1),
        _keypoint_result(90, 20, 2),
        _keypoint_result(90, 80, 3),
        _polygon_result([(10, 20), (90, 20), (90, 80), (10, 80)]),
    ]
    payload = [
        _task(
            "nominal",
            image_path,
            results,
            extra_annotation={
                "lead_time": 12.3,
                "active_time": 99,
                "result": [
                    {"from_name": "difficulty", "value": {"choices": ["occlusion"]}},
                    {"from_name": "model_issue", "value": {"choices": ["corner_duplicate"]}},
                ],
            },
        )
    ]
    input_json = tmp_path / "project.json"
    input_json.write_text(json.dumps(payload), encoding="utf-8")

    summary = run_dryrun(input_json, tmp_path / "out", image_root=tmp_path, max_per_sheet=1)

    manifest = Path(summary["outputs"]["sample_manifest"])
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert tuple(rows[0].keys()) == OUTPUT_COLUMNS
    assert rows[0]["dry_run_only"] == "true"
    assert rows[0]["do_not_use_for_split"] == "true"
    assert rows[0]["g_bucket"] == "nominal_prediction_structure"
    assert "difficulty" not in rows[0]
    assert "model_issue" not in rows[0]
    assert "lead_time" not in rows[0]
    assert "active_time" not in rows[0]
    assert summary["ignored_forbidden_fields"]["lead_time"] == 1
    assert summary["ignored_forbidden_fields"]["active_time"] == 1
