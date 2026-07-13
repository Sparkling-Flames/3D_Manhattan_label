from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.run_c1_raw_to_closeout_dryrun import materialize


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _kp(x: float, y: float) -> dict:
    return {"type": "keypointlabels", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def test_raw_to_closeout_dryrun_smoke_generates_provisional_gate_and_p1_readonly(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    workers = tmp_path / "workers.csv"
    mapping = tmp_path / "mapping.csv"
    reserve = tmp_path / "reserve.csv"
    inventory = tmp_path / "inventory.csv"
    p1 = tmp_path / "p1.csv"
    export = tmp_path / "raw_export.json"

    _csv(manual, fields, [{"round_id": "C1", "worker_id": "w1", "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"}])
    _csv(semi, fields, [])
    _csv(workers, fields, [{"round_id": "C1", "worker_id": "w1", "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"}])
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [{"task_id": "a1", "base_task_id": "scene_a", "inner_id": "1", "intended_project_group": "Calibration_anchor", "mapping_status": "planned"}])
    _csv(reserve, ["task_id", "base_task_id", "dataset_group", "calibration_split"], [{"task_id": "r1", "base_task_id": "reserve_scene", "dataset_group": "Calibration_reserve", "calibration_split": "reserve"}])
    _csv(inventory, ["task_id", "base_task_id", "dataset_group", "used_for_r_u"], [])
    _csv(p1, ["worker_id", "r_u_0"], [{"worker_id": "w1", "r_u_0": "0.8"}])
    export.write_text(
        json.dumps(
            [
                {
                    "id": "100",
                    "project": 66,
                    "data": {
                        "task_id": "a1",
                        "base_task_id": "scene_a",
                        "condition": "manual",
                    },
                    "annotations": [
                        {
                            "id": "ann1",
                            "completed_by": {"id": "w1"},
                            "lead_time": 6,
                            "result": [_kp(1, 1), _kp(2, 2), _kp(3, 3), _kp(4, 4)],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    out = tmp_path / "out"
    c2 = tmp_path / "c2"
    summary = materialize(
        [export],
        out,
        c2,
        reserve,
        inventory,
        min_r_u_tasks=2,
        min_scene_support=1,
        min_calib=2,
        epsilon_r=0.15,
        tasks_per_fill=1,
        manual_assignment=manual,
        semi_assignment=semi,
        worker_distribution=workers,
        planned_task_mapping=mapping,
        active_log=None,
        p1_artifacts=[p1],
    )

    gate = json.loads((out / "c1_closeout_dryrun_gate_summary.json").read_text(encoding="utf-8"))
    sidecar = json.loads((out / "worker_profile_sidecar_C1.summary.json").read_text(encoding="utf-8"))

    assert summary["canonical_csv"] == str(out / "c1_canonical_annotations.csv")
    assert (out / "c1_closeout_dryrun_gate_summary.md").exists()
    assert gate["passed"] is False
    assert gate["raw_pipeline_ready"] is False
    assert gate["formal_closeout_ready"] is False
    assert gate["formal_inputs_present"] is False
    assert gate["c2_decision_chain_ready"] is False
    assert not (c2 / "assignment_manifest_C2_draft.csv").exists()
    assert sidecar["profile_freeze_status"] == "C1_provisional"
    assert sidecar["input_p1_artifacts"] == [str(p1)]
    assert (out / "c1_raw_to_closeout_dryrun_summary.json").exists()
