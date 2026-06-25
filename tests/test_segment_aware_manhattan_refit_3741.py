import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_aware_manhattan_refit_3741 import run
from tools.paper_a_manhattan.segment_aware_manhattan_refit import (
    SOURCE_PAIR_TO_SOLVER_POSITION,
    VERIFIED_ORDER_SOURCE_IDS,
    solver_position_for_source_pair,
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
    assert payload["verified_order_source_ids"] == VERIFIED_ORDER_SOURCE_IDS
    assert payload["source_pair_to_solver_position"]["2"] == 1
    assert payload["source_pair_to_solver_position"]["1"] == 2
    assert payload["solver_position_to_verified_order_source_id"]["1"] == 2
    assert payload["solver_position_to_verified_order_source_id"]["2"] == 1
    assert len(payload["corrected_coordinates"]) == 12
    corrected = payload["corrected_coordinates"]
    assert [row["source_pair_id"] for row in corrected] == VERIFIED_ORDER_SOURCE_IDS
    assert [row["solver_position"] for row in corrected] == list(range(1, 13))
    assert corrected[0]["source_pair_id"] == 2
    assert corrected[0]["solver_position"] == 1
    assert corrected[1]["source_pair_id"] == 1
    assert corrected[1]["solver_position"] == 2
    segments = payload["segment_definitions_by_source_pair_id"]
    assert segments["strong_anchor_segment"]["source_pair_ids"] == [3, 4]
    assert segments["complex_short_wall_chain_A"]["source_pair_ids"] == [5, 6, 7, 8]
    assert segments["complex_short_wall_chain_B"]["source_pair_ids"] == [12, 11, 1]
    assert segments["suspect_skew_segment"]["low_confidence_source_pair_id"] == 2
    assert payload["observation_weights_by_source_pair_id"]["2"] == 0.25
    assert "verified_order" not in payload
    assert "segment_definitions" not in payload
    assert "observation_weights" not in payload
    deltas = payload["before_after_delta"]
    assert deltas[0]["source_pair_id"] == 2
    assert deltas[0]["solver_position"] == 1
    assert deltas[1]["source_pair_id"] == 1
    assert deltas[1]["solver_position"] == 2
    movement_by_source = {
        row["source_pair_id"]: row for row in top["movement_by_source_pair_id"]
    }
    assert metrics["suspect_source_pair_2_solver_position"] == 1
    assert (
        metrics["suspect_source_pair_2_movement"]
        == movement_by_source[2]["max"]
    )
    assert "suspect_point_2_movement" not in metrics
    assert all(
        set(line) >= {"source_edge_ids", "solver_edge_positions"}
        for line in top["wall_lines"]
    )
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
    candidate_manifest = json.loads(
        (tmp_path / "_review_candidate.json").read_text(encoding="utf-8")
    )["candidates"][0]
    assert candidate_manifest["id_semantics"]["effective_pair_index"].endswith(
        "solver_position"
    )
    assert candidate_manifest["changed_pair_indices_semantics"].startswith(
        "deprecated"
    )
    report = (tmp_path / "projection_review_report.md").read_text(encoding="utf-8")
    assert "source pair 2 (solver position 1)" in report
    projection = json.loads(
        (tmp_path / "projection_metrics.json").read_text(encoding="utf-8")
    )
    for variant in projection["variants"]:
        assert [
            row["source_preview_order_index"]
            for row in variant["projection"]["pairs"]
        ] == VERIFIED_ORDER_SOURCE_IDS
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
        point_ids_by_source_pair_id={
            index: {"top_id": f"t{index}", "bottom_id": f"b{index}"}
            for index in range(1, 13)
        },
        reprojection_fn=None,
    )
    assert result["fail_closed"] is True
    assert result["corrected_coordinates"] is None
    assert result["suppress_reasons"] == ["missing_projection_converter"]


def test_source_pair_id_two_resolves_to_solver_position_one():
    assert VERIFIED_ORDER_SOURCE_IDS[:4] == [2, 1, 3, 4]
    assert SOURCE_PAIR_TO_SOLVER_POSITION[2] == 1
    assert SOURCE_PAIR_TO_SOLVER_POSITION[1] == 2
    assert solver_position_for_source_pair(2) == 1
