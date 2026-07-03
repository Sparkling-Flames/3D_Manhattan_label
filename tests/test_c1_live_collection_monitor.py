from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_live_collection_monitor import build_monitor


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


def _task(runtime_id: str, task_id: str, base: str, source_draft: str, annotations: list[dict]) -> dict:
    return {
        "id": runtime_id,
        "project": 65,
        "data": {
            "task_id": task_id,
            "base_task_id": base,
            "title": f"{base}.jpg",
            "image": f"{base}.jpg",
            "source_draft": source_draft,
            "condition": "semi" if source_draft == "semi" else "manual",
        },
        "annotations": annotations,
    }


def test_live_monitor_audits_assignment_duplicates_reserve_and_log_policy(tmp_path: Path) -> None:
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
            {"task_id": "r1", "base_task_id": "reserve1", "inner_id": "1", "intended_project_group": "Calibration_reserve", "mapping_status": "planned"},
        ],
    )
    export = tmp_path / "c1_export.json"
    export.write_text(
        json.dumps(
            [
                _task("100", "t1", "base1", "core", [_ann("a1", "w1")]),
                _task("101", "t2", "base2", "core", [_ann("b1", "w2")]),
                _task("102", "t3", "base3", "core", [_ann("c1", "w3", lead_time=9)]),
                _task("103", "outside", "outside_base", "core", [_ann("x1", "w9")]),
                _task("104", "t1", "base1", "core", [_ann("d1", "w1"), _ann("d2", "w1")]),
                _task("105", "r1", "reserve1", "reserve", [_ann("r1", "w1")]),
            ]
        ),
        encoding="utf-8",
    )
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "active_times_2026-07-03.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"project_id": "65", "task_id": "100", "annotator_id": "w1", "annotation_id": "a1", "session_id": "s1", "active_seconds": 12}),
                json.dumps({"project_id": "65", "task_id": "101", "annotator_id": "w2", "session_id": "single", "active_seconds": 7}),
                json.dumps({"project_id": "65", "task_id": "104", "annotator_id": "w1", "session_id": "dup", "active_seconds": 5}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out = tmp_path / "out"
    summary = build_monitor(
        [export],
        manual_assignment=manual,
        semi_assignment=semi,
        worker_distribution=internal,
        planned_task_mapping=mapping,
        active_log=logs,
        output_dir=out,
    )

    assert summary["outside_assignment_submission_count"] == 2
    assert summary["duplicate_worker_task_submission_count"] == 2
    assert summary["reserve_realized_submission_count"] == 1
    assert (out / "c1_runtime_task_mapping.csv").exists()
    snapshot_rows = list(csv.DictReader((out / "c1_live_snapshot_manifest.csv").open(encoding="utf-8")))
    assert {row["source_kind"] for row in snapshot_rows} == {"label_studio_export_snapshot", "active_log_snapshot"}
    assert all(row["sha256"] for row in snapshot_rows)

    health = {row["worker_id"]: row for row in csv.DictReader((out / "c1_live_active_log_health_by_worker.csv").open(encoding="utf-8"))}
    assert health["w2"]["active_log_missing_count"] == "0"
    assert int(health["w3"]["active_log_missing_count"]) >= 1
