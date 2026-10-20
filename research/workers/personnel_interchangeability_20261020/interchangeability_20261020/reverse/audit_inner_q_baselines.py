#!/usr/bin/env python3
"""History-inner Q benchmarks rebuilt on each eight-building training set.

This audits already frozen classes; no class or shortlist is changed. Both
Q-only bins and a source x training-Q-tertile capacity randomization are shown.
The latter is a COARSE Q-control sensitivity, not exact control of all quality,
tail, difficulty or causal factors.
"""
from __future__ import annotations
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from learn_swap_types import (SEED,clean,domain_mask,fit_labels,load_history,
    make_graph,make_inner_folds,pair_building_table,sha,write_csv,write_json)
from audit_inner_baselines import FastAnchors

ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"interchangeability_20261020/reverse"
OUT=BASE/"inner_q_baselines";OUT.mkdir(parents=True,exist_ok=True)
CONTROL_SEED=2026102007;DRAWS=40


def quantiles(values,k,workers):
    order=sorted(range(len(values)),key=lambda i:(values[i],workers[i]))
    labels=np.zeros(len(values),int)
    for c,indices in enumerate(np.array_split(order,k)):labels[indices]=c
    return labels


def build_fold_quality(split):
    code=ROOT/"current_main_20261020/research/workers/personnel_composition_study_20261019/analysis/forward/build_forward.py"
    module_spec=importlib.util.spec_from_file_location("frozen_forward_for_eight_building_q",code)
    old=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(old)
    _,fn=old.upstream_functions(ROOT/"repo")
    record_source=ROOT/"repo"/old.RECORD_SOURCE
    records=json.load(gzip.open(record_source,"rt"))["records"]
    # Filter before flattening, feature construction, estimation, summaries or
    # any candidate comparison. Other-building outcomes never enter functions.
    records=[r for r in records if r["building_id"] in split["history_buildings"]]
    full_worker_ids=pd.read_csv(ROOT/"analysis/forward/results/features_train.csv.gz",usecols=["worker_id"]).worker_id.tolist()
    result={};rows=[];metadata=[]
    for fi,held in enumerate(make_inner_folds(split["history_buildings"])):
        train=[b for b in split["history_buildings"] if b not in held]
        rr=[r for r in records if r["building_id"] in train]
        assert set(r["building_id"] for r in rr).issubset(train)
        d=old.flatten(rr);extra=fn["extra_frame"](rr)
        f,meta=fn["_training_features"](d,extra,full_worker_ids,train)
        result[fi]=f
        metadata.append(dict(fold=fi,train_buildings=train,heldout_buildings=held,
            input_records=len(rr),supported_Q_workers=int(f.core_supported.sum())))
        for r in f[["worker_id","q_beta","core_supported","core_tasks","core_buildings","theta_hard","hard_supported"]].to_dict("records"):
            rows.append(dict(fold=fi,**r))
        print(json.dumps({"Q_features_rebuilt_fold":fi,"supported_Q":int(f.core_supported.sum())}),flush=True)
    write_csv(OUT/"eight_building_Q_features.csv.gz",pd.DataFrame(rows))
    return result,dict(feature_builder_sha256=sha(code),record_source_sha256=sha(record_source),
        imported_feature_source_sha256=sha(ROOT/"repo"/old.FEATURE_SOURCE),
        profile_estimator_sha256=sha(ROOT/"repo"/old.PROFILE_SOURCE),folds=metadata)


def main():
    start=time.perf_counter()
    # Audit definition is written before rebuilding any Q baseline or examining
    # its scores. Candidate membership is already frozen separately.
    write_json(OUT/"REGISTRATION.json",dict(seed=CONTROL_SEED,random_draws=DRAWS,
        classes_refitted_or_selected=False,Q_feature="q_beta rebuilt independently on each 8-building training fold",
        Q_only="Balanced empirical q_beta quantiles with same K as the candidate, ties broken by worker ID; minimum4 in each Q bin",
        source_Q_bins="Within each training-source cohort, up to3 balanced empirical q_beta bins, as capacity permits minimum4",
        randomization="Permute candidate class labels only within source x Q-bin strata, preserving exactly every class's count in each stratum and thus class capacity",
        interpretation="Separate coarse control sensitivity. Does not exactly equalize numeric Q, quality tails, difficulty adaptation or other worker features.",
        evaluation="Exact common heldout anchor intersection for each candidate/baseline pair; same worker Q-supported cohort, same n/image/building weighting",
        no_discovery_validation_fitting=True))
    frame,split,input_audit=load_history(ROOT,BASE/"native_history_events.csv.gz")
    qframes,qreceipt=build_fold_quality(split)
    source=pd.read_csv(ROOT/"analysis/forward/results/features_train.csv.gz",usecols=["worker_id","person_origin"]).set_index("worker_id").person_origin.to_dict()
    rows=[];ledger=[];cache={}
    for family,shortfile in [("legacy","LEGACY_SCREEN_SHORTLIST.json"),("mixed","MIXED_SCREEN_SHORTLIST.json")]:
        fit=BASE/(family+"_fit");short=json.load(open(BASE/shortfile));reg=json.load(open(fit/"REGISTRATION.json"))
        manifest=json.load(open(fit/"METHOD_MANIFEST.json"));gate=reg["opportunity"].get("each_class_known_pair_fraction_min",0)
        assert sha(fit/"worker_labels.csv.gz")==short["labels_sha256"]
        panels=reg.get("source_panels_for_learning",[reg.get("source_panel_for_learning")])
        data=frame[frame.panel_id.isin(panels)]
        for domain in sorted({x["domain"] for x in short["methods"]}):
            df=data.loc[domain_mask(data,domain)];pb=pair_building_table(df);cache[(family,domain)]=[]
            for fi,held in enumerate(make_inner_folds(split["history_buildings"])):
                train=df[~df.building.isin(held)];test=df[df.building.isin(held)]
                graph=make_graph(train,pb[~pb.building.isin(held)])
                q=qframes[fi].set_index("worker_id")
                indices=[i for i,w in enumerate(graph["workers"]) if bool(q.loc[w,"core_supported"]) and np.isfinite(q.loc[w,"q_beta"])]
                workers=[graph["workers"][i] for i in indices];values=q.loc[workers,"q_beta"].to_numpy(float)
                origins=np.asarray([source[w] for w in workers]);strata=np.zeros(len(workers),int);offset=0
                for origin in sorted(set(origins)):
                    ids=np.flatnonzero(origins==origin);n_bins=max(1,min(3,len(ids)//4))
                    strata[ids]=quantiles(values[ids],n_bins,[workers[i] for i in ids])+offset;offset+=n_bins
                cache[(family,domain)].append((fi,graph,np.asarray(indices),workers,values,strata,FastAnchors(test,workers)))
        for info in short["methods"]:
            mid=info["method_id"];spec=manifest[mid];domain=spec["domain"]
            seed=int(hashlib.sha256(mid.encode()).hexdigest()[:12],16)
            for fi,graph,indices,workers,values,strata,fast in cache[(family,domain)]:
                labels,status=fit_labels(graph,spec["representation"],spec["algorithm"],spec["requested_k"],SEED+fi*1000+spec["requested_k"],gate)
                ledger.append(dict(family=family,method_id=mid,domain=domain,fold=fi,status=status,
                    graph_workers=len(graph["workers"]),Q_supported_workers=len(workers),Q_missing_worker_loss=len(graph["workers"])-len(workers)))
                if labels is None:continue
                candidate=labels[indices]
                baselines=[("source_Q_tertile_cells",strata)]
                if len(workers)>=4*spec["requested_k"]:
                    baselines.append(("Q_only_balanced_same_K",quantiles(values,spec["requested_k"],workers)))
                else:
                    ledger.append(dict(family=family,method_id=mid,domain=domain,fold=fi,status="Q_only_K_capacity_unavailable"))
                for name,baseline in baselines:
                    paired=fast.paired(candidate,baseline)
                    if not paired:
                        ledger.append(dict(family=family,method_id=mid,domain=domain,fold=fi,status="no_common_anchor_for_"+name))
                    for r in paired:rows.append(dict(family=family,method_id=mid,domain=domain,fold=fi,baseline=name,draw=0,**r))
                rng=np.random.default_rng(CONTROL_SEED+seed+fi*100000)
                for draw in range(DRAWS):
                    random=candidate.copy()
                    for stratum in sorted(set(strata)):
                        ids=np.flatnonzero(strata==stratum);random[ids]=rng.permutation(candidate[ids])
                        assert np.array_equal(np.bincount(random[ids],minlength=spec["requested_k"]),np.bincount(candidate[ids],minlength=spec["requested_k"]))
                    for r in fast.paired(candidate,random):
                        rows.append(dict(family=family,method_id=mid,domain=domain,fold=fi,
                            baseline="random_source_Q3_preserving_capacity",draw=draw,**r))
            print(json.dumps({"Q_baseline_method_complete":mid,"elapsed_seconds":round(time.perf_counter()-start,1)}),flush=True)
    result=pd.DataFrame(rows);write_csv(OUT/"paired_building_draws.csv.gz",result)
    write_csv(OUT/"support_ledger.csv",pd.DataFrame(ledger))
    metrics=[c for c in result.columns if c.startswith(("candidate_","baseline_","delta_"))]
    bydraw=result.groupby(["family","method_id","domain","baseline","draw"],observed=True)[metrics].mean().reset_index()
    support=result.groupby(["family","method_id","domain","baseline","draw"],observed=True).agg(buildings=("building","nunique"),matched_backgrounds=("matched_backgrounds","sum")).reset_index()
    bydraw=bydraw.merge(support,on=["family","method_id","domain","baseline","draw"])
    write_csv(OUT/"paired_draw_summary.csv",bydraw)
    summary=[]
    for keys,g in bydraw.groupby(["family","method_id","domain","baseline"]):
        r=dict(zip(["family","method_id","domain","baseline"],keys));r.update(draws=len(g),buildings_min=g.buildings.min(),
            buildings_max=g.buildings.max(),matched_backgrounds_min=g.matched_backgrounds.min())
        for metric in metrics:
            r[metric+"_mean"]=g[metric].mean();r[metric+"_p05"]=g[metric].quantile(.05);r[metric+"_p95"]=g[metric].quantile(.95)
        summary.append(r)
    write_csv(OUT/"paired_summary.csv",pd.DataFrame(summary))
    write_json(OUT/"Q_BASELINE_RECEIPT.json",clean(dict(
        registration_sha256=sha(OUT/"REGISTRATION.json"),source_script_sha256=sha(Path(__file__)),
        feature_rebuild=qreceipt,fold_Q_values_sha256=sha(OUT/"eight_building_Q_features.csv.gz"),
        no_ten_building_Q_values_used_for_inner_folds=True,no_class_or_shortlist_changes=True,
        elapsed_seconds=time.perf_counter()-start)))


if __name__=="__main__":main()
