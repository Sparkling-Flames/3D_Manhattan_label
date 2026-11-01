#!/usr/bin/env python3
"""Reconcile normalized path frequencies with adopted screen439 published curves."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = p.parse_args()
    root = args.root.resolve()
    out = root / "stage02_normalized/doorway"
    src = root / "source/repo/research/data/doorway_review_20261030/screen439_results_20261031"
    index = pd.read_csv(out / "POOL_INDEX.csv")
    rows = []
    all_values = []
    for pr in index.itertuples(index=False):
        d = pd.read_csv(root / pr.path)
        assert len(d) == pr.row_count
        assert set(d.get("pool_id", [])) <= {pr.pool_id}
        for k, g in d.groupby("k"):
            for metric in ["B8L2", "D10", "IoU3D100"]:
                v = g[metric].dropna()
                rows.append({"pool_id": pr.pool_id, "k": k, "metric": metric,
                             "attempts": len(g), "unique_teams": g.endpoint_source_key.nunique(),
                             "complete_rate": g.complete_evaluable.mean(),
                             "valid": len(v), "mean": v.mean(), "sd": v.std(ddof=1),
                             "p10": v.quantile(.1) if len(v) else np.nan})
        if len(d):
            all_values.append(d[["team_key", "endpoint_source_key", "target_id", "image", "k", "B8L2", "D10",
                                 "IoU3D100", "complete_evaluable", "quality_valid", "stage"]].drop_duplicates())
    new = pd.DataFrame(rows)
    old = pd.read_csv(src / "NATURAL_CURVES.csv")
    compare = new.merge(old, on=["pool_id", "k", "metric"], suffixes=("_recomputed", "_adopted"),
                        how="outer", validate="one_to_one", indicator=True)
    assert compare._merge.eq("both").all()
    errors = {}
    for c in ["attempts", "unique_teams", "complete_rate", "valid", "mean", "sd", "p10"]:
        a, b = compare[c + "_recomputed"], compare[c + "_adopted"]
        assert a.isna().equals(b.isna()), c
        compare[c + "_difference"] = a - b
        errors[c] = float((a - b).abs().max())
        assert np.allclose(a, b, atol=1e-7, rtol=0, equal_nan=True), (c, errors[c])
    compare.to_csv(out / "ADOPTED_CURVE_RECONCILIATION.csv.gz", index=False,
                   compression={"method": "gzip", "mtime": 0})
    d = pd.concat(all_values, ignore_index=True).drop_duplicates()
    shared = d.groupby(["team_key", "target_id"]).agg(
        source_keys=("endpoint_source_key", "nunique"), image=("image", "first"), k=("k", "first"),
        complete_values=("complete_evaluable", "nunique"), valid_values=("quality_valid", "nunique"),
        B8_min=("B8L2", "min"), B8_max=("B8L2", "max"),
        D10_min=("D10", "min"), D10_max=("D10", "max"),
        IoU_min=("IoU3D100", "min"), IoU_max=("IoU3D100", "max"),
    ).reset_index()
    shared = shared[shared.source_keys > 1].copy()
    for stem in ["B8", "D10", "IoU"]:
        shared[stem + "_range"] = shared[stem + "_max"] - shared[stem + "_min"]
    shared.to_csv(out / "REUSED_MEMBER_TEAM_SOURCE_CONSISTENCY.csv", index=False)
    main = shared[shared.k >= 3]
    assert main.complete_values.le(1).all() and main.valid_values.le(1).all()
    assert main[["B8_range", "D10_range", "IoU_range"]].fillna(0).le(1e-7).all().all()
    receipt = {
        "adopted_metric_pool_k_rows": len(old), "reconciled_rows": len(compare),
        "maximum_absolute_differences": errors, "all_adopted_curve_rows_match": True,
        "multiply_sourced_member_target_teams": len(shared),
        "multiply_sourced_member_target_teams_k_ge_3": len(main),
        "all_main_duplicate_source_quality_and_status_consistent": True,
        "zero_B8L2_unique_team_target_rows": int(d.B8L2.eq(0).sum()),
        "finite_Q_but_source_complete_false": int((d.quality_valid & ~d.complete_evaluable).sum()),
        "complete_true_but_nonfinite_Q": int((d.complete_evaluable & ~d.quality_valid).sum()),
        "new_fusion_runs": 0, "new_quality_runs": 0,
    }
    (out / "ADOPTED_CURVE_RECONCILIATION.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
