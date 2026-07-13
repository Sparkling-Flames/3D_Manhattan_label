import pytest

from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, replay_temporal_events


def _policy(eval_fold: int, tmp_path) -> dict:
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != eval_fold)
    artifact = tmp_path / f"policy-{eval_fold}.json"
    artifact.write_text("{}", encoding="utf-8")
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    return {"policy_artifact_id": f"policy-{eval_fold}", "policy_artifact_path": str(artifact), "policy_artifact_sha256": sha256_file(artifact), "rule_version": "test-policy-v1", "fit_folds": [1 - eval_fold], "fit_base_task_ids": [fit_base]}


def test_temporal_replay_uses_only_prior_arrivals_and_base_folds(tmp_path) -> None:
    events = [
        {"event_id": "e2", "arrived_at": "2026-01-01T00:02:00Z", "task_id": "t2", "base_task_id": "b", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:01:00Z", "task_id": "t1", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion"},
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
        {"event_id": "e3", "arrived_at": "2026-01-01T03:00:00+03:00", "task_id": "t3", "base_task_id": "b3", "canonical_annotation_id": "a3", "worker_id": "w3", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "support_gap_candidate": "true"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "task_id": "t1", "base_task_id": "b3", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion"},
        {"event_id": "e2", "arrived_at": "2026-01-01T01:00:00+01:00", "task_id": "t2", "base_task_id": "b3", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion"},
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
    assert rows[2]["action"] == "stop_candidate"
