import pytest

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, replay_temporal_events


def _policy(eval_fold: int, tmp_path) -> dict:
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != eval_fold)
    artifact = tmp_path / f"policy-{eval_fold}.json"
    artifact.write_text('{"meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25, "min_q_boundary": 0.8, "min_q_wallwall": 0.8}', encoding="utf-8")
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    return {"policy_artifact_id": f"policy-{eval_fold}", "policy_artifact_path": str(artifact), "policy_artifact_sha256": sha256_file(artifact), "rule_version": "test-policy-v1", "fit_folds": [1 - eval_fold], "fit_base_task_ids": [fit_base]}


def test_temporal_replay_uses_only_prior_arrivals_and_base_folds(tmp_path) -> None:
    events = [
        {"event_id": "e2", "arrived_at": "2026-01-01T00:02:00Z", "task_id": "t2", "base_task_id": "b", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:01:00Z", "task_id": "t1", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
    ]
    evidence = {(event["canonical_annotation_id"], event["tag_family"], event["tag_name"]): {**event, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+"} for event in events}
    fold = _fold_for_base("b", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)
    assert [row["prior_legal_arrivals"] for row in rows] == [0, 1]
    assert [row["a"] for row in rows] == [0, 1]
    assert {row["crossfit_fold"] for row in rows} == {rows[0]["crossfit_fold"]}
    assert all(row["policy_fit_excludes_fold"] is True for row in rows)


def test_temporal_replay_rejects_missing_arrival_metadata(tmp_path) -> None:
    with pytest.raises(ValueError, match="event_id"):
        replay_temporal_events([{"task_id": "t", "base_task_id": "b"}], policy_by_fold={_fold_for_base("b", 2): _policy(_fold_for_base("b", 2), tmp_path)})


def test_temporal_replay_preserves_worker_identity_prior_state_and_utc_order(tmp_path) -> None:
    events = [
        {"event_id": "e3", "arrived_at": "2026-01-01T03:00:00+03:00", "task_id": "t3", "base_task_id": "b3", "canonical_annotation_id": "a3", "worker_id": "w3", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "task_id": "t1", "base_task_id": "b3", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e2", "arrived_at": "2026-01-01T01:00:00+01:00", "task_id": "t2", "base_task_id": "b3", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
    ]
    assertions = {"a1": "+", "a2": "-", "a3": "0"}
    evidence = {
        (event["canonical_annotation_id"], event["tag_family"], event["tag_name"]): {
            **event, "arrived_at": event["arrived_at"], "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": assertions[event["canonical_annotation_id"]],
        }
        for event in events
    }
    fold = _fold_for_base("b3", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)
    assert [row["event_id"] for row in rows] == ["e1", "e2", "e3"]
    assert [row["candidate_worker_id"] for row in rows] == ["w1", "w2", "w3"]
    assert rows[0]["arrived_at_utc"] == "2026-01-01T00:00:00+00:00"
    assert all(row["event_legal"] == "true" for row in rows)
    assert rows[0]["assertion"] == "+"
    assert rows[2]["prior_eligible_workers_json"] == '["w1", "w2"]'
    assert (rows[2]["a"], rows[2]["e"], rows[2]["u"]) == (1, 1, 0)
    assert rows[2]["action"] == "escalate_candidate"


def test_temporal_replay_keeps_tags_separate_and_batches_same_annotation(tmp_path) -> None:
    events = [
        {"event_id": "e1a", "arrived_at": "2026-01-01T00:00:00Z", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e1b", "arrived_at": "2026-01-01T00:00:00Z", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "model_issue", "tag_name": "corner_drift", "candidate_available_before_event": "true"},
        {"event_id": "e2", "arrived_at": "2026-01-01T00:01:00Z", "base_task_id": "b", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
    ]
    evidence = {(row["canonical_annotation_id"], row["tag_family"], row["tag_name"]): {**row, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+", "assertion_source": "explicit_worker_label"} for row in events}
    fold = _fold_for_base("b", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)
    assert [rows[0]["prior_legal_arrivals"], rows[1]["prior_legal_arrivals"]] == [0, 0]
    assert rows[2]["prior_legal_arrivals"] == 1
    assert rows[1]["a"] == 0


def test_temporal_replay_marks_missing_candidate_binding_illegal(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence = {("a1", "difficulty", "occlusion"): {**event, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+"}}
    fold = _fold_for_base("b", 2)
    row = replay_temporal_events([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)[0]
    assert row["event_legal"] == "false"
    assert "invalid_candidate_available_before_event" in row["event_legal_reason"]


def test_temporal_replay_stop_uses_prior_geometry_channels(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": f"2026-01-01T00:0{i}:00Z", "base_task_id": "b", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"} for i in (1, 2, 3)]
    evidence = {(row["canonical_annotation_id"], "difficulty", "occlusion"): {**row, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+"} for row in events}
    geometry = {row["canonical_annotation_id"]: normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400]]) for row in events}
    fold = _fold_for_base("b", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id=geometry)
    assert rows[2]["geometry_status"] == "evaluable"
    assert rows[2]["geometry_support"] == 2
    assert rows[2]["action"] == "stop_candidate"
