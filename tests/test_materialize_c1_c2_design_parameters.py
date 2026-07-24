import csv

from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_materializes_worker_risk_slope_from_eligible_c1_tasks(tmp_path):
    quality = tmp_path / "quality.csv"; risk = tmp_path / "risk.csv"; structural = tmp_path / "structural.csv"; completion = tmp_path / "completion.csv"
    _write(quality, [{"worker_id": "w1", "base_task_id": f"b{i}", "Q_GT_raw": 1 - i / 10, "global_analysis_eligible": "true"} for i in range(4)])
    _write(risk, [{"base_task_id": f"b{i}", "risk_route_score": i / 10, "building_id": f"h{i % 2}"} for i in range(4)])
    _write(structural, [{"worker_id": "w1", "structural_opportunity_eligible": "true", "failure_attribution": "none"}])
    _write(completion, [{"worker_id": "w1", "assigned_total_count": 4, "observed_total_count": 4, "completion_status": "completed"}])
    summary = materialize(quality, risk, structural, completion, tmp_path / "out")
    row = next(csv.DictReader((tmp_path / "out" / "c1_c2_design_parameters.csv").open(encoding="utf-8")))
    assert summary["n_estimated"] == 1
    assert float(row["risk_slope"]) < 0
