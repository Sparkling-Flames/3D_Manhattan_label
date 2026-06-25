import json

from tools.paper_a_manhattan.run_hrc_c6_5a_6_candidate_dry_run import (
    CASE_NAME,
    build_payload,
    run,
)


def test_candidate_dry_run_uses_corrected_four_pair_source():
    payload = build_payload()
    assert payload["case_name"] == CASE_NAME
    assert payload["schema_version"] == "hrc_c6_5a_6_1_pair2_y_step_audit_v1"
    assert payload["source_artifacts"]["corrected_projection"]["pair_count"] == 4
    assert "4543gt" in payload["source_artifacts"]["corrected_projection"]["path"]
    assert "local_3d_projection/task238_ann2389" not in json.dumps(
        payload["source_artifacts"]
    )
    assert payload["candidate_count"] > 0
    assert all(row["pair_count"] == 4 for row in payload["candidate_set"])
    assert all(row["topology_preserved"] is True for row in payload["candidate_set"])
    assert all(row["diagnostics"]["self_intersection"] is False for row in payload["candidate_set"])
    assert all(row["diagnostics"]["short_wall_count"] == 0 for row in payload["candidate_set"])
    assert payload["audit_stage"] == "C6.5a.6.1"
    assert payload["provenance_resolution"]["prior_c6_5a_6_candidate_0002_y_delta"] == 0.75
    assert payload["provenance_resolution"]["stale_description_y_delta"] == 0.50
    assert [row["y_step"] for row in payload["candidate_set"]] == [
        0.25,
        0.50,
        0.75,
        1.00,
    ]
    for row in payload["candidate_set"]:
        fields = row["coordinate_changes"][0]["fields"]
        assert set(fields) == {"top_y", "bottom_y"}
        assert fields["top_y"]["delta"] == fields["bottom_y"]["delta"] == row["y_step"]
        assert row["candidate_specific_c4"]["available"] is False
    assert payload["manual_visual_observation"]["preferred_y_step"] == 0.75
    assert payload["manual_visual_observation"]["scope"] == (
        "manual_visual_preference_only_not_automatic_acceptance"
    )


def test_candidate_dry_run_preserves_authorization_boundaries():
    payload = build_payload()
    assert payload["candidate_preference_authorized"] is False
    assert payload["generated_proposal"] is False
    assert payload["generated_geometry_search_result"] is False
    assert payload["safety_boundary"]["accepted"] is False
    assert payload["safety_boundary"]["downstream_recommendation"] is False
    assert payload["safety_boundary"]["annotation_patch_generated"] is False
    assert payload["safety_boundary"]["annotation_writeback"] is False
    assert set(payload["status_boundaries"].values()) == {"blocked"}
    for candidate in payload["candidate_set"]:
        assert candidate["candidate_specific_c4"]["availability"] == "unavailable"
        assert candidate["candidate_specific_c4"]["candidate_preference_authorized"] is False
        assert candidate["accepted"] is False
        assert candidate["downstream_recommendation"] is False


def test_candidate_dry_run_writes_preview(tmp_path):
    paths = run(tmp_path / "audit", tmp_path / "preview")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["review_manifest"].read_text(encoding="utf-8"))
    preview = json.loads(paths["preview_json"].read_text(encoding="utf-8"))
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert payload["candidate_count"] == 4
    assert len(preview["variants"]) == 5
    payload_deltas = [
        row["coordinate_changes"][0]["fields"]["top_y"]["delta"]
        for row in payload["candidate_set"]
    ]
    manifest_deltas = [
        row["coordinate_changes"][0]["fields"]["top_y"]["delta"]
        for row in manifest["candidates"]
    ]
    preview_deltas = [
        row["candidate_row"]["coordinate_changes"][0]["fields"]["top_y"]["delta"]
        for row in preview["variants"][1:]
    ]
    assert payload_deltas == manifest_deltas == preview_deltas == [0.25, 0.5, 0.75, 1.0]
    for step in payload_deltas:
        assert f"{step:+.2f}" in markdown
    assert paths["preview_html"].exists()
