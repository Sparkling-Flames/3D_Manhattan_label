import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_height_plane_preserving import (
    run,
)

PROTECTED = (
    Path("export_label/groudTruth.json"),
    Path("tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py"),
    Path("tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py"),
    Path("tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py"),
)
ORDER = [2, 1, 3, 4, 6, 5, 8, 7, 9, 10, 12, 11]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_materializes_height_plane_preserving_2d_constrained_review(tmp_path):
    before = {path: _sha(path) for path in PROTECTED}
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    manual = json.loads(paths["manual_copy"].read_text(encoding="utf-8"))
    top = payload["top_candidate"]
    refs = payload["rejected_diagnostic_references"]

    assert all(path.exists() for path in paths.values())
    assert len(paths["summary"].read_text(encoding="utf-8").splitlines()) <= 80
    assert refs["robust_all_long_edges"]["status"] == "rejected_by_2d_review"
    assert refs["s2_s11_height_pair_repair"]["status"] == (
        "rejected_by_human_3d_review"
    )
    assert top["source_pair_2_x_anchor_passed"] is True
    assert top["source_pair_2_x_delta_from_baseline"] <= 0.25
    assert top["source_pair_11_x_anchor_passed"] is True
    assert top["source_pair_11_x_delta_from_baseline"] <= 0.35
    assert "source_pair_11_height_residual_before" in top
    assert "source_pair_11_height_residual_after" in top
    assert abs(top["source_pair_11_height_residual_after"]) < 1e-8
    assert payload["bottom_y_direction_note"][
        "bottom_y_larger_means_point_lower_in_image"
    ] is True
    assert set(payload["bottom_y_sensitivity_screen"]) >= {
        "2",
        "5",
        "6",
        "7",
        "8",
    }
    assert payload["estimated_dominant_height_plane"] > 0
    assert top["height_plane_residual_l1"] >= 0
    assert top["height_outlier_count"] >= 0
    robust_residual = payload["reference_height_plane_metrics"][
        "robust_all_long_edges"
    ]["height_plane_residual_l1"]
    assert top["height_plane_residual_l1"] <= robust_residual + 1e-8
    assert top["chain_5_6_7_8_preserved"] is True
    assert top["chain_12_11_1_preserved"] is True
    assert top["order_preserved"] is True
    assert [row["source_pair_id"] for row in top["corrected_coordinates"]] == ORDER
    assert len(top["corrected_coordinates"]) == 12
    assert all(
        0 <= row[endpoint][axis] <= 100
        for row in top["corrected_coordinates"]
        for endpoint in ("top", "bottom")
        for axis in ("x", "y")
    )
    assert all(
        row["random_or_fixed_step_grid_used"] is False
        for row in payload["candidates"]
    )
    assert manual["candidate_id"] == top["candidate_id"]
    assert manual["previous_candidates_rejected_by_human_review"] is True
    assert manual["bottom_y_direction_note"][
        "bottom_y_larger_means_point_lower_in_image"
    ] is True
    assert len(manual["corrected_coordinates"]) == 12
    for field in (
        "accepted",
        "downstream_recommendation",
        "candidate_preference_authorized",
        "annotation_writeback",
        "annotation_patch_generated",
    ):
        assert payload[field] is False
        assert manual[field] is False
    overlay = paths["overlay"].read_text(encoding="utf-8")
    review = paths["review"].read_text(encoding="utf-8")
    assert all(
        token in overlay
        for token in (
            "s2 x anchor",
            "s11 x anchor",
            "bottom_y + means downward",
            "dominant height plane",
            "5–6–7–8 chain",
            "12–11–1 chain",
        )
    )
    assert "local_3d_review.html" in review
    metrics = json.loads((tmp_path / "projection_metrics.json").read_text(encoding="utf-8"))
    assert {row["name"] for row in metrics["variants"]} >= {
        "original",
        "robust_all_long_edges",
        "s2_s11_height_pair_repair",
        top["candidate_id"],
    }
    assert {path: _sha(path) for path in PROTECTED} == before
