"""Dev-only Manhattan constrained fitting prototype.

This module is a pure Python geometry prototype for the experiment-outside
Manhattan toolchain. It accepts ordered paired corners in Label Studio 0-100
coordinates, estimates a conservative Manhattan constrained candidate, and
returns diagnostics only. It performs no Label Studio integration, no export
read/write, no annotation writeback, no routing, no formal g_t, and no
P1/C1/C2/T1/V1 artifact materialization.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


FIT_VERSION = "manhattan_constrained_fit_m14_v1"
CAMERA_HEIGHT = 1.6
MIN_PAIR_COUNT = 4
VERTICAL_X_WARN_THRESHOLD = 1.0
DUPLICATE_POINT_THRESHOLD = 0.05
DUPLICATE_PAIR_X_THRESHOLD = 0.25
SEAM_EDGE_THRESHOLD = 5.0
FIT_RESIDUAL_FAIL_THRESHOLD = 0.18
MAX_POINT_MOVE_FAIL_THRESHOLD = 12.0


@dataclass(frozen=True)
class LsPoint:
    x: float
    y: float


@dataclass(frozen=True)
class CornerPair:
    pair_index: int
    top: LsPoint
    bottom: LsPoint

    @property
    def center_x(self) -> float:
        return (self.top.x + self.bottom.x) / 2.0


@dataclass(frozen=True)
class BevPoint:
    x: float
    y: float


def ls_x_to_u(x: float) -> float:
    """Convert Label Studio 0-100 horizontal coordinate to panorama u angle."""
    return (x / 100.0) * 2.0 * math.pi - math.pi


def ls_y_to_v(y: float) -> float:
    """Convert Label Studio 0-100 vertical coordinate to panorama elevation."""
    return math.pi / 2.0 - (y / 100.0) * math.pi


def u_to_ls_x(u: float) -> float:
    return ((math.atan2(math.sin(u), math.cos(u)) + math.pi) / (2.0 * math.pi)) * 100.0


def _as_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unparseable_{field_name}") from exc


def _point_from_mapping(value: Mapping[str, Any], prefix: str = "") -> LsPoint:
    if "x" in value and "y" in value:
        return LsPoint(_as_float(value["x"], f"{prefix}x"), _as_float(value["y"], f"{prefix}y"))
    raise ValueError(f"missing_{prefix}point_xy")


def parse_ordered_pairs(rows: Sequence[Mapping[str, Any]]) -> List[CornerPair]:
    """Parse ordered paired corners from small Label Studio 0-100 records.

    Supported row shapes are intentionally narrow:
    - {"top": {"x": ..., "y": ...}, "bottom": {"x": ..., "y": ...}}
    - {"ceiling": {"x": ..., "y": ...}, "floor": {"x": ..., "y": ...}}
    - {"top_x": ..., "top_y": ..., "bottom_x": ..., "bottom_y": ...}
    - {"x": ..., "y_ceiling": ..., "y_floor": ...}
    """
    pairs: List[CornerPair] = []
    for idx, row in enumerate(rows, start=1):
        if "top" in row and "bottom" in row:
            top = _point_from_mapping(row["top"], "top_")
            bottom = _point_from_mapping(row["bottom"], "bottom_")
        elif "ceiling" in row and "floor" in row:
            top = _point_from_mapping(row["ceiling"], "ceiling_")
            bottom = _point_from_mapping(row["floor"], "floor_")
        elif {"top_x", "top_y", "bottom_x", "bottom_y"}.issubset(row):
            top = LsPoint(_as_float(row["top_x"], "top_x"), _as_float(row["top_y"], "top_y"))
            bottom = LsPoint(
                _as_float(row["bottom_x"], "bottom_x"),
                _as_float(row["bottom_y"], "bottom_y"),
            )
        elif {"x", "y_ceiling", "y_floor"}.issubset(row):
            x = _as_float(row["x"], "x")
            top = LsPoint(x, _as_float(row["y_ceiling"], "y_ceiling"))
            bottom = LsPoint(x, _as_float(row["y_floor"], "y_floor"))
        else:
            raise ValueError("unparseable_ordered_pair")

        for point in (top, bottom):
            if not (0.0 <= point.x <= 100.0 and 0.0 <= point.y <= 100.0):
                raise ValueError("point_outside_label_studio_0_100")
        pairs.append(CornerPair(idx, top, bottom))
    return pairs


def _fail(reason: str, warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "fit_status": "failed",
        "fit_residual": None,
        "fit_confidence": "unavailable",
        "fitted_points": [],
        "per_point_delta": [],
        "direction_label": reason,
        "warnings": list(warnings or [reason]),
        "fit_version": FIT_VERSION,
    }


def _metadata_exclusion(metadata: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not metadata:
        return None
    scope = metadata.get("scope")
    if scope in {"oos_open_boundary", "oos_split_level", "oos_geometry"}:
        return str(scope)
    if metadata.get("manhattan_assumable") is False:
        return "not_manhattan_assumable"
    layout_type = metadata.get("layout_type")
    if layout_type in {"open_boundary", "split_level", "non_manhattan"}:
        return str(layout_type)
    return None


def _has_duplicate_points(pairs: Sequence[CornerPair]) -> bool:
    points = [p.top for p in pairs] + [p.bottom for p in pairs]
    for i, left in enumerate(points):
        for right in points[i + 1 :]:
            if math.hypot(left.x - right.x, left.y - right.y) < DUPLICATE_POINT_THRESHOLD:
                return True
    centers = [p.center_x for p in pairs]
    for i, left in enumerate(centers):
        for right in centers[i + 1 :]:
            if abs(left - right) < DUPLICATE_PAIR_X_THRESHOLD:
                return True
    return False


def _wrap_seam_unresolved(pairs: Sequence[CornerPair]) -> bool:
    xs = [p.center_x for p in pairs]
    return min(xs) < SEAM_EDGE_THRESHOLD and max(xs) > 100.0 - SEAM_EDGE_THRESHOLD


def _pair_to_bev(pair: CornerPair) -> Tuple[BevPoint, List[str]]:
    """Approximate pair ray and floor distance from pano angles.

    HoHoNet/MatterportLayout preparation uses camera height, layout height,
    atan2, and connected boundary curves instead of global image-space median
    bands. This prototype keeps the same angular intuition but stays small and
    deterministic for sandbox fitting.
    """
    warnings: List[str] = []
    u = ls_x_to_u(pair.center_x)
    v_floor = ls_y_to_v(pair.bottom.y)
    if v_floor >= -1e-6:
        distance = CAMERA_HEIGHT
        warnings.append("floor_not_below_horizon_distance_fallback")
    else:
        distance = CAMERA_HEIGHT / max(math.tan(-v_floor), 1e-6)
    return BevPoint(distance * math.cos(u), distance * math.sin(u)), warnings


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _fit_axis_aligned_closed_polygon(points: Sequence[BevPoint], start_horizontal: bool) -> List[BevPoint]:
    n = len(points)
    x_groups = _UnionFind(n)
    y_groups = _UnionFind(n)
    for i in range(n):
        j = (i + 1) % n
        horizontal = start_horizontal if i % 2 == 0 else not start_horizontal
        if horizontal:
            y_groups.union(i, j)
        else:
            x_groups.union(i, j)

    x_values: Dict[int, List[float]] = {}
    y_values: Dict[int, List[float]] = {}
    for i, point in enumerate(points):
        x_values.setdefault(x_groups.find(i), []).append(point.x)
        y_values.setdefault(y_groups.find(i), []).append(point.y)

    x_fit = {root: sum(values) / len(values) for root, values in x_values.items()}
    y_fit = {root: sum(values) / len(values) for root, values in y_values.items()}
    return [
        BevPoint(x_fit[x_groups.find(i)], y_fit[y_groups.find(i)])
        for i in range(n)
    ]


def _polygon_residual(original: Sequence[BevPoint], fitted: Sequence[BevPoint]) -> float:
    if not original:
        return 0.0
    xs = [p.x for p in original]
    ys = [p.y for p in original]
    diag = max(math.hypot(max(xs) - min(xs), max(ys) - min(ys)), 1e-6)
    distances = [math.hypot(a.x - b.x, a.y - b.y) / diag for a, b in zip(original, fitted)]
    return sum(distances) / len(distances)


def _ccw(a: BevPoint, b: BevPoint, c: BevPoint) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _segments_intersect(a: BevPoint, b: BevPoint, c: BevPoint, d: BevPoint) -> bool:
    def between(x: float, y: float, z: float) -> bool:
        return min(x, z) - 1e-9 <= y <= max(x, z) + 1e-9

    ab_c = _ccw(a, b, c)
    ab_d = _ccw(a, b, d)
    cd_a = _ccw(c, d, a)
    cd_b = _ccw(c, d, b)
    if ab_c == 0 and between(a.x, c.x, b.x) and between(a.y, c.y, b.y):
        return True
    if ab_d == 0 and between(a.x, d.x, b.x) and between(a.y, d.y, b.y):
        return True
    if cd_a == 0 and between(c.x, a.x, d.x) and between(c.y, a.y, d.y):
        return True
    if cd_b == 0 and between(c.x, b.x, d.x) and between(c.y, b.y, d.y):
        return True
    return (ab_c * ab_d < 0) and (cd_a * cd_b < 0)


def _self_crossing(points: Sequence[BevPoint]) -> bool:
    n = len(points)
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1 or {i, j} == {0, n - 1}:
                continue
            c = points[j]
            d = points[(j + 1) % n]
            if _segments_intersect(a, b, c, d):
                return True
    return False


def _max_vertical_x_residual(pairs: Sequence[CornerPair]) -> float:
    if not pairs:
        return 0.0
    return max(abs(pair.top.x - pair.bottom.x) for pair in pairs)


def _confidence(fit_residual: float, max_move: float) -> str:
    if fit_residual < 0.03 and max_move < 2.0:
        return "high"
    if fit_residual < 0.08 and max_move < 5.0:
        return "medium"
    return "low"


def _fitted_pairs_and_deltas(
    pairs: Sequence[CornerPair],
    fitted_bev: Sequence[BevPoint],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], float]:
    fitted_points: List[Dict[str, Any]] = []
    deltas: List[Dict[str, Any]] = []
    max_move = 0.0
    for pair, point in zip(pairs, fitted_bev):
        fitted_x = u_to_ls_x(math.atan2(point.y, point.x))
        top_dx = fitted_x - pair.top.x
        bottom_dx = fitted_x - pair.bottom.x
        top_delta = math.hypot(top_dx, 0.0)
        bottom_delta = math.hypot(bottom_dx, 0.0)
        max_move = max(max_move, top_delta, bottom_delta)
        fitted_points.append(
            {
                "pair_index": pair.pair_index,
                "top": {"x": fitted_x, "y": pair.top.y},
                "bottom": {"x": fitted_x, "y": pair.bottom.y},
            }
        )
        deltas.append(
            {
                "pair_index": pair.pair_index,
                "top_dx": top_dx,
                "top_dy": 0.0,
                "bottom_dx": bottom_dx,
                "bottom_dy": 0.0,
            }
        )
    return fitted_points, deltas, max_move


def fit_manhattan_layout(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Fit a dev-only Manhattan constrained candidate.

    The output is diagnostic only. `fitted_points` and `per_point_delta` are
    candidate deltas for review, not correction instructions and not writeback
    payloads.
    """
    exclusion = _metadata_exclusion(metadata)
    if exclusion:
        return _fail(exclusion)

    try:
        pairs = parse_ordered_pairs(ordered_pairs)
    except ValueError as exc:
        return _fail(str(exc))

    if len(pairs) < MIN_PAIR_COUNT:
        return _fail("pair_count_lt_4")
    if len(pairs) % 2 != 0:
        return _fail("odd_pair_count")
    if _has_duplicate_points(pairs):
        return _fail("duplicate_keypoints")
    if _wrap_seam_unresolved(pairs):
        return _fail("wrap_seam_unresolved")

    bev_points: List[BevPoint] = []
    warnings: List[str] = []
    for pair in pairs:
        point, pair_warnings = _pair_to_bev(pair)
        bev_points.append(point)
        warnings.extend(pair_warnings)

    if _self_crossing(bev_points):
        return _fail("self_crossing_input", warnings + ["self_crossing_input"])

    candidates = [
        _fit_axis_aligned_closed_polygon(bev_points, start_horizontal=True),
        _fit_axis_aligned_closed_polygon(bev_points, start_horizontal=False),
    ]
    fitted_bev = min(candidates, key=lambda candidate: _polygon_residual(bev_points, candidate))
    if _self_crossing(fitted_bev):
        return _fail("self_crossing_candidate", warnings + ["self_crossing_candidate"])

    fit_residual = _polygon_residual(bev_points, fitted_bev)
    fitted_points, per_point_delta, max_move = _fitted_pairs_and_deltas(pairs, fitted_bev)
    if fit_residual > FIT_RESIDUAL_FAIL_THRESHOLD:
        return _fail("fit_residual_too_high", warnings + ["fit_residual_too_high"])
    if max_move > MAX_POINT_MOVE_FAIL_THRESHOLD:
        return _fail("candidate_moves_points_too_far", warnings + ["candidate_moves_points_too_far"])

    vertical_residual = _max_vertical_x_residual(pairs)
    if vertical_residual > VERTICAL_X_WARN_THRESHOLD:
        direction_label = "align_vertical_pair_x"
        warnings.append("vertical_corner_x_mismatch")
    elif fit_residual > 0.03:
        direction_label = "review_manhattan_wall_directions"
    else:
        direction_label = "no_action"

    return {
        "fit_status": "ok",
        "fit_residual": fit_residual,
        "fit_confidence": _confidence(fit_residual, max_move),
        "fitted_points": fitted_points,
        "per_point_delta": per_point_delta,
        "direction_label": direction_label,
        "warnings": warnings,
        "fit_version": FIT_VERSION,
    }


__all__ = [
    "FIT_VERSION",
    "fit_manhattan_layout",
    "ls_x_to_u",
    "ls_y_to_v",
    "parse_ordered_pairs",
    "u_to_ls_x",
]
