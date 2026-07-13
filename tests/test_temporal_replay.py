import pytest

from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, replay_temporal_events


def _policy(eval_fold: int, tmp_path) -> dict:
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != eval_fold)
    artifact = tmp_path / f"policy-{eval_fold}.json"
    artifact.write_text("{}", encoding="utf-8")
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    return {"policy_artifact_id": f"policy-{eval_fold}", "policy_artifact_path": str(artifact), "policy_artifact_sha256": sha256_file(artifact), "rule_version": "test-policy-v1", "fit_folds": [1 - eval_fold], "fit_base_task_ids": [fit_base]}


def test_temporal_replay_uses_only_prior_arrivals_and_base_folds(tmp_path) -> None:
    rows = replay_temporal_events([
        {"event_id": "e2", "arrived_at": "2026-01-01T00:02:00Z", "task_id": "t2", "base_task_id": "b", "canonical_annotation_id": "a2"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:01:00Z", "task_id": "t1", "base_task_id": "b", "canonical_annotation_id": "a1"},
    ], policy_by_fold={0: _policy(0, tmp_path), 1: _policy(1, tmp_path)})
    assert [row["prior_legal_arrivals"] for row in rows] == [0, 1]
    assert {row["crossfit_fold"] for row in rows} == {rows[0]["crossfit_fold"]}
    assert all(row["policy_fit_excludes_fold"] is True for row in rows)


def test_temporal_replay_rejects_missing_arrival_metadata(tmp_path) -> None:
    with pytest.raises(ValueError, match="event_id"):
        replay_temporal_events([{"task_id": "t", "base_task_id": "b"}], policy_by_fold={0: _policy(0, tmp_path), 1: _policy(1, tmp_path)})
