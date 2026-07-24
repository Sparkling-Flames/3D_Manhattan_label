from __future__ import annotations

from typing import Any

import numpy as np


def _periodic_interp(xs: list[float], ys: list[float], width: int, grid: int) -> np.ndarray:
    x = np.asarray(xs, dtype=float) % float(width)
    y = np.asarray(ys, dtype=float)
    query = np.linspace(0.0, float(width), int(grid), endpoint=False)
    if len(x) == 1:
        return np.full(grid, float(y[0]))
    order = np.argsort(x)
    return np.interp(query, x[order], y[order], period=float(width))


def _circular_distance(a: float, b: float, width: float) -> float:
    delta = abs(float(a) - float(b)) % width
    return min(delta, width - delta)


def cyclic_order_correspondence(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Return one unique forward cyclic alignment; variable-count is not frozen."""
    failure = lambda reason: {"compatible": False, "reason": reason, "pairs": [], "direction": "", "rotation": "", "insertions": 0, "deletions": 0, "ambiguous": "ambiguous" in reason}
    width = float(left.get("width", 0))
    left_x = [float(value) % width for value in left.get("x_event_positions") or []] if width else []
    right_x = [float(value) % width for value in right.get("x_event_positions") or []] if width else []
    if len(left_x) < 2 or len(right_x) < 2 or len(set(left_x)) != len(left_x) or len(set(right_x)) != len(right_x):
        return failure("invalid_or_duplicate_events")
    def monotone(xs: list[float]) -> bool:
        return sum(xs[index] > xs[index + 1] for index in range(len(xs) - 1)) <= 1
    if not monotone(left_x) or not monotone(right_x):
        return failure("cyclic_order_reversed_or_topology_invalid")
    if len(left_x) != len(right_x):
        result = failure("not_evaluable_variable_count_contract_unfrozen")
        result.update({"insertions": max(0, len(right_x) - len(left_x)), "deletions": max(0, len(left_x) - len(right_x))})
        return result
    candidates = []
    for direction in ("forward", "reverse"):
        for shift in range(len(left_x)):
            indices = [((index + shift) % len(right_x)) if direction == "forward" else ((shift - index) % len(right_x)) for index in range(len(left_x))]
            cost = sum(_circular_distance(x, right_x[right_index], width) for x, right_index in zip(left_x, indices))
            candidates.append((cost, direction, shift, indices))
    # With two cyclic events, forward and reverse can describe the same index
    # mapping.  Collapse such representation duplicates before testing whether
    # the geometric correspondence itself is unique.
    unique_candidates: dict[tuple[int, ...], tuple[float, str, int, list[int]]] = {}
    for candidate in candidates:
        key = tuple(candidate[3])
        existing = unique_candidates.get(key)
        if existing is None or candidate[0] < existing[0] or (candidate[0] == existing[0] and candidate[1] == "forward"):
            unique_candidates[key] = candidate
    candidates = list(unique_candidates.values())
    best = min(cost for cost, _, _, _ in candidates)
    winners = [item for item in candidates if abs(item[0] - best) <= 1e-9]
    if len(winners) != 1:
        return failure("cyclic_correspondence_ambiguous")
    _, direction, shift, indices = winners[0]
    if direction != "forward":
        return failure("cyclic_order_reversed")
    return {"compatible": True, "reason": "unique_forward_cyclic_correspondence", "pairs": list(enumerate(indices)), "direction": direction, "rotation": shift, "insertions": 0, "deletions": 0, "ambiguous": False}


def boundary_similarity(left: dict[str, Any], right: dict[str, Any], *, grid: int = 256) -> float | None:
    if not left.get("valid") or not right.get("valid"):
        return None
    width = int(left.get("width", right.get("width", 1024)))
    height = float(left.get("height", right.get("height", 512)))
    left_top = _periodic_interp(left["x_event_positions"], left["top_y"], width, grid)
    left_floor = _periodic_interp(left["x_event_positions"], left["floor_y"], width, grid)
    right_top = _periodic_interp(right["x_event_positions"], right["top_y"], width, grid)
    right_floor = _periodic_interp(right["x_event_positions"], right["floor_y"], width, grid)
    error = (np.abs(left_top - right_top) + np.abs(left_floor - right_floor)) / (2.0 * height)
    return float(np.clip(1.0 - float(np.mean(error)), 0.0, 1.0))


def wallwall_similarity(left: dict[str, Any], right: dict[str, Any]) -> float | None:
    if not left.get("valid") or not right.get("valid"):
        return None
    width = float(left.get("width", right.get("width", 1024)))
    left_x = list(left.get("x_event_positions") or [])
    right_x = list(right.get("x_event_positions") or [])
    if not left_x or not right_x:
        return None
    directed = sum(min(_circular_distance(x, y, width) for y in right_x) for x in left_x) / len(left_x)
    reverse = sum(min(_circular_distance(y, x, width) for x in left_x) for y in right_x) / len(right_x)
    chamfer = (directed + reverse) / 2.0
    return float(np.clip(1.0 - chamfer / (width / 2.0), 0.0, 1.0))


def pairwise_similarity(left: dict[str, Any], right: dict[str, Any], *, grid: int = 256) -> dict[str, Any]:
    same_context = left.get("width") == right.get("width") and left.get("height") == right.get("height")
    alignment = cyclic_order_correspondence(left, right) if same_context else {"compatible": False, "reason": "geometry_context_mismatch", "pairs": [], "direction": "", "rotation": "", "insertions": 0, "deletions": 0, "ambiguous": False}
    order_compatible, order_reason, correspondence = alignment["compatible"], alignment["reason"], alignment["pairs"]
    geometry_compatible = bool(left.get("valid") and right.get("valid") and same_context)
    pointwise_compatible = bool(geometry_compatible and order_compatible)
    boundary_compatible = geometry_compatible
    wall_compatible = geometry_compatible
    boundary = boundary_similarity(left, right, grid=grid) if boundary_compatible else None
    wallwall = wallwall_similarity(left, right) if wall_compatible else None
    return {
        "metric_compatible": boundary_compatible and wall_compatible,
        "boundary_metric_compatible": boundary_compatible,
        "wall_event_metric_compatible": wall_compatible,
        "pointwise_correspondence_compatible": pointwise_compatible,
        "order_compatible": order_compatible,
        "order_reason": order_reason,
        "cyclic_correspondence": correspondence,
        "cyclic_correspondence_json": __import__("json").dumps(correspondence),
        "alignment_direction": alignment["direction"],
        "alignment_rotation": alignment["rotation"],
        "alignment_insertion_count": alignment["insertions"],
        "alignment_deletion_count": alignment["deletions"],
        "alignment_ambiguous": alignment["ambiguous"],
        "boundary_similarity": boundary,
        "wallwall_similarity": wallwall,
        "q_boundary": boundary,
        "q_wallwall": wallwall,
        "overall_similarity": None,  # retained only as an empty compatibility column; channels must not be merged.
        "left_pair_count": int(left.get("n_pairs", 0)),
        "right_pair_count": int(right.get("n_pairs", 0)),
        "validity_status": "valid" if boundary_compatible and wall_compatible and boundary is not None and wallwall is not None else "not_evaluable",
    }
