from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from tools.thesis_main.analysis.audit_rq1_corrections_20260826 import (
    build_variants,
    deterministic_building_bootstrap_spearman,
    formal_time_difficulty_analysis,
    git_head,
    group_records,
    select_latest_non_cancelled,
    sha256_file,
    subset_distance,
    task_pairwise_metrics,
)
from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.raw_difficulty_time_recompute_20260826 import (
    TAG_PATTERNS,
    normalise_tags,
)
from tools.thesis_main.analysis.raw_rq1_recompute_20260826 import (
    ROOT,
    SOURCE_FILES,
    CanonicalRecord,
    load_raw,
    quantile,
    spearman,
    write_rows,
)


DEFAULT_OUT = ROOT / "analysis_results" / "rq1_stratified_uncertainty_20260827_v1"
SEED = 20260827
KS = (3, 5, 8, 10, 12, 15, 20)
CLUSTER_THRESHOLDS = (0.90, 0.925, 0.95, 0.97, 0.98)
C2_SOURCE_FILES: tuple[tuple[str, str, str, str], ...] = (
    ("C2-B", "manual", "C2-B", "export_label/c2B_Chinese/project-77-at-2026-08-06-14-39-a247e8c0.json"),
    ("C2-B", "manual", "C2-B", "export_label/c2B_English/project-76-at-2026-08-06-14-41-45400e98.json"),
    ("C2-A-RP-B1", "manual", "C2-A-RP", "export_label/c2arp_block1/project-78-at-2026-08-10-07-22-d878a022.json"),
    ("C2-A-RP-B1", "manual", "C2-A-RP", "export_label/c2arp_block1/project-79-at-2026-08-10-07-21-c5055ba6.json"),
    ("C2-A-RP-B2", "manual", "C2-A-RP", "export_label/c2arp_block2/project-84-at-2026-08-14-08-36-31615637.json"),
    ("C2-A-RP-B2", "manual", "C2-A-RP", "export_label/c2arp_block2/project-85-at-2026-08-14-08-36-71fffb37.json"),
)
ALL_SOURCE_FILES = SOURCE_FILES + C2_SOURCE_FILES


def support_band(k: int) -> str:
    if k <= 0:
        return "k0"
    if k == 1:
        return "k1"
    if k <= 4:
        return "k2_4"
    if k <= 7:
        return "k5_7"
    if k <= 14:
        return "k8_14"
    return "k15_plus"


def cardinality_shape(counts: Counter[int]) -> str:
    total = sum(counts.values())
    if total == 0:
        return "not_evaluable"
    shares = sorted((count / total for count in counts.values()), reverse=True)
    top1 = shares[0]
    top2 = sum(shares[:2])
    if top1 >= 0.90:
        return "cardinality_concentrated"
    if top1 >= 0.70 and top2 >= 0.90:
        return "dominant_with_cardinality_dissent"
    if top2 >= 0.80:
        return "two_dominant_cardinalities"
    return "diffuse_cardinality"


def partial_spearman(
    rows: list[dict[str, Any]], predictor: str, outcome: str, control: str
) -> float | None:
    usable = [
        row
        for row in rows
        if row.get(predictor) is not None
        and row.get(outcome) is not None
        and row.get(control) is not None
    ]
    if len(usable) < 5:
        return None
    x = np.asarray([float(row[predictor]) for row in usable])
    y = np.asarray([float(row[outcome]) for row in usable])
    z = np.asarray([float(row[control]) for row in usable])
    r_xy, r_xz, r_yz = spearman(x, y), spearman(x, z), spearman(y, z)
    if r_xy is None or r_xz is None or r_yz is None:
        return None
    denominator = math.sqrt(max(0.0, (1.0 - r_xz**2) * (1.0 - r_yz**2)))
    return None if denominator <= 1e-12 else (r_xy - r_xz * r_yz) / denominator


def first_stable_k(
    rows: Iterable[dict[str, Any]], field: str, minimum_probability: float = 0.80
) -> int | None:
    ordered = sorted(
        (row for row in rows if row.get(field) is not None), key=lambda row: int(row["k"])
    )
    for index, row in enumerate(ordered):
        if all(float(later[field]) >= minimum_probability for later in ordered[index:]):
            return int(row["k"])
    return None


def _stage_parent(stage: str) -> str:
    return "C2-A-RP" if stage.startswith("C2-A-RP-") else stage


def _block_index(stage: str) -> int:
    return 1 if stage.endswith("B1") else 2 if stage.endswith("B2") else 0


def _cell_id(key: tuple[str, str, str, str]) -> str:
    return "|".join(key)


def _choice_values(record: CanonicalRecord, field_name: str) -> list[str]:
    try:
        payload = json.loads(record.raw.choices_json or "{}")
    except json.JSONDecodeError:
        return []
    for field, values in payload.items():
        if str(field).strip().casefold() != field_name.casefold():
            continue
        if not isinstance(values, list):
            values = [values]
        return [str(value) for value in values if value not in (None, "")]
    return []


def _jackknife_se(
    records: list[CanonicalRecord],
    lookup: dict[tuple[str, str], dict[str, Any]],
    channel: str,
) -> tuple[float | None, float | None, float | None]:
    if len(records) < 3:
        return None, None, None
    values = []
    for omitted in range(len(records)):
        value = subset_distance(records[:omitted] + records[omitted + 1 :], lookup, channel)
        if value is not None:
            values.append(value)
    if len(values) != len(records):
        return None, min(values) if values else None, max(values) if values else None
    mean = float(np.mean(values))
    se = math.sqrt((len(values) - 1) / len(values) * sum((value - mean) ** 2 for value in values))
    return se, min(values), max(values)


def _task_tables(
    groups: dict[tuple[str, str, str, str], list[CanonicalRecord]],
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, str, str, str], dict[str, Any]],
    dict[tuple[str, str, str, str], dict[tuple[str, str], dict[str, Any]]],
]:
    rows: list[dict[str, Any]] = []
    metric_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    lookups: dict[
        tuple[str, str, str, str], dict[tuple[str, str], dict[str, Any]]
    ] = {}
    for key, records in sorted(groups.items()):
        stage, condition, dataset_group, base = key
        metric, lookup = task_pairwise_metrics(key, records)
        metric_rows[key], lookups[key] = metric, lookup
        valid = [record for record in records if record.strict.get("valid")]
        count_distribution = Counter(int(record.strict.get("n_pairs", 0)) for record in valid)
        ordered_counts = sorted(count_distribution.items(), key=lambda item: (-item[1], item[0]))
        difficulty = [normalise_tags(record.raw.choices_json)[0] for record in valid]
        difficulty = [tags for tags in difficulty if tags]
        scopes = [_choice_values(record, "scope") for record in valid]
        scopes = [values for values in scopes if values]
        mask_se, loo_min, loo_max = _jackknife_se(valid, lookup, "mask")
        total = sum(count_distribution.values())
        largest = ordered_counts[0][1] / total if ordered_counts else None
        top2 = sum(count for _, count in ordered_counts[:2]) / total if ordered_counts else None
        row: dict[str, Any] = {
            **metric,
            "task_cell_id": _cell_id(key),
            "stage_parent": _stage_parent(stage),
            "block_index": _block_index(stage),
            "building_id": base.split("_", 1)[0],
            "support_band": support_band(len(valid)),
            "mask_jackknife_se": mask_se,
            "mask_loo_min": loo_min,
            "mask_loo_max": loo_max,
            "vertical_boundary_count_distribution_json": json.dumps(
                dict(sorted(count_distribution.items())), sort_keys=True
            ),
            "vertical_boundary_count_mode_count": len(count_distribution),
            "largest_vertical_boundary_count_share": largest,
            "top2_vertical_boundary_count_share": top2,
            "vertical_boundary_cardinality_shape": cardinality_shape(count_distribution),
            "difficulty_response_count": len(difficulty),
            "difficulty_nontrivial_rate": (
                float(np.mean([any(tag != "trivial" for tag in tags) for tags in difficulty]))
                if difficulty
                else None
            ),
            "difficulty_nontrivial_tag_count_mean": (
                float(np.mean([sum(tag != "trivial" for tag in tags) for tags in difficulty]))
                if difficulty
                else None
            ),
            "scope_response_count": len(scopes),
            "scope_non_normal_rate": (
                float(
                    np.mean(
                        [not any(value.casefold() == "normal" for value in values) for values in scopes]
                    )
                )
                if scopes
                else None
            ),
            "scope_choice_set_count": len({tuple(sorted(values)) for values in scopes}),
        }
        for tag in TAG_PATTERNS:
            row[f"difficulty_{tag}_rate"] = (
                float(np.mean([tag in tags for tags in difficulty])) if difficulty else None
            )
        rows.append(row)
    return rows, metric_rows, lookups


def _support_summary(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        grouped[(str(row["stage"]), str(row["condition"]))].append(row)
    out = []
    for (stage, condition), rows in sorted(grouped.items()):
        out.append(
            {
                "stage": stage,
                "stage_parent": _stage_parent(stage),
                "block_index": _block_index(stage),
                "condition": condition,
                "task_cell_count": len(rows),
                "unique_base_image_count": len({row["base_task_id"] for row in rows}),
                "unique_building_count": len({row["building_id"] for row in rows}),
                "selected_annotation_count": sum(int(row["selected_support"]) for row in rows),
                "geometry_valid_annotation_count": sum(int(row["strict_valid_support"]) for row in rows),
                "k0_task_count": sum(row["support_band"] == "k0" for row in rows),
                "k1_task_count": sum(row["support_band"] == "k1" for row in rows),
                "k2_4_task_count": sum(row["support_band"] == "k2_4" for row in rows),
                "k5_7_task_count": sum(row["support_band"] == "k5_7" for row in rows),
                "k8_14_task_count": sum(row["support_band"] == "k8_14" for row in rows),
                "k15_plus_task_count": sum(row["support_band"] == "k15_plus" for row in rows),
            }
        )
    return out


def _difficulty_associations(task_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        if int(row["strict_valid_support"]) >= 5:
            grouped[(str(row["stage"]), str(row["condition"]))].append(row)
    outcomes = (
        "difficulty_nontrivial_rate",
        "difficulty_nontrivial_tag_count_mean",
        "difficulty_occlusion_rate",
        "difficulty_seam_rate",
        "difficulty_reflection_rate",
        "difficulty_low_texture_rate",
        "difficulty_low_quality_rate",
        "scope_non_normal_rate",
    )
    out: list[dict[str, Any]] = []
    seed_offset = 1000
    for (stage, condition), rows in sorted(grouped.items()):
        comparisons = [("mask_distance_mean", outcome) for outcome in outcomes]
        comparisons += [
            (channel, outcome)
            for channel in ("boundary_distance_mean", "wall_distance_mean")
            for outcome in ("difficulty_nontrivial_rate", "difficulty_seam_rate")
        ]
        for predictor, outcome in comparisons:
            usable = [
                row
                for row in rows
                if row.get(predictor) is not None and row.get(outcome) is not None
            ]
            status = "estimated"
            rho = lower = upper = None
            if len(usable) < 8:
                status = "not_estimated_fewer_than_8_tasks"
            elif len({float(row[outcome]) for row in usable}) < 2:
                status = "not_estimated_constant_outcome"
            else:
                rho, lower, upper = deterministic_building_bootstrap_spearman(
                    usable, predictor, outcome, seed_offset
                )
            out.append(
                {
                    "stage": stage,
                    "condition": condition,
                    "predictor": predictor,
                    "outcome": outcome,
                    "task_count": len(usable),
                    "building_count": len({row["building_id"] for row in usable}),
                    "spearman": rho,
                    "building_bootstrap_ci_lower": lower,
                    "building_bootstrap_ci_upper": upper,
                    "status": status,
                    "interpretation": "post-response descriptive association; not inherent difficulty or causality",
                }
            )
            seed_offset += 1
    return out


def _scope_adjusted_difficulty_sensitivity(
    task_rows: list[dict[str, Any]], replicates: int = 4000
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stage_index, stage in enumerate(("P1", "C1")):
        rows = [
            row
            for row in task_rows
            if row["stage"] == stage
            and row["condition"] == "manual"
            and int(row["strict_valid_support"]) >= 5
        ]
        by_building: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_building[str(row["building_id"])].append(row)
        buildings = sorted(by_building)
        for outcome_index, outcome in enumerate(
            ("difficulty_nontrivial_rate", "difficulty_seam_rate")
        ):
            observed = partial_spearman(
                rows, "mask_distance_mean", outcome, "scope_non_normal_rate"
            )
            rng = np.random.default_rng(SEED + 7000 + stage_index * 100 + outcome_index)
            boot: list[float] = []
            for _ in range(replicates):
                selected = rng.choice(buildings, size=len(buildings), replace=True)
                sample = [row for building in selected for row in by_building[str(building)]]
                value = partial_spearman(
                    sample, "mask_distance_mean", outcome, "scope_non_normal_rate"
                )
                if value is not None and math.isfinite(value):
                    boot.append(value)
            out.append(
                {
                    "stage": stage,
                    "condition": "manual",
                    "predictor": "mask_distance_mean",
                    "outcome": outcome,
                    "control": "scope_non_normal_rate",
                    "task_count": len(rows),
                    "building_count": len(buildings),
                    "partial_spearman": observed,
                    "building_bootstrap_ci_lower": quantile(boot, 0.025),
                    "building_bootstrap_ci_upper": quantile(boot, 0.975),
                    "bootstrap_replicates": len(boot),
                    "interpretation": (
                        "exploratory partial-rank sensitivity; does not solve repeated-worker "
                        "dependence, post-response coupling, or multiplicity"
                    ),
                }
            )
    return out


def _cluster_full_support(
    task_id: str,
    records: list[CanonicalRecord],
    lookup: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    converted = [
        {
            "canonical_annotation_id": record.canonical_id,
            "worker_id": record.raw.worker_id,
            "geometry": record.strict,
        }
        for record in records
    ]
    id_by_geometry = {id(record.strict): record.canonical_id for record in records}

    def pair_fn(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        key = tuple(sorted((id_by_geometry[id(left)], id_by_geometry[id(right)])))
        return lookup[key]

    rows = []
    for threshold in CLUSTER_THRESHOLDS:
        result = cluster_geometry_records(
            converted,
            min_q_boundary=threshold,
            min_q_wallwall=threshold,
            base_task_id=task_id,
            minimum_valid_k=3,
            pairwise_fn=pair_fn,
        )
        largest_share = result.get("largest_cluster_share")
        strong = bool(
            result.get("task_crowd_structure_status") == "supported_multimodal"
            and largest_share is not None
            and float(largest_share) < 0.80
        )
        rows.append(
            {
                "task_cell_id": task_id,
                "threshold": threshold,
                "valid_k": result["valid_k"],
                "partition_status": result["partition_status"],
                "structure_status": result["task_crowd_structure_status"],
                "structure_reason": result["structure_reason"],
                "cluster_count": result["cluster_count"],
                "largest_cluster_support": result["largest_cluster_support"],
                "second_cluster_support": result["second_cluster_support"],
                "largest_cluster_share": largest_share,
                "second_cluster_share": result.get("second_cluster_share"),
                "strong_split": strong,
            }
        )
    return rows


def _dense_rarefaction(
    groups: dict[tuple[str, str, str, str], list[CanonicalRecord]],
    task_rows: list[dict[str, Any]],
    lookups: dict[tuple[str, str, str, str], dict[tuple[str, str], dict[str, Any]]],
    replicates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    row_by_id = {str(row["task_cell_id"]): row for row in task_rows}
    dense = []
    for key, records in sorted(groups.items()):
        stage, condition, _, _ = key
        valid = [record for record in records if record.strict.get("valid")]
        if condition != "manual" or len(valid) < 15 or stage not in {"P1", "C1", "C2-B"}:
            continue
        role = "main_p1_c1_dense42" if stage in {"P1", "C1"} else "c2b_dense_replication4"
        dense.append((key, valid, role))
    main = [item for item in dense if item[2] == "main_p1_c1_dense42"]
    replication = [item for item in dense if item[2] == "c2b_dense_replication4"]
    if len(main) != 42 or len(replication) != 4:
        raise AssertionError(
            f"Dense denominator drift: expected 42 P1/C1 + 4 C2-B, got {len(main)} + {len(replication)}"
        )
    main_full = [float(row_by_id[_cell_id(key)]["mask_distance_mean"]) for key, _, _ in main]
    main_q80 = float(np.quantile(np.asarray(main_full), 0.80))
    main_median = float(np.median(np.asarray(main_full)))
    stage_q80 = {
        stage: float(
            np.quantile(
                [
                    float(row_by_id[_cell_id(key)]["mask_distance_mean"])
                    for key, _, _ in main
                    if key[0] == stage
                ],
                0.80,
            )
        )
        for stage in ("P1", "C1")
    }
    rare_rows: list[dict[str, Any]] = []
    cluster_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []

    for key, records, role in dense:
        task_id = _cell_id(key)
        lookup = lookups[key]
        full_row = row_by_id[task_id]
        full_d = float(full_row["mask_distance_mean"])
        full_counts = Counter(int(record.strict.get("n_pairs", 0)) for record in records)
        ordered_counts = sorted(full_counts.items(), key=lambda item: (-item[1], item[0]))
        full_top1 = ordered_counts[0][0]
        full_top2 = ordered_counts[1][0] if len(ordered_counts) > 1 else None
        seed = SEED ^ int(hashlib.sha256(task_id.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        task_rare: list[dict[str, Any]] = []
        for k in (value for value in KS if value <= len(records)):
            estimates: list[float] = []
            diverse: list[int] = []
            top1_mode_observed: list[int] = []
            top2_covered: list[int] = []
            above_q80: list[int] = []
            above_stage_q80: list[int] = []
            for _ in range(replicates):
                indices = rng.choice(len(records), size=k, replace=False)
                sample = [records[int(index)] for index in indices]
                estimate = subset_distance(sample, lookup, "mask")
                if estimate is None:
                    continue
                estimates.append(estimate)
                sample_counts = Counter(int(record.strict.get("n_pairs", 0)) for record in sample)
                maximum = max(sample_counts.values())
                sample_modes = {count for count, support in sample_counts.items() if support == maximum}
                diverse.append(int(len(sample_counts) > 1))
                top1_mode_observed.append(int(full_top1 in sample_modes))
                top2_covered.append(
                    int(full_top2 is not None and full_top1 in sample_counts and full_top2 in sample_counts)
                )
                above_q80.append(int(estimate >= main_q80))
                if role == "main_p1_c1_dense42":
                    above_stage_q80.append(int(estimate >= stage_q80[key[0]]))
            errors = [abs(value - full_d) for value in estimates]
            row = {
                "task_cell_id": task_id,
                "stage": key[0],
                "condition": key[1],
                "dataset_group": key[2],
                "base_task_id": key[3],
                "dense_role": role,
                "full_valid_support": len(records),
                "k": k,
                "replicates": len(estimates),
                "full_mask_distance": full_d,
                "estimate_mean": float(np.mean(estimates)),
                "estimate_bias": float(np.mean(estimates)) - full_d,
                "estimate_q05": quantile(estimates, 0.05),
                "estimate_q95": quantile(estimates, 0.95),
                "mean_absolute_error": float(np.mean(errors)),
                "probability_abs_error_le_0_02": float(np.mean([error <= 0.02 for error in errors])),
                "probability_abs_error_le_0_03": float(np.mean([error <= 0.03 for error in errors])),
                "probability_abs_error_le_0_05": float(np.mean([error <= 0.05 for error in errors])),
                "full_cardinality_diverse": len(full_counts) > 1,
                "probability_detect_cardinality_diversity": float(np.mean(diverse)),
                "probability_full_top1_is_sample_mode": float(np.mean(top1_mode_observed)),
                "probability_cover_full_top2_cardinalities": (
                    float(np.mean(top2_covered)) if full_top2 is not None else None
                ),
                "main_dense42_mask_q80": main_q80,
                "probability_estimate_above_main_q80": (
                    float(np.mean(above_q80)) if role == "main_p1_c1_dense42" else None
                ),
                "stage_dense_mask_q80": (
                    stage_q80[key[0]] if role == "main_p1_c1_dense42" else None
                ),
                "probability_estimate_above_stage_q80": (
                    float(np.mean(above_stage_q80)) if above_stage_q80 else None
                ),
            }
            task_rare.append(row)
            rare_rows.append(row)

        task_clusters = _cluster_full_support(task_id, records, lookup)
        for row in task_clusters:
            row.update(
                {
                    "stage": key[0],
                    "base_task_id": key[3],
                    "dense_role": role,
                }
            )
        cluster_rows.extend(task_clusters)
        status_counts = Counter(str(row["structure_status"]) for row in task_clusters)
        modal_status, modal_count = status_counts.most_common(1)[0]
        strong_count = sum(bool(row["strong_split"]) for row in task_clusters)
        not_evaluable_count = sum(row["partition_status"] != "unique" for row in task_clusters)
        k_star_003 = first_stable_k(task_rare, "probability_abs_error_le_0_03")
        k15 = next((row for row in task_rare if int(row["k"]) == 15), None)
        roster_high_global = bool(
            role == "main_p1_c1_dense42"
            and full_d >= main_q80
            and full_row.get("mask_loo_min") is not None
            and float(full_row["mask_loo_min"]) >= main_q80
            and k15 is not None
            and float(k15["probability_estimate_above_main_q80"]) >= 0.80
        )
        roster_high_stage = bool(
            role == "main_p1_c1_dense42"
            and full_d >= stage_q80[key[0]]
            and full_row.get("mask_loo_min") is not None
            and float(full_row["mask_loo_min"]) >= stage_q80[key[0]]
            and k15 is not None
            and float(k15["probability_estimate_above_stage_q80"]) >= 0.80
        )
        classification_rows.append(
            {
                "task_cell_id": task_id,
                "stage": key[0],
                "condition": key[1],
                "dataset_group": key[2],
                "base_task_id": key[3],
                "building_id": key[3].split("_", 1)[0],
                "dense_role": role,
                "full_valid_support": len(records),
                "full_mask_distance": full_d,
                "main_dense42_mask_median": main_median,
                "main_dense42_mask_q80": main_q80,
                "full_exceeds_main_dense42_q80": (
                    role == "main_p1_c1_dense42" and full_d >= main_q80
                ),
                "stage_dense_mask_q80": (
                    stage_q80[key[0]] if role == "main_p1_c1_dense42" else None
                ),
                "full_exceeds_stage_dense_q80": (
                    role == "main_p1_c1_dense42" and full_d >= stage_q80[key[0]]
                ),
                "mask_loo_min": full_row.get("mask_loo_min"),
                "mask_loo_max": full_row.get("mask_loo_max"),
                "mask_loo_max_absolute_change": max(
                    abs(float(full_row.get("mask_loo_min") or full_d) - full_d),
                    abs(float(full_row.get("mask_loo_max") or full_d) - full_d),
                ),
                "k_star_mask_eps_0_02": first_stable_k(
                    task_rare, "probability_abs_error_le_0_02"
                ),
                "k_star_mask_eps_0_03": k_star_003,
                "k_star_mask_eps_0_05": first_stable_k(
                    task_rare, "probability_abs_error_le_0_05"
                ),
                "mask_support_readiness": (
                    "early_k_le_5"
                    if k_star_003 is not None and k_star_003 <= 5
                    else "intermediate_k_8_to_12"
                    if k_star_003 is not None and k_star_003 <= 12
                    else "late_k_15_to_20"
                    if k_star_003 is not None
                    else "unresolved_at_observed_k"
                ),
                "vertical_boundary_count_distribution_json": json.dumps(
                    dict(sorted(full_counts.items())), sort_keys=True
                ),
                "vertical_boundary_cardinality_shape": cardinality_shape(full_counts),
                "largest_vertical_boundary_count_share": ordered_counts[0][1] / len(records),
                "top2_vertical_boundary_count_share": sum(
                    count for _, count in ordered_counts[:2]
                )
                / len(records),
                "k_star_detect_cardinality_diversity": (
                    first_stable_k(task_rare, "probability_detect_cardinality_diversity")
                    if len(full_counts) > 1
                    else None
                ),
                "k_star_cover_top2_cardinalities": (
                    first_stable_k(task_rare, "probability_cover_full_top2_cardinalities")
                    if len(full_counts) > 1
                    else None
                ),
                "threshold_modal_cluster_status": modal_status,
                "threshold_modal_status_count_of_5": modal_count,
                "threshold_status_consistency_label": (
                    modal_status if modal_count >= 4 else "threshold_sensitive"
                ),
                "supported_multimodal_count_of_5": sum(
                    row["structure_status"] == "supported_multimodal" for row in task_clusters
                ),
                "strong_split_count_of_5": strong_count,
                "strong_split_at_least_4_of_5": strong_count >= 4,
                "cluster_not_evaluable_count_of_5": not_evaluable_count,
                "roster_high_mask_fixed_global_q80": roster_high_global,
                "roster_high_mask_fixed_stage_q80": roster_high_stage,
                "scope_non_normal_rate": full_row.get("scope_non_normal_rate"),
                "difficulty_nontrivial_rate": full_row.get("difficulty_nontrivial_rate"),
                "difficulty_seam_rate": full_row.get("difficulty_seam_rate"),
            }
        )
    return rare_rows, cluster_rows, classification_rows


def _plot_support(summary_rows: list[dict[str, Any]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    manual = [row for row in summary_rows if row["condition"] == "manual"]
    order = {stage: index for index, stage in enumerate(("P1", "C1", "C2-B", "C2-A-RP-B1", "C2-A-RP-B2"))}
    manual.sort(key=lambda row: order.get(str(row["stage"]), 99))
    labels = [str(row["stage"]) for row in manual]
    fields = (
        ("k0_task_count", "k=0"),
        ("k1_task_count", "k=1"),
        ("k2_4_task_count", "k=2-4"),
        ("k5_7_task_count", "k=5-7"),
        ("k8_14_task_count", "k=8-14"),
        ("k15_plus_task_count", "k>=15"),
    )
    bottom = np.zeros(len(manual))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    for field, label in fields:
        values = np.asarray([int(row[field]) for row in manual])
        ax.bar(labels, values, bottom=bottom, label=label)
        bottom += values
    ax.set_ylabel("Task-image cells")
    ax.set_title("Manual data support strata (stage/batch kept separate)")
    ax.legend(ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_rarefaction(rows: list[dict[str, Any]], path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    main = [row for row in rows if row["dense_role"] == "main_p1_c1_dense42"]
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in main:
        grouped[int(row["k"])].append(row)
    ks = sorted(grouped)
    accurate = [
        float(np.mean([float(row["probability_abs_error_le_0_03"]) for row in grouped[k]]))
        for k in ks
    ]
    detection = [
        float(
            np.mean(
                [
                    float(row["probability_detect_cardinality_diversity"])
                    for row in grouped[k]
                    if row["full_cardinality_diverse"]
                ]
            )
        )
        for k in ks
    ]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    ax.plot(ks, accurate, marker="o", label="P(|D(k)-D(full)| <= 0.03)")
    ax.plot(ks, detection, marker="s", label="Detect >1 boundary cardinality")
    ax.axhline(0.80, color="black", linestyle="--", linewidth=1, label="0.80 criterion")
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Annotators sampled per image (k)")
    ax.set_ylabel("Mean probability across 42 dense images")
    ax.set_title("More labels improve estimation and minority-pattern discovery")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None or value == "":
        return "NA"
    return f"{float(value):.{digits}f}"


def _find_association(
    rows: list[dict[str, Any]], stage: str, predictor: str, outcome: str
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in rows
            if row["stage"] == stage
            and row["condition"] == "manual"
            and row["predictor"] == predictor
            and row["outcome"] == outcome
        ),
        None,
    )


def _task_examples(rows: list[dict[str, Any]], predicate, limit: int = 6) -> str:
    selected = sorted(
        (row for row in rows if predicate(row)),
        key=lambda row: float(row["full_mask_distance"]),
        reverse=True,
    )[:limit]
    if not selected:
        return "- 无任务满足该严格条件。"
    return "\n".join(
        f"- `{row['base_task_id']}`（{row['stage']}，k={row['full_valid_support']}，"
        f"D_mask={_fmt(row['full_mask_distance'])}，k*₀.₀₃={row['k_star_mask_eps_0_03'] or 'NA'}，"
        f"cardinality={row['vertical_boundary_cardinality_shape']}，"
        f"threshold-status={row['threshold_status_consistency_label']}）"
        for row in selected
    )


def _report(
    task_rows: list[dict[str, Any]],
    support_rows: list[dict[str, Any]],
    difficulty_rows: list[dict[str, Any]],
    scope_adjusted_rows: list[dict[str, Any]],
    formal_time_rows: list[dict[str, Any]],
    rare_rows: list[dict[str, Any]],
    classification_rows: list[dict[str, Any]],
    source_summary: dict[str, Any],
) -> str:
    manual = [row for row in task_rows if row["condition"] == "manual"]
    manual_k5 = [row for row in manual if int(row["strict_valid_support"]) >= 5]
    manual_k2_4 = [row for row in manual if 2 <= int(row["strict_valid_support"]) <= 4]
    manual_k1 = [row for row in manual if int(row["strict_valid_support"]) == 1]
    manual_k0 = [row for row in manual if int(row["strict_valid_support"]) == 0]
    p1_general = _find_association(
        difficulty_rows, "P1", "mask_distance_mean", "difficulty_nontrivial_rate"
    )
    p1_seam = _find_association(
        difficulty_rows, "P1", "mask_distance_mean", "difficulty_seam_rate"
    )
    c1_general = _find_association(
        difficulty_rows, "C1", "mask_distance_mean", "difficulty_nontrivial_rate"
    )
    c1_seam = _find_association(
        difficulty_rows, "C1", "mask_distance_mean", "difficulty_seam_rate"
    )
    p1_scope = _find_association(
        difficulty_rows, "P1", "mask_distance_mean", "scope_non_normal_rate"
    )
    c1_scope = _find_association(
        difficulty_rows, "C1", "mask_distance_mean", "scope_non_normal_rate"
    )

    def adjusted(stage: str, outcome: str) -> dict[str, Any]:
        return next(
            row
            for row in scope_adjusted_rows
            if row["stage"] == stage and row["outcome"] == outcome
        )

    p1_general_adjusted = adjusted("P1", "difficulty_nontrivial_rate")
    p1_seam_adjusted = adjusted("P1", "difficulty_seam_rate")
    c1_general_adjusted = adjusted("C1", "difficulty_nontrivial_rate")
    c1_seam_adjusted = adjusted("C1", "difficulty_seam_rate")
    time = next(
        row
        for row in formal_time_rows
        if row["analysis_level"] == "task" and row["outcome"] == "active_time_median"
    )
    worker_time = next(
        row for row in formal_time_rows if row["analysis_level"] == "worker-task"
    )
    main_rare = [row for row in rare_rows if row["dense_role"] == "main_p1_c1_dense42"]
    rare_by_k: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in main_rare:
        rare_by_k[int(row["k"])].append(row)

    def rare_mean(k: int, field: str, diverse_only: bool = False) -> float:
        rows = rare_by_k[k]
        if diverse_only:
            rows = [row for row in rows if row["full_cardinality_diverse"]]
        return float(np.mean([float(row[field]) for row in rows]))

    main_classes = [
        row for row in classification_rows if row["dense_role"] == "main_p1_c1_dense42"
    ]
    def readiness_counts(field: str) -> Counter[str]:
        counts: Counter[str] = Counter()
        for row in main_classes:
            value = row[field]
            label = (
                "early"
                if value is not None and int(value) <= 5
                else "intermediate"
                if value is not None and int(value) <= 12
                else "late"
                if value is not None
                else "unresolved"
            )
            counts[label] += 1
        return counts

    readiness_002 = readiness_counts("k_star_mask_eps_0_02")
    readiness_003 = readiness_counts("k_star_mask_eps_0_03")
    readiness_005 = readiness_counts("k_star_mask_eps_0_05")
    shapes = Counter(row["vertical_boundary_cardinality_shape"] for row in main_classes)
    repeated_strong_split = sum(row["strong_split_at_least_4_of_5"] for row in main_classes)
    threshold_sensitive = sum(
        row["threshold_status_consistency_label"] == "threshold_sensitive"
        for row in main_classes
    )
    global_high_candidates = [
        row for row in main_classes if row["roster_high_mask_fixed_global_q80"]
    ]
    stage_high_candidates = [
        row for row in main_classes if row["roster_high_mask_fixed_stage_q80"]
    ]
    global_scope = [float(row["scope_non_normal_rate"]) for row in global_high_candidates]
    top_mask = sorted(main_classes, key=lambda row: float(row["full_mask_distance"]), reverse=True)[:10]

    def mask_summary(rows: list[dict[str, Any]]) -> tuple[int, float, float, float]:
        values = np.asarray(
            [float(row["mask_distance_mean"]) for row in rows if row["mask_distance_mean"] != ""],
            dtype=float,
        )
        q1, median, q3 = np.quantile(values, (0.25, 0.5, 0.75))
        return len(values), float(q1), float(median), float(q3)

    k5_n, k5_q1, k5_median, k5_q3 = mask_summary(manual_k5)
    small_n, small_q1, small_median, small_q3 = mask_summary(manual_k2_4)
    stage_mask_summaries = {
        stage: mask_summary([row for row in manual_k5 if row["stage_parent"] == stage])
        for stage in ("P1", "C1", "C2-B")
    }
    manual_selected = sum(int(row["selected_support"]) for row in manual)
    manual_valid = sum(int(row["strict_valid_support"]) for row in manual)
    manual_invalid = sum(int(row["strict_invalid_support"]) for row in manual)
    top_mask_lines = "\n".join(
        f"- `{row['base_task_id']}`：D_mask={_fmt(row['full_mask_distance'])}，"
        f"LOO范围={_fmt(row['mask_loo_min'])}–{_fmt(row['mask_loo_max'])}，"
        f"k*₀.₀₃={row['k_star_mask_eps_0_03'] or 'NA'}，"
        f"{row['vertical_boundary_cardinality_shape']}，"
        f"threshold-status={row['threshold_status_consistency_label']}"
        for row in top_mask
    )
    source_lines = "\n".join(
        f"- `{item['path']}` — {item['annotation_record_count']} annotation versions, SHA256 `{item['sha256'][:12]}…`"
        for item in source_summary["raw_sources"]
    )
    return f"""# RQ1 分层标注不确定性分析（探索性草稿）

生成日期：2026-08-27  
状态：**探索性、非规范、供导师讨论**。本分析不改写现行 P1/C1/C2/T1/V1 合同，也不把历史 eligibility 当作本研究的新排除规则；仅保留去重、批次、条件、可计算性和来源审计。

## 核心裁决

1. **现有数据足以先写出一个有证据的 RQ1 草稿，但证据强度必须分层。** Manual 共有 {len(manual)} 个“批次×图片”单元、{len({row['base_task_id'] for row in manual})} 张唯一图片、{len({row['building_id'] for row in manual})} 栋 building。{len(manual_k5)} 个单元达到 `k≥5`，其中 46 个达到 `k≥15`；不是只有 42 张能用。
2. **42 张 P1/C1 高密度图仍是标注人数校准主层。** C2-B 另有 4 个 `k=19–20` 的共同任务，可作独立批次复核，不能无条件与 42 张混成同一总体。
3. **增加人数主要改善当前历史有效标注 roster 的均值估计和稀有 cardinality 检出，不表示标注者“随着人数增加而收敛”。** `D_mask` 是同图两两距离均值的 U-statistic；随机抽取 k 人时其期望近似不随 k 系统改变，变化的是估计误差和类别检出率。
4. **当前只能讨论标注后的困难线索与行为负担，不能称为客观图像难度。** 未校正关联在 P1/C1 间不同，但 scope 分歧与 `D_mask` 本身高度相关；控制 scope 后，困难和 seam 关联均明显减弱，所以不能把 seam 写成已证实的独立机制。
5. **现有数据能筛出有限 roster 下的高输出差异候选，但尚未证明稳定的 1–2 个几何模式或多个正确答案。** cluster 目前只做阈值状态诊断，没有验证同一分区、成员或原型随人数稳定。

## 1. 数据分层，而不是只看高密度图

| 层级 | Manual 单元数 | 当前能回答什么 |
|---|---:|---|
| `k≥5` | {len(manual_k5)} | 任务级连续分歧分布；按阶段做困难/时间关联；不能把不同批次当 iid |
| `k=2–4` | {len(manual_k2_4)} | 有限的成对/小样本描述，可进入分层敏感性；不宜给单图稳定模式定性 |
| `k=1` | {len(manual_k1)} | 不提供同图人际分歧，只能提供有效性、元标签、时长等单标注结局 |
| `k=0` | {len(manual_k0)} | 不可评估几何分歧，必须显式保留而非填成最大分歧 |

`D_mask=1−wall-region mask IoU`，0 表示两份输出完全一致，值越大表示空间范围差异越大。在 `k≥5` 层，{k5_n} 个 Manual 单元的中位数为 {_fmt(k5_median)}（IQR {_fmt(k5_q1)}–{_fmt(k5_q3)}）；按阶段分别为 P1（n={stage_mask_summaries['P1'][0]}）{_fmt(stage_mask_summaries['P1'][2])}（{_fmt(stage_mask_summaries['P1'][1])}–{_fmt(stage_mask_summaries['P1'][3])}）、C1（n={stage_mask_summaries['C1'][0]}）{_fmt(stage_mask_summaries['C1'][2])}（{_fmt(stage_mask_summaries['C1'][1])}–{_fmt(stage_mask_summaries['C1'][3])}）、C2-B（n={stage_mask_summaries['C2-B'][0]}）{_fmt(stage_mask_summaries['C2-B'][2])}（{_fmt(stage_mask_summaries['C2-B'][1])}–{_fmt(stage_mask_summaries['C2-B'][3])}）。`k=2–4` 的 {small_n} 个单元中位数为 {_fmt(small_median)}（{_fmt(small_q1)}–{_fmt(small_q3)}），但任务构成与估计噪声均不同，不能把它与高支持层的差值解释成“人数增加导致分歧变大”。

上述 k 是**计算几何有效支持数**，不是提交人数。{manual_selected} 个 Manual selected annotations 中，{manual_valid} 个进入计算几何、{manual_invalid} 个进入 invalid lane（{_fmt(manual_invalid / manual_selected * 100, 1)}%）。`k≥5=118` 使用 C1 amendment calculation repair；若所有阶段统一按 raw-computable 或 strict-normalized 口径，分别为 117 和 116。46 个 `k≥15` 不受该口径变化影响。困难关联与 rarefaction 都是 conditional-valid 结果，invalid 可能相关所造成的选择偏差尚未消除。

Manual 的 218 个单元对应 187 张唯一图片，原因是 C2-B 与 C2-A-RP、以及两个 RP block 中存在同图重复。分析单位始终是 `base image × stage/batch × condition`；同图跨批次可做重复测量，但不是新的独立图片。

P1 另有 18 个 Semi 与 9 个 OOS 高密度单元，C1 有 25 个 Semi 单元。它们全部保留在表中，但 RQ1 的自然人际分歧主分析只使用 Manual；Semi 是 RQ2 的观察性桥接层，因为共享模型初值可能同时降低方差并引入共同偏差。

详见 `support_strata_summary.csv`、`task_cell_metrics.csv` 和 `manual_support_strata.png`。

## 2. 不确定性与困难度

历史界面**没有统一 1–5 主观难度分数**；只有 `trivial` 或遮挡、低纹理、拼接缝、反射、低画质等多选原因。因此下列结果是 post-response perceived-difficulty 关联，不是图像固有难度，也不是因果效应；本版本没有 pre-task、image-only 的客观难度指标。

### P1 Manual（30 个高密度任务，12 栋 building）

- `D_mask` vs 非平凡困难标签率：Spearman ρ={_fmt(p1_general and p1_general['spearman'])}，building bootstrap 95% CI [{_fmt(p1_general and p1_general['building_bootstrap_ci_lower'])}, {_fmt(p1_general and p1_general['building_bootstrap_ci_upper'])}]。
- `D_mask` vs seam 标签率：ρ={_fmt(p1_seam and p1_seam['spearman'])}，95% CI [{_fmt(p1_seam and p1_seam['building_bootstrap_ci_lower'])}, {_fmt(p1_seam and p1_seam['building_bootstrap_ci_upper'])}]。
- `D_mask` vs scope 非 normal 率：ρ={_fmt(p1_scope and p1_scope['spearman'])}，95% CI [{_fmt(p1_scope and p1_scope['building_bootstrap_ci_lower'])}, {_fmt(p1_scope and p1_scope['building_bootstrap_ci_upper'])}]。

### C1 Manual（84 个 `k≥5` 任务，13 栋 building）

- `D_mask` vs 非平凡困难标签率：ρ={_fmt(c1_general and c1_general['spearman'])}，95% CI [{_fmt(c1_general and c1_general['building_bootstrap_ci_lower'])}, {_fmt(c1_general and c1_general['building_bootstrap_ci_upper'])}]，没有稳定关联证据。
- `D_mask` vs seam 标签率：ρ={_fmt(c1_seam and c1_seam['spearman'])}，95% CI [{_fmt(c1_seam and c1_seam['building_bootstrap_ci_lower'])}, {_fmt(c1_seam and c1_seam['building_bootstrap_ci_upper'])}]。
- `D_mask` vs scope 非 normal 率：ρ={_fmt(c1_scope and c1_scope['spearman'])}，95% CI [{_fmt(c1_scope and c1_scope['building_bootstrap_ci_lower'])}, {_fmt(c1_scope and c1_scope['building_bootstrap_ci_upper'])}]。
- `D_mask` vs 每图 median formal active time：ρ={_fmt(time['spearman'])}，95% CI [{_fmt(time['building_bootstrap_ci_lower'])}, {_fmt(time['building_bootstrap_ci_upper'])}]。
- worker 固定效应后，排除本人几何的 LOO 分歧与 `log1p(active time)` 的组内相关为 {_fmt(worker_time['within_group_pearson'])}（594 个 worker-task，22 人）。

scope-adjusted partial-rank 敏感性进一步显示：P1 的非平凡困难/ seam 关联降至 {_fmt(p1_general_adjusted['partial_spearman'])} [{_fmt(p1_general_adjusted['building_bootstrap_ci_lower'])}, {_fmt(p1_general_adjusted['building_bootstrap_ci_upper'])}] / {_fmt(p1_seam_adjusted['partial_spearman'])} [{_fmt(p1_seam_adjusted['building_bootstrap_ci_lower'])}, {_fmt(p1_seam_adjusted['building_bootstrap_ci_upper'])}]；C1 为 {_fmt(c1_general_adjusted['partial_spearman'])} [{_fmt(c1_general_adjusted['building_bootstrap_ci_lower'])}, {_fmt(c1_general_adjusted['building_bootstrap_ci_upper'])}] / {_fmt(c1_seam_adjusted['partial_spearman'])} [{_fmt(c1_seam_adjusted['building_bootstrap_ci_lower'])}, {_fmt(c1_seam_adjusted['building_bootstrap_ci_upper'])}]。这仍不能处理重复 worker、post-response 共因或多重比较，只能说明 raw seam 关联有明显 scope 混杂。boundary/wall 指标方向一致也只是同源几何度量的敏感性，不是独立复现。

因此不能写成“越难就越不一致”或“seam 已被证实为机制”。更准确的草稿是：**标注者报告的困难、scope 判断和几何输出差异共同变化；scope 是当前最强的描述性伴随量，耗时仅呈弱到中等关联。**所有标签比较均未做 multiplicity 调整，阶段差异也未做正式 interaction test。

本次还修正了旧 C1 difficulty parser：原实现没有识别原始 vocabulary 中带下划线的 `low_texture`/`low_quality`，导致旧表中 C1 nontrivial ρ=0.017；修正后为 {_fmt(c1_general and c1_general['spearman'])}。旧值由本报告 supersede，几何分歧本身未改变。

## 3. 人数增加后，哪些东西稳定

在 42 张 P1/C1 高密度图上，从每图当前 23–26 个 strict-valid 历史 roster 中，对 `k={{3,5,8,10,12,15,20}}` 做 {source_summary['rarefaction_replicates']} 次无放回随机子样本。目标是恢复包含该子样本的**有限历史有效 roster** 的 full-sample 值；它不外推到新 worker population，也不包含 invalid 风险。以下两个目标必须分开：

- **估准平均连续分歧**：k=5 时，平均 `P(|D(k)-D(full)|≤0.03)` 为 {_fmt(rare_mean(5, 'probability_abs_error_le_0_03'))}；k=8 为 {_fmt(rare_mean(8, 'probability_abs_error_le_0_03'))}；k=15 为 {_fmt(rare_mean(15, 'probability_abs_error_le_0_03'))}。
- **发现 full support 中存在的多个垂直边界数量**：在 full 确有多种 cardinality 的任务中，k=5 的平均检出率为 {_fmt(rare_mean(5, 'probability_detect_cardinality_diversity', True))}，k=8 为 {_fmt(rare_mean(8, 'probability_detect_cardinality_diversity', True))}，k=15 为 {_fmt(rare_mean(15, 'probability_detect_cardinality_diversity', True))}，k=20 为 {_fmt(rare_mean(20, 'probability_detect_cardinality_diversity', True))}。

所以，“5 个人够不够”没有一个单一答案：对这个有限 roster 的平均连续分歧做粗略估计，k=5 已经有信息；对稀有 cardinality 检出，k=5 明显偏薄。这里没有检验完整几何模式的恢复。

以 `P(|D(k)-D(full)|≤ε)≥0.80` 且以后各**预设网格节点**均满足为操作性标准，结果高度依赖 ε：

| ε | early `k*≤5` | intermediate `8–12` | late `15–20` | unresolved |
|---:|---:|---:|---:|---:|
| 0.02 | {readiness_002['early']} | {readiness_002['intermediate']} | {readiness_002['late']} | {readiness_002['unresolved']} |
| 0.03 | {readiness_003['early']} | {readiness_003['intermediate']} | {readiness_003['late']} | {readiness_003['unresolved']} |
| 0.05 | {readiness_005['early']} | {readiness_005['intermediate']} | {readiness_005['late']} | {readiness_005['unresolved']} |

因此 early/late 是 tolerance-conditional 标签，不是图片固有类别；0.03 只是便于阅读的中间容差，并非规范阈值。1000 次 Monte Carlo 在 p≈0.80 时的二项标准误约 0.013，临界任务应视为 borderline。

## 4. “几个人可估准”“看到两种 count”“高差异候选”如何落到真实图片

### 4.1 几个人就够

这里的“够”仅表示在 ε=0.03 下估准有限 roster 的 `D_mask`，不表示恢复完整模式：

{_task_examples(main_classes, lambda row: row['mask_support_readiness'] == 'early_k_le_5')}

### 4.2 较大 k 才较常覆盖 full roster 中频数前两种 cardinality

该计算只要求 full roster 中频数前两种垂直边界 count 在子样本里各出现至少一次；第二种可能仅来自 1 人，既不保证它是“主要类别”，也不保证它在子样本中成为 mode：

{_task_examples(main_classes, lambda row: row['k_star_cover_top2_cardinalities'] is not None and int(row['k_star_cover_top2_cardinalities']) >= 8)}

full-roster cardinality 形状计数为：`concentrated` {shapes.get('cardinality_concentrated', 0)}、`dominant+dissent` {shapes.get('dominant_with_cardinality_dissent', 0)}、`two dominant` {shapes.get('two_dominant_cardinalities', 0)}、`diffuse` {shapes.get('diffuse_cardinality', 0)}。只有 {shapes.get('two_dominant_cardinalities', 0)}/42 在 count 层满足当前 two-dominant 规则；这里的 cardinality 只是垂直边界数量，**不是完整拓扑签名或几何模式**。

### 4.3 当前 roster 下的固定阈值高分歧筛查

全局筛查固定使用 42 张 full-roster `D_mask` 的 q80 cutoff：full 值、任意单 worker leave-one-out 值均超过该固定 cutoff，且 k=15 子样本估计至少 80% 超过同一 cutoff。它不是每次重抽后重新排名 top 20%。满足者 {len(global_high_candidates)} 张，全部来自 P1，scope 非 normal 率为 {_fmt(min(global_scope) * 100, 1)}%–{_fmt(max(global_scope) * 100, 1)}%：

{_task_examples(main_classes, lambda row: row['roster_high_mask_fixed_global_q80'])}

这首先提示全局 cutoff 受 stage/scope 混杂。改用 P1、C1 各自的固定 q80 后，满足相同 LOO 与 k=15 条件者共 {len(stage_high_candidates)} 张（P1 {sum(row['stage'] == 'P1' for row in stage_high_candidates)}，C1 {sum(row['stage'] == 'C1' for row in stage_high_candidates)}）：

{_task_examples(main_classes, lambda row: row['roster_high_mask_fixed_stage_q80'])}

这些只能称为“当前历史有效 roster 下对固定相对阈值不敏感的高输出差异候选”。不能外推为“无论增加多少人都不会收敛”，也不能把 scope 分歧自动解释为场景多解。

连续分歧最高的 10 个主层任务如下，便于下一步盲审：

{top_mask_lines}

### 4.4 operational cluster 仅作阈值状态诊断

完整支持下，用 boundary/wall 阈值 `.90/.925/.95/.97/.98` 做 complete-link operational clustering：{repeated_strong_split}/42 张在至少 4/5 个阈值下都被标为 strong split；{threshold_sensitive}/42 张连状态名称都未在 4/5 阈值下一致。该计数没有比较同一 partition、cluster membership 或 medoid，也没有做 worker 子样本稳定性；即使状态名称重复，也不能称为稳健 cluster/mode。阈值升高还会增加 `not_evaluable`，任何单一阈值的“多峰率”都不能当作真实多解 prevalence。

cluster 结果必须与连续 `D_mask`、cardinality、scope 分歧分轴阅读。尤其是 `scope_non_normal_rate` 较高的候选，可能是协议适用性分歧，不一定是两个同样合理的布局。

## 5. 可用于论文的 RQ1 草稿

> **RQ1：在曼哈顿全景布局标注协议下，独立标注输出在连续几何、垂直边界数量与可计算性方面呈现多大、何种形式的差异；这些差异的估计随每图标注者支持数增加如何稳定，并与标注者报告的困难线索及行为负担有何关联？**

建议主术语使用 **inter-annotator output variability / operational annotation reproducibility**。在没有专家确认多个模式都与图像证据相容前，不用 ground-truth uncertainty 或 multiple correct layouts。

### 方法段草稿

我们将分析单元定义为 `base image × stage/batch × condition`，同一 worker 在单元内保留分析器所选的最新未取消版本。历史 formal eligibility 不作为新的探索性排除规则；几何不可计算记录独立计数，不赋为最大距离。连续主指标为同图 calculation-valid 标注之间 `1 − wall-region mask IoU` 的平均值，并以 boundary 与 vertical-wall-event 距离作同源敏感性；结构轴仅统计垂直边界 cardinality，不将角点数误称为完整拓扑。所有总体汇总按图片单元而非 pair 加权。对高密度 P1/C1 子集从有限有效 roster 随机无放回 rarefaction，估计不同 k 下连续分歧误差与 cardinality 检出概率。困难标签与 active time 仅作 post-response 描述性关联，并按 building bootstrap；scope-adjusted partial rank 只作混杂敏感性。

### 结果段草稿

现有 Manual 数据覆盖 218 个批次内图片单元，其中按当前 C1 repair/calculation 口径有 118 个达到 `k≥5`，46 个达到 `k≥15`；`k≥5` 层 `D_mask` 中位数为 {_fmt(k5_median)}（IQR {_fmt(k5_q1)}–{_fmt(k5_q3)}）。高密度有限-roster 重抽样表明，较少标注者可粗略估计平均连续分歧，但稀有 cardinality 检出需要更高支持，且 k* 对容差选择敏感。困难与 seam 的 raw 关联受到 scope 明显混杂；active time 仅呈弱到中等关联。固定阈值筛查能找到对单人 LOO 和 k=15 子样本较不敏感的高差异候选，但 cluster 尚未验证相同几何分区或模式稳定，故候选只能进入盲法专家审查，不能视为已经证明的多个合理真值。

## 6. 与 Semi / 曼哈顿约束的边界

Semi 的模型初始 proposal 被强制满足曼哈顿结构，但仍可能偏离真实墙角。这里必须按 residual 的参照对象拆开：对 Manhattan/墙体内部约束的 residual 下降，只说明 **constraint compliance / internal geometric consistency** 改善；只有相对独立 reference 或图像边界证据的误差下降，才说明 **evidence fit** 改善。不能把二者统称“墙残差下降”。

1. constraint compliance：输出是否满足曼哈顿/结构规则；
2. evidence fit：输出是否贴合图像墙角或独立参考；
3. inter-annotator variability：不同人的输出有多散。

共享预标注可能降低第 3 轴，同时通过共同偏差损害第 2 轴。因此 RQ2 不能只比较方差；必须先冻结 residual 的数学定义，再同时报告 proposal 正误、constraint residual、独立 evidence-fit error，以及 Manual/Semi 输出分歧。

## 7. 仍不能声称什么

- 不能由有限的 23–26 人证明“无限增加人数仍然分歧”。
- 不能把 `C(k,2)` 个 pair 当作独立样本量。
- 不能把垂直边界数量差异叫完整拓扑差异。
- 不能把旧 difficulty 原因映射成不存在的 1–5 难度分数。
- 不能由 42 张高密度图估计所有 187 张图片或总体房型的歧义 prevalence。
- 不能把 cluster 自动解释为多个合理答案；需要盲法视觉审查。
- 不能把 Semi 修正前后坐标变化本身解释为视觉质量提升；至少需要独立图像证据或参考 residual。
- 不能把 finite-roster rarefaction 当成新标注者总体的样本量保证；重复 worker 与 invalid selection 仍需后续敏感性分析。
- 不能把未经 multiplicity 调整的 difficulty/tag 关联或未检验的阶段差值当作确认性结果。

## 8. 文献定位与创新性

多评者分歧并非新主题；创新性应落在结构化 360° 曼哈顿布局、高密度独立重复标注、支持数校准，以及连续几何/cardinality/可计算性的多层分解。外部研究也显示所需评者数依任务和 estimand 而变，没有可直接套用的“每图必须 15 人”：

- Wang et al., TACL 2023：主观 STS 中高一致样本和争议样本的稳定人数不同，不能迁移成布局几何通用阈值。https://aclanthology.org/2023.tacl-1.56/
- CrowdTruth：多个任务的稳定点不同，开放任务在较高支持下仍可能未稳。https://journals.sagepub.com/doi/10.3233/SW-200415
- Berkeley Segmentation：同图多个人工分割被用于评价与人际一致性分析，其评价度量允许不同粒度的分割结果。https://vision.ics.uci.edu/papers/MartinFTM_ICCV_2001/
- QUBIQ：其任务说明强调不确定性的操作定义依任务和数据而定；公开赛道实际使用 3–7 名专家标注，但这只是设计事实，不是最优人数证明。https://qubiq.grand-challenge.org/About/ ；https://qubiq.grand-challenge.org/Participation/
- Pavlick & Kwiatkowski：有些语言任务分歧在增加评者和上下文后仍持续。https://aclanthology.org/Q19-1043/
- Jiang & de Marneffe：分歧可来自输入歧义、指南欠规定与标注者行为，不能只归因于场景本身。https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00523/114372/Investigating-Reasons-for-Disagreement-in-Natural

不依赖“文献中从未做过”这一难以由有限检索证明的表述，当前可直接由本研究设计支撑的候选增量是：

> 面向结构化 360° 曼哈顿布局，本研究利用高密度独立重复标注进行任务内支持数校准，并联合描述连续几何、垂直边界 cardinality 与可计算性三层输出差异。

## 9. 原始数据审计

本次直接重读 18 个 Label Studio 原始导出，而不是只读整理表：

{source_lines}

原始版本数 {source_summary['raw_annotation_version_count']}；按 `stage/project/runtime task/worker` 取最新未取消版本后 {source_summary['selected_annotation_count']}。该数量与中性整理底座 `annotation_spine.csv` 的 {source_summary['organized_crosscheck']['annotation_spine_rows']} 行一致，但逐 acquisition key 比较只有 {source_summary['organized_crosscheck']['annotation_identity_match_count']}/{source_summary['selected_annotation_count']} 个 annotation identity 相同。唯一差异是 C1 project 66 / task 3192 / worker 34：分析器按时间选 6053，正式 spine 选 6052；两版本 result content 完全相同，因此本次几何与 difficulty 数值不变，但它是 provenance gap，不能写成 canonical 身份完全一致。

整理底座仅用于覆盖/身份交叉核验，没有被提升为本次几何重算的输入真源。P1/C1 的整理层与原始重算已有既有审计；C2-B 作为历史证据保留，C2-A-RP 已 terminal closeout。`SOURCE_AND_METHOD_SUMMARY.json` 记录生成器及直接依赖脚本 SHA、dirty worktree 状态、seed 和参数；所有生成表的 SHA 写入 `OUTPUT_MANIFEST.csv`。
"""


def _write_manifest(output_dir: Path) -> None:
    rows = []
    for path in sorted(output_dir.iterdir()):
        if path.is_file() and path.name != "OUTPUT_MANIFEST.csv":
            rows.append(
                {
                    "path": (
                        path.relative_to(ROOT).as_posix()
                        if path.is_relative_to(ROOT)
                        else path.as_posix()
                    ),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_rows(output_dir / "OUTPUT_MANIFEST.csv", rows)


def run(output_dir: Path = DEFAULT_OUT, replicates: int = 1000) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = load_raw(ALL_SOURCE_FILES)
    selected, selection_summary = select_latest_non_cancelled(raw)
    if len(raw) != 2513 or len(selected) != 2501:
        raise AssertionError(
            f"Raw/canonical denominator drift: expected 2513/2501, got {len(raw)}/{len(selected)}"
        )
    _, calculation_records, repair_rows = build_variants(selected)
    groups = group_records(calculation_records)
    task_rows, metric_rows, lookups = _task_tables(groups)
    support_rows = _support_summary(task_rows)
    difficulty_rows = _difficulty_associations(task_rows)
    scope_adjusted_rows = _scope_adjusted_difficulty_sensitivity(task_rows)
    _, formal_time_rows, formal_time_summary = formal_time_difficulty_analysis(
        groups, metric_rows, lookups
    )
    rare_rows, cluster_rows, classification_rows = _dense_rarefaction(
        groups, task_rows, lookups, replicates
    )
    source_rows = []
    raw_by_source = Counter(record.source_file for record in raw)
    for _, _, _, relative in ALL_SOURCE_FILES:
        source_rows.append(
            {
                "path": relative,
                "sha256": sha256_file(ROOT / relative),
                "annotation_record_count": raw_by_source[relative],
            }
        )
    substrate = ROOT / "analysis_results" / "uncertainty_substrate_20260823_v1"
    annotation_spine = substrate / "annotation_spine.csv"
    with annotation_spine.open("r", encoding="utf-8-sig") as handle:
        spine_rows = list(csv.DictReader(handle))
    annotation_spine_rows = len(spine_rows)
    if annotation_spine_rows != len(selected):
        raise AssertionError(
            f"Raw/canonical cross-check drift: selected={len(selected)}, spine={annotation_spine_rows}"
        )
    spine_by_key = {
        (row["raw_project_id"], row["raw_runtime_task_id"], row["raw_worker_id"]): row
        for row in spine_rows
    }
    raw_by_annotation = {
        (row.project_id, row.runtime_task_id, row.worker_id, row.annotation_id): row
        for row in raw
    }
    identity_mismatches = []
    for row in selected:
        key = (row.project_id, row.runtime_task_id, row.worker_id)
        spine_row = spine_by_key[key]
        if row.annotation_id == spine_row["raw_annotation_id"]:
            continue
        canonical_raw = raw_by_annotation[
            (row.project_id, row.runtime_task_id, row.worker_id, spine_row["raw_annotation_id"])
        ]
        identity_mismatches.append(
            {
                "stage": row.stage,
                "project_id": row.project_id,
                "runtime_task_id": row.runtime_task_id,
                "worker_id": row.worker_id,
                "analyzer_annotation_id": row.annotation_id,
                "spine_annotation_id": spine_row["raw_annotation_id"],
                "result_content_equal": (
                    row.keypoints == canonical_raw.keypoints
                    and row.width == canonical_raw.width
                    and row.height == canonical_raw.height
                    and row.choices_json == canonical_raw.choices_json
                ),
            }
        )
    organized_crosscheck = {
        "annotation_spine_path": annotation_spine.relative_to(ROOT).as_posix(),
        "annotation_spine_sha256": sha256_file(annotation_spine),
        "annotation_spine_rows": annotation_spine_rows,
        "annotation_identity_match_count": len(selected) - len(identity_mismatches),
        "annotation_identity_mismatch_count": len(identity_mismatches),
        "annotation_identity_mismatches": identity_mismatches,
        "qa_summary_path": (substrate / "QA_SUMMARY.json").relative_to(ROOT).as_posix(),
        "qa_summary_sha256": sha256_file(substrate / "QA_SUMMARY.json"),
        "role": "identity and coverage cross-check only; not geometry metric input",
    }
    code_paths = (
        Path(__file__).resolve(),
        ROOT / "tools/thesis_main/analysis/raw_rq1_recompute_20260826.py",
        ROOT / "tools/thesis_main/analysis/raw_difficulty_time_recompute_20260826.py",
        ROOT / "tools/thesis_main/analysis/audit_rq1_corrections_20260826.py",
        ROOT / "tools/thesis_main/analysis/geometry_cluster_v2.py",
    )
    git_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.splitlines()
    source_summary = {
        "source_commit": git_head(),
        "raw_sources": source_rows,
        "raw_annotation_version_count": len(raw),
        "selected_annotation_count": len(selected),
        "selection_summary": selection_summary,
        "organized_crosscheck": organized_crosscheck,
        "c1_repair_status_counts": dict(Counter(row["repair_status"] for row in repair_rows)),
        "rarefaction_replicates": replicates,
        "scope_adjusted_bootstrap_replicates": 4000,
        "formal_c1_time": formal_time_summary,
        "generator_provenance": {
            "git_head": git_head(),
            "git_worktree_dirty": bool(git_status),
            "git_status_short": git_status,
            "code_sha256": {
                path.relative_to(ROOT).as_posix(): sha256_file(path) for path in code_paths
            },
            "seed": SEED,
            "rarefaction_k_grid": list(KS),
            "cluster_thresholds": list(CLUSTER_THRESHOLDS),
        },
        "analysis_contract": {
            "unit": "base_image × stage_or_batch × condition",
            "manual_primary": True,
            "invalid_lane": "separate_not_max_distance",
            "continuous_primary": "mean pairwise (1 - wall-region mask IoU)",
            "cardinality_axis": "vertical boundary count only; not full topology",
            "cluster_role": "threshold sensitivity and candidate triage only",
            "rarefaction_target": "finite historical strict-valid roster full-sample value",
            "support_definition": (
                "calculation-valid geometry; C1 uses amendment calculation repair, other stages strict"
            ),
            "eligibility_role": "historical provenance only; not a new exclusion filter",
            "difficulty_parser": "exact low_texture/low_quality codes recognized; legacy space-separated aliases retained",
        },
    }
    write_rows(output_dir / "task_cell_metrics.csv", task_rows)
    write_rows(output_dir / "support_strata_summary.csv", support_rows)
    write_rows(output_dir / "difficulty_associations.csv", difficulty_rows)
    write_rows(
        output_dir / "difficulty_scope_adjusted_sensitivity.csv", scope_adjusted_rows
    )
    write_rows(output_dir / "formal_c1_time_associations.csv", formal_time_rows)
    write_rows(output_dir / "dense_rarefaction_by_task_k.csv", rare_rows)
    write_rows(output_dir / "dense_full_cluster_thresholds.csv", cluster_rows)
    write_rows(output_dir / "dense_task_classification.csv", classification_rows)
    (output_dir / "SOURCE_AND_METHOD_SUMMARY.json").write_text(
        json.dumps(source_summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    _plot_support(support_rows, output_dir / "manual_support_strata.png")
    _plot_rarefaction(rare_rows, output_dir / "dense_rarefaction_summary.png")
    (output_dir / "RQ1_STRATIFIED_UNCERTAINTY_REPORT_ZH.md").write_text(
        _report(
            task_rows,
            support_rows,
            difficulty_rows,
            scope_adjusted_rows,
            formal_time_rows,
            rare_rows,
            classification_rows,
            source_summary,
        ),
        encoding="utf-8",
    )
    _write_manifest(output_dir)
    summary = {
        "output_dir": (
            output_dir.relative_to(ROOT).as_posix()
            if output_dir.is_relative_to(ROOT)
            else output_dir.as_posix()
        ),
        "manual_task_cells": sum(row["condition"] == "manual" for row in task_rows),
        "manual_unique_images": len(
            {row["base_task_id"] for row in task_rows if row["condition"] == "manual"}
        ),
        "manual_k_ge_5": sum(
            row["condition"] == "manual" and int(row["strict_valid_support"]) >= 5
            for row in task_rows
        ),
        "main_dense_tasks": sum(
            row["dense_role"] == "main_p1_c1_dense42" for row in classification_rows
        ),
        "c2b_dense_replication_tasks": sum(
            row["dense_role"] == "c2b_dense_replication4" for row in classification_rows
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--replicates", type=int, default=1000)
    args = parser.parse_args()
    if args.replicates < 100:
        raise ValueError("replicates must be at least 100")
    run(args.output_dir, args.replicates)


if __name__ == "__main__":
    main()
