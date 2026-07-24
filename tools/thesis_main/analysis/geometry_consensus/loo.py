from __future__ import annotations

from typing import Any

import hashlib
import json
import numpy as np
import statistics

from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou

from .pairwise import pairwise_similarity
from .stability import _maximum_complete_link_clusters


def _corners(geometry: dict[str, Any]) -> np.ndarray:
    return np.asarray([[row["x"] % geometry["width"], row["y_ceiling"]] for row in geometry.get("pairs", [])] + [[row["x"] % geometry["width"], row["y_floor"]] for row in geometry.get("pairs", [])], dtype=float)


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
        peer_similarities = {}
        for left in range(len(peers)):
            for right in range(left + 1, len(peers)):
                metrics = pairwise_similarity(peers[left]["geometry"], peers[right]["geometry"], grid=grid)
                values = metrics.get("boundary_similarity"), metrics.get("wallwall_similarity")
                peer_similarities[(left, right)] = min(values) if all(value is not None for value in values) else None
        cliques = _maximum_complete_link_clusters(tuple(range(len(peers))), peer_similarities, .8) if len(peers) >= 2 else []
        cluster = cliques[0] if len(cliques) == 1 and len(cliques[0]) >= 2 else tuple()
        medoid_scores = []
        for peer_index in cluster:
            values = [peer_similarities[tuple(sorted((peer_index, other)))] for other in cluster if other != peer_index]
            medoid_scores.append((float(np.mean(values)), peer_index))
        medoid_scores.sort(reverse=True)
        medoid_index = medoid_scores[0][1] if medoid_scores and (len(medoid_scores) == 1 or medoid_scores[0][0] > medoid_scores[1][0] + 1e-12) else None
        medoid = peers[medoid_index] if medoid_index is not None else {}
        q_loo = None
        if held_out.get("valid") and medoid:
            q_loo, _ = compute_layout_mask_iou(_corners(held_out), _corners(medoid["geometry"]), width=int(held_out["width"]), height=int(held_out["height"]))
        consensus_geometry = medoid.get("geometry", {})
        consensus_sha = hashlib.sha256(json.dumps(consensus_geometry, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if consensus_geometry else ""
        status = "evaluable" if q_loo is not None else "multimodal" if len(cliques) > 1 else "medoid_tie" if cluster and medoid_index is None else "insufficient_peer_support"
        out.append(
            {
                "worker_id": record.get("worker_id", ""),
                "task_id": record.get("task_id", ""),
                "canonical_annotation_id": record.get("canonical_annotation_id", ""),
                "held_out_valid": bool(held_out.get("valid")),
                "peer_count_excluding_self": compatible_peers,
                "valid_k": n_valid,
                "loo_boundary_median": statistics.median(boundary) if boundary else None,
                "loo_wallwall_median": statistics.median(wallwall) if wallwall else None,
                "q_boundary_median": statistics.median(boundary) if boundary else None,
                "q_wallwall_median": statistics.median(wallwall) if wallwall else None,
                "loo_boundary_values_json": boundary,
                "loo_wallwall_values_json": wallwall,
                "q_LOO_tu": q_loo,
                "loo_consensus_status": status,
                "loo_consensus_annotation_id": medoid.get("canonical_annotation_id") or medoid.get("annotation_id", ""),
                "loo_consensus_worker_id": medoid.get("worker_id", ""),
                "loo_consensus_geometry_sha256": consensus_sha,
                "loo_largest_cluster_support": len(cluster),
                "loo_maximum_cluster_count": len(cliques),
                "interpretation_allowed": q_loo is not None,
                "validity_status": "valid" if q_loo is not None else "not_evaluable",
            }
        )
    return out
