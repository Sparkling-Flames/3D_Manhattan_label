import csv

from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def test_materializes_worker_risk_slope_from_eligible_c1_tasks(tmp_path):
    quality = tmp_path / "quality.csv"; risk = tmp_path / "risk.csv"; structural = tmp_path / "structural.csv"; completion = tmp_path / "completion.csv"
    _write(quality, [{"worker_id": "w1", "base_task_id": f"b{i}", "Q_GT_raw": 1 - i / 10, "gt_primary_analysis_eligible": "true"} for i in range(4)])
    _write(risk, [{"base_task_id": f"b{i}", "risk_design_score_A": i / 10, "building_id": f"h{i % 2}"} for i in range(4)])
    _write(structural, [{"worker_id": "w1", "structural_opportunity_eligible": "true", "failure_attribution": "none"}])
    _write(completion, [{"worker_id": "w1", "assigned_total_count": 4, "observed_total_count": 4, "completion_status": "completed"}])
    summary = materialize(quality, risk, structural, completion, tmp_path / "out")
    row = next(csv.DictReader((tmp_path / "out" / "c1_c2_design_parameters.csv").open(encoding="utf-8")))
    assert summary["n_estimated"] == 1
    assert float(row["risk_slope"]) < 0


def test_nonstarter_is_audited_but_not_required_for_formal_model_support(tmp_path):
    quality = tmp_path / "quality.csv"; risk = tmp_path / "risk.csv"; structural = tmp_path / "structural.csv"; completion = tmp_path / "completion.csv"; state = tmp_path / "state.csv"
    rows = []
    risks = []
    for worker, offset in (("w1", 0.0), ("w2", .05), ("w3", -.05)):
        for i in range(6):
            rows.append({"worker_id": worker, "base_task_id": f"b{i}", "Q_GT_raw": .9 + offset - .1 * i, "gt_primary_analysis_eligible": "true", "stage": "C1"})
    for i in range(6):
        risks.append({"base_task_id": f"b{i}", "risk_design_score_A": i / 5, "building_id": f"h{i % 3}"})
    _write(quality, rows); _write(risk, risks)
    _write(structural, [{"worker_id": "w1", "structural_opportunity_eligible": "true", "failure_attribution": "none"}])
    _write(completion, [
        {"worker_id": worker, "assigned_total_count": 6, "observed_total_count": 6, "completion_status": "completed"}
        for worker in ("w1", "w2", "w3")
    ] + [{"worker_id": "w4", "assigned_total_count": 6, "observed_total_count": 0, "completion_status": "nonstarter"}])
    _write(state, [
        {"worker_id": worker, "Q_GT_task_adjusted": value, "SE": ".03"}
        for worker, value in (("w1", .8), ("w2", .85), ("w3", .75))
    ])
    summary = materialize(quality, risk, structural, completion, tmp_path / "out", worker_state_csv=state)
    output = {row["worker_id"]: row for row in csv.DictReader((tmp_path / "out" / "c1_c2_design_parameters.csv").open(encoding="utf-8"))}
    assert summary["n_model_workers"] == 3
    assert output["w4"]["c2b_baseline_eligible"].lower() == "false"
    assert output["w4"]["Q_GT_baseline_se"] == ""
    assert all(float(output[worker]["Q_GT_baseline_se"]) == .03 for worker in ("w1", "w2", "w3"))
