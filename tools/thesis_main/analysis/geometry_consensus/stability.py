from __future__ import annotations

from typing import Any

import numpy as np

from .pairwise import pairwise_similarity


def stability_summary(records: list[dict[str, Any]], *, grid: int = 256, multimodal_cutoff: float = 0.8) -> dict[str, Any]:
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    pairwise = [
        pairwise_similarity(valid[i]["geometry"], valid[j]["geometry"], grid=grid)
        for i in range(len(valid))
        for j in range(i + 1, len(valid))
    ]
    boundary = [value["boundary_similarity"] for value in pairwise if value.get("boundary_similarity") is not None]
    wallwall = [value["wallwall_similarity"] for value in pairwise if value.get("wallwall_similarity") is not None]
    if not boundary or not wallwall:
        status = "not_evaluable"
        medoid_worker = ""
    else:
        medoid_worker = min(
            valid,
            key=lambda record: -float(np.mean([pairwise_similarity(record["geometry"], other["geometry"], grid=grid)["boundary_similarity"] for other in valid if other is not record])),
        ).get("worker_id", "")
        status = "multimodal_candidate" if min(boundary) < multimodal_cutoff or min(wallwall) < multimodal_cutoff else "stable_candidate"
    return {
        "valid_k": len(valid),
        "boundary_similarity_mean": float(np.mean(boundary)) if boundary else None,
        "boundary_similarity_min": min(boundary) if boundary else None,
        "wallwall_similarity_mean": float(np.mean(wallwall)) if wallwall else None,
        "wallwall_similarity_min": min(wallwall) if wallwall else None,
        "medoid_margin": None,
        "leave_two_out_status": "not_evaluable" if len(valid) < 4 else "candidate_only",
        "medoid_worker_id": medoid_worker,
        "stability_status": status,
        "interpretation_allowed": False,
    }
