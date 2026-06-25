from tools.paper_a_manhattan.candidate_specific_c4_evidence_contract import (
    validate_candidate_specific_c4,
)
from tools.paper_a_manhattan.run_hrc_candidate_specific_c4_contract_audit import (
    build_payload,
    run,
)


def test_current_candidate_specific_c4_records_fail_closed():
    payload = build_payload()
    rows = {row["case_name"]: row for row in payload["records"]}
    for row in rows.values():
        evaluation = row["contract_evaluation"]
        assert evaluation["candidate_specific_projection_delta_available"] is True
        assert evaluation["candidate_specific_image_evidence_available"] is False
        assert evaluation["manual_visual_note_available"] is True
        assert evaluation["manual_image_evidence_note_available"] is False
        assert evaluation["candidate_specific_c4_contract_complete"] is False
        assert evaluation["candidate_preference_authorized"] is False
        assert evaluation["fail_closed"] is True
    assert rows["task218_ann3741"]["candidate_id"] == "m1528_candidate_0017"
    assert rows["task238_ann2389_4543gt"]["candidate_id"] == (
        "c6_5a_6_1_candidate_0003"
    )


def test_complete_contract_requires_all_candidate_image_inputs():
    payload = {
        "schema_version": "hrc_candidate_specific_c4_evidence_v1",
        "case_name": "fixture",
        "candidate_id": "candidate",
        "baseline_only": {"available": True},
        "candidate_specific_projection_delta": {"status": "available"},
        "candidate_specific_image_evidence": {
            "status": "available",
            "image_edge_support": {"status": "available"},
            "candidate_image_boundary_alignment_delta": {"rmse_delta": -1.0},
            "manual_image_evidence_note": {"verdict": "supports_candidate"},
        },
        "manual_visual_note": {"status": "available"},
        "safety_boundary": {},
    }
    evaluation = validate_candidate_specific_c4(payload)
    assert evaluation["candidate_specific_c4_contract_complete"] is True
    assert evaluation["fail_closed"] is False
    assert evaluation["candidate_preference_authorized"] is False


def test_contract_audit_writes_artifacts(tmp_path):
    paths = run(tmp_path)
    assert paths["json"].exists()
    assert "fail closed" in paths["markdown"].read_text(encoding="utf-8")
