import json

from tools.paper_a_manhattan.run_hrc_candidate_adequacy_audit import (
    ALLOWED_NEXT_STEPS,
    SCHEMA_VERSION,
    build_audit_payload,
    run,
)


def test_candidate_adequacy_audit_conclusions_and_safety_flags():
    payload = build_audit_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["generated_new_candidates"] is False
    assert payload["active_runner_changed"] is False
    assert payload["ranking_changed"] is False
    assert payload["c3_changed"] is False
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["annotation_writeback"] is False

    assert payload["adequate_for_c6_3e_bucket_audit"] is False
    assert payload["adequate_for_hard_case_fix_claim"] is False
    assert payload["recommended_next_step"] in ALLOWED_NEXT_STEPS
    assert "C3 shadow expansion" not in payload["recommended_next_step"]
    assert "optimizer" not in payload["recommended_next_step"].lower()


def test_candidate_adequacy_case_coverage_and_risks():
    payload = build_audit_payload()
    cases = payload["cases"]

    ordinary = cases["ordinary_compatible"]
    assert ordinary["candidate_input_status"] == "unavailable"
    assert ordinary["candidate_count"] == 0
    assert ordinary["risk_flags"]["ordinary_compatible_missing_candidate_source"] is True
    assert ordinary["risk_flags"]["no_nonbaseline_candidate"] is True

    for name in ("task218_ann2369", "task238_ann2389", "gt75_task533"):
        summary = cases[name]
        assert summary["candidate_input_status"] == "available"
        assert summary["candidate_count"] > 0
        assert summary["risk_flags"]["height_only_candidates"] is True
        assert summary["risk_flags"]["no_geometry_diversity"] is True
        assert summary["risk_flags"]["hard_case_candidate_space_too_narrow"] is True
        assert summary["variable_coverage"]["top_y_change"] is True
        assert summary["variable_coverage"]["x_change"] is False

    task3741 = cases["task218_ann3741"]
    assert task3741["readiness"]["has_constrained_evaluation"] is True
    assert task3741["readiness"]["rankable_by_current_HRC"] is True
    assert task3741["candidate_count"] > 0


def test_candidate_adequacy_writes_artifacts(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.4 Candidate Adequacy Audit"
    )
