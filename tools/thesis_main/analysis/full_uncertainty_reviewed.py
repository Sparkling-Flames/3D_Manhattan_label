"""Reviewed corrections and expanded analyses for the advisor-facing report.

This module is intentionally explicit about three distinctions:
1. observed active engagement versus Label Studio elapsed lead time;
2. high-support persistent disagreement versus cap-five uncertainty;
3. supported crowd modes versus singleton dissent.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from tools.thesis_main.analysis.full_uncertainty_common import (
    C1,
    PACKAGE,
    PERSISTENT,
    ROOT,
    V2,
    bernoulli_entropy,
    choice_group,
    clean,
    extract_choice_records,
    parse_jsonish,
    read_csv,
    truth,
    worker_id,
)
from tools.thesis_main.analysis.full_uncertainty_geometry import worker_viewpoint_stability

SEED = 20260821
STAGE_MAP = {
    "C2A-RP-B1": "C2-A-RP-B1",
    "C2A-RP-B2": "C2-A-RP-B2",
    "C2A_RP_B1": "C2-A-RP-B1",
    "C2A_RP_B2": "C2-A-RP-B2",
    "C2-A-RP-B1": "C2-A-RP-B1",
    "C2-A-RP-B2": "C2-A-RP-B2",
}


def normalise_stage(value: Any) -> str:
    token = clean(value)
    return STAGE_MAP.get(token, token)


def normalise_raw_stages(raw: pd.DataFrame) -> pd.DataFrame:
    result = raw.copy()
    if "stage" in result:
        result["stage"] = result["stage"].map(normalise_stage)
    return result


def _merge_c1_classification(unified: pd.DataFrame) -> pd.DataFrame:
    classification = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    if classification.empty:
        return unified
    columns = [
        "canonical_annotation_id", "annotation_id", "assignment_provenance",
        "primary_exclusion_class", "secondary_exclusion_flags", "worker_process_class",
        "formal_use_allowed", "task_final_scope", "geometry_reference_status",
        "iou_to_gt", "worker_caused_structural_failure",
    ]
    columns = [column for column in columns if column in classification]
    selected = classification[columns].copy()
    selected["canonical_annotation_id"] = selected["canonical_annotation_id"].map(clean)
    selected = selected.drop_duplicates("canonical_annotation_id")
    mask = unified["stage"].eq("C1")
    c1 = unified.loc[mask].copy()
    c1["canonical_annotation_id"] = c1["canonical_annotation_id"].map(clean)
    c1 = c1.merge(selected, how="left", on="canonical_annotation_id", suffixes=("", "_class"))
    for column in (
        "assignment_provenance", "formal_use_allowed", "primary_exclusion_class",
        "secondary_exclusion_flags", "worker_process_class", "task_final_scope",
        "geometry_reference_status", "iou_to_gt", "worker_caused_structural_failure",
    ):
        classified = f"{column}_class"
        if classified not in c1:
            continue
        if column not in c1:
            c1[column] = c1[classified]
        else:
            source = c1[classified].astype(str)
            missing = c1[column].astype(str).map(clean).eq("")
            usable = source.map(clean).ne("")
            c1.loc[missing & usable, column] = source.loc[missing & usable]
        c1 = c1.drop(columns=[classified])
    if "annotation_id_class" in c1:
        c1 = c1.drop(columns=["annotation_id_class"])
    return pd.concat([unified.loc[~mask], c1], ignore_index=True, sort=False)


def _lead_time_lookup(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    frame = normalise_raw_stages(raw)
    frame["project_id"] = frame["project_id"].map(clean)
    frame["ls_runtime_task_id"] = frame["ls_runtime_task_id"].map(clean)
    frame["worker_id"] = frame["worker_id"].map(worker_id)
    frame["annotation_id"] = frame["annotation_id"].map(clean)
    frame["lead_time_seconds"] = pd.to_numeric(frame["lead_time_seconds"], errors="coerce")
    keys = ["stage", "project_id", "ls_runtime_task_id", "worker_id", "annotation_id"]
    return frame.groupby(keys, dropna=False).agg(
        raw_lead_time_seconds=("lead_time_seconds", "median"),
        raw_lead_time_observation_count=("lead_time_seconds", "count"),
        raw_annotation_version_count=("annotation_id", "size"),
    ).reset_index()


def review_unified_timing(unified: pd.DataFrame, raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove lead/proxy values from active-time analysis and attach raw lead time."""
    frame = unified.copy()
    frame["stage"] = frame["stage"].map(normalise_stage)
    frame = _merge_c1_classification(frame)
    frame["worker_id"] = frame["worker_id"].map(worker_id)
    for column in ("project_id", "runtime_task_id", "annotation_id"):
        frame[column] = frame[column].map(clean)

    frame["active_time_candidate_seconds"] = pd.to_numeric(frame["active_time_observed_seconds"], errors="coerce")
    source_text = (
        frame.get("active_time_source", pd.Series([""] * len(frame))).astype(str)
        + " "
        + frame.get("timing_status", pd.Series([""] * len(frame))).astype(str)
    ).str.lower()
    proxy = source_text.str.contains("lead_time|lead time|fallback|proxy", regex=True, na=False)
    frame["active_time_proxy_excluded"] = proxy & frame["active_time_candidate_seconds"].notna()
    frame["active_time_observed_seconds"] = frame["active_time_candidate_seconds"].where(~proxy, np.nan)
    formal = frame.get("active_time_formal_eligible", pd.Series([False] * len(frame))).map(truth)
    frame["active_time_formal_eligible"] = formal & frame["active_time_observed_seconds"].notna()
    frame["active_time_measurement_class"] = np.select(
        [
            frame["active_time_proxy_excluded"],
            frame["active_time_observed_seconds"].isna(),
            frame["active_time_formal_eligible"],
        ],
        ["lead_time_proxy_excluded", "missing", "formal_frozen"],
        default="direct_observed_nonformal",
    )

    lookup = _lead_time_lookup(raw)
    if not lookup.empty:
        merge_keys = ["stage", "project_id", "runtime_task_id", "worker_id", "annotation_id"]
        lookup = lookup.rename(columns={"ls_runtime_task_id": "runtime_task_id"})
        frame = frame.merge(lookup, how="left", on=merge_keys)
        existing = pd.to_numeric(frame.get("lead_time_seconds", pd.Series([np.nan] * len(frame))), errors="coerce")
        raw_lead = pd.to_numeric(frame["raw_lead_time_seconds"], errors="coerce")
        frame["lead_time_seconds"] = existing.where(existing.notna(), raw_lead)
        frame["lead_time_source"] = np.where(
            raw_lead.notna(), "raw_annotation_fact_label_studio_lead_time",
            np.where(existing.notna(), "stage_canonical_label_studio_lead_time", "missing"),
        )
    else:
        frame["raw_lead_time_seconds"] = np.nan
        frame["raw_lead_time_observation_count"] = 0
        frame["raw_annotation_version_count"] = 0
        frame["lead_time_source"] = np.where(
            pd.to_numeric(frame["lead_time_seconds"], errors="coerce").notna(),
            "stage_canonical_label_studio_lead_time", "missing",
        )
    frame["lead_time_seconds"] = pd.to_numeric(frame["lead_time_seconds"], errors="coerce")
    frame["lead_time_computable"] = frame["lead_time_seconds"].notna()
    frame["active_time_computable"] = frame["active_time_observed_seconds"].notna()

    source_audit = frame.groupby(
        ["stage", "condition", "active_time_source", "timing_status", "active_time_measurement_class"],
        dropna=False,
    ).agg(
        record_count=("annotation_id", "size"),
        active_candidate_count=("active_time_candidate_seconds", "count"),
        active_direct_count=("active_time_observed_seconds", "count"),
        active_formal_count=("active_time_formal_eligible", "sum"),
        lead_time_count=("lead_time_seconds", "count"),
        worker_count=("worker_id", "nunique"),
        task_count=("base_task_id", "nunique"),
    ).reset_index()

    if frame.loc[frame["active_time_proxy_excluded"], "active_time_observed_seconds"].notna().any():
        raise AssertionError("lead-time/proxy value leaked into active-time outcome")
    if len(frame) != 2501:
        raise AssertionError(f"selected/auditable spine drift: {len(frame)} != 2501")
    c1 = frame[frame["stage"].eq("C1")]
    if len(c1) != 780 or c1["worker_id"].nunique() != 23:
        raise AssertionError("C1 canonical/auditable spine drift")
    if len(c1[c1["worker_id"].eq("14")]) != 32:
        raise AssertionError("W014 contexts were not fully retained")
    if c1["lead_time_seconds"].notna().sum() < 750:
        raise AssertionError("C1 raw Label Studio lead time failed to bind")
    return frame, source_audit


def reviewed_meta_labels(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw = normalise_raw_stages(raw)
    long_rows: list[dict[str, Any]] = []
    response_rows: list[dict[str, Any]] = []
    response_universe: list[dict[str, Any]] = []
    for row in raw.itertuples(index=False):
        response_id = "|".join([
            clean(getattr(row, "stage", "")), clean(getattr(row, "project_id", "")),
            clean(getattr(row, "ls_runtime_task_id", "")), worker_id(getattr(row, "worker_id", "")),
            clean(getattr(row, "annotation_id", "")),
        ])
        response_universe.append({
            "stage": getattr(row, "stage", ""), "condition": getattr(row, "condition", ""),
            "base_task_id": getattr(row, "base_task_id", ""), "worker_id": worker_id(getattr(row, "worker_id", "")),
            "response_id": response_id, "canonical_join_status": getattr(row, "canonical_join_status", ""),
            "image_reference": getattr(row, "image_reference", ""),
        })
        grouped: dict[str, set[str]] = defaultdict(set)
        for item in extract_choice_records(getattr(row, "result_json", "")):
            group, code, label_zh = choice_group(item["from_name"], item["choice_raw"])
            grouped[group].add(code)
            long_rows.append({
                "stage": getattr(row, "stage", ""), "condition": getattr(row, "condition", ""),
                "project_id": getattr(row, "project_id", ""), "runtime_task_id": getattr(row, "ls_runtime_task_id", ""),
                "base_task_id": getattr(row, "base_task_id", ""), "worker_id": worker_id(getattr(row, "worker_id", "")),
                "annotation_id": getattr(row, "annotation_id", ""), "canonical_annotation_id": getattr(row, "canonical_annotation_id", ""),
                "canonical_join_status": getattr(row, "canonical_join_status", ""), "response_id": response_id,
                "meta_group": group, "choice_code": code, "choice_label_zh": label_zh,
                "choice_raw": item["choice_raw"], "from_name": item["from_name"],
                "result_type": item["result_type"], "image_reference": getattr(row, "image_reference", ""),
            })
        for group, labels in grouped.items():
            response_rows.append({
                "stage": getattr(row, "stage", ""), "condition": getattr(row, "condition", ""),
                "base_task_id": getattr(row, "base_task_id", ""), "worker_id": worker_id(getattr(row, "worker_id", "")),
                "response_id": response_id, "meta_group": group,
                "label_set_json": json.dumps(sorted(labels), ensure_ascii=False), "label_cardinality": len(labels),
                "canonical_join_status": getattr(row, "canonical_join_status", ""),
                "image_reference": getattr(row, "image_reference", ""),
            })
    long = pd.DataFrame(long_rows)
    responses = pd.DataFrame(response_rows)
    universe = pd.DataFrame(response_universe).drop_duplicates("response_id")
    if long.empty:
        return long, responses, pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    choice_dictionary = long.groupby(
        ["meta_group", "choice_code", "choice_label_zh", "from_name", "choice_raw"], dropna=False,
    ).agg(
        occurrence_count=("response_id", "size"), response_count=("response_id", "nunique"),
        worker_count=("worker_id", "nunique"), task_count=("base_task_id", "nunique"),
        stage_values=("stage", lambda values: ";".join(sorted(set(map(str, values))))),
        condition_values=("condition", lambda values: ";".join(sorted(set(map(str, values))))),
    ).reset_index().sort_values(["meta_group", "response_count"], ascending=[True, False])

    group_denominator = responses.groupby(["stage", "condition", "base_task_id", "meta_group"], dropna=False).agg(
        group_response_count=("response_id", "nunique"), group_worker_count=("worker_id", "nunique"),
    ).reset_index()
    total_denominator = universe.groupby(["stage", "condition", "base_task_id"], dropna=False).agg(
        total_response_count=("response_id", "nunique"), total_worker_count=("worker_id", "nunique"),
    ).reset_index()
    group_denominator = group_denominator.merge(total_denominator, how="left", on=["stage", "condition", "base_task_id"])
    group_denominator["group_response_coverage"] = group_denominator["group_response_count"] / group_denominator["total_response_count"]

    label_counts = long.drop_duplicates(["response_id", "meta_group", "choice_code"]).groupby(
        ["stage", "condition", "base_task_id", "meta_group", "choice_code", "choice_label_zh"], dropna=False,
    ).agg(
        positive_response_count=("response_id", "nunique"), positive_worker_count=("worker_id", "nunique"),
    ).reset_index()
    label_counts = label_counts.merge(group_denominator, how="left", on=["stage", "condition", "base_task_id", "meta_group"])
    label_counts["unasserted_response_count"] = label_counts["total_response_count"] - label_counts["group_response_count"]
    label_counts["positive_share_among_group_responders"] = label_counts["positive_response_count"] / label_counts["group_response_count"]
    label_counts["positive_share_all_responses_descriptive"] = label_counts["positive_response_count"] / label_counts["total_response_count"]
    label_counts["bernoulli_entropy_among_group_responders"] = label_counts["positive_share_among_group_responders"].map(bernoulli_entropy)
    label_counts["denominator_note"] = "unasserted is retained separately and is not silently coded as explicit negative"

    task_rows: list[dict[str, Any]] = []
    for (stage, condition, task, meta_group), group in responses.groupby(
        ["stage", "condition", "base_task_id", "meta_group"], dropna=False
    ):
        sets = [set(parse_jsonish(value) or []) for value in group["label_set_json"]]
        pair_values = []
        for left, right in combinations(sets, 2):
            union = left | right
            pair_values.append(1.0 if not union else len(left & right) / len(union))
        union = sorted(set().union(*sets)) if sets else []
        prevalence = {label: sum(label in values for values in sets) / len(sets) for label in union}
        denominator_row = group_denominator[
            group_denominator["stage"].eq(stage)
            & group_denominator["condition"].eq(condition)
            & group_denominator["base_task_id"].eq(task)
            & group_denominator["meta_group"].eq(meta_group)
        ]
        denominator = denominator_row.iloc[0] if not denominator_row.empty else {}
        task_rows.append({
            "stage": stage, "condition": condition, "base_task_id": task, "meta_group": meta_group,
            "group_response_count": len(group), "total_response_count": denominator.get("total_response_count", np.nan),
            "group_response_coverage": denominator.get("group_response_coverage", np.nan),
            "worker_count": int(group["worker_id"].nunique()), "pair_count": len(pair_values),
            "pairwise_jaccard_mean": float(np.mean(pair_values)) if pair_values else np.nan,
            "pairwise_jaccard_median": float(np.median(pair_values)) if pair_values else np.nan,
            "mean_label_entropy": float(np.mean([bernoulli_entropy(value) for value in prevalence.values()])) if prevalence else np.nan,
            "maximum_label_entropy": float(np.max([bernoulli_entropy(value) for value in prevalence.values()])) if prevalence else np.nan,
            "mean_label_cardinality": float(group["label_cardinality"].mean()),
            "label_union_count": len(union), "label_prevalence_json": json.dumps(prevalence, ensure_ascii=False, sort_keys=True),
            "measurement_note": "raw response versions retained; same-worker revision is not an independent annotator",
        })
    return long, responses, pd.DataFrame(task_rows), label_counts, choice_dictionary


def reviewed_persistent_disagreement() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tasks = read_csv(PERSISTENT / "PERSISTENT_DISAGREEMENT_TASKS.csv")
    robustness = read_csv(PERSISTENT / "PERSISTENT_DISAGREEMENT_THRESHOLD_ROBUSTNESS.csv")
    for frame in (tasks, robustness):
        for column in ("similarity_threshold", "valid_k", "cluster_count", "largest_cluster_support", "second_cluster_support", "largest_cluster_share"):
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        for column in (
            "supported_multimodal", "strong_persistent_split", "severe_persistent_split", "not_evaluable_partition",
            "supported_multimodal_at_all_thresholds", "supported_multimodal_at_any_threshold",
            "strong_at_all_thresholds", "strong_at_any_threshold", "not_evaluable_at_any_threshold",
        ):
            if column in frame:
                frame[column] = frame[column].map(truth)
    task_mask = (
        ((tasks["stage"].eq("Calibration")) & tasks["scenario"].eq("frozen_geometry_pool"))
        | ((tasks["stage"].eq("PreScreen")) & tasks["scenario"].eq("c1_eligible_combined"))
    ) & tasks["support_band"].eq("high_support_k_ge_20")
    high = tasks[task_mask].copy()
    q95 = high[np.isclose(high["similarity_threshold"], 0.95)].copy()

    robust_mask = (
        ((robustness["stage"].eq("Calibration")) & robustness["scenario"].eq("frozen_geometry_pool"))
        | ((robustness["stage"].eq("PreScreen")) & robustness["scenario"].eq("c1_eligible_combined"))
    ) & robustness["support_band"].eq("high_support_k_ge_20")
    robust = robustness[robust_mask].copy()

    expected = {
        "PreScreen": {"tasks": 29, "supported": 14, "strong": 10, "not_eval": 2, "robust": 6},
        "Calibration": {"tasks": 12, "supported": 6, "strong": 5, "not_eval": 3, "robust": 2},
    }
    summary_rows = []
    for stage, contract in expected.items():
        subset = q95[q95["stage"].eq(stage)]
        robust_subset = robust[robust["stage"].eq(stage)]
        observed = {
            "tasks": subset["base_task_id"].nunique(),
            "supported": int(subset["supported_multimodal"].sum()),
            "strong": int(subset["strong_persistent_split"].sum()),
            "not_eval": int(subset["not_evaluable_partition"].sum()),
            "robust": int(robust_subset["strong_at_all_thresholds"].sum()),
        }
        if observed != contract:
            raise AssertionError(f"high-support persistent disagreement drift for {stage}: {observed} != {contract}")
        summary_rows.append({
            "stage": stage, "high_support_task_count": observed["tasks"],
            "supported_multimodal_count_q095": observed["supported"],
            "strong_persistent_split_count_q095": observed["strong"],
            "not_evaluable_partition_count_q095": observed["not_eval"],
            "strong_at_all_three_thresholds_count": observed["robust"],
            "strong_persistent_split_rate_q095": observed["strong"] / observed["tasks"],
            "strong_all_thresholds_rate": observed["robust"] / observed["tasks"],
            "interpretation": "largest observed high support; not infinite-worker convergence claim",
        })
    return q95, robust, pd.DataFrame(summary_rows)


def _c1_quality_lookup() -> dict[str, dict[str, Any]]:
    evidence = read_csv(V2 / "ROW_INCLUSION_CLASSIFICATION.csv")
    lookup: dict[str, dict[str, Any]] = {}
    for row in evidence.to_dict("records"):
        for key in (clean(row.get("canonical_annotation_id")), clean(row.get("annotation_id"))):
            if key and key not in lookup:
                lookup[key] = row
    return lookup


def reviewed_crowd_gt_conflict() -> tuple[pd.DataFrame, pd.DataFrame]:
    crowd = read_csv(C1 / "geometry_task_crowd_structure_C1.csv")
    lookup = _c1_quality_lookup()
    if crowd.empty or not lookup:
        return pd.DataFrame(), pd.DataFrame()
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
                "cluster_count": pd.to_numeric(row.get("cluster_count"), errors="coerce"),
                "largest_cluster_support": pd.to_numeric(row.get("largest_cluster_support"), errors="coerce"),
                "second_cluster_support": pd.to_numeric(row.get("second_cluster_support"), errors="coerce"),
                "supported_cluster_count": np.nan, "singleton_cluster_count": np.nan,
                "largest_cluster_median_iou": np.nan, "best_cluster_median_iou": np.nan,
                "crowd_gt_gap_best_minus_largest": np.nan,
                "crowd_gt_relationship": "partition_not_unique_or_not_evaluable",
            })
            continue
        stats_rows: list[dict[str, Any]] = []
        for rank, members in enumerate(memberships, 1):
            identities = [clean(value) for value in members]
            records = [lookup[identity] for identity in identities if identity in lookup]
            ious = [pd.to_numeric(record.get("iou_to_gt"), errors="coerce") for record in records]
            ious = [float(value) for value in ious if pd.notna(value)]
            stat = {
                "base_task_id": task, "building_id": clean(row.get("building_id")), "condition": condition,
                "cluster_rank": rank, "cluster_support": len(identities), "supported_cluster": len(identities) >= 2,
                "quality_computable_count": len(ious), "cluster_iou_mean": float(np.mean(ious)) if ious else np.nan,
                "cluster_iou_median": float(np.median(ious)) if ious else np.nan,
                "cluster_iou_min": float(np.min(ious)) if ious else np.nan,
                "cluster_iou_max": float(np.max(ious)) if ious else np.nan,
                "worker_ids": ";".join(worker_id(record.get("worker_id")) for record in records),
                "annotation_ids": ";".join(identities),
            }
            stats_rows.append(stat)
            cluster_rows.append(stat)
        finite = [(index, value["cluster_iou_median"]) for index, value in enumerate(stats_rows) if pd.notna(value["cluster_iou_median"])]
        largest = stats_rows[0]["cluster_iou_median"]
        best_index, best_value = max(finite, key=lambda pair: pair[1]) if finite else (-1, np.nan)
        supports = [value["cluster_support"] for value in stats_rows]
        supported_indices = [index for index, value in enumerate(stats_rows) if value["cluster_support"] >= 2]
        high_supported = [index for index in supported_indices if pd.notna(stats_rows[index]["cluster_iou_median"]) and stats_rows[index]["cluster_iou_median"] >= 0.90]
        gap = best_value - largest if pd.notna(best_value) and pd.notna(largest) else np.nan
        if len(stats_rows) == 1:
            relationship = "unimodal_high_gt_alignment" if best_value >= 0.90 else "unimodal_low_gt_alignment" if best_value < 0.80 else "unimodal_intermediate_gt_alignment"
        elif max(supports) == 1:
            relationship = "diffuse_all_singletons_no_supported_crowd_mode"
        elif len(supported_indices) == 1:
            if best_index == 0:
                relationship = "dominant_with_singleton_dissent_largest_cluster_best_gt_alignment"
            elif best_index > 0 and pd.notna(gap) and gap >= 0.05:
                relationship = "dominant_with_singleton_dissent_singleton_better_gt_alignment"
            else:
                relationship = "dominant_with_singleton_dissent_no_clear_gt_order"
        else:
            if len(high_supported) >= 2:
                relationship = "supported_multimodal_multiple_gt_aligned_clusters"
            elif best_index > 0 and stats_rows[best_index]["cluster_support"] >= 2 and pd.notna(gap) and gap >= 0.05:
                relationship = "supported_multimodal_nonlargest_supported_cluster_better_gt_alignment"
            elif best_index == 0:
                relationship = "supported_multimodal_largest_cluster_best_gt_alignment"
            else:
                relationship = "supported_multimodal_no_clear_gt_alignment_order"
        first_record = next((lookup[identity] for members in memberships for identity in map(clean, members) if identity in lookup), {})
        task_rows.append({
            "base_task_id": task, "building_id": clean(row.get("building_id")), "condition": condition,
            "partition_status": partition, "task_crowd_structure_status": clean(row.get("task_crowd_structure_status")),
            "cluster_count": len(stats_rows), "largest_cluster_support": supports[0],
            "second_cluster_support": supports[1] if len(supports) > 1 else 0,
            "supported_cluster_count": len(supported_indices), "singleton_cluster_count": sum(value == 1 for value in supports),
            "largest_cluster_median_iou": largest, "best_cluster_rank": best_index + 1 if best_index >= 0 else np.nan,
            "best_cluster_support": stats_rows[best_index]["cluster_support"] if best_index >= 0 else np.nan,
            "best_cluster_median_iou": best_value, "crowd_gt_gap_best_minus_largest": gap,
            "crowd_gt_relationship": relationship,
            "task_final_scope": clean(first_record.get("task_final_scope")),
            "geometry_reference_status": clean(first_record.get("geometry_reference_status")),
            "display_thresholds": "high_alignment>=0.90;low_alignment<0.80;gap>=0.05;descriptive_only",
        })
    return pd.DataFrame(task_rows), pd.DataFrame(cluster_rows)


def _permutation_variance(
    memberships: pd.DataFrame, value_column: str, *, minimum_tasks: int = 5, permutations: int = 5000,
) -> dict[str, Any]:
    valid = memberships.dropna(subset=[value_column]).copy()
    counts = valid.groupby("worker_id").size()
    workers = counts[counts >= minimum_tasks].index
    rates = valid[valid["worker_id"].isin(workers)].groupby("worker_id")[value_column].mean()
    observed = float(rates.var(ddof=0)) if len(rates) >= 2 else np.nan
    if not math.isfinite(observed):
        return {"observed_variance": np.nan, "p_value": np.nan, "worker_count": len(rates), "permutations": 0}
    rng = np.random.default_rng(SEED + sum(map(ord, value_column)))
    draws = []
    for _ in range(permutations):
        shuffled = valid.copy()
        for _, indices in shuffled.groupby(["base_task_id", "condition"]).groups.items():
            indices = list(indices)
            shuffled.loc[indices, value_column] = rng.permutation(shuffled.loc[indices, value_column].to_numpy())
        draw_counts = shuffled.groupby("worker_id").size()
        draw_workers = draw_counts[draw_counts >= minimum_tasks].index
        draw_rates = shuffled[shuffled["worker_id"].isin(draw_workers)].groupby("worker_id")[value_column].mean()
        if len(draw_rates) >= 2:
            draws.append(float(draw_rates.var(ddof=0)))
    p = (1 + sum(value >= observed - 1e-15 for value in draws)) / (len(draws) + 1)
    return {"observed_variance": observed, "p_value": p, "worker_count": len(rates), "permutations": len(draws)}


def _split_half_reliability(memberships: pd.DataFrame, *, repetitions: int = 2000) -> dict[str, Any]:
    manual = memberships[memberships["condition"].eq("manual")].copy()
    tasks = sorted(manual["base_task_id"].unique())
    if len(tasks) < 10:
        return {"valid_split_count": 0}
    rng = np.random.default_rng(SEED)
    correlations = []
    worker_counts = []
    for _ in range(repetitions):
        permuted = rng.permutation(tasks)
        left_tasks = set(permuted[: len(tasks) // 2])
        right_tasks = set(permuted[len(tasks) // 2 :])
        left = manual[manual["base_task_id"].isin(left_tasks)].groupby("worker_id")["is_largest_mode"].agg(["mean", "count"])
        right = manual[manual["base_task_id"].isin(right_tasks)].groupby("worker_id")["is_largest_mode"].agg(["mean", "count"])
        shared = left.index.intersection(right.index)
        shared = [worker for worker in shared if left.loc[worker, "count"] >= 3 and right.loc[worker, "count"] >= 3]
        if len(shared) < 5:
            continue
        x = left.loc[shared, "mean"]
        y = right.loc[shared, "mean"]
        if x.nunique() < 2 or y.nunique() < 2:
            continue
        correlations.append(float(stats.spearmanr(x, y).statistic))
        worker_counts.append(len(shared))
    if not correlations:
        return {"valid_split_count": 0}
    return {
        "valid_split_count": len(correlations),
        "median_split_half_spearman": float(np.median(correlations)),
        "q25_split_half_spearman": float(np.quantile(correlations, 0.25)),
        "q75_split_half_spearman": float(np.quantile(correlations, 0.75)),
        "median_worker_count_per_split": float(np.median(worker_counts)),
        "interpretation": "descriptive repeatability under random task halves; not external validation",
    }


def reviewed_worker_viewpoints() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    memberships, workers, pairs, original_tests = worker_viewpoint_stability()
    if memberships.empty:
        return memberships, workers, pairs, original_tests, pd.DataFrame()
    largest = _permutation_variance(memberships, "is_largest_mode")
    minority = _permutation_variance(memberships, "is_supported_minority_mode")
    centered = _permutation_variance(memberships, "task_centered_n_pairs")
    split = _split_half_reliability(memberships)
    tests = pd.DataFrame([
        {"test": "task_stratified_worker_largest_mode_rate_heterogeneity", **largest,
         "interpretation": "repeated mode-membership heterogeneity; not correctness or cause"},
        {"test": "task_stratified_worker_supported_minority_rate_heterogeneity", **minority,
         "interpretation": "repeated supported-minority tendency; not correctness or cause"},
        {"test": "task_stratified_worker_centered_pair_count_heterogeneity", **centered,
         "interpretation": "worker tendency to use more/fewer corner pairs after task centering"},
        {"test": "manual_task_random_split_half_largest_mode_rate", **split,
         "interpretation": split.get("interpretation", "not_evaluable")},
    ])
    excluded = original_tests[original_tests.get("cluster_membership_status", pd.Series(dtype=str)).ne("")].copy() if not original_tests.empty and "cluster_membership_status" in original_tests else pd.DataFrame()
    return memberships, workers, pairs, tests, excluded


def semi_required_sample_projection(projection: pd.DataFrame) -> pd.DataFrame:
    if projection.empty:
        return pd.DataFrame()
    sd_values = pd.to_numeric(projection["observed_building_mean_sd"], errors="coerce").dropna()
    if sd_values.empty:
        return pd.DataFrame()
    sd = float(sd_values.iloc[0])
    current_buildings = int(pd.to_numeric(projection["projected_independent_building_count"], errors="coerce").min())
    base = projection[projection["projected_independent_building_count"].eq(current_buildings)].iloc[0]
    tasks_per_building = float(base["projected_paired_task_count_if_current_tasks_per_building"]) / current_buildings
    z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
    rows = []
    for effect in (0.05, 0.10, 0.15, 0.20):
        total_buildings = int(math.ceil((z * sd / effect) ** 2))
        rows.append({
            "assumed_true_absolute_entropy_effect": effect,
            "approximate_total_independent_buildings_for_80pct_power": total_buildings,
            "approximate_additional_buildings_beyond_current": max(0, total_buildings - current_buildings),
            "approximate_total_paired_tasks_at_current_tasks_per_building": int(math.ceil(tasks_per_building * total_buildings)),
            "assumption": "normal approximation; current building-level variance; comparable independent future buildings",
            "warning": "not a guarantee and invalid if future design/variance differs",
        })
    return pd.DataFrame(rows)


def reviewed_semi_mechanisms() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    review = read_csv(PACKAGE / "semi_review_fact.csv")
    population = read_csv(V2 / "POPULATION_TASK_METRICS.csv")
    quality = read_csv(V2 / "QUALITY_AUXILIARY.csv")
    if review.empty or population.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    for column in ("U_initial", "delta_U", "geometry_edit_rmse_px"):
        if column in review:
            review[column] = pd.to_numeric(review[column], errors="coerce")
    review = review[review["stage"].eq("C1")].copy()
    review["edited"] = review["geometry_edit_rmse_px"].fillna(0).gt(0)
    review["harmful_001"] = review["delta_U"].lt(-0.01)
    review["improving_001"] = review["delta_U"].gt(0.01)
    review["issue_reported_bool"] = review.get("issue_reported", pd.Series([False] * len(review))).map(truth)
    task_review = review.groupby("base_task_id", as_index=False).agg(
        semi_review_row_count=("worker_id", "size"), initial_quality_mean=("U_initial", "mean"),
        initial_quality_median=("U_initial", "median"), edit_rate=("edited", "mean"),
        edit_rmse_mean=("geometry_edit_rmse_px", "mean"), delta_u_mean=("delta_U", "mean"),
        harmful_rate_001=("harmful_001", "mean"), improving_rate_001=("improving_001", "mean"),
        issue_report_rate=("issue_reported_bool", "mean"),
    )
    population["threshold"] = pd.to_numeric(population["threshold"], errors="coerce")
    population["delta_shannon_entropy"] = pd.to_numeric(population["delta_shannon_entropy"], errors="coerce")
    task = population[
        population["population"].eq("all_canonical_planned") & np.isclose(population["threshold"], 0.95)
    ][["base_task_id", "building_id", "delta_shannon_entropy", "manual_shannon_entropy", "semi_shannon_entropy"]]
    task = task.merge(task_review, how="left", on="base_task_id")
    if not quality.empty:
        quality["delta_iou_to_gt"] = pd.to_numeric(quality["delta_iou_to_gt"], errors="coerce")
        task = task.merge(quality[["base_task_id", "delta_iou_to_gt"]], how="left", on="base_task_id")
    rows = []
    for x, y in (
        ("initial_quality_mean", "delta_shannon_entropy"),
        ("edit_rate", "delta_shannon_entropy"),
        ("harmful_rate_001", "delta_shannon_entropy"),
        ("initial_quality_mean", "delta_iou_to_gt"),
        ("edit_rate", "delta_iou_to_gt"),
        ("delta_shannon_entropy", "delta_iou_to_gt"),
    ):
        if x not in task or y not in task:
            continue
        usable = task[[x, y]].dropna()
        rho = float(stats.spearmanr(usable[x], usable[y]).statistic) if len(usable) >= 5 and usable[x].nunique() > 1 and usable[y].nunique() > 1 else np.nan
        rows.append({
            "predictor": x, "outcome": y, "task_count": len(usable), "spearman_rho": rho,
            "interpretation": "task-level proposal-conditioned association; not randomized causal mechanism",
        })
    return task, pd.DataFrame(rows), task_review
