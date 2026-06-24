import json
import copy

from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
)
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload
from tools.paper_a_manhattan.run_hrc_scoring_compliance_audit import (
    SCHEMA_VERSION,
    build_audit_payload,
    run,
)


def test_scoring_compliance_audit_reports_partial_without_mutation():
    payload = build_audit_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["contract_compliance_status"] == "partial"
    assert payload["audit_only"] is True
    assert payload["evaluator_changed"] is False
    assert payload["ranking_key_changed"] is False
    assert payload["portfolio_changed"] is False
    assert payload["active_runner_changed"] is False
    assert payload["c3_changed"] is False
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["annotation_writeback"] is False
    assert payload["c6_status"] == "audit_blocked"
    assert payload["c6_5b_authorized"] is False
    assert payload["c6_5a_4_authorized"] is False
    assert set(payload["status_boundaries"].values()) == {"blocked"}


def test_layer_mapping_and_violations_match_current_implementation():
    payload = build_audit_payload()
    assert set(payload["layer_mapping"]) == {"L0", "L1", "L2", "L3", "L4", "L5"}
    mapping = payload["ranking_key_mapping"]
    assert [row["index"] for row in mapping] == list(range(17))
    assert mapping[0] == {"index": 0, "field": "not hard_gate_passed", "layer": "L0"}
    assert mapping[10]["layer"] == "L3"
    assert mapping[11]["layer"] == "L2"
    assert all(row["layer"] == "L5" for row in mapping[-2:])

    audits = payload["layer_audits"]
    assert audits["L0"]["status"] == "complete"
    assert audits["L0"]["residual_height_or_movement_can_override_hard_gate"] is False
    assert audits["L1"]["single_direction_metric_can_dominate_current_global_key"] is True
    assert audits["L1"]["turn_and_local_residual_present_in_global_key"] is False
    assert audits["L2"]["candidate_preference_authorized"] is False
    assert audits["L2"]["baseline_only_diagnostics"] is True
    assert audits["L3"]["c5_is_c4_evidence"] is False
    assert audits["L5"]["legacy_score_in_active_ranking_key"] is False

    codes = {row["code"] for row in payload["layer_order_violations"]}
    assert {
        "L1_DIRECTION_PRECEDES_MULTI_METRIC_STRUCTURE",
        "L2_AFTER_L3_IN_GLOBAL_KEY",
        "C5_MIXED_INTO_MANHATTAN_BUCKET_KEY",
        "L2_BASELINE_ONLY_CANNOT_PREFER_CANDIDATE",
        "L4_MANUAL_EVIDENCE_INCOMPLETE",
    } <= codes
    assert payload["accepted_gate_audit"]["all_portfolio_buckets_accepted_false"] is True
    assert "C6.5b" not in payload["next_allowed_step"]


def test_scoring_compliance_audit_writes_artifacts(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.5a.3 Scoring Compliance Audit"
    )


def test_current_ranking_key_shape_hard_gate_and_legacy_exclusion():
    payload = build_payload()
    evaluation = next(iter(payload["constrained_evaluations"].values()))
    key = build_hypothesis_ranking_key(evaluation)
    assert len(key) == 17
    assert key[0] is (not evaluation["feasibility"]["hard_gate_passed"])

    changed = copy.deepcopy(evaluation)
    changed["local_score_total"] = 999999
    changed["legacy_score_breakdown"] = {"local_score_total": 999999}
    assert build_hypothesis_ranking_key(changed) == key
