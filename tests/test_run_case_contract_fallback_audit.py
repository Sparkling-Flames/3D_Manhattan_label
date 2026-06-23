import json

from tools.paper_a_manhattan.run_case_contract_fallback_audit import (
    SCHEMA_VERSION,
    build_payload,
    run,
)
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload as build_core_payload


def test_case_contract_fallback_audit_records_real_and_missing_metrics_paths():
    payload = build_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["active_runner_unchanged"] is True
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["annotation_writeback"] is False

    real = payload["cases"]["task218_ann3741"]
    assert real["contract_source"] == "rule_based_projection_v2"
    assert real["auto_contract_summary"]["source"] == "projection_rule_based_v1"
    assert real["legacy_default_contract"]["used"] is False
    assert real["fallback_used"] is False
    assert real["evidence_available_flags"]["projection_metrics"] is True
    assert real["protected_pairs"]
    assert real["movable_fields_by_pair"]
    assert all(real["inferred_fields_present"].values())
    assert real["safety_boundary"]["automatic_apply"] is False
    assert real["safety_boundary"]["annotation_writeback"] is False
    assert real["safety_boundary"]["worker_facing"] is False
    assert real["safety_boundary"]["routing_input"] is False

    missing = payload["cases"]["synthetic_missing_metrics"]
    assert missing["contract_source"] == "rule_based_v1"
    assert missing["auto_contract_summary"]["source"] == "legacy_fallback"
    assert missing["legacy_default_contract"]["used"] is True
    assert missing["fallback_used"] is True
    assert missing["risk"] == "legacy_default_contract_in_active_contract"
    assert missing["evidence_available_flags"]["projection_metrics"] is False
    assert missing["primary_edges"] == ["6-7"]
    assert missing["secondary_edges"] == ["2-3"]
    assert missing["local_window_pairs"] == [5, 6, 7, 8]
    assert not any(missing["inferred_fields_nonempty"].values())

    paths = run()
    written = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert written["cases"]["synthetic_missing_metrics"]["fallback_used"] is True
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C1.1 Case Contract Fallback Audit"
    )


def test_case_contract_audit_does_not_change_active_runner_selection():
    payload = build_core_payload()
    assert payload["candidate_source_metadata"]["source_id"] == "legacy_m1528"
    assert payload["candidate_source_metadata"]["source_type"] == "legacy_m1528_action_library"
    assert payload["portfolio_ranking"]["best_manhattan_feasible"]["candidate"]["candidate_id"] == "m1528_candidate_0017"
    assert payload["portfolio_ranking"]["best_balanced"]["candidate"]["candidate_id"] == "m1528_candidate_0017"
    assert payload["portfolio_ranking"]["best_height_consistent"]["candidate"]["candidate_id"] == "m1528_candidate_0017"
    assert payload["overall_verdict"]["recommended_review_candidate_available"] is False
    for name, bucket in payload["portfolio_ranking"].items():
        if name in {"diagnostic_only_candidates", "suppressed_candidates"}:
            continue
        assert bucket["accepted"] is False
        assert bucket["downstream_recommendation"] is False
