import copy
import json
import re
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_local_3d_projection_review import (
    REPO_ROOT,
    REVIEW_SCHEMA_VERSION,
    SAFETY_BOUNDARY,
    _build_review_asset_urls,
    _inspection_metadata,
    _windows_launcher_text,
    apply_m1522_candidate,
    apply_candidate_row,
    build_projection_variant,
    extract_m1522_candidate_rows,
    extract_ordered_pairs,
    resolve_local_image,
    run_local_review,
)
from tools.paper_a_manhattan.serve_local_3d_projection_review import (
    _within,
    build_server,
)
from tools.paper_a_manhattan.run_single_image_manhattan_assist import TOOL_VERSION


def _ordered_pairs():
    return [
        {"top": {"x": 10.0, "y": 20.0}, "bottom": {"x": 10.3, "y": 80.0}},
        {"top": {"x": 35.0, "y": 20.0}, "bottom": {"x": 35.0, "y": 80.0}},
        {"top": {"x": 60.0, "y": 20.0}, "bottom": {"x": 60.0, "y": 80.0}},
        {"top": {"x": 85.0, "y": 20.0}, "bottom": {"x": 85.0, "y": 80.0}},
    ]


def _candidate_row():
    return {
        "effective_pair_index": 1,
        "source_preview_order_index": 2,
        "probe_mode": "align_then_translate_column",
        "recommendation_eligible": True,
        "top_x_before": 10.0,
        "bottom_x_before": 10.3,
        "top_x_after": 10.5,
        "bottom_x_after": 10.5,
        "top_y_before": 20.0,
        "bottom_y_before": 80.0,
        "top_y_after": 20.0,
        "bottom_y_after": 80.0,
        "vertical_x_residual_before": 0.3,
        "vertical_x_residual_after": 0.0,
        "dense_pair_indices": [1, 2],
    }


def test_candidate_application_is_copy_only_and_aligns_column():
    original = _ordered_pairs()
    frozen = copy.deepcopy(original)
    candidate = apply_candidate_row(original, _candidate_row())

    assert original == frozen
    assert candidate[0]["top"]["x"] == candidate[0]["bottom"]["x"] == 10.5
    assert candidate[0]["source_preview_order_index"] == 2
    assert [row["top"]["x"] for row in candidate[1:]] == [35.0, 60.0, 85.0]


def test_asset_urls_use_the_consumer_document_or_server_root(tmp_path):
    root = tmp_path / "repo"
    viewer = root / "tools" / "label_studio" / "vis_3d.html"
    image = root / "data" / "mp3d_layout" / "img_v" / "pano.jpg"
    out_dir = root / "analysis_results" / "review" / "case"
    viewer.parent.mkdir(parents=True)
    image.parent.mkdir(parents=True)
    out_dir.mkdir(parents=True)
    viewer.write_text("viewer", encoding="utf-8")
    image.write_bytes(b"image")

    root_viewer_url, root_image_url = _build_review_asset_urls(
        viewer_path=viewer,
        resolved_image=image,
        out_dir=out_dir,
        local_server_root=root,
    )
    assert root_viewer_url == "/tools/label_studio/vis_3d.html"
    assert root_image_url == "/data/mp3d_layout/img_v/pano.jpg"

    file_viewer_url, file_image_url = _build_review_asset_urls(
        viewer_path=viewer,
        resolved_image=image,
        out_dir=out_dir,
        local_server_root=None,
    )
    assert file_viewer_url == "../../../tools/label_studio/vis_3d.html"
    assert file_image_url == "../../data/mp3d_layout/img_v/pano.jpg"


def test_local_launcher_is_portable_and_server_is_loopback_only(tmp_path):
    output = REPO_ROOT / "analysis_results" / "paper_a_manhattan" / "local_3d_projection" / "case"
    launcher = _windows_launcher_text(output, output / "local_3d_review.html")
    assert "serve_local_3d_projection_review.py" in launcher
    assert '--repo-root "%REPO_ROOT%"' in launcher
    assert "analysis_results\\paper_a_manhattan\\local_3d_projection\\case\\local_3d_review.html" in launcher
    assert str(REPO_ROOT) not in launcher

    root = tmp_path / "repo"
    root.mkdir()
    review = root / "review.html"
    review.write_text("review", encoding="utf-8")
    assert _within(review, root) == review.resolve()
    with pytest.raises(ValueError, match="outside repository root"):
        _within(tmp_path / "outside.html", root)
    with pytest.raises(ValueError, match="127.0.0.1"):
        build_server(repo_root=root, host="0.0.0.0", port=0)
    server = build_server(repo_root=root, port=0)
    try:
        assert server.server_address[0] == "127.0.0.1"
        assert server.server_address[1] > 0
    finally:
        server.server_close()


def test_inspection_metadata_has_authoritative_corner_wall_and_issue_metrics():
    variant = build_projection_variant(
        "original",
        _ordered_pairs(),
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        camera_height=1.6,
    )
    inspection = _inspection_metadata(variant)

    assert inspection["schema_version"] == "local_3d_inspection_m15_19_2_v1"
    assert inspection["pairs"][0]["floor_3d"] == variant["projection"]["pairs"][0]["floor_3d"]
    pair = inspection["pairs"][0]
    assert pair["previous_wall_index"] == 4
    assert pair["next_wall_index"] == 1
    assert pair["junction_angle_deg"] is not None
    assert pair["junction_residual_to_90_deg"] is not None
    assert pair["junction_angle_kind"] == "unsigned_smaller_floorprint_angle_0_180"
    wall = inspection["walls"][0]
    assert wall["direction_deg"] is not None
    assert wall["angle_residual_deg"] is not None
    assert "adjacent_corner_angles" not in wall
    assert inspection["issues"] == sorted(
        inspection["issues"], key=lambda row: (row["priority"], -row["severity"])
    )


def test_local_image_resolver_explicit_path_has_priority(tmp_path):
    root = tmp_path / "images"
    root.mkdir()
    rooted = root / "source.jpg"
    rooted.write_bytes(b"rooted")
    explicit = tmp_path / "explicit.jpg"
    explicit.write_bytes(b"explicit")
    payload = {"source_image": "https://example.invalid/source.jpg"}

    info, resolved = resolve_local_image(
        payload, image_root=root, image_path=explicit
    )
    assert resolved == explicit.resolve()
    assert info["resolution_method"] == "explicit_image_path"
    assert info["image_path"] == "explicit.jpg"
    assert info["network_access_used"] is False

    root_info, root_resolved = resolve_local_image(payload, image_root=root)
    assert root_resolved == rooted.resolve()
    assert root_info["resolution_method"] == "image_root_basename"


def test_missing_image_still_generates_geometry_only_outputs(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "ordered_pairs": _ordered_pairs(),
                "source_image": "https://example.invalid/missing.jpg",
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "review"
    paths = run_local_review(
        input_path=input_path,
        out_dir=out_dir,
        image_root=tmp_path / "missing-root",
        coordinate_mode="auto",
    )

    assert all(path.is_file() for path in paths.values())
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == REVIEW_SCHEMA_VERSION
    assert payload["input_provenance"]["image"]["image_exists"] is False
    assert "texture unavailable" in paths["html"].read_text(encoding="utf-8").lower()
    assert "--coordinate-mode ls_percent" in paths["report"].read_text(encoding="utf-8")


def test_candidate_metrics_and_static_html_contract(tmp_path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    image = image_root / "pano.jpg"
    image.write_bytes(b"local panorama fixture")
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "ordered_pairs": _ordered_pairs(),
                "source_image": "https://example.invalid/pano.jpg",
            }
        ),
        encoding="utf-8",
    )
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(
        json.dumps(
            {
                "pair_index_mapping": [
                    {"effective_pair_index": 1, "source_preview_order_index": 2}
                ],
                "verified_3d_local_assist": {
                    "local_dense_corner_probe_rows": [_candidate_row()]
                },
            }
        ),
        encoding="utf-8",
    )
    paths = run_local_review(
        input_path=input_path,
        candidate_json=candidate_path,
        image_root=image_root,
        out_dir=tmp_path / "review",
        coordinate_mode="ls_percent",
    )

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == REVIEW_SCHEMA_VERSION
    assert [variant["name"] for variant in payload["variants"]] == [
        "original",
        "candidate_1",
    ]
    candidate = payload["variants"][1]
    assert candidate["candidate_row"]["top_x_after"] == candidate["candidate_row"]["bottom_x_after"]
    assert "delta_from_original" in candidate
    assert candidate["metric_comparison"]["wall_residual_sum_deg"].keys() == {
        "before",
        "after",
        "delta",
    }
    assert candidate["metric_comparison"]["pair_vertical_x_residual"] == {
        "before": 0.3,
        "after": 0.0,
        "delta": pytest.approx(-0.3),
    }
    assert candidate["summary"]["minimum_dense_floor_3d_separation"] is not None
    assert candidate["summary"]["vertical_x_residual_sum"] < payload["variants"][0]["summary"]["vertical_x_residual_sum"]
    assert payload["local_review_assets"]["file"]["embed"]["embedded"] is True

    page = paths["html"].read_text(encoding="utf-8")
    lower = page.lower()
    assert "vis_3d.html" in page
    assert "postMessage" in page
    assert "update_layout" in page
    assert "Hide labels" in page and "Show labels" in page
    assert "hohonet_texture_status" in page
    assert "texture_load_status" in page
    assert "image_url_for_viewer" in page
    assert "viewer_url" in page
    assert "texture_expected" in page
    assert "texture_status_timeout" in page
    assert "--coordinate-mode ls_percent" in page
    assert "data:image/jpeg;base64," in page
    assert "hohonet_viewer_ready" in page
    assert "hohonet_geometry_selection" in page
    assert "hohonet_measurement_status" in page
    assert "inspectionMode: true" in page
    assert "Ghost original" in page and "Measure" in page
    assert "Residual edges" not in page
    assert "M15.22 triage" in page
    assert "Next issue" in page and 'data-camera="top"' in page
    assert "junction_angle_kind" in page
    assert "adjacent_corner_angles" not in page
    assert '<iframe id="left-view" title="selected geometry"></iframe>' in page
    for forbidden in (
        "fetch(",
        "label studio api",
        "writeback",
        "annotation patch",
        "submit",
        "routing",
        "formal_g_t",
    ):
        assert forbidden not in lower


def test_m1523_bridge_applies_ranked_multi_pair_candidates(tmp_path):
    input_path = REPO_ROOT / (
        "analysis_results/paper_a_manhattan/single_image_manual_test/"
        "latest_gt_checked/task218_ann3741_m1516_stabilized_input.json"
    )
    candidate_path = REPO_ROOT / (
        "analysis_results/paper_a_manhattan/local_candidate_search/"
        "task218_ann3741/candidate_search.json"
    )
    candidate_payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    rows = extract_m1522_candidate_rows(candidate_payload, limit=5)

    assert len(rows) == 5
    assert all(not row["hard_gate"] for row in rows)
    assert all(not row["assertion_violations"] for row in rows)
    multi = next(row for row in rows if len(row["coordinate_changes"]) > 1)
    pairs, _ = extract_ordered_pairs(json.loads(input_path.read_text(encoding="utf-8")))
    frozen = copy.deepcopy(pairs)
    applied = apply_m1522_candidate(pairs, multi)
    assert pairs == frozen
    for change in multi["coordinate_changes"]:
        pair = next(
            item
            for item in applied
            if int(item["effective_pair_index"]) == int(change["effective_pair_index"])
        )
        for field, values in change["fields"].items():
            endpoint, axis = field.split("_")
            assert pair[endpoint][axis] == pytest.approx(float(values["after"]))

    paths = run_local_review(
        input_path=input_path,
        candidate_json=candidate_path,
        candidate_limit=5,
        out_dir=tmp_path / "review",
        coordinate_mode="ls_percent",
    )
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["input_provenance"]["candidate"]["source"] == "m15_22_candidate_search_json"
    assert [row["name"] for row in payload["variants"]] == [
        "original",
        *[row["candidate_id"] for row in rows[:5]],
    ]
    assert payload["variants"][1]["candidate_row"]["decision_class"]

    page = paths["html"].read_text(encoding="utf-8")
    assert rows[0]["family"] in page
    assert "decision_class" in page and "direct_ls_trial_allowed" in page
    assert "variant.displayName" in page
    assert "let ghostVisible = true" in page
    assert "Residual edges" not in page
    assert "heatmap" not in page
    assert "PARTIAL DIAGNOSTIC ONLY — do not apply directly in LS." in page
    review = json.loads(re.search(r"const REVIEW = (.*);", page).group(1))
    variants = {variant["name"]: variant for variant in review["variants"]}
    assert variants["original"]["changedWallIndices"] == []
    assert variants["candidate_2"]["changedPairIndices"] == [5, 6, 7]
    assert variants["candidate_2"]["changedWallIndices"] == [4, 5, 6, 7]
    assert variants["candidate_5"]["changedPairIndices"] == [5]
    assert variants["candidate_5"]["changedWallIndices"] == [4, 5]

    viewer = (REPO_ROOT / "tools/label_studio/vis_3d.html").read_text(encoding="utf-8")
    assert "displayOptions.heatmap" not in viewer
    assert "const residualEdges = new THREE.LineSegments" not in viewer
    assert "const overlay = new THREE.Mesh" not in viewer
    assert "wallColor(" not in viewer
    assert "0xa855f7" not in viewer
    assert "0xf97316" not in viewer
    assert "changedPairIndices" in viewer and "changedWallIndices" in viewer
    assert "inspectionState.enabled && changedWallSet.size" in viewer
    assert "color: 0x00ff00" in viewer
    assert "new THREE.SphereGeometry(0.12" in viewer
    assert "0xff2d95" in viewer
    assert "color: 0xffffff" in viewer and "opacity: 0.95" in viewer
    assert "changedWallLine.computeLineDistances()" in viewer
    assert "LineDashedMaterial({ color:0xe5e7eb" in viewer
    assert "new THREE.MeshBasicMaterial({ color: 0xfacc15" in viewer


def test_safety_regression_keeps_m1518_and_formal_boundaries():
    assert TOOL_VERSION == "single_image_manhattan_assist_m15_18_3_v1"
    assert SAFETY_BOUNDARY["annotation_write_allowed"] is False
    assert SAFETY_BOUNDARY["annotation_patch_generated"] is False
    assert SAFETY_BOUNDARY["automatic_optimization"] is False
    assert SAFETY_BOUNDARY["automatic_reorder_merge_delete"] is False
    assert SAFETY_BOUNDARY["worker_facing"] is False
    assert SAFETY_BOUNDARY["formal_artifact"] is False
