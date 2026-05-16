"""Preview-only suggestion candidates for the experiment-outside Manhattan toolchain.

This module turns M1 residual dictionaries into conservative review prompts for
lab-side automation. It does not produce snap_to_axis coordinates, per-corner
adjustment vectors, automatic corrections, 3D projection, UI panels, writeback
payloads, correctness labels, formal g_t, routing inputs, or worker-facing hints.
"""

from __future__ import annotations

from typing import Any, Mapping


SUGGESTION_VERSION = "manhattan_preview_suggestions_m2_v1"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"

THRESHOLDS = {
    "x_spacing_cv": {"medium": 0.25, "high": 0.75},
    "ceiling_y_range": {"medium": 32.0, "high": 96.0},
    "floor_y_range": {"medium": 32.0, "high": 96.0},
    "wall_height_range": {"medium": 64.0, "high": 160.0},
    "vertical_pair_x_residual": {"medium": 0.005, "high": 0.02},
}

FIELD_SUGGESTIONS = {
    "x_spacing_cv": "review_spacing_irregularity",
    "ceiling_y_range": "review_ceiling_alignment",
    "floor_y_range": "review_floor_alignment",
    "wall_height_range": "review_wall_height_inconsistency",
    "vertical_pair_x_residual": "review_vertical_pair_alignment",
}


def _base_suggestion(
    suggestion_type: str,
    reason: str,
    source_residual_field: str | None,
    severity: str,
) -> dict[str, Any]:
    return {
        "suggestion_type": suggestion_type,
        "reason": reason,
        "source_residual_field": source_residual_field,
        "severity": severity,
        "preview_only": True,
        "not_correctness": True,
        "suggestion_version": SUGGESTION_VERSION,
    }


def _severity(value: float, field: str) -> str | None:
    threshold = THRESHOLDS[field]
    if value >= threshold["high"]:
        return SEVERITY_HIGH
    if value >= threshold["medium"]:
        return SEVERITY_MEDIUM
    return None


def build_preview_suggestion_candidates(
    residual: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build conservative preview-only suggestion candidates from M1 residuals."""

    if residual.get("diagnostic_valid") is not True:
        return [
            _base_suggestion(
                suggestion_type="no_action",
                reason="residual_diagnostic_not_valid",
                source_residual_field=None,
                severity=SEVERITY_LOW,
            )
        ]

    suggestions: list[dict[str, Any]] = []
    for field, suggestion_type in FIELD_SUGGESTIONS.items():
        value = residual.get(field)
        if not isinstance(value, (int, float)):
            continue
        severity = _severity(float(value), field)
        if severity is None:
            continue
        suggestions.append(
            _base_suggestion(
                suggestion_type=suggestion_type,
                reason=f"{field} exceeds fixed conservative {severity} threshold",
                source_residual_field=field,
                severity=severity,
            )
        )

    if suggestions:
        return suggestions
    return [
        _base_suggestion(
            suggestion_type="no_action",
            reason="no_residual_field_exceeds_fixed_review_threshold",
            source_residual_field=None,
            severity=SEVERITY_LOW,
        )
    ]
