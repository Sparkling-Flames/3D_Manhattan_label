#!/usr/bin/env python3
"""Strict common-context Q/QT size analysis; no fusion or policy fitting.

Run from any cwd; input/output paths default to this package.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = "v21_history_reselected_fixed_candidates"
Q, QT = "outside_Q", "outside_Q_outside_T_fast"
CTX = ["pair_id", "source_pool_id", "target_pool_id", "domain"]
SIZES = {"all_sizes_3_to_13": [3, 4, 5, 6, 7, 9, 13],
         "early_sizes_3_to_7": [3, 4, 5, 6, 7]}
METRICS = ["q_only", "q_time", "delta_q", "abs_delta_q", "loss_gt2", "loss_gt5",
           "loss_gt10", "log_labor_ratio", "joint_save20_loss_atmost2", "q_time_scored",
           "q_only_scored", "both_scored", "q_time_fusion_failure", "q_only_fusion_failure",
           "q_time_measurement_unavailable", "q_time_unavailable_or_loss_gt5",
           "identical_team", "replaced_fraction", "history_q_gap", "labor_q", "labor_qt"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.12g")


def levels(d, metrics):
    im = d.groupby(["building", "target_image"], sort=True)[metrics].mean()
    bu = im.groupby("building", sort=True).mean()
    return im, bu


def summarize(d, panel, metric_rows, image_rows, building_rows, leave_rows, seed):
    """Common resampling seed at each n yields synchronized building draws."""
    for n, x in d.groupby("n", sort=True):
        im, bu = levels(x, METRICS)
        image_rows.append(im.reset_index().assign(panel=panel, n=n))
        building_rows.append(bu.reset_index().assign(panel=panel, n=n))
        rng = np.random.default_rng(seed)
        draws = rng.integers(0, len(bu), size=(20000, len(bu)))
        for m in METRICS:
            vals = bu[m].to_numpy()
            # All reported principal metrics have a value in every building.
            assert np.isfinite(vals).all(), (panel, n, m, vals)
            boot = vals[draws].mean(axis=1)
            lo, hi = np.quantile(boot, [.025, .975])
            avg = vals.mean()
            is_log = m == "log_labor_ratio"
            out_m = "labor_ratio" if is_log else m
            transform = np.exp if is_log else lambda y: y
            valid = x[m].notna()
            row = dict(panel=panel, n=int(n), metric=out_m,
                       value=transform(avg), boot_lo=transform(lo), boot_hi=transform(hi),
                       total_contexts=len(x), valid_contexts=int(valid.sum()),
                       total_images=x.target_image.nunique(), valid_images=x.loc[valid, "target_image"].nunique(),
                       total_buildings=x.building.nunique(), valid_buildings=len(bu),
                       image_equal=transform(im[m].mean()),
                       positive_images=int((im[m] > 1e-9).sum()),
                       negative_images=int((im[m] < -1e-9).sum()),
                       zero_images=int((im[m].abs() <= 1e-9).sum()))
            metric_rows.append(row)
            for b in bu.index:
                leave_rows.append(dict(panel=panel, n=int(n), metric=out_m,
                                       omitted_building=b, value=transform(bu.loc[bu.index != b, m].mean())))


def main():
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=root / "inputs/HOHONET_v21_full_chain_20261030/stage05_selection_stop/selection")
    ap.add_argument("--output", type=Path, default=root / "results")
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    files = ["POLICY_EVENT_RESULTS.csv.gz", "RELATION_FLAGS.csv", "QT_N_SENSITIVITY.csv"]
    inputs = {f: dict(sha256=digest(args.input/f), bytes=(args.input/f).stat().st_size) for f in files}
    raw = pd.read_csv(args.input/files[0], low_memory=False)
    flags = pd.read_csv(args.input/files[1])
    assert not flags.pair_id.duplicated().any()
    d = raw[(raw.version == VERSION) & (raw.domain == "new_timed_history") &
            (raw.layer == "ordinary_manual") & raw.scope_comparable & raw.policy.isin([Q, QT])].copy()
    d = d.merge(flags[["pair_id", "relation_oos_pending", "relation_substantive_conflict", "direct_adopted"]],
                on="pair_id", how="left", validate="many_to_one")
    assert not d.relation_oos_pending.isna().any()
    d = d[d.direct_adopted & ~d.relation_oos_pending & ~d.relation_substantive_conflict].copy()
    assert not d.duplicated(CTX + ["n", "policy"]).any()
    assert d.condition.eq("manual").all()
    # Stable candidate identity within context is stronger than same target-image support.
    candidate_counts = d.groupby(CTX).available_worker_ids.nunique()
    assert candidate_counts.eq(1).all()
    assert d.groupby(CTX).available_workers.nunique().eq(1).all()
    assert (d.available_workers > d.n).all()
    for r in d.itertuples():
        members=set(r.member_workers.split('|'))
        candidates=set(r.available_worker_ids.split('|'))
        assert len(members)==r.n and members <= candidates
        assert len(candidates)==r.available_workers
    q = d[d.policy == Q].copy()
    qt = d[d.policy == QT].copy()
    cols = CTX + ["n", "B8L2", "target_activity_seconds", "team_key", "member_workers", "history_Q_mean",
                  "observed_fusion_failure", "measurement_unavailable"]
    pair = qt.merge(q[cols], on=CTX + ["n"], suffixes=("_qt", "_q"), how="outer", validate="one_to_one", indicator=True)
    assert pair._merge.eq("both").all()
    assert np.allclose(pair.B8L2_q, pair.base_B8L2, equal_nan=True)
    assert np.allclose(pair.target_activity_seconds_q, pair.base_target_activity_seconds, equal_nan=True)
    pair["q_only"] = pair.B8L2_q
    pair["q_time"] = pair.B8L2_qt
    pair["delta_q"] = pair.q_time - pair.q_only
    assert np.allclose(pair.delta_q, pair.delta_Q, equal_nan=True)
    pair["abs_delta_q"] = pair.delta_q.abs()
    pair["both_scored"] = (pair.q_time.notna() & pair.q_only.notna()).astype(float)
    for k in (2, 5, 10):
        pair[f"loss_gt{k}"] = np.where(pair.both_scored.eq(1), pair.delta_q < -k, np.nan)
    pair["log_labor_ratio"] = np.log(pair.target_activity_seconds_qt / pair.target_activity_seconds_q)
    assert np.isfinite(pair.log_labor_ratio).all()
    assert np.allclose(pair.log_labor_ratio, pair.log_activity_ratio)
    pair["joint_save20_loss_atmost2"] = np.where(pair.both_scored.eq(1),
        (pair.log_labor_ratio <= np.log(.8)) & (pair.delta_q >= -2), np.nan)
    pair["q_time_scored"] = pair.q_time.notna().astype(float)
    pair["q_only_scored"] = pair.q_only.notna().astype(float)
    pair["q_time_fusion_failure"] = pair.observed_fusion_failure_qt
    pair["q_only_fusion_failure"] = pair.observed_fusion_failure_q
    pair["q_time_measurement_unavailable"] = pair.measurement_unavailable_qt
    # This explicitly labelled composite never assigns zero Q to a failed team.
    pair["q_time_unavailable_or_loss_gt5"] = np.where(pair.q_only.notna(),
        pair.q_time.isna() | (pair.delta_q < -5), np.nan)
    pair["identical_team"] = pair.team_key_qt.eq(pair.team_key_q).astype(float)
    pair["replaced_fraction"] = [len(set(t.split('|')) - set(b.split('|'))) / n
        for t,b,n in zip(pair.member_workers_qt, pair.member_workers_q, pair.n)]
    pair["history_q_gap"] = pair.history_Q_mean_qt - pair.history_Q_mean_q
    assert (pair.history_q_gap >= -2-1e-9).all()
    pair["labor_q"] = pair.target_activity_seconds_q
    pair["labor_qt"] = pair.target_activity_seconds_qt
    # Reproduce the author's varying-support table before creating new estimates.
    reference = pd.read_csv(args.input/"QT_N_SENSITIVITY.csv")
    reference = reference[(reference.relation_layer == "no_pending_direct_relations") &
                          (reference.version == VERSION) & (reference.policy == QT)]
    validation_rows = []
    for _, r in reference.iterrows():
        x = pair[pair.n == r.n]
        im, bu = levels(x, ["q_time", "delta_q", "abs_delta_q", "loss_gt5", "log_labor_ratio", "q_time_scored"])
        for theirs, ours in [("B8L2", "q_time"), ("delta_Q", "delta_q"),
                             ("absolute_delta_Q", "abs_delta_q"), ("loss_over5", "loss_gt5"),
                             ("log_activity_ratio", "log_labor_ratio"), ("Q_available_rate", "q_time_scored")]:
            err = float(bu[ours].mean()-r[theirs])
            assert abs(err) < 1e-10, (r.n, theirs, err)
            validation_rows.append(dict(n=int(r.n), metric=theirs, reference=r[theirs], reconstructed=bu[ours].mean(), error=err))
        assert (len(x), x.target_image.nunique(), x.building.nunique()) == (r.events, r.images, r.buildings)
    write(pd.DataFrame(validation_rows), out/"REFERENCE_REPRODUCTION.csv")
    metrics, images, buildings, leaves, supports, transitions, transition_events, diagnostic = [], [], [], [], [], [], [], []
    panel_frames = []
    # Existing variable support is a reference, not pooled into common-support claims.
    summarize(pair, "varying_support_reference", metrics, images, buildings, leaves, 20261030)
    for panel, sizes in SIZES.items():
        z = pair[pair.n.isin(sizes)].copy()
        counts = z.groupby(CTX).n.nunique()
        eligible = counts[counts.eq(len(sizes))].index
        keep = pd.MultiIndex.from_frame(z[CTX]).isin(eligible)
        z = z.loc[keep].copy()
        assert z.groupby(CTX).size().eq(len(sizes)).all()
        z["panel"] = panel
        panel_frames.append(z)
        summarize(z, panel, metrics, images, buildings, leaves, 20261030)
        # All-sizes complete-case panel is supplementary; no failed contexts disappear from main panel.
        score_complete = z.groupby(CTX).both_scored.min().eq(1)
        good = score_complete[score_complete].index
        cc = z[pd.MultiIndex.from_frame(z[CTX]).isin(good)].copy()
        summarize(cc, panel+"__all_scored", metrics, images, buildings, leaves, 20261030)
        # Exploratory diagnostic prompted by the observed small relative tail at n13:
        # does this mean better absolute quality, or a lower Q-only benchmark too?
        # Restrict to ALL-sizes complete cases; do not use it to select optimal n.
        if panel == "all_sizes_3_to_13":
            a = cc[cc.n.eq(5)]
            b = cc[cc.n.eq(13)]
            c = a.merge(b,on=CTX,suffixes=("_5","_13"),validate="one_to_one")
            c["building"],c["target_image"] = c.building_5,c.target_image_5
            for policy in ["only","time"]:
                c[f"delta_Q_{policy}"] = c[f"q_{policy}_13"]-c[f"q_{policy}_5"]
            for policy in ["q","qt"]:
                c[f"log_labor_growth_{policy}"] = np.log(c[f"labor_{policy}_13"]/c[f"labor_{policy}_5"])
            ms=["delta_Q_only","delta_Q_time","log_labor_growth_q","log_labor_growth_qt"]
            ci,cb=levels(c,ms)
            for m in ms:
                vals=cb[m].to_numpy()
                rng=np.random.default_rng(20261030)
                boot=vals[rng.integers(0,len(vals),(20000,len(vals)))].mean(axis=1)
                lo,hi=np.quantile(boot,[.025,.975])
                tr=np.exp if m.startswith("log_") else lambda x:x
                diagnostic.append(dict(panel=panel+"__all_scored",n_from=5,n_to=13,metric=m,
                    value=tr(vals.mean()),boot_lo=tr(lo),boot_hi=tr(hi),contexts=len(c),
                    images=c.target_image.nunique(),buildings=c.building.nunique(),
                    positive_images=int((ci[m]>1e-9).sum()),negative_images=int((ci[m]<-1e-9).sum()),
                    zero_images=int((ci[m].abs()<=1e-9).sum()),
                    positive_buildings=int((cb[m]>1e-9).sum()),negative_buildings=int((cb[m]<-1e-9).sum())))
            write(c[CTX+["building","target_image"]+ms],out/"EXPLORATORY_N5_N13_EVENTS.csv")
        roster = z[z.n.eq(sizes[0])][CTX + ["building", "source_image", "target_image", "available_workers", "available_worker_ids", "difficulty"]].copy()
        roster["panel"] = panel
        roster["all_sizes_both_policies_scored"] = pd.MultiIndex.from_frame(roster[CTX]).isin(good)
        supports.append(roster)
        for a, b in zip(sizes[:-1], sizes[1:]):
            aa, bb = z[z.n.eq(a)].copy(), z[z.n.eq(b)].copy()
            t = aa.merge(bb, on=CTX, suffixes=("_a", "_b"), validate="one_to_one")
            t["building"] = t.building_a
            t["target_image"] = t.target_image_a
            valid = t.both_scored_a.eq(1) & t.both_scored_b.eq(1)
            t["change_q_only"] = (t.q_only_b-t.q_only_a).where(valid)
            t["change_q_time"] = (t.q_time_b-t.q_time_a).where(valid)
            t["change_delta_q"] = (t.delta_q_b-t.delta_q_a).where(valid)
            t["log_qt_labor_growth"] = np.log(t.labor_qt_b/t.labor_qt_a)
            t["log_q_labor_growth"] = np.log(t.labor_q_b/t.labor_q_a)
            for policy in ["q", "qt"]:
                t[f"nested_{policy}"] = [float(set(x.split('|')) <= set(y.split('|')))
                    for x,y in zip(t[f"member_workers_{policy}_a"], t[f"member_workers_{policy}_b"])]
            ms = ["change_q_only", "change_q_time", "change_delta_q", "log_qt_labor_growth", "log_q_labor_growth", "nested_q", "nested_qt"]
            ti, tb = levels(t, ms)
            for m in ms:
                vals = tb[m].dropna().to_numpy()
                rng = np.random.default_rng(20261030)
                boot = vals[rng.integers(0,len(vals),(20000,len(vals)))].mean(axis=1)
                lo,hi = np.quantile(boot,[.025,.975])
                trans = np.exp if m.startswith("log_") else lambda x:x
                transitions.append(dict(panel=panel, n_from=a, n_to=b, metric=m,
                    value=trans(vals.mean()), boot_lo=trans(lo), boot_hi=trans(hi),
                    total_contexts=len(t), valid_contexts=int(t[m].notna().sum()),
                    valid_images=int(ti[m].notna().sum()), valid_buildings=len(vals)))
            transition_events.append(t[CTX+["building","target_image"]+ms].assign(panel=panel,n_from=a,n_to=b))
    metric_df = pd.DataFrame(metrics)
    write(metric_df, out/"COMMON_SUPPORT_SUMMARY.csv")
    write(pd.concat(images, ignore_index=True), out/"COMMON_SUPPORT_IMAGES.csv")
    write(pd.concat(buildings, ignore_index=True), out/"COMMON_SUPPORT_BUILDINGS.csv")
    leave_df = pd.DataFrame(leaves)
    write(leave_df, out/"LEAVE_ONE_BUILDING_OUT.csv")
    leave_range = leave_df.groupby(["panel","n","metric"]).value.agg(["min","max"]).reset_index()
    write(leave_range, out/"LEAVE_ONE_BUILDING_RANGE.csv")
    write(pd.concat(supports,ignore_index=True), out/"COMMON_CONTEXT_ROSTER.csv")
    write(pd.DataFrame(transitions), out/"ADJACENT_SIZE_PAIRED_CHANGES.csv")
    write(pd.DataFrame(diagnostic), out/"EXPLORATORY_N5_N13_ABSOLUTE_CONTRAST.csv")
    write(pd.concat(transition_events, ignore_index=True), out/"ADJACENT_SIZE_EVENT_CHANGES.csv.gz")
    selected = CTX + ["panel","n","building","source_image","target_image","available_workers","difficulty",
                     "team_key_q","team_key_qt","member_workers_q","member_workers_qt"] + METRICS
    write(pd.concat(panel_frames,ignore_index=True)[selected], out/"COMMON_CONTEXT_EVENTS.csv.gz")
    # Building allocation quantifies the empirical support; shared workers do not make independent replications.
    coverage = pd.concat(supports,ignore_index=True).groupby(["panel","building"]).agg(
        contexts=("target_image","size"), images=("target_image","nunique"),
        candidates_min=("available_workers","min"), candidates_max=("available_workers","max"),
        all_sizes_scored_contexts=("all_sizes_both_policies_scored","sum")).reset_index()
    write(coverage, out/"BUILDING_COVERAGE.csv")
    plot(metric_df, out)
    validation = dict(status="passed", source_commit="13a7861334749805a86dc19e9ea79fcaa71020c0",
        inputs=inputs, source_event_rows=len(raw), filtered_policy_event_rows=len(d), paired_context_size_rows=len(pair),
        reference_reproduction_cells=len(validation_rows), max_reference_error=max(abs(x['error']) for x in validation_rows),
        assertions=["unique context-size-policy identities", "constant exact candidate roster across size and policy",
        "all candidate pools strictly larger than selected size", "distinct selected members equal n and subset of exact candidates",
        "direct adopted relations, no pending/conflict",
        "Q-only join reproduces author's baseline score/time", "historical Q mean constraint <=2 respected",
        "42 original table cells reproduced to <1e-10", "no missing Q filled as zero", "complete size coverage"],
        bootstrap=dict(repetitions=20000,seed=20261030,unit="building",kind="empirical percentile sensitivity, not population-valid confidence guarantee"),
        versions=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__),
        script_sha256=digest(__file__), new_fusion_endpoints=0, policy_fitting_or_parameter_tuning=False)
    (out/"VALIDATION.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(validation,ensure_ascii=False,indent=2))


def plot(df,out):
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/v21_common_support_mpl")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/v21_common_support_cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,axs=plt.subplots(1,3,figsize=(13,4),layout="constrained")
    panels=[("varying_support_reference","Original varying support","#999999"),
            ("all_sizes_3_to_13","Fixed contexts, n=3–13","#1565c0"),
            ("early_sizes_3_to_7","Fixed contexts, n=3–7","#b35c00")]
    specs=[("delta_q","Q/T minus Q-only (Q points)",0,1),
           ("labor_ratio","Recorded labor ratio (Q/T / Q-only)",1,1),
           ("loss_gt5","Paired scored Q loss >5 (%)",None,100)]
    for ax,(m,title,ref,scale) in zip(axs,specs):
        for panel,label,color in panels:
            z=df[(df.panel==panel)&(df.metric==m)].sort_values('n')
            ax.plot(z.n,z.value*scale,marker='o',label=label,color=color,lw=1.5)
            if panel=="all_sizes_3_to_13":
                ax.fill_between(z.n,z.boot_lo*scale,z.boot_hi*scale,color=color,alpha=.13)
        if ref is not None: ax.axhline(ref,color='#555555',ls='--',lw=.8)
        ax.set(title=title,xlabel="Team size n",xticks=[3,4,5,6,7,9,13])
        ax.grid(alpha=.15)
    axs[0].legend(loc='lower left',fontsize=8)
    fig.suptitle("Existing-history Q/QT replay: fixing source→target context and candidate roster",fontsize=12)
    fig.savefig(out/"COMMON_SUPPORT_SIZE_CURVES.png",dpi=180)
    fig.savefig(out/"COMMON_SUPPORT_SIZE_CURVES.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
