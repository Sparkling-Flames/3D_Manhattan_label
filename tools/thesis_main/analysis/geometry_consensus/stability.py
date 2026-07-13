from __future__ import annotations

from typing import Any

import itertools
import numpy as np

from .pairwise import pairwise_similarity


def _mode_summary(values: list[float], *, gap_cutoff: float = 0.15) -> tuple[int, float | None]:
    if len(values) < 4:
        return 1, None
    ordered = sorted(values)
    gaps = [ordered[index + 1] - ordered[index] for index in range(len(ordered) - 1)]
    largest = max(gaps)
    pivot = gaps.index(largest) + 1
    return (2 if largest >= gap_cutoff and pivot >= 2 and len(ordered) - pivot >= 2 else 1), largest


def _core_stability(records: list[dict[str, Any]], *, grid: int = 256) -> dict[str, Any]:
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    pairwise = [
        (i, j, pairwise_similarity(valid[i]["geometry"], valid[j]["geometry"], grid=grid))
        for i in range(len(valid))
        for j in range(i + 1, len(valid))
    ]
    boundary = [value["boundary_similarity"] for _, _, value in pairwise if value.get("boundary_similarity") is not None]
    wallwall = [value["wallwall_similarity"] for _, _, value in pairwise if value.get("wallwall_similarity") is not None]
    boundary_mode_count = wallwall_mode_count = 0
    boundary_largest_gap = wallwall_largest_gap = None
    boundary_margin = wallwall_margin = None
    if not boundary or not wallwall:
        status = "not_evaluable"
        boundary_medoid = wallwall_medoid = ""
        boundary_ambiguous = wallwall_ambiguous = False
        score_table = []
    else:
        def scores(index: int, channel: str) -> float:
            values = [item[channel] for left, right, item in pairwise if index in {left, right} and item.get(channel) is not None]
            return float(np.mean(values)) if values else float("-inf")
        boundary_scores = sorted([(scores(index, "boundary_similarity"), record.get("worker_id", "")) for index, record in enumerate(valid)], reverse=True)
        wallwall_scores = sorted([(scores(index, "wallwall_similarity"), record.get("worker_id", "")) for index, record in enumerate(valid)], reverse=True)
        boundary_ambiguous = len(boundary_scores) > 1 and abs(boundary_scores[0][0] - boundary_scores[1][0]) <= 1e-12
        wallwall_ambiguous = len(wallwall_scores) > 1 and abs(wallwall_scores[0][0] - wallwall_scores[1][0]) <= 1e-12
        boundary_medoid = "" if boundary_ambiguous else boundary_scores[0][1]
        wallwall_medoid = "" if wallwall_ambiguous else wallwall_scores[0][1]
        score_table = [{"worker_id": record.get("worker_id", ""), "boundary_score": scores(index, "boundary_similarity"), "wallwall_score": scores(index, "wallwall_similarity")} for index, record in enumerate(valid)]
        boundary_mode_count, boundary_largest_gap = _mode_summary(boundary)
        wallwall_mode_count, wallwall_largest_gap = _mode_summary(wallwall)
        status = "multimodal_candidate" if boundary_mode_count > 1 or wallwall_mode_count > 1 else "stable_candidate"
        boundary_margin = boundary_scores[0][0] - boundary_scores[1][0] if len(boundary_scores) > 1 else None
        wallwall_margin = wallwall_scores[0][0] - wallwall_scores[1][0] if len(wallwall_scores) > 1 else None
    return {
        "valid_k": len(valid),
        "boundary_similarity_mean": float(np.mean(boundary)) if boundary else None,
        "boundary_similarity_min": min(boundary) if boundary else None,
        "wallwall_similarity_mean": float(np.mean(wallwall)) if wallwall else None,
        "wallwall_similarity_min": min(wallwall) if wallwall else None,
        "q_boundary_mean": float(np.mean(boundary)) if boundary else None,
        "q_boundary_min": min(boundary) if boundary else None,
        "q_wallwall_mean": float(np.mean(wallwall)) if wallwall else None,
        "q_wallwall_min": min(wallwall) if wallwall else None,
        "boundary_mode_count": boundary_mode_count if boundary else 0, "wallwall_mode_count": wallwall_mode_count if wallwall else 0,
        "boundary_largest_gap": boundary_largest_gap if boundary else None, "wallwall_largest_gap": wallwall_largest_gap if wallwall else None,
        "medoid_margin_boundary": boundary_margin if boundary else None, "medoid_margin_wallwall": wallwall_margin if wallwall else None,
        "medoid_boundary_worker_id": boundary_medoid, "medoid_wallwall_worker_id": wallwall_medoid,
        "medoid_ambiguous": boundary_ambiguous or wallwall_ambiguous, "medoid_boundary_ambiguous": boundary_ambiguous, "medoid_wallwall_ambiguous": wallwall_ambiguous,
        "medoid_score_table_json": __import__("json").dumps(score_table, sort_keys=True),
        "medoid_worker_id": boundary_medoid if boundary_medoid == wallwall_medoid else "", "stability_status": status, "interpretation_allowed": False,
    }


def stability_summary(records: list[dict[str, Any]], *, grid: int = 256, multimodal_cutoff: float = 0.8) -> dict[str, Any]:
    result = _core_stability(records, grid=grid)
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    subset_statuses = []
    if len(valid) >= 4:
        for left, right in itertools.combinations(range(len(valid)), 2):
            subset = [record for index, record in enumerate(valid) if index not in {left, right}]
            subset_statuses.append(_core_stability(subset, grid=grid)["stability_status"])
    result["leave_two_out_status"] = "not_evaluable" if len(valid) < 4 else "robust" if subset_statuses and all(value == result["stability_status"] for value in subset_statuses) else "sensitive"
    return result
