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


def cyclic_order_correspondence(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, str, list[tuple[int, int]]]:
    """Require one monotone cyclic pairing; ties and reverse/topology breaks fail closed."""
    width = float(left.get("width", 0))
    left_x = [float(value) % width for value in left.get("x_event_positions") or []] if width else []
    right_x = [float(value) % width for value in right.get("x_event_positions") or []] if width else []
    if len(left_x) < 2 or len(right_x) < 2 or len(set(left_x)) != len(left_x) or len(set(right_x)) != len(right_x):
        return False, "invalid_or_duplicate_events", []
    def monotone(xs: list[float]) -> bool:
        return sum(xs[index] > xs[index + 1] for index in range(len(xs) - 1)) <= 1
    if not monotone(left_x) or not monotone(right_x):
        return False, "cyclic_order_reversed_or_topology_invalid", []
    # A single nearest counterpart per event permits variable point counts, but not ambiguous seams.
    pairs = []
    for index, x in enumerate(left_x):
        distances = [_circular_distance(x, y, width) for y in right_x]
        best = min(distances)
        if distances.count(best) != 1:
            return False, "cyclic_correspondence_ambiguous", []
        pairs.append((index, distances.index(best)))
    mapped = [right for _, right in pairs]
    wraps = sum(mapped[index] > mapped[index + 1] for index in range(len(mapped) - 1))
    if wraps > 1:
        return False, "cyclic_topology_mismatch", []
    return True, "unique_cyclic_correspondence", pairs


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
    order_compatible, order_reason, correspondence = cyclic_order_correspondence(left, right) if left.get("width") == right.get("width") and left.get("height") == right.get("height") else (False, "geometry_context_mismatch", [])
    compatible = bool(left.get("valid") and right.get("valid") and order_compatible)
    boundary = boundary_similarity(left, right, grid=grid) if compatible else None
    wallwall = wallwall_similarity(left, right) if compatible else None
    return {
        "metric_compatible": compatible,
        "order_compatible": order_compatible,
        "order_reason": order_reason,
        "cyclic_correspondence": correspondence,
        "boundary_similarity": boundary,
        "wallwall_similarity": wallwall,
        "q_boundary": boundary,
        "q_wallwall": wallwall,
        "overall_similarity": None,  # retained only as an empty compatibility column; channels must not be merged.
        "left_pair_count": int(left.get("n_pairs", 0)),
        "right_pair_count": int(right.get("n_pairs", 0)),
        "validity_status": "valid" if compatible and boundary is not None and wallwall is not None else "not_evaluable",
    }
