from __future__ import annotations

from typing import Any

import numpy as np

from .pairwise import pairwise_similarity


def stability_summary(records: list[dict[str, Any]], *, grid: int = 256, multimodal_cutoff: float = 0.8) -> dict[str, Any]:
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    pairwise = [
        pairwise_similarity(valid[i]["geometry"], valid[j]["geometry"], grid=grid)["overall_similarity"]
        for i in range(len(valid))
        for j in range(i + 1, len(valid))
    ]
    pairwise = [value for value in pairwise if value is not None]
    if not pairwise:
        status = "not_evaluable"
        medoid_worker = ""
    else:
        medoid_worker = min(
            valid,
            key=lambda record: -float(np.mean([pairwise_similarity(record["geometry"], other["geometry"], grid=grid)["overall_similarity"] for other in valid if other is not record])),
        ).get("worker_id", "")
        status = "multimodal_candidate" if min(pairwise) < multimodal_cutoff else "stable_candidate"
    return {
        "valid_k": len(valid),
        "pairwise_similarity_mean": float(np.mean(pairwise)) if pairwise else None,
        "pairwise_similarity_min": min(pairwise) if pairwise else None,
        "pairwise_similarity_max": max(pairwise) if pairwise else None,
        "medoid_worker_id": medoid_worker,
        "stability_status": status,
        "interpretation_allowed": False,
    }
