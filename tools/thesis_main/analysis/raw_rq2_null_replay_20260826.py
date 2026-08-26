from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from tools.thesis_main.analysis.raw_rq1_recompute_20260826 import (
    canonicalise,
    load_raw,
    pairwise_task_summary,
    quantile,
    subset_distance,
    task_groups,
    write_rows,
)

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "analysis_results" / "rq1_raw_recompute_20260826"
OUT = ROOT / "analysis_results" / "rq2_null_replay_20260826"
SEED = 20260826 + 2
REPLICATES = 2000


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    canonical, _ = canonicalise(raw)
    groups = task_groups(canonical)

    high_density = {}
    pair_lookup = {}
    for key, records in sorted(groups.items()):
        stage, condition, dataset_group, base = key
        if not (
            (stage == "P1" and condition == "manual" and dataset_group == "PreScreen_manual")
            or (stage == "C1" and condition == "manual" and dataset_group == "C1_anchor_all")
        ):
            continue
        strict = [row for row in records if row.strict.get("valid")]
        task_id = f"{stage}|{dataset_group}|{base}"
        _, lookup = pairwise_task_summary(key, records)
        high_density[task_id] = strict
        pair_lookup[task_id] = lookup

    if len(high_density) != 42 or min(len(rows) for rows in high_density.values()) < 15:
        raise AssertionError("Expected 42 high-density tasks with at least 15 strict-valid records")

    rng = np.random.default_rng(SEED)
    replicate_rows = []
    task_rows = []
    task_ids = sorted(high_density)
    contrast_names = ("C_minus_M", "W_minus_M", "W_minus_C")

    for replicate in range(REPLICATES):
        by_channel = {"boundary": {name: [] for name in contrast_names}, "wall": {name: [] for name in contrast_names}}
        for task_id in task_ids:
            records = high_density[task_id]
            permutation = rng.permutation(len(records))[:15]
            arms = {
                "M": [records[int(index)] for index in permutation[0:5]],
                "C": [records[int(index)] for index in permutation[5:10]],
                "W": [records[int(index)] for index in permutation[10:15]],
            }
            for channel in ("boundary", "wall"):
                d = {arm: subset_distance(sample, pair_lookup[task_id], channel) for arm, sample in arms.items()}
                if any(value is None for value in d.values()):
                    continue
                contrasts = {
                    "C_minus_M": float(d["C"] - d["M"]),
                    "W_minus_M": float(d["W"] - d["M"]),
                    "W_minus_C": float(d["W"] - d["C"]),
                }
                for name, value in contrasts.items():
                    by_channel[channel][name].append(value)
                task_rows.append(
                    {
                        "replicate": replicate,
                        "task_id": task_id,
                        "channel": channel,
                        "D_M": d["M"],
                        "D_C": d["C"],
                        "D_W": d["W"],
                        **contrasts,
                    }
                )
        for channel in ("boundary", "wall"):
            for name in contrast_names:
                values = np.asarray(by_channel[channel][name], dtype=float)
                replicate_rows.append(
                    {
                        "replicate": replicate,
                        "channel": channel,
                        "contrast": name,
                        "task_count": len(values),
                        "mean_contrast": float(np.mean(values)),
                        "image_contrast_sd": float(np.std(values, ddof=1)),
                    }
                )

    scenario_rows = []
    zsum = 1.959963984540054 + 0.8416212335729143
    for channel in ("boundary", "wall"):
        for contrast in contrast_names:
            rows = [row for row in replicate_rows if row["channel"] == channel and row["contrast"] == contrast]
            mean_values = [float(row["mean_contrast"]) for row in rows]
            image_sds = [float(row["image_contrast_sd"]) for row in rows]
            fixed_42_se = float(np.std(mean_values, ddof=1))
            median_image_sd = float(np.median(image_sds))
            for n_images in (42, 60, 72, 80):
                projected_se = median_image_sd / math.sqrt(n_images)
                scenario_rows.append(
                    {
                        "channel": channel,
                        "contrast": contrast,
                        "source_task_count": 42,
                        "projected_image_count": n_images,
                        "replicates": REPLICATES,
                        "mean_null_contrast": float(np.mean(mean_values)),
                        "fixed_42_empirical_se_of_mean": fixed_42_se,
                        "median_image_contrast_sd": median_image_sd,
                        "image_contrast_sd_q05": quantile(image_sds, 0.05),
                        "image_contrast_sd_q95": quantile(image_sds, 0.95),
                        "projected_se_from_median_image_sd": projected_se,
                        "conditional_80pct_mde_sampling_only": zsum * projected_se,
                        "interpretation": "sampling-noise lower bound under null; excludes treatment heterogeneity, building correlation, worker superpopulation, invalid outcomes, and stimulus variation",
                    }
                )

    threshold_rows = []
    threshold_file = SOURCE / "high_density_cluster_threshold_sensitivity.csv"
    import csv
    with threshold_file.open("r", encoding="utf-8-sig", newline="") as handle:
        table = list(csv.DictReader(handle))
    thresholds = sorted({float(row["threshold"]) for row in table})
    for threshold in thresholds:
        for stage in ("ALL", "P1", "C1"):
            subset = [row for row in table if float(row["threshold"]) == threshold and (stage == "ALL" or row["task_id"].startswith(stage + "|"))]
            counts = Counter(row["structure_status"] for row in subset)
            threshold_rows.append(
                {
                    "threshold": threshold,
                    "stage": stage,
                    "task_count": len(subset),
                    "unimodal": counts["unimodal"],
                    "dominant_with_dissent": counts["dominant_with_dissent"],
                    "supported_multimodal": counts["supported_multimodal"],
                    "not_evaluable": counts["not_evaluable"],
                    "supported_multimodal_rate": counts["supported_multimodal"] / len(subset) if subset else None,
                    "not_evaluable_rate": counts["not_evaluable"] / len(subset) if subset else None,
                }
            )

    write_rows(OUT / "null_replay_replicate_summary.csv", replicate_rows)
    write_rows(OUT / "null_replay_task_rows.csv", task_rows)
    write_rows(OUT / "null_replay_sample_size_scenarios.csv", scenario_rows)
    write_rows(OUT / "cluster_threshold_count_summary.csv", threshold_rows)
    summary = {
        "source_main_commit": "f3c7b713c6cff6c08dc1fe231c7e84b8db1774ee",
        "high_density_task_count": 42,
        "records_per_arm": 5,
        "arms": ["M", "C", "W"],
        "replicates": REPLICATES,
        "sampling": "15 distinct observed annotators per task, randomly partitioned 5/5/5 without replacement",
        "scope": "null replay only; not an estimate of treatment effect or success probability",
    }
    (OUT / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
