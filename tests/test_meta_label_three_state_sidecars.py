from tools.thesis_main.registry.materialize_meta_label_three_state_sidecars import build_response_style_diagnostics, build_tag_observations, build_three_state_summary


def test_concrete_tags_distinguish_positive_negative_and_zero() -> None:
    rows = [
        {"task_id": "t1", "base_task_id": "s1", "worker_id": "w1", "difficulty": "occlusion", "model_issue": "acceptable"},
        {"task_id": "t1", "base_task_id": "s1", "worker_id": "w2", "difficulty": "trivial", "model_issue": ""},
    ]
    summary = build_three_state_summary(build_tag_observations(rows, source_artifact="fixture", source_sha256="sha"))
    occlusion = next(row for row in summary if row["tag_family"] == "difficulty" and row["tag_name"] == "occlusion")
    issue = next(row for row in summary if row["tag_family"] == "model_issue" and row["tag_name"] == "corner_drift")
    assert (occlusion["a"], occlusion["e"], occlusion["u"], occlusion["k"]) == (1, 1, 0, 2)
    assert (issue["a"], issue["e"], issue["u"]) == (0, 1, 1)
    assert all(row["routing_eligible"] == "false" for row in summary)


def test_conflict_requires_replicated_positive_and_negative_evidence() -> None:
    rows = [
        {"task_id": "t1", "worker_id": "p1", "difficulty": "occlusion"},
        {"task_id": "t1", "worker_id": "p2", "difficulty": "occlusion"},
        {"task_id": "t1", "worker_id": "n1", "difficulty": "trivial"},
        {"task_id": "t1", "worker_id": "n2", "difficulty": "trivial"},
    ]
    summary = build_three_state_summary(build_tag_observations(rows, source_artifact="fixture", source_sha256="sha"))
    occlusion = next(row for row in summary if row["tag_family"] == "difficulty" and row["tag_name"] == "occlusion")
    assert occlusion["task_tag_state"] == "replicated_explicit_conflict"
    assert occlusion["replicated_explicit_conflict"] == "true"


def test_missing_and_schema_errors_are_na_not_zero() -> None:
    rows = [
        {"task_id": "t1", "worker_id": "w1", "difficulty_present": "false"},
        {"task_id": "t1", "worker_id": "w2", "difficulty": "unknown_tag"},
    ]
    observations = build_tag_observations(rows, source_artifact="fixture", source_sha256="sha")
    difficulty = [row for row in observations if row["tag_family"] == "difficulty" and row["tag_name"] == "occlusion"]
    assert {row["na_reason"] for row in difficulty} == {"n_missing", "n_schema_uninterpretable"}


def test_state_ladder_and_explicit_balance_are_fixed() -> None:
    rows = [{"task_id": "t1", "worker_id": f"p{index}", "difficulty": "occlusion"} for index in range(4)]
    rows += [{"task_id": "t1", "worker_id": "n1", "difficulty": "trivial"}]
    summary = build_three_state_summary(build_tag_observations(rows, source_artifact="fixture", source_sha256="sha"))
    occlusion = next(row for row in summary if row["tag_name"] == "occlusion")
    assert occlusion["task_tag_state"] == "high_replication_positive"
    assert occlusion["explicit_balance"] == 0.8


def test_response_style_is_family_specific_and_non_routing() -> None:
    rows = [{"worker_id": "w1", "difficulty": "occlusion;seam", "model_issue": "acceptable"}, {"worker_id": "w1", "difficulty": "trivial", "model_issue": "corner_drift"}]
    output = build_response_style_diagnostics(rows, source_artifact="fixture", source_sha256="sha")
    by_family = {row["label_family"]: row for row in output}
    assert by_family["difficulty"]["multi_select_rate_given_specific"] == 1.0
    assert by_family["model_issue"]["acceptable_rate"] == 0.5
    assert all(row["routing_eligible"] == "false" for row in output)
