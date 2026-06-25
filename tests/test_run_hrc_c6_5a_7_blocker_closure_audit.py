import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_hrc_c6_5a_7_blocker_closure_audit import run


def test_blocker_closure_does_not_forge_manual_or_candidate_evidence(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    schema = json.loads(
        Path(
            "analysis_results/paper_a_manhattan/hypothesis_ranking_core/"
            "source_artifact_readiness_audit/manual_evidence_sidecar_schema.json"
        ).read_text(encoding="utf-8")
    )
    for evidence_type in ("explicit_column_identity", "keep_distinct_contract"):
        sidecar = json.loads(paths[evidence_type].read_text(encoding="utf-8"))
        assert sidecar["evidence_type"] in schema["allowed_evidence_types"]
        assert sidecar["verdict"] == "unavailable"
        assert sidecar["reviewer"] == "pending_human_expert"
        assert sidecar["reviewed_at"] is None
        assert sidecar["supporting_artifacts_are_manual_verdict"] is False

    rows = {row["case_name"]: row for row in payload["c4_evidence_gap_table"]}
    assert rows["task218_ann2369"]["c4_lite_scope"] == "baseline_to_baseline_only"
    assert rows["task218_ann2369"]["candidate_specific_c4_available"] is False
    assert rows["task238_ann2389_4543gt"]["selected_or_review_candidate"] == (
        "c6_5a_6_1_candidate_0003"
    )
    assert rows["task238_ann2389_4543gt"]["accepted_final_fix"] is False
    assert rows["task238_ann2389_4543gt"][
        "candidate_specific_c4_available"
    ] is False
    assert rows["task218_ann3741"]["candidate_specific_c4_available"] is True
    assert all(not row["candidate_preference_authorized"] for row in rows.values())


def test_blocker_closure_preserves_sources_and_boundaries(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    for source_name in ("old_gt", "corrected_gt"):
        source = payload["source_artifacts"][source_name]
        assert hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() == source[
            "sha256"
        ]
    assert payload["c6_5b_readiness_decision"]["authorized"] is False
    assert payload["c6_5b_readiness_decision"]["decision"] == "blocked"
    assert payload["selected_candidate_status"]["accepted"] is False
    assert payload["selected_candidate_status"]["downstream_recommendation"] is False
    assert payload["safety_boundary"]["annotation_patch_generated"] is False
    assert payload["safety_boundary"]["annotation_writeback"] is False
    assert set(payload["status_boundaries"].values()) == {"blocked"}
