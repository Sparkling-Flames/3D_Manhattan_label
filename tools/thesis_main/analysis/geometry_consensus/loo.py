from __future__ import annotations

from typing import Any

from .pairwise import pairwise_similarity


def leave_one_out(records: list[dict[str, Any]], *, grid: int = 256) -> list[dict[str, Any]]:
    """Compute worker/task LOO similarity with the held-out worker excluded."""
    out = []
    for index, record in enumerate(records):
        held_out = record.get("geometry") or {}
        peers = [other for j, other in enumerate(records) if j != index and (other.get("geometry") or {}).get("valid")]
        similarities = [pairwise_similarity(held_out, other.get("geometry") or {}, grid=grid) for other in peers]
        values = [row["overall_similarity"] for row in similarities if row.get("overall_similarity") is not None]
        n_valid = len(values) + (1 if held_out.get("valid") else 0)
        out.append(
            {
                "worker_id": record.get("worker_id", ""),
                "task_id": record.get("task_id", ""),
                "held_out_valid": bool(held_out.get("valid")),
                "peer_count_excluding_self": len(peers),
                "valid_k": n_valid,
                "loo_similarity_mean": sum(values) / len(values) if values else None,
                "loo_similarity_min": min(values) if values else None,
                "loo_similarity_max": max(values) if values else None,
                "interpretation_allowed": False,
                "validity_status": "candidate_only" if n_valid >= 3 and values else "not_evaluable",
            }
        )
    return out
