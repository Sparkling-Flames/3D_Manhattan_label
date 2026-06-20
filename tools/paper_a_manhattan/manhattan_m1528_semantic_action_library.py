"""M15.28 deterministic semantic action-library expansion."""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import normalize_expert_assertions
from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
    evaluate_hypothesis,
)
from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import (
    build_hypothesis_portfolio,
)
from tools.paper_a_manhattan.manhattan_m1526_adaptive_local_probe import (
    _constraint_state,
    _copy_pairs,
    _movement,
    _pair_lookup,
    _score_breakdown,
    _signature,
)
from tools.paper_a_manhattan.manhattan_m1527_semantic_direct_search import (
    STEP_SCHEDULE,
    _evaluate,
    dominant_height_cluster,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import build_projection_variant


SCHEMA_VERSION = "m15_28_semantic_action_library_v1"
MAX_EVALUATIONS = 600
TOP_LIMIT = 5
ALLOWED_SHORT_DEFICIT_BAND = 0.005
SECONDARY_FIELDS = {"top_y", "bottom_y", "x"}

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

ACTION_FAMILIES = (
    "vertical_column_align_x",
    "endpoint_anchor_align_x",
    "azimuth_translate_pair_x",
    "azimuth_translate_keep_top_bottom_delta",
    "edge_6_7_azimuth_open_close",
    "edge_6_7_floor_depth_balance",
    "edge_6_7_pivot_around_6",
    "edge_6_7_pivot_around_7",
    "edge_6_7_normal_slide_proxy",
    "preserve_5_6_short_wall_block_x",
    "preserve_5_6_length_with_6_7_fix",
    "short_wall_compensated_mixed_move",
    "height_outlier_pull_top_y",
    "secondary_edge_2_3_semantic_probe",
)


def validate_secondary_assertions(
    payload: Mapping[str, Any], valid_pair_indices: Sequence[int]
) -> dict[str, Any]:
    valid = set(valid_pair_indices)
    pairs = payload.get("allow_secondary_window_pairs", [])
    edges = payload.get("secondary_primary_edges", [])
    fields = payload.get("allowed_movable_fields_for_secondary", [])
    if not isinstance(pairs, list) or any(not isinstance(value, int) or value not in valid for value in pairs):
        raise ValueError("allow_secondary_window_pairs must contain valid pair indices")
    if not isinstance(edges, list) or any(value != "2-3" for value in edges):
        raise ValueError("secondary_primary_edges v1 only supports 2-3")
    if not isinstance(fields, list) or any(value not in SECONDARY_FIELDS for value in fields):
        raise ValueError("allowed_movable_fields_for_secondary contains an unsupported field")
    enabled = {1, 2, 3}.issubset(pairs) and "2-3" in edges and bool(fields)
    return {
        "enabled": enabled,
        "allow_secondary_window_pairs": list(dict.fromkeys(pairs)),
        "secondary_primary_edges": list(dict.fromkeys(edges)),
        "allowed_movable_fields_for_secondary": list(dict.fromkeys(fields)),
    }


def build_action_specs(
    pairs: Sequence[Mapping[str, Any]],
    cluster: Mapping[str, Any],
    assertions: Mapping[str, Any],
    secondary: Mapping[str, Any],
    step: float,
) -> list[dict[str, Any]]:
    lookup = _pair_lookup(pairs)
    frozen = set(assertions["do_not_move_pairs"])
    specs: list[dict[str, Any]] = []

    def add(family: str, operations: list[dict[str, Any]], **metadata: Any) -> None:
        if not any(int(operation["pair_index"]) in frozen for operation in operations):
            specs.append({"family": family, "semantic_lever": metadata.pop("semantic_lever", "semantic_geometry"), "operations": operations, **metadata})

    for pair_index in (5, 6, 7):
        pair = lookup[pair_index]
        add("vertical_column_align_x", [{"pair_index": pair_index, "operation": "align_midpoint_x"}], semantic_lever="column_alignment")
        add("endpoint_anchor_align_x", [{"pair_index": pair_index, "operation": "top_to_bottom_x"}], anchor_endpoint="bottom", semantic_lever="column_alignment")
        add("endpoint_anchor_align_x", [{"pair_index": pair_index, "operation": "bottom_to_top_x"}], anchor_endpoint="top", semantic_lever="column_alignment")
        for direction in (-1, 1):
            delta = direction * step * 0.5
            add("azimuth_translate_keep_top_bottom_delta", [{"pair_index": pair_index, "operation": "translate_x", "delta": delta}], semantic_lever="azimuth")
            if abs(float(pair["top"]["x"]) - float(pair["bottom"]["x"])) <= 0.01:
                add("azimuth_translate_pair_x", [{"pair_index": pair_index, "operation": "translate_x", "delta": delta}], semantic_lever="azimuth")

    for direction in (-1, 1):
        x = direction * step * 0.5
        y = direction * step
        add("edge_6_7_azimuth_open_close", [{"pair_index": 6, "operation": "translate_x", "delta": -x}, {"pair_index": 7, "operation": "translate_x", "delta": x}], semantic_lever="primary_edge_6_7")
        for mode, signs in (("opposing", (-1, 1)), ("synchronized", (1, 1))):
            add("edge_6_7_floor_depth_balance", [{"pair_index": 6, "operation": "delta_field", "field": "bottom_y", "delta": signs[0] * y}, {"pair_index": 7, "operation": "delta_field", "field": "bottom_y", "delta": signs[1] * y}], mode=mode, semantic_lever="primary_edge_6_7")
        add("edge_6_7_pivot_around_6", [{"pair_index": 7, "operation": "translate_x", "delta": x}], fixed_pair=6, semantic_lever="primary_edge_6_7")
        add("edge_6_7_pivot_around_7", [{"pair_index": 6, "operation": "translate_x", "delta": x}], fixed_pair=7, semantic_lever="primary_edge_6_7")
        add("edge_6_7_normal_slide_proxy", [{"pair_index": 6, "operation": "translate_x", "delta": -x / 2}, {"pair_index": 6, "operation": "delta_field", "field": "bottom_y", "delta": -y / 2}, {"pair_index": 7, "operation": "translate_x", "delta": x / 2}, {"pair_index": 7, "operation": "delta_field", "field": "bottom_y", "delta": y / 2}], semantic_lever="azimuth+floor_depth")
        add("preserve_5_6_short_wall_block_x", [{"pair_index": 5, "operation": "translate_x", "delta": x}, {"pair_index": 6, "operation": "translate_x", "delta": x}], semantic_lever="short_wall_preservation")
        add("preserve_5_6_length_with_6_7_fix", [{"pair_index": 7, "operation": "translate_x", "delta": x}, {"pair_index": 7, "operation": "delta_field", "field": "bottom_y", "delta": y}], semantic_lever="primary_edge+short_wall_preservation")
        add("short_wall_compensated_mixed_move", [{"pair_index": 7, "operation": "translate_x", "delta": x}, {"pair_index": 7, "operation": "delta_field", "field": "bottom_y", "delta": y}], compensation_choices=[-0.25 * step, 0.0, 0.25 * step], semantic_lever="primary_edge+short_wall_compensation")

    for pair_index in cluster["height_outliers"]:
        for direction in (-1, 1):
            add("height_outlier_pull_top_y", [{"pair_index": pair_index, "operation": "delta_field", "field": "top_y", "delta": direction * step}], semantic_lever="wall_height")

    if secondary["enabled"]:
        for pair_index in secondary["allow_secondary_window_pairs"]:
            if pair_index in frozen:
                continue
            for field in secondary["allowed_movable_fields_for_secondary"]:
                for direction in (-1, 1):
                    operation = "translate_x" if field == "x" else "delta_field"
                    row = {"pair_index": pair_index, "operation": operation, "delta": direction * step * (0.5 if field == "x" else 1.0)}
                    if operation == "delta_field":
                        row["field"] = field
                    add("secondary_edge_2_3_semantic_probe", [row], semantic_lever="secondary_edge_2_3")
    return specs


def apply_action(
    pairs: Sequence[Mapping[str, Any]], action: Mapping[str, Any], *, compensation: float = 0.0
) -> list[dict[str, Any]]:
    output = copy.deepcopy(list(pairs))
    lookup = _pair_lookup(output)
    for operation in action["operations"]:
        pair = lookup[int(operation["pair_index"])]
        kind = operation["operation"]
        if kind == "align_midpoint_x":
            value = (float(pair["top"]["x"]) + float(pair["bottom"]["x"])) / 2
            pair["top"]["x"] = pair["bottom"]["x"] = value
        elif kind == "top_to_bottom_x":
            pair["top"]["x"] = float(pair["bottom"]["x"])
        elif kind == "bottom_to_top_x":
            pair["bottom"]["x"] = float(pair["top"]["x"])
        elif kind == "translate_x":
            for endpoint in ("top", "bottom"):
                pair[endpoint]["x"] = max(0.0, min(100.0, float(pair[endpoint]["x"]) + float(operation["delta"])))
        elif kind == "delta_field":
            endpoint, axis = operation["field"].split("_")
            pair[endpoint][axis] = max(0.0, min(100.0, float(pair[endpoint][axis]) + float(operation["delta"])))
        else:
            raise ValueError(f"unsupported M15.28 operation: {kind}")
    if action["family"] == "short_wall_compensated_mixed_move" and compensation:
        for pair_index in (5, 6):
            for endpoint in ("top", "bottom"):
                lookup[pair_index][endpoint]["x"] += compensation
    return output


def _short_deficit(score: Mapping[str, Any], edge: str = "5-6") -> float:
    return float(score.get("short_wall_deficits", {}).get(edge, 0.0))


def _candidate_rank(row: Mapping[str, Any]) -> tuple[Any, ...]:
    score = row["score_breakdown"]
    return (
        not row["m15_28_gate"]["passed"],
        not row["manual_review_candidate"],
        float(score["primary_edge_6_7_residual"]),
        abs(float(score["allowed_short_wall_deficit_delta"])),
        float(score["dominant_height_cluster_l1"]),
        float(score["movement_l1_ls_percent"]),
        row["candidate_id"],
    )


def _portfolio(rows: Sequence[Mapping[str, Any]], baseline_score: Mapping[str, Any]) -> dict[str, Any]:
    eligible = [row for row in rows if row["m15_28_gate"]["passed"]]

    def bucket(candidates: Sequence[Mapping[str, Any]], key: Any, empty: str) -> dict[str, Any]:
        return {"candidate": min(candidates, key=key) if candidates else None, "reason": None if candidates else empty}

    primary_before = float(baseline_score["primary_edge_6_7_residual"])
    return {
        "best_primary_candidate": bucket(eligible, lambda row: (row["score_breakdown"]["primary_edge_6_7_residual"], row["candidate_id"]), "no hard-gate and short-wall-band compliant candidate"),
        "best_height_candidate": bucket([row for row in eligible if row["score_breakdown"]["primary_edge_6_7_residual"] <= primary_before + 0.25], lambda row: (row["score_breakdown"]["dominant_height_cluster_l1"], row["candidate_id"]), "no height candidate preserves primary edge within 0.25 degrees"),
        "best_balanced_candidate": bucket(eligible, lambda row: (*row["hypothesis_ranking_key"], row["candidate_id"]), "no balanced candidate passed gates"),
        "best_short_wall_preserving_candidate": bucket(eligible, lambda row: (abs(row["score_breakdown"]["allowed_short_wall_deficit_delta"]), row["score_breakdown"]["primary_edge_6_7_residual"], row["candidate_id"]), "no short-wall preserving candidate passed gates"),
        "best_low_movement_candidate": bucket([row for row in eligible if primary_before - row["score_breakdown"]["primary_edge_6_7_residual"] >= 5.0], lambda row: (row["score_breakdown"]["movement_l1_ls_percent"], row["candidate_id"]), "no compliant candidate improves primary edge by at least 5 degrees"),
    }


def run_action_library(
    baseline_pairs: Sequence[Mapping[str, Any]],
    *,
    expert_assertion: Mapping[str, Any],
    projection_config: Mapping[str, Any],
    step_schedule: Sequence[float] = STEP_SCHEDULE,
    max_evaluations: int = MAX_EVALUATIONS,
) -> dict[str, Any]:
    valid_indices = sorted(_pair_lookup(baseline_pairs))
    assertions = normalize_expert_assertions(expert_assertion, valid_pair_indices=valid_indices, local_window=expert_assertion.get("candidate_window", []))
    if assertions is None:
        raise ValueError("expert assertion is required")
    secondary = validate_secondary_assertions(expert_assertion, valid_indices)
    baseline_variant = build_projection_variant("baseline", baseline_pairs, **projection_config)
    cluster = dominant_height_cluster(baseline_variant)
    constraints = _constraint_state(baseline_pairs, baseline_pairs, baseline_variant, assertions)
    baseline_score = _score_breakdown(baseline_variant, movement_l1=0.0, anchor_violations=constraints["anchor_violations"], assertion_violations=constraints["assertion_violations"], geometry_invalid_reasons=constraints["geometry_invalid_reasons"])
    from tools.paper_a_manhattan.manhattan_m1527_semantic_direct_search import _height_distance
    baseline_score["dominant_height_cluster_l1"] = _height_distance(baseline_variant, cluster["h_star"])
    baseline_score["legacy_score_role"] = "diagnostic_only"
    case_contract = build_case_contract(
        baseline_pairs,
        expert_assertions=expert_assertion,
        projection_metrics=baseline_variant["metrics"],
    )
    baseline_deficit = _short_deficit(baseline_score)
    seen = {_signature(baseline_pairs)}
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    for round_index, step in enumerate(step_schedule, 1):
        for action in build_action_specs(baseline_pairs, cluster, assertions, secondary, float(step)):
            candidate_pairs = apply_action(baseline_pairs, action)
            if action["family"] == "short_wall_compensated_mixed_move":
                choices = []
                for compensation in action["compensation_choices"]:
                    pairs = apply_action(baseline_pairs, action, compensation=float(compensation))
                    variant = build_projection_variant("compensation_probe", pairs, **projection_config)
                    movement, _, _ = _movement(baseline_pairs, pairs)
                    state = _constraint_state(baseline_pairs, pairs, variant, assertions)
                    score = _score_breakdown(variant, movement_l1=movement, anchor_violations=state["anchor_violations"], assertion_violations=state["assertion_violations"], geometry_invalid_reasons=state["geometry_invalid_reasons"])
                    choices.append((abs(_short_deficit(score) - baseline_deficit), abs(float(compensation)), float(compensation), pairs))
                _, _, selected_compensation, candidate_pairs = min(choices, key=lambda row: row[:3])
                action = {**action, "selected_compensation": selected_compensation}
            signature = _signature(candidate_pairs)
            if signature in seen or len(rows) >= max_evaluations:
                continue
            seen.add(signature)
            candidate_id = f"m1528_candidate_{len(rows) + 1:04d}"
            row = _evaluate(candidate_id, "baseline", "action_library", round_index, float(step), action, baseline_pairs, candidate_pairs, baseline_score, assertions, projection_config, cluster)
            deficit_delta = _short_deficit(row["score_breakdown"]) - baseline_deficit
            row["score_breakdown"]["allowed_short_wall_deficit_delta"] = deficit_delta
            row["score_breakdown"]["legacy_score_role"] = "diagnostic_only"
            candidate_variant = build_projection_variant(
                candidate_id,
                candidate_pairs,
                **projection_config,
            )
            row["constrained_evaluation"] = evaluate_hypothesis(
                baseline_variant,
                candidate_variant,
                baseline_pairs,
                candidate_pairs,
                case_contract,
                legacy_score_breakdown=row["score_breakdown"],
            )
            row["hypothesis_ranking_key"] = list(
                build_hypothesis_ranking_key(row["constrained_evaluation"])
            )
            band_ok = deficit_delta <= ALLOWED_SHORT_DEFICIT_BAND + 1e-12
            checks = {
                "assertion_compliant": row["assertion_compliant"],
                "geometry_valid": row["geometry_valid"],
                "allowed_short_wall_band": band_ok,
            }
            row["m15_28_gate"] = {"passed": all(checks.values()), "checks": checks}
            row["manual_review_candidate"] = bool(row["direct_ls_trial_allowed"] and band_ok)
            row["automatic_fix_claimed"] = False
            row["best_candidate_requires_visual_review"] = True
            if not band_ok:
                row["failure_reason"] = [*row["failure_reason"], "allowed_short_wall_deficit_band_exceeded"]
            rows.append(row)
            counts[action["family"]] += 1
        if len(rows) >= max_evaluations:
            break

    ranked = sorted(rows, key=lambda row: (*row["hypothesis_ranking_key"], row["candidate_id"]))
    portfolios = _portfolio(rows, baseline_score)
    structured_portfolio = build_hypothesis_portfolio(rows)
    available = any(row["manual_review_candidate"] for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "safety_boundary": dict(SAFETY_BOUNDARY),
        "case_contract": case_contract,
        "expert_assertions_used": assertions,
        "secondary_window": secondary,
        "dominant_height_cluster": cluster,
        "action_families": list(ACTION_FAMILIES),
        "search_config": {"step_schedule": list(step_schedule), "max_evaluations": max_evaluations, "randomness_used": False, "allowed_short_wall_deficit_band": ALLOWED_SHORT_DEFICIT_BAND, "order_mutation_allowed": False, "merge_delete_allowed": False, "topology_rewrite_allowed": False},
        "baseline": {"score_breakdown": baseline_score},
        "evaluation_count": len(rows),
        "family_evaluation_counts": dict(sorted(counts.items())),
        "top_candidates": ranked[:TOP_LIMIT],
        "portfolio_candidates": portfolios,
        "portfolio_ranking": structured_portfolio,
        "legacy_score_role": "diagnostic_only",
        "overall_verdict": {"manual_review_candidate_available": available, "automatic_fix_claimed": False, "best_candidate_requires_visual_review": True},
    }
