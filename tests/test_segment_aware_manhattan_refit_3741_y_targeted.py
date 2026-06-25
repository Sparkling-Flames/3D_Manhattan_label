import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_y_targeted import (
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


def test_materializes_baseline_x_anchored_y_targeted_review(tmp_path):
    before = {path: _sha(path) for path in PROTECTED}
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    manual = json.loads(paths["manual_copy"].read_text(encoding="utf-8"))
    top = payload["top_candidate"]
    previous = payload["previous_candidate_reference"]

    assert all(path.exists() for path in paths.values())
    assert len(paths["summary"].read_text(encoding="utf-8").splitlines()) <= 80
    assert payload["previous_candidate_id"] == "pair2_anchored_height_clamped"
    assert payload["previous_candidate_status"] == (
        "partially_improved_but_rejected_by_human_review"
    )
    assert previous["recommendation_label"] == "diagnostic_only"
    assert top["candidate_id"] != payload["previous_candidate_id"]
    assert top["source_pair_2_x_anchor_passed"] is True
    assert top["source_pair_2_x_delta_from_baseline"] <= 0.35
    s2 = next(row for row in top["corrected_coordinates"] if row["source_pair_id"] == 2)
    assert s2["top"]["x"] == 5.889724310776942
    assert s2["bottom"]["x"] == 5.889724310776942
    assert top["source_pair_2_bottom_y_angle_repair_applied"] is True
    assert top["source_pair_2_bottom_y_delta"] != 0
    assert abs(top["source_pair_2_top_y_delta"]) <= 3.0
    assert abs(top["source_pair_2_bottom_y_delta"]) <= 1.0
    assert top["source_pair_11_top_y_priority_variable"] is True
    assert top["source_pair_11_x_anchor_passed"] is True
    assert isinstance(top["source_pair_1_as_sacrificial_adapter"], bool)
    assert top["source_pair_1_movement"] >= 0
    assert isinstance(top["source_pair_5_6_micro_adjustment_applied"], bool)
    assert set(top["source_pair_5_6_movement"]) == {"5", "6"}
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
    assert top["height_consistency_improved_vs_previous"] is True
    assert top["height_consistency_l1"] < payload["previous_height_consistency_l1"]
    assert all(
        row["random_or_fixed_step_grid_used"] is False
        for row in payload["candidates"]
    )
    micro = next(
        row
        for row in payload["candidates"]
        if row["candidate_id"] == "s2_s11_s5_s6_micro_height_repair"
    )
    assert all(value <= 1.2 for value in micro["source_pair_5_6_movement"].values())
    assert manual["candidate_id"] == top["candidate_id"]
    assert manual["previous_candidate_reference"] == "pair2_anchored_height_clamped"
    assert manual["previous_candidate_rejected_by_human_review"] is True
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
            "s2 baseline-x anchor",
            "s11 top_y review",
            "s1 sacrificial adapter",
            "s5/s6 micro adjustment",
            "5–6–7–8 chain",
            "12–11–1 chain",
            "9–10 height review",
        )
    )
    assert "local_3d_review.html" in review
    metrics = json.loads((tmp_path / "projection_metrics.json").read_text(encoding="utf-8"))
    assert {row["name"] for row in metrics["variants"]} >= {
        "original",
        "pair2_anchored_height_clamped",
        top["candidate_id"],
    }
    assert {path: _sha(path) for path in PROTECTED} == before
