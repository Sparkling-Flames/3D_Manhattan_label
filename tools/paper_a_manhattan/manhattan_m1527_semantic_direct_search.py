"""Deterministic semantic Hooke-Jeeves search for task218_ann3741."""

from __future__ import annotations

import copy
import statistics
from collections import Counter
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import (
    normalize_expert_assertions,
)
from tools.paper_a_manhattan.manhattan_m1526_adaptive_local_probe import (
    HEIGHT_TARGET_PAIRS,
    IMPROVEMENT_EPSILON,
    _constraint_state,
    _copy_pairs,
    _direct_gate,
    _height_lookup,
    _movement,
    _pair_index,
    _pair_lookup,
    _score_breakdown,
    _signature,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import (
    build_projection_variant,
)


SCHEMA_VERSION = "m15_27_1_semantic_direct_search_v1"
STEP_SCHEDULE = (1.0, 0.5, 0.25, 0.125)
MAX_EVALUATIONS = 600
TOP_LIMIT = 5
HEIGHT_CLUSTER_GAP = 0.30

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

ACTION_FAMILIES = {
    "height_outlier_pull_top_y": "wall_height",
    "floor_depth_balance_bottom_y": "floor_depth",
    "azimuth_pair_shift_x": "azimuth",
    "azimuth_block_shift_x": "azimuth",
    "dense_pair_separation_x": "azimuth",
    "mixed_x_bottom_y_pattern": "azimuth+floor_depth",
}


def manual_review_candidate_available(payload: Mapping[str, Any]) -> bool:
    """Read the current verdict, with a legacy-only compatibility fallback."""
    verdict = payload.get("overall_verdict", {})
    if payload.get("schema_version") == SCHEMA_VERSION:
        return bool(verdict.get("manual_review_candidate_available"))
    return bool(verdict.get("direct_fix_available"))


def dominant_height_cluster(variant: Mapping[str, Any]) -> dict[str, Any]:
    """Select the largest projected-height component; MAD breaks ties."""
    heights = _height_lookup(variant)
    rows = sorted(
        (float(heights[index]["wall_height"]), index)
        for index in HEIGHT_TARGET_PAIRS
        if index in heights
    )
    components: list[list[tuple[float, int]]] = []
    for row in rows:
        if not components or row[0] - components[-1][-1][0] > HEIGHT_CLUSTER_GAP:
            components.append([row])
        else:
            components[-1].append(row)

    def summary(component: Sequence[tuple[float, int]]) -> tuple[int, float, float]:
        values = [row[0] for row in component]
        center = statistics.median(values)
        mad = statistics.median(abs(value - center) for value in values)
        return len(component), mad, center

    selected = min(components, key=lambda rows: (-summary(rows)[0], summary(rows)[1], summary(rows)[2]))
    _, mad, h_star = summary(selected)
    members = sorted(row[1] for row in selected)
    return {
        "source_metric": "projected_wall_height",
        "target_pair_indices": list(HEIGHT_TARGET_PAIRS),
        "method": "largest_gap_connected_cluster_then_minimum_mad",
        "gap_threshold": HEIGHT_CLUSTER_GAP,
        "h_star": h_star,
        "cluster_members": members,
        "mad": mad,
        "height_outliers": [index for index in HEIGHT_TARGET_PAIRS if index not in members],
        "projected_wall_heights": {
            str(index): float(heights[index]["wall_height"])
            for index in HEIGHT_TARGET_PAIRS
            if index in heights
        },
    }


def _actions(cluster: Mapping[str, Any], frozen: set[int]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    def add(family: str, moves: list[tuple[int, str, float]], direction: int) -> None:
        if not any(pair in frozen for pair, _, _ in moves):
            actions.append(
                {
                    "family": family,
                    "direction": direction,
                    "moves": [
                        {"pair_index": pair, "field": field, "multiplier": multiplier * direction}
                        for pair, field, multiplier in moves
                    ],
                }
            )

    for pair in cluster["height_outliers"]:
        for direction in (-1, 1):
            add("height_outlier_pull_top_y", [(pair, "top_y", 1.0)], direction)
    for pair in (5, 6, 7):
        for direction in (-1, 1):
            add("floor_depth_balance_bottom_y", [(pair, "bottom_y", 1.0)], direction)
            add("azimuth_pair_shift_x", [(pair, "x", 0.5)], direction)
    for direction in (-1, 1):
        add("floor_depth_balance_bottom_y", [(6, "bottom_y", 1.0), (7, "bottom_y", -1.0)], direction)
        add("azimuth_block_shift_x", [(5, "x", 0.5), (6, "x", 0.5), (7, "x", 0.5)], direction)
        add("dense_pair_separation_x", [(5, "x", -0.25), (6, "x", 0.25)], direction)
    return actions


def _apply_action(
    pairs: Sequence[Mapping[str, Any]], action: Mapping[str, Any], step: float
) -> list[dict[str, Any]]:
    output = copy.deepcopy(list(pairs))
    lookup = _pair_lookup(output)
    for move in action["moves"]:
        pair = lookup[int(move["pair_index"])]
        delta = float(step) * float(move["multiplier"])
        if move["field"] == "x":
            value = max(0.0, min(100.0, (float(pair["top"]["x"]) + float(pair["bottom"]["x"])) / 2 + delta))
            pair["top"]["x"] = pair["bottom"]["x"] = value
        else:
            endpoint, axis = str(move["field"]).split("_")
            pair[endpoint][axis] = max(0.0, min(100.0, float(pair[endpoint][axis]) + delta))
    return output


def _height_distance(variant: Mapping[str, Any], h_star: float) -> float:
    heights = _height_lookup(variant)
    return sum(
        abs(float(heights[index]["wall_height"]) - h_star)
        for index in HEIGHT_TARGET_PAIRS
        if index in heights
    )


def _evaluate(
    candidate_id: str,
    parent_id: str,
    phase: str,
    round_index: int,
    step: float,
    action: Mapping[str, Any],
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    baseline_score: Mapping[str, Any],
    assertions: Mapping[str, Any],
    projection_config: Mapping[str, Any],
    cluster: Mapping[str, Any],
) -> dict[str, Any]:
    variant = build_projection_variant(
        candidate_id,
        candidate_pairs,
        width=int(projection_config["width"]),
        height=int(projection_config["height"]),
        coordinate_mode=str(projection_config["coordinate_mode"]),
        camera_height=float(projection_config["camera_height"]),
    )
    movement, changes, changed_pairs = _movement(baseline_pairs, candidate_pairs)
    constraints = _constraint_state(baseline_pairs, candidate_pairs, variant, assertions)
    if action.get("enforce_dense_pair_order") or action["family"] == "dense_pair_separation_x":
        before = _pair_lookup(baseline_pairs)
        after = _pair_lookup(candidate_pairs)
        old_delta = float(before[6]["bottom"]["x"]) - float(before[5]["bottom"]["x"])
        new_delta = float(after[6]["bottom"]["x"]) - float(after[5]["bottom"]["x"])
        if old_delta * new_delta <= 0 or abs(new_delta) < 0.01:
            constraints["assertion_violations"].append("dense_pair_5-6_x_cross_or_collapse")
            constraints["assertion_compliant"] = False
    score = _score_breakdown(
        variant,
        movement_l1=movement,
        anchor_violations=constraints["anchor_violations"],
        assertion_violations=constraints["assertion_violations"],
        geometry_invalid_reasons=constraints["geometry_invalid_reasons"],
    )
    score["dominant_height_cluster_l1"] = _height_distance(variant, float(cluster["h_star"]))
    direct_gate = _direct_gate(baseline_score, score, constraints)
    hard_ok = bool(constraints["assertion_compliant"] and constraints["geometry_valid"])
    primary_gain = float(baseline_score["primary_edge_6_7_residual"]) - float(score["primary_edge_6_7_residual"])
    local_checks = {
        "hard_constraints": hard_ok,
        "primary_or_height_gain": primary_gain >= 0.25 or (
            action["family"] == "height_outlier_pull_top_y"
            and score["dominant_height_cluster_l1"] < baseline_score["dominant_height_cluster_l1"] - IMPROVEMENT_EPSILON
        ),
        "wall_2_3_not_materially_worsened": score["wall_2_3_surface_or_heading_residual"] <= baseline_score["wall_2_3_surface_or_heading_residual"] + 0.25,
        "footprint_not_materially_worsened": score["wall_5_6_7_8_footprint_residual"] <= baseline_score["wall_5_6_7_8_footprint_residual"] + 0.50,
        "short_wall_not_seriously_worsened": direct_gate["checks"]["short_wall_not_seriously_worsened"],
    }
    failure = [name for name, passed in local_checks.items() if not passed]
    decision = (
        "suppressed_hard_constraint"
        if not hard_ok
        else "candidate_for_manual_review"
        if direct_gate["passed"]
        else "partial_diagnostic"
        if primary_gain > IMPROVEMENT_EPSILON or score["dominant_height_cluster_l1"] < baseline_score["dominant_height_cluster_l1"]
        else "neutral_no_improvement"
    )
    return {
        "candidate_id": candidate_id,
        "parent_candidate_id": parent_id,
        "phase": phase,
        "round_index": round_index,
        "step_size": step,
        "action_family": action["family"],
        "semantic_lever": action.get("semantic_lever", ACTION_FAMILIES.get(action["family"], "semantic_geometry")),
        "action": copy.deepcopy(action),
        "changed_pair_indices": changed_pairs,
        "coordinate_changes": changes,
        "score_breakdown": score,
        "gate_result": {"passed": all(local_checks.values()), "checks": local_checks},
        "failure_reason": failure,
        "assertion_compliant": constraints["assertion_compliant"],
        "assertion_violations": constraints["assertion_violations"],
        "geometry_valid": constraints["geometry_valid"],
        "geometry_invalid_reasons": constraints["geometry_invalid_reasons"],
        "decision_class": decision,
        "direct_ls_trial_allowed": bool(direct_gate["passed"]),
        "direct_trial_gate": direct_gate,
        "order_mutation": False,
        "merge_delete": False,
        "topology_rewrite": False,
    }


def _rank(row: Mapping[str, Any]) -> tuple[Any, ...]:
    score = row["score_breakdown"]
    return (
        not bool(row["assertion_compliant"] and row["geometry_valid"]),
        not bool(row["direct_ls_trial_allowed"]),
        not bool(row["gate_result"]["passed"]),
        float(score["primary_edge_6_7_residual"]),
        not bool(row["gate_result"]["checks"]["wall_2_3_not_materially_worsened"]),
        not bool(row["gate_result"]["checks"]["footprint_not_materially_worsened"]),
        not bool(row["gate_result"]["checks"]["short_wall_not_seriously_worsened"]),
        float(score["dominant_height_cluster_l1"]),
        float(score["movement_l1_ls_percent"]),
        str(row["candidate_id"]),
    )


def run_semantic_direct_search(
    baseline_pairs: Sequence[Mapping[str, Any]],
    *,
    expert_assertion: Mapping[str, Any],
    projection_config: Mapping[str, Any],
    visual_verdict: Mapping[str, Any],
    adaptive_probe: Mapping[str, Any],
    step_schedule: Sequence[float] = STEP_SCHEDULE,
    max_evaluations: int = MAX_EVALUATIONS,
) -> dict[str, Any]:
    if visual_verdict.get("overall_verdict", {}).get("direct_fix_available") is not False:
        raise ValueError("M15.27 requires the archived M15.25 no-direct-fix verdict")
    assertions = normalize_expert_assertions(
        expert_assertion,
        valid_pair_indices=sorted(_pair_lookup(baseline_pairs)),
        local_window=expert_assertion.get("candidate_window", []),
    )
    if assertions is None:
        raise ValueError("expert assertion is required")
    baseline_variant = build_projection_variant("baseline", baseline_pairs, **projection_config)
    cluster = dominant_height_cluster(baseline_variant)
    baseline_constraints = _constraint_state(baseline_pairs, baseline_pairs, baseline_variant, assertions)
    baseline_score = _score_breakdown(
        baseline_variant,
        movement_l1=0.0,
        anchor_violations=baseline_constraints["anchor_violations"],
        assertion_violations=baseline_constraints["assertion_violations"],
        geometry_invalid_reasons=baseline_constraints["geometry_invalid_reasons"],
    )
    baseline_score["dominant_height_cluster_l1"] = _height_distance(baseline_variant, cluster["h_star"])
    frozen = set(assertions["do_not_move_pairs"])
    action_catalog = _actions(cluster, frozen)
    current_pairs = _copy_pairs(baseline_pairs)
    current_id = "baseline"
    seen = {_signature(current_pairs)}
    evaluated: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()

    def evaluate(action: Mapping[str, Any], pairs: Sequence[Mapping[str, Any]], phase: str, round_index: int, step: float) -> dict[str, Any] | None:
        nonlocal current_id
        if len(evaluated) >= max_evaluations:
            return None
        signature = _signature(pairs)
        if signature in seen:
            return None
        seen.add(signature)
        candidate_id = f"m1527_candidate_{len(evaluated) + 1:04d}"
        row = _evaluate(candidate_id, current_id, phase, round_index, step, action, baseline_pairs, pairs, baseline_score, assertions, projection_config, cluster)
        evaluated.append(row)
        family_counts[row["action_family"]] += 1
        return row

    for round_index, step in enumerate(step_schedule, 1):
        round_rows: list[dict[str, Any]] = []
        for action in action_catalog:
            row = evaluate(action, _apply_action(current_pairs, action, step), "exploratory", round_index, float(step))
            if row:
                round_rows.append(row)
        profitable_x = [row for row in round_rows if row["gate_result"]["passed"] and row["action_family"].startswith(("azimuth_", "dense_"))]
        profitable_floor = [row for row in round_rows if row["gate_result"]["passed"] and row["action_family"] == "floor_depth_balance_bottom_y"]
        if profitable_x and profitable_floor:
            x_action = min(profitable_x, key=_rank)["action"]
            floor_action = min(profitable_floor, key=_rank)["action"]
            mixed = {"family": "mixed_x_bottom_y_pattern", "direction": 1, "moves": [*x_action["moves"], *floor_action["moves"]]}
            row = evaluate(mixed, _apply_action(current_pairs, mixed, step), "exploratory_mixed", round_index, float(step))
            if row:
                round_rows.append(row)
        admissible = [row for row in round_rows if row["gate_result"]["passed"]]
        chosen = min(admissible, key=_rank) if admissible else None
        pattern = None
        if chosen is not None:
            chosen_pairs = _apply_action(current_pairs, chosen["action"], step)
            pattern_pairs = _apply_action(chosen_pairs, chosen["action"], step)
            pattern = evaluate(chosen["action"], pattern_pairs, "pattern_extension", round_index, float(step))
            if pattern and pattern["gate_result"]["passed"] and _rank(pattern) < _rank(chosen):
                chosen = pattern
                chosen_pairs = pattern_pairs
            current_pairs = chosen_pairs
            current_id = chosen["candidate_id"]
        trace.append(
            {
                "round_index": round_index,
                "step_size": float(step),
                "exploratory_count": len(round_rows),
                "mixed_enabled": bool(profitable_x and profitable_floor),
                "pattern_extension_evaluated": pattern is not None,
                "accepted_candidate_id": chosen["candidate_id"] if chosen else None,
                "accepted_action_family": chosen["action_family"] if chosen else None,
                "reason": "accepted_local_gate_move" if chosen else "no_local_gate_move_reduce_step",
            }
        )
        if len(evaluated) >= max_evaluations:
            break

    ranked = sorted(evaluated, key=_rank)
    top = ranked[:TOP_LIMIT]
    direct = [row for row in ranked if row["direct_ls_trial_allowed"]]
    best = top[0] if top else None
    m1526_best = adaptive_probe.get("top_candidates", [{}])[0]
    m1526_primary = m1526_best.get("score_breakdown", {}).get("primary_edge_6_7_residual")
    best_primary = best["score_breakdown"]["primary_edge_6_7_residual"] if best else baseline_score["primary_edge_6_7_residual"]
    return {
        "schema_version": SCHEMA_VERSION,
        "safety_boundary": dict(SAFETY_BOUNDARY),
        "semantic_variable_mapping": {"x": "azimuth", "top_y": "wall_height", "bottom_y": "floor_depth"},
        "semantic_action_families": dict(ACTION_FAMILIES),
        "dominant_height_cluster": cluster,
        "expert_assertions_used": assertions,
        "search_config": {
            "strategy": "deterministic_hooke_jeeves_semantic_pattern_search",
            "step_schedule": list(step_schedule),
            "max_evaluations": max_evaluations,
            "top_candidate_limit": TOP_LIMIT,
            "randomness_used": False,
            "mixed_action_requires_profitable_single_axis_actions": True,
            "order_mutation_allowed": False,
            "merge_delete_allowed": False,
            "topology_rewrite_allowed": False,
        },
        "baseline": {"score_breakdown": baseline_score},
        "evaluation_count": len(evaluated),
        "family_evaluation_counts": dict(sorted(family_counts.items())),
        "search_trace": trace,
        "top_candidates": top,
        "m15_26_comparison": {
            "m15_26_best_candidate_id": m1526_best.get("candidate_id"),
            "m15_26_primary_edge_residual": m1526_primary,
            "m15_27_primary_edge_residual": best_primary,
            "m15_27_primary_edge_better": m1526_primary is not None and best_primary < float(m1526_primary) - IMPROVEMENT_EPSILON,
            "m15_27_still_partial": not bool(direct),
        },
        "overall_verdict": {
            "manual_review_candidate_available": bool(direct),
            "automatic_fix_claimed": False,
            "best_candidate_requires_visual_review": True,
            "best_candidate_id": best["candidate_id"] if best else None,
            "best_decision_class": best["decision_class"] if best else None,
            "verdict": "manual_review_candidate_available" if direct else "no_manual_review_candidate_available",
        },
    }
