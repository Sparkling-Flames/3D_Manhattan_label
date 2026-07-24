import csv
import json

from tools.thesis_main.analysis.materialize_c2_task_risk import _composite_q75_bucket, materialize


def test_composite_q75_uses_frozen_c1_channel_percentiles() -> None:
    refs = {name: [0.0, 1.0, 2.0, 3.0] for name in ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A")}
    bucket, percentiles = _composite_q75_bucket({name: 3.0 for name in refs}, refs)
    assert bucket == "stress"
    assert max(percentiles.values()) >= .75


def test_candidate_risk_uses_c1_only_and_layout_structure(tmp_path):
    inventory = tmp_path / "inventory.csv"
    with inventory.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["task_id", "source_path"]); writer.writeheader(); writer.writerow({"task_id": "t1", "source_path": "missing.jpg"})
    layouts = tmp_path / "layouts"; layouts.mkdir()
    (layouts / "t1.json").write_text(json.dumps({"layout": {"corners": [
        {"x": 10, "y_ceiling": 100, "y_floor": 400}, {"x": 300, "y_ceiling": 100, "y_floor": 400},
        {"x": 600, "y_ceiling": 100, "y_floor": 400}, {"x": 900, "y_ceiling": 100, "y_floor": 400},
    ]}}), encoding="utf-8")
    c1 = tmp_path / "c1.jsonl"
    c1.write_text(json.dumps({"corners_px": [[10, 100], [10, 400], [500, 100], [500, 400]]}) + "\n", encoding="utf-8")

    summary = materialize(inventory, layouts, c1, tmp_path / "out", input_status="precloseout_rehearsal")

    assert summary["n_tasks"] == 1
    assert summary["formal_ready"] is False
    row = next(csv.DictReader((tmp_path / "out" / "c2_task_risk_inventory.csv").open(encoding="utf-8")))
    assert row["g_model_struct"]
    assert not row["d_cal_A"]
    assert row["feature_status"] == "not_requested"
    assert row["assignment_eligible"].lower() == "false"
