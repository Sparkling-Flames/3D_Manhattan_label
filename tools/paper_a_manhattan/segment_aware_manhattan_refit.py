"""Deterministic segment-aware Manhattan wall-line refit for annotation 3741."""

from __future__ import annotations

import math
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from tools.paper_a_manhattan.manhattan_3d_projection import (
    DEFAULT_CAMERA_HEIGHT,
    compute_all_geometry_metrics,
    floor_point_to_layout_pair,
    project_layout_to_3d,
)

VERIFIED_ORDER_SOURCE_IDS = [2, 1, 3, 4, 6, 5, 8, 7, 9, 10, 12, 11]
SOURCE_PAIR_TO_SOLVER_POSITION = {
    source_pair_id: solver_position
    for solver_position, source_pair_id in enumerate(
        VERIFIED_ORDER_SOURCE_IDS, start=1
    )
}
SOLVER_POSITION_TO_SOURCE_PAIR_ID = {
    solver_position: source_pair_id
    for source_pair_id, solver_position in SOURCE_PAIR_TO_SOLVER_POSITION.items()
}
SOURCE_PAIR_WEIGHTS = {
    1: 1.5,
    2: 0.25,
    3: 8.0,
    4: 8.0,
    5: 1.0,
    6: 1.0,
    7: 1.0,
    8: 1.0,
    9: 3.0,
    10: 3.0,
    11: 1.5,
    12: 1.5,
}
SEGMENTS_BY_SOURCE_PAIR_ID = {
    "strong_anchor_segment": {
        "source_pair_ids": [3, 4],
        "source_edge_ids": [3, 4],
    },
    "medium_anchor_segment": {
        "source_pair_ids": [9, 10],
        "source_edge_ids": [9, 10],
    },
    "suspect_skew_segment": {
        "source_pair_ids": [2, 3],
        "low_confidence_source_pair_id": 2,
    },
    "complex_short_wall_chain_A": {
        "source_pair_ids": [5, 6, 7, 8],
        "verified_cyclic_source_path": [6, 5, 8, 7],
    },
    "complex_short_wall_chain_B": {
        "source_pair_ids": [12, 11, 1],
        "verified_cyclic_source_path": [12, 11, 2, 1],
        "topology_note": "source pair 2 lies between source pairs 11 and 1 in verified order",
    },
    "protected_structure": {
        "source_pair_chains": [[5, 6, 7, 8], [12, 11, 1]]
    },
}
PROTECTED_SOURCE_EDGES_BY_CHAIN = {
    "chain_5_6_7_8": ((6, 5), (5, 8), (8, 7)),
    "chain_12_11_1": ((12, 11), (11, 2), (2, 1)),
}


def solver_position_for_source_pair(source_pair_id: int) -> int:
    return SOURCE_PAIR_TO_SOLVER_POSITION[source_pair_id]


def source_pair_id_for_solver_position(solver_position: int) -> int:
    return SOLVER_POSITION_TO_SOURCE_PAIR_ID[solver_position]


def _array_index_for_source_pair(source_pair_id: int) -> int:
    return solver_position_for_source_pair(source_pair_id) - 1


def _edge_index_for_source_edge(left_source_id: int, right_source_id: int) -> int:
    left_position = solver_position_for_source_pair(left_source_id)
    right_position = solver_position_for_source_pair(right_source_id)
    expected_right = left_position % len(VERIFIED_ORDER_SOURCE_IDS) + 1
    if right_position != expected_right:
        raise ValueError(
            f"source edge {left_source_id}->{right_source_id} is not adjacent "
            "in verified order"
        )
    return left_position - 1


def _angle_mod_90(vector: np.ndarray) -> float:
    return math.atan2(float(vector[1]), float(vector[0])) % (math.pi / 2.0)


def _periodic_mean(angles: Sequence[float], weights: Sequence[float]) -> float:
    sine = sum(w * math.sin(4.0 * a) for a, w in zip(angles, weights))
    cosine = sum(w * math.cos(4.0 * a) for a, w in zip(angles, weights))
    return (math.atan2(sine, cosine) / 4.0) % (math.pi / 2.0)


def _direction_variants(points: np.ndarray) -> list[dict[str, Any]]:
    edge_vectors = np.roll(points, -1, axis=0) - points
    edge_angles = [_angle_mod_90(row) for row in edge_vectors]
    lengths = np.linalg.norm(edge_vectors, axis=1)
    theta34 = edge_angles[_edge_index_for_source_edge(3, 4)]
    theta910 = edge_angles[_edge_index_for_source_edge(9, 10)]
    excluded_source_ids = {2, 6, 5, 8, 12, 11}
    long = [
        index
        for index, length in enumerate(lengths)
        if length >= float(np.median(lengths))
        and source_pair_id_for_solver_position(index + 1)
        not in excluded_source_ids
    ]
    return [
        {"variant_id": "anchor_34_dominant", "theta_rad": theta34},
        {
            "variant_id": "anchor_34_plus_910",
            "theta_rad": _periodic_mean([theta34, theta910], [4.0, 2.0]),
        },
        {
            "variant_id": "robust_all_long_edges",
            "theta_rad": _periodic_mean(
                [edge_angles[index] for index in long],
                [float(lengths[index]) for index in long],
            ),
        },
    ]


def _fit_lines(
    points: np.ndarray, theta: float
) -> tuple[list[dict[str, Any]], np.ndarray, list[str]]:
    directions = (
        np.array([math.cos(theta), math.sin(theta)]),
        np.array([-math.sin(theta), math.cos(theta)]),
    )
    edge_vectors = np.roll(points, -1, axis=0) - points
    best: tuple[float, list[int]] | None = None
    for start in (0, 1):
        families = [(start + index) % 2 for index in range(len(points))]
        residual = sum(
            SOURCE_PAIR_WEIGHTS[
                source_pair_id_for_solver_position(index + 1)
            ]
            * abs(
                math.sin(
                    math.atan2(float(vector[1]), float(vector[0]))
                    - math.atan2(directions[family][1], directions[family][0])
                )
            )
            for index, (vector, family) in enumerate(zip(edge_vectors, families))
        )
        if best is None or residual < best[0]:
            best = (residual, families)
    families = best[1] if best else []
    lines: list[dict[str, Any]] = []
    for index, family in enumerate(families):
        direction = directions[family]
        normal = np.array([-direction[1], direction[0]])
        left, right = points[index], points[(index + 1) % len(points)]
        left_solver_position = index + 1
        right_solver_position = (index + 1) % len(points) + 1
        left_source_id = source_pair_id_for_solver_position(left_solver_position)
        right_source_id = source_pair_id_for_solver_position(right_solver_position)
        left_weight = SOURCE_PAIR_WEIGHTS[left_source_id]
        right_weight = SOURCE_PAIR_WEIGHTS[right_source_id]
        offset = (
            left_weight * float(normal @ left)
            + right_weight * float(normal @ right)
        ) / (left_weight + right_weight)
        lines.append(
            {
                "source_edge_ids": [left_source_id, right_source_id],
                "solver_edge_positions": [
                    left_solver_position,
                    right_solver_position,
                ],
                "family": "A" if family == 0 else "B",
                "direction": direction.tolist(),
                "normal": normal.tolist(),
                "offset": offset,
            }
        )
    intersections = []
    errors = []
    for index in range(len(lines)):
        previous, current = lines[(index - 1) % len(lines)], lines[index]
        matrix = np.array([previous["normal"], current["normal"]], dtype=float)
        if abs(float(np.linalg.det(matrix))) <= 1e-9:
            source_pair_id = source_pair_id_for_solver_position(index + 1)
            errors.append(
                f"parallel_adjacent_lines_at_source_pair_{source_pair_id}"
            )
            continue
        intersections.append(
            np.linalg.solve(
                matrix, np.array([previous["offset"], current["offset"]], dtype=float)
            )
        )
    return lines, np.asarray(intersections), errors


def _chain_preserved(
    fitted: np.ndarray, baseline_lengths: Mapping[tuple[int, int], float]
) -> tuple[dict[str, bool], float]:
    median_length = float(np.median(list(baseline_lengths.values())))
    threshold = max(0.12, 0.12 * median_length)
    lengths = {
        edge: float(
            np.linalg.norm(
                fitted[_array_index_for_source_pair(edge[1])]
                - fitted[_array_index_for_source_pair(edge[0])]
            )
        )
        for edges in PROTECTED_SOURCE_EDGES_BY_CHAIN.values()
        for edge in edges
    }
    preserved = {
        chain_name: all(
            lengths[edge] >= min(threshold, baseline_lengths[edge] * 0.35)
            for edge in edges
        )
        for chain_name, edges in PROTECTED_SOURCE_EDGES_BY_CHAIN.items()
    }
    return preserved, min(lengths.values())


def _movement(
    before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    rows = []
    for index, (left, right) in enumerate(zip(before, after), start=1):
        top = math.dist(
            (float(left["top"]["x"]), float(left["top"]["y"])),
            (float(right["top"]["x"]), float(right["top"]["y"])),
        )
        bottom = math.dist(
            (float(left["bottom"]["x"]), float(left["bottom"]["y"])),
            (float(right["bottom"]["x"]), float(right["bottom"]["y"])),
        )
        source_pair_id = source_pair_id_for_solver_position(index)
        rows.append(
            {
                "source_pair_id": source_pair_id,
                "solver_position": index,
                "verified_order_source_id": source_pair_id,
                "top": top,
                "bottom": bottom,
                "max": max(top, bottom),
            }
        )
    return {
        "per_pair": rows,
        "total": sum(row["top"] + row["bottom"] for row in rows),
        "max": max(row["max"] for row in rows),
    }


def solve_segment_aware_refit(
    ordered_pairs: Sequence[Mapping[str, Any]],
    *,
    point_ids_by_source_pair_id: Mapping[int, Mapping[str, str]],
    reprojection_fn: Callable[..., dict[str, Any]] | None = floor_point_to_layout_pair,
) -> dict[str, Any]:
    if len(ordered_pairs) != 12:
        return {"status": "failed", "fail_closed": True, "suppress_reasons": ["pair_count_not_12"]}
    if reprojection_fn is None:
        return {
            "status": "failed",
            "fail_closed": True,
            "suppress_reasons": ["missing_projection_converter"],
            "corrected_coordinates": None,
        }
    baseline_projection = project_layout_to_3d(
        ordered_pairs, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT
    )
    points = np.array(
        [
            [row["floor_3d"]["x"], row["floor_3d"]["z"]]
            for row in baseline_projection["pairs"]
        ],
        dtype=float,
    )
    baseline_lengths = {
        (
            source_pair_id_for_solver_position(index + 1),
            source_pair_id_for_solver_position((index + 1) % 12 + 1),
        ): float(
            np.linalg.norm(points[(index + 1) % 12] - points[index])
        )
        for index in range(12)
    }
    layout_height = float(
        np.median(
            [
                baseline_projection["pairs"][
                    _array_index_for_source_pair(source_pair_id)
                ]["wall_height"]
                for source_pair_id in (3, 4)
            ]
        )
    )
    variants = []
    for direction in _direction_variants(points):
        lines, fitted, errors = _fit_lines(points, direction["theta_rad"])
        suppress = list(errors)
        corrected = []
        if len(fitted) == 12 and not errors:
            try:
                for index, point in enumerate(fitted, start=1):
                    source_pair_id = source_pair_id_for_solver_position(index)
                    pair = reprojection_fn(
                        float(point[0]),
                        float(point[1]),
                        layout_height=layout_height,
                        camera_height=DEFAULT_CAMERA_HEIGHT,
                    )
                    corrected.append(
                        {
                            **pair,
                            "source_pair_id": source_pair_id,
                            "solver_position": index,
                            "verified_order_source_id": source_pair_id,
                            "effective_pair_index": index,
                            "source_preview_order_index": source_pair_id,
                            "point_ids": dict(
                                point_ids_by_source_pair_id[source_pair_id]
                            ),
                        }
                    )
            except (KeyError, TypeError, ValueError) as exc:
                suppress.append(f"reprojection_failed:{type(exc).__name__}")
        chain_status, protected_min = (
            _chain_preserved(fitted, baseline_lengths)
            if len(fitted) == 12
            else (
                {
                    chain_name: False
                    for chain_name in PROTECTED_SOURCE_EDGES_BY_CHAIN
                },
                0.0,
            )
        )
        if not all(chain_status.values()):
            suppress.append("protected_short_wall_chain_not_preserved")
        variant_projection = (
            project_layout_to_3d(corrected, 1024, 512, "ls_percent", DEFAULT_CAMERA_HEIGHT)
            if corrected and not suppress
            else None
        )
        metrics = compute_all_geometry_metrics(variant_projection) if variant_projection else {}
        floor = metrics.get("floorprint", {})
        turns = metrics.get("corner_turns", {})
        movement = _movement(ordered_pairs, corrected) if corrected else {"per_pair": [], "total": None, "max": None}
        movement_by_source = {
            row["source_pair_id"]: row for row in movement["per_pair"]
        }
        if floor.get("self_intersection"):
            suppress.append("self_intersection")
        recommendation = "suppress" if suppress else "plausible_but_needs_review"
        variants.append(
            {
                **direction,
                "direction_theta_deg": math.degrees(direction["theta_rad"]),
                "direction_theta_plus_90_deg": (
                    math.degrees(direction["theta_rad"]) + 90.0
                )
                % 180.0,
                "wall_lines": lines,
                "fitted_intersections_by_solver_position": [
                    {
                        "source_pair_id": source_pair_id_for_solver_position(
                            solver_position
                        ),
                        "solver_position": solver_position,
                        "verified_order_source_id": source_pair_id_for_solver_position(
                            solver_position
                        ),
                        "floor_xz": point.tolist(),
                    }
                    for solver_position, point in enumerate(fitted, start=1)
                ],
                "corrected_coordinates": corrected or None,
                "movement_by_source_pair_id": movement["per_pair"],
                "metrics": {
                    "topology_valid": len(fitted) == 12,
                    "self_intersection": floor.get("self_intersection"),
                    "order_preserved": bool(corrected) and [
                        row["verified_order_source_id"] for row in corrected
                    ]
                    == VERIFIED_ORDER_SOURCE_IDS,
                    "wall_family_assignment_valid": not errors,
                    "strong_anchor_movement": max(
                        (
                            movement_by_source[source_pair_id]["max"]
                            for source_pair_id in (3, 4)
                        ),
                        default=None,
                    ),
                    "medium_anchor_movement": max(
                        (
                            movement_by_source[source_pair_id]["max"]
                            for source_pair_id in (9, 10)
                        ),
                        default=None,
                    ),
                    "suspect_source_pair_2_movement": (
                        movement_by_source[2]["max"] if movement_by_source else None
                    ),
                    "suspect_source_pair_2_solver_position": (
                        solver_position_for_source_pair(2)
                    ),
                    "chain_5_6_7_8_preserved": chain_status["chain_5_6_7_8"],
                    "chain_12_11_1_preserved": chain_status["chain_12_11_1"],
                    "min_wall_length": floor.get("summary", {}).get("minimum_wall_length"),
                    "protected_chain_min_wall_length": protected_min,
                    "short_wall_count": floor.get("summary", {}).get("short_wall_count"),
                    "manhattan_turn_residual_max": turns.get("summary", {}).get(
                        "corner_residual_max_deg"
                    ),
                    "manhattan_turn_residual_sum": turns.get("summary", {}).get(
                        "corner_residual_sum_deg"
                    ),
                    "parallel_family_residual": 0.0 if not errors else None,
                    "height_refit_status": "available_from_strong_anchor_3_4",
                    "height_consistency_l1": metrics.get("heights", {})
                    .get("summary", {})
                    .get("height_residual_sum"),
                    "total_movement": movement["total"],
                    "max_movement": movement["max"],
                    "fitted_from_wall_line_intersections": True,
                    "random_or_grid_perturbation_used": False,
                    "fail_closed": bool(suppress),
                    "suppress_reasons": suppress,
                    "recommendation_label": recommendation,
                },
            }
        )
    viable = [row for row in variants if not row["metrics"]["fail_closed"]]
    if viable:
        top = min(
            viable,
            key=lambda row: (
                row["metrics"]["strong_anchor_movement"],
                row["metrics"]["total_movement"],
            ),
        )
        top["metrics"]["recommendation_label"] = "recommended_for_human_review"
    else:
        top = None
    return {
        "status": "ok" if top else "failed",
        "fail_closed": top is None,
        "id_semantics": {
            "source_pair_id": "Label Studio / preview original pair number",
            "solver_position": "one-based position after verified-order sorting",
            "verified_order_source_id": "source_pair_id at each solver_position",
        },
        "verified_order_source_ids": VERIFIED_ORDER_SOURCE_IDS,
        "source_pair_to_solver_position": SOURCE_PAIR_TO_SOLVER_POSITION,
        "solver_position_to_verified_order_source_id": SOLVER_POSITION_TO_SOURCE_PAIR_ID,
        "segment_definitions_by_source_pair_id": SEGMENTS_BY_SOURCE_PAIR_ID,
        "observation_weights_by_source_pair_id": SOURCE_PAIR_WEIGHTS,
        "layout_height_source": "strong_anchor_source_pairs_3_4",
        "layout_height": layout_height,
        "direction_variants": variants,
        "top_candidate_id": top["variant_id"] if top else None,
        "top_candidate": top,
        "suppress_reasons": [] if top else ["no_viable_refit_variant"],
    }
