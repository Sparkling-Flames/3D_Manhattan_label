import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_joint_xy_search import (
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


def test_materializes_bounded_deterministic_joint_xy_search(tmp_path):
    before = {path: _sha(path) for path in PROTECTED}
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    manual = json.loads(paths["manual_copy"].read_text(encoding="utf-8"))
    top = payload["top_candidate"]

    assert all(path.exists() for path in paths.values())
    assert len(paths["summary"].read_text(encoding="utf-8").splitlines()) <= 100
    assert payload["search_budget"] >= payload["evaluated_count"]
    assert payload["evaluated_count"] > 1000
    assert payload["kept_count"] + payload["suppressed_count"] == payload["evaluated_count"]
    assert payload["random_seed_used"] is False
    assert len(payload["action_family_counts"]) >= 5
    assert abs(top["source_pair_2_x_delta_from_baseline"]) <= 0.45
    assert abs(top["source_pair_11_x_delta_from_baseline"]) <= 0.45
    if top["source_pair_2_bottom_y_downward_adjustment_applied"]:
        assert top["source_pair_2_bottom_y_delta_from_baseline"] > 0
    assert "source_pair_2_x_compensation_applied" in top
    assert "source_pair_11_x_compensation_applied" in top
    assert top["objective_breakdown"]["height_plane_is_soft_regularizer"] is True
    assert len(top["objective_breakdown"]) > 2
    refs = payload["rejected_diagnostic_references"]
    assert refs["robust_all_long_edges"]["status"] == "rejected_by_2d_review"
    assert refs["height_plane_preserved_s2_s11_s1_adapter"]["status"] == (
        "rejected_by_human_2d_review"
    )
    assert [row["source_pair_id"] for row in top["corrected_coordinates"]] == ORDER
    assert len(top["corrected_coordinates"]) == 12
    assert all(
        0 <= row[endpoint][axis] <= 100
        for row in top["corrected_coordinates"]
        for endpoint in ("top", "bottom")
        for axis in ("x", "y")
    )
    assert top["chain_5_6_7_8_preserved"] is True
    assert top["chain_12_11_1_preserved"] is True
    assert manual["candidate_id"] == top["candidate_id"]
    assert manual["previous_candidates_rejected"] is True
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
            "bottom_y arrows",
            "x compensation arrows",
            "s2/s11 guard bands",
            "chain 5–6–7–8",
            "chain 12–11–1",
            "only changed points",
        )
    )
    assert "local_3d_review.html" in review
    metrics = json.loads((tmp_path / "projection_metrics.json").read_text(encoding="utf-8"))
    assert {row["name"] for row in metrics["variants"]} >= {
        "original",
        "robust_all_long_edges",
        "height_plane_preserved_s2_s11_s1_adapter",
        top["candidate_id"],
    }
    assert {path: _sha(path) for path in PROTECTED} == before
