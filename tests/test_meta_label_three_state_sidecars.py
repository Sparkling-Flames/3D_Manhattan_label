from tools.thesis_main.registry.materialize_meta_label_three_state_sidecars import build_tag_observations, build_three_state_summary


def test_three_state_preserves_positive_negative_and_unasserted() -> None:
    rows = [
        {"task_id": "t1", "base_task_id": "s1", "dataset_group": "Calibration_core", "worker_id": "w1", "difficulty": "occlusion", "model_issue": "acceptable"},
        {"task_id": "t1", "base_task_id": "s1", "dataset_group": "Calibration_core", "worker_id": "w2", "difficulty": "trivial", "model_issue": ""},
    ]
    observations = build_tag_observations(rows, source_artifact="fixture", source_sha256="sha")
    summary = build_three_state_summary(observations)
    difficulty = next(row for row in summary if row["tag_name"] == "difficulty")
    issue = next(row for row in summary if row["tag_name"] == "model_issue")
    assert difficulty["n_positive_assertions"] == 1
    assert difficulty["n_explicit_negatives"] == 1
    assert issue["n_explicit_negatives"] == 1
    assert issue["n_unasserted"] == 1
    assert all(row["routing_eligible"] == "false" for row in summary)


def test_three_state_replicated_conflict_is_not_evaluable() -> None:
    rows = [
        {"task_id": "t1", "worker_id": "w1", "difficulty": "occlusion", "model_issue": ""},
        {"task_id": "t1", "worker_id": "w1", "difficulty": "trivial", "model_issue": ""},
    ]
    observations = build_tag_observations(rows, source_artifact="fixture", source_sha256="sha")
    difficulty = [row for row in observations if row["tag_name"] == "difficulty"]
    assert all(row["assertion_status"] == "not_evaluable" for row in difficulty)
    assert all(row["replicated_conflict"] == "true" for row in difficulty)

