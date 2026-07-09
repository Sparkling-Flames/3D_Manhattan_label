import json
from pathlib import Path

from tools.paper_a_manhattan.run_m_anchor_4_staged_vertical_height_solver import (
    ALLOWED_SOURCE_PAIR_IDS,
    PROTECTED_SOURCE_PAIR_IDS,
    TOP_K,
    run,
)


def test_m_anchor_4_materializes_staged_review_candidates(tmp_path: Path) -> None:
    paths = run(tmp_path / "m4", tmp_path / "review")

    payload = json.loads(paths["audit"].read_text(encoding="utf-8"))
    authorization = json.loads(paths["authorization"].read_text(encoding="utf-8"))

    assert payload["schema_version"] == "m_anchor_4_staged_vertical_height_solver_audit_v1"
    assert authorization["allowed_source_pair_ids"] == list(ALLOWED_SOURCE_PAIR_IDS)
    assert authorization["protected_source_pair_ids"] == list(PROTECTED_SOURCE_PAIR_IDS)
    assert 0 < payload["candidate_count"] <= TOP_K
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["candidate_preference_authorized"] is False
    assert payload["annotation_writeback"] is False

    for card in payload["candidate_cards"]:
        assert set(card["changed_pairs"]) <= set(ALLOWED_SOURCE_PAIR_IDS)
        assert not (set(card["changed_pairs"]) & set(PROTECTED_SOURCE_PAIR_IDS))
        assert card["hard_gate"]["protected_pair_3_unchanged"] is True
        assert card["hard_gate"]["vertical_wall_x_residual_zero"] is True
        assert card["wall_residual_max_after_footprint"] < card["wall_residual_max_before"]
        assert card["wall_residual_sum_after_footprint"] < card["wall_residual_sum_before"]
        assert card["height_l1_after_height"] < card["height_l1_before"]
        assert len(card["per_wall_residual_diagnostic"]["walls"]) == 12
        assert card["decision"] == "review_available"
        assert card["accepted"] is False
        assert card["downstream_recommendation"] is False
        assert card["annotation_writeback"] is False
        for change in card["coordinate_changes"]:
            assert change["source_pair_id"] in ALLOWED_SOURCE_PAIR_IDS
            assert change["source_pair_id"] not in PROTECTED_SOURCE_PAIR_IDS

    manifest = json.loads(paths["review_manifest"].read_text(encoding="utf-8"))
    assert len(manifest["candidates"]) == payload["candidate_count"]
    assert manifest["safety_boundary"]["annotation_writeback"] is False
    assert all(candidate["required_wall_residuals"] for candidate in manifest["candidates"])

    html = paths["review_html"].read_text(encoding="utf-8")
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
    assert "m_anchor_4_candidate" in html

    review_blob = html.split("const REVIEW = ", 1)[1].split(";\n", 1)[0]
    review_data = json.loads(review_blob)
    assert len(review_data["variants"]) == payload["candidate_count"] + 1
    assert all(variant["overlayPairs"] for variant in review_data["variants"])
