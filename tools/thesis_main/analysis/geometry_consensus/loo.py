from __future__ import annotations

from typing import Any

import statistics

from .pairwise import pairwise_similarity


def leave_one_out(records: list[dict[str, Any]], *, grid: int = 256) -> list[dict[str, Any]]:
    """Compute worker/task LOO similarity with the held-out worker excluded."""
    out = []
    for index, record in enumerate(records):
        held_out = record.get("geometry") or {}
        held_out_worker = str(record.get("worker_id", ""))
        peers = [other for j, other in enumerate(records) if j != index and str(other.get("worker_id", "")) != held_out_worker and (other.get("geometry") or {}).get("valid")]
        similarities = [pairwise_similarity(held_out, other.get("geometry") or {}, grid=grid) for other in peers]
        boundary = [row["boundary_similarity"] for row in similarities if row.get("boundary_similarity") is not None]
        wallwall = [row["wallwall_similarity"] for row in similarities if row.get("wallwall_similarity") is not None]
        compatible_peers = min(len(boundary), len(wallwall))
        n_valid = compatible_peers + (1 if held_out.get("valid") else 0)
        out.append(
            {
                "worker_id": record.get("worker_id", ""),
                "task_id": record.get("task_id", ""),
                "held_out_valid": bool(held_out.get("valid")),
                "peer_count_excluding_self": compatible_peers,
                "valid_k": n_valid,
                "loo_boundary_median": statistics.median(boundary) if boundary else None,
                "loo_wallwall_median": statistics.median(wallwall) if wallwall else None,
                "q_boundary_median": statistics.median(boundary) if boundary else None,
                "q_wallwall_median": statistics.median(wallwall) if wallwall else None,
                "loo_boundary_values_json": boundary,
                "loo_wallwall_values_json": wallwall,
                "interpretation_allowed": False,
                "validity_status": "candidate_only" if held_out.get("valid") and len(boundary) >= 2 and len(wallwall) >= 2 else "not_evaluable",
            }
        )
    return out
