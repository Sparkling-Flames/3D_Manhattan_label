import copy
import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
    build_hypothesis_ranking_layers,
)
from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import (
    build_hypothesis_portfolio,
)
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload


FIXTURE = json.loads(
    Path("tests/fixtures/paper_a_manhattan/hrc_scoring_layer_compliance_v1.json").read_text(
        encoding="utf-8"
    )
)["cases"]
SPEC = Path(
    "docs/paper_a_manhattan/HRC_C6_5A_4_SCORING_EVALUATOR_HARDENING_SPEC_v1.md"
)


def _evaluation():
    return copy.deepcopy(next(iter(build_payload()["constrained_evaluations"].values())))


def test_hardening_spec_contract_is_explicit_and_does_not_authorize_c6_5b():
    text = SPEC.read_text(encoding="utf-8")
    for needle in (
        "L0 hard feasibility",
        "L1 multi-metric Manhattan structure",
        "evidence_available_gate",
        "evidence_conflict_gate",
        "evidence_delta_key",
        "best_manhattan_feasible",
        "manual sidecar gate",
        "legacy_score_role=diagnostic_only",
        "C6.5b remains unauthorized",
    ):
        assert needle in text


def _set_direction(evaluation, maximum):
    evaluation["manhattan_feasibility"]["direction_family_fit"]["residual_summary"][
        "max_deg"
    ] = maximum


def test_l0_and_l1_fixture_contract():
    case = FIXTURE["l1_unresolved_before_direction"]
    structure = _evaluation()
    direction = copy.deepcopy(structure)
    for evaluation, values in (
        (structure, case["better_structure"]),
        (direction, case["better_direction_only"]),
    ):
        manhattan = evaluation["manhattan_feasibility"]
        manhattan["unresolved_edge_count"] = values["unresolved_edge_count"]
        manhattan["turn_residual_max"] = values["turn_residual_max"]
        manhattan["local_window_residual"] = values["local_window_residual"]
        _set_direction(evaluation, values["direction_max_deg"])
    assert build_hypothesis_ranking_key(structure) < build_hypothesis_ranking_key(direction)

    failed = copy.deepcopy(structure)
    failed["feasibility"]["hard_gate_passed"] = False
    assert build_hypothesis_ranking_key(structure) < build_hypothesis_ranking_key(failed)


def test_l2_gate_precedes_l3_and_baseline_evidence_cannot_prefer():
    case = FIXTURE["l2_conflict_before_l3"]
    supported = _evaluation()
    conflict = copy.deepcopy(supported)
    for evaluation, values in (
        (supported, case["supported"]),
        (conflict, case["conflicted_better_height"]),
    ):
        evidence = evaluation["evidence_consistency"]
        evidence["evidence_status"] = values["evidence_status"]
        evidence["candidate_preference_authorized"] = values[
            "candidate_preference_authorized"
        ]
        evidence["visual_conflict_flags"] = values["visual_conflict_flags"]
        evaluation["height_consistency"]["height_outlier_l1"] = values[
            "height_outlier_l1"
        ]
    assert build_hypothesis_ranking_key(supported) < build_hypothesis_ranking_key(conflict)

    baseline = copy.deepcopy(supported)
    baseline["evidence_consistency"].update(
        FIXTURE["baseline_evidence_not_candidate_preference"]
    )
    layers = build_hypothesis_ranking_layers(baseline)
    assert layers["L2"][0] is True


def test_c5_does_not_change_best_manhattan_feasible():
    left = _evaluation()
    right = copy.deepcopy(left)
    left["plane_proxy_metrics"]["wall_plane_orthogonal_consistency"][
        "orthogonal_residual_deg"
    ] = 99.0
    right["plane_proxy_metrics"]["wall_plane_orthogonal_consistency"][
        "orthogonal_residual_deg"
    ] = 0.0
    portfolio = build_hypothesis_portfolio(
        [{"candidate_id": "left"}, {"candidate_id": "right"}], [left, right]
    )
    assert portfolio["best_manhattan_feasible"]["candidate"]["candidate_id"] == "left"


def test_l4_manual_gate_precedes_l5_and_legacy_is_excluded():
    case = FIXTURE["manual_gate_before_movement"]
    available = _evaluation()
    missing = copy.deepcopy(available)
    for evaluation, values in (
        (available, case["manual_available"]),
        (missing, case["manual_missing_low_movement"]),
    ):
        evaluation["manual_evidence"] = {
            "required": values["required"],
            "status": values["status"],
        }
        evaluation["movement_edit_cost"]["movement_l1_normalized"] = values[
            "movement_l1_normalized"
        ]
    assert build_hypothesis_ranking_key(available) < build_hypothesis_ranking_key(missing)

    changed_legacy = copy.deepcopy(available)
    changed_legacy["local_score_total"] = -1e12
    changed_legacy["legacy_score_breakdown"] = {"local_score_total": -1e12}
    assert build_hypothesis_ranking_key(changed_legacy) == build_hypothesis_ranking_key(
        available
    )
