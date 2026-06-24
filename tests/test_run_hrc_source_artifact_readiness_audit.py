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

    gt75 = cases["gt75_task533"]["evidence_readiness_matrix"]
    assert gt75["verified_order_record"]["status"] == "available_from_existing_artifact"
    assert gt75["projection_metrics"]["status"] == "unavailable"
    assert gt75["projection_derived_height_evidence"]["status"] == "unavailable"
    assert gt75["candidate_row_height_source"]["status"] == "available_from_existing_artifact"

    assert payload["recommended_next_step"] == "materialize audit-only evidence inputs from existing artifacts"
    forbidden = ("C3", "C7", "optimizer", "active runner", "writeback", "proposal manifest")
    assert not any(token.lower() in payload["recommended_next_step"].lower() for token in forbidden)


def test_readiness_audit_writes_artifacts(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.5a.1 Source Artifact Readiness Audit"
    )
