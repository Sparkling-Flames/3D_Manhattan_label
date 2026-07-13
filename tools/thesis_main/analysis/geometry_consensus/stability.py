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


def stability_summary(records: list[dict[str, Any]], *, grid: int = 256, multimodal_cutoff: float = 0.8) -> dict[str, Any]:
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    pairwise = [
        pairwise_similarity(valid[i]["geometry"], valid[j]["geometry"], grid=grid)
        for i in range(len(valid))
        for j in range(i + 1, len(valid))
    ]
    boundary = [value["boundary_similarity"] for value in pairwise if value.get("boundary_similarity") is not None]
    wallwall = [value["wallwall_similarity"] for value in pairwise if value.get("wallwall_similarity") is not None]
    boundary_mode_count = wallwall_mode_count = 0
    boundary_largest_gap = wallwall_largest_gap = None
    boundary_margin = wallwall_margin = None
    if not boundary or not wallwall:
        status = "not_evaluable"
        medoid_worker = ""
    else:
        medoid_worker = min(
            valid,
            key=lambda record: -float(np.mean([pairwise_similarity(record["geometry"], other["geometry"], grid=grid)["boundary_similarity"] for other in valid if other is not record])),
        ).get("worker_id", "")
        boundary_mode_count, boundary_largest_gap = _mode_summary(boundary)
        wallwall_mode_count, wallwall_largest_gap = _mode_summary(wallwall)
        status = "multimodal_candidate" if boundary_mode_count > 1 or wallwall_mode_count > 1 else "stable_candidate"
        boundary_scores = sorted([(float(np.mean([pairwise_similarity(record["geometry"], other["geometry"], grid=grid)["boundary_similarity"] for other in valid if other is not record])), record.get("worker_id", "")) for record in valid], reverse=True)
        wallwall_scores = sorted([(float(np.mean([pairwise_similarity(record["geometry"], other["geometry"], grid=grid)["wallwall_similarity"] for other in valid if other is not record])), record.get("worker_id", "")) for record in valid], reverse=True)
        boundary_margin = boundary_scores[0][0] - boundary_scores[1][0] if len(boundary_scores) > 1 else None
        wallwall_margin = wallwall_scores[0][0] - wallwall_scores[1][0] if len(wallwall_scores) > 1 else None
    subset_statuses = []
    if len(valid) >= 4:
        for left, right in itertools.combinations(range(len(valid)), 2):
            subset = [record for index, record in enumerate(valid) if index not in {left, right}]
            subset_statuses.append(stability_summary(subset, grid=grid, multimodal_cutoff=multimodal_cutoff)["stability_status"])
    leave_two_out = "not_evaluable" if len(valid) < 4 else "robust" if subset_statuses and all(value == status for value in subset_statuses) else "sensitive"
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
        "boundary_mode_count": boundary_mode_count if boundary else 0,
        "wallwall_mode_count": wallwall_mode_count if wallwall else 0,
        "boundary_largest_gap": boundary_largest_gap if boundary else None,
        "wallwall_largest_gap": wallwall_largest_gap if wallwall else None,
        "medoid_margin_boundary": boundary_margin if boundary else None,
        "medoid_margin_wallwall": wallwall_margin if wallwall else None,
        "leave_two_out_status": leave_two_out,
        "medoid_worker_id": medoid_worker,
        "stability_status": status,
        "interpretation_allowed": False,
    }
