import json
from pathlib import Path

from tools.paper_a_manhattan.run_m_anchor_3b_local_3d_review import (
    DEFAULT_AUDIT_PATH,
    build_bridge_manifest,
    run,
)


def test_m_anchor_3b_bridge_manifest_uses_reviewed_m1_candidate_baseline() -> None:
    manifest = build_bridge_manifest(DEFAULT_AUDIT_PATH)

    assert manifest["schema_version"] == "m_anchor_3b_local_3d_review_bridge_v1"
    assert manifest["case_name"] == "task218_ann3741_m_anchor_3b"
    assert len(manifest["ordered_pairs"]) == 12
    assert len(manifest["candidates"]) == 5
    assert manifest["input_provenance"]["review_baseline_candidate"]["candidate_id"] == (
        "m_anchor_1_footprint_only_joint_xy"
    )
    assert manifest["safety_boundary"]["accepted"] is False
    assert manifest["safety_boundary"]["downstream_recommendation"] is False
    assert manifest["safety_boundary"]["annotation_writeback"] is False
    assert manifest["safety_boundary"]["ranking_entry_allowed"] is False

    for candidate in manifest["candidates"]:
        assert candidate["decision_class"] == "review_available"
        assert candidate["accepted"] is False
        assert candidate["downstream_recommendation"] is False
        assert candidate["candidate_preference_authorized"] is False
        assert candidate["annotation_writeback"] is False
        assert candidate["coordinate_changes"]
        for change in candidate["coordinate_changes"]:
            assert set(change["fields"]) == {"bottom_y"}
            assert change["source_pair_id"] in {5, 6, 7, 8}


def test_m_anchor_3b_local_3d_review_materializes_hypothesis_style_outputs(
    tmp_path: Path,
) -> None:
    paths = run(DEFAULT_AUDIT_PATH, tmp_path)

    expected = {"json", "report", "html", "bridge_manifest"}
    assert expected <= set(paths)
    for path in paths.values():
        assert path.exists()

    html = paths["html"].read_text(encoding="utf-8")
    assert "M15.23.7 Scrollable Flexible Compare Grid" in html
    assert "Focus 2D/3D Review" in html
    assert "open-2d-review" in html
    assert "focus-review" in html
    assert "focus-stage" in html
    assert "focus-drag-handle" in html
    assert "focus-resize-handle" in html
    assert "focus-coordinate-readout" in html
    assert "focus-2d-viewbox" in html
    assert "renderFocus2DOverlay" in html
    assert "setFocusReviewOpen" in html
    assert "placementFromPointer" in html
    assert "resizeFocusFromPointer" in html
    assert "sizeFocus2DViewbox" in html
    assert "aspect-ratio:2/1" in html
    assert "overlay-layout" not in html
    assert "panel-2d" not in html
    assert "image-overlay-review" not in html
    assert "pointToLsPercent" in html
    assert "nearestEndpoint" in html
    assert "source_pair_id" in html
    assert "solver_position" in html
    assert "m_anchor_3b_candidate_0016" in html

    metrics = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert metrics["case_name"] == "task218_ann3741_m_anchor_3b"
    assert [variant["name"] for variant in metrics["variants"]][:2] == [
        "original",
        "m_anchor_3b_candidate_0016",
    ]
    assert len(metrics["variants"]) == 6
    assert metrics["safety_boundary"]["annotation_write_allowed"] is False
    assert metrics["safety_boundary"]["annotation_patch_generated"] is False

    review_blob = html.split("const REVIEW = ", 1)[1].split(";\n", 1)[0]
    review_data = json.loads(review_blob)
    assert review_data["variants"][0]["overlayPairs"]
    assert {"source_pair_id", "solver_position"} <= set(
        review_data["variants"][0]["overlayPairs"][0]
    )

    bridge = json.loads(paths["bridge_manifest"].read_text(encoding="utf-8"))
    changed_fields = {
        field
        for candidate in bridge["candidates"]
        for change in candidate["coordinate_changes"]
        for field in change["fields"]
    }
    assert changed_fields == {"bottom_y"}
