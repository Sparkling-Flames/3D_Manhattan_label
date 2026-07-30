"""One complete-link partition and medoid contract shared by C1 and V1."""

from __future__ import annotations

import hashlib
import itertools
import json
import statistics
from typing import Any

from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.medoid import select_medoid


def _geometry(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("_geometry") or row.get("geometry") or {}


def _sha(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(_geometry(row), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _maximum_cliques(indices: tuple[int, ...], edges: set[tuple[int, int]], *, maximum_search_nodes: int = 10000) -> tuple[list[tuple[int, ...]], bool, int]:
    search_nodes = 0
    for size in range(len(indices), 0, -1):
        found = []
        for group in itertools.combinations(indices, size):
            search_nodes += 1
            if search_nodes > maximum_search_nodes:
                return [], True, search_nodes
            if all(tuple(sorted(pair)) in edges for pair in itertools.combinations(group, 2)):
                found.append(group)
        if found:
            return found, False, search_nodes
    return [], False, search_nodes


def _maximum_clique_partitions(indices: tuple[int, ...], edges: set[tuple[int, int]], *, maximum_partition_count: int = 256, maximum_search_nodes: int = 10000) -> tuple[list[tuple[tuple[int, ...], ...]], bool, int]:
    """Enumerate every partition induced by successive maximum-clique choices."""
    partitions: set[tuple[tuple[int, ...], ...]] = set()
    search_nodes = 0
    truncated = False
    def visit(remaining: tuple[int, ...], chosen: tuple[tuple[int, ...], ...]) -> None:
        nonlocal search_nodes, truncated
        search_nodes += 1
        if search_nodes > maximum_search_nodes or len(partitions) >= maximum_partition_count:
            truncated = True
            return
        if not remaining:
            partitions.add(tuple(sorted(chosen, key=lambda group: (-len(group), group))))
            return
        cliques, cap_hit, _ = _maximum_cliques(remaining, edges, maximum_search_nodes=maximum_search_nodes)
        if cap_hit:
            truncated = True
            return
        for clique in cliques:
            visit(tuple(index for index in remaining if index not in clique), (*chosen, tuple(sorted(clique))))
    visit(indices, tuple())
    return sorted(partitions), truncated, search_nodes


def cluster_geometry_records(records: list[dict[str, Any]], *, min_q_boundary: float, min_q_wallwall: float, base_task_id: str = "", condition: str = "", minimum_valid_k: int = 3, maximum_partition_count: int = 256, maximum_search_nodes: int = 10000) -> dict[str, Any]:
    valid = [row for row in records if _geometry(row).get("valid")]
    scores: dict[tuple[int, int], float] = {}
    edges: set[tuple[int, int]] = set()
    compatible = True
    for left, right in itertools.combinations(range(len(valid)), 2):
        item = pairwise_similarity(_geometry(valid[left]), _geometry(valid[right]))
        boundary = item.get("q_boundary", item.get("boundary_similarity"))
        wall = item.get("q_wallwall", item.get("wallwall_similarity"))
        if boundary is None or wall is None or not item.get("metric_compatible", True):
            compatible = False
            continue
        score = min(float(boundary), float(wall))
        scores[left, right] = score
        if float(boundary) >= min_q_boundary and float(wall) >= min_q_wallwall:
            edges.add((left, right))
    all_partitions, enumeration_truncated, partition_search_nodes = _maximum_clique_partitions(tuple(range(len(valid))), edges, maximum_partition_count=maximum_partition_count, maximum_search_nodes=maximum_search_nodes) if valid else ([], False, 0)
    partition_unique = compatible and not enumeration_truncated and len(all_partitions) == 1
    partition = list(all_partitions[0]) if partition_unique else []
    maxima, clique_truncated, clique_search_nodes = _maximum_cliques(tuple(range(len(valid))), edges, maximum_search_nodes=maximum_search_nodes) if valid else ([], False, 0)
    enumeration_truncated = enumeration_truncated or clique_truncated
    ambiguous_candidates = [list(group) for group in maxima] if len(all_partitions) > 1 else []
    partition.sort(key=lambda group: (-len(group), tuple(_sha(valid[index]) for index in group)))
    largest = partition[0] if partition_unique else tuple()
    second = partition[1] if partition_unique and len(partition) > 1 else tuple()

    def medoid(group: tuple[int, ...]) -> tuple[int | None, str]:
        return select_medoid(valid, group, scores, task_id=base_task_id)[:2]

    medoid_index, medoid_sha = medoid(largest)
    n1, n2, k = len(largest), len(second), len(valid)
    status = "not_evaluable"
    reason = "partition_enumeration_truncated" if enumeration_truncated else "non_unique_complete_link_partition" if len(all_partitions) > 1 else "minimum_valid_k_or_metric_compatibility"
    if partition_unique and k >= minimum_valid_k:
        status = "unimodal" if len(partition) == 1 else "dominant_with_dissent" if n2 <= 1 else "supported_multimodal"
        reason = "unique_complete_link_partition"
    selected = valid[medoid_index] if medoid_index is not None else {}
    memberships = [[str(valid[index].get("canonical_annotation_id") or valid[index].get("annotation_id") or "") for index in group] for group in partition]
    candidate_partitions = [
        [[str(valid[index].get("canonical_annotation_id") or valid[index].get("annotation_id") or "") for index in group] for group in candidate]
        for candidate in all_partitions
    ]
    result = {
        "schema_version": "geometry_cluster_v2", "base_task_id": base_task_id, "condition": condition,
        "valid_k": k, "partition_status": "unique" if partition_unique else "not_evaluable",
        "cluster_membership_json": json.dumps(memberships, sort_keys=True),
        "ambiguity_candidates_json": json.dumps(ambiguous_candidates, sort_keys=True),
        "candidate_partitions_json": json.dumps(candidate_partitions, sort_keys=True),
        "enumeration_truncated": enumeration_truncated, "maximum_partition_count": maximum_partition_count,
        "maximum_search_nodes": maximum_search_nodes, "clique_search_nodes": clique_search_nodes,
        "partition_search_nodes": partition_search_nodes,
        "cluster_count": len(partition) if partition_unique else "", "largest_cluster_support": n1,
        "second_cluster_support": n2, "largest_cluster_share": n1 / k if k else None,
        "second_cluster_share": n2 / k if k else None,
        "cluster_margin_all": (n1 - n2) / k if k and partition_unique else None,
        "cluster_margin_top2": (n1 - n2) / (n1 + n2) if n1 + n2 and partition_unique else None,
        "largest_cluster_worker_ids": ";".join(str(valid[index].get("worker_id", "")) for index in largest),
        "second_cluster_worker_ids": ";".join(str(valid[index].get("worker_id", "")) for index in second),
        "largest_cluster_medoid_annotation_id": str(selected.get("canonical_annotation_id") or selected.get("annotation_id") or ""),
        "largest_cluster_medoid_worker_id": str(selected.get("worker_id") or ""),
        "largest_cluster_medoid_geometry_sha256": medoid_sha,
        "largest_cluster_medoid_index": medoid_index,
        "task_crowd_structure_status": status, "structure_reason": reason,
    }
    return result
