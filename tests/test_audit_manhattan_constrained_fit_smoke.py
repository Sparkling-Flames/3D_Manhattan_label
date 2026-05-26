import csv
import json
import math
from pathlib import Path

import pytest

from tools.audit_manhattan_constrained_fit_smoke import (
    audit_export,
    audit_tasks,
    find_latest_export_for_date,
    main,
)


CAMERA_HEIGHT = 1.6
LAYOUT_HEIGHT = 3.0


def _ls_pair_from_bev(x, y, layout_height=LAYOUT_HEIGHT):
    theta = math.atan2(y, x)
    distance = math.hypot(x, y)
    floor_y = (math.pi / 2.0 + math.atan(CAMERA_HEIGHT / distance)) / math.pi * 100.0
    ceiling_y = (math.pi / 2.0 - math.atan((layout_height - CAMERA_HEIGHT) / distance)) / math.pi * 100.0
    ls_x = ((theta + math.pi) / (2.0 * math.pi)) * 100.0
    return [{"x": ls_x, "y": ceiling_y}, {"x": ls_x, "y": floor_y}]


def _rectangle_keypoints():
    points = []
    for x, y in [(-2.0, -1.0), (2.0, -1.0), (2.0, 1.0), (-2.0, 1.0)]:
        points.extend(_ls_pair_from_bev(x, y))
    return points


def _annotation(annotation_id, scope="normal", points=None):
    results = []
    for point in points if points is not None else _rectangle_keypoints():
        results.append(
            {
                "type": "keypointlabels",
                "from_name": "kp",
                "value": {"x": point["x"], "y": point["y"], "keypointlabels": ["Corner"]},
            }
        )
    if scope is not None:
        results.append(
            {
                "type": "choices",
                "from_name": "scope",
                "value": {"choices": [scope]},
            }
        )
    return {
        "id": annotation_id,
        "completed_by": 7,
        "result": results,
    }


def _task(task_id, annotations):
    return {
        "id": task_id,
        "data": {
            "base_task_id": f"base-{task_id}",
            "title": f"task {task_id}",
            "image": f"http://example.test/{task_id}.jpg",
        },
        "annotations": annotations,
    }


def test_normal_compatible_annotation_produces_fit_ok_record():
    records, summary = audit_tasks([_task(1, [_annotation(101)])], source_export="<memory>")

    assert summary["n_annotations"] == 1
    assert summary["n_scope_normal"] == 1
    assert summary["n_preview_compatible"] == 1
    assert summary["n_fit_ok"] == 1
    assert records[0]["fit_status"] == "ok"
    assert records[0]["review_priority"] in {"low", "medium", "high"}


def test_oos_scope_is_excluded():
    records, summary = audit_tasks(
        [_task(1, [_annotation(101, scope="oos_geometry")])],
        source_export="<memory>",
    )

    assert summary["n_fit_ok"] == 0
    assert summary["n_preview_excluded"] == 1
    assert summary["preview_exclusion_counts"]["oos_geometry"] == 1
    assert records[0]["fit_status"] == "ineligible"


def test_odd_keypoints_are_excluded():
    points = _rectangle_keypoints()[:-1]
    _, summary = audit_tasks([_task(1, [_annotation(101, points=points)])], source_export="<memory>")

    assert summary["n_preview_excluded"] == 1
    assert summary["preview_exclusion_counts"]["compatibility_failure_odd_keypoint"] == 1


def test_duplicate_keypoints_are_excluded():
    points = _rectangle_keypoints()
    points[2] = {"x": points[0]["x"] + 0.1, "y": points[2]["y"]}
    points[3] = {"x": points[0]["x"] + 0.1, "y": points[3]["y"]}
    _, summary = audit_tasks([_task(1, [_annotation(101, points=points)])], source_export="<memory>")

    assert summary["n_preview_excluded"] == 1
    assert summary["preview_exclusion_counts"]["compatibility_failure_duplicate"] == 1


def test_unparseable_keypoints_are_counted():
    annotation = _annotation(101)
    annotation["result"][0]["value"] = {"x": "bad", "y": 10}
    records, summary = audit_tasks([_task(1, [annotation])], source_export="<memory>")

    assert records[0]["parse_error_count"] == 1
    assert summary["preview_exclusion_counts"]["unparseable_keypoints"] == 1


def test_large_movement_candidate_appears_in_candidate_summary():
    points = _rectangle_keypoints()
    points[0] = {"x": points[0]["x"], "y": points[0]["y"] + 8.0}
    records, summary = audit_tasks(
        [_task(1, [_annotation(101, points=points)])],
        source_export="<memory>",
    )

    assert records[0]["fit_status"] == "ok"
    assert records[0]["max_abs_delta"] >= 5.0
    assert summary["n_large_move_candidates"] == 1
    assert summary["top_candidate_examples"]


def test_cli_writes_summary_records_csv_report_to_temp_output_dir(tmp_path):
    export_path = tmp_path / "project-99-at-2026-05-18-00-00-test.json"
    output_dir = tmp_path / "out"
    export_path.write_text(
        json.dumps([_task(1, [_annotation(101)])], ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--input",
            str(export_path),
            "--output-dir",
            str(output_dir),
            "--date",
            "2026-05-18",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "smoke_fit_records_2026-05-18.jsonl").exists()
    assert (output_dir / "smoke_fit_summary_2026-05-18.json").exists()
    assert (output_dir / "smoke_fit_candidates_2026-05-18.csv").exists()
    assert (output_dir / "smoke_fit_report_2026-05-18.md").exists()
    assert (output_dir / "README.md").exists()
    with (output_dir / "smoke_fit_candidates_2026-05-18.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["task_id"] == "1"


def test_auto_latest_date_selects_local_export(tmp_path):
    export_root = tmp_path / "export_label"
    export_root.mkdir()
    old_file = export_root / "project-1-at-2026-05-18-01-00-old.json"
    new_file = export_root / "project-1-at-2026-05-18-02-00-new.json"
    old_file.write_text("[]", encoding="utf-8")
    new_file.write_text("[]", encoding="utf-8")

    selected = find_latest_export_for_date(export_root, "2026-05-18")

    assert selected.name == new_file.name


def test_no_test_modifies_export_label(tmp_path):
    export_path = tmp_path / "synthetic_export.json"
    output_dir = tmp_path / "out"
    export_path.write_text(json.dumps([_task(1, [_annotation(101)])]), encoding="utf-8")
    before = export_path.read_text(encoding="utf-8")

    audit_export(export_path, output_dir, "2026-05-18")

    assert export_path.read_text(encoding="utf-8") == before
