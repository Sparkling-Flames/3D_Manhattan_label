"""Experiment-outside deterministic 3D preview compatibility parser.

This module mirrors the current HoHoNet 3D preview keypoint conversion and
pairing assumptions for lab-side Manhattan assistant prototyping. It has no UI
integration, no Label Studio integration, and no file I/O. Results are not
correctness labels, not formal g_t, not routing inputs, and not worker-facing
guidance for the current experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence


COMPATIBLE = "compatible"
FAILURE_ODD_KEYPOINT = "compatibility_failure_odd_keypoint"
FAILURE_DUPLICATE = "compatibility_failure_duplicate"
FAILURE_WRONG_ORDER = "compatibility_failure_wrong_order"
FAILURE_WRAPAROUND = "compatibility_failure_wraparound_unresolved"

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 512
PAIRING_THRESHOLD_RATIO = 0.05
PAIRING_RULE_VERSION = "official_userscript_nearest_x_strict_lt_v1"
DUPLICATE_CORNER_THRESHOLD_RATIO = 0.01
SEAM_EDGE_RATIO = 0.05
SEAM_GAP_RATIO = 0.5


@dataclass(frozen=True)
class PreviewPoint:
    """A Label Studio percent point converted into current-preview pixels."""

    x_percent: float
    y_percent: float
    x: float
    y: float
    point_id: str | None = None
    original_index: int | None = None


@dataclass(frozen=True)
class PreviewPair:
    """A current-preview ceiling/floor pair."""

    x: float
    y_ceiling: float
    y_floor: float
    p1: PreviewPoint
    p2: PreviewPoint
    original_order_index: int


@dataclass(frozen=True)
class PreviewCompatibilityResult:
    """Compatibility status for future deterministic assistant checks."""

    status: str
    pairs: tuple[PreviewPair, ...]
    ordered_corners: tuple[PreviewPair, ...]
    unpaired_points: tuple[PreviewPoint, ...]
    suggestion_allowed: bool
    allowed_adjustment_type: str
    compatibility_reason: str
    pairing_rule_version: str = PAIRING_RULE_VERSION


def _point_value(point: Mapping[str, object] | object, key: str) -> object:
    if isinstance(point, Mapping):
        return point[key]
    return getattr(point, key)


def _point_optional(point: Mapping[str, object] | object, key: str, default: object = None) -> object:
    if isinstance(point, Mapping):
        return point.get(key, default)
    return getattr(point, key, default)


def percent_to_pixel(
    point: Mapping[str, object] | object,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> PreviewPoint:
    """Convert Label Studio percent coordinates into preview pixel coordinates."""

    x_percent = float(_point_value(point, "x"))
    y_percent = float(_point_value(point, "y"))
    return PreviewPoint(
        x_percent=x_percent,
        y_percent=y_percent,
        x=x_percent * width / 100.0,
        y=y_percent * height / 100.0,
        point_id=(
            None
            if _point_optional(point, "point_id") is None
            else str(_point_optional(point, "point_id"))
        ),
        original_index=(
            None
            if _point_optional(point, "original_index") is None
            else int(_point_optional(point, "original_index"))
        ),
    )


def _normalize_points(
    points: Iterable[Mapping[str, object] | PreviewPoint],
    width: int,
    height: int,
) -> list[PreviewPoint]:
    normalized: list[PreviewPoint] = []
    for idx, point in enumerate(points):
        if isinstance(point, PreviewPoint):
            preview_point = point
            if preview_point.original_index is None:
                preview_point = PreviewPoint(
                    x_percent=preview_point.x_percent,
                    y_percent=preview_point.y_percent,
                    x=preview_point.x,
                    y=preview_point.y,
                    point_id=preview_point.point_id,
                    original_index=idx,
                )
        else:
            enriched = dict(point)
            enriched.setdefault("original_index", idx)
            preview_point = percent_to_pixel(enriched, width=width, height=height)
        normalized.append(preview_point)
    return normalized


def pair_keypoints_like_current_preview(
    points: Iterable[Mapping[str, object] | PreviewPoint],
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    threshold_ratio: float = PAIRING_THRESHOLD_RATIO,
) -> tuple[tuple[PreviewPair, ...], tuple[PreviewPoint, ...]]:
    """Pair keypoints by x like the current preview: sort by x, greedy nearest-x.

    The pairing threshold is W * 0.05 by default.
    """

    preview_points = _normalize_points(points, width=width, height=height)
    sorted_points = sorted(preview_points, key=lambda p: p.x)
    threshold = width * threshold_ratio
    used = [False] * len(sorted_points)
    pairs: list[PreviewPair] = []

    for i, point in enumerate(sorted_points):
        if used[i]:
            continue
        best_j = -1
        min_diff = float("inf")
        for j in range(i + 1, len(sorted_points)):
            if used[j]:
                continue
            diff = abs(sorted_points[j].x - point.x)
            if diff < threshold and diff < min_diff:
                min_diff = diff
                best_j = j
        if best_j == -1:
            continue

        other = sorted_points[best_j]
        used[i] = True
        used[best_j] = True
        order_candidates = [
            idx
            for idx in (point.original_index, other.original_index)
            if idx is not None
        ]
        original_order_index = min(order_candidates) if order_candidates else len(pairs)
        pairs.append(
            PreviewPair(
                x=(point.x + other.x) / 2.0,
                y_ceiling=min(point.y, other.y),
                y_floor=max(point.y, other.y),
                p1=point,
                p2=other,
                original_order_index=original_order_index,
            )
        )

    unpaired = tuple(
        point for idx, point in enumerate(sorted_points) if not used[idx]
    )
    return tuple(pairs), unpaired


def build_ordered_preview_corners(
    points: Iterable[Mapping[str, object] | PreviewPoint],
    preserve_order: bool = False,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> tuple[PreviewPair, ...]:
    """Build ordered corner pairs using current preview order semantics."""

    pairs, _ = pair_keypoints_like_current_preview(points, width=width, height=height)
    if preserve_order:
        return tuple(sorted(pairs, key=lambda pair: pair.original_order_index))
    return tuple(sorted(pairs, key=lambda pair: pair.x))


def _has_near_duplicate_corner(
    pairs: Sequence[PreviewPair],
    width: int,
    duplicate_threshold_ratio: float = DUPLICATE_CORNER_THRESHOLD_RATIO,
) -> bool:
    threshold = width * duplicate_threshold_ratio
    ordered = sorted(pairs, key=lambda pair: pair.x)
    for left, right in zip(ordered, ordered[1:]):
        if abs(right.x - left.x) < threshold:
            return True
    return False


def _has_preserve_order_conflict(pairs: Sequence[PreviewPair]) -> bool:
    preserve_order = [pair.x for pair in sorted(pairs, key=lambda pair: pair.original_order_index)]
    x_order = [pair.x for pair in sorted(pairs, key=lambda pair: pair.x)]
    return preserve_order != x_order


def _has_unresolved_wraparound(pairs: Sequence[PreviewPair], width: int) -> bool:
    if len(pairs) < 4:
        return False
    ordered_x = [pair.x for pair in sorted(pairs, key=lambda pair: pair.x)]
    near_left = ordered_x[0] <= width * SEAM_EDGE_RATIO
    near_right = ordered_x[-1] >= width * (1.0 - SEAM_EDGE_RATIO)
    if not (near_left and near_right):
        return False
    largest_internal_gap = max(
        (right - left for left, right in zip(ordered_x, ordered_x[1:])),
        default=0.0,
    )
    return largest_internal_gap > width * SEAM_GAP_RATIO


def check_preview_compatibility(
    points: Iterable[Mapping[str, object] | PreviewPoint],
    preserve_order: bool = False,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> PreviewCompatibilityResult:
    """Check whether keypoints are compatible with current 3D preview semantics."""

    preview_points = _normalize_points(points, width=width, height=height)
    pairs, unpaired = pair_keypoints_like_current_preview(
        preview_points,
        width=width,
        height=height,
    )
    ordered = (
        tuple(sorted(pairs, key=lambda pair: pair.original_order_index))
        if preserve_order
        else tuple(sorted(pairs, key=lambda pair: pair.x))
    )

    if len(preview_points) % 2 == 1 or unpaired:
        return PreviewCompatibilityResult(
            status=FAILURE_ODD_KEYPOINT,
            pairs=pairs,
            ordered_corners=ordered,
            unpaired_points=unpaired,
            suggestion_allowed=False,
            allowed_adjustment_type="none",
            compatibility_reason="odd_keypoint_count_or_unpaired_points",
        )

    if _has_near_duplicate_corner(pairs, width=width):
        return PreviewCompatibilityResult(
            status=FAILURE_DUPLICATE,
            pairs=pairs,
            ordered_corners=ordered,
            unpaired_points=unpaired,
            suggestion_allowed=False,
            allowed_adjustment_type="none",
            compatibility_reason="near_duplicate_corner_pair",
        )

    if preserve_order and _has_preserve_order_conflict(pairs):
        return PreviewCompatibilityResult(
            status=FAILURE_WRONG_ORDER,
            pairs=pairs,
            ordered_corners=ordered,
            unpaired_points=unpaired,
            suggestion_allowed=False,
            allowed_adjustment_type="none",
            compatibility_reason="preserve_order_conflicts_with_x_sorted_preview_order",
        )

    if _has_unresolved_wraparound(pairs, width=width):
        return PreviewCompatibilityResult(
            status=FAILURE_WRAPAROUND,
            pairs=pairs,
            ordered_corners=ordered,
            unpaired_points=unpaired,
            suggestion_allowed=False,
            allowed_adjustment_type="none",
            compatibility_reason="seam_adjacent_x_sort_order_unresolved",
        )

    return PreviewCompatibilityResult(
        status=COMPATIBLE,
        pairs=pairs,
        ordered_corners=ordered,
        unpaired_points=unpaired,
        suggestion_allowed=True,
        allowed_adjustment_type="closure_check_only",
        compatibility_reason="current_preview_pairing_and_order_compatible",
    )
