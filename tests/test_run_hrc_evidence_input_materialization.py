import json

from tools.paper_a_manhattan.run_hrc_evidence_input_materialization import (
    SCHEMA_VERSION,
    TARGET_CASES,
    build_payload,
    run,
)


def test_materialization_is_audit_only_and_does_not_rank():
    payload = build_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["processed_cases"] == list(TARGET_CASES)
    assert payload["processed_status"] == "existing_artifact_only_with_corrected_gt"
    assert payload["manual_evidence_processed"] is True
    assert payload["supporting_artifacts_used_as_manual_verdicts"] is False
    assert payload["generated_candidate"] is False
    assert payload["generated_proposal_manifest"] is False
    assert payload["generated_geometry_variant"] is False
    assert payload["active_runner_changed"] is False
    assert payload["ranking_changed"] is False
    assert payload["c3_changed"] is False
    assert payload["execution_allowed"] is False
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["annotation_writeback"] is False
    assert payload["c6_status"] == "audit_blocked"
    assert payload["c6_5b_authorized"] is False
    assert set(payload["status_boundaries"].values()) == {"blocked"}


def test_materialized_fields_and_source_validation():
    payload = build_payload()
    expected = {
        "c4_evidence_diagnostics",
        "c5_plane_proxy_metrics",
        "case_contract",
        "constrained_evaluation",
        "direction_family_fit",
        "parallel_family_residual",
        "rankable_by_current_HRC",
    }
    for name in ("task218_ann2369", "task238_ann2389"):
        case = payload["cases"][name]
        assert set(case["processed_materializable_inputs"]) == expected
        assert case["direction_family_fit"]["status"] == "available"
        assert case["parallel_family_residual"]["status"] == "available"
        assert case["case_contract"]["contract_status"] == "available"
        assert case["case_contract"]["fail_closed"] is False
        assert case["case_contract"]["legacy_default_contract"]["used"] is False
        assert case["constrained_evaluation"]["baseline_original_not_candidate_evaluation"] is True
        assert case["constrained_evaluation"]["evaluation_status"] == "complete"
        assert case["c4_lite_diagnostics"]["evidence_status"] == "available"
        assert case["c4_lite_diagnostics"]["baseline_to_baseline_materialization"] is True
        assert case["c4_lite_diagnostics"]["candidate_preference_claim"] is False
        assert case["c5_plane_proxy_metrics"]["plane_proxy_status"] in {"available", "partial_available"}
        assert case["rankable_by_current_HRC_input_summary"]["rankable"] is False
        assert case["rankable_by_current_HRC_input_summary"]["ranking_key_materialized"] is False
        assert case["rankable_by_current_HRC_input_summary"]["portfolio_materialized"] is False
        assert case["candidate_rows_read_only"]["modified"] is False
        assert case["candidate_rows_read_only"]["used_as_projected_candidate_variant"] is False
        assert case["audit_only"] is True
        assert case["execution_allowed"] is False
        assert all(row["sha256"] for row in case["source_artifacts"].values())

    corrected = payload["cases"]["task238_ann2389_4543gt"]
    assert corrected["projection_pair_count"] == 4
    assert corrected["old_gt_projection_used"] is False
    assert "4543gt" in corrected["source_artifacts"]["corrected_projection"]["path"]
    assert corrected["old_gt_projection_path"] not in json.dumps(
        corrected["source_artifacts"]
    )
    assert corrected["manual_evidence"] == {
        "explicit_column_identity": "available",
        "keep_distinct_contract": "not_applicable",
        "short_wall_exists": False,
        "keep_distinct_required": False,
    }
    assert corrected["candidate_specific"] is False
    assert corrected["candidate_count"] == 0
    assert corrected["candidate_preference_authorized"] is False
    assert corrected["candidate_dry_run"]["generated"] is True
    assert corrected["candidate_dry_run"]["candidate_count"] > 0
    assert corrected["candidate_dry_run"]["used_for_preference"] is False
    assert corrected["rankable_by_current_HRC_input_summary"][
        "candidate_preference_authorized"
    ] is False
    assert corrected["accepted"] is False
    assert corrected["downstream_recommendation"] is False
    assert corrected["annotation_writeback"] is False


def test_materialization_writes_json_and_markdown(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.5a.2 Evidence Input Materialization"
    )
