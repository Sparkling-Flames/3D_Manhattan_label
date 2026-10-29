from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from tools.thesis_main.analysis.quality_core.active_time import load_active_logs, lookup_active_log_entry
from tools.thesis_main.analysis.raw_rq1_recompute_20260826 import (
    CanonicalRecord,
    canonicalise,
    load_raw,
    pairwise_task_summary,
    quantile,
    spearman,
    task_groups,
    write_rows,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results" / "rq1_difficulty_time_raw_20260826"
SEED = 20260829
BOOTSTRAPS = 4000

TAG_PATTERNS = {
    "trivial": ("trivial", "非常简单"),
    "occlusion": ("occlusion", "遮挡"),
    "low_texture": ("low_texture", "low texture", "纹理"),
    "seam": ("seam", "拼接"),
    "reflection": ("reflection", "反光", "玻璃"),
    "low_quality": ("low_quality", "blur", "low quality", "画质", "遮罩"),
}


def normalise_tags(choices_json: str) -> tuple[list[str], list[str]]:
    try:
        payload = json.loads(choices_json or "{}")
    except json.JSONDecodeError:
        return [], []
    raw = []
    for field, values in payload.items():
        if str(field).strip().casefold() != "difficulty":
            continue
        if not isinstance(values, list):
            values = [values]
        raw.extend(str(value) for value in values)
    tags = []
    for token in raw:
        low = token.casefold()
        for tag, patterns in TAG_PATTERNS.items():
            if any(pattern.casefold() in low for pattern in patterns):
                tags.append(tag)
                break
    return sorted(set(tags)), raw


def pair_distance(lookup: dict[tuple[str, str], dict[str, Any]], left: CanonicalRecord, right: CanonicalRecord) -> float | None:
    key = tuple(sorted((left.canonical_id, right.canonical_id)))
    item = lookup.get(key)
    if not item or item.get("boundary_similarity") is None:
        return None
    return 1.0 - float(item["boundary_similarity"])


def dispersion(records: list[CanonicalRecord], lookup: dict[tuple[str, str], dict[str, Any]]) -> float | None:
    values = []
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            value = pair_distance(lookup, left, right)
            if value is not None:
                values.append(value)
    return float(np.mean(values)) if values else None


def pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if len(left) < 3 or float(np.std(left)) == 0 or float(np.std(right)) == 0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def residualise_by_group(values: np.ndarray, groups: list[str]) -> np.ndarray:
    result = values.astype(float).copy()
    by_group: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        by_group[group].append(index)
    for indices in by_group.values():
        result[indices] -= float(np.mean(result[indices]))
    return result


def fixed_effect_slope(x: np.ndarray, y: np.ndarray, groups: list[str]) -> dict[str, float | None]:
    x_resid = residualise_by_group(x, groups)
    y_resid = residualise_by_group(y, groups)
    denom = float(np.dot(x_resid, x_resid))
    if denom <= 0:
        return {"slope": None, "standardized_slope": None, "within_group_pearson": None}
    slope = float(np.dot(x_resid, y_resid) / denom)
    x_sd = float(np.std(x_resid, ddof=1))
    y_sd = float(np.std(y_resid, ddof=1))
    return {
        "slope": slope,
        "standardized_slope": slope * x_sd / y_sd if y_sd > 0 else None,
        "within_group_pearson": pearson(x_resid, y_resid),
    }


def bootstrap_buildings_task_spearman(task_rows: list[dict[str, Any]], predictor: str, outcome: str) -> tuple[float | None, float | None, float | None]:
    usable = [row for row in task_rows if row.get(predictor) is not None and row.get(outcome) is not None]
    if len(usable) < 5:
        return None, None, None
    observed = spearman(np.asarray([float(row[predictor]) for row in usable]), np.asarray([float(row[outcome]) for row in usable]))
    by_building: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in usable:
        by_building[str(row["building_id"])].append(row)
    buildings = sorted(by_building)
    if len(buildings) < 3:
        return observed, None, None
    rng = np.random.default_rng(SEED + abs(hash((predictor, outcome))) % 10000)
    samples = []
    for _ in range(BOOTSTRAPS):
        picked = rng.choice(buildings, size=len(buildings), replace=True)
        rows = []
        for replicate_id, building in enumerate(picked):
            for row in by_building[str(building)]:
                rows.append({**row, "bootstrap_building": f"{building}__{replicate_id}"})
        value = spearman(np.asarray([float(row[predictor]) for row in rows]), np.asarray([float(row[outcome]) for row in rows]))
        if value is not None and math.isfinite(value):
            samples.append(value)
    return observed, quantile(samples, 0.025), quantile(samples, 0.975)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    canonical, _ = canonicalise(raw)
    c1 = [row for row in canonical if row.raw.stage == "C1"]

    owner_map: dict[Any, str] = {}
    for item in c1:
        r = item.raw
        owner_map[(r.project_id, r.runtime_task_id, r.annotation_id)] = r.worker_id
        owner_map[(r.runtime_task_id, r.annotation_id)] = r.worker_id
    active_times = load_active_logs(str(ROOT / "active_logs" / "c1"), annotation_owner_map=owner_map, policy="calibration")

    groups = task_groups(canonical)
    response_rows = []
    task_rows = []
    vocabulary: Counter[tuple[str, str]] = Counter()

    for key, records in sorted(groups.items()):
        stage, condition, dataset_group, base = key
        if stage != "C1" or condition != "manual" or dataset_group not in {"C1_anchor_all", "C1_core_all"}:
            continue
        valid = [row for row in records if row.strict.get("valid")]
        if len(valid) < 5:
            continue
        _, lookup = pairwise_task_summary(key, records)
        task_d = dispersion(valid, lookup)
        if task_d is None:
            continue
        per_response = []
        for item in valid:
            others = [candidate for candidate in valid if candidate.canonical_id != item.canonical_id]
            d_loo = dispersion(others, lookup) if len(others) >= 4 else None
            r = item.raw
            tags, raw_tags = normalise_tags(r.choices_json)
            try:
                choices = json.loads(r.choices_json or "{}")
                for field, values in choices.items():
                    if not isinstance(values, list):
                        values = [values]
                    for value in values:
                        vocabulary[(str(field), str(value))] += 1
            except json.JSONDecodeError:
                pass
            entry, match_status = lookup_active_log_entry(
                active_times,
                r.project_id,
                r.runtime_task_id,
                r.worker_id,
                annotation_id=r.annotation_id,
                allow_task_level_fallback=False,
            )
            active_seconds = float(entry.get("active_time_value")) if entry and entry.get("active_time_value") is not None else None
            row = {
                "stage": stage,
                "dataset_group": dataset_group,
                "base_task_id": base,
                "building_id": base.split("_", 1)[0],
                "worker_id": r.worker_id,
                "project_id": r.project_id,
                "runtime_task_id": r.runtime_task_id,
                "annotation_id": r.annotation_id,
                "strict_valid_support": len(valid),
                "task_boundary_dispersion": task_d,
                "leave_one_worker_out_boundary_dispersion": d_loo,
                "active_time_seconds": active_seconds,
                "log1p_active_time": math.log1p(active_seconds) if active_seconds is not None else None,
                "active_time_match_status": match_status,
                "difficulty_tags_json": json.dumps(tags),
                "difficulty_raw_values_json": json.dumps(raw_tags, ensure_ascii=False),
                "difficulty_trivial": int("trivial" in tags),
                "difficulty_nontrivial": int(any(tag != "trivial" for tag in tags)),
                "difficulty_nontrivial_tag_count": sum(tag != "trivial" for tag in tags),
                **{f"difficulty_{tag}": int(tag in tags) for tag in TAG_PATTERNS if tag != "trivial"},
            }
            response_rows.append(row)
            per_response.append(row)

        times = [float(row["active_time_seconds"]) for row in per_response if row["active_time_seconds"] is not None]
        task_rows.append(
            {
                "dataset_group": dataset_group,
                "base_task_id": base,
                "building_id": base.split("_", 1)[0],
                "strict_valid_support": len(valid),
                "task_boundary_dispersion": task_d,
                "active_time_observed_count": len(times),
                "active_time_median": float(np.median(times)) if times else None,
                "active_time_mean": float(np.mean(times)) if times else None,
                "difficulty_response_count": len(per_response),
                "difficulty_nontrivial_rate": float(np.mean([row["difficulty_nontrivial"] for row in per_response])),
                "difficulty_trivial_rate": float(np.mean([row["difficulty_trivial"] for row in per_response])),
                "difficulty_nontrivial_tag_count_mean": float(np.mean([row["difficulty_nontrivial_tag_count"] for row in per_response])),
                **{f"difficulty_{tag}_rate": float(np.mean([row[f"difficulty_{tag}"] for row in per_response])) for tag in TAG_PATTERNS if tag != "trivial"},
            }
        )

    vocabulary_rows = [
        {"field": field, "raw_value": value, "count": count}
        for (field, value), count in sorted(vocabulary.items(), key=lambda item: (item[0][0], -item[1], item[0][1]))
    ]

    association_rows = []
    task_outcomes = [
        "active_time_median",
        "difficulty_nontrivial_rate",
        "difficulty_trivial_rate",
        "difficulty_nontrivial_tag_count_mean",
        "difficulty_occlusion_rate",
        "difficulty_low_texture_rate",
        "difficulty_seam_rate",
        "difficulty_reflection_rate",
        "difficulty_low_quality_rate",
    ]
    for outcome in task_outcomes:
        observed, lower, upper = bootstrap_buildings_task_spearman(task_rows, "task_boundary_dispersion", outcome)
        association_rows.append(
            {
                "analysis_level": "task",
                "predictor": "task_boundary_dispersion",
                "outcome": outcome,
                "row_count": sum(row.get(outcome) is not None for row in task_rows),
                "building_count": len({row["building_id"] for row in task_rows if row.get(outcome) is not None}),
                "spearman": observed,
                "building_bootstrap_ci_lower": lower,
                "building_bootstrap_ci_upper": upper,
                "interpretation": "descriptive association; old difficulty tags are post-response and not objective task truth",
            }
        )

    response_time = [row for row in response_rows if row["leave_one_worker_out_boundary_dispersion"] is not None and row["log1p_active_time"] is not None]
    if response_time:
        x = np.asarray([float(row["leave_one_worker_out_boundary_dispersion"]) for row in response_time])
        y = np.asarray([float(row["log1p_active_time"]) for row in response_time])
        workers = [str(row["worker_id"]) for row in response_time]
        fe = fixed_effect_slope(x, y, workers)
        association_rows.append(
            {
                "analysis_level": "worker-task",
                "predictor": "leave_one_worker_out_boundary_dispersion",
                "outcome": "log1p_active_time",
                "row_count": len(response_time),
                "worker_count": len(set(workers)),
                "building_count": len({row["building_id"] for row in response_time}),
                "raw_spearman": spearman(x, y),
                **fe,
                "interpretation": "worker-fixed descriptive association; the focal worker's own geometry is excluded from the dispersion predictor",
            }
        )

    response_difficulty = [row for row in response_rows if row["leave_one_worker_out_boundary_dispersion"] is not None]
    for outcome in ("difficulty_nontrivial", "difficulty_nontrivial_tag_count", "difficulty_occlusion"):
        x = np.asarray([float(row["leave_one_worker_out_boundary_dispersion"]) for row in response_difficulty])
        y = np.asarray([float(row[outcome]) for row in response_difficulty])
        workers = [str(row["worker_id"]) for row in response_difficulty]
        fe = fixed_effect_slope(x, y, workers)
        association_rows.append(
            {
                "analysis_level": "worker-task",
                "predictor": "leave_one_worker_out_boundary_dispersion",
                "outcome": outcome,
                "row_count": len(response_difficulty),
                "worker_count": len(set(workers)),
                "building_count": len({row["building_id"] for row in response_difficulty}),
                "raw_spearman": spearman(x, y),
                **fe,
                "interpretation": "worker-fixed linear-probability/count association; old post-response tags are interface-dependent outcomes",
            }
        )

    coverage = Counter(row["active_time_match_status"] for row in response_rows)
    summary = {
        "source_main_commit": "f3c7b713c6cff6c08dc1fe231c7e84b8db1774ee",
        "manual_c1_tasks_k_ge5": len(task_rows),
        "manual_c1_worker_task_rows": len(response_rows),
        "active_time_observed_rows": sum(row["active_time_seconds"] is not None for row in response_rows),
        "active_time_match_status_counts": dict(coverage),
        "difficulty_tag_contract": "legacy required multi-select; trivial mutually exclusive with nontrivial reasons",
        "cautions": [
            "The legacy difficulty form has no ordinal overall-difficulty score.",
            "Difficulty responses were collected with the annotation and are not frozen pre-task predictors.",
            "Associations do not identify inherent ambiguity or causality.",
            "Leave-one-worker-out dispersion avoids using the focal worker's own geometry to construct the predictor.",
        ],
    }

    write_rows(OUT / "choice_vocabulary.csv", vocabulary_rows)
    write_rows(OUT / "worker_task_loo_dispersion_time_difficulty.csv", response_rows)
    write_rows(OUT / "task_dispersion_time_difficulty.csv", task_rows)
    write_rows(OUT / "associations.csv", association_rows)
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
