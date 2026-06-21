"""Portfolio selection for structured Manhattan hypothesis evaluations."""

from __future__ import annotations

import math
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

    evidence_available = [entry for entry in eligible if entry["evaluation"]["evidence_consistency"]["evidence_status"] == "available"]

    def metric(value: Any) -> float:
        return float(value) if isinstance(value, (int, float)) else math.inf

    def l1_vector(entry: Mapping[str, Any]) -> tuple[float, ...]:
        manhattan = entry["evaluation"]["manhattan_feasibility"]
        direction = manhattan.get("direction_family_fit")
        parallel = manhattan.get("parallel_family_residual")
        direction_summary = direction.get("residual_summary", {}) if isinstance(direction, Mapping) else {}
        return (
            float(direction is None),
            metric(direction_summary.get("max_deg")),
            metric(direction_summary.get("median_deg")),
            float(parallel is None),
            metric(parallel.get("max_deg")) if isinstance(parallel, Mapping) else math.inf,
            metric(parallel.get("median_deg")) if isinstance(parallel, Mapping) else math.inf,
            metric(manhattan.get("turn_residual_max")),
            metric(manhattan.get("turn_residual_median")),
            metric(manhattan.get("unresolved_edge_count")),
            metric(manhattan.get("local_window_residual")),
            metric(manhattan.get("floor_ceiling_column_consistency")),
        )

    def dominates(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
        a, b = l1_vector(left), l1_vector(right)
        return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))

    manhattan_frontier = [
        entry for entry in eligible
        if not any(dominates(other, entry) for other in eligible if other is not entry)
    ]

    def evidence_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
        evidence = entry["evaluation"]["evidence_consistency"]
        deltas = [
            metric(evidence.get(name))
            for name in (
                "candidate_corner_column_delta",
                "hohonet_floor_boundary_rmse_delta",
                "hohonet_ceiling_boundary_rmse_delta",
                "seam_consistency_delta",
            )
        ]
        finite = [value for value in deltas if math.isfinite(value)]
        return (
            evidence.get("evidence_status") != "available",
            len(evidence.get("visual_conflict_flags") or []),
            sum(value > 0 for value in finite),
            sum(max(0.0, value) for value in finite),
            *deltas,
        )

    def manhattan_key(entry: Mapping[str, Any]) -> tuple[Any, ...]:
        evaluation = entry["evaluation"]
        manhattan = evaluation["manhattan_feasibility"]
        direction = manhattan.get("direction_family_fit")
        parallel = manhattan.get("parallel_family_residual")
        direction_summary = direction.get("residual_summary", {}) if isinstance(direction, Mapping) else {}
        plane = evaluation.get("plane_proxy_metrics", {})
        plane_parallel = plane.get("wall_plane_parallel_consistency", {})
        plane_orthogonal = plane.get("wall_plane_orthogonal_consistency", {})
        return (
            direction is None,
            metric(direction_summary.get("max_deg")),
            metric(direction_summary.get("median_deg")),
            parallel is None,
            metric(parallel.get("max_deg")) if isinstance(parallel, Mapping) else math.inf,
            metric(parallel.get("median_deg")) if isinstance(parallel, Mapping) else math.inf,
            plane_parallel.get("status") != "available",
            metric(plane_parallel.get("max_deg")),
            metric(plane_parallel.get("median_deg")),
            plane_orthogonal.get("status") != "available",
            metric(plane_orthogonal.get("orthogonal_residual_deg")),
            int(manhattan["unresolved_edge_count"]),
            float(manhattan["wall_residual_max"]),
            float(manhattan["wall_residual_median"]),
        )

    selected_ids: set[Any] = set()
    result = {
        "best_manhattan_feasible": bucket(
            manhattan_frontier,
            lambda entry: (*evidence_key(entry), *manhattan_key(entry)),
            "no candidate passed the hard gate",
        ),
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
