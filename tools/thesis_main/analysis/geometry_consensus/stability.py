from __future__ import annotations

from typing import Any

import itertools
import hashlib
import json
import numpy as np

from .pairwise import pairwise_similarity
from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou_from_normalized_pairs


def _mode_summary(values: list[float], *, gap_cutoff: float = 0.15) -> tuple[int, float | None]:
    if len(values) < 4:
        return 1, None
    ordered = sorted(values)
    gaps = [ordered[index + 1] - ordered[index] for index in range(len(ordered) - 1)]
    largest = max(gaps)
    pivot = gaps.index(largest) + 1
    return (2 if largest >= gap_cutoff and pivot >= 2 and len(ordered) - pivot >= 2 else 1), largest


def _core_stability(records: list[dict[str, Any]], *, grid: int = 256, gap_cutoff: float = 0.15) -> dict[str, Any]:
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    pairwise = [
        (i, j, pairwise_similarity(valid[i]["geometry"], valid[j]["geometry"], grid=grid))
        for i in range(len(valid))
        for j in range(i + 1, len(valid))
    ]
    boundary = [value["boundary_similarity"] for _, _, value in pairwise if value.get("boundary_similarity") is not None]
    wallwall = [value["wallwall_similarity"] for _, _, value in pairwise if value.get("wallwall_similarity") is not None]
    boundary_mode_count = wallwall_mode_count = 0
    boundary_largest_gap = wallwall_largest_gap = None
    boundary_margin = wallwall_margin = None
    if not boundary or not wallwall:
        status = "not_evaluable"
        boundary_medoid = wallwall_medoid = ""
        boundary_ambiguous = wallwall_ambiguous = False
        score_table = []
    else:
        def scores(index: int, channel: str) -> float:
            values = [item[channel] for left, right, item in pairwise if index in {left, right} and item.get(channel) is not None]
            return float(np.mean(values)) if values else float("-inf")
        boundary_scores = sorted([(scores(index, "boundary_similarity"), record.get("worker_id", "")) for index, record in enumerate(valid)], reverse=True)
        wallwall_scores = sorted([(scores(index, "wallwall_similarity"), record.get("worker_id", "")) for index, record in enumerate(valid)], reverse=True)
        boundary_ambiguous = len(boundary_scores) > 1 and abs(boundary_scores[0][0] - boundary_scores[1][0]) <= 1e-12
        wallwall_ambiguous = len(wallwall_scores) > 1 and abs(wallwall_scores[0][0] - wallwall_scores[1][0]) <= 1e-12
        boundary_medoid = "" if boundary_ambiguous else boundary_scores[0][1]
        wallwall_medoid = "" if wallwall_ambiguous else wallwall_scores[0][1]
        score_table = [{"worker_id": record.get("worker_id", ""), "boundary_score": scores(index, "boundary_similarity"), "wallwall_score": scores(index, "wallwall_similarity")} for index, record in enumerate(valid)]
        boundary_mode_count, boundary_largest_gap = _mode_summary(boundary, gap_cutoff=gap_cutoff)
        wallwall_mode_count, wallwall_largest_gap = _mode_summary(wallwall, gap_cutoff=gap_cutoff)
        status = "multimodal_candidate" if boundary_mode_count > 1 or wallwall_mode_count > 1 else "stable_candidate"
        boundary_margin = boundary_scores[0][0] - boundary_scores[1][0] if len(boundary_scores) > 1 else None
        wallwall_margin = wallwall_scores[0][0] - wallwall_scores[1][0] if len(wallwall_scores) > 1 else None
    return {
        "valid_k": len(valid),
        "boundary_similarity_mean": float(np.mean(boundary)) if boundary else None,
        "boundary_similarity_min": min(boundary) if boundary else None,
        "wallwall_similarity_mean": float(np.mean(wallwall)) if wallwall else None,
        "wallwall_similarity_min": min(wallwall) if wallwall else None,
        "q_boundary_mean": float(np.mean(boundary)) if boundary else None,
        "q_boundary_min": min(boundary) if boundary else None,
        "q_wallwall_mean": float(np.mean(wallwall)) if wallwall else None,
        "q_wallwall_min": min(wallwall) if wallwall else None,
        "boundary_mode_count": boundary_mode_count if boundary else 0, "wallwall_mode_count": wallwall_mode_count if wallwall else 0,
        "boundary_largest_gap": boundary_largest_gap if boundary else None, "wallwall_largest_gap": wallwall_largest_gap if wallwall else None,
        "medoid_margin_boundary": boundary_margin if boundary else None, "medoid_margin_wallwall": wallwall_margin if wallwall else None,
        "medoid_boundary_worker_id": boundary_medoid, "medoid_wallwall_worker_id": wallwall_medoid,
        "medoid_ambiguous": boundary_ambiguous or wallwall_ambiguous, "medoid_boundary_ambiguous": boundary_ambiguous, "medoid_wallwall_ambiguous": wallwall_ambiguous,
        "medoid_score_table_json": __import__("json").dumps(score_table, sort_keys=True),
        "medoid_worker_id": boundary_medoid if boundary_medoid == wallwall_medoid else "", "stability_status": status, "interpretation_allowed": False,
    }


def _maximum_complete_link_clusters(indices: tuple[int, ...], similarities: dict[tuple[int, int], float | None], cutoff: float) -> list[tuple[int, ...]]:
    """Enumerate all maximum cliques; C1 peer groups are deliberately small."""
    def compatible(left: int, right: int) -> bool:
        value = similarities.get(tuple(sorted((left, right))))
        return value is not None and value >= cutoff
    for size in range(len(indices), 0, -1):
        cliques = [group for group in itertools.combinations(indices, size) if all(compatible(left, right) for left, right in itertools.combinations(group, 2))]
        if cliques:
            return cliques
    return []


def _complete_link_cluster(indices: tuple[int, ...], similarities: dict[tuple[int, int], float | None], cutoff: float) -> tuple[int, ...]:
    clusters = _maximum_complete_link_clusters(indices, similarities, cutoff)
    return clusters[0] if clusters else tuple()


def stability_summary(records: list[dict[str, Any]], *, grid: int = 256, multimodal_cutoff: float = 0.8, _resample: bool = True) -> dict[str, Any]:
    valid = [record for record in records if (record.get("geometry") or {}).get("valid")]
    gap_cutoff = 1 - multimodal_cutoff
    result = _core_stability(valid, grid=grid, gap_cutoff=gap_cutoff)
    similarities: dict[tuple[int, int], float | None] = {}
    channel_metrics: dict[tuple[int, int], dict[str, Any]] = {}
    for left, right in itertools.combinations(range(len(valid)), 2):
        metrics = pairwise_similarity(valid[left]["geometry"], valid[right]["geometry"], grid=grid)
        channel_metrics[(left, right)] = metrics
        boundary_value, wall_value = metrics.get("boundary_similarity"), metrics.get("wallwall_similarity")
        similarities[(left, right)] = (
            1.0 if boundary_value >= multimodal_cutoff and wall_value >= multimodal_cutoff else 0.0
        ) if boundary_value is not None and wall_value is not None else None

    compatible = bool(similarities) and all(value is not None for value in similarities.values())
    largest_candidates = _maximum_complete_link_clusters(tuple(range(len(valid))), similarities, multimodal_cutoff) if compatible else []
    largest = largest_candidates[0] if largest_candidates else tuple()
    remainder = tuple(index for index in range(len(valid)) if index not in largest)
    second_support = len(_complete_link_cluster(remainder, similarities, multimodal_cutoff)) if len(remainder) >= 2 else 0
    disjoint_maxima = any(set(left).isdisjoint(right) for left, right in itertools.combinations(largest_candidates, 2))
    multimodal = disjoint_maxima or second_support >= 2
    all_values = [value for value in similarities.values() if value is not None]
    result["consensus_status"] = "insufficient" if len(valid) < 3 else "metric_incompatible" if not compatible else "multimodal" if multimodal else "stable" if len(largest) == len(valid) else "weak"
    result["peer_support"] = len(valid)
    result["largest_cluster_support"] = len(largest)
    result["second_mode_support"] = second_support
    medoid_index = None
    medoid_scores = []
    for index in largest:
        peers = [channel_metrics[tuple(sorted((index, other)))] for other in largest if other != index]
        boundary_values = [item["boundary_similarity"] for item in peers]
        wall_values = [item["wallwall_similarity"] for item in peers]
        score = (min(boundary_values, default=1.0), min(wall_values, default=1.0), float(np.mean(boundary_values)) if boundary_values else 1.0, float(np.mean(wall_values)) if wall_values else 1.0)
        geometry_sha = hashlib.sha256(json.dumps(valid[index].get("geometry", {}), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        medoid_scores.append((score, geometry_sha, index))
    medoid_scores.sort(key=lambda item: tuple(-value for value in item[0]) + (item[1],))
    if medoid_scores:
        medoid_index = medoid_scores[0][2]
    medoid = valid[medoid_index] if medoid_index is not None else {}
    result["medoid_annotation_id"] = medoid.get("canonical_annotation_id") or medoid.get("annotation_id", "")
    result["medoid_geometry_sha256"] = hashlib.sha256(json.dumps(medoid.get("geometry", {}), sort_keys=True, separators=(",", ":")).encode()).hexdigest() if medoid else ""
    result["medoid_worker_id"] = medoid.get("worker_id", "")
    result["medoid_margin"] = medoid_scores[0][0][0] - medoid_scores[1][0][0] if len(medoid_scores) > 1 else None
    result["primary_eligible"] = result["consensus_status"] == "stable"
    result["sensitivity_eligible"] = result["consensus_status"] in {"stable", "weak"}
    def subset_signature(indices: tuple[int, ...]) -> tuple[str, str, int, float | None, float | None]:
        sub_pairs = {key: value for key, value in similarities.items() if key[0] in indices and key[1] in indices}
        sub_compatible = bool(sub_pairs) and all(value is not None for value in sub_pairs.values())
        sub_largest = _complete_link_cluster(indices, sub_pairs, multimodal_cutoff) if sub_compatible else tuple()
        sub_remainder = tuple(index for index in indices if index not in sub_largest)
        sub_second = len(_complete_link_cluster(sub_remainder, sub_pairs, multimodal_cutoff)) if len(sub_remainder) >= 2 else 0
        sub_status = "insufficient" if len(indices) < 3 else "metric_incompatible" if not sub_compatible else "multimodal" if sub_second >= 2 else "stable" if len(sub_largest) == len(indices) else "weak"
        scores = []
        for index in sub_largest:
            peers = [channel_metrics[tuple(sorted((index, other)))] for other in sub_largest if other != index]
            boundary_values = [item["boundary_similarity"] for item in peers]
            wall_values = [item["wallwall_similarity"] for item in peers]
            score = (min(boundary_values, default=1.0), min(wall_values, default=1.0), float(np.mean(boundary_values)) if boundary_values else 1.0, float(np.mean(wall_values)) if wall_values else 1.0)
            geometry_sha = hashlib.sha256(json.dumps(valid[index].get("geometry", {}), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            scores.append((score, geometry_sha, index))
        scores.sort(key=lambda item: tuple(-value for value in item[0]) + (item[1],))
        medoid_index = scores[0][2] if scores else None
        medoid_id = (valid[medoid_index].get("canonical_annotation_id") or valid[medoid_index].get("annotation_id", "")) if medoid_index is not None else ""
        margin = scores[0][0][0] - scores[1][0][0] if len(scores) > 1 else None
        geometry_iou = None
        if medoid_index is not None and medoid:
            try:
                geometry_iou, _ = compute_layout_mask_iou_from_normalized_pairs(
                    medoid["geometry"]["pairs"], valid[medoid_index]["geometry"]["pairs"],
                    width=int(medoid["geometry"]["width"]), height=int(medoid["geometry"]["height"]),
                )
            except (KeyError, TypeError, ValueError):
                geometry_iou = None
        return sub_status, medoid_id, len(sub_largest), margin, geometry_iou

    baseline_status = result["consensus_status"]
    baseline_support = result["largest_cluster_support"]
    loo = [subset_signature(tuple(j for j in range(len(valid)) if j != index)) for index in range(len(valid))] if _resample and len(valid) >= 4 else []
    lto = [subset_signature(tuple(j for j in range(len(valid)) if j not in removed)) for removed in itertools.combinations(range(len(valid)), 2)] if _resample and len(valid) >= 5 else []
    # A removed medoid may be replaced by another member of the same mode.  The
    # robustness contract is status, expected support loss and consensus geometry,
    # never literal annotation-id persistence.
    def robust(items: list[tuple[str, str, int, float | None, float | None]], removed: int) -> bool:
        return all(
            item[0] == baseline_status
            and item[2] >= max(0, baseline_support - removed)
            and item[4] is not None and item[4] >= multimodal_cutoff
            for item in items
        )
    result["leave_one_out_stability"] = "not_evaluable" if not loo else "robust" if robust(loo, 1) else "sensitive"
    result["leave_two_out_stability"] = "not_evaluable" if not lto else "robust" if robust(lto, 2) else "sensitive"
    result["leave_two_out_status"] = result["leave_two_out_stability"]
    result["metric_compatibility"] = "compatible" if compatible else "incompatible"
    return result
