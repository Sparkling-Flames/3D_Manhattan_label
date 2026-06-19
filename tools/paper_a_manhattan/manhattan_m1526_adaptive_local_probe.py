"""Deterministic bounded M15.26 adaptive local geometry probe.

Expert-side dry-run only.  This module reuses the frozen projection/metric
implementation and never mutates annotations, topology, routing, or M15.22.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import (
    normalize_expert_assertions,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import (
    build_projection_variant,
)


SCHEMA_VERSION = "m15_26_adaptive_local_probe_v1"
STEP_SCHEDULE = (1.0, 0.5, 0.25, 0.125)
BEAM_WIDTH = 5
MAX_EVALUATIONS = 500
IMPROVEMENT_EPSILON = 1e-6
TARGET_Y_PAIRS = (1, 2, 5, 6, 7, 8)
OPTIONAL_X_PAIRS = (5, 6, 7)
HEIGHT_TARGET_PAIRS = (1, 2, 5, 6, 7, 8)
FOOTPRINT_EDGES = ((5, 6), (6, 7), (7, 8))
SHORT_WALL_EDGES = ((2, 3), (5, 6), (6, 7), (7, 8))
COLLAPSE_THRESHOLD = 0.10
MIN_TOP_BOTTOM_GAP = 1.0
MOVEMENT_GATE_THRESHOLD = 6.0
UNRESOLVED_EDGE_THRESHOLD_DEG = 15.0

SAFETY_BOUNDARY = {
    "expert_side": True,
    "offline_local_only": True,
    "dry_run_only": True,
    "annotation_write_allowed": False,
    "annotation_patch_generated": False,
    "automatic_apply": False,
    "automatic_global_optimization": False,
    "worker_facing": False,
    "routing_input": False,
    "formal_artifact": False,
}


def _pair_index(pair: Mapping[str, Any]) -> int:
    return int(pair["effective_pair_index"])


def _pair_lookup(pairs: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    return {_pair_index(pair): pair for pair in pairs}


def _copy_pairs(pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return copy.deepcopy(list(pairs))


def _wall_lookup(variant: Mapping[str, Any]) -> dict[tuple[int, int], Mapping[str, Any]]:
    return {
        (int(row["from_pair"]), int(row["to_pair"])): row
        for row in variant["metrics"]["floorprint"]["walls"]
    }


def _height_lookup(variant: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["effective_pair_index"]): row
        for row in variant["metrics"]["heights"]["pairs"]
    }


def _edge_name(edge: tuple[int, int]) -> str:
    return f"{edge[0]}-{edge[1]}"


def _wall(lookup: Mapping[tuple[int, int], Mapping[str, Any]], edge: tuple[int, int]) -> Mapping[str, Any]:
    row = lookup.get(edge) or lookup.get((edge[1], edge[0]))
    if row is None:
        raise ValueError(f"required edge {_edge_name(edge)} is missing")
    return row


def _movement(
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
) -> tuple[float, list[dict[str, Any]], list[int]]:
    baseline = _pair_lookup(baseline_pairs)
    candidate = _pair_lookup(candidate_pairs)
    changes: list[dict[str, Any]] = []
    changed_pairs: list[int] = []
    total = 0.0
    for pair_index in sorted(baseline):
        fields: dict[str, dict[str, float]] = {}
        for endpoint in ("top", "bottom"):
            for axis in ("x", "y"):
                before = float(baseline[pair_index][endpoint][axis])
                after = float(candidate[pair_index][endpoint][axis])
                if abs(after - before) <= 1e-12:
                    continue
                fields[f"{endpoint}_{axis}"] = {"before": before, "after": after}
                total += abs(after - before)
        if fields:
            changed_pairs.append(pair_index)
            changes.append({"effective_pair_index": pair_index, "fields": fields})
    return total, changes, changed_pairs


def build_search_variables(
    ordered_pairs: Sequence[Mapping[str, Any]], assertions: Mapping[str, Any]
) -> dict[str, Any]:
    available = set(_pair_lookup(ordered_pairs))
    frozen = set(int(value) for value in assertions["do_not_move_pairs"])
    y_pairs = [value for value in TARGET_Y_PAIRS if value in available and value not in frozen]
    x_pairs = [value for value in OPTIONAL_X_PAIRS if value in available and value not in frozen]
    variables = [
        {"pair_index": pair_index, "field": field}
        for pair_index in y_pairs
        for field in ("top_y", "bottom_y")
    ]
    variables.extend({"pair_index": pair_index, "field": "x"} for pair_index in x_pairs)
    anchors = sorted({4, *frozen}.intersection(available))
    return {
        "movable_variables": variables,
        "movable_pair_indices": sorted({row["pair_index"] for row in variables}),
        "fixed_anchor_pair_indices": anchors,
        "score_target_pair_indices": list(HEIGHT_TARGET_PAIRS),
        "score_only_frozen_pair_indices": sorted(
            set(HEIGHT_TARGET_PAIRS).intersection(frozen)
        ),
        "order_mutation_allowed": False,
        "merge_delete_allowed": False,
        "auto_reorder_allowed": False,
        "topology_rewrite_allowed": False,
        "assertion_candidate_window_context": list(assertions["candidate_window"]),
    }


def _apply_perturbation(
    pairs: Sequence[Mapping[str, Any]], variable: Mapping[str, Any], delta: float
) -> list[dict[str, Any]]:
    output = _copy_pairs(pairs)
    target = next(row for row in output if _pair_index(row) == int(variable["pair_index"]))
    field = str(variable["field"])
    if field == "x":
        center = (float(target["top"]["x"]) + float(target["bottom"]["x"])) / 2.0
        value = max(0.0, min(100.0, center + delta))
        target["top"]["x"] = value
        target["bottom"]["x"] = value
    else:
        endpoint, axis = field.split("_")
        value = float(target[endpoint][axis]) + delta
        target[endpoint][axis] = max(0.0, min(100.0, value))
    return output


def _signature(pairs: Sequence[Mapping[str, Any]]) -> tuple[float, ...]:
    values: list[float] = []
    for pair in sorted(pairs, key=_pair_index):
        values.extend(
            round(float(pair[endpoint][axis]), 8)
            for endpoint in ("top", "bottom")
            for axis in ("x", "y")
        )
    return tuple(values)


def _score_breakdown(
    variant: Mapping[str, Any],
    *,
    movement_l1: float,
    anchor_violations: Sequence[str],
    assertion_violations: Sequence[str],
    geometry_invalid_reasons: Sequence[str],
) -> dict[str, Any]:
    walls = _wall_lookup(variant)
    heights = _height_lookup(variant)
    primary = float(_wall(walls, (6, 7))["angle_residual_deg"])
    wall_2_3 = float(_wall(walls, (2, 3))["angle_residual_deg"])
    footprint = sum(float(_wall(walls, edge)["angle_residual_deg"]) for edge in FOOTPRINT_EDGES)
    y_height = sum(
        abs(float(heights[pair_index]["height_residual"]))
        for pair_index in HEIGHT_TARGET_PAIRS
    )
    short_deficits = {
        _edge_name(edge): max(
            0.0,
            float(_wall(walls, edge)["short_wall_threshold"])
            - float(_wall(walls, edge)["floor_wall_length"]),
        )
        for edge in SHORT_WALL_EDGES
        if bool(_wall(walls, edge)["short_wall"])
    }
    short_penalty = 100.0 * sum(short_deficits.values())
    movement_penalty = 0.25 * movement_l1
    anchor_penalty = 10000.0 * len(anchor_violations)
    assertion_penalty = 10000.0 * len(assertion_violations)
    fold_penalty = 10000.0 * len(geometry_invalid_reasons)
    total = (
        4.0 * primary
        + 1.5 * wall_2_3
        + footprint
        + 10.0 * y_height
        + short_penalty
        + movement_penalty
        + anchor_penalty
        + assertion_penalty
        + fold_penalty
    )
    return {
        "primary_edge_6_7_residual": primary,
        "wall_2_3_surface_or_heading_residual": wall_2_3,
        "wall_5_6_7_8_footprint_residual": footprint,
        "y_height_consistency_residual_pairs_1_2_5_6_7_8": y_height,
        "short_wall_penalty": short_penalty,
        "short_wall_deficits": short_deficits,
        "movement_penalty": movement_penalty,
        "movement_l1_ls_percent": movement_l1,
        "anchor_violation_penalty": anchor_penalty,
        "assertion_violation_penalty": assertion_penalty,
        "fold_or_self_intersection_penalty": fold_penalty,
        "local_score_total": total,
    }


def _constraint_state(
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    variant: Mapping[str, Any],
    assertions: Mapping[str, Any],
) -> dict[str, Any]:
    baseline = _pair_lookup(baseline_pairs)
    candidate = _pair_lookup(candidate_pairs)
    anchor_violations: list[str] = []
    assertion_violations: list[str] = []
    geometry_invalid: list[str] = []
    for pair_index in sorted({4, *assertions["do_not_move_pairs"]}):
        if pair_index in baseline and candidate[pair_index] != baseline[pair_index]:
            reason = f"anchor_pair_{pair_index}_moved"
            anchor_violations.append(reason)
            if pair_index in assertions["do_not_move_pairs"]:
                assertion_violations.append(f"do_not_move_pair_{pair_index}_moved")
    if [_pair_index(row) for row in candidate_pairs] != [_pair_index(row) for row in baseline_pairs]:
        geometry_invalid.append("ordered_pair_sequence_changed")
    for pair in candidate_pairs:
        if float(pair["top"]["y"]) + MIN_TOP_BOTTOM_GAP >= float(pair["bottom"]["y"]):
            geometry_invalid.append(f"pair_{_pair_index(pair)}_top_bottom_fold")
    if bool(variant["metrics"]["floorprint"]["self_intersection"]):
        geometry_invalid.append("floorprint_self_intersection")
    walls = _wall_lookup(variant)
    for left, right in assertions["keep_distinct_pairs"]:
        edge = (int(left), int(right))
        wall = _wall(walls, edge)
        if float(wall["floor_wall_length"]) < COLLAPSE_THRESHOLD:
            assertion_violations.append(f"keep_distinct_{left}-{right}_collapse")
    explanations = [
        (
            f"{edge} is an allowed existing short-wall risk for explanation only; "
            "the allowance is not a correctness claim."
        )
        for edge in assertions["allowed_short_edges"]
        if bool(_wall(walls, tuple(int(value) for value in edge.split("-")))["short_wall"])
    ]
    return {
        "anchor_violations": anchor_violations,
        "assertion_violations": assertion_violations,
        "assertion_compliant": not assertion_violations,
        "geometry_invalid_reasons": geometry_invalid,
        "geometry_valid": not geometry_invalid,
        "allowed_short_edge_explanations": explanations,
    }


def _short_wall_gate(
    baseline_score: Mapping[str, Any], candidate_score: Mapping[str, Any]
) -> tuple[bool, list[str]]:
    before = baseline_score["short_wall_deficits"]
    after = candidate_score["short_wall_deficits"]
    reasons: list[str] = []
    for edge, deficit in after.items():
        if edge not in before:
            reasons.append(f"new_short_wall_{edge}")
        elif float(deficit) > float(before[edge]) + 0.02:
            reasons.append(f"short_wall_deficit_worsened_{edge}")
    return not reasons, reasons


def _direct_gate(
    baseline_score: Mapping[str, Any],
    score: Mapping[str, Any],
    constraints: Mapping[str, Any],
) -> dict[str, Any]:
    primary_before = float(baseline_score["primary_edge_6_7_residual"])
    primary_after = float(score["primary_edge_6_7_residual"])
    short_ok, short_reasons = _short_wall_gate(baseline_score, score)
    checks = {
        "assertion_compliant": bool(constraints["assertion_compliant"]),
        "geometry_valid": bool(constraints["geometry_valid"]),
        "primary_edge_significantly_improved": (
            primary_before - primary_after >= 5.0
            and primary_after <= primary_before * 0.80
        ),
        "primary_edge_resolved_under_15_deg": (
            primary_after <= UNRESOLVED_EDGE_THRESHOLD_DEG
        ),
        "wall_2_3_not_worsened": (
            float(score["wall_2_3_surface_or_heading_residual"])
            <= float(baseline_score["wall_2_3_surface_or_heading_residual"])
            + IMPROVEMENT_EPSILON
        ),
        "wall_5_6_7_8_not_worsened": (
            float(score["wall_5_6_7_8_footprint_residual"])
            <= float(baseline_score["wall_5_6_7_8_footprint_residual"])
            + IMPROVEMENT_EPSILON
        ),
        "y_height_consistency_improved": (
            float(score["y_height_consistency_residual_pairs_1_2_5_6_7_8"])
            <= float(baseline_score["y_height_consistency_residual_pairs_1_2_5_6_7_8"])
            - 0.05
        ),
        "movement_below_threshold": (
            float(score["movement_l1_ls_percent"]) <= MOVEMENT_GATE_THRESHOLD
        ),
        "short_wall_not_seriously_worsened": short_ok,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "checks": checks,
        "failed_checks": failed,
        "short_wall_gate_reasons": short_reasons,
        "passed": all(checks.values()),
    }


def evaluate_probe_candidate(
    *,
    candidate_id: str,
    parent_candidate_id: str,
    round_index: int,
    step_size: float,
    perturbation: Mapping[str, Any],
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    baseline_score: Mapping[str, Any],
    assertions: Mapping[str, Any],
    projection_config: Mapping[str, Any],
) -> dict[str, Any]:
    variant = build_projection_variant(
        candidate_id,
        candidate_pairs,
        width=int(projection_config["width"]),
        height=int(projection_config["height"]),
        coordinate_mode=str(projection_config["coordinate_mode"]),
        camera_height=float(projection_config["camera_height"]),
    )
    movement, coordinate_changes, changed_pairs = _movement(
        baseline_pairs, candidate_pairs
    )
    constraints = _constraint_state(
        baseline_pairs, candidate_pairs, variant, assertions
    )
    score = _score_breakdown(
        variant,
        movement_l1=movement,
        anchor_violations=constraints["anchor_violations"],
        assertion_violations=constraints["assertion_violations"],
        geometry_invalid_reasons=constraints["geometry_invalid_reasons"],
    )
    gate = _direct_gate(baseline_score, score, constraints)
    score_improved = (
        float(score["local_score_total"])
        < float(baseline_score["local_score_total"]) - IMPROVEMENT_EPSILON
    )
    primary_improved = (
        float(score["primary_edge_6_7_residual"])
        < float(baseline_score["primary_edge_6_7_residual"]) - 1.0
    )
    if not constraints["geometry_valid"]:
        decision = "suppressed_geometry_invalid"
    elif not constraints["assertion_compliant"]:
        decision = "suppressed_assertion_violation"
    elif gate["passed"]:
        decision = "candidate_for_manual_review"
    elif score_improved or primary_improved:
        decision = "partial_diagnostic"
    else:
        decision = "neutral_no_improvement"
    return {
        "candidate_id": candidate_id,
        "parent_candidate_id": parent_candidate_id,
        "round_index": round_index,
        "step_size": step_size,
        "perturbation": dict(perturbation),
        "changed_pair_indices": changed_pairs,
        "coordinate_changes": coordinate_changes,
        "order_mutation": False,
        "merge_delete": False,
        "auto_reorder": False,
        "topology_rewrite": False,
        **constraints,
        "score_breakdown": score,
        "score_delta_from_baseline": (
            float(score["local_score_total"])
            - float(baseline_score["local_score_total"])
        ),
        "direct_trial_gate": gate,
        "decision_class": decision,
        "direct_ls_trial_allowed": bool(gate["passed"]),
    }


def _ranking_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    suppressed = candidate["decision_class"] in {
        "suppressed_assertion_violation",
        "suppressed_geometry_invalid",
    }
    return (
        suppressed,
        not bool(candidate["assertion_compliant"]),
        not bool(candidate["geometry_valid"]),
        float(candidate["score_breakdown"]["local_score_total"]),
        str(candidate["candidate_id"]),
    )


def run_adaptive_probe(
    baseline_pairs: Sequence[Mapping[str, Any]],
    *,
    expert_assertion: Mapping[str, Any],
    projection_config: Mapping[str, Any],
    visual_verdict: Mapping[str, Any],
    step_schedule: Sequence[float] = STEP_SCHEDULE,
    beam_width: int = BEAM_WIDTH,
    max_evaluations: int = MAX_EVALUATIONS,
) -> dict[str, Any]:
    if visual_verdict.get("overall_verdict", {}).get("direct_fix_available") is not False:
        raise ValueError("M15.26 requires an archived no-direct-fix visual verdict")
    valid_indices = sorted(_pair_lookup(baseline_pairs))
    assertions = normalize_expert_assertions(
        expert_assertion,
        valid_pair_indices=valid_indices,
        local_window=expert_assertion.get("candidate_window", []),
    )
    if assertions is None:
        raise ValueError("expert assertion is required")
    variables = build_search_variables(baseline_pairs, assertions)
    baseline_variant = build_projection_variant(
        "baseline",
        baseline_pairs,
        width=int(projection_config["width"]),
        height=int(projection_config["height"]),
        coordinate_mode=str(projection_config["coordinate_mode"]),
        camera_height=float(projection_config["camera_height"]),
    )
    baseline_constraints = _constraint_state(
        baseline_pairs, baseline_pairs, baseline_variant, assertions
    )
    baseline_score = _score_breakdown(
        baseline_variant,
        movement_l1=0.0,
        anchor_violations=baseline_constraints["anchor_violations"],
        assertion_violations=baseline_constraints["assertion_violations"],
        geometry_invalid_reasons=baseline_constraints["geometry_invalid_reasons"],
    )
    baseline_record = {
        "candidate_id": "baseline",
        "ordered_pairs": _copy_pairs(baseline_pairs),
        "score_breakdown": baseline_score,
        "assertion_compliant": baseline_constraints["assertion_compliant"],
        "geometry_valid": baseline_constraints["geometry_valid"],
        "decision_class": "baseline",
    }
    beam = [baseline_record]
    seen = {_signature(baseline_pairs)}
    candidates: list[dict[str, Any]] = []
    states: dict[str, list[dict[str, Any]]] = {"baseline": _copy_pairs(baseline_pairs)}
    trace: list[dict[str, Any]] = []
    evaluation_count = 0
    previous_best_score = float(baseline_score["local_score_total"])

    for round_index, step in enumerate(step_schedule, start=1):
        generated: list[dict[str, Any]] = []
        for parent in beam:
            parent_pairs = states[parent["candidate_id"]]
            for variable in variables["movable_variables"]:
                for direction in (-1.0, 1.0):
                    if evaluation_count >= max_evaluations:
                        break
                    candidate_pairs = _apply_perturbation(
                        parent_pairs, variable, direction * float(step)
                    )
                    signature = _signature(candidate_pairs)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    evaluation_count += 1
                    candidate_id = f"m1526_candidate_{evaluation_count:04d}"
                    record = evaluate_probe_candidate(
                        candidate_id=candidate_id,
                        parent_candidate_id=str(parent["candidate_id"]),
                        round_index=round_index,
                        step_size=float(step),
                        perturbation={
                            **variable,
                            "direction": int(direction),
                            "delta": direction * float(step),
                        },
                        baseline_pairs=baseline_pairs,
                        candidate_pairs=candidate_pairs,
                        baseline_score=baseline_score,
                        assertions=assertions,
                        projection_config=projection_config,
                    )
                    states[candidate_id] = candidate_pairs
                    candidates.append(record)
                    generated.append(record)
                if evaluation_count >= max_evaluations:
                    break
            if evaluation_count >= max_evaluations:
                break
        pool = [*beam, *generated]
        beam = sorted(pool, key=_ranking_key)[:beam_width]
        best = beam[0]
        best_score = float(best["score_breakdown"]["local_score_total"])
        improved = best_score < previous_best_score - IMPROVEMENT_EPSILON
        maxed = evaluation_count >= max_evaluations
        final_round = round_index == len(step_schedule)
        reason = (
            "max_evaluations_reached"
            if maxed
            else (
                "step_schedule_exhausted"
                if final_round
                else (
                    "improved_continue_with_smaller_step"
                    if improved
                    else "no_improvement_advance_to_smaller_step"
                )
            )
        )
        trace.append(
            {
                "round_index": round_index,
                "step_size": float(step),
                "generated_count": len(generated),
                "retained_count": len(beam),
                "best_score": best_score,
                "best_candidate_id": best["candidate_id"],
                "primary_edge_residual_before": float(
                    baseline_score["primary_edge_6_7_residual"]
                ),
                "primary_edge_residual_after": float(
                    best["score_breakdown"]["primary_edge_6_7_residual"]
                ),
                "reason_for_stopping": reason,
            }
        )
        previous_best_score = min(previous_best_score, best_score)
        if maxed:
            break

    ranked = sorted(candidates, key=_ranking_key)
    direct_candidates = [row for row in ranked if row["direct_ls_trial_allowed"]]
    best = ranked[0] if ranked else None
    overall = {
        "direct_fix_available": bool(direct_candidates),
        "verdict": (
            "candidate_for_manual_review_available"
            if direct_candidates
            else "no_direct_fix_available"
        ),
        "best_candidate_id": best["candidate_id"] if best else None,
        "best_decision_class": best["decision_class"] if best else None,
        "best_score": (
            float(best["score_breakdown"]["local_score_total"])
            if best
            else float(baseline_score["local_score_total"])
        ),
        "best_primary_edge_residual": (
            float(best["score_breakdown"]["primary_edge_6_7_residual"])
            if best
            else float(baseline_score["primary_edge_6_7_residual"])
        ),
        "stopping_reason": (
            "direct_trial_gate_passed"
            if direct_candidates
            else "step_schedule_exhausted_without_direct_trial_gate"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "safety_boundary": dict(SAFETY_BOUNDARY),
        "visual_verdict_context": {
            "schema_version": visual_verdict.get("schema_version"),
            "direct_fix_available": False,
            "best_visual_candidate": visual_verdict.get("overall_verdict", {}).get(
                "best_visual_candidate"
            ),
        },
        "expert_assertions_used": assertions,
        "search_space": variables,
        "search_config": {
            "strategy": "deterministic_bounded_adaptive_coordinate_beam_search",
            "step_schedule": [float(value) for value in step_schedule],
            "beam_width": beam_width,
            "max_evaluations": max_evaluations,
            "improvement_epsilon": IMPROVEMENT_EPSILON,
            "randomness_used": False,
        },
        "baseline": {
            "score_breakdown": baseline_score,
            "assertion_compliant": baseline_constraints["assertion_compliant"],
            "geometry_valid": baseline_constraints["geometry_valid"],
        },
        "evaluation_count": evaluation_count,
        "candidates": candidates,
        "top_candidates": ranked[:5],
        "search_trace": trace,
        "overall_verdict": overall,
    }
