"""Shared deterministic medoid selection for the Paper A geometry DAG."""

from __future__ import annotations

import hashlib
import json
import statistics
from typing import Any


def geometry_sha256(row: dict[str, Any]) -> str:
    geometry = row.get("_geometry") or row.get("geometry") or {}
    return hashlib.sha256(json.dumps(geometry, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def frozen_geometry_tie_key(row: dict[str, Any], *, task_id: str, geometry_sha: str | None = None) -> tuple[str, str, str]:
    """Return the contractual GT-blind final tie key."""
    sha = geometry_sha or geometry_sha256(row)
    annotation_id = str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")
    if not annotation_id:
        raise ValueError("geometry medoid requires a canonical annotation identity")
    seed = hashlib.sha256(f"{task_id}|{sha}|{annotation_id}".encode()).hexdigest()
    return sha, annotation_id, seed


def select_medoid(
    records: list[dict[str, Any]], indices: tuple[int, ...], pair_scores: dict[tuple[int, int], float], *, task_id: str,
) -> tuple[int | None, str, list[tuple[float, float, str, str, str, int]]]:
    """Select max median then mean similarity, then the frozen identity key."""
    ranked: list[tuple[float, float, str, str, str, int]] = []
    for index in indices:
        similarities = [float(pair_scores[tuple(sorted((index, other)))]) for other in indices if other != index and tuple(sorted((index, other))) in pair_scores]
        median = float(statistics.median(similarities)) if similarities else 1.0
        mean = float(statistics.mean(similarities)) if similarities else 1.0
        sha, annotation_id, seed = frozen_geometry_tie_key(records[index], task_id=task_id)
        ranked.append((median, mean, sha, annotation_id, seed, index))
    ranked.sort(key=lambda item: (-item[0], -item[1], item[2], item[3], item[4]))
    return (ranked[0][5], ranked[0][2], ranked) if ranked else (None, "", ranked)
