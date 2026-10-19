#!/usr/bin/env python3
"""Meaningful feature/provenance verification, no fusion-outcome inspection."""
from __future__ import annotations
import argparse
import gzip
import json
from pathlib import Path
import numpy as np
import pandas as pd
from build_forward import upstream_functions, flatten, read_history, js, RECORD_SOURCE, conditional_features


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    _, fn = upstream_functions(args.repo)
    evidence = json.load(gzip.open(args.repo / RECORD_SOURCE, "rt"))["records"]
    d = flatten(evidence)
    ex = fn["extra_frame"](evidence)
    buildings = read_history(json.loads(args.split.read_text()))
    workers = sorted(d.loc[d.quality_usable, "worker_id"].unique())
    f, _ = fn["_training_features"](d, ex, workers, buildings)
    f, _ = conditional_features(d, f, buildings, fn, "B8L2")
    # Make all evaluation quality/geometry/time/behavior values absurd while
    # keeping identity and opportunity schema intact. None may affect features.
    poisoned = d.copy(deep=True)
    future = ~poisoned.building_id.isin(buildings)
    numerical = ["B8L2", "D10", "source_active_time_seconds", "target_matched_time_seconds", "declared_pair_count", "reference_pair_count", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "height_mean_ratio"]
    poisoned.loc[future, numerical] = 987654.321
    ex2 = ex.copy(deep=True)
    numeric = list(ex2.select_dtypes(include=["number"]).columns)
    ex2.loc[~ex2.building_id.isin(buildings), numeric] = -987654.321
    fp, _ = fn["_training_features"](poisoned, ex2, workers, buildings)
    fp, _ = conditional_features(poisoned, fp, buildings, fn, "B8L2")
    pd.testing.assert_frame_equal(f, fp, check_exact=True)
    # A separate dense dummy-variable least-squares implementation checks the
    # frozen FE algebra on the exact training panel (including centering).
    q = d[d.building_id.isin(buildings) & d.quality_usable & d.condition.eq("manual") & d.quality_use.eq("ordinary_primary")].copy()
    wi = {w: i for i, w in enumerate(sorted(q.worker_id.unique()))}
    ti = {t: i for i, t in enumerate(sorted(q.task.unique()))}
    design = np.zeros((len(q) + 1, len(wi) + len(ti)))
    rows = np.arange(len(q))
    design[rows, q.worker_id.map(wi)] = 1.
    design[rows, len(wi) + q.task.map(ti)] = 1.
    design[-1, :len(wi)] = 1.
    y = np.r_[q.B8L2.to_numpy(float), 0.]
    estimate = np.linalg.lstsq(design, y, rcond=1e-11)[0][:len(wi)]
    fitted = f.set_index("worker_id").loc[list(wi), "q_beta"].to_numpy(float)
    delta = float(np.max(np.abs(estimate - fitted)))
    assert delta < 1e-8, delta
    saved = pd.read_csv(args.out / "features_train.csv.gz").drop(columns="train_key")
    # CSV has no separate empty-string token. Normalize string fields only;
    # numerical missing opportunities remain NaN.
    for col in f.select_dtypes(include=["object"]).columns:
        saved[col] = saved[col].fillna("")
        f[col] = f[col].fillna("")
    pd.testing.assert_frame_equal(f, saved, check_exact=False, check_dtype=False, atol=1e-10, rtol=1e-10)
    labels = pd.read_csv(args.out / "worker_labels.csv.gz")
    assert not labels.duplicated(["method_id", "domain", "worker_id"]).any()
    assert labels.known.eq(labels.class_id.ne("unknown")).all()
    js(args.out / "verification_receipt.json", {"heldout_value_poisoning": "all fitted features exactly unchanged", "independent_dummy_OLS_q_beta_max_abs_difference": delta, "training_quality_rows": len(q), "training_images": q.image_id.nunique(), "training_buildings": q.building_id.nunique(), "training_worker_count": q.worker_id.nunique(), "csv_roundtrip_tolerance": 1e-10, "label_keys_unique": True, "unknown_is_not_a_class": True})
    print(json.dumps({"poisoning": "unchanged", "FE_delta": delta, "labels": len(labels)}))


if __name__ == "__main__":
    main()
