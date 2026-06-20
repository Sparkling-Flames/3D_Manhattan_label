"""Structured evaluator for expert-side Manhattan candidate hypotheses."""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence


EVALUATOR_VERSION = "manhattan_constrained_hypothesis_evaluator_v1"
UNRESOLVED_EDGE_DEG = 15.0
COLLAPSE_THRESHOLD = 0.05
HEIGHT_CLUSTER_GAP = 0.30
HARD_SEAM_WARNING_CODES = {"wrap_seam_broken", "wrap_or_seam_broken", "unresolved_wrap_seam"}
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
        if (
            not isinstance(row, Mapping)
            or row.get("from_pair") is None
            or row.get("to_pair") is None
            or not all(_finite(row.get(field)) for field in ("floor_wall_length", "short_wall_threshold", "angle_residual_deg"))
        ):
            continue
        direct = _edge_name(row["from_pair"], row["to_pair"])
        reverse = _edge_name(row["to_pair"], row["from_pair"])
        result[direct] = result[reverse] = row
    return result


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _projection_metric_errors(variant: Mapping[str, Any]) -> list[str]:
    walls = variant.get("metrics", {}).get("floorprint", {}).get("walls")
    heights = variant.get("metrics", {}).get("heights", {}).get("pairs")
    pairs = variant.get("projection", {}).get("pairs")
    errors: list[str] = []
    if not isinstance(walls, list) or not walls:
        errors.append("missing_floorprint_walls")
    elif any(
        not isinstance(row, Mapping)
        or row.get("from_pair") is None
        or row.get("to_pair") is None
        or not all(_finite(row.get(field)) for field in ("floor_wall_length", "short_wall_threshold", "angle_residual_deg"))
        for row in walls
    ):
        errors.append("invalid_floorprint_wall_values")
    if not isinstance(heights, list) or not heights:
        errors.append("missing_height_pairs")
    elif any(
        not isinstance(row, Mapping)
        or row.get("effective_pair_index") is None
        or not _finite(row.get("wall_height"))
        for row in heights
    ):
        errors.append("invalid_height_pair_values")
    if not isinstance(pairs, list) or not pairs:
        errors.append("missing_projection_pairs")
    elif any(
        not isinstance(row, Mapping)
        or row.get("effective_pair_index") is None
        or not _finite(row.get("top_bottom_x_residual"))
        for row in pairs
    ):
        errors.append("invalid_projection_pair_values")
    return errors


def dominant_height_cluster_from_rows(
    height_rows: Sequence[Mapping[str, Any]],
    *,
    target_pair_indices: Sequence[int] | None = None,
    gap_threshold: float = HEIGHT_CLUSTER_GAP,
) -> dict[str, Any]:
    """Largest connected projected-height component; minimum MAD breaks ties."""
    targets = list(target_pair_indices) if target_pair_indices is not None else [int(row["effective_pair_index"]) for row in height_rows]
    lookup = {int(row["effective_pair_index"]): float(row["wall_height"]) for row in height_rows}
    rows = sorted((lookup[index], index) for index in targets if index in lookup)
    if not rows:
        raise ValueError("dominant height cluster requires projected wall heights")
    components: list[list[tuple[float, int]]] = []
    for row in rows:
        if not components or row[0] - components[-1][-1][0] > gap_threshold:
            components.append([row])
        else:
            components[-1].append(row)

    def summary(component: Sequence[tuple[float, int]]) -> tuple[int, float, float]:
        values = [row[0] for row in component]
        center = statistics.median(values)
        mad = statistics.median(abs(value - center) for value in values)
        return len(component), mad, center

    selected = min(components, key=lambda component: (-summary(component)[0], summary(component)[1], summary(component)[2]))
    _, mad, h_star = summary(selected)
    members = sorted(row[1] for row in selected)
    return {
        "source_metric": "projected_wall_height",
        "target_pair_indices": targets,
        "method": "largest_gap_connected_cluster_then_minimum_mad",
        "gap_threshold": gap_threshold,
        "h_star": h_star,
        "cluster_members": members,
        "mad": mad,
        "height_outliers": [index for index in targets if index in lookup and index not in members],
        "projected_wall_heights": {str(index): lookup[index] for index in targets if index in lookup},
    }


def _unauthorized_mutations(
    before: Mapping[int, Mapping[str, Any]],
    after: Mapping[int, Mapping[str, Any]],
    movable_fields_by_pair: Mapping[str, Any],
) -> list[str]:
    allowed = {int(index): set(fields) for index, fields in movable_fields_by_pair.items()}
    violations: list[str] = []
    for index in before.keys() & after.keys():
        for endpoint in ("top", "bottom"):
            for axis in ("x", "y"):
                if float(before[index][endpoint][axis]) == float(after[index][endpoint][axis]):
                    continue
                field = "x" if axis == "x" else f"{endpoint}_y"
                if field not in allowed.get(index, set()):
                    violations.append(f"unauthorized_mutation_pair_{index}_{field}")
    return violations


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
    baseline_metric_errors = _projection_metric_errors(baseline_variant)
    candidate_metric_errors = _projection_metric_errors(candidate_variant)
    metric_errors = [*(f"baseline:{reason}" for reason in baseline_metric_errors), *candidate_metric_errors]
    baseline_walls, candidate_walls = _walls(baseline_variant), _walls(candidate_variant)
    baseline_order = [int(row["effective_pair_index"]) for row in baseline_pairs]
    candidate_order = [int(row["effective_pair_index"]) for row in candidate_pairs]
    topology_valid = set(before) == set(after) and len(before) == len(after)
    no_order_mutation = baseline_order == candidate_order
    no_pair_fold = all(float(row["top"]["y"]) < float(row["bottom"]["y"]) for row in candidate_pairs)
    no_self_intersection = not bool(candidate_variant.get("metrics", {}).get("floorprint", {}).get("self_intersection"))
    protected_moved = [index for index in case_contract.get("protected_pairs", []) if index in before and before[index] != after.get(index)]
    unauthorized_mutations = _unauthorized_mutations(
        before, after, case_contract.get("movable_fields_by_pair", {})
    )
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
    warning_codes = set(candidate_variant.get("projection", {}).get("warning_codes", []))
    warning_codes.update(str(row["code"]) for row in warnings if isinstance(row, Mapping) and row.get("code"))
    seam_diagnostics = [str(value) for value in warnings if not isinstance(value, Mapping) and ("seam" in str(value).lower() or "wrap" in str(value).lower())]
    wrap_ok = not bool(warning_codes & HARD_SEAM_WARNING_CODES)
    projection_valid = not metric_errors
    assertion_valid = not protected_moved and not distinct_failures and not unauthorized_mutations
    checks = {
        "topology_valid": topology_valid,
        "assertion_valid": assertion_valid,
        "projection_valid": projection_valid,
        "no_self_intersection": no_self_intersection,
        "no_pair_fold": no_pair_fold,
        "no_unapproved_order_mutation": no_order_mutation,
        "keep_distinct_pairs_not_collapsed": not distinct_failures,
        "protected_pairs_not_moved": not protected_moved,
        "authorized_mutations_only": not unauthorized_mutations,
        "wrap_or_seam_not_broken": wrap_ok,
    }
    hard_reasons = [name for name, passed in checks.items() if not passed]
    hard_reasons.extend(unauthorized_mutations)
    hard_reasons.extend(f"projection_metrics:{reason}" for reason in metric_errors)
    feasibility = {
        **checks,
        "hard_gate_passed": not hard_reasons,
        "hard_failure_reasons": hard_reasons,
        "projection_metric_errors": metric_errors,
        "wrap_or_seam_gate_status": "structured_codes_checked" if warning_codes else "not_available_diagnostic_only",
        "wrap_or_seam_diagnostic_warnings": seam_diagnostics,
    }

    wall_rows = list(candidate_variant.get("metrics", {}).get("floorprint", {}).get("walls", []))
    wall_residuals = [float(row["angle_residual_deg"]) for row in wall_rows if _finite(row.get("angle_residual_deg"))]
    turn_rows = list(candidate_variant.get("metrics", {}).get("corner_turns", {}).get("corners", []))
    turn_residuals = [float(row["angle_to_90_residual_deg"]) for row in turn_rows if _finite(row.get("angle_to_90_residual_deg"))]
    local_edges = list(case_contract.get("primary_edges", [])) + list(case_contract.get("secondary_edges", []))
    local_residuals = [float(candidate_walls[name]["angle_residual_deg"]) for name in local_edges if name in candidate_walls]
    projection_pairs = list(candidate_variant.get("projection", {}).get("pairs", []))
    column_residuals = [float(row["top_bottom_x_residual"]) for row in projection_pairs if _finite(row.get("top_bottom_x_residual"))]
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
    valid_height_rows = [row for row in height_rows if row.get("effective_pair_index") is not None and _finite(row.get("wall_height"))]
    cluster = dominant_height_cluster_from_rows(valid_height_rows) if valid_height_rows else None
    h_star = cluster["h_star"] if cluster else None
    residual_by_pair = {
        int(row["effective_pair_index"]): abs(float(row["wall_height"]) - h_star)
        for row in valid_height_rows
    } if h_star is not None else {}
    residuals = list(residual_by_pair.values())
    mad = cluster["mad"] if cluster else None
    height_outliers = cluster["height_outliers"] if cluster else []
    height = {
        "dominant_height_h_star": h_star,
        "height_cluster_mad": mad,
        "height_outlier_l1": sum(residuals),
        "max_height_residual": max(residuals, default=0.0),
        "top_bottom_column_residual": sum(column_residuals) / len(column_residuals) if column_residuals else None,
        "height_outlier_pairs": height_outliers,
        "height_correction_direction": None,
        "dominant_height_cluster_members": cluster["cluster_members"] if cluster else [],
        "dominant_height_cluster_method": cluster["method"] if cluster else None,
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
        "evaluation_status": "incomplete_metrics" if metric_errors else "complete",
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
