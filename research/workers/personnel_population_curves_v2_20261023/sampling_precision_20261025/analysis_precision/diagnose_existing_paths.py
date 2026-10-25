#!/usr/bin/env python3
"""Precision diagnostics for the saved natural permutations; no fusion.

The existing sample is never chosen or dropped according to Q.  Duplicate
prefix teams retain permutation multiplicity.  Exact small-pool catalogues
and the sole full-pool team have zero Monte Carlo error.  Missing scores and
k=2 contract deferral remain separate from actual fusion failures.
"""
from pathlib import Path
import argparse
import hashlib
import json
import warnings
import numpy as np
import pandas as pd
from scipy.stats import beta, binom, t

warnings.filterwarnings("ignore", category=RuntimeWarning)
META = ["pool_id", "image", "building", "condition", "layer", "difficulty", "pool_n"]
METRICS = ["B8L2", "D10", "floor_turn5_n", "floor_redundant5_n", "nodes"]
SEED = 2026102503


def seed_for(kind, key, master=SEED):
    return int.from_bytes(hashlib.sha256(f"{master}|{kind}|{key}".encode()).digest()[:8], "little")


def qlinear(a, p=.1, axis=1):
    """NaN-safe NumPy-linear quantile, vectorized over small path axes."""
    s = np.sort(a, axis=axis)
    count = np.isfinite(a).sum(axis=axis)
    rank = np.maximum(count - 1, 0) * p
    lo = np.floor(rank).astype(int)
    hi = np.ceil(rank).astype(int)
    lv = np.take_along_axis(s, np.expand_dims(lo, axis), axis=axis).squeeze(axis)
    hv = np.take_along_axis(s, np.expand_dims(hi, axis), axis=axis).squeeze(axis)
    return np.where(count > 0, lv + (hv - lv) * (rank - lo), np.nan)


def quantile_order_interval(q, p=.1, alpha=.05):
    """Equal-tailed binomial order-stat CI, with Q's [0,100] support bounds.

    This is conservative for atoms/ties.  It targets a population quantile,
    whereas qlinear is the retained empirical-quantile point estimator.
    """
    v = np.sort(q[np.isfinite(q)])
    n = len(v)
    if not n:
        return (np.nan, np.nan, 0, 0, False, False)
    lr = int(binom.ppf(alpha / 2, n, p))
    ur = int(binom.ppf(1 - alpha / 2, n, p)) + 1
    return (0.0 if lr == 0 else v[lr - 1],
            100.0 if ur > n else v[ur - 1], lr, ur, lr == 0, ur > n)


def binomial_interval(f, n, exact=False, alpha=.05):
    if not n:
        return np.nan, np.nan, np.nan
    p = f / n
    if exact:
        return p, p, p
    lo = 0.0 if f == 0 else beta.ppf(alpha / 2, f, n - f + 1)
    hi = 1.0 if f == n else beta.ppf(1 - alpha / 2, f + 1, n - f)
    hi_one = 1.0 if f == n else beta.ppf(1 - alpha, f + 1, n - f)
    return lo, hi, hi_one


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression="gzip" if path.suffix == ".gz" else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(a.input, low_memory=False)
    d = raw[raw.policy.eq("natural_random")].copy()
    assert not d.duplicated(["pool_id", "path_id", "k"]).any()
    rows, intervals, seeds, genrows = [], [], [], []
    boot_rows = []
    for pi, (pool, g) in enumerate(d.groupby("pool_id", sort=True)):
        paths = sorted(g.path_id.unique())
        ks = sorted(g.k.unique())
        meta = g[META].iloc[0].to_dict()
        r = len(paths)
        arr = {c: g.pivot(index="path_id", columns="k", values=c).reindex(index=paths, columns=ks).to_numpy(float)
               for c in METRICS + ["score_failure_nonpolicy", "incomplete_nonpolicy", "policy_deferred"]}
        exact_catalogue = g.sample_kind.eq("exact_permutation").all()
        seed = seed_for("old_whole_path_precision", pool, a.seed)
        seeds.append({"pool_id": pool, "kind": "old_whole_path_precision", "seed": str(seed), "paths": r, "B": a.bootstrap})
        if a.bootstrap:
            ix = np.random.default_rng(seed).integers(r, size=(a.bootstrap, r))
            qb = arr["B8L2"][ix]
            bstats = {"Q_mean": np.nanmean(qb, 1), "Q_p10": qlinear(qb), "Q_sd_ddof1": np.nanstd(qb, 1, ddof=1)}
        else:
            bstats = {}
        for j, k in enumerate(ks):
            x = g[g.k.eq(k)]
            q = arr["B8L2"][:, j]
            good = np.isfinite(q)
            qn = int(good.sum())
            exact = exact_catalogue or k == int(meta["pool_n"])
            deferred = int(arr["policy_deferred"][:, j].sum())
            attempted = r - deferred
            fail = int(arr["score_failure_nonpolicy"][:, j].sum())
            flo, fhi, fhione = binomial_interval(fail, attempted, exact=exact)
            qmean = np.nanmean(q)
            qsd = np.nanstd(q, ddof=1) if qn > 1 else np.nan
            qse = (0.0 if qn else np.nan) if exact else (qsd / np.sqrt(qn) if qn > 1 else np.nan)
            qlo, qhi, qlr, qur, qlowbound, qupbound = quantile_order_interval(q)
            qp10 = np.nanquantile(q, .1) if qn else np.nan
            if exact:
                qlo = qhi = qp10
                qlowbound = qupbound = False
            row = {**meta, "k": int(k), "paths_attempted": r, "quality_valid_paths": qn,
                   "unique_teams": x.team_key.nunique(), "sample_kind": "exact_permutation" if exact_catalogue else "MC",
                   "finite_team_space": str(__import__("math").comb(int(meta["pool_n"]), int(k))),
                   "mc_exact": exact, "policy_deferred_paths": deferred, "nondeferred_attempts": attempted,
                   "failure_paths": fail, "incomplete_paths": int(arr["incomplete_nonpolicy"][:, j].sum()),
                   "Q_mean": qmean, "Q_p10": qp10, "Q_sd_ddof1": qsd,
                   "Q_mean_MCSE": qse,
                   "Q_mean_t95_halfwidth": (t.ppf(.975, qn-1) * qse if qn > 1 else np.nan),
                   "Q_p10_order95_low": qlo, "Q_p10_order95_high": qhi,
                   "Q_p10_order95_lower_rank": qlr, "Q_p10_order95_upper_rank": qur,
                   "Q_p10_order95_uses_lower_support_bound": qlowbound,
                   "Q_p10_order95_uses_upper_support_bound": qupbound,
                   "failure_rate": fail/attempted if attempted else np.nan,
                   "failure_CP95_low": flo, "failure_CP95_high": fhi, "failure_one_sided95_high": fhione,
                   "estimated_total_valid_paths_for_mean_95halfwidth1": (int(np.ceil((1.96*qsd)**2)) if qn > 1 and not exact else 0),
                   "bootstrap_replicates": a.bootstrap}
            for c in METRICS[1:]:
                v = arr[c][:, j]
                nv = int(np.isfinite(v).sum())
                vs = np.nanstd(v, ddof=1) if nv > 1 else np.nan
                row[c+"_valid_paths"] = nv
                row[c+"_mean"] = np.nanmean(v)
                row[c+"_sd_ddof1"] = vs
                row[c+"_MCSE"] = (0.0 if nv else np.nan) if exact else vs / np.sqrt(nv) if nv > 1 else np.nan
            for m, bb in bstats.items():
                vals = bb[:, j]
                if exact:
                    lo = hi = row[m]
                    se = 0.0
                else:
                    lo, hi = np.nanquantile(vals, [.025, .975])
                    se = np.nanstd(vals, ddof=1)
                row[m+"_boot95_low"] = lo
                row[m+"_boot95_high"] = hi
                row[m+"_boot95_halfwidth"] = (hi-lo)/2
                row[m+"_bootse"] = se
                row[m+"_bootstrap_valid_draws"] = int(np.isfinite(vals).sum())
            rows.append(row)
            for generation, h in x.groupby("generation"):
                vals = h.B8L2.to_numpy(float)
                genrows.append({**meta, "k": int(k), "generation": generation, "paths": len(h),
                                "valid_Q": int(np.isfinite(vals).sum()), "Q_mean": np.nanmean(vals),
                                "Q_p10": np.nanquantile(vals,.1) if np.isfinite(vals).any() else np.nan,
                                "failure_rate": h.score_failure_nonpolicy.mean() if not deferred else np.nan})
        for ka, kb in [(1,3),(3,6),(6,10),(10,20),(20,30),(30,35),(3,20),(3,int(meta["pool_n"])),(int(meta["pool_n"])-1,int(meta["pool_n"]))]:
            if ka not in ks or kb not in ks or ka == kb:
                continue
            ia, ib = ks.index(ka), ks.index(kb)
            qa, qb0 = arr["B8L2"][:,ia], arr["B8L2"][:,ib]
            dq = qb0-qa
            nn = int(np.isfinite(dq).sum())
            sd = np.nanstd(dq,ddof=1) if nn>1 else np.nan
            z = {**meta,"from_k":ka,"to_k":kb,"paths_attempted":r,"both_quality_valid_paths":nn,
                 "paired_Q_delta":np.nanmean(dq),"paired_Q_MCSE":0.0 if exact_catalogue else sd/np.sqrt(nn) if nn>1 else np.nan,
                 "paired_positive_fraction":np.nanmean(np.where(np.isfinite(dq),dq>0,np.nan)),
                 "paired_loss_gt5_fraction":np.nanmean(np.where(np.isfinite(dq),dq < -5,np.nan)),
                 "gained_score_paths":int((~np.isfinite(qa)&np.isfinite(qb0)).sum()),
                 "lost_score_paths":int((np.isfinite(qa)&~np.isfinite(qb0)).sum())}
            if a.bootstrap:
                for m, bb in bstats.items():
                    vals=bb[:,ib]-bb[:,ia]
                    z[m+"_marginal_delta"] = (np.nanmean(qb0)-np.nanmean(qa) if m == "Q_mean" else np.nanquantile(qb0,.1)-np.nanquantile(qa,.1) if m == "Q_p10" else np.nanstd(qb0,ddof=1)-np.nanstd(qa,ddof=1))
                    z[m+"_delta_bootse"] = 0.0 if exact_catalogue else np.nanstd(vals,ddof=1)
                    z[m+"_delta_boot95_low"], z[m+"_delta_boot95_high"] = np.nanquantile(vals,[.025,.975])
                dq_b = dq[ix]
                z["paired_Q_delta_bootse"] = 0.0 if exact_catalogue else np.nanstd(np.nanmean(dq_b,1),ddof=1)
            intervals.append(z)
        if pi % 20 == 0:
            print(f"diagnosed {pi+1} pools", flush=True)
    out=pd.DataFrame(rows)
    save(out,a.out/"OLD_PATH_POOL_K_PRECISION.csv.gz")
    save(pd.DataFrame(intervals).drop_duplicates(["pool_id","from_k","to_k"]),a.out/"OLD_PAIRED_INTERVAL_PRECISION.csv")
    save(pd.DataFrame(genrows),a.out/"OLD4_VS_OLD20_GENERATION_DIAGNOSTIC.csv.gz")
    save(pd.DataFrame(seeds),a.out/"EXACT_DIAGNOSTIC_SEEDS.csv")
    summaries=[]
    for (layer, difficulty),g in out.groupby(["layer","difficulty"]):
        for k in [1,3,4,5,6,8,10,15,20,25,30,34,35]:
            h=g[g.k.eq(k)]
            if not len(h): continue
            z={"layer":layer,"difficulty":difficulty,"k":k,"pools":h.pool_id.nunique(),"buildings":h.building.nunique(),
               "quality_pools":int(h.Q_mean.notna().sum()),"full_pool_count":int(h.k.eq(h.pool_n).sum()),
               "mean_MCSE_median":h.Q_mean_MCSE.median(),"mean_MCSE_p90":h.Q_mean_MCSE.quantile(.9),
               "mean_t95_halfwidth_median":h.Q_mean_t95_halfwidth.median(),
               "mean_t95_halfwidth_le1_fraction":h.Q_mean_t95_halfwidth.le(1).mean(),
               "old_Q_mean_image_equal":h.Q_mean.mean(),"old_Q_p10_image_equal":h.Q_p10.mean(),
               "old_Q_sd_image_equal":h.Q_sd_ddof1.mean(),
               "MCSE_overall_mean_image_equal":np.sqrt(np.nansum(h.Q_mean_MCSE**2))/h.Q_mean.notna().sum(),
               "zero_observed_failure_pools":int(h.failure_paths.eq(0).sum()),
               "failure_image_equal":h.failure_rate.mean(),
               "p10_order95_lower_supportbound_fraction":h.Q_p10_order95_uses_lower_support_bound.mean()}
            if a.bootstrap:
                z.update(p10_boot95_halfwidth_median=h.Q_p10_boot95_halfwidth.median(),
                         p10_boot95_halfwidth_p90=h.Q_p10_boot95_halfwidth.quantile(.9),
                         p10_boot95_halfwidth_le2_fraction=h.Q_p10_boot95_halfwidth.le(2).mean(),
                         MCSE_overall_p10_image_equal=np.sqrt(np.nansum(h.Q_p10_bootse**2))/h.Q_p10.notna().sum())
            summaries.append(z)
    save(pd.DataFrame(summaries),a.out/"OLD_PRECISION_BY_LAYER_DIFFICULTY_K.csv")
    # All selection scores depend solely on old precision, never on new scores.
    rankrows=[]
    for pool,g in out.groupby("pool_id"):
        meta=g[META].iloc[0].to_dict()
        h=g[g.k.between(3, min(10,int(meta["pool_n"])-1))]
        l=g[g.k.between(11,int(meta["pool_n"])-1)]
        q={**meta,"early_mean_MCSE_p75":h.Q_mean_MCSE.quantile(.75),"early_mean_MCSE_max":h.Q_mean_MCSE.max(),
           "late_mean_MCSE_p75":l.Q_mean_MCSE.quantile(.75),"early_failure_max":h.failure_rate.max(),
           "old_only_selection_basis":"early_k3_to10_mean_precision_and_tail_precision_no_new_outcomes"}
        if a.bootstrap:
            q["early_p10_boot95_halfwidth_p75"]=h.Q_p10_boot95_halfwidth.quantile(.75)
            q["late_p10_boot95_halfwidth_p75"]=l.Q_p10_boot95_halfwidth.quantile(.75)
            q["precision_priority_score"]=max(q["early_mean_MCSE_p75"],q["early_p10_boot95_halfwidth_p75"]/3.92)
        else:q["precision_priority_score"]=q["early_mean_MCSE_p75"]
        rankrows.append(q)
    rank=pd.DataFrame(rankrows).sort_values(["layer","difficulty","precision_priority_score"],ascending=[True,True,False])
    rank["precision_rank_within_layer_difficulty"]=rank.groupby(["layer","difficulty"]).cumcount()+1
    save(rank,a.out/"OLD_ONLY_EXTRA_SAMPLING_PRIORITY.csv")
    receipt={"source_commit":"40d0fe62dc62f6f6c12723af10195b7abb7bc9fe","source_input":str(a.input),
             "prefix_rows_read":len(raw),"natural_rows":len(d),"pools":d.pool_id.nunique(),
             "new_fusion":0,"new_random_orders":0,"bootstrap_replicates":a.bootstrap,"seed":a.seed,
             "estimand":"fixed_real_eligible_pool_uniform_permutation_k_prefix; Q conditional on scoreable team",
             "P10":"empirical NumPy linear; distribution-free binomial rank CI additionally",
             "SD":"ddof1; exact finite distribution also reported with retained convention",
             "failure":"all nondeferred attempted paths; no Q zero-fill",
             "bootstrap":"whole paths within pool, same index across all k; not independent added paths",
             "selection_rule":"rank existing-only k3_to10 precision within layer/difficulty; final allocation frozen separately"}
    (a.out/"DIAGNOSTIC_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__ == "__main__":
    main()
