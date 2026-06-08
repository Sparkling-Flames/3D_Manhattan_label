"""M14.3 candidate gating for Paper A Manhattan geometry candidates.

This module is a pure Python expert-side gating layer for experiment-outside
Manhattan geometry assist candidates. It does not modify fitting behavior, does
not write annotations, does not connect to Label Studio UI, and does not feed
formal g_t, routing, worker quality metrics, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_constrained_fit import (
    FIT_RESIDUAL_FAIL_THRESHOLD,
    HEIGHT_SPREAD_FAIL_THRESHOLD,
    HEIGHT_SPREAD_WARN_THRESHOLD,
    MAX_POINT_MOVE_FAIL_THRESHOLD,
)


GATE_VERSION = "manhattan_candidate_gate_m14_3_v1"

CANDIDATE_ALLOWED = "candidate_allowed"
EXPERT_REVIEW_ONLY = "expert_review_only"
SUPPRESS = "suppress"

# M15 smoke audit used this as the high-review large-delta line. M14.2 still
# owns the hard fail threshold imported above.
EXPERT_REVIEW_DELTA_THRESHOLD = 5.0

PREVIEW_BLOCKING_TOKENS = {
    "incompatible",
    "failure",
    "odd_keypoint",
    "duplicate",
    "wrong_order",
    "wraparound",
    "missing_corner",
    "too_few_corners",
}
METADATA_BLOCKING_TOKENS = {
    "oos_open_boundary",
    "oos_split_level",
    "oos_geometry",
    "not_manhattan_assumable",
    "open_boundary",
    "split_level",
    "non_manhattan",
}
WARNING_BLOCKING_TOKENS = {
    "self_crossing_input",
    "self_crossing_candidate",
    "wrap_seam_unresolved",
    "duplicate_keypoints",
    "layout_height_unstable",
    "implausible_layout_height",
    "candidate_moves_points_too_far",
    "fit_residual_too_high",
}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _as_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        tokens: list[str] = []
        for key, nested in value.items():
            tokens.extend(_as_tokens(key))
            tokens.extend(_as_tokens(nested))
        return tokens
    if isinstance(value, (list, tuple, set)):
        tokens = []
        for nested in value:
            tokens.extend(_as_tokens(nested))
        return tokens
    return [str(value).strip().lower()]


def _contains_any_token(value: Any, blocking_tokens: set[str]) -> list[str]:
    hits: list[str] = []
    for token in _as_tokens(value):
        for blocker in blocking_tokens:
            if blocker in token and blocker not in hits:
                hits.append(blocker)
    return sorted(hits)


def compute_max_abs_delta(per_point_delta: Any) -> float | None:
    """Return max absolute dx/dy component from a fit `per_point_delta` payload."""
    if not isinstance(per_point_delta, Sequence) or isinstance(per_point_delta, (str, bytes)):
        return None
    values: list[float] = []
    for row in per_point_delta:
        if not isinstance(row, Mapping):
            continue
        for key, value in row.items():
            if key == "pair_index":
                continue
            number = _as_float(value)
            if number is not None:
                values.append(abs(number))
    return max(values) if values else None


def _merged_record(fit_record: Mapping[str, Any], context: Mapping[str, Any] | None) -> dict[str, Any]:
    nested_fit = fit_record.get("fit")
    merged: dict[str, Any] = dict(nested_fit) if isinstance(nested_fit, Mapping) else {}
    merged.update(fit_record)
    if context:
        merged.update(context)
    return merged


def _finish(
    *,
    blocking_reasons: list[str],
    review_reasons: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    if blocking_reasons:
        status = SUPPRESS
    elif review_reasons:
        status = EXPERT_REVIEW_ONLY
    else:
        status = CANDIDATE_ALLOWED
    gate_reasons = blocking_reasons if blocking_reasons else review_reasons or ["clean_candidate"]
    return {
        "gate_status": status,
        "gate_reasons": gate_reasons,
        "blocking_reasons": blocking_reasons,
        "non_blocking_warnings": warnings,
        "gate_version": GATE_VERSION,
    }


def gate_manhattan_candidate(
    fit_record: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Gate a Manhattan fit candidate for expert-side use only.

    `gate_status` is a candidate-safety decision for the experiment-outside
    Manhattan assistant. It is not correctness, not formal g_t, not routing,
    and not a worker quality metric.
    """
    record = _merged_record(fit_record, context)
    blocking_reasons: list[str] = []
    review_reasons: list[str] = []
    non_blocking_warnings: list[str] = []

    fit_status = str(record.get("fit_status", "")).strip().lower()
    if fit_status != "ok":
        blocking_reasons.append(f"fit_status_not_ok:{fit_status or 'missing'}")

    preview_hits = _contains_any_token(record.get("preview_status"), PREVIEW_BLOCKING_TOKENS)
    blocking_reasons.extend(f"preview_{hit}" for hit in preview_hits)

    metadata_payload = record.get("metadata")
    if metadata_payload is None:
        metadata_payload = {
            "scope": record.get("scope") or record.get("scope_vote"),
            "layout_type": record.get("layout_type"),
            "manhattan_assumable": record.get("manhattan_assumable"),
        }
    metadata_hits = _contains_any_token(metadata_payload, METADATA_BLOCKING_TOKENS)
    if isinstance(metadata_payload, Mapping) and metadata_payload.get("manhattan_assumable") is False:
        metadata_hits.append("not_manhattan_assumable")
    blocking_reasons.extend(f"metadata_{hit}" for hit in sorted(set(metadata_hits)))

    warning_hits = _contains_any_token(record.get("warnings"), WARNING_BLOCKING_TOKENS)
    blocking_reasons.extend(f"warning_{hit}" for hit in warning_hits)

    supplied_delta = _as_float(record.get("max_abs_delta"))
    computed_delta = compute_max_abs_delta(record.get("per_point_delta"))
    max_abs_delta = supplied_delta if supplied_delta is not None else computed_delta
    if max_abs_delta is not None:
        if max_abs_delta > MAX_POINT_MOVE_FAIL_THRESHOLD:
            blocking_reasons.append("max_abs_delta_exceeds_fit_fail_threshold")
        elif max_abs_delta >= EXPERT_REVIEW_DELTA_THRESHOLD:
            review_reasons.append("max_abs_delta_large")

    layout_height_spread = _as_float(record.get("layout_height_spread"))
    if layout_height_spread is not None:
        if layout_height_spread > HEIGHT_SPREAD_FAIL_THRESHOLD:
            blocking_reasons.append("layout_height_spread_exceeds_fail_threshold")
        elif layout_height_spread > HEIGHT_SPREAD_WARN_THRESHOLD:
            review_reasons.append("layout_height_spread_high")

    fit_residual = _as_float(record.get("fit_residual"))
    if fit_residual is not None and fit_residual > FIT_RESIDUAL_FAIL_THRESHOLD:
        blocking_reasons.append("fit_residual_exceeds_fail_threshold")

    if str(record.get("fit_confidence", "")).strip().lower() == "low":
        review_reasons.append("fit_confidence_low")

    warning_values = _as_tokens(record.get("warnings"))
    for warning in warning_values:
        if warning and warning not in WARNING_BLOCKING_TOKENS:
            non_blocking_warnings.append(warning)

    return _finish(
        blocking_reasons=sorted(set(blocking_reasons)),
        review_reasons=sorted(set(review_reasons)),
        warnings=sorted(set(non_blocking_warnings)),
    )


__all__ = [
    "CANDIDATE_ALLOWED",
    "EXPERT_REVIEW_ONLY",
    "GATE_VERSION",
    "SUPPRESS",
    "compute_max_abs_delta",
    "gate_manhattan_candidate",
]
