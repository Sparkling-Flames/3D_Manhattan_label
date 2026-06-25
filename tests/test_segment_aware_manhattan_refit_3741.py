import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741 import run
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    VERIFIED_ORDER,
    solve_segment_aware_refit,
)


PROTECTED_CODE = (
    Path("tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py"),
    Path("tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py"),
    Path("tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py"),
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_runner_materializes_complete_review_only_refit(tmp_path):
    gt_before = _sha(Path("export_label/groudTruth.json"))
    protected_before = {path: _sha(path) for path in PROTECTED_CODE}
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    manual = json.loads(paths["manual_copy"].read_text(encoding="utf-8"))
    top = payload["top_candidate"]
    metrics = top["metrics"]

    assert all(paths[name].exists() for name in ("json", "summary", "review", "manual_copy"))
    assert len(paths["summary"].read_text(encoding="utf-8").splitlines()) <= 80
    review_html = paths["review"].read_text(encoding="utf-8")
    assert all(
        label in review_html
        for label in ("strong anchor: 3–4", "suspect: 2", "chain A: 5–6–7–8", "chain B: 12–11–1")
    )
    assert payload["verified_order"] == VERIFIED_ORDER
    assert len(payload["corrected_coordinates"]) == 12
    assert [row["source_preview_order_index"] for row in payload["corrected_coordinates"]] == VERIFIED_ORDER
    assert payload["segment_definitions"]["strong_anchor_segment"]["pairs"] == [3, 4]
    assert payload["segment_definitions"]["complex_short_wall_chain_A"]["pairs"] == [5, 6, 7, 8]
    assert payload["segment_definitions"]["complex_short_wall_chain_B"]["pairs"] == [12, 11, 1]
    assert payload["segment_definitions"]["suspect_skew_segment"]["low_confidence_pair"] == 2
    assert metrics["chain_5_6_7_8_preserved"] is True
    assert metrics["chain_12_11_1_preserved"] is True
    assert metrics["fitted_from_wall_line_intersections"] is True
    assert metrics["random_or_grid_perturbation_used"] is False
    assert metrics["self_intersection"] is False
    assert metrics["order_preserved"] is True
    assert manual["human_must_confirm"] is True
    assert manual["accepted"] is False
    assert manual["downstream_recommendation"] is False
    assert manual["candidate_preference_authorized"] is False
    assert manual["annotation_writeback"] is False
    assert manual["annotation_patch_generated"] is False
    assert len(manual["corrected_coordinates"]) == 12
    assert "local_score_total" not in paths["json"].read_text(encoding="utf-8")
    assert _sha(Path("export_label/groudTruth.json")) == gt_before
    assert {path: _sha(path) for path in PROTECTED_CODE} == protected_before


def test_direction_variants_are_deterministic_wall_line_intersections(tmp_path):
    first = json.loads(run(tmp_path / "first")["json"].read_text(encoding="utf-8"))
    second = json.loads(run(tmp_path / "second")["json"].read_text(encoding="utf-8"))
    assert first["top_candidate_id"] == second["top_candidate_id"]
    assert len(first["direction_variants"]) <= 3
    assert [row["variant_id"] for row in first["direction_variants"]] == [
        "anchor_34_dominant",
        "anchor_34_plus_910",
        "robust_all_long_edges",
    ]
    assert first["corrected_coordinates"] == second["corrected_coordinates"]
    assert all(
        row["metrics"]["random_or_grid_perturbation_used"] is False
        for row in first["direction_variants"]
    )


def test_missing_reprojection_converter_fails_closed():
    pairs = [
        {
            "top": {"x": float(index), "y": 25.0},
            "bottom": {"x": float(index), "y": 75.0},
        }
        for index in range(1, 13)
    ]
    result = solve_segment_aware_refit(
        pairs,
        point_ids={
            index: {"top_id": f"t{index}", "bottom_id": f"b{index}"}
            for index in range(1, 13)
        },
        reprojection_fn=None,
    )
    assert result["fail_closed"] is True
    assert result["corrected_coordinates"] is None
    assert result["suppress_reasons"] == ["missing_projection_converter"]
