from __future__ import annotations

from typing import Any

import hashlib
import itertools
import json
import numpy as np
import statistics

from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou_from_normalized_pairs

from .pairwise import pairwise_similarity
from .stability import _complete_link_cluster, _maximum_complete_link_clusters


def _corners(geometry: dict[str, Any]) -> np.ndarray:
    return np.asarray([[row["x"] % geometry["width"], row["y_ceiling"]] for row in geometry.get("pairs", [])] + [[row["x"] % geometry["width"], row["y_floor"]] for row in geometry.get("pairs", [])], dtype=float)


def leave_one_out(
    records: list[dict[str, Any]], *, grid: int = 256,
    similarity_cutoff: float = 0.8, tie_iou_range_cutoff: float = 0.02,
) -> list[dict[str, Any]]:
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
        peer_metrics = {}
        compatible_edges = {}
        for left in range(len(peers)):
            for right in range(left + 1, len(peers)):
                metrics = pairwise_similarity(peers[left]["geometry"], peers[right]["geometry"], grid=grid)
                peer_metrics[(left, right)] = metrics
                boundary_value, wall_value = metrics.get("boundary_similarity"), metrics.get("wallwall_similarity")
                compatible_edges[(left, right)] = 1.0 if boundary_value is not None and wall_value is not None and boundary_value >= similarity_cutoff and wall_value >= similarity_cutoff else None
        cliques = _maximum_complete_link_clusters(tuple(range(len(peers))), compatible_edges, 1.0) if len(peers) >= 2 else []
        # A formal peer reference exists only for one maximum complete-link
        # cluster.  Overlap is not a licence to select one maximum clique.
        unique_maximum_cluster = len(cliques) == 1 and len(cliques[0]) >= 2
        cluster = cliques[0] if unique_maximum_cluster else tuple()
        medoid_scores = []
        for peer_index in cluster:
            metrics = [peer_metrics[tuple(sorted((peer_index, other)))] for other in cluster if other != peer_index]
            boundary_values = [item["boundary_similarity"] for item in metrics]
            wall_values = [item["wallwall_similarity"] for item in metrics]
            geometry_sha = hashlib.sha256(json.dumps(peers[peer_index]["geometry"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            medoid_scores.append(((min(boundary_values), min(wall_values), float(np.mean(boundary_values)), float(np.mean(wall_values))), geometry_sha, peer_index))
        medoid_scores.sort(key=lambda item: tuple(-value for value in item[0]) + (item[1],))
        medoid_index = medoid_scores[0][2] if medoid_scores else None
        tied_count = sum(item[0] == medoid_scores[0][0] for item in medoid_scores) if medoid_scores else 0
        medoid = peers[medoid_index] if medoid_index is not None else {}
        tied_ious = []
        if held_out.get("valid") and medoid_scores:
            for _score, _sha, candidate_index in medoid_scores:
                value, _ = compute_layout_mask_iou_from_normalized_pairs(held_out["pairs"], peers[candidate_index]["geometry"]["pairs"], width=int(held_out["width"]), height=int(held_out["height"]))
                if _score == medoid_scores[0][0]:
                    tied_ious.append(value)
        q_loo = tied_ious[0] if tied_ious else None
        tied_range = max(tied_ious) - min(tied_ious) if tied_ious else None
        tie_unstable = tied_range is not None and tied_range > tie_iou_range_cutoff
        if tie_unstable:
            q_loo = None
        consensus_geometry = medoid.get("geometry", {})
        consensus_sha = hashlib.sha256(json.dumps(consensus_geometry, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if consensus_geometry else ""
        if not cliques:
            status = "insufficient_peer_support"
        elif not unique_maximum_cluster:
            status = "multiple_maximum_cliques_sensitivity"
        elif tie_unstable:
            status = "tied_medoid_sensitivity"
        elif q_loo is not None:
            status = "evaluable"
        else:
            status = "insufficient_peer_support"
        second = _complete_link_cluster(tuple(i for i in range(len(peers)) if i not in cluster), compatible_edges, 1.0) if cluster else tuple()
        excluded_status = "unimodal" if cluster and len(cluster) == len(peers) else "dominant_with_dissent" if unique_maximum_cluster and len(second) <= 1 else "supported_multimodal" if len(second) >= 2 else "insufficient_or_incompatible"
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
                # q_LOO_tu remains the compatibility alias; only the explicit
                # Primary LOO is emitted only through its explicit medoid field.
                "q_LOO_tu": q_loo,
                "q_LOO_primary": q_loo,
                "q_LOO_tie_min": min(tied_ious) if tied_ious else None,
                "q_LOO_tie_max": max(tied_ious) if tied_ious else None,
                "q_LOO_tie_mean": float(np.mean(tied_ious)) if tied_ious else None,
                "tie_sensitivity_only": tie_unstable or not unique_maximum_cluster,
                "loo_consensus_status": status,
                "loo_consensus_annotation_id": medoid.get("canonical_annotation_id") or medoid.get("annotation_id", ""),
                "loo_consensus_worker_id": medoid.get("worker_id", ""),
                "loo_consensus_geometry_sha256": consensus_sha,
                "loo_largest_cluster_support": len(cluster),
                "worker_excluded_largest_cluster_support": len(cluster),
                "worker_excluded_second_cluster_support": len(second),
                "worker_excluded_unique_dominant_cluster": unique_maximum_cluster,
                "worker_excluded_structure_status": excluded_status,
                "loo_maximum_cluster_count": len(cliques),
                "tied_medoid_count": tied_count,
                "held_out_tied_medoid_iou_min": min(tied_ious) if tied_ious else None,
                "held_out_tied_medoid_iou_max": max(tied_ious) if tied_ious else None,
                "held_out_tied_medoid_iou_range": tied_range,
                "interpretation_allowed": q_loo is not None and unique_maximum_cluster,
                "validity_status": "sensitivity_only" if tie_unstable or not unique_maximum_cluster else "valid" if q_loo is not None else "not_evaluable",
            }
        )
    return out
