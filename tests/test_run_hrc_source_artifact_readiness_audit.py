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
    assert payload["ready_for_c6_5b_proposal_manifest"] is False
    assert payload["ready_cases"] == []
    assert set(payload["status_boundaries"].values()) == {"blocked"}


def test_readiness_matrix_fail_closed_rules():
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
        matrix = case["evidence_readiness_matrix"]
        assert set(matrix) == set(EVIDENCE_TYPES)
        assert all(row["status"] in STATUSES for row in matrix.values())
        for row in matrix.values():
            assert set(row) == {
                "status",
                "source_artifact",
                "sha256",
                "materialization_hint",
                "missing_reason",
                "manual_evidence_requirement",
            }
            if row["status"] in {
                "available_from_existing_artifact",
                "materializable_from_existing_artifact",
                "requires_manual_visual_evidence",
            }:
                assert row["source_artifact"]
                assert row["sha256"]

    ordinary = cases["ordinary_compatible"]
    assert ordinary["source_readiness"] == "source_blocked"
    assert ordinary["probe_family_readiness"]["multi_pair_x_alignment"]["ready"] is False
    assert ordinary["probe_family_readiness"]["floor_depth_balance_global"]["ready"] is False

    task3741 = cases["task218_ann3741"]
    assert task3741["evidence_readiness_matrix"]["rankable_by_current_HRC"]["status"] == "available_from_existing_artifact"
    assert task3741["evidence_readiness_matrix"]["explicit_column_identity"]["status"] == "requires_manual_visual_evidence"
    assert task3741["probe_family_readiness"]["multi_pair_x_alignment"]["ready"] is False

    for name in ("task218_ann2369", "task238_ann2389"):
        matrix = cases[name]["evidence_readiness_matrix"]
        assert matrix["direction_family_fit"]["status"] == "materializable_from_existing_artifact"
        assert matrix["parallel_family_residual"]["status"] == "materializable_from_existing_artifact"

    assert cases["gt75_task533"]["evidence_readiness_matrix"]["verified_order_record"]["status"] == "available_from_existing_artifact"
    assert cases["gt75_task533"]["evidence_readiness_matrix"]["projection_metrics"]["status"] == "unavailable"
    assert payload["manual_evidence_required"]
    assert payload["recommended_next_step"] == "materialize available source artifacts"
    forbidden = ("C3", "C7", "optimizer", "active runner", "writeback")
    assert not any(token.lower() in payload["recommended_next_step"].lower() for token in forbidden)


def test_readiness_audit_writes_artifacts(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.5a.1 Source Artifact Readiness Audit"
    )
