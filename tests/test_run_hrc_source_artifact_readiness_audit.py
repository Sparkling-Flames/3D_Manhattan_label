import json

from tools.paper_a_manhattan.run_hrc_source_artifact_readiness_audit import (
    EVIDENCE_TYPES,
    SCHEMA_VERSION,
    STATUSES,
    build_audit_payload,
    run,
)


def test_readiness_audit_is_read_only_and_blocked():
    payload = build_audit_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["generated_candidate"] is False
    assert payload["generated_proposal_manifest"] is False
    assert payload["generated_geometry_variant"] is False
    assert payload["active_runner_changed"] is False
    assert payload["ranking_changed"] is False
    assert payload["c3_changed"] is False
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["annotation_writeback"] is False
    assert payload["execution_allowed"] is False
    assert payload["artifact_inputs_ready_for_c6_5b"] is False
    assert payload["artifact_inputs_ready_cases"] == []
    assert set(payload["status_boundaries"].values()) == {"blocked"}


def test_manifest_validation_and_readiness_semantics():
    payload = build_audit_payload()
    cases = payload["cases"]
    assert set(cases) == {
        "task218_ann3741",
        "task218_ann2369",
        "task238_ann2389",
        "task238_ann2389_4543gt",
        "gt75_task533",
        "ordinary_compatible",
    }
    for case in cases.values():
        assert case["execution_allowed"] is False
        assert "ready" not in case
        assert all("ready" not in row for row in case["probe_family_readiness"].values())
        assert all(
            "artifact_inputs_ready" in row and row["execution_allowed"] is False
            for row in case["probe_family_readiness"].values()
        )
        assert all(validation["valid"] for validation in case["source_validation"].values())
        matrix = case["evidence_readiness_matrix"]
        assert set(matrix) == set(EVIDENCE_TYPES)
        assert all(row["status"] in STATUSES for row in matrix.values())

    task3741 = cases["task218_ann3741"]
    manual = task3741["evidence_readiness_matrix"]["explicit_column_identity"]
    assert manual["status"] == "requires_manual_visual_evidence"
    assert manual["source_artifact"] is None
    assert manual["sha256"] is None
    assert manual["supporting_artifacts"]
    assert manual["manual_evidence_sidecar_schema"]
    assert task3741["probe_family_readiness"]["multi_pair_x_alignment"]["artifact_inputs_ready"] is False

    for name in ("task218_ann2369", "task238_ann2389"):
        matrix = cases[name]["evidence_readiness_matrix"]
        assert matrix["direction_family_fit"]["status"] == "materializable_from_existing_artifact"
        assert matrix["parallel_family_residual"]["status"] == "materializable_from_existing_artifact"
        assert matrix["projection_derived_height_evidence"]["status"] == "available_from_existing_artifact"
        assert matrix["candidate_row_height_source"]["status"] == "available_from_existing_artifact"

    assert cases["task238_ann2389"]["source_status"] == "deprecated_old_gt_diagnostic"
    corrected = cases["task238_ann2389_4543gt"]
    assert corrected["corrected_gt_materialized"] is True
    assert corrected["corrected_gt_id"] == "4543gt"
    assert corrected["manual_evidence_available_for_corrected_gt"] is True
    assert corrected["candidate_specific"] is False
    assert corrected["candidate_preference_authorized"] is False
    assert corrected["short_wall_exists"] is False
    assert corrected["keep_distinct_required"] is False
    assert corrected["corrected_pair_count"] == 4
    assert corrected["evidence_readiness_matrix"]["explicit_column_identity"]["status"] == "available_from_existing_artifact"
    assert corrected["evidence_readiness_matrix"]["keep_distinct_contract"]["status"] == "not_applicable"
    assert corrected["probe_family_readiness"]["short_wall_preserving_floorprint_balance"]["applicable"] is False
    assert corrected["probe_family_readiness"]["short_wall_preserving_floorprint_balance"]["artifact_inputs_ready"] is False
    assert corrected["candidate_dry_run"]["generated"] is True
    assert corrected["candidate_dry_run"]["candidate_count"] > 0
    assert corrected["candidate_dry_run"]["candidate_preference_authorized"] is False
    assert corrected["manual_selection"] == {
        "selected_candidate": "c6_5a_6_1_candidate_0003",
        "selected_y_step": 0.75,
        "review_only": True,
        "accepted": False,
        "candidate_preference_authorized": False,
    }
    sidecars = cases["task218_ann2369"]["manual_sidecar_status"]
    assert set(sidecars) == {"explicit_column_identity", "keep_distinct_contract"}
    assert all(row["verdict"] == "unavailable" for row in sidecars.values())
    assert all(
        row["supporting_artifacts_are_manual_verdict"] is False
        for row in sidecars.values()
    )
    assert payload["candidate_preference_authorized"] == {
        "task218_ann2369": False,
        "task238_ann2389": False,
        "task238_ann2389_4543gt": False,
    }
    assert payload["corrected_gt_status_summary"] == {
        "old_case": "task238_ann2389",
        "old_case_role": "deprecated_old_gt_diagnostic_only",
        "old_case_manual_requirements_are_corrected_gt_blockers": False,
        "corrected_case": "task238_ann2389_4543gt",
        "candidate_preference_authorized_old_case": False,
        "candidate_preference_authorized_corrected_case": False,
    }

    gt75 = cases["gt75_task533"]["evidence_readiness_matrix"]
    assert gt75["verified_order_record"]["status"] == "available_from_existing_artifact"
    assert gt75["projection_metrics"]["status"] == "unavailable"
    assert gt75["projection_derived_height_evidence"]["status"] == "unavailable"
    assert gt75["candidate_row_height_source"]["status"] == "available_from_existing_artifact"

    assert "C6.5a.5.1 consistency fix" not in payload["recommended_next_step"]
    assert payload["recommended_next_step"] == (
        "human review of task218_ann2369 explicit column identity and "
        "keep-distinct contract; candidate-specific C4 evidence remains required"
    )
    forbidden = ("C3", "C7", "optimizer", "active runner", "writeback", "proposal manifest")
    assert not any(token.lower() in payload["recommended_next_step"].lower() for token in forbidden)


def test_readiness_audit_writes_artifacts(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.5a.1 Source Artifact Readiness Audit"
    )
