from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import (
    normalize_geometry,
    normalize_geometry_for_c1_calculation,
)
from tools.thesis_main.analysis.quality_core.geometry_metrics import (
    compute_layout_mask_iou_from_normalized_pairs,
)
from tools.thesis_main.analysis.raw_difficulty_time_recompute_20260826 import (
    fixed_effect_slope,
    normalise_tags,
)
from tools.thesis_main.analysis.raw_rq1_recompute_20260826 import (
    CanonicalRecord,
    RawRecord,
    choose_latest,
    load_raw,
    quantile,
    spearman,
    write_rows,
)


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results" / "rq1_corrections_20260826"
SEED = 20260826 + 11
CALIBRATION_REPLICATES = 1000
NULL_REPLICATES = 2000
ROSTER_REPLICATES = 1000

P1_FROZEN = (
    ROOT
    / "analysis_results"
    / "prescreen_closeout_final_gold_v2_20260701"
    / "prescreen_canonical_annotations.csv"
)
C1_ROOT = (
    ROOT
    / "analysis_results"
    / "c1_formal_audit_20260802_v16_final"
    / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
)
C1_FROZEN = C1_ROOT / "c1_canonical_annotations.csv"
C1_TIME = C1_ROOT / "c1_task_worker_active_time.csv"
C1_TIME_SUMMARY = C1_ROOT / "c1_task_worker_active_time.summary.json"

CHANNEL_TO_SIMILARITY = {
    "mask": "mask_similarity",
    "boundary": "boundary_similarity",
    "wall": "wallwall_similarity",
}


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def truth(value: Any) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "y", "eligible", "valid"}


def select_latest_non_cancelled(raw: list[RawRecord]) -> tuple[list[RawRecord], dict[str, Any]]:
    all_keys = {row.acquisition_key for row in raw}
    non_cancelled = [row for row in raw if not row.was_cancelled]
    groups: dict[tuple[str, str, str, str], list[RawRecord]] = defaultdict(list)
    for row in non_cancelled:
        groups[row.acquisition_key].append(row)
    selected = [choose_latest(versions) for _, versions in sorted(groups.items())]
    summary = {
        "raw_versions_all": len(raw),
        "raw_versions_cancelled": sum(row.was_cancelled for row in raw),
        "raw_versions_non_cancelled": len(non_cancelled),
        "acquisition_keys_all": len(all_keys),
        "acquisition_keys_with_non_cancelled_version": len(groups),
        "cancelled_only_acquisition_keys": len(all_keys - set(groups)),
        "selected_latest_non_cancelled": len(selected),
        "duplicate_version_excess_non_cancelled": len(non_cancelled) - len(groups),
    }
    return selected, summary


def frozen_selection_map() -> dict[tuple[str, str, str, str], dict[str, str]]:
    result: dict[tuple[str, str, str, str], dict[str, str]] = {}
    with P1_FROZEN.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = ("P1", row["project_id"], row["task_id"], row["annotator_id"])
            result[key] = {
                "annotation_id": row["annotation_id"],
                "canonical_annotation_id": row.get("canonical_annotation_id", ""),
                "source": P1_FROZEN.relative_to(ROOT).as_posix(),
            }
    with C1_FROZEN.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = ("C1", row["project_id"], row["ls_runtime_task_id"], row["worker_id"])
            result[key] = {
                "annotation_id": row["annotation_id"],
                "canonical_annotation_id": row.get("canonical_annotation_id", ""),
                "source": C1_FROZEN.relative_to(ROOT).as_posix(),
            }
    return result


def build_variants(selected: list[RawRecord]) -> tuple[list[CanonicalRecord], list[CanonicalRecord], list[dict[str, Any]]]:
    raw_records: list[CanonicalRecord] = []
    calculation_records: list[CanonicalRecord] = []
    repair_rows: list[dict[str, Any]] = []
    for row in selected:
        raw_geometry = normalize_geometry(list(row.keypoints), width=row.width, height=row.height)
        calculation_geometry = (
            normalize_geometry_for_c1_calculation(list(row.keypoints), width=row.width, height=row.height)
            if row.stage == "C1"
            else raw_geometry
        )
        raw_records.append(CanonicalRecord(row, raw_geometry))
        calculation_records.append(CanonicalRecord(row, calculation_geometry))
        if row.stage == "C1":
            repair_rows.append(
                {
                    "project_id": row.project_id,
                    "runtime_task_id": row.runtime_task_id,
                    "base_task_id": row.base_task_id,
                    "condition": row.condition,
                    "dataset_group": row.dataset_group,
                    "worker_id": row.worker_id,
                    "annotation_id": row.annotation_id,
                    "raw_point_count": len(row.keypoints),
                    "raw_valid": bool(raw_geometry.get("valid")),
                    "raw_reason": raw_geometry.get("reason", ""),
                    "calculation_valid": bool(calculation_geometry.get("valid")),
                    "calculation_reason": calculation_geometry.get("reason", ""),
                    "repair_applied": bool(calculation_geometry.get("geometry_repair_applied")),
                    "repair_status": calculation_geometry.get("geometry_repair_status", ""),
                    "dropped_point_index": calculation_geometry.get("dropped_point_index"),
                    "orphan_candidate_count": calculation_geometry.get("orphan_candidate_count"),
                }
            )
    return raw_records, calculation_records, repair_rows


def group_records(records: list[CanonicalRecord]) -> dict[tuple[str, str, str, str], list[CanonicalRecord]]:
    groups: dict[tuple[str, str, str, str], list[CanonicalRecord]] = defaultdict(list)
    for item in records:
        row = item.raw
        groups[(row.stage, row.condition, row.dataset_group, row.base_task_id)].append(item)
    return groups


def task_pairwise_metrics(
    key: tuple[str, str, str, str], records: list[CanonicalRecord]
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    valid = [row for row in records if row.strict.get("valid")]
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    values: dict[str, list[float]] = {channel: [] for channel in CHANNEL_TO_SIMILARITY}
    count_disagreement: list[int] = []
    for left, right in combinations(valid, 2):
        item = dict(pairwise_similarity(left.strict, right.strict))
        mask_iou, mask_meta = compute_layout_mask_iou_from_normalized_pairs(
            left.strict.get("pairs") or [],
            right.strict.get("pairs") or [],
            width=int(left.strict.get("width", 1024)),
            height=int(left.strict.get("height", 512)),
        )
        item["mask_similarity"] = mask_iou
        item["mask_reason"] = mask_meta.get("reason", "")
        pair_key = tuple(sorted((left.canonical_id, right.canonical_id)))
        lookup[pair_key] = item
        for channel, field in CHANNEL_TO_SIMILARITY.items():
            if item.get(field) is not None:
                values[channel].append(1.0 - float(item[field]))
        count_disagreement.append(
            int(int(left.strict.get("n_pairs", 0)) != int(right.strict.get("n_pairs", 0)))
        )
    stage, condition, dataset_group, base = key
    all_pairs = math.comb(len(records), 2) if len(records) >= 2 else 0
    result: dict[str, Any] = {
        "stage": stage,
        "condition": condition,
        "dataset_group": dataset_group,
        "base_task_id": base,
        "selected_support": len(records),
        "strict_valid_support": len(valid),
        "strict_invalid_support": len(records) - len(valid),
        "all_selected_pair_count": all_pairs,
        "strict_pair_count": math.comb(len(valid), 2) if len(valid) >= 2 else 0,
        "vertical_boundary_count_disagreement": (
            float(np.mean(count_disagreement)) if count_disagreement else None
        ),
        "strict_boundary_count_diverse": len({int(row.strict.get("n_pairs", 0)) for row in valid}) > 1,
    }
    for channel in CHANNEL_TO_SIMILARITY:
        channel_values = values[channel]
        result[f"{channel}_metric_pair_count"] = len(channel_values)
        result[f"{channel}_pair_coverage_over_all_selected"] = (
            len(channel_values) / all_pairs if all_pairs else None
        )
        result[f"{channel}_distance_mean"] = (
            float(np.mean(channel_values)) if channel_values else None
        )
        result[f"{channel}_distance_median"] = (
            float(np.median(channel_values)) if channel_values else None
        )
        result[f"{channel}_distance_q90"] = quantile(channel_values, 0.90)
    return result, lookup


def subset_distance(
    sample: list[CanonicalRecord],
    lookup: dict[tuple[str, str], dict[str, Any]],
    channel: str,
) -> float | None:
    field = CHANNEL_TO_SIMILARITY[channel]
    distances: list[float] = []
    for left, right in combinations(sample, 2):
        item = lookup.get(tuple(sorted((left.canonical_id, right.canonical_id))))
        if item is not None and item.get(field) is not None:
            distances.append(1.0 - float(item[field]))
    return float(np.mean(distances)) if distances else None


def distribution_summary(values: list[float], prefix: str) -> dict[str, Any]:
    usable = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return {
        f"{prefix}_mean": float(np.mean(usable)) if usable else None,
        f"{prefix}_median": float(np.median(usable)) if usable else None,
        f"{prefix}_q05": quantile(usable, 0.05),
        f"{prefix}_q95": quantile(usable, 0.95),
    }


def support_calibration(
    high_density: dict[str, list[CanonicalRecord]],
    lookups: dict[str, dict[tuple[str, str], dict[str, Any]]],
    full_values: dict[str, dict[str, float]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(SEED)
    summary_rows: list[dict[str, Any]] = []
    count_rows: list[dict[str, Any]] = []
    full_diverse = {
        task_id: len({int(row.strict.get("n_pairs", 0)) for row in records}) > 1
        for task_id, records in high_density.items()
    }
    for k in (2, 3, 5, 8, 10, 15, 20):
        eligible = [task_id for task_id, records in high_density.items() if len(records) >= k]
        per_channel: dict[str, dict[str, list[float]]] = {
            channel: {"mae": [], "rmse": [], "spearman": [], "top20_recall": []}
            for channel in CHANNEL_TO_SIMILARITY
        }
        hits: Counter[str] = Counter()
        trials: Counter[str] = Counter()
        for _ in range(CALIBRATION_REPLICATES):
            sampled: dict[str, dict[str, float]] = {
                channel: {} for channel in CHANNEL_TO_SIMILARITY
            }
            for task_id in eligible:
                records = high_density[task_id]
                indices = rng.choice(len(records), size=k, replace=False)
                sample = [records[int(index)] for index in indices]
                for channel in CHANNEL_TO_SIMILARITY:
                    value = subset_distance(sample, lookups[task_id], channel)
                    if value is not None:
                        sampled[channel][task_id] = value
                trials[task_id] += 1
                if len({int(row.strict.get("n_pairs", 0)) for row in sample}) > 1:
                    hits[task_id] += 1
            for channel in CHANNEL_TO_SIMILARITY:
                common = [
                    task_id
                    for task_id in eligible
                    if task_id in sampled[channel] and channel in full_values[task_id]
                ]
                estimate = np.asarray([sampled[channel][task_id] for task_id in common], dtype=float)
                target = np.asarray([full_values[task_id][channel] for task_id in common], dtype=float)
                error = estimate - target
                top_n = max(1, math.ceil(0.20 * len(common)))
                target_top = set(np.argsort(target)[-top_n:])
                estimate_top = set(np.argsort(estimate)[-top_n:])
                per_channel[channel]["mae"].append(float(np.mean(np.abs(error))))
                per_channel[channel]["rmse"].append(float(np.sqrt(np.mean(np.square(error)))))
                correlation = spearman(estimate, target)
                if correlation is not None:
                    per_channel[channel]["spearman"].append(correlation)
                per_channel[channel]["top20_recall"].append(len(target_top & estimate_top) / top_n)
        for channel in CHANNEL_TO_SIMILARITY:
            row: dict[str, Any] = {
                "channel": channel,
                "k": k,
                "replicates": CALIBRATION_REPLICATES,
                "task_count": len(eligible),
            }
            for metric, metric_values in per_channel[channel].items():
                row.update(distribution_summary(metric_values, metric))
            summary_rows.append(row)
        diverse_ids = [task_id for task_id in eligible if full_diverse[task_id]]
        count_rows.append(
            {
                "k": k,
                "eligible_task_count": len(eligible),
                "full_count_diverse_task_count": len(diverse_ids),
                "mean_detection_probability_all_tasks": float(
                    np.mean([hits[task_id] / trials[task_id] for task_id in eligible])
                ),
                "mean_detection_probability_given_full_diverse": (
                    float(np.mean([hits[task_id] / trials[task_id] for task_id in diverse_ids]))
                    if diverse_ids
                    else None
                ),
            }
        )
    return summary_rows, count_rows


def cluster_threshold_summary(
    high_density: dict[str, list[CanonicalRecord]],
    lookups: dict[str, dict[tuple[str, str], dict[str, Any]]],
) -> list[dict[str, Any]]:
    task_rows: list[dict[str, Any]] = []
    for threshold in (0.90, 0.925, 0.95, 0.97, 0.98):
        for task_id, records in sorted(high_density.items()):
            converted = [
                {
                    "canonical_annotation_id": row.canonical_id,
                    "worker_id": row.raw.worker_id,
                    "geometry": row.strict,
                }
                for row in records
            ]
            id_by_geometry = {id(row.strict): row.canonical_id for row in records}

            def pair_fn(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
                key = tuple(sorted((id_by_geometry[id(left)], id_by_geometry[id(right)])))
                return lookups[task_id][key]

            result = cluster_geometry_records(
                converted,
                min_q_boundary=threshold,
                min_q_wallwall=threshold,
                base_task_id=task_id,
                minimum_valid_k=3,
                pairwise_fn=pair_fn,
            )
            task_rows.append(
                {
                    "task_id": task_id,
                    "stage": task_id.split("|", 1)[0],
                    "threshold": threshold,
                    "valid_k": result["valid_k"],
                    "partition_status": result["partition_status"],
                    "structure_status": result["task_crowd_structure_status"],
                }
            )
    summary_rows: list[dict[str, Any]] = []
    for threshold in sorted({row["threshold"] for row in task_rows}):
        for stage in ("ALL", "P1", "C1"):
            subset = [
                row
                for row in task_rows
                if row["threshold"] == threshold and (stage == "ALL" or row["stage"] == stage)
            ]
            counts = Counter(row["structure_status"] for row in subset)
            summary_rows.append(
                {
                    "threshold": threshold,
                    "stage": stage,
                    "task_count": len(subset),
                    "unimodal": counts["unimodal"],
                    "dominant_with_dissent": counts["dominant_with_dissent"],
                    "supported_multimodal": counts["supported_multimodal"],
                    "not_evaluable": counts["not_evaluable"],
                    "supported_multimodal_rate": counts["supported_multimodal"] / len(subset),
                    "not_evaluable_rate": counts["not_evaluable"] / len(subset),
                }
            )
    return summary_rows


def roster20_sensitivity(
    c1_anchor: dict[str, list[CanonicalRecord]],
    lookups: dict[str, dict[tuple[str, str], dict[str, Any]]],
    full_values: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    common_workers = set.intersection(
        *[{row.raw.worker_id for row in records} for records in c1_anchor.values()]
    )
    if len(common_workers) < 20:
        raise AssertionError(f"C1 anchor common worker support is only {len(common_workers)}")
    workers = sorted(common_workers, key=lambda value: int(value) if value.isdigit() else value)
    rng = np.random.default_rng(SEED + 1)
    results = {
        channel: {
            "roster20_mae": [],
            "roster20_spearman": [],
            "roster20_k5_mae": [],
            "roster20_k5_spearman": [],
        }
        for channel in CHANNEL_TO_SIMILARITY
    }
    task_ids = sorted(c1_anchor)
    for _ in range(ROSTER_REPLICATES):
        roster = set(rng.choice(workers, size=20, replace=False).tolist())
        roster_values = {channel: [] for channel in CHANNEL_TO_SIMILARITY}
        k5_values = {channel: [] for channel in CHANNEL_TO_SIMILARITY}
        targets = {channel: [] for channel in CHANNEL_TO_SIMILARITY}
        for task_id in task_ids:
            records = [row for row in c1_anchor[task_id] if row.raw.worker_id in roster]
            sample_indices = rng.choice(len(records), size=5, replace=False)
            sample = [records[int(index)] for index in sample_indices]
            for channel in CHANNEL_TO_SIMILARITY:
                roster_value = subset_distance(records, lookups[task_id], channel)
                k5_value = subset_distance(sample, lookups[task_id], channel)
                target = full_values[task_id][channel]
                roster_values[channel].append(roster_value)
                k5_values[channel].append(k5_value)
                targets[channel].append(target)
        for channel in CHANNEL_TO_SIMILARITY:
            target = np.asarray(targets[channel], dtype=float)
            roster_array = np.asarray(roster_values[channel], dtype=float)
            k5_array = np.asarray(k5_values[channel], dtype=float)
            results[channel]["roster20_mae"].append(float(np.mean(np.abs(roster_array - target))))
            results[channel]["roster20_k5_mae"].append(float(np.mean(np.abs(k5_array - target))))
            rho = spearman(roster_array, target)
            rho_k5 = spearman(k5_array, target)
            if rho is not None:
                results[channel]["roster20_spearman"].append(rho)
            if rho_k5 is not None:
                results[channel]["roster20_k5_spearman"].append(rho_k5)
    rows: list[dict[str, Any]] = []
    for channel, metrics in results.items():
        row: dict[str, Any] = {
            "channel": channel,
            "common_worker_count": len(workers),
            "roster_size": 20,
            "within_roster_arm_k": 5,
            "task_count": len(task_ids),
            "replicates": ROSTER_REPLICATES,
        }
        for metric, values in metrics.items():
            row.update(distribution_summary(values, metric))
        rows.append(row)
    return rows


def null_replay(
    high_density: dict[str, list[CanonicalRecord]],
    lookups: dict[str, dict[tuple[str, str], dict[str, Any]]],
) -> list[dict[str, Any]]:
    rng = np.random.default_rng(SEED + 2)
    contrasts = ("C_minus_M", "W_minus_M", "W_minus_C")
    replicate_store = {
        channel: {contrast: {"means": [], "image_sds": []} for contrast in contrasts}
        for channel in CHANNEL_TO_SIMILARITY
    }
    for _ in range(NULL_REPLICATES):
        by_channel = {
            channel: {contrast: [] for contrast in contrasts}
            for channel in CHANNEL_TO_SIMILARITY
        }
        for task_id, records in sorted(high_density.items()):
            indices = rng.permutation(len(records))[:15]
            arms = {
                "M": [records[int(index)] for index in indices[:5]],
                "C": [records[int(index)] for index in indices[5:10]],
                "W": [records[int(index)] for index in indices[10:15]],
            }
            for channel in CHANNEL_TO_SIMILARITY:
                d = {
                    arm: subset_distance(sample, lookups[task_id], channel)
                    for arm, sample in arms.items()
                }
                values = {
                    "C_minus_M": d["C"] - d["M"],
                    "W_minus_M": d["W"] - d["M"],
                    "W_minus_C": d["W"] - d["C"],
                }
                for contrast, value in values.items():
                    by_channel[channel][contrast].append(float(value))
        for channel in CHANNEL_TO_SIMILARITY:
            for contrast in contrasts:
                values = np.asarray(by_channel[channel][contrast], dtype=float)
                replicate_store[channel][contrast]["means"].append(float(np.mean(values)))
                replicate_store[channel][contrast]["image_sds"].append(float(np.std(values, ddof=1)))
    zsum = 1.959963984540054 + 0.8416212335729143
    rows: list[dict[str, Any]] = []
    for channel in CHANNEL_TO_SIMILARITY:
        for contrast in contrasts:
            means = replicate_store[channel][contrast]["means"]
            image_sds = replicate_store[channel][contrast]["image_sds"]
            median_sd = float(np.median(image_sds))
            for n_images in (42, 60, 72, 80):
                projected_se = median_sd / math.sqrt(n_images)
                rows.append(
                    {
                        "channel": channel,
                        "contrast": contrast,
                        "source_task_count": len(high_density),
                        "projected_image_count": n_images,
                        "replicates": NULL_REPLICATES,
                        "mean_null_contrast": float(np.mean(means)),
                        "fixed_source_empirical_se": float(np.std(means, ddof=1)),
                        "median_image_contrast_sd": median_sd,
                        "image_contrast_sd_q05": quantile(image_sds, 0.05),
                        "image_contrast_sd_q95": quantile(image_sds, 0.95),
                        "projected_se_sampling_only": projected_se,
                        "conditional_80pct_mde_sampling_only": zsum * projected_se,
                        "interpretation": (
                            "lower bound under zero treatment effect; excludes treatment heterogeneity, "
                            "building correlation, worker superpopulation, invalid outcomes, and new-stimulus shift"
                        ),
                    }
                )
    return rows


def deterministic_building_bootstrap_spearman(
    rows: list[dict[str, Any]], predictor: str, outcome: str, seed_offset: int
) -> tuple[float | None, float | None, float | None]:
    usable = [row for row in rows if row.get(predictor) is not None and row.get(outcome) is not None]
    if len(usable) < 5:
        return None, None, None
    observed = spearman(
        np.asarray([float(row[predictor]) for row in usable]),
        np.asarray([float(row[outcome]) for row in usable]),
    )
    by_building: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usable:
        by_building[str(row["building_id"])].append(row)
    buildings = sorted(by_building)
    if len(buildings) < 3:
        return observed, None, None
    rng = np.random.default_rng(SEED + 100 + seed_offset)
    values: list[float] = []
    for _ in range(4000):
        selected = rng.choice(buildings, size=len(buildings), replace=True)
        sample = [row for building in selected for row in by_building[str(building)]]
        rho = spearman(
            np.asarray([float(row[predictor]) for row in sample]),
            np.asarray([float(row[outcome]) for row in sample]),
        )
        if rho is not None and math.isfinite(rho):
            values.append(rho)
    return observed, quantile(values, 0.025), quantile(values, 0.975)


def formal_time_difficulty_analysis(
    groups: dict[tuple[str, str, str, str], list[CanonicalRecord]],
    task_rows: dict[tuple[str, str, str, str], dict[str, Any]],
    lookups: dict[tuple[str, str, str, str], dict[tuple[str, str], dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    summary = json.loads(C1_TIME_SUMMARY.read_text(encoding="utf-8"))
    actual_sha = sha256_file(C1_TIME)
    if summary.get("output_sha256") != actual_sha:
        raise AssertionError("C1 active-time table SHA does not match frozen summary")
    with C1_TIME.open("r", encoding="utf-8-sig", newline="") as handle:
        time_rows = list(csv.DictReader(handle))
    time_map = {
        (row["project_id"], row["runtime_task_id"], row["worker_id"]): row
        for row in time_rows
    }
    if len(time_rows) != 780 or len(time_map) != 780:
        raise AssertionError("C1 active-time context count/key drift")

    response_rows: list[dict[str, Any]] = []
    aggregated_rows: list[dict[str, Any]] = []
    for key, records in sorted(groups.items()):
        stage, condition, dataset_group, base = key
        if stage != "C1" or condition != "manual" or dataset_group not in {"C1_anchor_all", "C1_core_all"}:
            continue
        valid = [row for row in records if row.strict.get("valid")]
        if len(valid) < 5:
            continue
        lookup = lookups[key]
        task_d = task_rows[key].get("mask_distance_mean")
        per_task: list[dict[str, Any]] = []
        for item in valid:
            peers = [row for row in valid if row.canonical_id != item.canonical_id]
            loo_d = subset_distance(peers, lookup, "mask") if len(peers) >= 4 else None
            raw = item.raw
            time = time_map.get((raw.project_id, raw.runtime_task_id, raw.worker_id))
            eligible = bool(
                time
                and truth(time.get("formal_assignment_eligible"))
                and truth(time.get("task_worker_time_analysis_eligible"))
                and str(time.get("task_worker_active_seconds") or "").strip()
            )
            active_seconds = float(time["task_worker_active_seconds"]) if eligible else None
            tags, raw_tags = normalise_tags(raw.choices_json)
            row = {
                "dataset_group": dataset_group,
                "base_task_id": base,
                "building_id": base.split("_", 1)[0],
                "project_id": raw.project_id,
                "runtime_task_id": raw.runtime_task_id,
                "worker_id": raw.worker_id,
                "annotation_id": raw.annotation_id,
                "strict_valid_support": len(valid),
                "task_mask_dispersion": task_d,
                "leave_one_worker_out_mask_dispersion": loo_d,
                "active_time_seconds": active_seconds,
                "log1p_active_time": math.log1p(active_seconds) if active_seconds is not None else None,
                "active_time_status": time.get("timing_status", "missing") if time else "missing",
                "formal_assignment_eligible": truth(time.get("formal_assignment_eligible")) if time else False,
                "task_worker_time_analysis_eligible": truth(time.get("task_worker_time_analysis_eligible")) if time else False,
                "difficulty_tags_json": json.dumps(tags),
                "difficulty_raw_values_json": json.dumps(raw_tags, ensure_ascii=False),
                "difficulty_trivial": int("trivial" in tags),
                "difficulty_nontrivial": int(any(tag != "trivial" for tag in tags)),
                "difficulty_nontrivial_tag_count": sum(tag != "trivial" for tag in tags),
                "difficulty_occlusion": int("occlusion" in tags),
                "difficulty_seam": int("seam" in tags),
            }
            response_rows.append(row)
            per_task.append(row)
        times = [row["active_time_seconds"] for row in per_task if row["active_time_seconds"] is not None]
        aggregated_rows.append(
            {
                "dataset_group": dataset_group,
                "base_task_id": base,
                "building_id": base.split("_", 1)[0],
                "strict_valid_support": len(valid),
                "task_mask_dispersion": task_d,
                "active_time_observed_count": len(times),
                "active_time_median": float(np.median(times)) if times else None,
                "active_time_mean": float(np.mean(times)) if times else None,
                "difficulty_response_count": len(per_task),
                "difficulty_nontrivial_rate": float(np.mean([row["difficulty_nontrivial"] for row in per_task])),
                "difficulty_occlusion_rate": float(np.mean([row["difficulty_occlusion"] for row in per_task])),
                "difficulty_seam_rate": float(np.mean([row["difficulty_seam"] for row in per_task])),
                "difficulty_nontrivial_tag_count_mean": float(
                    np.mean([row["difficulty_nontrivial_tag_count"] for row in per_task])
                ),
            }
        )

    association_rows: list[dict[str, Any]] = []
    for index, outcome in enumerate(
        (
            "active_time_median",
            "difficulty_nontrivial_rate",
            "difficulty_occlusion_rate",
            "difficulty_seam_rate",
            "difficulty_nontrivial_tag_count_mean",
        )
    ):
        observed, lower, upper = deterministic_building_bootstrap_spearman(
            aggregated_rows, "task_mask_dispersion", outcome, index
        )
        usable = [row for row in aggregated_rows if row.get(outcome) is not None]
        association_rows.append(
            {
                "analysis_level": "task",
                "predictor": "task_mask_dispersion",
                "outcome": outcome,
                "row_count": len(usable),
                "building_count": len({row["building_id"] for row in usable}),
                "spearman": observed,
                "building_bootstrap_ci_lower": lower,
                "building_bootstrap_ci_upper": upper,
                "interpretation": "descriptive; difficulty is post-response and active time is not randomized",
            }
        )

    time_response = [
        row
        for row in response_rows
        if row["leave_one_worker_out_mask_dispersion"] is not None and row["log1p_active_time"] is not None
    ]
    if time_response:
        x = np.asarray([float(row["leave_one_worker_out_mask_dispersion"]) for row in time_response])
        y = np.asarray([float(row["log1p_active_time"]) for row in time_response])
        workers = [row["worker_id"] for row in time_response]
        association_rows.append(
            {
                "analysis_level": "worker-task",
                "predictor": "leave_one_worker_out_mask_dispersion",
                "outcome": "log1p_active_time",
                "row_count": len(time_response),
                "worker_count": len(set(workers)),
                "building_count": len({row["building_id"] for row in time_response}),
                "raw_spearman": spearman(x, y),
                **fixed_effect_slope(x, y, workers),
                "interpretation": "worker-fixed descriptive association; focal geometry excluded from predictor",
            }
        )

    audit_summary = {
        "active_time_table_sha256": actual_sha,
        "active_time_summary_sha256_expected": summary["output_sha256"],
        "active_time_context_count": len(time_rows),
        "active_time_eligible_context_count_frozen": summary.get("eligible_context_count"),
        "manual_tasks_k_ge5": len(aggregated_rows),
        "manual_worker_task_rows": len(response_rows),
        "active_time_observed_rows": sum(row["active_time_seconds"] is not None for row in response_rows),
        "active_time_observed_tasks": sum(row["active_time_observed_count"] > 0 for row in aggregated_rows),
    }
    return response_rows, association_rows, audit_summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw_all = load_raw()
    selected, selection_summary = select_latest_non_cancelled(raw_all)
    raw_records, calculation_records, repair_rows = build_variants(selected)

    frozen = frozen_selection_map()
    selection_comparison: list[dict[str, Any]] = []
    for row in selected:
        authority = frozen.get(row.acquisition_key)
        selection_comparison.append(
            {
                "stage": row.stage,
                "project_id": row.project_id,
                "runtime_task_id": row.runtime_task_id,
                "worker_id": row.worker_id,
                "latest_non_cancelled_annotation_id": row.annotation_id,
                "frozen_annotation_id": authority.get("annotation_id", "") if authority else "",
                "frozen_canonical_annotation_id": authority.get("canonical_annotation_id", "") if authority else "",
                "comparison_status": (
                    "match"
                    if authority and authority.get("annotation_id") == row.annotation_id
                    else "mismatch"
                    if authority
                    else "missing_frozen_authority"
                ),
            }
        )

    raw_groups = group_records(raw_records)
    calculation_groups = group_records(calculation_records)
    raw_task_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    calculation_task_rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    calculation_lookups: dict[
        tuple[str, str, str, str], dict[tuple[str, str], dict[str, Any]]
    ] = {}
    for key, records in sorted(raw_groups.items()):
        raw_task_rows[key] = task_pairwise_metrics(key, records)[0]
    for key, records in sorted(calculation_groups.items()):
        task_row, lookup = task_pairwise_metrics(key, records)
        calculation_task_rows[key] = task_row
        calculation_lookups[key] = lookup

    support_comparison_rows: list[dict[str, Any]] = []
    for key in sorted(set(raw_task_rows) | set(calculation_task_rows)):
        raw_row = raw_task_rows[key]
        calculation_row = calculation_task_rows[key]
        support_comparison_rows.append(
            {
                "stage": key[0],
                "condition": key[1],
                "dataset_group": key[2],
                "base_task_id": key[3],
                "raw_strict_valid_support": raw_row["strict_valid_support"],
                "amendment_calculation_valid_support": calculation_row["strict_valid_support"],
                "support_delta": calculation_row["strict_valid_support"] - raw_row["strict_valid_support"],
                "raw_mask_distance_mean": raw_row.get("mask_distance_mean"),
                "calculation_mask_distance_mean": calculation_row.get("mask_distance_mean"),
                "raw_boundary_distance_mean": raw_row.get("boundary_distance_mean"),
                "calculation_boundary_distance_mean": calculation_row.get("boundary_distance_mean"),
            }
        )

    high_density: dict[str, list[CanonicalRecord]] = {}
    high_lookups: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    full_values: dict[str, dict[str, float]] = {}
    c1_anchor: dict[str, list[CanonicalRecord]] = {}
    for key, records in sorted(calculation_groups.items()):
        stage, condition, dataset_group, base = key
        high = (
            stage == "P1" and condition == "manual" and dataset_group == "PreScreen_manual"
        ) or (
            stage == "C1" and condition == "manual" and dataset_group == "C1_anchor_all"
        )
        if not high:
            continue
        valid = [row for row in records if row.strict.get("valid")]
        task_id = f"{stage}|{dataset_group}|{base}"
        high_density[task_id] = valid
        high_lookups[task_id] = calculation_lookups[key]
        task_row = calculation_task_rows[key]
        full_values[task_id] = {
            channel: float(task_row[f"{channel}_distance_mean"])
            for channel in CHANNEL_TO_SIMILARITY
            if task_row.get(f"{channel}_distance_mean") is not None
        }
        if stage == "C1":
            c1_anchor[task_id] = valid

    calibration_rows, count_rows = support_calibration(high_density, high_lookups, full_values)
    cluster_rows = cluster_threshold_summary(high_density, high_lookups)
    roster_rows = roster20_sensitivity(c1_anchor, high_lookups, full_values)
    null_rows = null_replay(high_density, high_lookups)
    worker_time_rows, time_associations, time_summary = formal_time_difficulty_analysis(
        calculation_groups, calculation_task_rows, calculation_lookups
    )

    c1_core_raw = [
        row
        for key, row in raw_task_rows.items()
        if key[0] == "C1" and key[1] == "manual" and key[2] == "C1_core_all"
    ]
    c1_core_calculation = [
        row
        for key, row in calculation_task_rows.items()
        if key[0] == "C1" and key[1] == "manual" and key[2] == "C1_core_all"
    ]
    selection_counts = Counter(row["comparison_status"] for row in selection_comparison)
    repair_counts = Counter(row["repair_status"] for row in repair_rows)

    summary = {
        "source_commit": git_head(),
        "selection": selection_summary,
        "frozen_selection_comparison": dict(selection_counts),
        "c1_repair_status_counts": dict(repair_counts),
        "c1_repair_applied_count": sum(row["repair_applied"] for row in repair_rows),
        "c1_core_unique_task_count": len(c1_core_calculation),
        "c1_core_raw_strict_k_distribution": dict(
            sorted(Counter(int(row["strict_valid_support"]) for row in c1_core_raw).items())
        ),
        "c1_core_amendment_k_distribution": dict(
            sorted(Counter(int(row["strict_valid_support"]) for row in c1_core_calculation).items())
        ),
        "c1_core_raw_strict_k_ge5": sum(int(row["strict_valid_support"]) >= 5 for row in c1_core_raw),
        "c1_core_amendment_k_ge5": sum(
            int(row["strict_valid_support"]) >= 5 for row in c1_core_calculation
        ),
        "high_density_task_count": len(high_density),
        "high_density_min_amendment_support": min(len(records) for records in high_density.values()),
        "high_density_max_amendment_support": max(len(records) for records in high_density.values()),
        "metric_contract": {
            "mask": "1 - IoU of the periodic panorama wall-region band between ceiling and floor boundaries",
            "boundary": "1 - mean periodic ceiling/floor boundary similarity",
            "wall": "1 - symmetric circular Chamfer similarity of vertical wall-event x positions",
        },
        "formal_active_time": time_summary,
        "cautions": [
            "The wall-region mask distance is a candidate overall image-plane layout distance, not a frozen Primary metric.",
            "Cardinality/topology disagreement remains a separate axis because mask IoU can be high for different event counts.",
            "The 20-of-23 replay samples random historical rosters and does not substitute for the final named Main roster.",
            "Null replay MDE values are sampling-noise lower bounds, not power guarantees.",
            "Difficulty responses are post-response appraisals and cannot define inherent task difficulty causally.",
        ],
    }

    write_rows(OUT / "frozen_selection_comparison.csv", selection_comparison)
    write_rows(OUT / "c1_geometry_repair_audit.csv", repair_rows)
    write_rows(OUT / "raw_vs_amendment_task_support.csv", support_comparison_rows)
    write_rows(OUT / "support_calibration_summary.csv", calibration_rows)
    write_rows(OUT / "boundary_count_detection_summary.csv", count_rows)
    write_rows(OUT / "cluster_threshold_count_summary.csv", cluster_rows)
    write_rows(OUT / "c1_anchor_roster20_sensitivity.csv", roster_rows)
    write_rows(OUT / "null_replay_sample_size_scenarios.csv", null_rows)
    write_rows(OUT / "formal_time_worker_task_rows.csv", worker_time_rows)
    write_rows(OUT / "formal_time_difficulty_associations.csv", time_associations)
    (OUT / "SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
