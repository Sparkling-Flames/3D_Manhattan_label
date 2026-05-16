"""M1 preview-geometry residuals for the experiment-outside Manhattan toolchain.

This module computes offline residual diagnostics only after keypoints are
compatible with the current 3D preview parser. Results describe preview geometry
stability; they are not correctness labels, not worker quality evidence, not
formal g_t, not routing inputs, and not worker-facing guidance. The module does
not implement snap_to_axis, adjustment vectors, 3D projection, Three.js geometry,
realtime panels, UI hooks, or file I/O.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from tools.manhattan_preview_compat import (
    COMPATIBLE,
    DEFAULT_WIDTH,
    PreviewCompatibilityResult,
    PreviewPair,
)


RESIDUAL_VERSION = "manhattan_preview_residual_m1_v1"


def _base_output(
    diagnostic_valid: bool,
    exclusion_reason: str | None,
    n_corners: int,
) -> dict[str, Any]:
    return {
        "diagnostic_valid": diagnostic_valid,
        "exclusion_reason": exclusion_reason,
        "n_corners": n_corners,
        "x_spacing_cv": None,
        "ceiling_y_range": None,
        "floor_y_range": None,
        "wall_height_range": None,
        "vertical_pair_x_residual": None,
        "closure_status": None,
        "residual_version": RESIDUAL_VERSION,
    }


def _range(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return max(values) - min(values)


def _coefficient_of_variation(values: Sequence[float]) -> float | None:
    if not values:
        return None
    mean_value = sum(values) / len(values)
    if abs(mean_value) <= 1e-12:
        return None
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return math.sqrt(variance) / abs(mean_value)


def _vertical_pair_x_residual(pairs: Sequence[PreviewPair], width: float) -> float | None:
    if not pairs:
        return None
    scale = max(float(width), 1.0)
    return sum(abs(pair.p1.x - pair.p2.x) / scale for pair in pairs) / len(pairs)


def compute_residual_from_pairs(
    ordered_pairs: Sequence[PreviewPair],
    width: int = DEFAULT_WIDTH,
) -> dict[str, Any]:
    """Compute M1 residual fields from current-preview ordered corner pairs."""

    pairs = tuple(ordered_pairs)
    if len(pairs) < 2:
        return _base_output(
            diagnostic_valid=False,
            exclusion_reason="insufficient_compatible_corners",
            n_corners=len(pairs),
        )

    ordered = tuple(sorted(pairs, key=lambda pair: pair.x))
    x_values = [pair.x for pair in ordered]
    x_spacings = [right - left for left, right in zip(x_values, x_values[1:])]
    ceiling_values = [pair.y_ceiling for pair in ordered]
    floor_values = [pair.y_floor for pair in ordered]
    wall_heights = [pair.y_floor - pair.y_ceiling for pair in ordered]

    out = _base_output(
        diagnostic_valid=True,
        exclusion_reason=None,
        n_corners=len(ordered),
    )
    out["x_spacing_cv"] = _coefficient_of_variation(x_spacings)
    out["ceiling_y_range"] = _range(ceiling_values)
    out["floor_y_range"] = _range(floor_values)
    out["wall_height_range"] = _range(wall_heights)
    out["vertical_pair_x_residual"] = _vertical_pair_x_residual(ordered, width=width)
    out["closure_status"] = "implicit_preview_loop_closure"
    return out


def compute_residual_from_compatibility(
    result: PreviewCompatibilityResult,
    width: int = DEFAULT_WIDTH,
) -> dict[str, Any]:
    """Compute M1 residual fields only for compatible preview parser results."""

    if result.status != COMPATIBLE:
        return _base_output(
            diagnostic_valid=False,
            exclusion_reason=result.status,
            n_corners=len(result.ordered_corners),
        )
    return compute_residual_from_pairs(result.ordered_corners, width=width)


def compute_m1_residual(
    value: PreviewCompatibilityResult | Sequence[PreviewPair],
    width: int = DEFAULT_WIDTH,
) -> dict[str, Any]:
    """Compute M1 residuals from a compatibility result or ordered pairs."""

    if isinstance(value, PreviewCompatibilityResult):
        return compute_residual_from_compatibility(value, width=width)
    return compute_residual_from_pairs(value, width=width)
