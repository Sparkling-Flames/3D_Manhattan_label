from __future__ import annotations

from typing import Any

import numpy as np

from tools.thesis_main.analysis.quality_core.geometry_metrics import analyze_layout_pairing


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a, b, c, d) -> bool:
    eps = 1e-9
    ab_c = _orientation(a, b, c)
    ab_d = _orientation(a, b, d)
    cd_a = _orientation(c, d, a)
    cd_b = _orientation(c, d, b)
    if ((ab_c > eps and ab_d < -eps) or (ab_c < -eps and ab_d > eps)) and ((cd_a > eps and cd_b < -eps) or (cd_a < -eps and cd_b > eps)):
        return True
    return False


def _simple_wall_polygon(pairs: list[dict[str, float]]) -> bool:
    top = [(p["x"], p["y_ceiling"]) for p in pairs]
    floor = [(p["x"], p["y_floor"]) for p in reversed(pairs)]
    polygon = top + floor
    if len(polygon) < 4:
        return False
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    for i, (a, b) in enumerate(edges):
        for j, (c, d) in enumerate(edges):
            if j <= i or j in {i - 1, i + 1} or (i == 0 and j == len(edges) - 1):
                continue
            if _segments_intersect(a, b, c, d):
                return False
    return True


def normalize_geometry(
    corners: Any,
    *,
    width: int = 1024,
    height: int = 512,
    threshold_ratio: float = 0.05,
) -> dict[str, Any]:
    """Normalize unordered corner keypoints into a strict seam-aware form."""
    try:
        array = np.asarray(corners, dtype=np.float64)
    except Exception:
        array = np.empty((0, 2), dtype=np.float64)
    result: dict[str, Any] = {
        "valid": False,
        "validity_status": "not_evaluable",
        "reason": "",
        "width": int(width),
        "height": int(height),
        "n_points": int(array.shape[0]) if array.ndim == 2 else 0,
        "n_pairs": 0,
        "pairs": [],
        "x_event_positions": [],
    }
    if array.ndim != 2 or array.shape[1:] != (2,):
        result["reason"] = "shape_invalid"
        return result
    if not np.isfinite(array).all():
        result["reason"] = "non_finite"
        return result
    if (array[:, 0] < 0).any() or (array[:, 0] > width).any() or (array[:, 1] < 0).any() or (array[:, 1] >= height).any():
        result["reason"] = "out_of_range"
        return result
    array = array.copy()
    array[:, 0] %= float(width)
    pairs, stats = analyze_layout_pairing(array, width=width, height=height, threshold_ratio=threshold_ratio)
    result["pairing_stats"] = stats
    result["n_pairs"] = len(pairs)
    if int(stats.get("n_points", 0)) % 2:
        result["reason"] = "odd_keypoint_count"
        return result
    if int(stats.get("n_pairs", 0)) < 2 or int(stats.get("unpaired_point_count", 0)) != 0:
        result["reason"] = "incomplete_pairing"
        return result
    if bool(stats.get("pairing_ambiguous")):
        result["reason"] = "ambiguous_pairing"
        return result
    pairs = sorted(pairs, key=lambda row: row["x"])
    xs = [float(row["x"]) % float(width) for row in pairs]
    if any(abs(xs[i] - xs[i - 1]) < 1e-6 for i in range(1, len(xs))):
        result["reason"] = "duplicate_event_positions"
        return result
    if any(float(row["y_floor"]) <= float(row["y_ceiling"]) for row in pairs):
        result["reason"] = "top_floor_order_invalid"
        return result
    if not _simple_wall_polygon(pairs):
        result["reason"] = "self_intersecting_or_open_topology"
        return result
    result.update(
        {
            "valid": True,
            "validity_status": "valid",
            "reason": "",
            "pairs": pairs,
            "x_event_positions": xs,
            "top_y": [float(row["y_ceiling"]) for row in pairs],
            "floor_y": [float(row["y_floor"]) for row in pairs],
        }
    )
    return result
