from tools.thesis_main.analysis.routing.offline_replay_v2 import replay_sequential_routing


def test_offline_replay_never_generates_formal_assignment() -> None:
    rows = replay_sequential_routing([
        {"task_id": "t1", "base_task_id": "b1", "snapshot_id": "s1", "n_independent_workers": "2", "support_gap_candidate": "false", "stage": "C1", "validity_status": "dry_run"},
    ])
    assert rows[0]["formal_assignment_generated"] == "false"
    assert rows[0]["candidate_only"] is True
    assert rows[0]["routing_eligible"] is False
    assert rows[0]["validity_status"] == "dry_run"
    assert rows[0]["artifact_role"] == "static_evidence_scaffold"
    assert rows[0]["temporal_replay"] == "false"
