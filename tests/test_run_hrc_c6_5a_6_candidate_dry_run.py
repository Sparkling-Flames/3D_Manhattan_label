import json

from tools.paper_a_manhattan.run_hrc_c6_5a_6_candidate_dry_run import (
    CASE_NAME,
    build_payload,
    run,
)


def test_candidate_dry_run_uses_corrected_four_pair_source():
    payload = build_payload()
    assert payload["case_name"] == CASE_NAME
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
    changes = [
        row["coordinate_changes"][0]["fields"] for row in payload["candidate_set"]
    ]
    assert changes[0]["top_x"]["delta"] == changes[0]["bottom_x"]["delta"] == -0.75
    assert changes[1]["top_y"]["delta"] == changes[1]["bottom_y"]["delta"] == 0.75
    assert changes[2]["top_y"]["delta"] == changes[2]["bottom_y"]["delta"] == -0.75
    assert len({json.dumps(row, sort_keys=True) for row in changes}) == 3


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
    preview = json.loads(paths["preview_json"].read_text(encoding="utf-8"))
    assert payload["candidate_count"] == 3
    assert len(preview["variants"]) == 4
    assert paths["preview_html"].exists()
