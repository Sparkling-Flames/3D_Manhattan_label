from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Callable

import numpy as np

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results" / "rq1_raw_recompute_20260826"
SEED = 20260826

SOURCE_FILES: tuple[tuple[str, str, str, str], ...] = (
    ("P1", "manual", "PreScreen_manual", "export_label/stage1_English/project-39-at-2026-06-28-05-14-65ca3316.json"),
    ("P1", "manual", "PreScreen_manual", "export_label/stage1_chinese/project-28-at-2026-07-01-07-14-56a198ba.json"),
    ("P1", "semi", "PreScreen_semi", "export_label/stage1_English/project-40-at-2026-06-28-05-14-bb74a057.json"),
    ("P1", "semi", "PreScreen_semi", "export_label/stage1_chinese/project-29-at-2026-06-30-09-00-e7ea6931.json"),
    ("P1", "oos", "PreScreen_oos", "export_label/stage1_English/project-41-at-2026-06-28-05-13-8641854f.json"),
    ("P1", "oos", "PreScreen_oos", "export_label/stage1_chinese/project-30-at-2026-06-30-09-00-69d8051b.json"),
    ("C1", "manual", "C1_anchor_all", "export_label/stage2_English/project-66-at-2026-07-30-13-01-cdb9fe80.json"),
    ("C1", "manual", "C1_anchor_all", "export_label/stage2_Chinese/project-69-at-2026-07-30-13-02-cb472115.json"),
    ("C1", "manual", "C1_core_all", "export_label/stage2_English/project-67-at-2026-07-30-13-01-f5126135.json"),
    ("C1", "manual", "C1_core_all", "export_label/stage2_Chinese/project-71-at-2026-07-30-14-18-54a73158.json"),
    ("C1", "semi", "C1_semi", "export_label/stage2_English/project-68-at-2026-07-30-13-02-cf7d8306.json"),
    ("C1", "semi", "C1_semi", "export_label/stage2_Chinese/project-72-at-2026-07-30-13-02-f69c5ac4.json"),
)


@dataclass(frozen=True)
class RawRecord:
    stage: str
    condition: str
    dataset_group: str
    source_file: str
    project_id: str
    runtime_task_id: str
    base_task_id: str
    image_id: str
    worker_id: str
    annotation_id: str
    annotation_unique_id: str
    created_at: str
    updated_at: str
    was_cancelled: bool
    keypoints: tuple[tuple[float, float], ...]
    width: int
    height: int
    choices_json: str

    @property
    def acquisition_key(self) -> tuple[str, str, str, str]:
        return self.stage, self.project_id, self.runtime_task_id, self.worker_id


@dataclass
class CanonicalRecord:
    raw: RawRecord
    strict: dict[str, Any]

    @property
    def canonical_id(self) -> str:
        r = self.raw
        return f"{r.stage}|{r.project_id}|{r.runtime_task_id}|{r.worker_id}|{r.annotation_id}"


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return scalar(value.get("id", value.get("pk", value.get("email", ""))))
    return str(value).strip()


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def base_id(data: dict[str, Any]) -> str:
    for key in ("base_task_id", "image_id", "planned_task_id", "task_id"):
        value = scalar(data.get(key))
        if value:
            if key in {"planned_task_id", "task_id"} and "__" in value:
                value = value.split("__", 1)[0]
            return value
    image = scalar(data.get("image")).split("?", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
    return Path(image).stem


def extract_annotation(annotation: dict[str, Any]) -> tuple[tuple[tuple[float, float], ...], int, int, str]:
    points: list[tuple[float, float]] = []
    choices: dict[str, list[str]] = defaultdict(list)
    width = 1024
    height = 512
    for row in annotation.get("result") or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "")
        value = row.get("value") or {}
        width = int(row.get("original_width") or width)
        height = int(row.get("original_height") or height)
        if kind in {"keypointlabels", "keypointregion"}:
            x = value.get("x")
            y = value.get("y")
            if x is None or y is None:
                continue
            points.append((float(x) * width / 100.0, float(y) * height / 100.0))
        elif kind in {"choices", "labels", "taxonomy"}:
            selected = value.get("choices") or value.get("labels") or value.get("taxonomy") or []
            if not isinstance(selected, list):
                selected = [selected]
            field = str(row.get("from_name") or row.get("id") or kind)
            choices[field].extend(str(item) for item in selected if item not in (None, ""))
    return tuple(points), width, height, json.dumps(dict(choices), ensure_ascii=False, sort_keys=True)


def load_raw(
    source_files: tuple[tuple[str, str, str, str], ...] = SOURCE_FILES,
) -> list[RawRecord]:
    out: list[RawRecord] = []
    for stage, fallback_condition, fallback_group, relative in source_files:
        path = ROOT / relative
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, list):
            raise TypeError(f"Expected Label Studio list: {relative}")
        for task in payload:
            if not isinstance(task, dict):
                continue
            data = task.get("data") or {}
            if not isinstance(data, dict):
                data = {}
            task_id = scalar(task.get("id"))
            base = base_id(data)
            condition = scalar(data.get("condition")).lower() or fallback_condition
            group = scalar(data.get("dataset_group")) or fallback_group
            image_id = scalar(data.get("image_id")) or base
            project_task = scalar(task.get("project"))
            annotations = task.get("annotations") or []
            if not isinstance(annotations, list):
                continue
            for ann in annotations:
                if not isinstance(ann, dict):
                    continue
                points, width, height, choices_json = extract_annotation(ann)
                out.append(
                    RawRecord(
                        stage=stage,
                        condition=condition,
                        dataset_group=group,
                        source_file=relative,
                        project_id=scalar(ann.get("project") or project_task),
                        runtime_task_id=scalar(ann.get("task") or task_id),
                        base_task_id=base,
                        image_id=image_id,
                        worker_id=scalar(ann.get("completed_by")),
                        annotation_id=scalar(ann.get("id")),
                        annotation_unique_id=scalar(ann.get("unique_id")),
                        created_at=scalar(ann.get("created_at")),
                        updated_at=scalar(ann.get("updated_at")),
                        was_cancelled=boolish(ann.get("was_cancelled")),
                        keypoints=points,
                        width=width,
                        height=height,
                        choices_json=choices_json,
                    )
                )
    return out


def annotation_number(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def choose_latest(records: list[RawRecord]) -> RawRecord:
    return max(records, key=lambda row: (row.updated_at, row.created_at, annotation_number(row.annotation_id), row.annotation_id))


def choose_max_id(records: list[RawRecord]) -> RawRecord:
    return max(records, key=lambda row: (annotation_number(row.annotation_id), row.updated_at, row.created_at))


def choose_earliest(records: list[RawRecord]) -> RawRecord:
    return min(records, key=lambda row: (row.created_at, annotation_number(row.annotation_id), row.annotation_id))


def canonicalise(raw: list[RawRecord]) -> tuple[list[CanonicalRecord], list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str, str], list[RawRecord]] = defaultdict(list)
    for row in raw:
        groups[row.acquisition_key].append(row)
    selected: list[CanonicalRecord] = []
    duplicate_audit: list[dict[str, Any]] = []
    for key, versions in sorted(groups.items()):
        latest = choose_latest(versions)
        max_id = choose_max_id(versions)
        earliest = choose_earliest(versions)
        strict = normalize_geometry(list(latest.keypoints), width=latest.width, height=latest.height)
        selected.append(CanonicalRecord(latest, strict))
        duplicate_audit.append(
            {
                "stage": key[0],
                "project_id": key[1],
                "runtime_task_id": key[2],
                "worker_id": key[3],
                "version_count": len(versions),
                "annotation_ids_json": json.dumps([row.annotation_id for row in sorted(versions, key=lambda x: annotation_number(x.annotation_id))]),
                "latest_annotation_id": latest.annotation_id,
                "max_id_annotation_id": max_id.annotation_id,
                "earliest_annotation_id": earliest.annotation_id,
                "latest_equals_max_id": latest.annotation_id == max_id.annotation_id,
                "latest_equals_earliest": latest.annotation_id == earliest.annotation_id,
                "latest_point_count": len(latest.keypoints),
                "latest_strict_valid": bool(strict.get("valid")),
                "latest_strict_reason": str(strict.get("reason") or ""),
            }
        )
    return selected, duplicate_audit


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=float), q))


def task_groups(records: list[CanonicalRecord]) -> dict[tuple[str, str, str, str], list[CanonicalRecord]]:
    out: dict[tuple[str, str, str, str], list[CanonicalRecord]] = defaultdict(list)
    for row in records:
        r = row.raw
        out[(r.stage, r.condition, r.dataset_group, r.base_task_id)].append(row)
    return out


def pairwise_task_summary(key: tuple[str, str, str, str], records: list[CanonicalRecord]) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    strict = [row for row in records if row.strict.get("valid")]
    pair_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    boundary_distances: list[float] = []
    wall_distances: list[float] = []
    count_disagreements: list[int] = []
    all_pair_count = math.comb(len(records), 2) if len(records) >= 2 else 0
    for left, right in combinations(strict, 2):
        item = pairwise_similarity(left.strict, right.strict)
        pair_key = tuple(sorted((left.canonical_id, right.canonical_id)))
        pair_lookup[pair_key] = item
        if item.get("boundary_similarity") is not None:
            boundary_distances.append(1.0 - float(item["boundary_similarity"]))
        if item.get("wallwall_similarity") is not None:
            wall_distances.append(1.0 - float(item["wallwall_similarity"]))
        count_disagreements.append(int(int(left.strict.get("n_pairs", 0)) != int(right.strict.get("n_pairs", 0))))
    stage, condition, dataset_group, base = key
    selected_counts = [len(row.raw.keypoints) for row in records]
    strict_counts = [int(row.strict.get("n_pairs", 0)) for row in strict]
    row = {
        "stage": stage,
        "condition": condition,
        "dataset_group": dataset_group,
        "base_task_id": base,
        "selected_support": len(records),
        "distinct_workers": len({row.raw.worker_id for row in records}),
        "even_point_candidate_support": sum(len(row.raw.keypoints) >= 4 and len(row.raw.keypoints) % 2 == 0 for row in records),
        "strict_valid_support": len(strict),
        "strict_invalid_support": len(records) - len(strict),
        "all_selected_pair_count": all_pair_count,
        "strict_pair_count": math.comb(len(strict), 2) if len(strict) >= 2 else 0,
        "boundary_metric_pair_count": len(boundary_distances),
        "wall_metric_pair_count": len(wall_distances),
        "metric_pair_coverage_over_all_selected": len(boundary_distances) / all_pair_count if all_pair_count else None,
        "boundary_distance_mean": float(np.mean(boundary_distances)) if boundary_distances else None,
        "boundary_distance_median": float(np.median(boundary_distances)) if boundary_distances else None,
        "boundary_distance_q90": quantile(boundary_distances, 0.90),
        "wall_distance_mean": float(np.mean(wall_distances)) if wall_distances else None,
        "wall_distance_median": float(np.median(wall_distances)) if wall_distances else None,
        "wall_distance_q90": quantile(wall_distances, 0.90),
        "vertical_boundary_count_disagreement": float(np.mean(count_disagreements)) if count_disagreements else None,
        "selected_point_counts_json": json.dumps(selected_counts),
        "strict_vertical_boundary_counts_json": json.dumps(strict_counts),
        "strict_boundary_count_diverse": len(set(strict_counts)) > 1,
    }
    return row, pair_lookup


def rankdata(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    index = 0
    while index < len(values):
        end = index + 1
        while end < len(values) and values[order[end]] == values[order[index]]:
            end += 1
        rank = (index + end - 1) / 2.0 + 1.0
        ranks[order[index:end]] = rank
        index = end
    return ranks


def spearman(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 3:
        return None
    a = rankdata(left)
    b = rankdata(right)
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def subset_distance(sample: list[CanonicalRecord], pair_lookup: dict[tuple[str, str], dict[str, Any]], channel: str) -> float | None:
    values: list[float] = []
    similarity_key = "boundary_similarity" if channel == "boundary" else "wallwall_similarity"
    for left, right in combinations(sample, 2):
        item = pair_lookup.get(tuple(sorted((left.canonical_id, right.canonical_id))))
        if not item or item.get(similarity_key) is None:
            continue
        values.append(1.0 - float(item[similarity_key]))
    return float(np.mean(values)) if values else None


def summarise_replicates(rows: list[dict[str, Any]], channel: str, k: int) -> dict[str, Any]:
    out: dict[str, Any] = {"channel": channel, "k": k, "replicates": len(rows)}
    for field in ("mae", "rmse", "spearman", "top20_recall"):
        values = [float(row[field]) for row in rows if row.get(field) is not None and math.isfinite(float(row[field]))]
        out[f"{field}_mean"] = float(np.mean(values)) if values else None
        out[f"{field}_median"] = float(np.median(values)) if values else None
        out[f"{field}_q05"] = quantile(values, 0.05)
        out[f"{field}_q95"] = quantile(values, 0.95)
    return out


def run_support_calibration(
    high_density: dict[str, list[CanonicalRecord]],
    task_pair_lookup: dict[str, dict[tuple[str, str], dict[str, Any]]],
    task_full: dict[str, dict[str, float]],
    replicates: int = 1000,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(SEED)
    ks = (2, 3, 5, 8, 10, 15, 20)
    replicate_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    count_detection_rows: list[dict[str, Any]] = []
    task_ids = sorted(high_density)
    full_diverse = {
        task_id: len({int(row.strict.get("n_pairs", 0)) for row in records}) > 1
        for task_id, records in high_density.items()
    }

    for k in ks:
        eligible = [task_id for task_id in task_ids if len(high_density[task_id]) >= k]
        if not eligible:
            continue
        count_hits_all: Counter[str] = Counter()
        count_hits_diverse: Counter[str] = Counter()
        count_trials: Counter[str] = Counter()
        for replicate in range(replicates):
            sampled_values: dict[str, dict[str, float]] = {"boundary": {}, "wall": {}}
            count_seen: dict[str, bool] = {}
            for task_id in eligible:
                records = high_density[task_id]
                indices = rng.choice(len(records), size=k, replace=False)
                sample = [records[int(index)] for index in indices]
                for channel in ("boundary", "wall"):
                    value = subset_distance(sample, task_pair_lookup[task_id], channel)
                    if value is not None:
                        sampled_values[channel][task_id] = value
                count_seen[task_id] = len({int(row.strict.get("n_pairs", 0)) for row in sample}) > 1
                count_trials[task_id] += 1
                if count_seen[task_id]:
                    count_hits_all[task_id] += 1
                    if full_diverse[task_id]:
                        count_hits_diverse[task_id] += 1

            for channel in ("boundary", "wall"):
                common = [task_id for task_id in eligible if task_id in sampled_values[channel] and channel in task_full[task_id]]
                if len(common) < 3:
                    continue
                sampled = np.asarray([sampled_values[channel][task_id] for task_id in common], dtype=float)
                full = np.asarray([task_full[task_id][channel] for task_id in common], dtype=float)
                errors = sampled - full
                top_n = max(1, math.ceil(0.20 * len(common)))
                full_top = set(np.argsort(full)[-top_n:])
                sampled_top = set(np.argsort(sampled)[-top_n:])
                replicate_rows.append(
                    {
                        "channel": channel,
                        "k": k,
                        "replicate": replicate,
                        "task_count": len(common),
                        "mae": float(np.mean(np.abs(errors))),
                        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                        "spearman": spearman(sampled, full),
                        "top20_recall": len(full_top & sampled_top) / top_n,
                    }
                )
        for channel in ("boundary", "wall"):
            summary_rows.append(summarise_replicates([row for row in replicate_rows if row["channel"] == channel and row["k"] == k], channel, k))
        diverse_ids = [task_id for task_id in eligible if full_diverse[task_id]]
        count_detection_rows.append(
            {
                "k": k,
                "eligible_task_count": len(eligible),
                "full_count_diverse_task_count": len(diverse_ids),
                "mean_probability_observe_multiple_counts_all_tasks": float(np.mean([count_hits_all[task_id] / count_trials[task_id] for task_id in eligible])),
                "mean_probability_observe_multiple_counts_given_full_diverse": float(np.mean([count_hits_diverse[task_id] / count_trials[task_id] for task_id in diverse_ids])) if diverse_ids else None,
            }
        )
    return replicate_rows, summary_rows, count_detection_rows


def cluster_full_and_prefix(
    high_density: dict[str, list[CanonicalRecord]],
    task_pair_lookup: dict[str, dict[tuple[str, str], dict[str, Any]]],
    replicates: int = 200,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rng = np.random.default_rng(SEED + 1)
    thresholds = (0.90, 0.925, 0.95, 0.97, 0.98)
    full_rows: list[dict[str, Any]] = []
    prefix_rows: list[dict[str, Any]] = []
    prefix_summary: list[dict[str, Any]] = []

    def records_for(task_id: str, sample: list[CanonicalRecord]) -> tuple[list[dict[str, Any]], Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]]:
        converted = []
        id_by_geometry: dict[int, str] = {}
        for item in sample:
            geometry = item.strict
            id_by_geometry[id(geometry)] = item.canonical_id
            converted.append({"canonical_annotation_id": item.canonical_id, "worker_id": item.raw.worker_id, "geometry": geometry})
        def lookup(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
            key = tuple(sorted((id_by_geometry[id(left)], id_by_geometry[id(right)])))
            return task_pair_lookup[task_id][key]
        return converted, lookup

    for threshold in thresholds:
        for task_id, sample in sorted(high_density.items()):
            converted, lookup = records_for(task_id, sample)
            result = cluster_geometry_records(
                converted,
                min_q_boundary=threshold,
                min_q_wallwall=threshold,
                base_task_id=task_id,
                minimum_valid_k=3,
                pairwise_fn=lookup,
            )
            full_rows.append(
                {
                    "task_id": task_id,
                    "threshold": threshold,
                    "valid_k": result["valid_k"],
                    "partition_status": result["partition_status"],
                    "structure_status": result["task_crowd_structure_status"],
                    "cluster_count": result["cluster_count"],
                    "largest_support": result["largest_cluster_support"],
                    "second_support": result["second_cluster_support"],
                    "reason": result["structure_reason"],
                }
            )

    q = 0.95
    full_q = {row["task_id"]: row for row in full_rows if row["threshold"] == q}
    ks = (5, 8, 12, 16, 20)
    for k in ks:
        eligible = [task_id for task_id, sample in high_density.items() if len(sample) >= k]
        for replicate in range(replicates):
            for task_id in sorted(eligible):
                sample_all = high_density[task_id]
                indices = rng.choice(len(sample_all), size=k, replace=False)
                sample = [sample_all[int(index)] for index in indices]
                converted, lookup = records_for(task_id, sample)
                result = cluster_geometry_records(
                    converted,
                    min_q_boundary=q,
                    min_q_wallwall=q,
                    base_task_id=task_id,
                    minimum_valid_k=3,
                    pairwise_fn=lookup,
                )
                prefix_rows.append(
                    {
                        "task_id": task_id,
                        "k": k,
                        "replicate": replicate,
                        "full_structure_status": full_q[task_id]["structure_status"],
                        "prefix_partition_status": result["partition_status"],
                        "prefix_structure_status": result["task_crowd_structure_status"],
                    }
                )
        all_rows = [row for row in prefix_rows if row["k"] == k]
        full_multi = [row for row in all_rows if row["full_structure_status"] == "supported_multimodal"]
        prefix_summary.append(
            {
                "k": k,
                "replicates": replicates,
                "task_count": len(eligible),
                "supported_multimodal_rate_all": sum(row["prefix_structure_status"] == "supported_multimodal" for row in all_rows) / len(all_rows) if all_rows else None,
                "not_evaluable_rate_all": sum(row["prefix_partition_status"] != "unique" for row in all_rows) / len(all_rows) if all_rows else None,
                "full_supported_multimodal_task_count": len({row["task_id"] for row in full_multi}),
                "reproduction_rate_given_full_supported_multimodal": sum(row["prefix_structure_status"] == "supported_multimodal" for row in full_multi) / len(full_multi) if full_multi else None,
            }
        )
    return full_rows, prefix_rows, prefix_summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    canonical, duplicates = canonicalise(raw)
    groups = task_groups(canonical)

    task_rows: list[dict[str, Any]] = []
    lookups_by_group: dict[tuple[str, str, str, str], dict[tuple[str, str], dict[str, Any]]] = {}
    for key, records in sorted(groups.items()):
        row, lookup = pairwise_task_summary(key, records)
        task_rows.append(row)
        lookups_by_group[key] = lookup

    canonical_rows = []
    for item in canonical:
        r = item.raw
        canonical_rows.append(
            {
                "canonical_id": item.canonical_id,
                "stage": r.stage,
                "condition": r.condition,
                "dataset_group": r.dataset_group,
                "source_file": r.source_file,
                "project_id": r.project_id,
                "runtime_task_id": r.runtime_task_id,
                "base_task_id": r.base_task_id,
                "worker_id": r.worker_id,
                "annotation_id": r.annotation_id,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "raw_keypoint_count": len(r.keypoints),
                "raw_even_point_candidate": len(r.keypoints) >= 4 and len(r.keypoints) % 2 == 0,
                "strict_valid": bool(item.strict.get("valid")),
                "strict_reason": str(item.strict.get("reason") or ""),
                "strict_vertical_boundary_count": int(item.strict.get("n_pairs", 0)),
                "pairing_method": str(item.strict.get("pairing_method") or ""),
                "seam_crossing_detected": bool(item.strict.get("seam_crossing_detected")),
            }
        )

    high_density: dict[str, list[CanonicalRecord]] = {}
    high_lookup: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    task_full: dict[str, dict[str, float]] = {}
    high_key_map: dict[str, tuple[str, str, str, str]] = {}
    for key, records in sorted(groups.items()):
        stage, condition, dataset_group, base = key
        if not ((stage == "P1" and condition == "manual" and dataset_group == "PreScreen_manual") or (stage == "C1" and condition == "manual" and dataset_group == "C1_anchor_all")):
            continue
        strict = [row for row in records if row.strict.get("valid")]
        task_id = f"{stage}|{dataset_group}|{base}"
        high_density[task_id] = strict
        high_lookup[task_id] = lookups_by_group[key]
        high_key_map[task_id] = key
        task_row = next(row for row in task_rows if (row["stage"], row["condition"], row["dataset_group"], row["base_task_id"]) == key)
        task_full[task_id] = {}
        if task_row["boundary_distance_mean"] is not None:
            task_full[task_id]["boundary"] = float(task_row["boundary_distance_mean"])
        if task_row["wall_distance_mean"] is not None:
            task_full[task_id]["wall"] = float(task_row["wall_distance_mean"])

    calibration_replicates, calibration_summary, count_detection = run_support_calibration(high_density, high_lookup, task_full)
    cluster_full, cluster_prefix, cluster_prefix_summary = cluster_full_and_prefix(high_density, high_lookup)

    source_summary: list[dict[str, Any]] = []
    for stage, condition, group, relative in SOURCE_FILES:
        subset_raw = [row for row in raw if row.source_file == relative]
        subset_selected = [row for row in canonical if row.raw.source_file == relative]
        source_summary.append(
            {
                "stage": stage,
                "condition": condition,
                "dataset_group": group,
                "source_file": relative,
                "raw_annotation_versions": len(subset_raw),
                "independent_acquisition_keys": len({row.acquisition_key for row in subset_raw}),
                "selected_latest_versions": len(subset_selected),
                "duplicate_version_excess": len(subset_raw) - len({row.acquisition_key for row in subset_raw}),
                "selected_even_point_candidates": sum(len(row.raw.keypoints) >= 4 and len(row.raw.keypoints) % 2 == 0 for row in subset_selected),
                "selected_strict_valid": sum(bool(row.strict.get("valid")) for row in subset_selected),
                "unique_base_tasks": len({row.base_task_id for row in subset_raw}),
                "distinct_workers": len({row.worker_id for row in subset_raw}),
            }
        )

    broad_core = [row for row in task_rows if row["stage"] == "C1" and row["condition"] == "manual" and row["dataset_group"] == "C1_core_all"]
    core_k5 = [row for row in broad_core if int(row["strict_valid_support"] or 0) >= 5]
    high_task_rows = [
        {"high_density_task_id": task_id, **next(row for row in task_rows if (row["stage"], row["condition"], row["dataset_group"], row["base_task_id"]) == key)}
        for task_id, key in high_key_map.items()
    ]

    summary = {
        "source_commit": "runtime_branch_parent_main_f3c7b713c6cff6c08dc1fe231c7e84b8db1774ee",
        "selection_rule": "latest updated_at, then created_at, then numeric annotation_id",
        "raw_annotation_versions": len(raw),
        "independent_acquisition_keys": len({row.acquisition_key for row in raw}),
        "selected_canonical_records": len(canonical),
        "duplicate_version_excess": len(raw) - len({row.acquisition_key for row in raw}),
        "duplicate_groups": sum(row["version_count"] > 1 for row in duplicates),
        "latest_vs_max_id_disagreements": sum(not row["latest_equals_max_id"] for row in duplicates),
        "stage_selected_counts": dict(Counter(row.raw.stage for row in canonical)),
        "stage_strict_valid_counts": dict(Counter(row.raw.stage for row in canonical if row.strict.get("valid"))),
        "high_density_task_count": len(high_density),
        "high_density_min_strict_support": min((len(rows) for rows in high_density.values()), default=0),
        "high_density_max_strict_support": max((len(rows) for rows in high_density.values()), default=0),
        "high_density_tasks_with_strict_support_ge20": sum(len(rows) >= 20 for rows in high_density.values()),
        "high_density_full_count_diverse_tasks": sum(len({int(row.strict.get("n_pairs", 0)) for row in rows}) > 1 for rows in high_density.values()),
        "c1_core_unique_task_count": len(broad_core),
        "c1_core_tasks_strict_k_ge5": len(core_k5),
        "c1_core_strict_k_distribution": dict(sorted(Counter(int(row["strict_valid_support"] or 0) for row in broad_core).items())),
        "c1_core_boundary_distance_mean_across_images": float(np.mean([float(row["boundary_distance_mean"]) for row in core_k5 if row["boundary_distance_mean"] is not None])) if core_k5 else None,
        "c1_core_boundary_distance_median_across_images": float(np.median([float(row["boundary_distance_mean"]) for row in core_k5 if row["boundary_distance_mean"] is not None])) if core_k5 else None,
        "c1_core_boundary_distance_q10_across_images": quantile([float(row["boundary_distance_mean"]) for row in core_k5 if row["boundary_distance_mean"] is not None], 0.10),
        "c1_core_boundary_distance_q90_across_images": quantile([float(row["boundary_distance_mean"]) for row in core_k5 if row["boundary_distance_mean"] is not None], 0.90),
        "notes": [
            "Raw selection is independent of historical canonical authority tables.",
            "Strict validity is the current image-plane serialization contract, not physical floor-plan topology validity.",
            "Boundary and wall-wall channels are reported separately and are never merged.",
            "Cluster outputs are algorithmic partitions under current complete-link/maximum-clique rules; they are not claims of true alternative layouts.",
        ],
    }

    write_rows(OUT / "raw_source_selection_summary.csv", source_summary)
    write_rows(OUT / "duplicate_version_audit.csv", duplicates)
    write_rows(OUT / "independent_canonical_records.csv", canonical_rows)
    write_rows(OUT / "task_support_and_geometry_metrics.csv", task_rows)
    write_rows(OUT / "high_density_task_metrics.csv", high_task_rows)
    write_rows(OUT / "support_calibration_replicates.csv", calibration_replicates)
    write_rows(OUT / "support_calibration_summary.csv", calibration_summary)
    write_rows(OUT / "boundary_count_detection_summary.csv", count_detection)
    write_rows(OUT / "high_density_cluster_threshold_sensitivity.csv", cluster_full)
    write_rows(OUT / "high_density_cluster_prefix_replay.csv", cluster_prefix)
    write_rows(OUT / "high_density_cluster_prefix_summary.csv", cluster_prefix_summary)
    write_rows(OUT / "c1_core_k_ge5_task_metrics.csv", core_k5)
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
