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
    frozen = row.get("frozen_geometry_sha256") or _geometry(row).get("frozen_geometry_sha256")
    if frozen:
        return str(frozen)
    return hashlib.sha256(json.dumps(_geometry(row), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _connected_components(indices: tuple[int, ...], edges: set[tuple[int, int]]) -> list[tuple[int, ...]]:
    allowed = set(indices)
    remaining = set(indices)
    components = []
    while remaining:
        pending = [min(remaining)]
        component = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            remaining.discard(current)
            pending.extend(
                right if left == current else left
                for left, right in edges
                if current in (left, right)
                and (right if left == current else left) in allowed
                and (right if left == current else left) not in component
            )
        components.append(tuple(sorted(component)))
    return components


def _maximum_cliques(indices: tuple[int, ...], edges: set[tuple[int, int]], *, maximum_search_nodes: int = 10000) -> tuple[list[tuple[int, ...]], bool, int]:
    components = _connected_components(indices, edges)
    if len(components) > 1:
        maxima: list[tuple[int, ...]] = []
        maximum_size = search_nodes = 0
        for component in components:
            cliques, truncated, nodes = _maximum_cliques(
                component, edges, maximum_search_nodes=max(1, maximum_search_nodes - search_nodes),
            )
            search_nodes += nodes
            if truncated:
                return [], True, search_nodes
            component_size = len(cliques[0]) if cliques else 0
            if component_size > maximum_size:
                maxima, maximum_size = cliques, component_size
            elif component_size == maximum_size:
                maxima.extend(cliques)
        return sorted(maxima), False, search_nodes
    neighbors = {
        vertex: {
            other for other in indices
            if other != vertex and tuple(sorted((vertex, other))) in edges
        }
        for vertex in indices
    }
    maxima: list[tuple[int, ...]] = []
    maximum_size = search_nodes = 0
    truncated = False

    def visit(chosen: tuple[int, ...], candidates: set[int], excluded: set[int]) -> None:
        nonlocal maximum_size, search_nodes, truncated
        search_nodes += 1
        if search_nodes > maximum_search_nodes:
            truncated = True
            return
        if len(chosen) + len(candidates) < maximum_size:
            return
        if not candidates and not excluded:
            group = tuple(sorted(chosen))
            if len(group) > maximum_size:
                maxima.clear()
                maximum_size = len(group)
            if len(group) == maximum_size:
                maxima.append(group)
            return
        pivot_pool = candidates | excluded
        pivot = min(pivot_pool, key=lambda vertex: (-len(candidates & neighbors[vertex]), vertex)) if pivot_pool else None
        for vertex in sorted(candidates - (neighbors[pivot] if pivot is not None else set())):
            visit((*chosen, vertex), candidates & neighbors[vertex], excluded & neighbors[vertex])
            candidates.remove(vertex)
            excluded.add(vertex)
            if truncated:
                return

    visit(tuple(), set(indices), set())
    return ([] if truncated else sorted(set(maxima))), truncated, search_nodes


def _maximum_clique_partitions(indices: tuple[int, ...], edges: set[tuple[int, int]], *, maximum_partition_count: int = 256, maximum_search_nodes: int = 10000) -> tuple[list[tuple[tuple[int, ...], ...]], bool, int]:
    """Enumerate every partition induced by successive maximum-clique choices."""
    components = _connected_components(indices, edges)
    if len(components) > 1:
        choices = []
        search_nodes = 0
        for component in components:
            partitions, truncated, nodes = _maximum_clique_partitions(
                component, edges,
                maximum_partition_count=maximum_partition_count,
                maximum_search_nodes=max(1, maximum_search_nodes - search_nodes),
            )
            search_nodes += nodes
            if truncated:
                return [], True, search_nodes
            choices.append(partitions)
        combined = {
            tuple(sorted((group for partition in selection for group in partition), key=lambda group: (-len(group), group)))
            for selection in itertools.product(*choices)
        }
        truncated = len(combined) > maximum_partition_count
        return sorted(combined)[:maximum_partition_count], truncated, search_nodes
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


def cluster_geometry_records(records: list[dict[str, Any]], *, min_q_boundary: float, min_q_wallwall: float, base_task_id: str = "", condition: str = "", minimum_valid_k: int = 3, maximum_partition_count: int = 256, maximum_search_nodes: int = 10000, pairwise_fn=None) -> dict[str, Any]:
    valid = [row for row in records if _geometry(row).get("valid")]
    scores: dict[tuple[int, int], float] = {}
    edges: set[tuple[int, int]] = set()
    compatible = True
    for left, right in itertools.combinations(range(len(valid)), 2):
        item = (pairwise_fn or pairwise_similarity)(_geometry(valid[left]), _geometry(valid[right]))
        boundary = item.get("q_boundary", item.get("boundary_similarity"))
        wall = item.get("q_wallwall", item.get("wallwall_similarity"))
        if boundary is None or wall is None or not item.get("metric_compatible", True):
            compatible = False
            continue
        score = min(float(boundary), float(wall))
        scores[left, right] = score
        if item.get("pointwise_correspondence_compatible") is True and float(boundary) >= min_q_boundary and float(wall) >= min_q_wallwall:
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
    second_medoid_index, second_medoid_sha = medoid(second)
    n1, n2, k = len(largest), len(second), len(valid)
    status = "not_evaluable"
    reason = "partition_enumeration_truncated" if enumeration_truncated else "non_unique_complete_link_partition" if len(all_partitions) > 1 else "minimum_valid_k_or_metric_compatibility"
    if partition_unique and k >= minimum_valid_k:
        if len(partition) == 1:
            status, reason = "unimodal", "unique_complete_link_partition"
        elif n1 > n2 and n2 <= 1:
            status, reason = "dominant_with_dissent", "unique_complete_link_partition"
        elif n2 >= 2:
            status, reason = "supported_multimodal", "unique_complete_link_partition"
        else:
            reason = "no_dominant_or_supported_partition"
    selected = valid[medoid_index] if medoid_index is not None else {}
    selected_second = valid[second_medoid_index] if second_medoid_index is not None else {}
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
        "second_cluster_medoid_annotation_id": str(selected_second.get("canonical_annotation_id") or selected_second.get("annotation_id") or ""),
        "second_cluster_medoid_worker_id": str(selected_second.get("worker_id") or ""),
        "second_cluster_medoid_geometry_sha256": second_medoid_sha,
        "second_cluster_medoid_index": second_medoid_index,
        "task_crowd_structure_status": status, "structure_reason": reason,
    }
    return result
