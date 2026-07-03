from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_canonicalize_exports import build_canonicalization


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _kp(x: float, y: float) -> dict:
    return {"type": "keypointlabels", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def _ann(ann_id: str, worker: str, lead_time: float = 0.0) -> dict:
    return {"id": ann_id, "completed_by": {"id": worker}, "lead_time": lead_time, "result": [_kp(1, 1), _kp(2, 2)]}


def _task(runtime_id: str, task_id: str, base: str, annotations: list[dict]) -> dict:
    return {
        "id": runtime_id,
        "project": 66,
        "data": {
            "task_id": task_id,
            "base_task_id": base,
            "title": f"{base}.jpg",
            "image": f"{base}.jpg",
            "source_draft": "core",
            "condition": "manual",
        },
        "annotations": annotations,
    }


def test_c1_canonicalization_materializes_required_fields_and_active_policy(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    internal = tmp_path / "internal.csv"
    mapping = tmp_path / "mapping.csv"
    assigned = [
        {"round_id": "C1", "worker_id": "w1", "task_id": "t1", "base_task_id": "base1", "dataset_group": "Calibration_core"},
        {"round_id": "C1", "worker_id": "w2", "task_id": "t2", "base_task_id": "base2", "dataset_group": "Calibration_core"},
        {"round_id": "C1", "worker_id": "w3", "task_id": "t3", "base_task_id": "base3", "dataset_group": "Calibration_core"},
    ]
    _csv(manual, fields, assigned)
    _csv(semi, fields, [])
    _csv(internal, fields, assigned)
    _csv(
        mapping,
        ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"],
        [
            {"task_id": "t1", "base_task_id": "base1", "inner_id": "1", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
            {"task_id": "t2", "base_task_id": "base2", "inner_id": "2", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
            {"task_id": "t3", "base_task_id": "base3", "inner_id": "3", "intended_project_group": "Calibration_core", "mapping_status": "planned"},
        ],
    )
    export = tmp_path / "c1_export.json"
    export.write_text(
        json.dumps(
            [
                _task("200", "t1", "base1", [_ann("a1", "w1")]),
                _task("201", "t2", "base2", [_ann("b1", "w2")]),
                _task("202", "t3", "base3", [_ann("c1", "w3", lead_time=11)]),
                _task("203", "t1", "base1", [_ann("d1", "w1"), _ann("d2", "w1", lead_time=9)]),
            ]
        ),
        encoding="utf-8",
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "active_times_2026-07-03.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"project_id": "66", "task_id": "200", "annotator_id": "w1", "annotation_id": "a1", "session_id": "s1", "active_seconds": 12}),
                json.dumps({"project_id": "66", "task_id": "201", "annotator_id": "w2", "session_id": "single", "active_seconds": 7}),
                json.dumps({"project_id": "66", "task_id": "203", "annotator_id": "w1", "annotation_id": "d2", "session_id": "s2", "active_seconds": 5}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "out"
    summary = build_canonicalization(
        [export],
        manual_assignment=manual,
        semi_assignment=semi,
        worker_distribution=internal,
        planned_task_mapping=mapping,
        active_log=logs,
        output_dir=out,
    )

    rows = list(csv.DictReader((out / "c1_canonical_annotations.csv").open(encoding="utf-8")))
    by_runtime = {row["ls_runtime_task_id"]: row for row in rows}
    assert summary["n_canonical_rows"] == 4
    assert summary["outside_assignment_submission_count"] == 0
    assert summary["duplicate_worker_task_submission_count"] == 1
    assert all(row["round_id"] == "C1" for row in rows)
    assert all(row["canonical_annotation_id"] for row in rows)
    assert by_runtime["200"]["primary_active_time_eligible"] == "true"
    assert by_runtime["201"]["active_time_match_status"] == "project+task+annotator"
    assert by_runtime["201"]["primary_active_time_eligible"] == "true"
    assert by_runtime["202"]["active_time_source"] == "lead_time_fallback"
    assert by_runtime["202"]["primary_active_time_eligible"] == "false"
    assert by_runtime["202"]["sensitivity_active_time_eligible"] == "true"
    assert by_runtime["203"]["duplicate_group_size"] == "2"
    assert by_runtime["203"]["duplicate_worker_task_submission"] == "true"
    assert (out / "raw_inputs" / "raw_input_snapshot_manifest.csv").exists()
    assert (out / "c1_runtime_task_mapping.csv").exists()
