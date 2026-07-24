import csv
import hashlib
import json

from tools.thesis_main.analysis.materialize_frozen_routing_profiles import build_global, materialize


def _csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_task_adjusted_global_and_full_gates_are_frozen(tmp_path):
    submissions = tmp_path / "submissions.csv"
    states = tmp_path / "states.csv"
    components = tmp_path / "components.csv"
    _csv(submissions, [
        {"worker_id": worker, "task_id": task, "condition": "manual", "iou_to_gt": value, "quality_evaluable": "true"}
        for worker, task, value in [
            ("w1", "easy", .9), ("w1", "hard", .5),
            ("w2", "easy", .8), ("w2", "hard", .6),
        ]
    ])
    _csv(states, [
        {"worker_id": worker, "process_eligible": "true", "independence_eligible": "true",
         "F_struct": "0", "R_LOO_compatible": loo, "LOO_support": "2"}
        for worker, loo in (("w1", ".8"), ("w2", ".9"))
    ])
    common = {
        "component_family": "undercoverage", "p1_integrity_eligible": "true",
        "c1_predictive_validated": "true", "direction_consistent": "true",
        "leave_one_task_out_stable": "true", "leave_one_block_out_stable": "true",
        "routing_activation_allowed": "true",
    }
    _csv(components, [
        {"worker_id": "w1", **common, "c2b_confirmed": "true"},
        {"worker_id": "w2", **common, "c2b_confirmed": "false"},
    ])
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps({
        "profile_version": "p1",
        "input_sha256": {
            "submissions_csv": _sha(submissions),
            "worker_state_csv": _sha(states),
            "component_evidence_csv": _sha(components),
        },
    }), encoding="utf-8")
    summary = materialize(submissions, states, components, manifest, tmp_path / "out")
    assert summary["n_global_eligible"] == 2
    assert summary["n_full_components"] == 1
    rows = list(csv.DictReader((tmp_path / "out" / "full_component_table.csv").open()))
    assert rows[1]["disable_reason"] == "c2b_confirmed"


def test_confidence_level_changes_task_cluster_interval():
    submissions = [
        {"worker_id": worker, "task_id": task, "condition": "manual", "iou_to_gt": str(value), "quality_evaluable": "true"}
        for worker, task, value in [("w1", "t1", .9), ("w1", "t2", .4), ("w2", "t1", .7), ("w2", "t2", .6)]
    ]
    states = [{"worker_id": worker, "process_eligible": "true", "independence_eligible": "true", "reference_evaluable": "true", "F_struct": "0"} for worker in ("w1", "w2")]
    low, _, _ = build_global(submissions, states, profile_version="p", estimator={"confidence_level": .8})
    high, _, _ = build_global(submissions, states, profile_version="p", estimator={"confidence_level": .99})
    assert float(high[0]["Q_GT_CI_upper"]) - float(high[0]["Q_GT_CI_lower"]) > float(low[0]["Q_GT_CI_upper"]) - float(low[0]["Q_GT_CI_lower"])
