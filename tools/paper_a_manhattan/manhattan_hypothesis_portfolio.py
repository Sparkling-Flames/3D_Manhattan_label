"""Portfolio selection for structured Manhattan hypothesis evaluations."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
    build_hypothesis_ranking_layers,
)


def build_hypothesis_portfolio(
    candidate_rows: Sequence[Mapping[str, Any]],
    structured_evaluations: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    evaluations = list(structured_evaluations) if structured_evaluations is not None else [row["constrained_evaluation"] for row in candidate_rows]
    if len(candidate_rows) != len(evaluations):
        raise ValueError("candidate_rows and structured_evaluations must have equal length")
    entries = [{"candidate": dict(row), "evaluation": evaluation} for row, evaluation in zip(candidate_rows, evaluations)]
    eligible = [entry for entry in entries if entry["evaluation"]["feasibility"]["hard_gate_passed"]]
    suppressed = [entry for entry in entries if not entry["evaluation"]["feasibility"]["hard_gate_passed"]]

    def bucket(candidates: Sequence[Mapping[str, Any]], key: Any, reason: str) -> dict[str, Any]:
        if not candidates:
            return {"candidate": None, "reason": reason}
        selected = min(candidates, key=key)
        return {"candidate": selected["candidate"], "evaluation": selected["evaluation"], "reason": None}

    evidence_available = [entry for entry in eligible if entry["evaluation"]["evidence_consistency"]["evidence_status"] == "available"]

    def metric(value: Any) -> float:
        return float(value) if isinstance(value, (int, float)) else math.inf

    def l1_vector(entry: Mapping[str, Any]) -> tuple[Any, ...]:
        return build_hypothesis_ranking_layers(entry["evaluation"])["L1"]

    def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
        a, b = l1_vector(left), l1_vector(right)
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    manhattan_frontier = [
        entry for entry in eligible
        if not any(dominates(other, entry) for other in eligible if other is not entry)
    ]

    def evidence_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
        return build_hypothesis_ranking_layers(entry["evaluation"])["L2"]

    def manhattan_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
        return build_hypothesis_ranking_layers(entry["evaluation"])["L1"]

    selected_ids: set[Any] = set()
    result = {
        "best_manhattan_feasible": bucket(
            manhattan_frontier,
            manhattan_key,
            "no candidate passed the hard gate",
        ),
        "best_height_consistent": bucket(eligible, lambda entry: (
            entry["evaluation"]["height_consistency"]["height_outlier_l1"],
            entry["evaluation"]["height_consistency"]["max_height_residual"],
        ), "no candidate passed the hard gate"),
        "best_short_wall_preserving": bucket(
            eligible,
            lambda entry: build_hypothesis_ranking_layers(entry["evaluation"])["L4"],
            "no candidate passed the hard gate",
        ),
        "best_low_movement": bucket(eligible, lambda entry: (
            entry["evaluation"]["movement_edit_cost"]["movement_l1_normalized"],
            entry["evaluation"]["movement_edit_cost"]["changed_endpoint_count"],
        ), "no candidate passed the hard gate"),
        "best_hohonet_consistent": bucket(
            evidence_available,
            evidence_key,
            "HoHoNet evidence unavailable for all hard-gate candidates" if eligible else "no candidate passed the hard gate",
        ),
        "best_balanced": bucket(
            manhattan_frontier,
            lambda entry: (*evidence_key(entry), *build_hypothesis_ranking_key(entry["evaluation"])),
            "no candidate passed the hard gate",
        ),
    }
    for value in result.values():
        evidence = value.get("evaluation", {}).get("evidence_consistency", {})
        value["selection_status"] = "selected_but_audit_blocked" if value.get("candidate") else "unavailable"
        value["layer_status"] = (
            "diagnostic_only"
            if evidence.get("evidence_status") == "available" and not evidence.get("visual_conflict_flags")
            else "needs_manual_review"
        ) if value.get("candidate") else "unavailable"
        value["accepted"] = False
        value["downstream_recommendation"] = False
    for value in result.values():
        if value["candidate"] is not None:
            selected_ids.add(value["candidate"].get("candidate_id"))
    result["diagnostic_only_candidates"] = [entry for entry in eligible if entry["candidate"].get("candidate_id") not in selected_ids]
    result["suppressed_candidates"] = suppressed
    return result
