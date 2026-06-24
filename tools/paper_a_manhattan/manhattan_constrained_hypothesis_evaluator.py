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


def _angular_distance_deg(left: float, right: float, period: float) -> float:
    delta = abs((left - right) % period)
    return min(delta, period - delta)


def _direction_family_diagnostics(
    wall_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Fit one orthogonal frame from explicit wall headings; never infer missing headings."""
    if len(wall_rows) < 2:
        return None, None, "insufficient_walls"
    headings = [row for row in wall_rows if _finite(row.get("direction_deg"))]
    if len(headings) != len(wall_rows):
        return None, None, "unavailable_due_to_missing_wall_heading"

    folded = [float(row["direction_deg"]) % 90.0 for row in headings]
    frame_offset = min(
        folded,
        key=lambda candidate: (
            statistics.median(
                _angular_distance_deg(value, candidate, 90.0) for value in folded
            ),
            sum(_angular_distance_deg(value, candidate, 90.0) for value in folded),
            max(_angular_distance_deg(value, candidate, 90.0) for value in folded),
            candidate,
        ),
    )
    axes = (frame_offset, (frame_offset + 90.0) % 180.0)
    assignments: list[dict[str, Any]] = []
    for position, row in enumerate(headings):
        heading = float(row["direction_deg"]) % 180.0
        family_index = min(
            range(2), key=lambda index: (_angular_distance_deg(heading, axes[index], 180.0), index)
        )
        assignments.append(
            {
                "wall_index": row.get("wall_index", position + 1),
                "from_pair": row.get("from_pair"),
                "to_pair": row.get("to_pair"),
                "heading_deg": heading,
                "assigned_family": f"family_{family_index}",
                "assigned_axis_heading_deg": axes[family_index],
                "residual_deg": _angular_distance_deg(heading, axes[family_index], 180.0),
            }
        )

    families = []
    for index, axis in enumerate(axes):
        family_id = f"family_{index}"
        members = [row for row in assignments if row["assigned_family"] == family_id]
        residuals = [row["residual_deg"] for row in members]
        families.append(
            {
                "family_id": family_id,
                "axis_heading_deg": axis,
                "wall_count": len(members),
                "residual_median_deg": statistics.median(residuals) if residuals else None,
                "residual_max_deg": max(residuals) if residuals else None,
            }
        )
    dominant = min(
        families,
        key=lambda family: (
            -family["wall_count"],
            family["residual_median_deg"] if family["residual_median_deg"] is not None else math.inf,
            family["family_id"],
        ),
    )
    residuals = [row["residual_deg"] for row in assignments]
    fit = {
        "status": "available",
        "method": "wall_direction_deg_l1_frame_mod_90_v1",
        "frame_offset_deg": frame_offset,
        "dominant_family": dict(dominant),
        "families": families,
        "assignments": assignments,
        "residual_summary": {
            "median_deg": statistics.median(residuals),
            "max_deg": max(residuals),
            "wall_count": len(assignments),
        },
    }

    pair_residuals = []
    family_summaries = []
    for family in families:
        members = [row for row in assignments if row["assigned_family"] == family["family_id"]]
        values = [
            _angular_distance_deg(left["heading_deg"], right["heading_deg"], 180.0)
            for index, left in enumerate(members)
            for right in members[index + 1 :]
        ]
        pair_residuals.extend(values)
        family_summaries.append(
            {
                "family_id": family["family_id"],
                "pair_count": len(values),
                "median_deg": statistics.median(values) if values else None,
                "max_deg": max(values) if values else None,
            }
        )
    parallel = None if not pair_residuals else {
        "status": "available",
        "method": "within_assigned_family_pairwise_heading_residual_v1",
        "median_deg": statistics.median(pair_residuals),
        "max_deg": max(pair_residuals),
        "pair_count": len(pair_residuals),
        "families": family_summaries,
    }
    return fit, parallel, "available" if parallel is not None else "insufficient_same_family_pairs"


def _plane_proxy_metrics(
    manhattan: Mapping[str, Any],
    height: Mapping[str, Any],
    floorprint: Mapping[str, Any],
) -> dict[str, Any]:
    """Materialize geometry-only plane proxies; this is not depth-based plane fitting."""
    direction = manhattan.get("direction_family_fit")
    parallel = manhattan.get("parallel_family_residual")
    if isinstance(direction, Mapping):
        plane_assignment = {
            "status": "available",
            "method": "direction_family_assignments_as_vertical_plane_families_v0",
            "frame_offset_deg": direction["frame_offset_deg"],
            "plane_families": [
                {
                    "plane_family_id": family["family_id"],
                    "wall_axis_heading_deg": family["axis_heading_deg"],
                    "wall_count": family["wall_count"],
                }
                for family in direction["families"]
            ],
            "wall_assignments": [
                {
                    "wall_index": row["wall_index"],
                    "from_pair": row["from_pair"],
                    "to_pair": row["to_pair"],
                    "plane_family_id": row["assigned_family"],
                    "heading_residual_deg": row["residual_deg"],
                }
                for row in direction["assignments"]
            ],
        }
    else:
        plane_assignment = {
            "status": "unavailable",
            "method": "direction_family_assignments_as_vertical_plane_families_v0",
            "unavailable_reason": manhattan.get("direction_family_fit_unavailable_reason"),
        }

    parallel_consistency = (
        {
            "status": "available",
            "method": "direction_family_pairwise_heading_residual_v0",
            "median_deg": parallel["median_deg"],
            "max_deg": parallel["max_deg"],
            "pair_count": parallel["pair_count"],
        }
        if isinstance(parallel, Mapping)
        else {
            "status": "unavailable",
            "method": "direction_family_pairwise_heading_residual_v0",
            "median_deg": None,
            "max_deg": None,
            "pair_count": 0,
            "unavailable_reason": manhattan.get("parallel_family_residual_unavailable_reason"),
        }
    )

    populated_families = (
        [family for family in direction["families"] if family["wall_count"] > 0]
        if isinstance(direction, Mapping)
        else []
    )
    if len(populated_families) == 2:
        separation = _angular_distance_deg(
            populated_families[0]["axis_heading_deg"],
            populated_families[1]["axis_heading_deg"],
            180.0,
        )
        orthogonal_consistency = {
            "status": "available",
            "method": "fitted_plane_family_axis_separation_v0",
            "axis_separation_deg": separation,
            "orthogonal_residual_deg": abs(90.0 - separation),
        }
    else:
        orthogonal_consistency = {
            "status": "unavailable",
            "method": "fitted_plane_family_axis_separation_v0",
            "axis_separation_deg": None,
            "orthogonal_residual_deg": None,
            "unavailable_reason": "insufficient_populated_direction_families",
        }

    height_available = _finite(height.get("dominant_height_h_star"))
    height_consistency = {
        "status": "available" if height_available else "unavailable",
        "method": "dominant_projected_wall_height_cluster_v0",
        "dominant_height_h_star": height.get("dominant_height_h_star"),
        "height_cluster_mad": height.get("height_cluster_mad"),
        "max_height_residual": height.get("max_height_residual") if height_available else None,
        "height_outlier_pairs": list(height.get("height_outlier_pairs", [])),
        "unavailable_reason": None if height_available else "missing_projected_wall_heights",
    }

    walls = list(floorprint.get("walls", []))
    wall_residuals = [
        float(row["angle_residual_deg"])
        for row in walls
        if isinstance(row, Mapping) and _finite(row.get("angle_residual_deg"))
    ]
    floor_available = bool(wall_residuals)
    floor_residual = {
        "status": "available" if floor_available else "unavailable",
        "method": "structured_floorprint_wall_residual_proxy_v0_no_depth_no_plane_fit",
        "wall_residual_median_deg": statistics.median(wall_residuals) if floor_available else None,
        "wall_residual_max_deg": max(wall_residuals) if floor_available else None,
        "unresolved_edge_count": manhattan.get("unresolved_edge_count") if floor_available else None,
        "self_intersection": bool(floorprint.get("self_intersection")) if floor_available else None,
        "unavailable_reason": None if floor_available else "missing_floorprint_wall_residuals",
    }

    components = {
        "plane_family_assignment": plane_assignment,
        "wall_plane_parallel_consistency": parallel_consistency,
        "wall_plane_orthogonal_consistency": orthogonal_consistency,
        "dominant_height_plane_consistency": height_consistency,
        "floor_polygon_plane_proxy_residual": floor_residual,
    }
    missing = [name for name, value in components.items() if value["status"] != "available"]
    available_count = len(components) - len(missing)
    status = "available" if not missing else "partial_available" if available_count else "unavailable"
    return {
        "plane_proxy_version": "plane_proxy_metrics_v0",
        "status": status,
        "plane_proxy_status": status,
        **components,
        "unavailable_reason": (
            None if status == "available" else
            "missing_or_insufficient_proxy_inputs" if status == "partial_available" else
            "no_plane_proxy_inputs_available"
        ),
        "missing_fields": missing,
        "scope_boundary": {
            "geometry_proxy_only": True,
            "depth_model_used": False,
            "geolayout_reproduction": False,
            "column_evidence_layer": False,
        },
    }


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
    required = EVIDENCE_FIELDS[:-1]
    present = [field for field in required if source.get(field) is not None]
    status = source.get("evidence_status")
    if status not in {"available", "partial", "unavailable"}:
        status = "available" if len(present) == len(required) else "partial" if present else "unavailable"
    return {
        **{field: source.get(field) for field in EVIDENCE_FIELDS},
        "evidence_status": status,
        "evidence_version": source.get("evidence_version"),
        "source_provenance": source.get("source_provenance"),
        "candidate_preference_authorized": bool(
            source.get("candidate_preference_authorized", status == "available")
        ),
        "candidate_specific_geometry": source.get("candidate_specific_geometry"),
        "unavailable_reason": source.get("unavailable_reason"),
        "missing_fields": list(source.get("missing_fields") or [field for field in required if source.get(field) is None]),
    }


def evaluate_hypothesis(
    baseline_variant: Mapping[str, Any],
    candidate_variant: Mapping[str, Any],
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    case_contract: Mapping[str, Any],
    legacy_score_breakdown: Mapping[str, Any] | None = None,
    legacy_trial_allowed: bool | None = None,
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
    direction_fit, parallel_residual, direction_status = _direction_family_diagnostics(wall_rows)
    parallel_status = direction_status if direction_fit is None else (
        "available" if parallel_residual is not None else "insufficient_same_family_pairs"
    )
    manhattan = {
        "direction_family_fit": direction_fit,
        "direction_family_fit_status": "available" if direction_fit is not None else direction_status,
        "direction_family_fit_unavailable_reason": None if direction_fit is not None else direction_status,
        "wall_residual_median": statistics.median(wall_residuals) if wall_residuals else math.inf,
        "wall_residual_max": max(wall_residuals, default=math.inf),
        "turn_residual_median": statistics.median(turn_residuals) if turn_residuals else None,
        "turn_residual_max": max(turn_residuals) if turn_residuals else None,
        "parallel_family_residual": parallel_residual,
        "parallel_family_residual_status": parallel_status,
        "parallel_family_residual_unavailable_reason": None if parallel_residual is not None else parallel_status,
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
    plane_proxy = _plane_proxy_metrics(
        manhattan,
        height,
        candidate_variant.get("metrics", {}).get("floorprint", {}),
    )

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
    baseline_wall_residuals = [
        float(row["angle_residual_deg"])
        for row in baseline_variant.get("metrics", {}).get("floorprint", {}).get("walls", [])
        if _finite(row.get("angle_residual_deg"))
    ]
    baseline_local_residuals = [
        float(baseline_walls[name]["angle_residual_deg"])
        for name in local_edges
        if name in baseline_walls
    ]
    baseline_height_rows = [
        row
        for row in baseline_variant.get("metrics", {}).get("heights", {}).get("pairs", [])
        if row.get("effective_pair_index") is not None and _finite(row.get("wall_height"))
    ]
    baseline_cluster = dominant_height_cluster_from_rows(baseline_height_rows) if baseline_height_rows else None
    baseline_height_l1 = (
        sum(abs(float(row["wall_height"]) - baseline_cluster["h_star"]) for row in baseline_height_rows)
        if baseline_cluster
        else math.inf
    )
    improved = bool(
        (
            wall_residuals
            and baseline_wall_residuals
            and (
            max(wall_residuals) < max(baseline_wall_residuals) - 1e-9
            or statistics.median(wall_residuals) < statistics.median(baseline_wall_residuals) - 1e-9
            )
        )
        or (local_residuals and baseline_local_residuals and sum(local_residuals) < sum(baseline_local_residuals) - 1e-9)
        or height["height_outlier_l1"] < baseline_height_l1 - 1e-9
    )
    evidence = _evidence(candidate_variant)
    manual_evidence = dict(
        candidate_variant.get("manual_evidence")
        or {
            "required": False,
            "status": "not_required",
            "schema_version": None,
        }
    )
    if metric_errors:
        decision_class = "diagnostic_only_incomplete_metrics"
    elif not feasibility["hard_gate_passed"]:
        decision_class = "suppressed_hard_constraint"
    elif not improved:
        decision_class = "hard_feasible_neutral"
    elif legacy_trial_allowed is False:
        decision_class = "legacy_trial_blocked"
    elif evidence["evidence_status"] != "available":
        decision_class = "hard_feasible_improving_evidence_unavailable"
    else:
        decision_class = "hard_feasible_improving_evidence_supported"
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "evaluation_status": "incomplete_metrics" if metric_errors else "complete",
        "decision_class": decision_class,
        "is_improving_hypothesis": improved,
        "feasibility": feasibility,
        "manhattan_feasibility": manhattan,
        "height_consistency": height,
        "plane_proxy_metrics": plane_proxy,
        "layout_plausibility": plausibility,
        "column_evidence": evidence,
        "evidence_consistency": evidence,
        "manual_evidence": manual_evidence,
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


def build_hypothesis_ranking_layers(
    evaluation: Mapping[str, Any],
) -> dict[str, tuple[Any, ...]]:
    """Return explicit L0-L5 lexicographic groups for active ranking."""
    feasibility = evaluation["feasibility"]
    manhattan = evaluation["manhattan_feasibility"]
    height = evaluation["height_consistency"]
    evidence = evaluation["evidence_consistency"]
    plane = evaluation.get("plane_proxy_metrics", {})
    plausibility = evaluation["layout_plausibility"]
    movement = evaluation["movement_edit_cost"]
    manual = evaluation.get("manual_evidence", {})
    direction = manhattan.get("direction_family_fit")
    parallel = manhattan.get("parallel_family_residual")
    direction_summary = direction.get("residual_summary", {}) if isinstance(direction, Mapping) else {}
    deltas = tuple(
        float(evidence.get(name))
        if isinstance(evidence.get(name), (int, float))
        else math.inf
        for name in (
            "candidate_corner_column_delta",
            "hohonet_floor_boundary_rmse_delta",
            "hohonet_ceiling_boundary_rmse_delta",
            "seam_consistency_delta",
        )
    )
    finite_deltas = [value for value in deltas if math.isfinite(value)]
    plane_parallel = plane.get("wall_plane_parallel_consistency", {})
    plane_orthogonal = plane.get("wall_plane_orthogonal_consistency", {})
    floor_plane = plane.get("floor_polygon_plane_proxy_residual", {})
    manual_blocked = bool(manual.get("required")) and manual.get("status") != "available"

    metric = lambda value: float(value) if isinstance(value, (int, float)) else math.inf
    return {
        "L0": (not bool(feasibility["hard_gate_passed"]),),
        "L1": (
            int(manhattan["unresolved_edge_count"]),
            manhattan.get("turn_residual_max") is None,
            metric(manhattan.get("turn_residual_max")),
            metric(manhattan.get("turn_residual_median")),
            manhattan.get("local_window_residual") is None,
            metric(manhattan.get("local_window_residual")),
            manhattan.get("floor_ceiling_column_consistency") is None,
            metric(manhattan.get("floor_ceiling_column_consistency")),
            direction is None,
            parallel is None,
            metric(direction_summary.get("max_deg")),
            metric(direction_summary.get("median_deg")),
            metric(parallel.get("max_deg")) if isinstance(parallel, Mapping) else math.inf,
            metric(parallel.get("median_deg")) if isinstance(parallel, Mapping) else math.inf,
            metric(manhattan.get("wall_residual_max")),
            metric(manhattan.get("wall_residual_median")),
        ),
        "L2": (
            evidence.get("evidence_status") != "available"
            or not evidence.get("candidate_preference_authorized", False),
            bool(evidence.get("visual_conflict_flags")),
            len(evidence.get("visual_conflict_flags") or []),
            sum(value > 0 for value in finite_deltas),
            sum(max(0.0, value) for value in finite_deltas),
            *deltas,
        ),
        "L3": (
            plane_parallel.get("status") != "available",
            metric(plane_parallel.get("max_deg")),
            metric(plane_parallel.get("median_deg")),
            plane_orthogonal.get("status") != "available",
            metric(plane_orthogonal.get("orthogonal_residual_deg")),
            floor_plane.get("status") != "available",
            metric(floor_plane.get("wall_residual_max_deg")),
            metric(height.get("height_outlier_l1")),
            metric(height.get("max_height_residual")),
            metric(height.get("height_cluster_mad")),
        ),
        "L4": (
            manual_blocked,
            len(plausibility["short_wall_collapsed"]),
            len(plausibility["new_short_wall_created"]),
            max(0.0, float(plausibility["short_wall_deficit_delta"])),
        ),
        "L5": (
            metric(movement.get("movement_l1_normalized")),
            int(movement.get("changed_pair_count", 0)),
            int(movement.get("changed_endpoint_count", 0)),
            metric(movement.get("manual_adjustment_cost_proxy")),
        ),
    }


def build_hypothesis_ranking_key(evaluation: Mapping[str, Any]) -> tuple[Any, ...]:
    """Lexicographic L0-L5 ranking key; legacy score is excluded."""
    layers = build_hypothesis_ranking_layers(evaluation)
    return tuple(value for layer in ("L0", "L1", "L2", "L3", "L4", "L5") for value in layers[layer])
