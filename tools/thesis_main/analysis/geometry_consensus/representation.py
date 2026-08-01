from __future__ import annotations

import hashlib
import json
from typing import Any

import numpy as np

from tools.thesis_main.analysis.quality_core.geometry_metrics import analyze_layout_pairing


C1_ORPHAN_POINT_REPAIR_RULE_VERSION = "c1_recoverable_orphan_point_removed_v1"


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


def _circular_pairs(pairs: list[dict[str, float]], width: int) -> list[dict[str, float]]:
    """Cut the panorama at its largest empty arc before planar checks."""
    ordered = sorted(pairs, key=lambda row: row["x"] % width)
    if len(ordered) < 2:
        return ordered
    xs = [float(row["x"]) % width for row in ordered]
    gaps = [xs[index + 1] - xs[index] for index in range(len(xs) - 1)] + [xs[0] + width - xs[-1]]
    start = (max(range(len(gaps)), key=gaps.__getitem__) + 1) % len(ordered)
    rotated = ordered[start:] + ordered[:start]
    unwrapped = []
    previous = None
    for row in rotated:
        x = float(row["x"]) % width
        if previous is not None and x <= previous:
            x += width
        previous = x
        unwrapped.append({**row, "x": x})
    return unwrapped


def _raw_order_pairs(array: np.ndarray, width: int, threshold_ratio: float) -> list[dict[str, float]]:
    if len(array) < 4 or len(array) % 2:
        return []
    threshold = float(width) * float(threshold_ratio)
    pairs = []
    for first, second in array.reshape(-1, 2, 2):
        dx = abs(float(first[0]) - float(second[0])) % float(width)
        dx = min(dx, float(width) - dx)
        if dx >= threshold or abs(float(first[1]) - float(second[1])) < 1.0:
            return []
        x1, x2 = float(first[0]), float(second[0])
        x = ((max(x1, x2) + min(x1, x2) + width) / 2.0) % width if abs(x1 - x2) > width / 2 else (x1 + x2) / 2.0
        pairs.append({"x": x, "y_ceiling": min(float(first[1]), float(second[1])), "y_floor": max(float(first[1]), float(second[1]))})
    xs = [row["x"] % width for row in pairs]
    if any(min(abs(x - y), width - abs(x - y)) < 1e-6 for index, x in enumerate(xs) for y in xs[index + 1 :]):
        return []
    return pairs


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
        "geometry_parse_valid": False,
        "coordinate_range_valid": False,
        "corner_count_valid": False,
        "pair_count_valid": False,
        "pairing_valid": False,
        "top_bottom_order_valid": False,
        "pair_fold_absent": False,
        "duplicate_corner_absent": False,
        "polygon_closed": False,
        "polygon_simple": False,
        "topology_valid": False,
        "seam_representation_valid": False,
        "seam_crossing_detected": False,
        "pairing_method": "circular_x_pairing",
        "raw_points": array.tolist() if array.ndim == 2 and array.shape[1:] == (2,) else [],
        "canonical_points": [],
        "coordinate_transform": "none",
    }
    if array.ndim != 2 or array.shape[1:] != (2,):
        result["reason"] = "shape_invalid"
        return result
    if not np.isfinite(array).all():
        result["reason"] = "non_finite"
        return result
    result["geometry_parse_valid"] = True
    result["coordinate_range_valid"] = not ((array[:, 0] < 0).any() or (array[:, 0] > width).any() or (array[:, 1] < 0).any() or (array[:, 1] >= height).any())
    if not result["coordinate_range_valid"]:
        result["reason"] = "out_of_range"
        return result
    result["corner_count_valid"] = len(array) >= 4 and len(array) % 2 == 0
    result["duplicate_corner_absent"] = len({(round(float(x), 9), round(float(y), 9)) for x, y in array}) == len(array)
    result["seam_crossing_detected"] = bool(len(array) and np.ptp(array[:, 0]) > width / 2)
    result["seam_representation_valid"] = True
    array = array.copy()
    array[:, 0] %= float(width)
    result["canonical_points"] = array.tolist()
    result["coordinate_transform"] = "x_modulo_panorama_width_only"
    unordered_pairs, stats = analyze_layout_pairing(array, width=width, height=height, threshold_ratio=threshold_ratio)
    raw_pairs = _raw_order_pairs(array, width, threshold_ratio)
    stats = {**stats, "raw_order_pairing_valid": bool(raw_pairs), "unordered_pairing_ambiguous": bool(stats.get("pairing_ambiguous"))}
    pairs = raw_pairs or unordered_pairs
    if raw_pairs:
        stats.update(n_pairs=len(raw_pairs), coverage=1.0, unpaired_point_count=0, pairing_ambiguous=False, ambiguity_reason="")
        result["pairing_method"] = "raw_order_pairing"
    else:
        result["pairing_method"] = "circular_x_pairing"
    result["pairing_stats"] = stats
    result["n_pairs"] = len(pairs)
    result["pair_count_valid"] = int(stats.get("n_pairs", 0)) >= 2 and int(stats.get("unpaired_point_count", 0)) == 0
    if int(stats.get("n_points", 0)) % 2:
        result["reason"] = "odd_keypoint_count"
        return result
    if int(stats.get("n_pairs", 0)) < 2 or int(stats.get("unpaired_point_count", 0)) != 0:
        result["reason"] = "incomplete_pairing"
        return result
    if bool(stats.get("pairing_ambiguous")):
        result["reason"] = "ambiguous_pairing"
        return result
    result["pairing_valid"] = True
    pairs = _circular_pairs(pairs, width)
    xs = [float(row["x"]) % float(width) for row in pairs]
    if any(abs(xs[i] - xs[i - 1]) < 1e-6 for i in range(1, len(xs))):
        result["reason"] = "duplicate_event_positions"
        return result
    result["top_bottom_order_valid"] = not any(float(row["y_floor"]) <= float(row["y_ceiling"]) for row in pairs)
    result["pair_fold_absent"] = result["top_bottom_order_valid"] and result["duplicate_corner_absent"]
    if not result["top_bottom_order_valid"]:
        result["reason"] = "top_floor_order_invalid"
        return result
    result["polygon_closed"] = len(pairs) >= 2
    result["polygon_simple"] = _simple_wall_polygon(pairs)
    if not result["polygon_simple"]:
        result["reason"] = "self_intersecting_or_open_topology"
        return result
    result["topology_valid"] = True
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


def _geometry_sha256(points: Any) -> str:
    """Hash the exact numeric point list retained in a derived geometry audit."""
    return hashlib.sha256(json.dumps(points, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def normalize_geometry_for_c1_calculation(
    corners: Any,
    *,
    width: int = 1024,
    height: int = 512,
    threshold_ratio: float = 0.05,
) -> dict[str, Any]:
    """Return C1 calculation geometry, repairing only one uniquely removable orphan point.

    The raw submission is never changed.  Candidate selection depends solely on
    the submitted points and the public geometry validator; it never reads GT,
    peer geometry, worker identity, or any scored outcome.
    """
    raw = normalize_geometry(corners, width=width, height=height, threshold_ratio=threshold_ratio)
    raw_points = raw["raw_points"]
    audit = {
        "geometry_repair_rule_version": C1_ORPHAN_POINT_REPAIR_RULE_VERSION,
        "geometry_repair_applied": False,
        "geometry_repair_status": "not_needed" if raw["valid"] else "not_eligible",
        "raw_point_count": raw["n_points"],
        "repaired_point_count": raw["n_points"],
        "dropped_point_index": None,
        "orphan_candidate_count": 0,
        "raw_geometry_sha256": _geometry_sha256(raw_points),
        "repaired_geometry_sha256": "",
        "raw_structural_failure_reason": raw["reason"],
        "raw_geometry_valid": raw["valid"],
    }
    if raw["valid"]:
        return {**raw, **audit}
    if raw["reason"] != "odd_keypoint_count" or raw["n_points"] < 5:
        return {**raw, **audit}

    candidates: list[tuple[int, dict[str, Any]]] = []
    for index in range(len(raw_points)):
        repaired_points = raw_points[:index] + raw_points[index + 1 :]
        candidate = normalize_geometry(repaired_points, width=width, height=height, threshold_ratio=threshold_ratio)
        if candidate["valid"] and candidate["pairing_valid"] and candidate["topology_valid"] and candidate["polygon_simple"]:
            candidates.append((index, candidate))
    audit["orphan_candidate_count"] = len(candidates)
    if len(candidates) != 1:
        audit["geometry_repair_status"] = "ambiguous_extra_or_missing_pair" if candidates else "not_recoverable_odd_keypoint_count"
        return {**raw, **audit}

    dropped_index, repaired = candidates[0]
    return {
        **repaired,
        **audit,
        "geometry_repair_applied": True,
        "geometry_repair_status": "recoverable_orphan_point_removed",
        "repaired_point_count": repaired["n_points"],
        "dropped_point_index": dropped_index,
        "repaired_geometry_sha256": _geometry_sha256(repaired["canonical_points"]),
        "raw_points": raw_points,
        "raw_structural_failure_reason": raw["reason"],
        "raw_geometry_valid": raw["valid"],
    }
