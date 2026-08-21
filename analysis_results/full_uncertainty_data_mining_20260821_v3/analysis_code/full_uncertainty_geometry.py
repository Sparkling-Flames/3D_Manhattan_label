"""Geometry, meta-label, crowd/GT and worker-viewpoint uncertainty analyses."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from tools.thesis_main.analysis.full_uncertainty_common import (
    C1,
    PERSISTENT,
    V2,
    bernoulli_entropy,
    choice_group,
    clean,
    cyclic_rmse,
    extract_choice_records,
    gini_simpson,
    integer,
    number,
    pairwise_jaccard,
    parse_jsonish,
    read_csv,
    shannon_entropy,
    truth,
    worker_id,
)


def _geometry_list(value: Any) -> list[list[float]]:
    payload = parse_jsonish(value)
    if isinstance(payload, list):
        result: list[list[float]] = []
        for item in payload:
            if not isinstance(item, (list, tuple)) or len(item) < 2:
                return []
            left, right = number(item[0]), number(item[1])
            if left is None or right is None:
                return []
            result.append([float(left), float(right)])
        return result
    return []


def cross_stage_geometry_uncertainty(unified: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Describe topology and same-topology coordinate dispersion at every stage.

    One worker contributes at most one selected record per task/condition.  Raw
    revisions remain in the unified evidence table but are not treated as
    independent annotators in this task-level lane.
    """
    if unified.empty:
        return pd.DataFrame(), pd.DataFrame()
    frame = unified.copy()
    frame["geometry_computable"] = frame["geometry_computable"].map(truth)
    frame["selected_preference"] = frame["record_role"].map(
        {"stage_canonical": 0, "c1_auditable_noncanonical_or_raw_only": 1}
    ).fillna(2)
    frame = frame.sort_values(
        ["stage", "condition", "base_task_id", "worker_id", "selected_preference", "geometry_computable"],
        ascending=[True, True, True, True, True, False],
    )
    revision_counts = frame.groupby(["stage", "condition", "base_task_id", "worker_id"], dropna=False).size().rename("available_record_count")
    selected = frame.drop_duplicates(["stage", "condition", "base_task_id", "worker_id"], keep="first").copy()
    selected = selected.merge(revision_counts.reset_index(), how="left", on=["stage", "condition", "base_task_id", "worker_id"])

    rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    for (stage, condition, task), group in selected.groupby(["stage", "condition", "base_task_id"], dropna=False):
        group = group.copy()
        usable = group[group["geometry_computable"]].copy()
        topology_counts = Counter(
            int(value) for value in pd.to_numeric(usable["n_corners"], errors="coerce").dropna().astype(int) if value >= 4 and value % 2 == 0
        )
        total_pairs = 0
        different_topology_pairs = 0
        same_rmse: list[float] = []
        usable_records = list(usable.itertuples(index=False))
        for left, right in combinations(usable_records, 2):
            total_pairs += 1
            left_n, right_n = int(left.n_corners), int(right.n_corners)
            same_topology = left_n == right_n
            if not same_topology:
                different_topology_pairs += 1
                distance = None
            else:
                distance = cyclic_rmse(_geometry_list(left.geometry_points_json), _geometry_list(right.geometry_points_json))
                if distance is not None:
                    same_rmse.append(distance)
            pair_rows.append({
                "stage": stage,
                "condition": condition,
                "base_task_id": task,
                "building_id": clean(left.building_id) or clean(right.building_id),
                "worker_id_left": left.worker_id,
                "worker_id_right": right.worker_id,
                "n_corners_left": left_n,
                "n_corners_right": right_n,
                "same_topology": same_topology,
                "cyclic_rmse_diagonal_normalized": distance,
                "measurement_note": "descriptive_cyclic_rmse_not_c1_frozen_similarity",
            })
        support = sum(topology_counts.values())
        counts = sorted(topology_counts.values(), reverse=True)
        largest_share = counts[0] / support if counts and support else np.nan
        rows.append({
            "stage": stage,
            "condition": condition,
            "base_task_id": task,
            "building_id": clean(group["building_id"].iloc[0]),
            "observed_worker_count": int(group["worker_id"].nunique()),
            "available_record_count": int(group["available_record_count"].sum()),
            "geometry_computable_worker_count": int(len(usable)),
            "geometry_missing_worker_count": int(len(group) - len(usable)),
            "topology_counts_json": json.dumps({str(key): value for key, value in sorted(topology_counts.items())}, sort_keys=True),
            "topology_mode_count": int(len(topology_counts)),
            "topology_shannon_entropy": shannon_entropy(topology_counts.values()) if topology_counts else np.nan,
            "topology_gini_simpson": gini_simpson(topology_counts.values()) if topology_counts else np.nan,
            "largest_topology_share": largest_share,
            "different_topology_pair_share": different_topology_pairs / total_pairs if total_pairs else np.nan,
            "same_topology_pair_count": len(same_rmse),
            "same_topology_cyclic_rmse_median": float(np.median(same_rmse)) if same_rmse else np.nan,
            "same_topology_cyclic_rmse_q25": float(np.quantile(same_rmse, 0.25)) if same_rmse else np.nan,
            "same_topology_cyclic_rmse_q75": float(np.quantile(same_rmse, 0.75)) if same_rmse else np.nan,
            "geometry_uncertainty_class": (
                "not_evaluable_lt2_geometry" if len(usable) < 2 else
                "multiple_topologies" if len(topology_counts) > 1 else
                "single_topology_continuous_dispersion"
            ),
            "measurement_lane": "cross_stage_topology_and_cyclic_rmse_descriptive",
        })
    return pd.DataFrame(rows), pd.DataFrame(pair_rows)


def meta_label_uncertainty(raw_annotations: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if raw_annotations.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    long_rows: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    for row in raw_annotations.itertuples(index=False):
        response_id = "|".join([
            clean(getattr(row, "stage", "")), clean(getattr(row, "project_id", "")),
            clean(getattr(row, "ls_runtime_task_id", "")), clean(getattr(row, "worker_id", "")),
            clean(getattr(row, "annotation_id", "")),
        ])
        choices = extract_choice_records(getattr(row, "result_json", ""))
        grouped: dict[str, set[str]] = defaultdict(set)
        for item in choices:
            group, code, label_zh = choice_group(item["from_name"], item["choice_raw"])
            grouped[group].add(code)
            long_rows.append({
                "stage": getattr(row, "stage", ""),
                "condition": getattr(row, "condition", ""),
                "project_id": getattr(row, "project_id", ""),
                "runtime_task_id": getattr(row, "ls_runtime_task_id", ""),
                "base_task_id": getattr(row, "base_task_id", ""),
                "worker_id": getattr(row, "worker_id", ""),
                "annotation_id": getattr(row, "annotation_id", ""),
                "canonical_annotation_id": getattr(row, "canonical_annotation_id", ""),
                "canonical_join_status": getattr(row, "canonical_join_status", ""),
                "response_id": response_id,
                "meta_group": group,
                "choice_code": code,
                "choice_label_zh": label_zh,
                "choice_raw": item["choice_raw"],
                "from_name": item["from_name"],
                "result_type": item["result_type"],
                "image_reference": getattr(row, "image_reference", ""),
            })
        for group, labels in grouped.items():
            response_rows.append({
                "stage": getattr(row, "stage", ""),
                "condition": getattr(row, "condition", ""),
                "base_task_id": getattr(row, "base_task_id", ""),
                "worker_id": getattr(row, "worker_id", ""),
                "response_id": response_id,
                "meta_group": group,
                "label_set_json": json.dumps(sorted(labels), ensure_ascii=False),
                "label_cardinality": len(labels),
                "canonical_join_status": getattr(row, "canonical_join_status", ""),
                "image_reference": getattr(row, "image_reference", ""),
            })
    long = pd.DataFrame(long_rows)
    responses = pd.DataFrame(response_rows)
    if responses.empty:
        return long, responses, pd.DataFrame()

    task_rows: list[dict[str, Any]] = []
    for (stage, condition, task, meta_group), group in responses.groupby(["stage", "condition", "base_task_id", "meta_group"], dropna=False):
        label_sets = [set(parse_jsonish(value) or []) for value in group["label_set_json"]]
        mean_jaccard, median_jaccard, pair_count = pairwise_jaccard(label_sets)
        union = sorted(set().union(*label_sets)) if label_sets else []
        prevalence = {label: sum(label in values for values in label_sets) / len(label_sets) for label in union}
        entropies = [bernoulli_entropy(value) for value in prevalence.values()]
        task_rows.append({
            "stage": stage,
            "condition": condition,
            "base_task_id": task,
            "meta_group": meta_group,
            "response_count": len(group),
            "worker_count": int(group["worker_id"].nunique()),
            "pair_count": pair_count,
            "pairwise_jaccard_mean": mean_jaccard,
            "pairwise_jaccard_median": median_jaccard,
            "mean_label_entropy": float(np.mean(entropies)) if entropies else np.nan,
            "maximum_label_entropy": float(np.max(entropies)) if entropies else np.nan,
            "mean_label_cardinality": float(group["label_cardinality"].mean()),
            "sd_label_cardinality": float(group["label_cardinality"].std(ddof=1)) if len(group) > 1 else 0.0,
            "label_union_count": len(union),
            "label_prevalence_json": json.dumps(prevalence, ensure_ascii=False, sort_keys=True),
            "raw_or_canonical_mix": ";".join(sorted(set(map(clean, group["canonical_join_status"])) - {""})),
            "measurement_note": "all_observed_response_versions_descriptive_not_independent_if_same_worker_revised",
        })
    return long, responses, pd.DataFrame(task_rows)


def c1_crowd_gt_conflict() -> tuple[pd.DataFrame, pd.DataFrame]:
    crowd = read_csv(C1 / "geometry_task_crowd_structure_C1.csv")
    evidence = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    if crowd.empty or evidence.empty:
        return pd.DataFrame(), pd.DataFrame()
    lookup: dict[str, dict[str, Any]] = {}
    for row in evidence.to_dict("records"):
        for key in (clean(row.get("canonical_annotation_id")), clean(row.get("annotation_id"))):
            if key and key not in lookup:
                lookup[key] = row
    task_rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    for row in crowd.to_dict("records"):
        task = clean(row.get("base_task_id"))
        condition = clean(row.get("condition"))
        partition = clean(row.get("partition_status"))
        memberships = parse_jsonish(row.get("cluster_membership_json")) or []
        if partition != "unique" or not isinstance(memberships, list) or not memberships:
            task_rows.append({
                "base_task_id": task, "building_id": clean(row.get("building_id")), "condition": condition,
                "partition_status": partition or "not_evaluable", "task_crowd_structure_status": clean(row.get("task_crowd_structure_status")),
                "cluster_count": integer(row.get("cluster_count")), "largest_cluster_support": integer(row.get("largest_cluster_support")),
                "largest_cluster_median_iou": np.nan, "best_cluster_median_iou": np.nan, "crowd_gt_gap_best_minus_largest": np.nan,
                "crowd_gt_relationship": "partition_not_unique_or_not_evaluable", "task_final_scope": "", "geometry_reference_status": "",
            })
            continue
        cluster_stats: list[dict[str, Any]] = []
        for rank, members in enumerate(memberships, 1):
            identities = [clean(value) for value in members]
            records = [lookup[identity] for identity in identities if identity in lookup]
            ious = [number(record.get("iou_to_gt")) for record in records]
            ious = [value for value in ious if value is not None]
            workers = [worker_id(record.get("worker_id")) for record in records]
            stat = {
                "base_task_id": task,
                "building_id": clean(row.get("building_id")),
                "condition": condition,
                "cluster_rank": rank,
                "cluster_support": len(identities),
                "quality_computable_count": len(ious),
                "cluster_iou_mean": float(np.mean(ious)) if ious else np.nan,
                "cluster_iou_median": float(np.median(ious)) if ious else np.nan,
                "cluster_iou_min": float(np.min(ious)) if ious else np.nan,
                "cluster_iou_max": float(np.max(ious)) if ious else np.nan,
                "worker_ids": ";".join(workers),
                "annotation_ids": ";".join(identities),
            }
            cluster_stats.append(stat)
            cluster_rows.append(stat)
        medians = [stat["cluster_iou_median"] for stat in cluster_stats]
        finite = [(index, value) for index, value in enumerate(medians) if pd.notna(value)]
        largest = medians[0] if medians else np.nan
        if finite:
            best_index, best_value = max(finite, key=lambda pair: pair[1])
            high_count = sum(value >= 0.90 for _, value in finite)
            if len(cluster_stats) == 1:
                relationship = "unimodal_high_gt_alignment" if best_value >= 0.90 else "unimodal_low_gt_alignment" if best_value < 0.80 else "unimodal_intermediate_gt_alignment"
            elif high_count >= 2:
                relationship = "multimodal_multiple_gt_aligned_clusters"
            elif best_index > 0 and pd.notna(largest) and best_value - largest >= 0.05:
                relationship = "multimodal_minority_cluster_better_gt_alignment"
            elif best_index == 0:
                relationship = "multimodal_largest_cluster_best_gt_alignment"
            else:
                relationship = "multimodal_no_clear_gt_alignment_order"
        else:
            best_index, best_value, relationship = -1, np.nan, "gt_not_computable_for_cluster_members"
        first_evidence = next((lookup[clean(identity)] for cluster in memberships for identity in cluster if clean(identity) in lookup), {})
        task_rows.append({
            "base_task_id": task,
            "building_id": clean(row.get("building_id")),
            "condition": condition,
            "partition_status": partition,
            "task_crowd_structure_status": clean(row.get("task_crowd_structure_status")),
            "cluster_count": len(cluster_stats),
            "largest_cluster_support": len(memberships[0]) if memberships else 0,
            "second_cluster_support": len(memberships[1]) if len(memberships) > 1 else 0,
            "largest_cluster_median_iou": largest,
            "best_cluster_rank": best_index + 1 if best_index >= 0 else np.nan,
            "best_cluster_median_iou": best_value,
            "crowd_gt_gap_best_minus_largest": best_value - largest if pd.notna(best_value) and pd.notna(largest) else np.nan,
            "crowd_gt_relationship": relationship,
            "task_final_scope": clean(first_evidence.get("task_final_scope")),
            "geometry_reference_status": clean(first_evidence.get("geometry_reference_status")),
            "display_thresholds": "high_alignment>=0.90;low_alignment<0.80;cluster_gap>=0.05;descriptive_only",
        })
    return pd.DataFrame(task_rows), pd.DataFrame(cluster_rows)


def worker_viewpoint_stability(*, permutations: int = 5000, seed: int = 20260821) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    crowd = read_csv(C1 / "geometry_task_crowd_structure_C1.csv")
    evidence = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    excluded_pairs = read_csv(V2 / "EXCLUDED_WORKER_PEER_COMPARISONS.csv")
    if crowd.empty or evidence.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    lookup: dict[str, dict[str, Any]] = {}
    for record in evidence.to_dict("records"):
        for key in (clean(record.get("canonical_annotation_id")), clean(record.get("annotation_id"))):
            if key and key not in lookup:
                lookup[key] = record
    membership_rows: list[dict[str, Any]] = []
    for row in crowd.to_dict("records"):
        if clean(row.get("partition_status")) != "unique":
            continue
        memberships = parse_jsonish(row.get("cluster_membership_json")) or []
        if not isinstance(memberships, list) or not memberships:
            continue
        task_records: list[tuple[str, dict[str, Any], int, int]] = []
        for rank, members in enumerate(memberships, 1):
            for identity in members:
                key = clean(identity)
                if key in lookup:
                    task_records.append((key, lookup[key], rank, len(members)))
        n_pairs = [number(record.get("repaired_point_count")) for _key, record, _rank, _support in task_records]
        n_pairs = [value / 2.0 for value in n_pairs if value is not None]
        task_median_pairs = float(np.median(n_pairs)) if n_pairs else np.nan
        for identity, record, rank, support in task_records:
            points = number(record.get("repaired_point_count"))
            membership_rows.append({
                "base_task_id": clean(row.get("base_task_id")),
                "building_id": clean(row.get("building_id")),
                "condition": clean(row.get("condition")),
                "worker_id": worker_id(record.get("worker_id")),
                "annotation_id": identity,
                "cluster_rank": rank,
                "cluster_support": support,
                "cluster_count": len(memberships),
                "is_largest_mode": rank == 1,
                "is_supported_minority_mode": rank > 1 and support >= 2,
                "n_pairs": points / 2.0 if points is not None else np.nan,
                "task_centered_n_pairs": points / 2.0 - task_median_pairs if points is not None and pd.notna(task_median_pairs) else np.nan,
                "assignment_provenance": clean(record.get("assignment_provenance")),
                "formal_use_allowed": truth(record.get("formal_use_allowed")),
                "worker_process_class": clean(record.get("worker_process_class")),
            })
    memberships = pd.DataFrame(membership_rows)
    if memberships.empty:
        return memberships, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    worker_rows: list[dict[str, Any]] = []
    for worker, group in memberships.groupby("worker_id"):
        worker_rows.append({
            "worker_id": worker,
            "task_count": int(len(group)),
            "building_count": int(group["building_id"].nunique()),
            "manual_task_count": int(group["condition"].eq("manual").sum()),
            "semi_task_count": int(group["condition"].eq("semi").sum()),
            "largest_mode_rate": float(group["is_largest_mode"].mean()),
            "supported_minority_mode_rate": float(group["is_supported_minority_mode"].mean()),
            "mean_task_centered_n_pairs": float(group["task_centered_n_pairs"].mean()) if group["task_centered_n_pairs"].notna().any() else np.nan,
            "median_task_centered_n_pairs": float(group["task_centered_n_pairs"].median()) if group["task_centered_n_pairs"].notna().any() else np.nan,
            "formal_use_allowed_any": bool(group["formal_use_allowed"].any()),
            "assignment_provenance_values": ";".join(sorted(set(group["assignment_provenance"]) - {""})),
            "interpretation": "descriptive_worker_viewpoint_rate_not_quality_rank",
        })
    workers = pd.DataFrame(worker_rows)

    supported_workers = workers[workers["task_count"] >= 5].copy()
    observed_variance = float(supported_workers["largest_mode_rate"].var(ddof=0)) if len(supported_workers) >= 2 else np.nan
    rng = np.random.default_rng(seed)
    permutation_values: list[float] = []
    if pd.notna(observed_variance) and permutations > 0:
        template = memberships.copy()
        for _ in range(permutations):
            shuffled = template.copy()
            for _, indices in shuffled.groupby(["base_task_id", "condition"]).groups.items():
                indices = list(indices)
                shuffled.loc[indices, "is_largest_mode"] = rng.permutation(shuffled.loc[indices, "is_largest_mode"].to_numpy())
            rates = shuffled.groupby("worker_id")["is_largest_mode"].mean()
            task_counts = shuffled.groupby("worker_id").size()
            rates = rates[task_counts >= 5]
            if len(rates) >= 2:
                permutation_values.append(float(rates.var(ddof=0)))
    p_value = (1 + sum(value >= observed_variance - 1e-15 for value in permutation_values)) / (len(permutation_values) + 1) if permutation_values else np.nan
    test = pd.DataFrame([{
        "test": "task_stratified_worker_largest_mode_rate_heterogeneity",
        "supported_worker_count": len(supported_workers),
        "minimum_tasks_per_worker": 5,
        "observed_worker_rate_variance": observed_variance,
        "permutation_count": len(permutation_values),
        "permutation_p_value": p_value,
        "interpretation_boundary": "tests repeated mode-membership heterogeneity;does_not_identify_correctness_or_cause",
    }])

    pair_rows: list[dict[str, Any]] = []
    by_worker = {worker: group.set_index(["base_task_id", "condition"]) for worker, group in memberships.groupby("worker_id")}
    for left, right in combinations(sorted(by_worker), 2):
        shared = by_worker[left].index.intersection(by_worker[right].index)
        if len(shared) < 3:
            continue
        left_rows = by_worker[left].loc[shared]
        right_rows = by_worker[right].loc[shared]
        if isinstance(left_rows, pd.Series):
            left_rows = left_rows.to_frame().T
            right_rows = right_rows.to_frame().T
        same = (left_rows["cluster_rank"].to_numpy() == right_rows["cluster_rank"].to_numpy())
        pair_rows.append({
            "worker_id_left": left,
            "worker_id_right": right,
            "shared_task_condition_count": len(shared),
            "same_cluster_rate": float(np.mean(same)),
            "both_largest_mode_rate": float(np.mean(left_rows["is_largest_mode"].to_numpy() & right_rows["is_largest_mode"].to_numpy())),
            "opposite_largest_status_rate": float(np.mean(left_rows["is_largest_mode"].to_numpy() != right_rows["is_largest_mode"].to_numpy())),
            "interpretation": "descriptive_co_clustering_not_independent_pair_sample",
        })
    pairs = pd.DataFrame(pair_rows)

    # Explicitly retain workers with excluded/outside peer evidence even when no
    # validated complete partition can assign a stable cluster.
    if not excluded_pairs.empty:
        excluded_summary = excluded_pairs.groupby("excluded_worker_id").agg(
            excluded_peer_pair_count=("formal_peer_worker_id", "size"),
            excluded_shared_task_count=("base_task_id", "nunique"),
            q_boundary_median=("q_boundary", lambda values: pd.to_numeric(values, errors="coerce").median()),
            q_wallwall_median=("q_wallwall", lambda values: pd.to_numeric(values, errors="coerce").median()),
            q095_compatible_rate=("passes_q095", lambda values: np.mean([truth(value) for value in values])),
        ).reset_index().rename(columns={"excluded_worker_id": "worker_id"})
        excluded_summary["cluster_membership_status"] = "peer_comparison_available_stable_cluster_not_materialized"
    else:
        excluded_summary = pd.DataFrame()
    return memberships, workers, pairs, pd.concat([test, excluded_summary], ignore_index=True, sort=False)


def persistent_disagreement_catalog() -> pd.DataFrame:
    frame = read_csv(PERSISTENT / "PERSISTENT_DISAGREEMENT_TASKS.csv")
    if frame.empty:
        return frame
    numeric = ["similarity_threshold", "valid_k", "cluster_count", "largest_cluster_support", "second_cluster_support", "largest_cluster_share", "second_cluster_share"]
    for column in numeric:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("supported_multimodal", "strong_persistent_split", "severe_persistent_split", "not_evaluable_partition"):
        if column in frame:
            frame[column] = frame[column].map(truth)
    return frame
