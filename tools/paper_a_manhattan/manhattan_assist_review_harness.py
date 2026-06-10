"""M15.6 review harness for Paper A Manhattan assist candidates.

This module builds offline review/evaluation sidecar rows for M14.x Manhattan
assist outputs. It does not train a scorer, create UI, apply candidates, snap,
reproject height, move walls, write annotations, connect to Label Studio, or
feed correctness, formal g_t, routing, worker quality metrics, or
P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_pair_assist import (
    ELIGIBLE,
    REVIEW_ONLY,
    SUPPRESS,
    diagnose_pair_alignment,
    propose_align_pair_x,
)


REVIEW_HARNESS_VERSION = "manhattan_assist_review_harness_m15_6_v1"
SUMMARY_SCHEMA_VERSION = "manhattan_assist_summary_schema_m15_6_1_v1"


def _is_true_like(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
    return None


def _manual_fields(manual_review: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(manual_review, Mapping):
        return {
            "has_manual_review": False,
            "manual_plausible_candidate": None,
            "manual_unsafe_candidate": None,
            "manual_algorithm_overfit": None,
            "manual_review_notes": None,
        }

    likely_issue = str(manual_review.get("likely_issue", "")).strip().lower()
    explicit_algorithm_overfit = _is_true_like(
        manual_review.get("manual_algorithm_overfit", manual_review.get("algorithm_overfit"))
    )
    manual_algorithm_overfit = (
        explicit_algorithm_overfit
        if explicit_algorithm_overfit is not None
        else likely_issue == "algorithm_overfit"
    )
    notes = (
        manual_review.get("manual_review_notes")
        or manual_review.get("reviewer_note")
        or manual_review.get("review_notes")
        or manual_review.get("notes")
    )
    return {
        "has_manual_review": True,
        "manual_plausible_candidate": manual_review.get("plausible_candidate"),
        "manual_unsafe_candidate": _is_true_like(manual_review.get("unsafe_candidate")),
        "manual_algorithm_overfit": manual_algorithm_overfit,
        "manual_review_notes": notes,
    }


def _movement_gate_status(proposal: Mapping[str, Any]) -> str:
    reasons = set(proposal.get("assist_reasons", []))
    if "max_abs_delta_exceeds_fit_fail_threshold" in reasons:
        return "suppress_large_delta"
    if "max_abs_delta_large" in reasons:
        return "review_only_large_delta"
    if "max_abs_delta_unavailable" in reasons:
        return "review_only_delta_unavailable"
    if proposal.get("candidate_pairs"):
        return "candidate_retained"
    return "not_candidate_returned"


def build_pair_assist_review_rows(
    records: Sequence[Mapping[str, Any]],
    operation: str = "align_pair_x",
) -> list[dict[str, Any]]:
    """Build JSON-friendly review rows for offline pair-assist evaluation."""
    rows: list[dict[str, Any]] = []
    for record in records:
        ordered_pairs = record.get("ordered_pairs", [])
        target_pair_index = record.get("target_pair_index")
        metadata = record.get("metadata")
        if operation == "align_pair_x":
            diagnosis = diagnose_pair_alignment(ordered_pairs, target_pair_index, metadata=metadata)
            proposal = propose_align_pair_x(ordered_pairs, target_pair_index, metadata=metadata)
        else:
            diagnosis = {
                "state_status": "failed",
                "target_pair_index": target_pair_index,
                "vertical_x_residual": None,
                "height_residual": None,
                "pair_warnings": [],
                "state_warnings": ["unsupported_operation"],
                "assist_status": SUPPRESS,
                "assist_reasons": ["unsupported_operation"],
            }
            proposal = {
                "candidate_pairs": [],
                "max_abs_delta": None,
                "assist_status": SUPPRESS,
                "assist_reasons": ["unsupported_operation"],
            }

        candidate_returned = bool(proposal.get("candidate_pairs"))
        manual_fields = _manual_fields(record.get("manual_review"))
        row = {
            "task_id": record.get("task_id"),
            "annotation_id": record.get("annotation_id"),
            "target_pair_index": diagnosis.get("target_pair_index", target_pair_index),
            "operation": operation,
            "state_status": diagnosis.get("state_status"),
            "assist_status": proposal.get("assist_status", diagnosis.get("assist_status")),
            "assist_reasons": list(proposal.get("assist_reasons", diagnosis.get("assist_reasons", []))),
            "state_warnings": list(diagnosis.get("state_warnings", [])),
            "pair_warnings": list(diagnosis.get("pair_warnings", [])),
            "vertical_x_residual": diagnosis.get("vertical_x_residual"),
            "height_residual": diagnosis.get("height_residual"),
            "max_abs_delta": proposal.get("max_abs_delta"),
            "candidate_returned": candidate_returned,
            "candidate_retained": candidate_returned,
            "movement_gate_status": _movement_gate_status(proposal),
            "review_harness_version": REVIEW_HARNESS_VERSION,
        }
        row.update(manual_fields)
        rows.append(row)
    return rows


def _rate(count: int, denominator: int) -> float:
    return count / denominator if denominator else 0.0


def _numeric_values(rows: Sequence[Mapping[str, Any]], field_name: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = row.get(field_name)
        if isinstance(value, bool) or value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)
    return sorted(values)


def _quantile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return values[lower_index]
    lower = values[lower_index]
    upper = values[upper_index]
    return lower + (upper - lower) * (position - lower_index)


def _has_large_delta_block(row: Mapping[str, Any]) -> bool:
    reasons = set(row.get("assist_reasons", []))
    return bool(
        reasons
        & {
            "max_abs_delta_large",
            "max_abs_delta_exceeds_fit_fail_threshold",
        }
    )


def _is_plausible_yes(row: Mapping[str, Any]) -> bool:
    return str(row.get("manual_plausible_candidate", "")).strip().lower() == "yes"


def summarize_pair_assist_review(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize pair-assist review rows without inferring correctness."""
    n_records = len(rows)
    manual_rows = [row for row in rows if row.get("has_manual_review")]
    manual_candidate_rows = [
        row for row in manual_rows
        if row.get("candidate_returned")
    ]
    deltas = _numeric_values(rows, "max_abs_delta")
    n_candidate_returned = sum(1 for row in rows if row.get("candidate_returned"))
    n_suppressed = sum(1 for row in rows if row.get("assist_status") == SUPPRESS)
    n_review_only = sum(1 for row in rows if row.get("assist_status") == REVIEW_ONLY)
    n_eligible = sum(1 for row in rows if row.get("assist_status") == ELIGIBLE)
    n_large_delta_blocked = sum(1 for row in rows if _has_large_delta_block(row))
    n_manual_review = len(manual_rows)
    n_missing_manual_review = sum(1 for row in rows if not row.get("has_manual_review"))
    n_manual_candidate_returned = len(manual_candidate_rows)
    n_manual_plausible_yes = sum(1 for row in manual_rows if _is_plausible_yes(row))
    n_manual_unsafe_candidate = sum(
        1 for row in manual_candidate_rows
        if row.get("manual_unsafe_candidate") is True
    )
    n_manual_algorithm_overfit = sum(
        1 for row in manual_rows
        if row.get("manual_algorithm_overfit") is True
    )
    return {
        "n_records": n_records,
        "n_candidate_returned": n_candidate_returned,
        "n_suppressed": n_suppressed,
        "n_review_only": n_review_only,
        "n_eligible": n_eligible,
        "n_large_delta_blocked": n_large_delta_blocked,
        "n_manual_review": n_manual_review,
        "n_missing_manual_review": n_missing_manual_review,
        "n_manual_candidate_returned": n_manual_candidate_returned,
        "n_manual_plausible_yes": n_manual_plausible_yes,
        "n_manual_unsafe_candidate": n_manual_unsafe_candidate,
        "n_manual_algorithm_overfit": n_manual_algorithm_overfit,
        "candidate_retention_rate": _rate(n_candidate_returned, n_records),
        "suppress_rate": _rate(n_suppressed, n_records),
        "review_only_rate": _rate(n_review_only, n_records),
        "eligible_rate": _rate(n_eligible, n_records),
        "large_delta_block_rate": _rate(n_large_delta_blocked, n_records),
        "unsafe_candidate_rate": _rate(
            n_manual_unsafe_candidate,
            len(manual_candidate_rows),
        ),
        "algorithm_overfit_rate": _rate(
            n_manual_algorithm_overfit,
            len(manual_rows),
        ),
        "manual_review_plausible_rate": _rate(
            n_manual_plausible_yes,
            len(manual_rows),
        ),
        "missing_manual_review_rate": _rate(
            n_missing_manual_review,
            n_records,
        ),
        "max_abs_delta_p50": _quantile(deltas, 0.5),
        "max_abs_delta_p90": _quantile(deltas, 0.9),
        "max_abs_delta_max": max(deltas) if deltas else None,
        "review_harness_version": REVIEW_HARNESS_VERSION,
        "summary_schema_version": SUMMARY_SCHEMA_VERSION,
    }


__all__ = [
    "REVIEW_HARNESS_VERSION",
    "SUMMARY_SCHEMA_VERSION",
    "build_pair_assist_review_rows",
    "summarize_pair_assist_review",
]
