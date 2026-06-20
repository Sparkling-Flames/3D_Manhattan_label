"""Structured evaluator for expert-side Manhattan candidate hypotheses."""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence


EVALUATOR_VERSION = "manhattan_constrained_hypothesis_evaluator_v1"
UNRESOLVED_EDGE_DEG = 15.0
COLLAPSE_THRESHOLD = 0.05
EVIDENCE_FIELDS = (
    "hohonet_wallwall_peak_alignment",
    "hohonet_floor_boundary_rmse_delta",
    "hohonet_ceiling_boundary_rmse_delta",
    "candidate_corner_column_delta",
    "seam_consistency_delta",
    "visual_conflict_flags",
    "image_edge_support_optional",
)


def _pairs(rows: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    return {int(row["effective_pair_index"]): row for row in rows}


def _edge_name(left: Any, right: Any | None = None) -> str:
    if right is None:
        if isinstance(left, str):
            return left
        left, right = left
    return f"{int(left)}-{int(right)}"


def _walls(variant: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = variant.get("metrics", {}).get("floorprint", {}).get("walls", [])
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        direct = _edge_name(row["from_pair"], row["to_pair"])
        reverse = _edge_name(row["to_pair"], row["from_pair"])
        result[direct] = result[reverse] = row
    return result


def _movement(
    baseline_pairs: Sequence[Mapping[str, Any]], candidate_pairs: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    before, after = _pairs(baseline_pairs), _pairs(candidate_pairs)
    per_pair: dict[int, float] = {}
    changed_endpoints: set[tuple[int, str]] = set()
    for index in before.keys() & after.keys():
        total = 0.0
        for endpoint in ("top", "bottom"):
            endpoint_changed = False
            for axis in ("x", "y"):
                delta = abs(float(after[index][endpoint][axis]) - float(before[index][endpoint][axis]))
                total += delta
                endpoint_changed |= delta > 1e-12
            if endpoint_changed:
                changed_endpoints.add((index, endpoint))
        if total > 1e-12:
            per_pair[index] = total
    total = sum(per_pair.values())
    denominator = max(1, len(before)) * 400.0
    maximum = max(per_pair.values(), default=0.0)
    return {
        "movement_l1_normalized": total / denominator,
        "movement_max_pair": maximum / 400.0,
        "changed_pair_count": len(per_pair),
        "changed_endpoint_count": len(changed_endpoints),
        "movement_concentration": maximum / total if total else 0.0,
        "edit_explainability": "single_pair" if len(per_pair) == 1 else "localized" if len(per_pair) <= 3 else "distributed",
        "manual_adjustment_cost_proxy": len(changed_endpoints) + total / 100.0,
    }


def _evidence(variant: Mapping[str, Any]) -> dict[str, Any]:
    source = variant.get("evidence") or variant.get("metrics", {}).get("evidence") or {}
    present = [field for field in EVIDENCE_FIELDS if field in source]
    status = "available" if len(present) == len(EVIDENCE_FIELDS) else "partial" if present else "unavailable"
    return {
        **{field: source.get(field) for field in EVIDENCE_FIELDS},
        "evidence_status": status,
        "missing_fields": [field for field in EVIDENCE_FIELDS if field not in source],
    }


def evaluate_hypothesis(
    baseline_variant: Mapping[str, Any],
    candidate_variant: Mapping[str, Any],
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    case_contract: Mapping[str, Any],
    legacy_score_breakdown: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one candidate. Hard failures are gates, never numeric penalties."""
    before, after = _pairs(baseline_pairs), _pairs(candidate_pairs)
    baseline_walls, candidate_walls = _walls(baseline_variant), _walls(candidate_variant)
    baseline_order = [int(row["effective_pair_index"]) for row in baseline_pairs]
    candidate_order = [int(row["effective_pair_index"]) for row in candidate_pairs]
    topology_valid = set(before) == set(after) and len(before) == len(after)
    no_order_mutation = baseline_order == candidate_order
    no_pair_fold = all(float(row["top"]["y"]) < float(row["bottom"]["y"]) for row in candidate_pairs)
    no_self_intersection = not bool(candidate_variant.get("metrics", {}).get("floorprint", {}).get("self_intersection"))
    protected_moved = [index for index in case_contract.get("protected_pairs", []) if index in before and before[index] != after.get(index)]
    distinct_failures: list[str] = []
    margins: list[float] = []
    for pair in case_contract.get("keep_distinct_pairs", []):
        name = _edge_name(pair)
        wall = candidate_walls.get(name)
        if wall is None or float(wall["floor_wall_length"]) < COLLAPSE_THRESHOLD:
            distinct_failures.append(name)
        elif wall:
            margins.append(float(wall["floor_wall_length"]) - COLLAPSE_THRESHOLD)
    warnings = list(candidate_variant.get("projection", {}).get("warnings", []))
    wrap_ok = not any("seam" in str(value).lower() or "wrap" in str(value).lower() for value in warnings)
    projection_valid = bool(candidate_variant.get("metrics")) and not any(
        "projection" in str(value).lower() and "invalid" in str(value).lower() for value in warnings
    )
    assertion_valid = not protected_moved and not distinct_failures
    checks = {
        "topology_valid": topology_valid,
        "assertion_valid": assertion_valid,
        "projection_valid": projection_valid,
        "no_self_intersection": no_self_intersection,
        "no_pair_fold": no_pair_fold,
        "no_unapproved_order_mutation": no_order_mutation,
        "keep_distinct_pairs_not_collapsed": not distinct_failures,
        "protected_pairs_not_moved": not protected_moved,
        "wrap_or_seam_not_broken": wrap_ok,
    }
    hard_reasons = [name for name, passed in checks.items() if not passed]
    feasibility = {**checks, "hard_gate_passed": not hard_reasons, "hard_failure_reasons": hard_reasons}

    wall_rows = list(candidate_variant.get("metrics", {}).get("floorprint", {}).get("walls", []))
    wall_residuals = [float(row["angle_residual_deg"]) for row in wall_rows]
    turn_rows = list(candidate_variant.get("metrics", {}).get("corner_turns", {}).get("corners", []))
    turn_residuals = [float(row["angle_to_90_residual_deg"]) for row in turn_rows if row.get("angle_to_90_residual_deg") is not None]
    local_edges = list(case_contract.get("primary_edges", [])) + list(case_contract.get("secondary_edges", []))
    local_residuals = [float(candidate_walls[name]["angle_residual_deg"]) for name in local_edges if name in candidate_walls]
    projection_pairs = list(candidate_variant.get("projection", {}).get("pairs", []))
    column_residuals = [float(row.get("top_bottom_x_residual", 0.0)) for row in projection_pairs]
    manhattan = {
        "direction_family_fit": None,
        "direction_family_fit_unavailable_reason": "v1 projection metrics expose nearest-axis residuals, not fitted direction-family labels",
        "wall_residual_median": statistics.median(wall_residuals) if wall_residuals else math.inf,
        "wall_residual_max": max(wall_residuals, default=math.inf),
        "turn_residual_median": statistics.median(turn_residuals) if turn_residuals else None,
        "turn_residual_max": max(turn_residuals) if turn_residuals else None,
        "parallel_family_residual": None,
        "parallel_family_residual_unavailable_reason": "parallel family grouping is not emitted by the current projection core",
        "local_window_residual": sum(local_residuals) if local_residuals else None,
        "unresolved_edge_count": sum(value > UNRESOLVED_EDGE_DEG for value in wall_residuals),
        "floor_ceiling_column_consistency": statistics.median(column_residuals) if column_residuals else None,
    }

    height_rows = list(candidate_variant.get("metrics", {}).get("heights", {}).get("pairs", []))
    heights = [float(row["wall_height"]) for row in height_rows]
    h_star = statistics.median(heights) if heights else None
    residual_by_pair = {
        int(row["effective_pair_index"]): abs(float(row["wall_height"]) - h_star)
        for row in height_rows
    } if h_star is not None else {}
    residuals = list(residual_by_pair.values())
    mad = statistics.median(residuals) if residuals else None
    threshold = max(0.15, 2.5 * mad) if mad is not None else math.inf
    height_outliers = sorted(index for index, value in residual_by_pair.items() if value > threshold)
    height = {
        "dominant_height_h_star": h_star,
        "height_cluster_mad": mad,
        "height_outlier_l1": sum(residuals),
        "max_height_residual": max(residuals, default=0.0),
        "top_bottom_column_residual": sum(column_residuals) / len(column_residuals) if column_residuals else None,
        "height_outlier_pairs": height_outliers,
        "height_correction_direction": None,
    }

    baseline_short = {name for name, row in baseline_walls.items() if row.get("short_wall") and int(name.split("-")[0]) < int(name.split("-")[1])}
    candidate_short = {name for name, row in candidate_walls.items() if row.get("short_wall") and int(name.split("-")[0]) < int(name.split("-")[1])}
    # Use undirected canonical names because each wall is indexed in both directions.
    canonical = lambda name: "-".join(map(str, sorted(map(int, name.split("-")))))
    baseline_short = {canonical(name) for name in baseline_short}
    candidate_short = {canonical(name) for name in candidate_short}
    allowed_short = {canonical(str(name)) for name in case_contract.get("allowed_short_edges", [])}
    new_short = sorted(candidate_short - baseline_short)
    preserved_short = sorted(candidate_short & baseline_short)
    collapsed_short = sorted(
        _edge_name(pair)
        for pair in case_contract.get("keep_distinct_pairs", [])
        if _edge_name(pair) in distinct_failures
    )
    def deficit(walls: Mapping[str, Mapping[str, Any]], names: set[str]) -> float:
        return sum(max(0.0, float(walls[name]["short_wall_threshold"]) - float(walls[name]["floor_wall_length"])) for name in names if name in walls)
    movement = _movement(baseline_pairs, candidate_pairs)
    plausibility_reasons = [f"new_short_wall:{name}" for name in new_short if name not in allowed_short]
    plausibility_reasons += [f"short_wall_collapsed:{name}" for name in collapsed_short]
    plausibility = {
        "new_short_wall_created": new_short,
        "existing_short_wall_preserved": preserved_short,
        "short_wall_collapsed": collapsed_short,
        "short_wall_deficit_delta": deficit(candidate_walls, candidate_short) - deficit(baseline_walls, baseline_short),
        "short_wall_explains_dense_corner": bool(set(preserved_short) & allowed_short),
        "keep_distinct_margin": min(margins) if margins else None,
        "movement_l1_normalized": movement["movement_l1_normalized"],
        "movement_max_pair": movement["movement_max_pair"],
        "changed_pair_count": movement["changed_pair_count"],
        "plausibility_failure_reasons": plausibility_reasons,
    }
    legacy = dict(legacy_score_breakdown or {})
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "feasibility": feasibility,
        "manhattan_feasibility": manhattan,
        "height_consistency": height,
        "layout_plausibility": plausibility,
        "evidence_consistency": _evidence(candidate_variant),
        "movement_edit_cost": movement,
        "legacy_score_breakdown": legacy,
        "local_score_total": legacy.get("local_score_total"),
        "legacy_score_role": "diagnostic_only",
        "safety_boundary": {
            "automatic_apply": False,
            "annotation_patch_generated": False,
            "annotation_writeback": False,
            "worker_facing": False,
            "routing_input": False,
        },
    }


def build_hypothesis_ranking_key(evaluation: Mapping[str, Any]) -> tuple[Any, ...]:
    """Lexicographic ranking key; legacy score is the final fallback only."""
    feasibility = evaluation["feasibility"]
    manhattan = evaluation["manhattan_feasibility"]
    height = evaluation["height_consistency"]
    evidence = evaluation["evidence_consistency"]
    plausibility = evaluation["layout_plausibility"]
    movement = evaluation["movement_edit_cost"]
    evidence_regression = 0
    if evidence["evidence_status"] != "unavailable":
        numeric_deltas = [evidence.get(name) for name in ("hohonet_floor_boundary_rmse_delta", "hohonet_ceiling_boundary_rmse_delta", "candidate_corner_column_delta", "seam_consistency_delta")]
        evidence_regression = sum(float(value) > 0 for value in numeric_deltas if isinstance(value, (int, float))) + bool(evidence.get("visual_conflict_flags"))
    legacy = evaluation.get("local_score_total")
    return (
        not bool(feasibility["hard_gate_passed"]),
        int(manhattan["unresolved_edge_count"]),
        float(manhattan["wall_residual_max"]),
        float(manhattan["wall_residual_median"]),
        float(height["height_outlier_l1"]),
        evidence_regression,
        len(plausibility["short_wall_collapsed"]),
        len(plausibility["new_short_wall_created"]),
        max(0.0, float(plausibility["short_wall_deficit_delta"])),
        float(movement["movement_l1_normalized"]),
        float(movement["manual_adjustment_cost_proxy"]),
        float(legacy) if legacy is not None else math.inf,
    )
