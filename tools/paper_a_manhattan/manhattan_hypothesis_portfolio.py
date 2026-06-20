"""Portfolio selection for structured Manhattan hypothesis evaluations."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import build_hypothesis_ranking_key


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

    evidence_available = [entry for entry in eligible if entry["evaluation"]["evidence_consistency"]["evidence_status"] != "unavailable"]
    selected_ids: set[Any] = set()
    result = {
        "best_manhattan_feasible": bucket(eligible, lambda entry: (
            entry["evaluation"]["manhattan_feasibility"]["unresolved_edge_count"],
            entry["evaluation"]["manhattan_feasibility"]["wall_residual_max"],
        ), "no candidate passed the hard gate"),
        "best_height_consistent": bucket(eligible, lambda entry: (
            entry["evaluation"]["height_consistency"]["height_outlier_l1"],
            entry["evaluation"]["height_consistency"]["max_height_residual"],
        ), "no candidate passed the hard gate"),
        "best_short_wall_preserving": bucket(eligible, lambda entry: (
            len(entry["evaluation"]["layout_plausibility"]["short_wall_collapsed"]),
            len(entry["evaluation"]["layout_plausibility"]["new_short_wall_created"]),
            max(0.0, entry["evaluation"]["layout_plausibility"]["short_wall_deficit_delta"]),
        ), "no candidate passed the hard gate"),
        "best_low_movement": bucket(eligible, lambda entry: (
            entry["evaluation"]["movement_edit_cost"]["movement_l1_normalized"],
            entry["evaluation"]["movement_edit_cost"]["changed_endpoint_count"],
        ), "no candidate passed the hard gate"),
        "best_hohonet_consistent": bucket(evidence_available, lambda entry: (
            bool(entry["evaluation"]["evidence_consistency"].get("visual_conflict_flags")),
            entry["evaluation"]["evidence_consistency"].get("hohonet_floor_boundary_rmse_delta") or 0.0,
            entry["evaluation"]["evidence_consistency"].get("hohonet_ceiling_boundary_rmse_delta") or 0.0,
        ), "HoHoNet evidence unavailable for all hard-gate candidates" if eligible else "no candidate passed the hard gate"),
        "best_balanced": bucket(eligible, lambda entry: build_hypothesis_ranking_key(entry["evaluation"]), "no candidate passed the hard gate"),
    }
    for value in result.values():
        if value["candidate"] is not None:
            selected_ids.add(value["candidate"].get("candidate_id"))
    result["diagnostic_only_candidates"] = [entry for entry in eligible if entry["candidate"].get("candidate_id") not in selected_ids]
    result["suppressed_candidates"] = suppressed
    return result
