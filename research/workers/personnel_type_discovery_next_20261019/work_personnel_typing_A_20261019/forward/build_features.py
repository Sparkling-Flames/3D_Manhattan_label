#!/usr/bin/env python3
"""Refit all Part-A multivariate history features inside each training set.

Uses unchanged archived task-effect and partial-pooling functions. Inventory
evidence is flattened anew; archived person-level fits are not consumed here.
"""
from __future__ import annotations
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
import time
import tempfile
import shutil
import inspect
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RECOVERED = ROOT / "recovered"
ORIGINAL = RECOVERED / "work_v2_20261019/profiles/run_profiles.py"
SPEC = importlib.util.spec_from_file_location("frozen_pro_profile_functions", ORIGINAL)
NATIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NATIVE)
DIFFS = ("easy", "medium", "hard")
from atomic_exports import csv_verified

DOMAINS = {
    "Q": ["q_beta", "q_abs_mean", "q_abs_p10", "q_abs_sd", "q_residual_p10", "q_residual_sd"],
    "T": ["t_source_origin_effect", "t_log_residual_tail"],
    "difficulty": ["hard_minus_easy", "hard_minus_medium"],
    "structure": ["pair_count_effect", "pair_count_residual_sd", "bottom_y_effect", "top_y_effect", "height_log_effect"],
    "semi": ["semi_old_error_nonedit_effect", "semi_new_error_nonedit_effect", "semi_old_edit_effect", "semi_new_edit_effect"],
    "scope": ["scope_out_effect"],
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe_num(x):
    try:
        a = float(x)
        return a if np.isfinite(a) else np.nan
    except (ValueError, TypeError):
        return np.nan


def key(*parts):
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def extra_frame(evidence):
    rows = []
    for e in evidence:
        s = e.get("semi_evidence") or {}
        sc = e.get("scope_evidence") or {}
        audit = s.get("initialization_audit") or {}
        flags = s.get("reported_flags") or {}
        phase = audit.get("initialization_hash") or flags.get("initialization_kind") or s.get("status")
        p = np.asarray(e.get("points_1024x512") or [], dtype=float)
        r = {"object_id": e["object_id"], "worker_id": e["worker_id"], "building_id": e["building_id"],
             "image_id": e["image_id"], "condition": e["condition"], "origin": e["origin"],
             "semi_old_opp": bool(s.get("confirmed_error_opportunity")),
             "semi_new_opp": bool(s.get("reported_error_opportunity")),
             "semi_old_nonedit": float(bool(s["known_error_unchanged"])) if s.get("known_error_unchanged") is not None else np.nan,
             "semi_new_nonedit": float(bool(s["reported_known_error_unchanged"])) if s.get("reported_known_error_unchanged") is not None else np.nan,
             "semi_edited": float(bool(s["edited"])) if s.get("edited") is not None else np.nan,
             "semi_task": key(e["image_id"], e["condition"], e.get("reference_id"), e["origin"], phase),
             "semi_attributable": bool(s.get("worker_attributable_gain_available")),
             "semi_gain_B8": safe_num((s.get("current_worker_attributable_gain") or {}).get("B8L2")),
             "semi_initial_B8": safe_num((s.get("current_initial_scores") or {}).get("B8L2")),
             "semi_final_B8": safe_num(e.get("B8L2")),
             "scope_out": (1. if sc.get("response") == "out_of_scope" else 0.) if sc.get("response") in ("in_scope", "out_of_scope") else np.nan,
             "scope_compatible_gold": bool(sc.get("judgement_opportunity")),
             "scope_correct": sc.get("correct"),
             "scope_task": key(e["image_id"], e["condition"], e["origin"], sc.get("response_source")),
             "source_individual_review": (e.get("review_evidence") or {}).get("verdict") not in (None, "", "not_individually_reviewed"),
             "specific_error_candidate": bool((e.get("exclusion_attribution") or {}).get("specific_person_error_candidate")),
             "legacy_explicit_person_error": bool((e.get("exclusion_attribution") or {}).get("legacy_explicit_person_error")),
             "bottom_y_mean": float(p[1::2, 1].mean()/512) if p.ndim == 2 and len(p) >= 6 and len(p)%2 == 0 else np.nan,
             "top_y_mean": float(p[0::2, 1].mean()/512) if p.ndim == 2 and len(p) >= 6 and len(p)%2 == 0 else np.nan}
        rows.append(r)
    return pd.DataFrame(rows)


def numeric_group_stats(g, col, prefix):
    a = pd.to_numeric(g[col], errors="coerce").dropna()
    return {prefix+"n": int(len(a)), prefix+"mean": float(a.mean()) if len(a) else np.nan,
            prefix+"median": float(a.median()) if len(a) else np.nan,
            prefix+"p10": float(a.quantile(.1)) if len(a) else np.nan,
            prefix+"p90": float(a.quantile(.9)) if len(a) else np.nan,
            prefix+"sd": float(a.std(ddof=1)) if len(a)>1 else np.nan}


def effect(frame, value, task_col="task", ridge=0.):
    f = frame[frame[value].notna()].copy()
    if not len(f):
        return {}, {"raw_rows": 0, "effective_person_tasks": 0, "duplicate_rows_collapsed": 0}
    f["task"] = f[task_col]
    # Inventory can include more than one record for a person/task. Those records
    # remain in opportunity ledgers, but do not multiply a person's task vote.
    effective = f.groupby(["task", "worker_id"], as_index=False)[value].mean()
    beta, fit = NATIVE.fit_fe(effective, value, ridge=ridge)
    fit.update(raw_rows=len(f), effective_person_tasks=len(effective), duplicate_rows_collapsed=len(f)-len(effective))
    return beta, fit


def _training_features(d, extras, workers, buildings, metric="B8L2"):
    buildings = set(buildings)
    a = d[d.building_id.isin(buildings)].copy()
    ex = extras[extras.building_id.isin(buildings)].copy()
    assert set(a.building_id).issubset(buildings) and set(ex.building_id).issubset(buildings)
    q = a[a.quality_usable & a.condition.eq("manual") & a.quality_use.eq("ordinary_primary")].copy()
    q = q.merge(ex[["object_id", "bottom_y_mean", "top_y_mean"]], on="object_id", validate="one_to_one")
    q["height_log"] = np.log(q.height_mean_ratio.where(q.height_mean_ratio > 0))
    q["reference_pair_gap"] = q.declared_pair_count - q.reference_pair_count
    beta, info = effect(q, metric)
    joint = NATIVE.fit_joint(q, metric, strength=20)
    # Residuals retain within-task worker effect: low tail may indicate systematic
    # relative deficit as well as volatility. No all-data mean enters.
    q["q_centered"] = q[metric] - q.groupby("task")[metric].transform("mean")
    q["pair_count_centered"] = q.declared_pair_count - q.groupby("task").declared_pair_count.transform("mean")
    structural = {}
    for name, col in [("pair_count_effect", "declared_pair_count"), ("bottom_y_effect", "bottom_y_mean"),
                      ("top_y_effect", "top_y_mean"), ("height_log_effect", "height_log")]:
        structural[name] = effect(q, col, ridge=5)[0]
    tg = a.pool_analysis_eligible & a.condition.eq("manual") & a.ordinary_difficulty_eligible & a.difficulty.isin(DIFFS)
    t = a[tg & a.source_active_time_seconds.gt(0)].copy()
    t["log_seconds"] = np.log(t.source_active_time_seconds)
    t["task"] = [key(i,c,o,s) for i,c,o,s in zip(t.image_id,t.condition,t.origin,t.time_source_kind)]
    tfits, tfitmeta = {}, {}
    for origin, g in t.groupby(["origin", "time_source_kind"]):
        m, meta = effect(g, "log_seconds")
        tfits.update(m)
        tfitmeta[str(origin)] = meta
    t["log_centered"] = t.log_seconds - t.groupby("task").log_seconds.transform("mean")
    # Scope tasks compare the same image/condition and source semantics. No GT
    # answer or image OOS label is used as a person's correct/incorrect label.
    scope = ex[ex.scope_out.notna()].copy()
    scope["task"] = scope.scope_task
    scope = scope[scope.groupby("task").worker_id.transform("nunique") >= 2].copy()
    scope["task_varies"] = scope.groupby("task").scope_out.transform("nunique") > 1
    scope_beta, scope_meta = effect(scope, "scope_out", ridge=5)
    semi_maps, semi_frames, semi_fit = {}, {}, {}
    for tier, opp, value in [("old_error_nonedit", "semi_old_opp", "semi_old_nonedit"),
                             ("new_error_nonedit", "semi_new_opp", "semi_new_nonedit")]:
        s = ex[ex[opp] & ex[value].notna()].copy()
        s["task"] = s.semi_task
        semi_frames[tier] = s
        semi_maps[tier], semi_fit[tier] = effect(s, value, ridge=5)
    for origin, short in [("v1", "old"), ("new", "new")]:
        s = ex[ex.condition.eq("semi") & ex.origin.eq(origin) & ex.semi_edited.notna()].copy()
        s["task"] = s.semi_task
        name = short+"_edit"
        semi_frames[name] = s
        semi_maps[name], semi_fit[name] = effect(s, "semi_edited", ridge=5)
    byq = dict(tuple(q.groupby("worker_id"))); byt = dict(tuple(t.groupby("worker_id")))
    byscope = dict(tuple(scope.groupby("worker_id"))); byex = dict(tuple(ex.groupby("worker_id")))
    semigroups = {name:dict(tuple(s.groupby("worker_id"))) for name,s in semi_frames.items()}
    rows = []
    for w in workers:
        g = byq.get(w, q.iloc[:0]); tt = byt.get(w, t.iloc[:0]); s = byscope.get(w, scope.iloc[:0]); ee = byex.get(w, ex.iloc[:0])
        r = {"worker_id": w, "metric": metric, "core_tasks": int(g.task.nunique()),
             "core_images": int(g.image_id.nunique()), "core_buildings": int(g.building_id.nunique()),
             "core_records": len(g), "core_supported": g.task.nunique()>=8 and g.building_id.nunique()>=3,
             "person_origin": "|".join(sorted(a.loc[a.worker_id.eq(w), "origin"].unique())),
             "q_beta": beta.get(w, np.nan), "q_effect_connectivity_nullity": info.get("nullity"),
             "q_residual_p10": float(g.q_centered.quantile(.1)) if len(g) else np.nan,
             "q_residual_sd": float(g.q_centered.std()) if len(g)>1 else np.nan,
             "pair_count_residual_sd": float(g.pair_count_centered.std()) if len(g)>1 else np.nan,
             "reference_pair_gap_mean": float(g.reference_pair_gap.mean()) if len(g) else np.nan,
             "reference_fewer_pairs_fraction": float((g.reference_pair_gap<0).mean()) if len(g) else np.nan,
             "reference_more_pairs_fraction": float((g.reference_pair_gap>0).mean()) if len(g) else np.nan}
        r.update(numeric_group_stats(g, metric, "q_abs_"))
        for name, mp in structural.items(): r[name] = mp.get(w, np.nan)
        for comp in ["iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "height_mean_ratio", "declared_pair_count"]:
            r[comp+"_mean"] = float(g[comp].mean()) if len(g) else np.nan
        for diff in DIFFS:
            dd = g[g.difficulty.eq(diff)]
            supported = dd.task.nunique()>=6 and dd.building_id.nunique()>=3
            r.update({f"{diff}_tasks": int(dd.task.nunique()), f"{diff}_images": int(dd.image_id.nunique()),
                      f"{diff}_buildings": int(dd.building_id.nunique()), f"{diff}_supported": supported,
                      f"theta_{diff}_estimate": joint.get((w,diff), np.nan),
                      f"theta_{diff}": joint.get((w,diff), np.nan) if supported else np.nan,
                      f"absolute_{diff}_mean": float(dd[metric].mean()) if len(dd) else np.nan,
                      f"absolute_{diff}_p10": float(dd[metric].quantile(.1)) if len(dd) else np.nan})
        r["hard_minus_easy"] = r["theta_hard"]-r["theta_easy"]
        r["hard_minus_medium"] = r["theta_hard"]-r["theta_medium"]
        r["medium_minus_easy"] = r["theta_medium"]-r["theta_easy"]
        r["t_records"] = len(tt); r["t_images"] = tt.image_id.nunique(); r["t_buildings"] = tt.building_id.nunique()
        r["t_supported"] = len(tt)>=6 and tt.building_id.nunique()>=3
        r["t_source_origin_effect"] = tfits.get(w,np.nan) if r["t_supported"] else np.nan
        r["t_log_residual_tail"] = float(tt.log_centered.quantile(.9)-tt.log_centered.median()) if r["t_supported"] else np.nan
        r.update(numeric_group_stats(tt,"source_active_time_seconds","source_time_"))
        r["time_source_kind"] = "|".join(sorted(tt.time_source_kind.unique()))
        target = a[tg & a.worker_id.eq(w) & a.target_matched_time_seconds.gt(0)]
        r["target_time_n"] = len(target); r["target_time_images"] = target.image_id.nunique()
        r["target_time_median"] = float(target.target_matched_time_seconds.median()) if len(target) else np.nan
        for name, sub in semigroups.items():
            ss = sub.get(w,semi_frames[name].iloc[:0]); error = "error" in name
            supported = len(ss)>= (3 if error else 6) and ss.building_id.nunique()>= (2 if error else 3)
            col = ("semi_old_nonedit" if name.startswith("old") else "semi_new_nonedit") if error else "semi_edited"
            r[f"semi_{name}_records"] = len(ss); r[f"semi_{name}_images"] = ss.image_id.nunique(); r[f"semi_{name}_buildings"] = ss.building_id.nunique()
            r[f"semi_{name}_supported"] = supported
            r[f"semi_{name}_effect"] = semi_maps[name].get(w,np.nan) if supported else np.nan
            r[f"semi_{name}_raw_rate"] = float(ss[col].mean()) if len(ss) else np.nan
            r[f"semi_{name}_count"] = float(ss[col].sum()) if len(ss) else np.nan
        pp = ee[ee.semi_attributable & ee.semi_gain_B8.notna()]
        r.update(semi_attributable_n=len(pp), semi_attributable_images=pp.image_id.nunique(),
                 semi_gain_mean=float(pp.semi_gain_B8.mean()) if len(pp) else np.nan,
                 semi_initial_mean=float(pp.semi_initial_B8.mean()) if len(pp) else np.nan,
                 semi_final_mean=float(pp.semi_final_B8.mean()) if len(pp) else np.nan)
        varying = s[s.task_varies].task.nunique()
        r.update(scope_records=len(s),scope_tasks=s.task.nunique(),scope_buildings=s.building_id.nunique(),scope_varying_tasks=varying,
                 scope_supported=len(s)>=10 and s.building_id.nunique()>=3 and varying>=2,
                 scope_out_raw_rate=float(s.scope_out.mean()) if len(s) else np.nan)
        r["scope_out_effect"] = scope_beta.get(w,np.nan) if r["scope_supported"] else np.nan
        r["scope_gold_n"] = int(ee.scope_compatible_gold.sum())
        r["individual_review_records"] = int(ee.source_individual_review.sum())
        r["specific_error_candidate_n"] = int(ee.specific_error_candidate.sum())
        r["legacy_explicit_person_error_n"] = int(ee.legacy_explicit_person_error.sum())
        rows.append(r)
    return pd.DataFrame(rows), {"train_buildings": sorted(buildings), "q_records": len(q), "q_images": q.image_id.nunique(),
                                "q_fit": info, "time_source_fits": tfitmeta, "scope_fit": scope_meta,
                                "semi_fits": semi_fit, "uses_target_outcomes": False}


def training_sets(splits):
    unique, aliases = {}, []
    for fold_id, f in splits["folds"].items():
        base = sorted(f["train_buildings"])
        for inner, heldout in [(None, [])] + [(int(k),v) for k,v in f["inner_validation_groups"].items()]:
            bs = sorted(set(base)-set(heldout))
            h = hashlib.sha256("|".join(bs).encode()).hexdigest()[:16]
            train_key = "train_"+h
            unique[train_key] = bs
            aliases.append({"fold_id":fold_id,"heldout_building":f["heldout_building"],"inner_group":inner,
                            "inner_validation_buildings":heldout,"train_key":train_key})
    return unique, aliases


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--metric",choices=["B8L2","D10"],default="B8L2");ap.add_argument("--only-full",action="store_true");args=ap.parse_args()
    start=time.time();out=HERE;repo=RECOVERED/"repo_main_20261019"
    source=repo/"research/statistics/v2_evidence_audit_20261019/records.json.gz"
    evidence=json.load(gzip.open(source,"rt"))["records"]
    # Shared immutable flattening code, recomputed from supplied records.
    with tempfile.TemporaryDirectory(prefix="flatten_",dir=out) as fresh:
        fresh=Path(fresh)
        shutil.copyfile(out/"REGISTRATION.json",fresh/"REGISTRATION.json")
        d,q,mainframe,times,tables,ctx=NATIVE.load_inputs(repo,fresh)
        if args.metric=="B8L2":
            csv_verified(d,out/"records_flat.csv")
            shutil.copyfile(fresh/"INPUT_COVERAGE.json",out/"INPUT_COVERAGE.json")
    ex=extra_frame(evidence)
    if args.metric=="B8L2":
        csv_verified(ex,out/"behavior_geometry_source_columns.csv.gz")
    assert int(ex.semi_old_opp.sum())==156 and int(ex.semi_new_opp.sum())==284
    assert int(ex.loc[ex.semi_old_opp,"semi_old_nonedit"].sum())==25
    assert int(ex.loc[ex.semi_new_opp,"semi_new_nonedit"].sum())==45
    assert int(ex.scope_out.notna().sum())==9845 and int(ex.scope_compatible_gold.sum())==93
    workers=sorted(q.worker_id.unique())
    splits_path=ROOT/"reverse/FROZEN_BUILDING_SPLITS.json"
    assert sha(splits_path)=="ec5a004db1c868e9802a3729af549ac959b29bd43772b53c0af18f4d32c7f9b4"
    sets,aliases=training_sets(json.loads(splits_path.read_text()))
    if args.only_full:
        full=next(x["train_key"] for x in aliases if x["fold_id"]=="FULL" and x["inner_group"] is None)
        sets={full:sets[full]}
    cache=out/"feature_fits"/args.metric;cache.mkdir(parents=True,exist_ok=True)
    expected_cache={"source_records_sha256":sha(source),"native_fit_function_file_sha256":sha(ORIGINAL),
                    "feature_function_sha256":hashlib.sha256(inspect.getsource(_training_features).encode()).hexdigest()}
    allframes=[];fits={};counts={"new_fits":0,"cached_fits":0}
    for n,(train_key,buildings) in enumerate(sets.items(),1):
        dest=cache/f"{train_key}.csv"
        receipt=cache/f"{train_key}.json"
        if dest.exists() and receipt.exists():
            frame=pd.read_csv(dest);meta=json.loads(receipt.read_text());counts["cached_fits"]+=1
            for key,value in expected_cache.items():
                assert meta.get(key)==value,f"Cached feature input/code identity mismatch: {dest} / {key}"
            assert meta["train_buildings"]==buildings and len(frame)==len(workers)
        else:
            frame,meta=_training_features(d,ex,workers,buildings,args.metric)
            frame.insert(0,"train_key",train_key);frame.to_csv(dest,index=False)
            meta.update(expected_cache)
            NATIVE.js(receipt,meta);counts["new_fits"]+=1
        allframes.append(frame);fits[train_key]=meta
        print(json.dumps({"fit":n,"total":len(sets),"train_key":train_key,"buildings":len(buildings),"core_supported":int(frame.core_supported.sum())}),flush=True)
    allf=pd.concat(allframes,ignore_index=True)
    suffix="" if args.metric=="B8L2" else "_D10"
    csv_verified(allf,out/f"worker_features_by_training_set{suffix}.csv.gz")
    outer=pd.DataFrame([x for x in aliases if x["inner_group"] is None])
    outer=outer[outer.train_key.isin(allf.train_key.unique())]
    csv_verified(outer.merge(allf,on="train_key",validate="many_to_many"),out/f"fold_features{suffix}.csv.gz")
    NATIVE.js(out/"TRAINING_SETS.json",{"sets":sets,"aliases":aliases,"splits_sha256":sha(splits_path)})
    NATIVE.js(out/"FEATURE_DOMAINS.json",DOMAINS)
    NATIVE.js(out/f"FEATURE_REPLAY_RECEIPT{suffix}.json",{"metric":args.metric,"inventory":len(d),"quality_workers":len(workers),"fits":len(sets),
                 "fit_rows":len(allf),"source_sha256":sha(source),"native_fit_code_sha256":sha(ORIGINAL),
                 "script_sha256":sha(__file__),"registration_sha256":sha(out/"REGISTRATION.json"),"seconds":time.time()-start,**counts,
                 "semi_old_opportunities":156,"semi_old_nonmodified":25,"semi_reported_opportunities":284,"semi_reported_nonmodified":45,
                 "scope_answers":9845,"scope_compatible_gold":93,"gold_accuracy_feature_used":False,
                 "new_fit_targets": "individual historical records only; no fusion or validation outcome file read"})


if __name__=="__main__":main()
