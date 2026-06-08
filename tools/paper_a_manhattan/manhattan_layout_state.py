"""M14.4 RoomLayoutState and pair diagnostics for Paper A Manhattan tools.

This module converts ordered Label Studio paired corners into an enclosed-only
geometry state for expert-side diagnostics. It does not apply, snap, move walls,
adjust room height, write annotations, integrate with Label Studio UI, or feed
formal g_t, routing, worker quality metrics, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_constrained_fit import (
    CAMERA_HEIGHT,
    HEIGHT_SPREAD_WARN_THRESHOLD,
    MIN_PAIR_COUNT,
    SEAM_EDGE_THRESHOLD,
    VERTICAL_X_WARN_THRESHOLD,
    ls_x_to_u,
    ls_y_to_v,
    parse_ordered_pairs,
)


STATE_VERSION = "manhattan_layout_state_m14_4_v1"
HEIGHT_RESIDUAL_ANCHOR_THRESHOLD = HEIGHT_SPREAD_WARN_THRESHOLD
METADATA_EXCLUSION_TOKENS = {
    "oos_open_boundary",
    "oos_split_level",
    "oos_geometry",
    "oos_insufficient",
    "open_boundary",
    "split_level",
    "non_manhattan",
}


@dataclass(frozen=True)
class CornerState:
    pair_index: int
    top: dict[str, float]
    bottom: dict[str, float]
    center_x: float
    u_rad: float
    floor_distance: float
    ceiling_height_estimate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WallState:
    wall_index: int
    from_pair_index: int
    to_pair_index: int
    length: float
    direction_rad: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PairDiagnostic:
    pair_index: int
    vertical_x_residual: float
    height_residual: float
    top_bottom_delta_y: float
    is_anchor_candidate: bool
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RoomLayoutState:
    camera_height: float
    layout_height_candidate: float | None
    layout_height_spread: float | None
    corners: list[CornerState]
    walls: list[WallState]
    pair_diagnostics: list[PairDiagnostic]
    state_status: str
    state_warnings: list[str]
    state_version: str = STATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_height": self.camera_height,
            "layout_height_candidate": self.layout_height_candidate,
            "layout_height_spread": self.layout_height_spread,
            "corners": [corner.to_dict() for corner in self.corners],
            "walls": [wall.to_dict() for wall in self.walls],
            "pair_diagnostics": [diagnostic.to_dict() for diagnostic in self.pair_diagnostics],
            "state_status": self.state_status,
            "state_warnings": list(self.state_warnings),
            "state_version": self.state_version,
        }


@dataclass(frozen=True)
class _BevPoint:
    x: float
    y: float


def _is_false_like(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"false", "0", "no"}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value == 0
    return False


def _metadata_exclusion(metadata: Mapping[str, Any] | None) -> str | None:
    if not metadata:
        return None
    values = [metadata.get("scope"), metadata.get("layout_type")]
    for value in values:
        if value is not None and str(value).strip().lower() in METADATA_EXCLUSION_TOKENS:
            return str(value).strip().lower()
    for token in METADATA_EXCLUSION_TOKENS:
        if metadata.get(token):
            return token
    if _is_false_like(metadata.get("manhattan_assumable")):
        return "not_manhattan_assumable"
    return None


def _failed_state(reason: str, *, camera_height: float, status: str = "failed") -> RoomLayoutState:
    return RoomLayoutState(
        camera_height=camera_height,
        layout_height_candidate=None,
        layout_height_spread=None,
        corners=[],
        walls=[],
        pair_diagnostics=[],
        state_status=status,
        state_warnings=[reason],
    )


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _layout_height_spread(values: Sequence[float]) -> float:
    if len(values) <= 1:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        lower = ordered[:mid]
        upper = ordered[mid + 1 :]
    else:
        lower = ordered[:mid]
        upper = ordered[mid:]
    if not lower or not upper:
        return 0.0
    return _median(upper) - _median(lower)


def _floor_distance(pair: Any, camera_height: float) -> tuple[float, list[str]]:
    v_floor = ls_y_to_v(pair.bottom.y)
    if v_floor >= -1e-6:
        return camera_height, ["floor_not_below_horizon_distance_fallback"]
    return camera_height / max(math.tan(-v_floor), 1e-6), []


def _corner_to_bev(corner: CornerState) -> _BevPoint:
    return _BevPoint(
        corner.floor_distance * math.cos(corner.u_rad),
        corner.floor_distance * math.sin(corner.u_rad),
    )


def _wrap_seam_unresolved(center_xs: Sequence[float]) -> bool:
    return min(center_xs) < SEAM_EDGE_THRESHOLD and max(center_xs) > 100.0 - SEAM_EDGE_THRESHOLD


def _build_walls(corners: Sequence[CornerState]) -> list[WallState]:
    bev_points = [_corner_to_bev(corner) for corner in corners]
    walls: list[WallState] = []
    for index, point in enumerate(bev_points):
        next_index = (index + 1) % len(bev_points)
        nxt = bev_points[next_index]
        dx = nxt.x - point.x
        dy = nxt.y - point.y
        walls.append(
            WallState(
                wall_index=index + 1,
                from_pair_index=corners[index].pair_index,
                to_pair_index=corners[next_index].pair_index,
                length=math.hypot(dx, dy),
                direction_rad=math.atan2(dy, dx),
            )
        )
    return walls


def build_room_layout_state(
    ordered_pairs: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any] | None = None,
    camera_height: float = CAMERA_HEIGHT,
) -> dict[str, Any]:
    """Build an enclosed-only RoomLayoutState for diagnostics.

    The result is JSON-friendly and diagnostic only. It is not a correction
    instruction and has no annotation writeback or formal artifact role.
    """
    exclusion = _metadata_exclusion(metadata)
    if exclusion:
        return _failed_state(exclusion, camera_height=camera_height, status="excluded").to_dict()

    try:
        pairs = parse_ordered_pairs(ordered_pairs)
    except ValueError as exc:
        return _failed_state(str(exc), camera_height=camera_height).to_dict()

    if len(pairs) < MIN_PAIR_COUNT:
        return _failed_state("pair_count_lt_4", camera_height=camera_height).to_dict()
    if len(pairs) % 2 != 0:
        return _failed_state("odd_pair_count", camera_height=camera_height).to_dict()

    center_xs = [pair.center_x for pair in pairs]
    if _wrap_seam_unresolved(center_xs):
        return _failed_state("wrap_seam_unresolved", camera_height=camera_height).to_dict()

    corners: list[CornerState] = []
    state_warnings: list[str] = []
    for pair in pairs:
        floor_distance, warnings = _floor_distance(pair, camera_height)
        state_warnings.extend(warnings)
        center_x = pair.center_x
        u_rad = ls_x_to_u(center_x)
        ceiling_v = ls_y_to_v(pair.top.y)
        height_estimate = camera_height + floor_distance * math.tan(ceiling_v)
        corners.append(
            CornerState(
                pair_index=pair.pair_index,
                top={"x": pair.top.x, "y": pair.top.y},
                bottom={"x": pair.bottom.x, "y": pair.bottom.y},
                center_x=center_x,
                u_rad=u_rad,
                floor_distance=floor_distance,
                ceiling_height_estimate=height_estimate,
            )
        )

    heights = [corner.ceiling_height_estimate for corner in corners]
    layout_height_candidate = _median(heights)
    layout_height_spread = _layout_height_spread(heights)
    if layout_height_spread > HEIGHT_SPREAD_WARN_THRESHOLD:
        state_warnings.append("layout_height_spread_high")

    pair_diagnostics: list[PairDiagnostic] = []
    for pair, corner in zip(pairs, corners):
        warnings: list[str] = []
        vertical_x_residual = abs(pair.top.x - pair.bottom.x)
        height_residual = abs(corner.ceiling_height_estimate - layout_height_candidate)
        top_bottom_delta_y = pair.bottom.y - pair.top.y
        if vertical_x_residual > VERTICAL_X_WARN_THRESHOLD:
            warnings.append("vertical_corner_x_mismatch")
        if height_residual > HEIGHT_RESIDUAL_ANCHOR_THRESHOLD:
            warnings.append("height_residual_high")
        if top_bottom_delta_y <= 0:
            warnings.append("top_not_above_bottom")
        pair_diagnostics.append(
            PairDiagnostic(
                pair_index=pair.pair_index,
                vertical_x_residual=vertical_x_residual,
                height_residual=height_residual,
                top_bottom_delta_y=top_bottom_delta_y,
                is_anchor_candidate=not warnings,
                warnings=warnings,
            )
        )

    state = RoomLayoutState(
        camera_height=camera_height,
        layout_height_candidate=layout_height_candidate,
        layout_height_spread=layout_height_spread,
        corners=corners,
        walls=_build_walls(corners),
        pair_diagnostics=pair_diagnostics,
        state_status="ok",
        state_warnings=sorted(set(state_warnings)),
    )
    return state.to_dict()


__all__ = [
    "CornerState",
    "PairDiagnostic",
    "RoomLayoutState",
    "STATE_VERSION",
    "WallState",
    "build_room_layout_state",
]
