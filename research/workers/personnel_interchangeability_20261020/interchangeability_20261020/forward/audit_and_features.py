#!/usr/bin/env python3
"""History-only extension and independent audit for the 2026-10-20 types.

This reads the adopted 10-building history only. Old analysis outputs and the
scientific input are never modified. No fusion outcome from discovery or
evaluation enters this file. Additional time/geometry features are explicitly
condition-specific; source time units are seconds as supplied by the frozen
evidence, with no invented trimming or conversion.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[2]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (tuple, list, np.ndarray)):
        return [clean(v) for v in x]
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    return x


def js(path, x):
    Path(path).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2,
                                   allow_nan=False) + "\n")


def independent_time_fit(t):
    """Dense constrained worker/task OLS, independent of frozen normal equations."""
    if t.empty:
        return {}
    e = t.groupby(["task", "worker_id"], as_index=False).log_seconds.mean()
    workers = sorted(e.worker_id.unique())
    parent = {w: w for w in workers}
    def root(w):
        while parent[w] != w:
            parent[w] = parent[parent[w]]
            w = parent[w]
        return w
    for _, g in e.groupby("task"):
        ws = g.worker_id.tolist()
        for w in ws[1:]:
            parent[root(w)] = root(ws[0])
    components = {}
    for w in workers:
        components.setdefault(root(w), []).append(w)
    if len(components) > 1:
        out = {}
        for ws in components.values():
            out.update(independent_time_fit(t[t.worker_id.isin(ws)]))
        return out
    tasks = sorted(e.task.unique())
    wi = {w: i for i, w in enumerate(workers)}
    ti = {v: i for i, v in enumerate(tasks)}
    # Last worker coefficient is minus the sum of the others: exact sum-zero.
    a = np.zeros((len(e), len(tasks) + len(workers) - 1))
    for row, r in enumerate(e.itertuples()):
        a[row, ti[r.task]] = 1
        if wi[r.worker_id] == len(workers) - 1:
            a[row, len(tasks):] = -1
        else:
            a[row, len(tasks) + wi[r.worker_id]] = 1
    b = np.linalg.lstsq(a, e.log_seconds.to_numpy(), rcond=None)[0]
    coeff = b[len(tasks):]
    return dict(zip(workers, np.r_[coeff, -coeff.sum()]))


def moments(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    return {"n": len(s), "min_seconds": s.min() if len(s) else None,
            "p01_seconds": s.quantile(.01) if len(s) else None,
            "median_seconds": s.median() if len(s) else None,
            "p99_seconds": s.quantile(.99) if len(s) else None,
            "max_seconds": s.max() if len(s) else None,
            "below_1_second": int((s < 1).sum()),
            "below_5_seconds": int((s < 5).sum()),
            "above_1800_seconds": int((s > 1800).sum()),
            "above_3600_seconds": int((s > 3600).sum())}


def extend(f, d, ex, fn):
    """New features use history data already filtered by caller."""
    f = f.copy().set_index("worker_id", drop=False)
    d = d.merge(ex[["object_id", "bottom_y_mean", "top_y_mean"]],
                on="object_id", validate="one_to_one")
    d["height_log"] = np.log(d.height_mean_ratio.where(d.height_mean_ratio > 0))
    masks = {
        "manual": d.quality_usable & d.condition.eq("manual") & d.quality_use.eq("ordinary_primary"),
        "doorway": d.quality_usable & d.condition.eq("manual") & d.quality_use.eq("doorway_quality"),
        "semi_new": d.quality_usable & d.condition.eq("semi") & d.quality_use.eq("ordinary_primary") & d.origin.eq("new"),
        "semi_v1": d.quality_usable & d.condition.eq("semi") & d.quality_use.eq("ordinary_primary") & d.origin.eq("v1"),
    }
    for difficulty in ["easy", "medium", "hard"]:
        masks["manual_" + difficulty] = masks["manual"] & d.difficulty.eq(difficulty)
    manifests, time_rows, opportunity_rows = {}, [], []
    for name, mask in masks.items():
        f = f.copy()
        a = d[mask].copy()
        min_tasks = 8 if name == "manual" else (6 if name.startswith("manual_") else 4)
        features = {
            "q_effect": ("B8L2", 0), "pair_effect": ("declared_pair_count", 5),
            "bottom_y_effect": ("bottom_y_mean", 5),
            "top_y_effect": ("top_y_mean", 5),
            "height_log_effect": ("height_log", 5),
        }
        fmap = {key: fn["effect"](a, col, ridge=ridge)[0]
                for key, (col, ridge) in features.items()}
        # A matching-record time feature is additional to the inherited Manual
        # time feature. It deliberately does not overwrite t_source_origin_effect.
        t = a[a.source_active_time_seconds.gt(0)].copy()
        t["log_seconds"] = np.log(t.source_active_time_seconds)
        t["task"] = [fn["key"](i, c, o, s) for i, c, o, s in
                     zip(t.image_id, t.condition, t.origin, t.time_source_kind)]
        tmap, checks = {}, {}
        for key, g in t.groupby(["origin", "time_source_kind"]):
            est, meta = fn["effect"](g, "log_seconds")
            independent = independent_time_fit(g)
            discrepancy = max([abs(est[w] - independent[w]) for w in est] or [0])
            assert discrepancy < 1e-8, (name, key, discrepancy)
            tmap.update(est)
            checks[str(key)] = {"fit": meta, "dense_OLS_max_abs_difference": discrepancy}
            time_rows.append(dict(panel=name, origin=key[0], source_kind=key[1],
                                  images=g.image_id.nunique(), buildings=g.building_id.nunique(),
                                  workers=g.worker_id.nunique(), **moments(g.source_active_time_seconds)))
        for w in f.index:
            g, gt = a[a.worker_id.eq(w)], t[t.worker_id.eq(w)]
            good = g.task.nunique() >= min_tasks and g.building_id.nunique() >= 3
            # Conditional times use the same declared count gate as their
            # condition quality, minimum four tasks and three buildings.
            tgood = gt.task.nunique() >= min_tasks and gt.building_id.nunique() >= 3
            for k, v in {"records": len(g), "tasks": g.task.nunique(),
                         "images": g.image_id.nunique(), "buildings": g.building_id.nunique(),
                         "supported": good, "q_abs_mean": g.B8L2.mean(),
                         "q_abs_p10": g.B8L2.quantile(.1), "q_abs_sd": g.B8L2.std()}.items():
                f.loc[w, "cond_" + name + "_" + k] = v
            for feat, mp in fmap.items():
                f.loc[w, "cond_" + name + "_" + feat] = mp.get(w, np.nan) if good else np.nan
            for k, v in {"records": len(gt), "tasks": gt.task.nunique(),
                         "images": gt.image_id.nunique(), "buildings": gt.building_id.nunique(),
                         "supported": tgood, "effect": tmap.get(w, np.nan) if tgood else np.nan,
                         "median_seconds": gt.source_active_time_seconds.median(),
                         "min_seconds": gt.source_active_time_seconds.min(),
                         "max_seconds": gt.source_active_time_seconds.max()}.items():
                f.loc[w, "cond_" + name + "_time_" + k] = v
            opportunity_rows.append(dict(worker_id=w, panel=name, quality_records=len(g),
                                         quality_tasks=g.task.nunique(), quality_buildings=g.building_id.nunique(),
                                         quality_supported=good, time_records=len(gt),
                                         time_tasks=gt.task.nunique(), time_buildings=gt.building_id.nunique(),
                                         time_supported=tgood))
        manifests[name] = {"records": len(a), "images": a.image_id.nunique(),
                           "buildings": a.building_id.nunique(), "time_records": len(t),
                           "quality_supported": int(f["cond_"+name+"_supported"].sum()),
                           "time_supported": int(f["cond_"+name+"_time_supported"].sum()),
                           "gate": {"tasks": min_tasks, "buildings": 3},
                           "time_fit": checks}
    # Condition-specific scope propensities compare responses only. The general
    # inherited scope effect stays intact; no correct-answer score enters labels.
    scope = ex[ex.scope_out.notna()].copy()
    for name, mask in {
        "manual": scope.condition.eq("manual"),
        "semi_new": scope.condition.eq("semi") & scope.origin.eq("new"),
        "semi_v1": scope.condition.eq("semi") & scope.origin.eq("v1"),
    }.items():
        s = scope[mask].copy()
        s["task"] = s.scope_task
        s = s[s.groupby("task").worker_id.transform("nunique") >= 2].copy()
        s["varies"] = s.groupby("task").scope_out.transform("nunique") > 1
        mp, meta = fn["effect"](s, "scope_out", ridge=5)
        for w in f.index:
            g = s[s.worker_id.eq(w)]
            good = len(g) >= 10 and g.building_id.nunique() >= 3 and g[g.varies].task.nunique() >= 2
            for k, v in {"records": len(g), "tasks": g.task.nunique(),
                         "buildings": g.building_id.nunique(),
                         "varying_tasks": g[g.varies].task.nunique(), "supported": good,
                         "effect": mp.get(w, np.nan) if good else np.nan}.items():
                f.loc[w, "cond_" + name + "_scope_" + k] = v
        manifests[name]["scope_fit"] = {"records": len(s), "fit": meta,
            "gate": {"responses": 10, "buildings": 3, "varying_tasks": 2},
            "supported": int(f["cond_"+name+"_scope_supported"].sum())}
    return f.reset_index(drop=True), manifests, time_rows, opportunity_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=BASE / "repo")
    ap.add_argument("--prior", type=Path, default=BASE / "current_main_20261020/research/workers/personnel_composition_study_20261019/analysis")
    ap.add_argument("--followup", type=Path, default=BASE / "current_main_20261020/research/workers/personnel_composition_followup_20261019")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    prior = args.prior
    splitpath = prior / "composition/SPLIT.json"
    split = json.loads(splitpath.read_text())
    buildings = split["history_buildings"]
    old = load_module(prior / "forward/build_forward.py", "prior_forward")
    native, fn = old.upstream_functions(args.repo)
    records_path = args.repo / old.RECORD_SOURCE
    records = json.load(gzip.open(records_path, "rt"))["records"]
    d, ex = old.flatten(records), fn["extra_frame"](records)
    supplied = pd.read_csv(prior / "forward/results/features_train.csv.gz")
    # Filter before estimating or recording outcome-bearing rows.
    d = d[d.building_id.isin(buildings)].copy()
    ex = ex[ex.building_id.isin(buildings)].copy()
    assert set(d.building_id) == set(buildings)
    assert set(ex.building_id).issubset(buildings)
    f, meta = fn["_training_features"](d, ex, supplied.worker_id.tolist(), buildings)
    f, cmeta = old.conditional_features(d, f, buildings, fn, "B8L2")
    f.insert(0, "train_key", supplied.train_key.iloc[0])
    same = []
    for col in supplied.columns:
        x, y = supplied.sort_values("worker_id")[col], f.sort_values("worker_id")[col]
        if pd.api.types.is_numeric_dtype(x) and not pd.api.types.is_bool_dtype(x):
            a, b = x.to_numpy(float), y.to_numpy(float)
            ok = np.allclose(a, b, rtol=0, atol=1e-9, equal_nan=True)
            diff = np.nanmax(np.abs(a-b)) if np.isfinite(a-b).any() else 0
        else:
            ok = x.replace("", np.nan).fillna("NA").reset_index(drop=True).eq(y.replace("", np.nan).fillna("NA").reset_index(drop=True)).all()
            diff = None
        assert ok, (col, diff)
        same.append(dict(field=col, equal=True, max_abs_difference=diff))
    high = f[f.core_supported & f.q_beta.ge(0)]
    supplied_high = pd.read_csv(args.followup / "HIGH_Q_FEATURES.csv")
    assert set(high.worker_id) == set(supplied_high.worker_id)
    for col in supplied_high.columns:
        x = supplied_high.set_index("worker_id")[col] if col != "worker_id" else None
        if x is None:
            continue
        y = f.set_index("worker_id").loc[x.index, col]
        if pd.api.types.is_numeric_dtype(x):
            assert np.allclose(x.to_numpy(float), y.to_numpy(float), rtol=0, atol=1e-9, equal_nan=True), col
        else:
            assert x.fillna("NA").eq(y.fillna("NA")).all(), col
    labels = pd.read_csv(prior / "forward/results/worker_labels.csv.gz")
    high18 = labels[(labels.method_id == "F_rule_Q_quantile_K3") & labels.class_id.eq("C03")]
    time_mask = (d.pool_analysis_eligible & d.condition.eq("manual") & d.ordinary_difficulty_eligible
                 & d.difficulty.isin(["easy", "medium", "hard"]))
    t = d[time_mask & d.source_active_time_seconds.gt(0)].copy()
    t["log_seconds"] = np.log(t.source_active_time_seconds)
    t["task"] = [fn["key"](i,c,o,s) for i,c,o,s in zip(t.image_id,t.condition,t.origin,t.time_source_kind)]
    time_audit = []
    worker_time = []
    for key, g in t.groupby(["origin", "time_source_kind"]):
        independent = independent_time_fit(g)
        checked = f[f.t_supported & f.person_origin.eq(key[0])]
        discrepancy = max([abs(independent[r.worker_id] - r.t_source_origin_effect) for r in checked.itertuples()] or [0])
        assert discrepancy < 1e-8
        time_audit.append(dict(origin=key[0], source_kind=key[1],
                               dense_OLS_max_abs_difference=discrepancy,
                               **moments(g.source_active_time_seconds)))
        for w, wt in g.groupby("worker_id"):
            if w in set(f.worker_id):
                worker_time.append(dict(worker_id=w, origin=key[0], source_kind=key[1],
                                        records=len(wt), images=wt.image_id.nunique(),
                                        buildings=wt.building_id.nunique(), **moments(wt.source_active_time_seconds)))
    f, extended_meta, time_rows, opportunities = extend(f, d, ex, fn)
    f.to_csv(args.out / "features_train.csv.gz", index=False)
    pd.DataFrame(worker_time).to_csv(args.out / "time_history_per_worker.csv", index=False)
    pd.DataFrame(time_rows).to_csv(args.out / "time_condition_ranges.csv", index=False)
    pd.DataFrame(opportunities).to_csv(args.out / "condition_opportunities.csv", index=False)
    pd.DataFrame(same).to_csv(args.out / "prior_feature_parity.csv", index=False)
    js(args.out / "FEATURE_AUDIT.json", {
        "schema": "interchangeability_history_features_20261020_v1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "main_commit": "445686f8f3cf6039c4ce1f60016cad1d26829044",
        "scientific_commit": "82c6164b0d4630de5316199c92aa405930973168",
        "history_buildings": buildings, "train_key": f.train_key.iloc[0],
        "history_records_read": len(d), "target_outcomes_used": False,
        "source_sha256": {str(p.relative_to(BASE)): sha(p) for p in [records_path,
            prior / "forward/build_forward.py", prior / "forward/results/features_train.csv.gz",
            splitpath, args.followup / "HIGH_Q_FEATURES.csv", args.followup / "SUBDIVISION_SUPPORT.csv"]},
        "prior_feature_columns_checked": len(same), "prior_features_match": True,
        "high_Q23": {"definition": "core_supported and history q_beta >= 0; F_rule_Q_threshold_K2 C02",
            "workers": sorted(high.worker_id), "origin_counts": high.person_origin.value_counts().to_dict(),
            "followup_all_shared_fields_equal": True,
            "extra_vs_Q_tertile_high18": sorted(set(high.worker_id)-set(high18.worker_id)),
            "Q_tertile_high18_is_subset": set(high18.worker_id).issubset(high.worker_id)},
        "inherited_time": {"filter": "history; pool_analysis_eligible; manual; ordinary_difficulty_eligible; easy/medium/hard; source_active_time_seconds > 0",
            "unit": "seconds as frozen evidence; no raw export processing or unit conversion",
            "additional_minimum_seconds": None, "additional_maximum_seconds": None,
            "nonpositive_or_missing_in_gate": int((~d.loc[time_mask, "source_active_time_seconds"].gt(0)).sum()),
            "unsupported_not_zero": True, "support_gate": {"records": 6, "buildings": 3},
            "source_summaries": time_audit,
            "interpretation": "exp(t_effect) is a source-specific task-adjusted time multiplier; cross-source absolute efficiency not inferred"},
        "prior_feature_fit": meta, "prior_condition_fit": cmeta,
        "extended_conditions": extended_meta,
        "scope_boundary": "Response propensity only; compatible in-scope adjudication count is not bidirectional OOS accuracy; no correctness or target pool OOS label in classes.",
        "semi_boundary": "Old confirmed and new reported opportunities separate; editing is not correction; no missing initialization gain invented."
    })
    print(json.dumps(clean({"workers": len(f), "columns": len(f.columns),
                            "highQ23": len(high), "time": time_audit,
                            "extended_support": {k:{j:v[j] for j in ["quality_supported","time_supported"]} for k,v in extended_meta.items()}}), ensure_ascii=False))


if __name__ == "__main__":
    main()
