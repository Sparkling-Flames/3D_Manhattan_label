#!/usr/bin/env python3
"""Full-curve natural-path precision, using saved frozen endpoint results.

Example:
  python analysis_precision26/analyze_natural.py --root . --stage 2 --bootstrap 2000
No generation of new random permutations or fusion occurs here. Per-pool
results are checkpointed atomically; --resume skips completed checkpoints.
"""
from pathlib import Path
import argparse, gc, hashlib, json, os, sys, time
for _env in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_env] = "1"
import numpy as np
import pandas as pd
import scipy
from scipy.stats import t
from precision_core import (META, COMP, RAW, BOOL, STATUS, METRICS, IMETRICS,
    COHORTS, STRATUM_COUNTS, numeric, arrays, concatenate_arrays, weighted_stats,
    weighted_mean, weighted_intervals, interval_definitions, bootstrap_weights,
    boot_summary, quantile_order_interval, binomial_precision, curve_band,
    save_csv, save_json, write_bytes, verify_weighted_bootstrap, seed_for, read_csv_exact_seeds)
from precision_core import add_frozen_blocks

NATURAL = "natural_random"
LAYERS = ["ordinary_manual", "doorway_manual"]
PRIOR_BASE = "research/workers/personnel_population_curves_v2_20261023"
SOURCE_COLUMNS = set(META + COMP + RAW + BOOL + STATUS +
                     ["path_id", "team_key", "k", "policy", "batch", "new_index", "stage",
                      "endpoint_execution", "actual_consensus_failure", "output_generated_unscorable", "reference_unavailable"])


def read_selected(path, label=None):
    header = pd.read_csv(path, nrows=0).columns
    use = [c for c in header if c in SOURCE_COLUMNS]
    chunks = []
    for d in pd.read_csv(path, usecols=use, chunksize=50000, low_memory=False):
        if "policy" in d:
            d = d[d.policy.eq(NATURAL)]
        if "layer" in d:
            d = d[d.layer.isin(LAYERS)]
        if not d.empty:
            chunks.append(d)
    if not chunks:
        return pd.DataFrame(columns=use)
    d = pd.concat(chunks, ignore_index=True)
    for c in set(RAW + COMP + BOOL).intersection(d.columns):
        d[c] = numeric(d[c])
    if label:
        d["stratum"] = label
    return d


def enrich_old(d, scalar_path):
    """Reuse existing scalar component/status fields; never rescore old Q."""
    header = pd.read_csv(scalar_path, nrows=0).columns
    requested = [c for c in COMP + STATUS + BOOL if c in header and
                 (c not in d or d[c].isna().any())]
    keys = set(d.team_key)
    parts = []
    for s in pd.read_csv(scalar_path, usecols=["team_key"] + requested,
                         chunksize=50000, low_memory=False):
        parts.append(s[s.team_key.isin(keys)])
    s = pd.concat(parts, ignore_index=True).drop_duplicates("team_key").set_index("team_key")
    for c in requested:
        found = d.team_key.map(s[c])
        if c not in d:
            d[c] = found
        else:
            d[c] = d[c].where(d[c].notna(), found)
    for c in set(RAW + COMP + BOOL).intersection(d.columns):
        d[c] = numeric(d[c])
    return d


def prepare_prior(root, cache_dir):
    """Build small per-pool working cache once; it is not a new deliverable input."""
    receipt_path = cache_dir / "READY.json"
    if receipt_path.exists():
        return json.loads(receipt_path.read_text())["pool_ids"]
    old_path = root / "repo" / PRIOR_BASE / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz"
    prior_path = root / "inputs_cache26/precision25/NEW_PREFIX_VALUES_COMPACT.csv.gz"
    old = read_selected(old_path, "old24")
    old = enrich_old(old, root / "inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz")
    prior = read_selected(prior_path)
    prior["stratum"] = prior.batch.map({"balanced_new24": "prior_new24", "focus_new48": "prior_focus48"})
    assert prior.stratum.notna().all(), prior.batch.unique()
    pids = sorted(prior.pool_id.unique())
    old = old[old.pool_id.isin(pids)]
    d = pd.concat([old, prior], ignore_index=True)
    rows = []
    for pid, g in d.groupby("pool_id", sort=True):
        path = cache_dir / (pid + ".csv.gz")
        receipt = save_csv(g, path); rows.append(receipt)
    save_json(dict(pool_ids=pids, old_path=str(old_path), prior_path=str(prior_path),
                   purpose="transient per-pool analysis cache; no fusion", files=rows), receipt_path)
    return pids


def status_class(row):
    """Explicit observed status taxonomy, with unknowns preserved."""
    def yes(name):
        x = row.get(name, np.nan)
        return pd.notna(x) and bool(float(x))
    if yes("policy_deferred") or row.get("k") == 2:
        return "contract_deferred_k2"
    s = str(row.get("score_status", "")).lower()
    if str(row.get("endpoint_execution", "")) == "not_executed" or s in {"not_computed", "not_executed", "pending", "unexecuted"}:
        return "not_executed"
    if pd.notna(row.get("B8L2", np.nan)):
        return "scoreable"
    if s in {"floor_only_reference", "missing_reference", "reference_unavailable"} or any(x in s for x in ("reference_missing", "reference_paused", "gt_paused", "no_reference")):
        return "reference_unavailable"
    if s in {"fusion_exception", "below_four", "no_connection"} or yes("below_four"):
        return "consensus_not_formed"
    if s in {"invalid_floor", "invalid_full_geometry", "measurement_exception", "invalid_geometry", "nonfinite_score", "score_error"}:
        return "output_unscoreable"
    if yes("score_failure_nonpolicy"):
        connection = row.get("connection_available", np.nan)
        if pd.notna(connection) and not bool(float(connection)):
            return "consensus_not_formed"
        return "failure_other_preserved"
    return "unclassified_or_missing_status"


def per_pool(pid, g, out, B, master, stage, exact_keys=None):
    n = int(g.pool_n.iloc[0]); ks = np.arange(1, n + 1)
    g = add_frozen_blocks(g, out.parent.parent)
    g["status_class"] = [status_class(r) for r in g.to_dict("records")]
    for native_flag, label in [("actual_consensus_failure", "consensus_not_formed"),
                               ("output_generated_unscorable", "output_unscoreable"),
                               ("reference_unavailable", "reference_unavailable")]:
        if native_flag in g:
            native = numeric(g[native_flag]); known = native.notna()
            assert (g.loc[known, "status_class"].eq(label).to_numpy() == native[known].eq(1).to_numpy()).all(), (pid, native_flag, "status definition differs from native contract")
    for column, target in [("consensus_unformed_nonpolicy", "consensus_not_formed"),
                           ("output_unscoreable_nonpolicy", "output_unscoreable"),
                           ("reference_unavailable_nonpolicy", "reference_unavailable"),
                           ("not_executed_nonpolicy", "not_executed")]:
        g[column] = g.status_class.eq(target).astype(float)
    meta = {c: g[c].dropna().iloc[0] if c in g and g[c].notna().any() else None for c in META}
    meta["pool_n"] = n
    strata = {}
    wstrata = {}
    for name, sg in g.groupby("stratum", sort=True):
        assert not sg.duplicated(["path_id", "k"]).any(), (pid, name, "duplicate prefix")
        paths = sorted(sg.path_id.unique())
        assert len(paths) == STRATUM_COUNTS[name], (pid, name, len(paths))
        assert len(sg) == len(paths) * n, (pid, name, "missing prefix", len(sg))
        assert sg.groupby("path_id").k.nunique().eq(n).all()
        strata[name] = dict(frame=sg, arrays=arrays(sg, paths, ks), paths=paths)
        wstrata[name] = bootstrap_weights(pid, name, len(paths), B, master)
    records, intervals, components, statuses, bands, curve_summary = [], [], [], [], [], []
    cache = dict(ks=ks, metric_names=np.array(METRICS), interval_metric_names=np.array(IMETRICS))
    idefs = interval_definitions(n)
    cache["interval_names"] = np.array([x[0] for x in idefs])
    cache["interval_ks"] = np.array([[x[1], x[2]] for x in idefs])
    available = [c for c, needed in COHORTS.items() if all(s in strata for s in needed)]
    for cohort in available:
        names = COHORTS[cohort]
        gg = g[g.stratum.isin(names)]
        aa = concatenate_arrays([strata[name]["arrays"] for name in names])
        rr = len(aa["B8L2"])
        w0 = np.ones((1, rr), dtype=float)
        wb = np.concatenate([wstrata[name] for name in names], axis=1)
        observed = weighted_stats(aa, w0)[0]
        boot = weighted_stats(aa, wb)
        ivobs = weighted_intervals(aa, w0, observed[None], idefs)[0]
        ivboot = weighted_intervals(aa, wb, boot, idefs)
        cache["curve_" + cohort] = boot.astype(np.float32)
        cache["interval_" + cohort] = ivboot.astype(np.float32)
        cache["observed_" + cohort] = observed
        cache["interval_observed_" + cohort] = ivobs
        validq = np.isfinite(aa["B8L2"]).sum(0)
        scopes = [("all_random_prefix_k", np.ones(n, bool)),
                  ("nonexact_display_k", np.array([(pid, int(k)) not in (exact_keys or set()) for k in ks]))]
        for band_scope, mask in scopes:
            for metric in ["Q_mean", "Q_p10"]:
                mi = METRICS.index(metric)
                bandrow, values = curve_band(observed[:, mi], boot[:, :, mi], ks, validq, n, mask)
                curve_summary.append({**meta, "cohort": cohort, "metric": metric, "band_scope": band_scope,
                                      "bootstrap_requested": B, "paths": rr, **bandrow})
                for ki, k in enumerate(ks):
                    bands.append({**meta, "cohort": cohort, "metric": metric, "band_scope": band_scope, "k": int(k),
                                  "estimate": observed[ki, mi],
                                  "max_absolute_low": values[ki, 0], "max_absolute_high": values[ki, 1],
                                  "max_studentized_low": values[ki, 2], "max_studentized_high": values[ki, 3],
                                  "complete_bootstrap_draws": bandrow["complete_bootstrap_draws"]})
        nonempty_k_count = int(((validq > 0) & (ks != 2)).sum())
        for ki, k in enumerate(ks):
            q = aa["B8L2"][:, ki]; finiteq = q[np.isfinite(q)]; nv = len(finiteq)
            kg = gg[gg.k.eq(k)]
            deferv = aa["policy_deferred"][:, ki]
            nd = np.isfinite(deferv) & (deferv == 0)
            fail = int(np.sum(aa["score_failure_nonpolicy"][nd, ki])); den = int(nd.sum())
            full_exact = k == n and kg.team_key.nunique() == 1
            est = dict(zip(METRICS, observed[ki]))
            row = {**meta, "cohort": cohort, "k": int(k), "paths_attempted": rr,
                   "quality_valid_paths": nv, "unique_teams": int(kg.team_key.nunique()),
                   "nondeferred_attempts": den, "failure_paths": fail,
                   "incomplete_paths": int(np.sum(aa["incomplete_nonpolicy"][nd, ki])),
                   "policy_deferred_paths": int(np.nansum(deferv)), "fullN_single_known_team": bool(full_exact),
                   "finite_population_teams": str(__import__("math").comb(n, int(k))),
                   "bootstrap_requested": B, "precision_target": "pure_uniform_random_path_prefixes", **est}
            row["status_definition_version"] = "population_extension_20261026_v1"
            attempted = nd & (aa["not_executed_nonpolicy"][:, ki] == 0)
            attempted_n = int(attempted.sum())
            row["actual_executed_nondeferred_paths"] = attempted_n
            for raw_name, prefix in [("consensus_unformed_nonpolicy", "actual_consensus_failure"),
                                     ("output_unscoreable_nonpolicy", "output_unscoreable")]:
                f = int(np.sum(aa[raw_name][attempted, ki]))
                row[prefix + "_paths"] = f
                for key, value in binomial_precision(f, attempted_n).items():
                    row[prefix + "_" + key] = f / attempted_n if full_exact and attempted_n else value
            row["reference_unavailable_paths"] = int(np.sum(aa["reference_unavailable_nonpolicy"][nd, ki]))
            row["not_executed_paths"] = int(np.sum(aa["not_executed_nonpolicy"][nd, ki]))
            row["failure_rate_semantics"] = "legacy nondeferred score-unavailable total, not solely consensus failure"
            mcse = float(np.std(finiteq, ddof=1) / np.sqrt(nv)) if nv >= 2 else np.nan
            if full_exact and nv:
                mcse = 0.0
            row["Q_mean_MCSE_analytic"] = mcse
            qhalf = float(t.ppf(.975, nv - 1) * mcse) if nv >= 2 else np.nan
            row["Q_mean_t95_low"] = est["Q_mean"] - qhalf
            row["Q_mean_t95_high"] = est["Q_mean"] + qhalf
            for metric in METRICS:
                bs = boot_summary(boot[:, ki, METRICS.index(metric)])
                # n=1 empirical quantile/mean is not a precision guarantee.
                row.update({metric + "_boot_" + key: value for key, value in bs.items()})
            qi = quantile_order_interval(q)
            qs = quantile_order_interval(q, alpha=.05 / max(1, nonempty_k_count))
            row.update({"P10_order_" + key: value for key, value in qi.items()})
            row.update({"P10_curve_Bonferroni_" + key: value for key, value in qs.items()})
            row["P10_order_interval_target"] = "population inverse CDF; conservative with ties"
            row["P10_linear_boot_halfwidth"] = (row["Q_p10_boot_high"] - row["Q_p10_boot_low"]) / 2
            row["P10_order_halfwidth"] = (qi["high"] - qi["low"]) / 2
            row["conditional_Q_precision_identifiable_from_observed_sample"] = bool(nv >= 2 or (full_exact and nv))
            if nv < 2 and not (full_exact and nv):
                row["P10_linear_boot_halfwidth"] = np.nan
            if full_exact and nv:
                for prefix in ["P10_order_", "P10_curve_Bonferroni_"]:
                    row[prefix + "low"] = row[prefix + "high"] = est["Q_p10"]
                row["P10_order_halfwidth"] = 0.0
            for key, value in binomial_precision(fail, den).items():
                row["failure_" + key] = value
            if full_exact and den:
                for key in ["CP_low", "CP_high", "Wilson_low", "Wilson_high", "one_sided_CP_high"]:
                    row["failure_" + key] = fail / den
            row["zero_failures_finite_exact"] = bool(full_exact and fail == 0)
            row["empirical_constant_Q_nonfull"] = bool(nv >= 2 and np.ptp(finiteq) == 0 and not full_exact)
            records.append(row)
            for status, count in kg.status_class.value_counts(dropna=False).items():
                statuses.append({**meta, "cohort": cohort, "k": int(k), "status_class": status,
                                 "paths": int(count), "all_scheduled_paths": rr,
                                 "nondeferred_paths": den})
            for component in COMP:
                xx = aa[component][:, ki]; xx = xx[np.isfinite(xx)]
                components.append({**meta, "cohort": cohort, "k": int(k), "component": component,
                                   "valid_paths": len(xx), "paths_attempted": rr,
                                   "mean": float(np.mean(xx)) if len(xx) else np.nan,
                                   "sd_ddof1": float(np.std(xx, ddof=1)) if len(xx) > 1 else np.nan,
                                   "MCSE": float(np.std(xx, ddof=1) / np.sqrt(len(xx))) if len(xx) > 1 else np.nan,
                                   "component_projection_version": "frozen_B8L2_D10_named_blocks_20261023_projected_20261026"})
        for j, (name, ka, kb) in enumerate(idefs):
            pair = np.isfinite(aa["B8L2"][:, ka - 1]) & np.isfinite(aa["B8L2"][:, kb - 1])
            row = {**meta, "cohort": cohort, "interval": name, "k_from": ka, "k_to": kb,
                   "paths_attempted": rr, "paired_Q_valid_paths": int(pair.sum()),
                   "from_Q_valid_paths": int(validq[ka - 1]), "to_Q_valid_paths": int(validq[kb - 1]),
                   "bootstrap_requested": B, **dict(zip(IMETRICS, ivobs[j]))}
            for m, metric in enumerate(IMETRICS):
                row.update({metric + "_boot_" + key: value for key, value in boot_summary(ivboot[:, j, m]).items()})
            intervals.append(row)
    tmp = out / "bootstrap_cache" / (pid + ".npz.writing")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "wb") as f:
        np.savez_compressed(f, **cache); f.flush(); os.fsync(f.fileno())
    destination = tmp.with_suffix("")
    os.replace(tmp, destination)
    with np.load(destination, allow_pickle=False) as z:
        assert len(z["ks"]) == n and all("curve_" + c in z.files for c in available)
    path_strata = []
    for name, item in strata.items():
        membership = "|".join(c for c in available if name in COHORTS[c])
        for ordinal, path_id in enumerate(item["paths"]):
            path_strata.append(dict(pool_id=pid, image=meta["image"], building=meta["building"],
                                    path_id=path_id, stratum=name, ordinal_within_stratum=ordinal,
                                    cohort_membership=membership, prefix_k_count=n,
                                    bootstrap_stratum_seed=str(seed_for(master, pid, name, "whole_paths"))))
    tables = {"curves": records, "intervals": intervals, "components": components,
              "status": statuses, "curve_bands": bands, "curve_band_summary": curve_summary,
              "path_strata": path_strata}
    receipts = []
    for stem, rows in tables.items():
        receipts.append(save_csv(pd.DataFrame(rows), out / "pool_checkpoints" / (pid + "__" + stem + ".csv.gz")))
    receipt = dict(pool_id=pid, metadata=meta, cohorts=available, stage=stage, bootstrap=B,
                   bootstrap_master_seed=master, input_rows=len(g), files=receipts,
                   metric_names=METRICS, interval_metric_names=IMETRICS,
                   analysis_schema="natural_curve_precision_20261026_v1")
    save_json(receipt, out / "pool_checkpoints" / (pid + "__DONE.json"))
    return receipt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--stage", type=int, choices=[0, 1, 2], default=2)
    ap.add_argument("--bootstrap", type=int, default=2000)
    ap.add_argument("--master-seed", type=int, default=2026102607)
    ap.add_argument("--pool", action="append", help="Explicit pool ids for smoke run or targeted resume")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--compile-only", action="store_true")
    ap.add_argument("--ready-only", action="store_true", help="Checkpoint only complete pool shards already present; explicitly mark partial support")
    ap.add_argument("--no-compile", action="store_true", help="Incremental per-pool checkpoints only; leave global tables untouched")
    args = ap.parse_args(); root = args.root.resolve()
    out = root / "analysis_precision26" / ("results_stage" + str(args.stage))
    out.mkdir(parents=True, exist_ok=True)
    check = verify_weighted_bootstrap()
    cache = root / "analysis_precision26" / "prior_pool_cache"
    pids = prepare_prior(root, cache)
    ep = root / "prior_recovered" / PRIOR_BASE / "sampling_precision_20261025/analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv"
    exact = pd.read_csv(ep)
    exact_keys = set(map(tuple, exact[exact.exact_complete.eq(True) & exact.k.ne(2)][["pool_id", "k"]].to_numpy()))
    if args.pool:
        assert set(args.pool) <= set(pids)
        pids = sorted(set(args.pool))
    expected_pids = list(pids)
    if args.ready_only and args.stage:
        pids = [pid for pid in pids if all((root / "new_endpoints26" / ("stage" + str(stage)) /
                 "prefix_values" / (pid + ".csv.gz")).exists() for stage in range(1, args.stage + 1))]
        if not pids:
            print(json.dumps(dict(ready_pools=0, expected_pools=len(expected_pids), stage=args.stage)), flush=True)
            return
    receipts = []
    if not args.compile_only:
        for number, pid in enumerate(pids):
            done = out / "pool_checkpoints" / (pid + "__DONE.json")
            if args.resume and done.exists():
                receipt = json.loads(done.read_text())
                assert receipt["bootstrap"] == args.bootstrap and receipt["bootstrap_master_seed"] == args.master_seed
                if (receipt.get("metric_names") == METRICS and receipt.get("interval_metric_names") == IMETRICS
                        and (out / "pool_checkpoints" / (pid + "__path_strata.csv.gz")).exists()):
                    receipts.append(receipt); continue
            chunks = [pd.read_csv(cache / (pid + ".csv.gz"), low_memory=False)]
            for stage in range(1, args.stage + 1):
                path = root / "new_endpoints26" / ("stage" + str(stage)) / "prefix_values" / (pid + ".csv.gz")
                if not path.exists():
                    raise FileNotFoundError(f"Required completed new prefixes absent: {path}")
                nd = read_selected(path, "new104A" if stage == 1 else "new104B")
                chunks.append(nd)
            g = pd.concat(chunks, ignore_index=True)
            for c in set(RAW + COMP + BOOL).intersection(g.columns):
                g[c] = numeric(g[c])
            started = time.time()
            receipt = per_pool(pid, g, out, args.bootstrap, args.master_seed, args.stage, exact_keys)
            receipts.append(receipt)
            print(json.dumps(dict(done=number + 1, total=len(pids), pool_id=pid,
                                  seconds=round(time.time() - started, 2), cohorts=receipt["cohorts"])), flush=True)
            del g, chunks; gc.collect()
    tables = ["curves", "intervals", "components", "status", "curve_bands", "curve_band_summary", "path_strata"]
    if args.compile_only:
        completed = [pid for pid in pids if all((out / "pool_checkpoints" / (pid + "__" + stem + ".csv.gz")).exists() for stem in tables)]
        if len(completed) != len(pids):
            if args.ready_only:
                pids = completed
            else:
                raise FileNotFoundError("Requested pool analysis checkpoints incomplete: " + "|".join(sorted(set(pids) - set(completed))))
        if not pids:
            print(json.dumps(dict(ready_analysis_pools=0, expected_pools=len(expected_pids), stage=args.stage)), flush=True)
            return
    outputs = []
    for stem in ([] if args.no_compile else tables):
        paths = [out / "pool_checkpoints" / (pid + "__" + stem + ".csv.gz") for pid in pids]
        if not all(p.exists() for p in paths):
            continue
        frames = [read_csv_exact_seeds(p) for p in paths]
        outputs.append(save_csv(pd.concat(frames, ignore_index=True), out / ("NATURAL_" + stem.upper() + ".csv.gz")))
    save_json(dict(stage=args.stage, pools=len(pids), pool_ids=pids, bootstrap=args.bootstrap,
                   expected_pools=len(expected_pids), missing_pool_ids=sorted(set(expected_pids) - set(pids)),
                   complete_requested_pool_support=len(pids) == len(expected_pids),
                   bootstrap_master_seed=args.master_seed, fixture=check, outputs=outputs,
                   new_fusion=False, analysis="saved-endpoint whole-path precision",
                   versions=dict(python=sys.version, numpy=np.__version__, pandas=pd.__version__, scipy=scipy.__version__),
                   source_commit="b9bcec809fbaec8ab055931a1abb7baa5db44dac"), out / ("PROGRESS_RECEIPT.json" if args.no_compile else "ANALYSIS_RECEIPT.json"))
    print(json.dumps(dict(analysis_call_finished=True, complete_requested_pool_support=len(pids) == len(expected_pids),
                          stage=args.stage, pools=len(pids), expected_pools=len(expected_pids), output=str(out))), flush=True)


if __name__ == "__main__":
    main()
