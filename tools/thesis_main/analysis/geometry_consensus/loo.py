from __future__ import annotations

from typing import Any

import hashlib
import json
import numpy as np
import statistics

from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou_from_normalized_pairs
from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records

from .pairwise import pairwise_similarity


def leave_one_out(
    records: list[dict[str, Any]], *, grid: int = 256,
    similarity_cutoff: float = 0.8, tie_iou_range_cutoff: float = 0.02,
    maximum_partition_count: int = 256, maximum_search_nodes: int = 10000,
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
        shared_cluster = cluster_geometry_records(
            peers,
            min_q_boundary=similarity_cutoff,
            min_q_wallwall=similarity_cutoff,
            base_task_id=str(record.get("base_task_id") or record.get("task_id") or ""),
            minimum_valid_k=2,
            maximum_partition_count=maximum_partition_count,
            maximum_search_nodes=maximum_search_nodes,
        )
        unique_maximum_cluster = (
            shared_cluster["partition_status"] == "unique"
            and int(shared_cluster["largest_cluster_support"]) >= 2
        )
        medoid_index = shared_cluster["largest_cluster_medoid_index"] if unique_maximum_cluster else None
        tied_count = 1 if medoid_index is not None else 0
        medoid = peers[medoid_index] if medoid_index is not None else {}
        tied_ious = []
        if held_out.get("valid") and medoid_index is not None:
            value, _ = compute_layout_mask_iou_from_normalized_pairs(held_out["pairs"], peers[medoid_index]["geometry"]["pairs"], width=int(held_out["width"]), height=int(held_out["height"]))
            tied_ious.append(value)
        q_loo = tied_ious[0] if tied_ious else None
        tied_range = max(tied_ious) - min(tied_ious) if tied_ious else None
        tie_unstable = False
        consensus_geometry = medoid.get("geometry", {})
        consensus_sha = hashlib.sha256(json.dumps(consensus_geometry, sort_keys=True, separators=(",", ":")).encode()).hexdigest() if consensus_geometry else ""
        if len(peers) < 2 or (
            shared_cluster["partition_status"] == "unique"
            and int(shared_cluster["largest_cluster_support"]) < 2
        ):
            status = "insufficient_peer_support"
        elif not unique_maximum_cluster:
            status = "multiple_maximum_cliques_sensitivity"
        elif tie_unstable:
            status = "tied_medoid_sensitivity"
        elif q_loo is not None:
            status = "evaluable"
        else:
            status = "insufficient_peer_support"
        largest_support = int(shared_cluster["largest_cluster_support"])
        second_support = int(shared_cluster["second_cluster_support"])
        excluded_status = shared_cluster["task_crowd_structure_status"] if unique_maximum_cluster else "insufficient_or_incompatible"
        candidate_partition_count = len(json.loads(shared_cluster["candidate_partitions_json"]))
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
                "loo_largest_cluster_support": largest_support,
                "worker_excluded_largest_cluster_support": largest_support,
                "worker_excluded_second_cluster_support": second_support,
                "worker_excluded_unique_dominant_cluster": unique_maximum_cluster,
                "worker_excluded_structure_status": excluded_status,
                "loo_maximum_cluster_count": candidate_partition_count,
                "tied_medoid_count": tied_count,
                "held_out_tied_medoid_iou_min": min(tied_ious) if tied_ious else None,
                "held_out_tied_medoid_iou_max": max(tied_ious) if tied_ious else None,
                "held_out_tied_medoid_iou_range": tied_range,
                "interpretation_allowed": q_loo is not None and unique_maximum_cluster,
                "validity_status": "sensitivity_only" if tie_unstable or not unique_maximum_cluster else "valid" if q_loo is not None else "not_evaluable",
            }
        )
    return out
