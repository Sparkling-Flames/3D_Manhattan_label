import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741_2d_guarded import (
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


def test_materializes_fail_closed_2d_guarded_refit(tmp_path):
    before = {path: _sha(path) for path in PROTECTED}
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    manual = json.loads(paths["manual_copy"].read_text(encoding="utf-8"))
    top = payload["top_candidate"]
    old = payload["rejected_diagnostic_reference"]

    assert all(path.exists() for path in paths.values())
    assert len(paths["summary"].read_text(encoding="utf-8").splitlines()) <= 80
    assert payload["rejected_candidate_id"] == "robust_all_long_edges"
    assert payload["rejected_by_2d_review"] is True
    assert old["recommendation_label"] in {"diagnostic_only", "suppress"}
    assert top["candidate_id"] != old["candidate_id"]
    assert top["source_pair_2_guard_passed"] is True
    assert top["source_pair_2_deltas"]["top_x"] <= 1.5
    assert top["source_pair_2_deltas"]["bottom_x"] <= 1.5
    assert abs(top["source_pair_2_deltas"]["top_y"]) <= 2.0
    assert abs(top["source_pair_2_deltas"]["bottom_y"]) <= 2.0
    assert top["right_half_top_y_guard_passed"] is True
    assert top["right_half_top_y_violations"] == []
    for source_id, limit in {7: 2.0, 9: 1.2, 10: 1.2, 11: 1.5, 12: 1.5}.items():
        assert top["top_y_changes_by_source_pair_id"][str(source_id)] >= -limit
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
    assert manual["rejected_old_candidate_reference"] == "robust_all_long_edges"
    assert len(manual["corrected_coordinates"]) == 12
    assert "robust_all_long_edges" not in json.dumps(
        manual["corrected_coordinates"]
    )
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
    assert "2D-guarded review only; no writeback; human must confirm." in overlay
    assert all(
        token in overlay
        for token in (
            "pair2Guard",
            "rightGuard",
            "chainA",
            "chainB",
            "heightReview",
            "onlyChanged",
        )
    )
    assert "local_3d_review.html" in review
    metrics = json.loads((tmp_path / "projection_metrics.json").read_text(encoding="utf-8"))
    assert {row["name"] for row in metrics["variants"]} >= {
        "original",
        "robust_all_long_edges",
        top["candidate_id"],
    }
    assert {path: _sha(path) for path in PROTECTED} == before
