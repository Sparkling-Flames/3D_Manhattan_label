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


def test_direction_family_and_parallel_residual_are_auditable_when_headings_exist():
    variant = _variant()
    for wall, heading in zip(
        variant["metrics"]["floorprint"]["walls"], (2.0, 91.0, 181.0, 272.0)
    ):
        wall["direction_deg"] = heading
    manhattan = _evaluate(candidate_variant=variant)["manhattan_feasibility"]

    fit = manhattan["direction_family_fit"]
    assert fit["status"] == "available"
    assert fit["dominant_family"]["family_id"] in {"family_0", "family_1"}
    assert len(fit["assignments"]) == 4
    assert fit["residual_summary"]["wall_count"] == 4
    assert manhattan["direction_family_fit_unavailable_reason"] is None

    parallel = manhattan["parallel_family_residual"]
    assert parallel["status"] == "available"
    assert parallel["pair_count"] == 2
    assert parallel["median_deg"] == pytest.approx(1.0)
    assert parallel["max_deg"] == pytest.approx(1.0)
    assert manhattan["parallel_family_residual_unavailable_reason"] is None


def test_direction_family_missing_heading_is_explicit_and_does_not_crash():
    manhattan = _evaluate()["manhattan_feasibility"]
    assert manhattan["direction_family_fit"] is None
    assert manhattan["direction_family_fit_status"] == "unavailable_due_to_missing_wall_heading"
    assert manhattan["direction_family_fit_unavailable_reason"] == "unavailable_due_to_missing_wall_heading"
    assert manhattan["parallel_family_residual"] is None
    assert manhattan["parallel_family_residual_unavailable_reason"] == "unavailable_due_to_missing_wall_heading"

    one_wall = _variant()
    one_wall["metrics"]["floorprint"]["walls"] = one_wall["metrics"]["floorprint"]["walls"][:1]
    one_wall["metrics"]["floorprint"]["walls"][0]["direction_deg"] = 0.0
    limited = _evaluate(candidate_variant=one_wall)["manhattan_feasibility"]
    assert limited["direction_family_fit_status"] == "insufficient_walls"
    assert limited["parallel_family_residual_unavailable_reason"] == "insufficient_walls"


def test_direction_ranking_preserves_hard_gate_and_legacy_last_fallback():
    available_variant = _variant()
    for wall, heading in zip(
        available_variant["metrics"]["floorprint"]["walls"], (0.0, 100.0, 180.0, 280.0)
    ):
        wall["direction_deg"] = heading
    available = _evaluate(candidate_variant=available_variant, legacy=1000.0)
    missing = _evaluate(legacy=-1000.0)
    assert build_hypothesis_ranking_key(available) < build_hypothesis_ranking_key(missing)

    hard_pairs = _pairs()
    hard_pairs[0]["top"]["x"] += 1.0
    hard = _evaluate(candidate_pairs=hard_pairs, candidate_variant=available_variant, legacy=-1e9)
    assert build_hypothesis_ranking_key(available) < build_hypothesis_ranking_key(hard)

    same_but_low_legacy = deepcopy(available)
    same_but_low_legacy["local_score_total"] = -1.0
    assert build_hypothesis_ranking_key(available)[:-1] == build_hypothesis_ranking_key(same_but_low_legacy)[:-1]
    assert build_hypothesis_ranking_key(same_but_low_legacy) < build_hypothesis_ranking_key(available)


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
    direction_fit = evaluation["manhattan_feasibility"]["direction_family_fit"]
    assert evaluation["manhattan_feasibility"]["direction_family_fit_status"] == "available"
    assert direction_fit is not None
    assert direction_fit["residual_summary"]["wall_count"] > 0


def test_decision_classes_are_structured_and_legacy_gate_is_not_a_hard_gate():
    baseline = _variant()
    improved = _variant()
    next(row for row in improved["metrics"]["floorprint"]["walls"] if row["from_pair"] == 3)["angle_residual_deg"] = 10.0
    contract = build_case_contract(_pairs(), {"primary_edges": ["3-4"], "candidate_window": []})

    diagnostic = evaluate_hypothesis(baseline, improved, _pairs(), _pairs(), contract)
    blocked = evaluate_hypothesis(
        baseline, improved, _pairs(), _pairs(), contract, legacy_trial_allowed=False
    )
    evidence = {field: [] if field == "visual_conflict_flags" else 0.0 for field in (
        "hohonet_wallwall_peak_alignment",
        "hohonet_floor_boundary_rmse_delta",
        "hohonet_ceiling_boundary_rmse_delta",
        "candidate_corner_column_delta",
        "seam_consistency_delta",
        "visual_conflict_flags",
        "image_edge_support_optional",
    )}
    eligible_variant = _variant(evidence=evidence)
    next(row for row in eligible_variant["metrics"]["floorprint"]["walls"] if row["from_pair"] == 3)["angle_residual_deg"] = 10.0
    eligible = evaluate_hypothesis(
        baseline, eligible_variant, _pairs(), _pairs(), contract, legacy_trial_allowed=True
    )
    neutral = evaluate_hypothesis(baseline, baseline, _pairs(), _pairs(), contract)
    hard = _evaluate(candidate_variant={"metrics": {}})

    assert diagnostic["decision_class"] == "hard_feasible_improving_evidence_unavailable"
    assert blocked["decision_class"] == "legacy_trial_blocked"
    assert blocked["feasibility"]["hard_gate_passed"] is True
    assert eligible["decision_class"] == "hard_feasible_improving_evidence_supported"
    assert neutral["decision_class"] == "hard_feasible_neutral"
    assert hard["decision_class"] == "diagnostic_only_incomplete_metrics"


def test_projection_rule_based_case_analyzer_on_real_artifacts():
    root = Path("analysis_results/paper_a_manhattan/local_3d_projection")
    expected = {
        "task218_ann3741": {"primary": "2-3", "height": {1, 2}},
        "task218_ann2369": {"primary": "8-1", "height": {1, 7, 8}},
        "task238_ann2389": {"primary": "6-1", "height": {4}},
    }
    for case, values in expected.items():
        payload = json.loads((root / case / "projection_metrics.json").read_text(encoding="utf-8"))
        original = payload["variants"][0]
        contract = build_case_contract(
            original["ordered_pairs"], projection_metrics=original["metrics"]
        )
        assert contract["inferred_primary_edges"] == [values["primary"]]
        assert set(contract["inferred_height_target_pairs"]) == values["height"]
        assert contract["auto_contract_summary"]["legacy_fallback_used"] is False
        assert contract["inferred_local_window_pairs"]
    payload = json.loads((root / "task218_ann2369/projection_metrics.json").read_text(encoding="utf-8"))
    original = payload["variants"][0]
    contract = build_case_contract(original["ordered_pairs"], projection_metrics=original["metrics"])
    assert contract["inferred_keep_distinct_pairs"] == [[5, 6]]
