#!/usr/bin/env python3
"""Fixed-support summaries, independent-batch comparisons and curve precision.

The resampling columns distinguish path Monte Carlo error (fixed images) from
building resampling (fixed estimated image curves). Missing bootstrap image
values invalidate that draw; remaining images are never reweighted silently.
"""
from pathlib import Path
import argparse, gc, json, os
for _env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_env] = "1"
import numpy as np
import pandas as pd
from precision_core import (META, METRICS, IMETRICS, TOL, seed_for, boot_summary,
                            save_csv, save_json, interval_definitions, curve_band)

PANELS = ["all_available_at_k", "fixed_N_ge_30", "fixed_N_ge_35"]
PRIMARY = ["old48", "new208", "pooled256"]


def groups(meta, min_n=0):
    d = meta[meta.pool_n.ge(min_n)]
    for layer, g in d.groupby("layer", sort=True):
        yield layer, "全部" if layer == "ordinary_manual" else "单列", g
        for difficulty, h in g.groupby("difficulty", dropna=False, sort=True):
            if layer == "ordinary_manual":
                yield layer, str(difficulty), h


def weights_and_building_draws(building, weighting, B, seed):
    labels, inverse = np.unique(building, return_inverse=True)
    counts = np.bincount(inverse); n = len(building); nb = len(labels)
    weights = np.repeat(1 / n, n) if weighting == "image_equal" else 1 / (nb * counts[inverse])
    rng = np.random.default_rng(seed)
    bw = rng.multinomial(nb, np.repeat(1 / nb, nb), size=B)
    if weighting == "image_equal":
        iw = bw[:, inverse].astype(float)
        iw /= (bw @ counts)[:, None]
    else:
        iw = bw[:, inverse].astype(float) / (nb * counts[inverse])[None]
    return weights, iw


def estimate(x, boot, building, weighting, B, seed):
    assert np.isfinite(x).all()
    labels, inverse = np.unique(building, return_inverse=True)
    counts = np.bincount(inverse); nb = len(labels)
    weights = np.repeat(1 / len(x), len(x)) if weighting == "image_equal" else 1 / (nb * counts[inverse])
    rng = np.random.default_rng(seed)
    bw = rng.multinomial(nb, np.repeat(1 / nb, nb), size=B)
    sums = np.bincount(inverse, weights=x)
    # NaN deliberately propagates: fixed observed support does not change
    # between resamples. boot is image x replicate.
    path = np.sum(boot * weights[:, None], axis=0)
    # Same generated building counts as the image-weight matrix formulation,
    # but avoid allocating B x images for each scalar cell.
    bdraw = (bw @ sums) / (bw @ counts) if weighting == "image_equal" else (bw @ (sums / counts)) / nb
    ps = boot_summary(path); bs = boot_summary(bdraw)
    return dict(estimate=float(weights @ x), images=len(x), buildings=len(set(building)),
                positive_images=int((x > TOL).sum()), negative_images=int((x < -TOL).sum()),
                near_zero_images=int((np.abs(x) <= TOL).sum()),
                image_median=float(np.median(x)), image_p10=float(np.quantile(x, .1)),
                image_p90=float(np.quantile(x, .9)),
                path_MCSE=ps["MCSE"], path95_low=ps["low"], path95_high=ps["high"],
                path_valid_draws=ps["valid"], path_requested_draws=B,
                building_MCSE=bs["MCSE"], building95_low=bs["low"], building95_high=bs["high"],
                building_requested_draws=B, building_resample_identifiable=len(set(building)) >= 2)


def observed_lookup(frame, key_fields, metrics):
    values = frame[metrics].to_numpy(float)
    keys = frame[key_fields].itertuples(index=False, name=None)
    return dict(zip(keys, values))


def curve_precision_tables(curve, out, filename="PRECISION_REACH_BY_LAYER_K.csv.gz"):
    rows = []
    for cohort, c in curve.groupby("cohort", sort=False):
        for panel in PANELS:
            cutoff = int(panel.rsplit("_", 1)[-1]) if panel.startswith("fixed_") else None
            d = c[c.pool_n.ge(cutoff) & c.k.le(cutoff)] if cutoff else c
            for layer, g0 in d.groupby("layer", sort=False):
                diffs = [("全部" if layer == "ordinary_manual" else "单列", g0)]
                if layer == "ordinary_manual":
                    diffs += [(str(dif), z) for dif, z in g0.groupby("difficulty", dropna=False)]
                for difficulty, h in diffs:
                    for k, g in h.groupby("k", sort=True):
                        qse = g.Q_mean_MCSE_analytic
                        pwidth = g.P10_linear_boot_halfwidth
                        rwidth = g.P10_order_halfwidth
                        actual_attempt = g.actual_executed_nondeferred_paths.gt(0)
                        fail_cp_half = (g.actual_consensus_failure_CP_high - g.actual_consensus_failure_CP_low) / 2
                        output_cp_half = (g.output_unscoreable_CP_high - g.output_unscoreable_CP_low) / 2
                        zero_consensus = actual_attempt & g.actual_consensus_failure_paths.eq(0)
                        zero_output = actual_attempt & g.output_unscoreable_paths.eq(0)
                        zero_upper = g.loc[zero_consensus, "actual_consensus_failure_one_sided_CP_high"]
                        rows.append(dict(cohort=cohort, panel=panel, layer=layer, difficulty=difficulty, k=int(k),
                                         images=len(g), buildings=g.building.nunique(),
                                         mean_mcse_estimable_images=int(qse.notna().sum()),
                                         mean_mcse_gt1_images=int(qse.gt(1).sum()),
                                         mean_mcse_median=float(qse.median()), mean_mcse_p90=float(qse.quantile(.9)),
                                         P10_boot_estimable_images=int(pwidth.notna().sum()),
                                         P10_boot_halfwidth_gt2_images=int(pwidth.gt(2).sum()),
                                         P10_boot_halfwidth_median=float(pwidth.median()),
                                         P10_rank_estimable_images=int(rwidth.notna().sum()),
                                         P10_rank_halfwidth_gt2_images=int(rwidth.gt(2).sum()),
                                         P10_rank_halfwidth_median=float(rwidth.median()),
                                         zero_observed_failures_images=int((g.nondeferred_attempts.gt(0) & g.failure_paths.eq(0)).sum()),
                                         actual_failure_estimable_images=int(actual_attempt.sum()),
                                         zero_observed_consensus_failures_images=int(zero_consensus.sum()),
                                         zero_observed_output_unscoreable_images=int(zero_output.sum()),
                                         consensus_failure_CP_halfwidth_median=float(fail_cp_half.median()),
                                         consensus_failure_CP_halfwidth_p90=float(fail_cp_half.quantile(.9)),
                                         output_unscoreable_CP_halfwidth_median=float(output_cp_half.median()),
                                         output_unscoreable_CP_halfwidth_p90=float(output_cp_half.quantile(.9)),
                                         zero_consensus_one_sided95_upper_median=float(zero_upper.median()),
                                         zero_consensus_one_sided95_upper_max=float(zero_upper.max()),
                                         zero_failure_fullN_exact_images=int((zero_consensus & g.fullN_single_known_team).sum()),
                                         all_paths_unscoreable_images=int((actual_attempt & g.quality_valid_paths.eq(0)).sum()),
                                         no_observed_Q_images_including_deferred=int(g.quality_valid_paths.eq(0).sum())))
    return save_csv(pd.DataFrame(rows), out / filename)


def observed_comparisons(curve, interval, out):
    cvars = set(curve.cohort)
    comparisons = [("new208", "old48"), ("pooled256", "old48"),
                   ("stage2_104", "stage1_104"), ("pooled256", "pooled152"),
                   ("all_history304", "pooled256"), ("stage1_104", "old48"),
                   ("pooled152", "old48")]
    rows = []
    for newer, older in comparisons:
        if not {newer, older} <= cvars:
            continue
        a = curve[curve.cohort.eq(older)]; b = curve[curve.cohort.eq(newer)]
        z = a.merge(b, on=["pool_id", "k"], suffixes=("_old", "_new"), validate="one_to_one")
        for r in z.to_dict("records"):
            row = {key: r[key] if key == "pool_id" else r[key + "_old"] for key in META}
            row.update(k=int(r["k"]), older_cohort=older, newer_cohort=newer,
                       old_paths=r["paths_attempted_old"], new_paths=r["paths_attempted_new"],
                       old_Q_valid=r["quality_valid_paths_old"], new_Q_valid=r["quality_valid_paths_new"],
                       old_failures=r["failure_paths_old"], new_failures=r["failure_paths_new"],
                       new_failure_seen_after_zero_old=bool(r["failure_paths_old"] == 0 and r["failure_paths_new"] > 0),
                       old_actual_consensus_failures=r["actual_consensus_failure_paths_old"],
                       new_actual_consensus_failures=r["actual_consensus_failure_paths_new"],
                       old_output_unscoreable=r["output_unscoreable_paths_old"],
                       new_output_unscoreable=r["output_unscoreable_paths_new"],
                       new_consensus_failure_seen_after_zero_old=bool(r["actual_executed_nondeferred_paths_old"] > 0 and
                           r["actual_consensus_failure_paths_old"] == 0 and r["actual_consensus_failure_paths_new"] > 0),
                       new_output_unscoreable_seen_after_zero_old=bool(r["actual_executed_nondeferred_paths_old"] > 0 and
                           r["output_unscoreable_paths_old"] == 0 and r["output_unscoreable_paths_new"] > 0),
                       old_Q_mean_MCSE=r["Q_mean_MCSE_analytic_old"], new_Q_mean_MCSE=r["Q_mean_MCSE_analytic_new"],
                       old_P10_boot_halfwidth=r["P10_linear_boot_halfwidth_old"],
                       new_P10_boot_halfwidth=r["P10_linear_boot_halfwidth_new"],
                       old_P10_rank_halfwidth=r["P10_order_halfwidth_old"], new_P10_rank_halfwidth=r["P10_order_halfwidth_new"])
            for metric in METRICS:
                row[metric + "_old"] = r[metric + "_old"]
                row[metric + "_new"] = r[metric + "_new"]
                row[metric + "_difference"] = r[metric + "_new"] - r[metric + "_old"]
            for name in ["Q_mean_MCSE", "P10_boot_halfwidth", "P10_rank_halfwidth"]:
                old_width, new_width = row["old_" + name], row["new_" + name]
                row[name + "_new_over_old"] = new_width / old_width if pd.notna(old_width) and old_width > 0 else np.nan
                row[name + "_old_zero_new_positive"] = bool(pd.notna(old_width) and old_width == 0 and pd.notna(new_width) and new_width > 0)
            row["old_empirical_Q_constant_new_variable"] = bool(abs(r["Q_sd_ddof1_old"]) <= 1e-12 and r["Q_sd_ddof1_new"] > 1e-12)
            rows.append(row)
    if not rows:
        return []
    receipt = save_csv(pd.DataFrame(rows), out / "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz")
    curve_rows = []
    d = pd.DataFrame(rows)
    for (newer, older, pid), g in d.groupby(["newer_cohort", "older_cohort", "pool_id"], sort=False):
        meta = {c: g[c].iloc[0] for c in META}
        for metric in ["Q_mean", "Q_p10", "Q_sd_ddof1", "failure_rate"]:
            x = g[metric + "_difference"]
            valid = x.notna() & g.k.ne(2)
            h = g[valid]
            if h.empty:
                continue
            xx = x[valid]
            mx = int(xx.abs().idxmax())
            curve_rows.append({**meta, "newer_cohort": newer, "older_cohort": older, "metric": metric,
                               "comparable_k_n": len(h), "comparable_k": "|".join(map(str, h.k)),
                               "max_absolute_change": float(xx.abs().max()),
                               "k_at_max_absolute_change": int(g.loc[mx, "k"]),
                               "signed_change_at_max": float(x.loc[mx]),
                               "mean_absolute_change_over_k": float(xx.abs().mean()),
                               "rms_change_over_k": float(np.sqrt(np.mean(xx * xx))),
                               "k_abs_change_gt1": int(xx.abs().gt(1).sum()),
                               "k_abs_change_gt2": int(xx.abs().gt(2).sum()),
                               "k_abs_change_gt5": int(xx.abs().gt(5).sum())})
    r2 = save_csv(pd.DataFrame(curve_rows), out / "PER_IMAGE_FULL_CURVE_BATCH_DIFFERENCES.csv.gz")
    return [receipt, r2]


def component_summaries(components, out):
    """Frozen quality subcomponents with fixed common support and analytic MCSE.

    No additive attribution of the nonlinear Q score is implied. Old-versus-
    pooled MC errors are dependent; only independent new208-minus-old48 gets
    the sum-of-variances contrast diagnostic.
    """
    versions = set(components.cohort)
    main_versions = [c for c in PRIMARY if c in versions]
    if len(main_versions) < 2:
        main_versions = [c for c in ["old48", "stage1_104", "pooled152"] if c in versions]
    good = components[components["mean"].notna()].copy()
    counts = good[good.cohort.isin(main_versions)].groupby(["pool_id", "k", "component"]).cohort.nunique()
    common = set(counts[counts.eq(len(main_versions))].index)
    rows = []
    for cohort in versions:
        cc = good[good.cohort.eq(cohort)]
        cc = cc[[tuple(x) in common for x in cc[["pool_id", "k", "component"]].to_numpy()]]
        for panel in PANELS:
            cutoff = int(panel.rsplit("_", 1)[-1]) if panel.startswith("fixed_") else 0
            d = cc[cc.pool_n.ge(cutoff) & cc.k.le(cutoff)] if cutoff else cc
            for (layer, component, k), h0 in d.groupby(["layer", "component", "k"], sort=False):
                subsets = [("全部" if layer == "ordinary_manual" else "单列", h0)]
                if layer == "ordinary_manual":
                    subsets += [(str(diff), h) for diff, h in h0.groupby("difficulty", dropna=False)]
                for diff, h in subsets:
                    nb = h.building.nunique(); bsize = h.groupby("building").size()
                    for weighting in ["image_equal", "building_equal"]:
                        w = np.repeat(1 / len(h), len(h)) if weighting == "image_equal" else 1 / (nb * h.building.map(bsize).to_numpy())
                        rows.append(dict(cohort=cohort, panel=panel, layer=layer, difficulty=diff,
                                         k=int(k), component=component, weighting=weighting,
                                         images=len(h), buildings=nb, estimate=float(w @ h["mean"]),
                                         MCSE=float(np.sqrt(np.sum(w * w * h.MCSE.to_numpy() ** 2))),
                                         support_rule="common " + "|".join(main_versions),
                                         interpretation="B8 loss block: lower better" if component.startswith("B8_") else "saved frozen scalar"))
    return save_csv(pd.DataFrame(rows), out / "QUALITY_COMPONENT_COMMON_SUPPORT_SUMMARY.csv.gz")


def independent_interval_repetition(intervals, out):
    """Independent old/new and A/B slopes; zeros never count as active agreement."""
    available = set(intervals.cohort)
    pairs = [("new208", "old48"), ("stage2_104", "stage1_104")]
    thresholds = {"marginal_Q_delta": [0., 1.], "Q_p10_delta": [0., 2.],
                  "Q_sd_delta": [0., 1.], "failure_delta": [0., .01],
                  "actual_consensus_failure_delta": [0., .01]}
    rows = []
    for newer, older in pairs:
        if not {newer, older} <= available:
            continue
        z = intervals[intervals.cohort.eq(older)].merge(intervals[intervals.cohort.eq(newer)],
             on=["pool_id", "interval"], suffixes=("_old", "_new"), validate="one_to_one")
        for metric, ts in thresholds.items():
            if metric + "_old" not in z:
                continue
            for threshold in ts:
                for r in z.to_dict("records"):
                    a, b = r[metric + "_old"], r[metric + "_new"]
                    if not np.isfinite(a) or not np.isfinite(b):
                        state = "unestimable_one_or_both"
                    else:
                        t = TOL if threshold == 0 else threshold
                        sa = 1 if a > t else -1 if a < -t else 0
                        sb = 1 if b > t else -1 if b < -t else 0
                        if sa == sb == 0:
                            state = "both_near_zero"
                        elif sa == 0 or sb == 0:
                            state = "one_active_one_near_zero"
                        elif sa == sb:
                            state = "both_active_same_direction"
                        else:
                            state = "both_active_opposite_direction"
                    row = {c: r[c] if c == "pool_id" else r[c + "_old"] for c in META}
                    row.update(interval=r["interval"], k_from=r["k_from_old"], k_to=r["k_to_old"],
                               older_cohort=older, newer_cohort=newer, metric=metric, threshold=threshold,
                               old_effect=a, new_effect=b, response_class=state)
                    rows.append(row)
    if not rows:
        return []
    d = pd.DataFrame(rows)
    r1 = save_csv(d, out / "INDEPENDENT_INTERVAL_REPETITION_PER_IMAGE.csv.gz")
    summaries = []
    for key, h in d.groupby(["older_cohort", "newer_cohort", "interval", "metric", "threshold", "layer"], sort=False):
        older, newer, name, metric, threshold, layer = key
        subsets = [("全部" if layer == "ordinary_manual" else "单列", h)]
        if layer == "ordinary_manual":
            subsets += [(str(diff), g) for diff, g in h.groupby("difficulty", dropna=False)]
        for difficulty, g in subsets:
            counts = g.response_class.value_counts()
            both_active = counts.get("both_active_same_direction", 0) + counts.get("both_active_opposite_direction", 0)
            summaries.append(dict(older_cohort=older, newer_cohort=newer, interval=name, metric=metric,
                                  threshold=threshold, layer=layer, difficulty=difficulty,
                                  images=len(g), buildings=g.building.nunique(),
                                  both_near_zero=int(counts.get("both_near_zero", 0)),
                                  one_active_one_near_zero=int(counts.get("one_active_one_near_zero", 0)),
                                  both_active_same_direction=int(counts.get("both_active_same_direction", 0)),
                                  both_active_opposite_direction=int(counts.get("both_active_opposite_direction", 0)),
                                  unestimable_one_or_both=int(counts.get("unestimable_one_or_both", 0)),
                                  same_direction_fraction_all_images=counts.get("both_active_same_direction", 0) / len(g),
                                  both_active_images=int(both_active),
                                  same_direction_fraction_conditional_both_active=(counts.get("both_active_same_direction", 0) / both_active if both_active else np.nan)))
    return [r1, save_csv(pd.DataFrame(summaries), out / "INDEPENDENT_INTERVAL_REPETITION_SUMMARY.csv")]


def load_boot(out, meta, cohort, B, max_n, interval_names):
    curve = np.full((len(meta), B, max_n, len(METRICS)), np.nan, dtype=np.float32)
    ints = np.full((len(meta), B, len(interval_names), len(IMETRICS)), np.nan, dtype=np.float32)
    for i, r in enumerate(meta.to_dict("records")):
        path = out / "bootstrap_cache" / (r["pool_id"] + ".npz")
        with np.load(path, allow_pickle=False) as z:
            if "curve_" + cohort not in z.files:
                continue
            a = z["curve_" + cohort]
            assert a.shape[0] == B
            curve[i, :, :a.shape[1]] = a
            ix = [interval_names.index(name) for name in z["interval_names"]]
            v = z["interval_" + cohort]
            for j, dest in enumerate(ix):
                ints[i, :, dest] = v[:, j]
    return curve, ints


def common_observed_mask(table, versions, key_fields, metrics):
    output = {}
    for metric in metrics:
        sets = []
        for cohort in versions:
            d = table[table.cohort.eq(cohort) & table[metric].notna()]
            sets.append(set(map(tuple, d[key_fields].to_numpy())))
        output[metric] = set.intersection(*sets) if sets else set()
    return output


def summarize(out, curve, intervals, B, master, final):
    meta = curve[META].drop_duplicates("pool_id").sort_values("pool_id").reset_index(drop=True)
    indices = {pid: i for i, pid in enumerate(meta.pool_id)}
    meta_indexed = meta.set_index("pool_id")
    cvars = list(dict.fromkeys(curve.cohort))
    main_versions = PRIMARY if final else [c for c in ["old48", "stage1_104", "pooled152"] if c in cvars]
    if not main_versions:
        main_versions = ["old48"]
    support = common_observed_mask(curve, main_versions, ["pool_id", "k"], METRICS)
    isupport = common_observed_mask(intervals, main_versions, ["pool_id", "interval"], IMETRICS)
    common_rows = []
    for metric, keys in support.items():
        common_rows += [dict(kind="curve", pool_id=pid, k=k, interval="", metric=metric,
                            common_cohorts="|".join(main_versions)) for pid, k in sorted(keys)]
    for metric, keys in isupport.items():
        common_rows += [dict(kind="interval", pool_id=pid, k=np.nan, interval=name, metric=metric,
                            common_cohorts="|".join(main_versions)) for pid, name in sorted(keys)]
    support_receipt = save_csv(pd.DataFrame(common_rows), out / "COMMON_SUPPORT_KEYS.csv.gz")
    int_names = list(dict.fromkeys(intervals.interval))
    max_n = int(meta.pool_n.max()); summaries, isum, changes, ichanges = [], [], [], []
    aggregate_bands, aggregate_band_summary = [], []
    base_boot = None; base_iboot = None; stage1_boot = None; stage1_iboot = None
    cohorts = [c for c in ["old48", "stage1_104", "stage2_104", "new208", "pooled152", "pooled256", "prior96", "all_history304"] if c in cvars]
    curve_lookups = {c: observed_lookup(curve[curve.cohort.eq(c)], ["pool_id", "k"], METRICS) for c in cohorts}
    interval_lookups = {c: observed_lookup(intervals[intervals.cohort.eq(c)], ["pool_id", "interval"], IMETRICS) for c in cohorts}
    for cohort in cohorts:
        print("aggregate cohort", cohort, flush=True)
        cb, ib = load_boot(out, meta, cohort, B, max_n, int_names)
        cc = curve_lookups[cohort]
        ii = interval_lookups[cohort]
        # Entire mean-of-image curve on one fixed set of images and k values.
        # This is distinct from the pointwise common support below, and from
        # uncertainty of any individual image's curve.
        for cutoff in [27, 30, 35]:
            ks = np.array([k for k in range(1, cutoff + 1) if k != 2])
            for layer, difficulty, mg in groups(meta, cutoff):
                if cutoff == 27 and layer != "doorway_manual":
                    continue
                for metric in ["Q_mean", "Q_p10", "Q_sd_ddof1", "actual_consensus_failure_rate"]:
                    mi = METRICS.index(metric)
                    pids = [p for p in mg.pool_id if all((p, int(k)) in support[metric] and
                            (p, int(k)) in cc and np.isfinite(cc[(p, int(k))][mi]) for k in ks)]
                    if not pids:
                        continue
                    gx = meta_indexed.loc[pids]
                    x = np.array([[cc[(p, int(k))][mi] for k in ks] for p in pids])
                    boot = cb[[indices[p] for p in pids], :, :, mi][:, :, ks - 1]
                    for weighting in ["image_equal", "building_equal"]:
                        w, bw = weights_and_building_draws(gx.building.to_numpy(), weighting, B,
                            seed_for(master, "wholecurve", cutoff, layer, difficulty, metric, "building"))
                        obs = w @ x
                        pb = np.sum(boot * w[:, None, None], axis=0)
                        bb = bw @ x
                        for uncertainty, draws in [("paths_fixed_images", pb), ("buildings_fixed_path_estimates", bb)]:
                            bandrow, band = curve_band(obs, draws, ks, np.repeat(max(2, len(pids)), len(ks)), -1)
                            common = dict(cohort=cohort, panel="fixed_N_ge_" + str(cutoff), layer=layer,
                                          difficulty=difficulty, metric=metric, weighting=weighting,
                                          uncertainty=uncertainty, images=len(pids), buildings=gx.building.nunique(),
                                          capacity_images=len(mg), excluded_pool_ids="|".join(sorted(set(mg.pool_id) - set(pids))),
                                          support_rule="fixed images across all legal k and " + "|".join(main_versions))
                            aggregate_band_summary.append({**common, **bandrow})
                            for ki, k in enumerate(ks):
                                point = boot_summary(draws[:, ki])
                                aggregate_bands.append({**common, "k": int(k), "estimate": obs[ki],
                                                        "max_absolute_low": band[ki, 0], "max_absolute_high": band[ki, 1],
                                                        "max_studentized_low": band[ki, 2], "max_studentized_high": band[ki, 3],
                                                        "pointwise_low": point["low"], "pointwise_high": point["high"],
                                                        "pointwise_MCSE": point["MCSE"], "pointwise_valid_draws": point["valid"],
                                                        "complete_bootstrap_draws": bandrow["complete_bootstrap_draws"]})
        for panel in PANELS:
            cutoff = int(panel.rsplit("_", 1)[-1]) if panel.startswith("fixed_") else 0
            limit = cutoff or max_n
            for k in range(1, limit + 1):
                for layer, difficulty, mg in groups(meta, max(cutoff, k)):
                    pids0 = list(mg.pool_id)
                    for mi, metric in enumerate(METRICS):
                        pids = [p for p in pids0 if (p, k) in support[metric] and
                                (p, k) in cc and np.isfinite(cc[(p, k)][mi])]
                        if not pids:
                            continue
                        gx = meta_indexed.loc[pids]
                        x = np.array([cc[(p, k)][mi] for p in pids], float)
                        boot = cb[[indices[p] for p in pids], :, k - 1, mi]
                        for weighting in ["image_equal", "building_equal"]:
                            s = estimate(x, boot, gx.building.to_numpy(), weighting, B,
                                         seed_for(master, panel, layer, difficulty, k, metric, "buildings"))
                            summaries.append(dict(cohort=cohort, panel=panel, layer=layer, difficulty=difficulty,
                                                  k=k, metric=metric, weighting=weighting,
                                                  support_rule="common " + "|".join(main_versions),
                                                  **s))
        for name in int_names:
            # capacity_all uses all images eligible for this interval; fixed30
            # additionally restricts the same N>=30 inventory for early/late comparisons.
            for panel, cutoff in [("interval_eligible", 0), ("fixed_N_ge_30", 30), ("fixed_N_ge_35", 35)]:
                for layer, difficulty, mg in groups(meta, cutoff):
                    pids0 = list(mg.pool_id)
                    for mi, metric in enumerate(IMETRICS):
                        pids = [p for p in pids0 if (p, name) in isupport[metric] and
                                (p, name) in ii and np.isfinite(ii[(p, name)][mi])]
                        if not pids:
                            continue
                        gx = meta_indexed.loc[pids]
                        x = np.array([ii[(p, name)][mi] for p in pids], float)
                        boot = ib[[indices[p] for p in pids], :, int_names.index(name), mi]
                        for weighting in ["image_equal", "building_equal"]:
                            s = estimate(x, boot, gx.building.to_numpy(), weighting, B,
                                         seed_for(master, panel, layer, difficulty, name, metric, "buildings"))
                            isum.append(dict(cohort=cohort, panel=panel, layer=layer, difficulty=difficulty,
                                             interval=name, metric=metric, weighting=weighting,
                                             support_rule="common " + "|".join(main_versions), **s))
        # Dependent old-versus-pooled contrast uses identical old resample
        # weights, whereas new208-versus-old48 is genuinely independent.
        contrasts = []
        if cohort == "old48":
            base_boot, base_iboot = cb, ib
        elif base_boot is not None and cohort not in ["prior96", "all_history304"]:
            contrasts.append(("old48", base_boot, base_iboot))
        if cohort == "stage1_104":
            stage1_boot, stage1_iboot = cb, ib
        elif cohort == "stage2_104" and stage1_boot is not None:
            contrasts.append(("stage1_104", stage1_boot, stage1_iboot))
        for older, oldcb, oldib in contrasts:
            oldc = curve_lookups[older]
            oldi = interval_lookups[older]
            for k in range(1, min(35, max_n) + 1):
                for layer, difficulty, mg in groups(meta, max(30, k)):
                    for mi, metric in enumerate(METRICS):
                        pids = [p for p in mg.pool_id if (p, k) in cc and (p, k) in oldc and
                                np.isfinite(cc[(p, k)][mi]) and np.isfinite(oldc[(p, k)][mi])]
                        if not pids:
                            continue
                        idx = [indices[p] for p in pids]; gx = meta_indexed.loc[pids]
                        x = np.array([cc[(p, k)][mi] - oldc[(p, k)][mi] for p in pids])
                        boot = cb[idx, :, k - 1, mi] - oldcb[idx, :, k - 1, mi]
                        for weighting in ["image_equal", "building_equal"]:
                            s = estimate(x, boot, gx.building.to_numpy(), weighting, B,
                                         seed_for(master, "contrast", layer, difficulty, k, metric, "buildings"))
                            changes.append(dict(newer_cohort=cohort, older_cohort=older,
                                                panel="fixed_N_ge_30" if k <= 30 else "eligible_N_ge_k",
                                                layer=layer, difficulty=difficulty, k=k, metric=metric,
                                                weighting=weighting, **s))
            for name in int_names:
                for layer, difficulty, mg in groups(meta, 0):
                    for mi, metric in enumerate(IMETRICS):
                        pids = [p for p in mg.pool_id if (p, name) in ii and (p, name) in oldi and
                                np.isfinite(ii[(p, name)][mi]) and np.isfinite(oldi[(p, name)][mi])]
                        if not pids:
                            continue
                        idx = [indices[p] for p in pids]; gx = meta_indexed.loc[pids]
                        x = np.array([ii[(p, name)][mi] - oldi[(p, name)][mi] for p in pids])
                        boot = ib[idx, :, int_names.index(name), mi] - oldib[idx, :, int_names.index(name), mi]
                        for weighting in ["image_equal", "building_equal"]:
                            s = estimate(x, boot, gx.building.to_numpy(), weighting, B,
                                         seed_for(master, "contrast", layer, difficulty, name, metric, "buildings"))
                            ichanges.append(dict(newer_cohort=cohort, older_cohort=older,
                                                 panel="interval_eligible", layer=layer, difficulty=difficulty,
                                                 interval=name, metric=metric, weighting=weighting, **s))
        # Checkpoint after every cohort; large bootstrap arrays are working
        # data only and excluded from delivery archives.
        save_csv(pd.DataFrame(summaries), out / "COMMON_SUPPORT_CURVE_SUMMARY.csv.gz")
        save_csv(pd.DataFrame(isum), out / "COMMON_SUPPORT_INTERVAL_SUMMARY.csv.gz")
        if changes:
            save_csv(pd.DataFrame(changes), out / "BATCH_CURVE_CONTRAST_SUMMARY.csv.gz")
        if ichanges:
            save_csv(pd.DataFrame(ichanges), out / "BATCH_INTERVAL_CONTRAST_SUMMARY.csv.gz")
        if aggregate_bands:
            save_csv(pd.DataFrame(aggregate_bands), out / "FIXED_IMAGE_AGGREGATE_CURVE_BANDS.csv.gz")
            save_csv(pd.DataFrame(aggregate_band_summary), out / "FIXED_IMAGE_AGGREGATE_CURVE_BAND_SUMMARY.csv")
        if cohort == "stage2_104":
            stage1_boot = stage1_iboot = None
        if cohort not in ["old48", "stage1_104"]:
            del cb, ib
        gc.collect()
    return [support_receipt]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--stage", type=int, choices=[0, 1, 2], default=2)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--master-seed", type=int, default=2026102607)
    ap.add_argument("--descriptive-only", action="store_true")
    args = ap.parse_args(); root = args.root.resolve()
    out = root / "analysis_precision26" / ("results_stage" + str(args.stage))
    analysis_receipt = json.loads((out / "ANALYSIS_RECEIPT.json").read_text())
    curve = pd.read_csv(out / "NATURAL_CURVES.csv.gz", low_memory=False)
    intervals = pd.read_csv(out / "NATURAL_INTERVALS.csv.gz", low_memory=False)
    receipts = [curve_precision_tables(curve, out)]
    focus_ids = set(curve.loc[curve.cohort.eq("prior96"), "pool_id"])
    if focus_ids:
        receipts.append(curve_precision_tables(curve[curve.pool_id.isin(focus_ids)], out,
                                               "PRIOR_FOCUS_MATCHED_PRECISION_REACH.csv.gz"))
    receipts += observed_comparisons(curve, intervals, out)
    receipts += independent_interval_repetition(intervals, out)
    component_path = out / "NATURAL_COMPONENTS.csv.gz"
    if component_path.exists():
        receipts.append(component_summaries(pd.read_csv(component_path, low_memory=False), out))
    if not args.descriptive_only:
        receipts += summarize(out, curve, intervals, args.bootstrap, args.master_seed, args.stage == 2)
    save_json(dict(stage=args.stage, pools=int(curve.pool_id.nunique()), cohorts=sorted(curve.cohort.unique()),
                   complete_requested_pool_support=analysis_receipt.get("complete_requested_pool_support", False),
                   expected_pools=analysis_receipt.get("expected_pools", 194),
                   bootstrap=args.bootstrap, bootstrap_master_seed=args.master_seed,
                   source_commit="b9bcec809fbaec8ab055931a1abb7baa5db44dac", outputs=receipts,
                   common_support="Fixed observed metric support across comparison versions; no bootstrap skip-renormalize"),
              out / "SUMMARY_RECEIPT.json")


if __name__ == "__main__":
    main()
