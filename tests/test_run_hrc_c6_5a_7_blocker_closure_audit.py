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
    explicit = json.loads(paths["explicit_column_identity"].read_text(encoding="utf-8"))
    keep = json.loads(paths["keep_distinct_contract"].read_text(encoding="utf-8"))
    assert explicit["evidence_type"] in schema["allowed_evidence_types"]
    assert explicit["verdict"] == "available_with_exception"
    assert explicit["verdict"] in schema["allowed_verdicts"]
    assert explicit["full_availability"] is False
    assert explicit["exceptions"] == [
        {
            "pair_index": 2,
            "status": "unresolved",
            "reason": "heavy occlusion and unreliable 3D preview texture in that region",
        }
    ]
    assert keep["verdict"] == "available"
    assert keep["keep_distinct_pairs"] == [[4, 5]]
    assert keep["must_not_merge"] is True
    assert keep["protruding_wall_structure_between_pairs"] == [4, 5]
    assert explicit["supporting_artifacts_are_manual_verdict"] is False
    assert keep["supporting_artifacts_are_manual_verdict"] is False

    rows = {row["case_name"]: row for row in payload["c4_evidence_gap_table"]}
    assert rows["task218_ann2369"]["c4_lite_scope"] == "baseline_to_baseline_only"
    assert rows["task218_ann2369"]["candidate_available"] is False
    assert rows["task218_ann2369"][
        "candidate_specific_projection_delta_available"
    ] is False
    assert rows["task218_ann2369"][
        "candidate_specific_image_evidence_available"
    ] is False
    assert rows["task238_ann2389_4543gt"]["selected_or_review_candidate"] == (
        "c6_5a_6_1_candidate_0003"
    )
    assert rows["task238_ann2389_4543gt"]["accepted_final_fix"] is False
    assert rows["task238_ann2389_4543gt"][
        "candidate_specific_projection_delta_available"
    ] is True
    assert rows["task238_ann2389_4543gt"][
        "candidate_specific_image_evidence_available"
    ] is False
    assert rows["task218_ann3741"][
        "candidate_specific_projection_delta_available"
    ] is True
    assert rows["task218_ann3741"][
        "candidate_specific_image_evidence_available"
    ] is False
    assert all(
        not row["candidate_specific_c4_contract_complete"] for row in rows.values()
    )
    assert all(not row["candidate_preference_authorized"] for row in rows.values())
    reference = json.loads(paths["same_image_reference"].read_text(encoding="utf-8"))
    gt = json.loads(Path("export_label/groudTruth.json").read_text(encoding="utf-8"))
    records = {
        annotation["id"]: (task["id"], task["data"]["image"], task["data"]["title"])
        for task in gt
        for annotation in task.get("annotations", [])
        if annotation.get("id") in (2369, 3741)
    }
    assert records[2369] == records[3741]
    assert reference["same_image"] is True
    assert reference["source_annotation_id"] == 2369
    assert reference["reference_annotation_id"] == 3741
    assert reference["verified_order"] == [2, 1, 3, 4, 6, 5, 8, 7, 9, 10, 12, 11]
    assert reference["accepted"] is False
    assert reference["candidate_preference_authorized"] is False
    assert reference["annotation_writeback"] is False


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
