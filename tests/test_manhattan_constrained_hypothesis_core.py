from copy import deepcopy
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
    evaluate_hypothesis,
)
from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import (
    build_hypothesis_portfolio,
)


def _pairs():
    return [
        {
            "effective_pair_index": index,
            "top": {"x": index * 10.0, "y": 20.0},
            "bottom": {"x": index * 10.0, "y": 80.0},
        }
        for index in range(1, 5)
    ]


def _variant(*, short_edges=(), lengths=None, self_intersection=False, evidence=None, warnings=None, warning_codes=None):
    lengths = lengths or {}
    walls = []
    for left, right, residual in ((1, 2, 3.0), (2, 3, 8.0), (3, 4, 18.0), (4, 1, 5.0)):
        name = f"{left}-{right}"
        length = lengths.get(name, 0.4)
        walls.append(
            {
                "from_pair": left,
                "to_pair": right,
                "floor_wall_length": length,
                "short_wall_threshold": 0.2,
                "short_wall": name in short_edges,
                "angle_residual_deg": residual,
            }
        )
    heights = [
        {"effective_pair_index": index, "wall_height": value}
        for index, value in enumerate((2.8, 2.82, 2.81, 3.2), 1)
    ]
    projection_pairs = [
        {"effective_pair_index": index, "top_bottom_x_residual": 0.0}
        for index in range(1, 5)
    ]
    result = {
        "metrics": {
            "floorprint": {"walls": walls, "self_intersection": self_intersection},
            "corner_turns": {
                "corners": [
                    {"angle_to_90_residual_deg": value} for value in (2.0, 4.0, 6.0, 8.0)
                ]
            },
            "heights": {"pairs": heights},
        },
        "projection": {
            "pairs": projection_pairs,
            "warnings": list(warnings or []),
            **({"warning_codes": list(warning_codes)} if warning_codes is not None else {}),
        },
    }
    if evidence is not None:
        result["evidence"] = evidence
    return result


def _evaluate(candidate_pairs=None, candidate_variant=None, *, contract=None, legacy=7.5):
    baseline_pairs = _pairs()
    return evaluate_hypothesis(
        _variant(short_edges={"2-3"}, lengths={"2-3": 0.15}),
        candidate_variant or _variant(short_edges={"2-3"}, lengths={"2-3": 0.15}),
        baseline_pairs,
        candidate_pairs or deepcopy(baseline_pairs),
        contract
        or build_case_contract(
            baseline_pairs,
            {"protected_pairs": [1], "keep_distinct_pairs": [[2, 3]], "allowed_short_edges": ["2-3"]},
        ),
        {"local_score_total": legacy},
    )


def test_hard_constraint_failure_is_a_gate_not_a_penalty():
    candidate = _pairs()
    candidate[0]["top"]["x"] += 1.0
    evaluation = _evaluate(candidate_pairs=candidate)
    assert evaluation["feasibility"]["hard_gate_passed"] is False
    assert "protected_pairs_not_moved" in evaluation["feasibility"]["hard_failure_reasons"]
    assert build_hypothesis_ranking_key(evaluation)[0] is True


def test_evidence_unavailable_and_legacy_score_are_diagnostic_only():
    evaluation = _evaluate()
    assert evaluation["evidence_consistency"]["evidence_status"] == "unavailable"
    assert evaluation["evidence_consistency"]["missing_fields"]
    assert evaluation["local_score_total"] == 7.5
    assert evaluation["legacy_score_role"] == "diagnostic_only"


def test_short_wall_existing_new_and_collapsed_are_distinct():
    candidate_variant = _variant(
        short_edges={"2-3", "3-4"},
        lengths={"2-3": 0.15, "3-4": 0.1},
    )
    evaluation = _evaluate(candidate_variant=candidate_variant)
    plausibility = evaluation["layout_plausibility"]
    assert plausibility["existing_short_wall_preserved"] == ["2-3"]
    assert plausibility["new_short_wall_created"] == ["3-4"]
    assert plausibility["short_wall_collapsed"] == []

    collapsed = _evaluate(
        candidate_variant=_variant(short_edges={"2-3"}, lengths={"2-3": 0.01})
    )
    assert collapsed["layout_plausibility"]["short_wall_collapsed"] == ["2-3"]
    assert collapsed["feasibility"]["hard_gate_passed"] is False


def test_portfolio_suppresses_hard_failures_and_populates_every_bucket():
    good = _evaluate(legacy=9999.0)
    bad_pairs = _pairs()
    bad_pairs[0]["top"]["y"] = 90.0
    bad = _evaluate(candidate_pairs=bad_pairs, legacy=0.0)
    rows = [{"candidate_id": "good"}, {"candidate_id": "bad"}]
    portfolio = build_hypothesis_portfolio(rows, [good, bad])
    for name, bucket in portfolio.items():
        if name in {"diagnostic_only_candidates", "suppressed_candidates"}:
            continue
        assert bucket.get("candidate") is not None or bucket.get("reason")
    assert {entry["candidate"]["candidate_id"] for entry in portfolio["suppressed_candidates"]} == {"bad"}
    for name in (
        "best_manhattan_feasible",
        "best_height_consistent",
        "best_short_wall_preserving",
        "best_low_movement",
        "best_balanced",
    ):
        assert portfolio[name]["candidate"]["candidate_id"] == "good"
    assert portfolio["best_hohonet_consistent"]["candidate"] is None
    assert portfolio["best_hohonet_consistent"]["reason"]


def test_case_contract_and_evaluator_keep_the_safety_boundary_read_only():
    contract = build_case_contract(
        _pairs(),
        {
            "primary_edges": ["1-2"],
            "candidate_window": [1, 2],
            "movable_fields_by_pair": {"2": ["x"]},
        },
    )
    assert contract["primary_edges"] == ["1-2"]
    assert contract["legacy_default_contract"]["reason"]
    assert contract["safety_boundary"]["automatic_apply"] is False
    assert contract["safety_boundary"]["annotation_writeback"] is False
    evaluation = _evaluate(contract=contract)
    assert evaluation["safety_boundary"]["annotation_patch_generated"] is False
    assert evaluation["safety_boundary"]["worker_facing"] is False
    assert evaluation["safety_boundary"]["routing_input"] is False


def test_movable_fields_are_a_hard_contract():
    contract = build_case_contract(
        _pairs(),
        {"candidate_window": [2], "movable_fields_by_pair": {"2": ["x"]}},
    )
    candidate = _pairs()
    candidate[1]["top"]["y"] += 1.0
    evaluation = _evaluate(candidate_pairs=candidate, contract=contract)
    assert evaluation["feasibility"]["authorized_mutations_only"] is False
    assert "unauthorized_mutation_pair_2_top_y" in evaluation["feasibility"]["hard_failure_reasons"]
    assert evaluation["feasibility"]["hard_gate_passed"] is False


def test_height_uses_largest_gap_dominant_cluster_not_global_median():
    evaluation = _evaluate()
    height = evaluation["height_consistency"]
    assert height["dominant_height_h_star"] == pytest.approx(2.81)
    assert height["dominant_height_cluster_members"] == [1, 2, 3]
    assert height["height_outlier_pairs"] == [4]
    assert height["dominant_height_cluster_method"] == "largest_gap_connected_cluster_then_minimum_mad"


def test_incomplete_projection_metrics_hard_fail_without_exception():
    variant = _variant()
    variant["metrics"]["heights"]["pairs"] = []
    evaluation = _evaluate(candidate_variant=variant)
    assert evaluation["evaluation_status"] == "incomplete_metrics"
    assert evaluation["feasibility"]["projection_valid"] is False
    assert "projection_metrics:missing_height_pairs" in evaluation["feasibility"]["hard_failure_reasons"]
    assert evaluation["feasibility"]["hard_gate_passed"] is False


def test_seam_text_is_diagnostic_but_structured_code_is_a_hard_gate():
    text_only = _evaluate(candidate_variant=_variant(warnings=["wrap seam may need review"]))
    assert text_only["feasibility"]["wrap_or_seam_not_broken"] is True
    assert text_only["feasibility"]["wrap_or_seam_gate_status"] == "not_available_diagnostic_only"
    assert text_only["feasibility"]["wrap_or_seam_diagnostic_warnings"]

    coded = _evaluate(candidate_variant=_variant(warning_codes=["wrap_seam_broken"]))
    assert coded["feasibility"]["wrap_or_seam_not_broken"] is False
    assert coded["feasibility"]["hard_gate_passed"] is False


@pytest.mark.parametrize(
    "artifact",
    [
        "analysis_results/paper_a_manhattan/local_3d_projection/task218_ann3741/projection_metrics.json",
        "analysis_results/paper_a_manhattan/local_3d_projection/task218_ann2369/projection_metrics.json",
        "analysis_results/paper_a_manhattan/local_3d_projection/task238_ann2389/projection_metrics.json",
    ],
)
def test_real_projection_artifact_regression(artifact):
    payload = json.loads(Path(artifact).read_text(encoding="utf-8"))
    variant = next(row for row in payload["variants"] if row["name"] == "original")
    pairs = variant["ordered_pairs"]
    evaluation = evaluate_hypothesis(
        variant,
        variant,
        pairs,
        pairs,
        build_case_contract(pairs, projection_metrics=variant["metrics"]),
    )
    assert evaluation["evaluation_status"] == "complete"
    assert evaluation["feasibility"]["projection_valid"] is True
    assert evaluation["height_consistency"]["dominant_height_cluster_members"]
