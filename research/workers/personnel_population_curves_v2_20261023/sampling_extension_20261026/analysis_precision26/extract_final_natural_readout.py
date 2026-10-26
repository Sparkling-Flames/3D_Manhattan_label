#!/usr/bin/env python3
"""Small final report readout from completed natural analyses only.

No fusion, resampling, fitting or sample selection occurs here. All reported
changes are direct reaggregation of the saved per-image estimates. The final
194-pool gate prevents completion-order subsets becoming report evidence.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from precision_core import save_csv, save_json


PRIMARY = ["old48", "new208", "pooled256"]
VERSIONS = PRIMARY + ["stage1_104", "stage2_104"]


def populations(meta):
    for panel, layer, cutoff in [
        ("fixed_N_ge_30", "ordinary_manual", 30),
        ("fixed_N_ge_35", "ordinary_manual", 35),
        ("all_doorway", "doorway_manual", 0),
    ]:
        d = meta[(meta.layer == layer) & meta.pool_n.ge(cutoff)]
        if d.empty:
            continue
        yield panel, layer, "全部" if layer == "ordinary_manual" else "单列", d
        if layer == "ordinary_manual":
            for difficulty, g in d.groupby("difficulty", dropna=False):
                yield panel, layer, str(difficulty), g


def band_readout(source, meta):
    records = []
    for panel, layer, difficulty, m in populations(meta):
        d = source[source.pool_id.isin(m.pool_id) & source.cohort.isin(VERSIONS) &
                   source.metric.isin(["Q_mean", "Q_p10"])]
        for (metric, scope), z in d.groupby(["metric", "band_scope"]):
            common = set(m.pool_id)
            for version in PRIMARY:
                common &= set(z.loc[z.cohort.eq(version) & z.max_abs_95.notna(), "pool_id"])
            for version, h in z.groupby("cohort"):
                for support_rule, x in [("all_estimable_within_candidate", h[h.max_abs_95.notna()]),
                                        ("same_images_estimable_in_three_primary_cohorts", h[h.pool_id.isin(common)])]:
                    records.append(dict(
                        panel=panel, layer=layer, difficulty=difficulty, cohort=version,
                        metric=metric, band_scope=scope, support_rule=support_rule,
                        candidate_images=len(m), candidate_buildings=m.building.nunique(),
                        images=len(x), buildings=x.building.nunique(),
                        halfwidth_median=x.max_abs_95.median(), halfwidth_p90=x.max_abs_95.quantile(.9),
                        halfwidth_min=x.max_abs_95.min(), halfwidth_max=x.max_abs_95.max(),
                        halfwidth_gt1_images=int(x.max_abs_95.gt(1).sum()),
                        halfwidth_gt2_images=int(x.max_abs_95.gt(2).sum()),
                        estimated_k_min=x.estimated_k_n.min(), estimated_k_max=x.estimated_k_n.max(),
                        complete_bootstrap_draws_min=x.complete_bootstrap_draws.min(),
                        complete_bootstrap_draws_max=x.complete_bootstrap_draws.max(),
                        excluded_pool_ids="|".join(sorted(set(m.pool_id) - set(x.pool_id))),
                    ))
    return pd.DataFrame(records)


def per_point_changes(source, meta):
    records = []
    for panel, layer, difficulty, m in populations(meta):
        z = source[source.pool_id.isin(m.pool_id) & source.older_cohort.eq("old48") &
                   source.newer_cohort.isin(["new208", "pooled256"]) & source.k.ne(2)]
        if panel == "fixed_N_ge_30":
            z = z[z.k.le(30)]
        elif panel == "fixed_N_ge_35":
            z = z[z.k.le(35)]
        for (newer, k), g in z.groupby(["newer_cohort", "k"]):
            for metric in ["Q_mean", "Q_p10", "Q_sd_ddof1", "D10_mean"]:
                vals = g[metric + "_difference"]
                h = g[vals.notna()]
                x = vals[vals.notna()]
                records.append(dict(
                    panel=panel, layer=layer, difficulty=difficulty, older_cohort="old48",
                    newer_cohort=newer, k=int(k), metric=metric,
                    candidate_images=len(m), images=len(h), buildings=h.building.nunique(),
                    signed_change_mean=x.mean(), signed_change_median=x.median(),
                    absolute_change_median=x.abs().median(), absolute_change_p90=x.abs().quantile(.9),
                    positive_images=int(x.gt(1e-10).sum()), negative_images=int(x.lt(-1e-10).sum()),
                    zero_images=int(x.abs().le(1e-10).sum()),
                    absolute_change_gt1_images=int(x.abs().gt(1).sum()),
                    absolute_change_gt2_images=int(x.abs().gt(2).sum()),
                    absolute_change_gt5_images=int(x.abs().gt(5).sum()),
                    mean_mcse_ratio_median=h.Q_mean_MCSE_new_over_old.median(),
                    p10_boot_halfwidth_ratio_median=h.P10_boot_halfwidth_new_over_old.median(),
                    p10_rank_halfwidth_ratio_median=h.P10_rank_halfwidth_new_over_old.median(),
                ))
    return pd.DataFrame(records)


def new_failure_readout(source, meta):
    records = []
    d = source[source.older_cohort.eq("old48") & source.newer_cohort.eq("new208") & source.k.ne(2)].copy()
    d["k_scope"] = np.select(
        [d.k.eq(d.pool_n), d.k.eq(d.pool_n - 1), d.k.eq(1)],
        ["actual_full", "near_full_Nminus1", "singleton"], default="interior_k3_to_Nminus2")
    for panel, layer, difficulty, m in populations(meta):
        z = d[d.pool_id.isin(m.pool_id)]
        for scope in ["all_non_deferred", "singleton", "interior_k3_to_Nminus2", "near_full_Nminus1", "actual_full"]:
            g = z if scope == "all_non_deferred" else z[z.k_scope.eq(scope)]
            for status, field, old_count, new_count in [
                ("actual_consensus_failure", "new_consensus_failure_seen_after_zero_old", "old_actual_consensus_failures", "new_actual_consensus_failures"),
                ("output_generated_unscoreable", "new_output_unscoreable_seen_after_zero_old", "old_output_unscoreable", "new_output_unscoreable"),
            ]:
                h = g[g[field].eq(True)]
                records.append(dict(
                    panel=panel, layer=layer, difficulty=difficulty, k_scope=scope, status=status,
                    compared_image_k_cells=len(g), compared_images=g.pool_id.nunique(), compared_buildings=g.building.nunique(),
                    old_zero_new_positive_cells=len(h), affected_images=h.pool_id.nunique(), affected_buildings=h.building.nunique(),
                    old_zero_cells=int(g[old_count].eq(0).sum()),
                    newly_observed_failed_path_occurrences=int(h[new_count].sum()),
                    affected_pool_ids="|".join(sorted(h.pool_id.unique())),
                    interpretation="descriptive discoveries among fixed images; image-k cells are not independent images",
                ))
    return pd.DataFrame(records)


def component_interval_readout(source, meta):
    records = []
    source = source[source.cohort.isin(VERSIONS)]
    for panel, layer, difficulty, m in populations(meta):
        intervals = [(3, 6), (6, 10), (10, 20), (20, 30), (30, 35)]
        for ka, kb in intervals:
            eligible = m[m.pool_n.ge(kb)]
            if panel == "fixed_N_ge_30" and kb > 30:
                continue
            if eligible.empty:
                continue
            d = source[source.pool_id.isin(eligible.pool_id) & source.k.isin([ka, kb])]
            for component, z in d.groupby("component"):
                common = set(eligible.pool_id)
                for version in PRIMARY:
                    for k in [ka, kb]:
                        common &= set(z.loc[z.cohort.eq(version) & z.k.eq(k) & z["mean"].notna(), "pool_id"])
                for version in VERSIONS:
                    g = z[z.cohort.eq(version) & z.pool_id.isin(common)]
                    wide = g.pivot(index="pool_id", columns="k", values="mean")
                    if ka not in wide or kb not in wide:
                        continue
                    vals = (wide[kb] - wide[ka]).dropna()
                    h = eligible[eligible.pool_id.isin(vals.index)]
                    records.append(dict(
                        panel=panel, layer=layer, difficulty=difficulty, cohort=version,
                        k_from=ka, k_to=kb, component=component,
                        candidate_images=len(eligible), images=len(vals), buildings=h.building.nunique(),
                        mean_change=vals.mean(), median_change=vals.median(), p10_change=vals.quantile(.1), p90_change=vals.quantile(.9),
                        positive_images=int(vals.gt(1e-10).sum()), negative_images=int(vals.lt(-1e-10).sum()), zero_images=int(vals.abs().le(1e-10).sum()),
                        support_rule="same images at both k in old48,new208,pooled256; A/B restricted to this support",
                        interpretation="B8 block is a dimensionless loss, lower better; no additive Q attribution" if component.startswith("B8_") else "frozen raw scalar",
                    ))
    return pd.DataFrame(records)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    src = root / "analysis_precision26/results_stage2"
    gate = json.loads((src / "NATURAL_FINALIZATION_COMPLETE.json").read_text())
    assert gate["complete"] and gate["pools"] == 194
    curve = pd.read_csv(src / "NATURAL_CURVES.csv.gz")
    meta = curve[["pool_id", "image", "building", "layer", "difficulty", "pool_n"]].drop_duplicates("pool_id")
    assert len(meta) == 194
    # Do not assume the doorway layer spelling: verify against the frozen table.
    assert set(meta.layer) == {"ordinary_manual", "doorway_manual"}, sorted(meta.layer.unique())
    receipts = []
    pairs = [
        ("FINAL_READOUT_WHOLE_CURVE_PRECISION.csv", band_readout(pd.read_csv(src / "NATURAL_CURVE_BAND_SUMMARY.csv.gz"), meta)),
        ("FINAL_READOUT_POINT_REVISIONS.csv", per_point_changes(pd.read_csv(src / "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz"), meta)),
        ("FINAL_READOUT_NEW_FAILURES.csv", new_failure_readout(pd.read_csv(src / "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz"), meta)),
        ("FINAL_READOUT_MATCHED_COMPONENT_INTERVALS.csv", component_interval_readout(pd.read_csv(src / "NATURAL_COMPONENTS.csv.gz"), meta)),
    ]
    for filename, frame in pairs:
        receipts.append(save_csv(frame, src / filename))
    save_json(dict(complete=True, pools=194, new_fusion=False, new_resampling=False,
                   purpose="compact deterministic report readout of final saved estimates",
                   sources=["NATURAL_CURVES.csv.gz", "NATURAL_CURVE_BAND_SUMMARY.csv.gz",
                            "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz", "NATURAL_COMPONENTS.csv.gz"],
                   outputs=receipts), src / "FINAL_READOUT_RECEIPT.json")


if __name__ == "__main__":
    main()
