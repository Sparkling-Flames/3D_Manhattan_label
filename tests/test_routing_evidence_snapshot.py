from tools.thesis_main.analysis.routing.evidence_snapshot import build_evidence_snapshot
from tools.thesis_main.analysis.routing.sequential_rule import candidate_rule_config, decide_candidate_action


def test_routing_snapshot_is_task_level_and_non_eligible() -> None:
    rows = build_evidence_snapshot([
        {"task_id": "t1", "worker_id": "w1", "geometry_hash": "g", "primary_active_time_eligible": "true"},
        {"task_id": "t1", "worker_id": "w2", "geometry_hash": "g", "primary_active_time_eligible": "true"},
    ])
    assert rows[0]["n_independent_workers"] == 2
    assert rows[0]["routing_eligible"] == "false"
    assert rows[0]["interpretation_allowed"] == "false"


def test_sequential_rule_supports_legacy_read_compatibility() -> None:
    config = candidate_rule_config("low_risk", k0=2, k_max=5)
    action = decide_candidate_action({"n_independent_workers": 2}, config)
    assert config["legacy_compatibility_mode"] == "legacy_fixed_cap"
    assert action["k_min_for_stop"] == 2
    assert action["routing_eligible"] is False

