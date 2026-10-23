#!/usr/bin/env python3
"""Regroup committed, independently recomputed small tables; no bootstrap/fusion.

Run from this directory or elsewhere:
    python extract_existing_path_tables.py --repo /path/to/3D_Manhattan_label --out .
Or use only the three raw-byte small tables included with this package:
    python extract_existing_path_tables.py --inputs ./inputs --out ./reproduced
Requires Python 3, pandas and numpy. Input commit is recorded in RECEIPT.json.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

EXPECTED_COMMIT = "e92abe8631d7f01dc192ee796b46f295ece37a6d"
BASE = "research/statistics/pro_return_review_20261023/population"
EXPECTED_INPUTS = {
    "POLICY_PER_IMAGE_RECOMPUTED.csv": {"sha256": "f019d326c619c4c92112ed067a58d9f446e32e3a605621140bed7a4d0e199a59", "rows": 712},
    "NATURAL_INTERVAL_RECOMPUTED.csv": {"sha256": "f3ff6983f81f4fa231df8cabc4e4292306d8de5f1570559327e5f136c83b830c", "rows": 27},
    "NATURAL_RECOMPUTED.csv": {"sha256": "3556b736176895a870e16573f5d02c8e276560ea105368d62a0a8f524c0ce34c", "rows": 323},
}


def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo", type=Path, help="Frozen repository checkout")
    source.add_argument("--inputs", type=Path, help="Directory with the three packaged original-byte CSV inputs")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if args.repo is not None:
        repo = args.repo.resolve()
        commit = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
        if commit != EXPECTED_COMMIT:
            raise SystemExit(f"Use frozen main {EXPECTED_COMMIT}; actual {commit}")
        input_dir = repo / BASE
        input_mode = "frozen_repository"
    else:
        commit = EXPECTED_COMMIT
        input_dir = args.inputs.resolve()
        input_mode = "packaged_original_byte_inputs_sha256_verified"
    inputs = {}

    def read(name):
        path = input_dir / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != EXPECTED_INPUTS[name]["sha256"]:
            raise SystemExit(f"Input SHA256 mismatch: {name}; expected {EXPECTED_INPUTS[name]['sha256']}, actual {digest}")
        frame = pd.read_csv(path)
        assert len(frame) == EXPECTED_INPUTS[name]["rows"], name
        inputs[name] = {"relative_path": f"{BASE}/{name}", "package_relative_path": f"inputs/{name}", "sha256": digest, "sha256_verified": True, "rows": len(frame), "fields": list(frame.columns)}
        return frame

    def save(frame, name):
        frame.to_csv(args.out / name, index=False, encoding="utf-8-sig")
        return len(frame)

    pi = read("POLICY_PER_IMAGE_RECOMPUTED.csv")
    assert not pi.duplicated(["condition", "pool_id", "policy"]).any()
    complete_manual = pi[(pi.condition == "manual") & (pi.layer == "ordinary_manual") & pi.pool_n.eq(pi.pool_time_known)]
    complete_counts = complete_manual.groupby("policy").agg(images=("image", "nunique"), buildings=("building", "nunique"))
    assert len(complete_counts) == 4 and complete_counts.images.eq(88).all() and complete_counts.buildings.eq(20).all()
    assert complete_manual[["B8L2_delta", "qt_q", "logtime", "qt_logtime"]].notna().all().all()
    assert np.allclose(complete_manual.B8L2_delta, complete_manual.qt_q, atol=1e-12, rtol=1e-12)
    # Complete recorded time does not make every path jointly scorable. Joint
    # Q/T claims therefore retain qt_logtime, not unconditional logtime.
    different_time_support = ~np.isclose(complete_manual.logtime, complete_manual.qt_logtime, atol=1e-12, rtol=1e-12)
    complete_time_check = {"subset": "complete_time", "definition": "common four policies, ordinary Manual, N>=20, pool_n==pool_time_known, k=3..floor(N/2)", "counts": complete_counts.reset_index().to_dict("records"), "per_image_Q_equals_QT_Q": True, "per_image_logtime_equals_QT_logtime": bool(not different_time_support.any()), "image_policy_rows_with_different_logtime_and_QT_logtime": int(different_time_support.sum()), "joint_time_column_used": "qt_logtime", "time_support_note": "Full-pool time completeness does not eliminate unscorable paths; qt_logtime excludes pairs without a Q delta.", "common_partial_time_subset_used_for_joint_claims": False}
    numerical = ["B8L2_delta", "D10_delta", "p10_delta", "qt_q", "qt_logtime", "logtime", "floor_turn5_n_delta", "ref_bottom_pair_mean_deg_delta", "ref_top_pair_mean_deg_delta", "S_bottom_deg_delta", "dir_delta", "Hmean_delta"]
    building_rows, summary_rows = [], []
    for subset, data in [("common", pi), ("complete_time", pi[pi.pool_n.eq(pi.pool_time_known)])]:
        for scope, frame in [("all_difficulties", data), ("difficulty", data)]:
            key = ["condition", "layer", "policy"] + (["difficulty"] if scope == "difficulty" else [])
            for values, group in frame.groupby(key + ["building"], dropna=False):
                row = dict(zip(key + ["building"], values))
                row.update(subset=subset, difficulty_scope=scope,
                           images=group.image.nunique(), pools=group.pool_id.nunique(),
                           quality_images=int(group.B8L2_delta.notna().sum()),
                           quality_positive_images=int(group.B8L2_delta.gt(0).sum()),
                           p10_images=int(group.p10_delta.notna().sum()),
                           joint_qt_images=int((group.qt_q.notna() & group.qt_logtime.notna()).sum()))
                for field in numerical:
                    row[field] = group[field].mean()
                row["joint_time_pct"] = 100 * np.expm1(row["qt_logtime"])
                row.update(source_commit=commit, stage="new_reaggregation_of_main_existing_point_estimates", source_table=f"{BASE}/POLICY_PER_IMAGE_RECOMPUTED.csv", outcome_budget="k=3..floor(pool_n/2); per-image k equally weighted")
                building_rows.append(row)
            for values, group in frame.groupby(key, dropna=False):
                row = dict(zip(key, values))
                buildings = group.groupby("building", dropna=False)
                bq = buildings.B8L2_delta.mean()
                bp = buildings.p10_delta.mean()
                bqt = buildings[["qt_q", "qt_logtime"]].mean()
                row.update(subset=subset, difficulty_scope=scope,
                           images=group.image.nunique(), buildings=group.building.nunique(),
                           quality_images=int(group.B8L2_delta.notna().sum()),
                           positive_images=int(group.B8L2_delta.gt(0).sum()),
                           quality_buildings=int(bq.notna().sum()), positive_buildings=int(bq.gt(0).sum()),
                           Q_image_equal=group.B8L2_delta.mean(), Q_building_equal=bq.mean(),
                           P10_image_equal=group.p10_delta.mean(), P10_building_equal=bp.mean(),
                           QT_Q_image_equal=group.qt_q.mean(), QT_Q_building_equal=bqt.qt_q.mean(),
                           joint_time_pct_image_equal=100*np.expm1(group.qt_logtime.mean()),
                           joint_time_pct_building_equal=100*np.expm1(bqt.qt_logtime.mean()),
                           source_commit=commit, stage="new_reaggregation_of_main_existing_point_estimates")
                summary_rows.append(row)
    outputs = {}
    outputs["EXISTING_MAIN_POLICY_BUILDING_POINTS.csv"] = save(pd.DataFrame(building_rows), "EXISTING_MAIN_POLICY_BUILDING_POINTS.csv")
    outputs["EXISTING_MAIN_POLICY_WEIGHTING_COMPARISON.csv"] = save(pd.DataFrame(summary_rows), "EXISTING_MAIN_POLICY_WEIGHTING_COMPARISON.csv")
    intervals = read("NATURAL_INTERVAL_RECOMPUTED.csv")
    intervals["source_commit"] = commit
    intervals["stage"] = "main_existing_independent_point_estimate"
    intervals["quality_observed_image_denominator"] = "not separately supplied by this summary table"
    intervals["source_table"] = f"{BASE}/NATURAL_INTERVAL_RECOMPUTED.csv"
    outputs["EXISTING_MAIN_NATURAL_INTERVALS.csv"] = save(intervals, "EXISTING_MAIN_NATURAL_INTERVALS.csv")
    curves = read("NATURAL_RECOMPUTED.csv")
    selected = curves[curves.k.isin([3,6,10,20])].copy()
    selected["source_commit"] = commit
    selected["stage"] = "main_existing_independent_point_estimate"
    selected["scored_image_counts"] = "not separately supplied by this summary table; each metric omits missing values"
    outputs["EXISTING_MAIN_SELECTED_CURVE_POINTS.csv"] = save(selected, "EXISTING_MAIN_SELECTED_CURVE_POINTS.csv")
    # These are source records from the prior conversation, NOT recovered results.
    prior = pd.DataFrame([
        {"metric":"Q_mean_delta", "lower":-3.030539, "upper":2.419851},
        {"metric":"Q_p10_delta", "lower":0.285305, "upper":6.034697},
        {"metric":"Q_sd_delta", "lower":-5.676943, "upper":-0.383782},
    ])
    prior["condition"] = "manual"
    prior["layer"] = "ordinary_manual"
    prior["difficulty"] = "困难"
    prior["interval"] = "10_to_20"
    prior["status"] = "prior_reported_unreproduced"
    prior["source"] = "previous conversation, relayed by root in this task"
    prior["missing_artifact"] = "path_sampling_closeout_20261023 original bootstrap CSV / code / draw receipt"
    prior["intended_sampling_level_as_reported"] = "building"
    prior["confidence_level_or_quantiles_verified"] = False
    prior["independently_recomputed_this_round"] = False
    outputs["PRIOR_REPORTED_BUILDING_RANGES_UNREPRODUCED.csv"] = save(prior, "PRIOR_REPORTED_BUILDING_RANGES_UNREPRODUCED.csv")
    receipt = {"source_commit":commit,"input_mode":input_mode,"new_fusion_endpoints":0,"new_classifications":0,"new_orders":0,"bootstrap_runs":0,"inputs":inputs,"outputs":outputs,"complete_manual_time_support_check":complete_time_check,
               "definitions_sources":["research/workers/personnel_population_curves_v2_20261023/code/analyze_natural_curves.py", "research/workers/personnel_population_curves_v2_20261023/code/analyze_policy_curves.py", "research/statistics/pro_return_review_20261023/audit_scripts/audit_population.py"],
               "limitations":"Prior bootstrap original files are unavailable; existing main policy points are regrouped, not recovered bootstrap results."}
    (args.out/"RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"commit":commit,"outputs":outputs},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
