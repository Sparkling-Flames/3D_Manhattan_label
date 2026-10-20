#!/usr/bin/env python3
"""Freeze-preserving stress on old A_nested backgrounds excluded from fitting.

These are reused historical images and previously generated teams, not new
independent images or an external blind test. Each nested anchor holds only one
person pair; therefore this file NEVER calls its within/between contrasts exact
common-background comparisons. Pool,n,entrant-source-pair strata are matched.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from learn_swap_types import (NESTED_PANEL,OLD_PANEL,SUMMARY_METRICS,clean,
    domain_mask,load_history,sha,write_csv,write_json)


def summarize(d):
    keys=["building","pool_id","k","source_pair","same"]
    metrics=d.groupby(keys,observed=True)[SUMMARY_METRICS].mean().reset_index()
    support=d.groupby(keys,observed=True).agg(events=("event_id","size"),
        workers=("worker_a","nunique")).reset_index()
    metrics=metrics.merge(support,on=keys)
    common=metrics.groupby(keys[:-1],observed=True).same.nunique()
    common=set(common[common==2].index)
    matched=metrics[[tuple(x) in common for x in metrics[keys[:-1]].itertuples(index=False,name=None)]]
    if not len(matched):return pd.DataFrame(),metrics
    pn=matched.groupby(["building","pool_id","k","same"],observed=True)[SUMMARY_METRICS].mean().reset_index()
    image=pn.groupby(["building","pool_id","same"],observed=True)[SUMMARY_METRICS].mean().reset_index()
    building=image.groupby(["building","same"],observed=True)[SUMMARY_METRICS].mean().unstack("same")
    rows=[]
    for b in building.index:
        r=dict(building=b,images=int(matched[matched.building.eq(b)].pool_id.nunique()),
               matched_pool_n_source_strata=len(matched[matched.building.eq(b)])//2)
        for metric in SUMMARY_METRICS:
            r["within_"+metric]=building.loc[b,(metric,True)]
            r["between_"+metric]=building.loc[b,(metric,False)]
        r["gap_main"]=r["within_stable_main"]-r["between_stable_main"]
        r["gap_geometry"]=r["within_stable_geometry"]-r["between_stable_geometry"]
        r["within_bad_wide"]=1-r["within_stable_wide"]
        rows.append(r)
    return pd.DataFrame(rows),metrics


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path.cwd())
    ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter();base=a.root/"interchangeability_20261020/reverse"
    # No supplementary panel needed: it was a learning input, whereas this
    # pressure panel is the pre-existing A_nested one explicitly held aside.
    frame,split,input_audit=load_history(a.root)
    nested=frame[frame.panel_id.eq(NESTED_PANEL)].copy();old=frame[frame.panel_id.eq(OLD_PANEL)].copy()
    assert len(nested)==7272 and nested.event_id.is_unique
    assert nested.groupby(["pool_id","k","background_id"]).size().max()==1
    assert set(nested.building).issubset(set(split["history_buildings"]))
    building_rows=[];cell_rows=[];class_rows=[];ledgers=[];same_pair_rows=[];hashes=[]
    for family,shortfile in [("legacy","LEGACY_SCREEN_SHORTLIST.json"),("mixed","MIXED_SCREEN_SHORTLIST.json")]:
        short=json.load(open(base/shortfile));fit=base/(family+"_fit")
        manifest=json.load(open(fit/"METHOD_MANIFEST.json"))
        assert sha(fit/"worker_labels.csv.gz")==short["labels_sha256"]
        hashes.append(dict(shortlist=shortfile,sha256=sha(base/shortfile),labels_sha256=short["labels_sha256"]))
        for info in short["methods"]:
            mid=info["method_id"];spec=manifest[mid];domain=spec["domain"]
            mapper={w:c for c,ws in spec["classes"].items() for w in ws}
            d=nested.loc[domain_mask(nested,domain)].copy()
            requested=len(d);d["class_a"]=d.worker_a.map(mapper);d["class_b"]=d.worker_b.map(mapper)
            d=d[d.class_a.notna()&d.class_b.notna()].copy();d["same"]=d.class_a.eq(d.class_b)
            d["source_pair"]=["|".join(sorted(v)) for v in d[["entrant_origin_a","entrant_origin_b"]].itertuples(index=False,name=None)]
            pb,cells=summarize(d)
            for r in pb.to_dict("records"):building_rows.append(dict(method_id=mid,domain=domain,**r))
            for r in cells.to_dict("records"):cell_rows.append(dict(method_id=mid,domain=domain,**r))
            ledgers.append(dict(method_id=mid,domain=domain,registered_domain_events=requested,known_events=len(d),
                unknown_entrant_events=requested-len(d),images=d.pool_id.nunique(),buildings=d.building.nunique(),
                actual_backgrounds=d.background_id.nunique(),actual_workers=len(set(d.worker_a)|set(d.worker_b)),
                matched_buildings=len(pb),matched_images=int(pb.images.sum()) if len(pb) else 0,
                exact_same_background_within_between_comparisons=0,
                interpretation="frozen historical different-background stress; no new independent images"))
            # Detailed fixed class pairs remain separate. Different source-pair
            # and n cells are averaged in the explicitly stated hierarchy.
            cp=np.sort(d[["class_a","class_b"]].to_numpy(),axis=1)
            d["class_low"],d["class_high"]=cp[:,0],cp[:,1]
            cc=d.groupby(["building","pool_id","k","class_low","class_high"],observed=True)[SUMMARY_METRICS].mean().reset_index()
            ci=cc.groupby(["building","pool_id","class_low","class_high"],observed=True)[SUMMARY_METRICS].mean().reset_index()
            cb=ci.groupby(["building","class_low","class_high"],observed=True)[SUMMARY_METRICS].mean().reset_index()
            for r in cb.to_dict("records"):class_rows.append(dict(method_id=mid,domain=domain,**r))
            # Old exact panel is a learning input; this comparison only isolates
            # change of previously generated background for the SAME person pair.
            reference=old.loc[domain_mask(old,domain)].groupby(["pool_id","k","worker_a","worker_b"],observed=True)[SUMMARY_METRICS].mean().add_prefix("old_").reset_index()
            matched=d.merge(reference,on=["pool_id","k","worker_a","worker_b"],how="inner",validate="many_to_one")
            for metric in ["stable_main","stable_geometry","stable_wide","abs_B8L2_change","floor_jaccard_difference"]:
                matched["change_"+metric]=matched[metric]-matched["old_"+metric]
            fields=[c for c in matched.columns if c.startswith("change_")]
            nn=matched.groupby(["building","pool_id","k","same"],observed=True)[fields].mean().reset_index()
            ni=nn.groupby(["building","pool_id","same"],observed=True)[fields].mean().reset_index()
            nb=ni.groupby(["building","same"],observed=True)[fields].mean().reset_index()
            for r in nb.to_dict("records"):same_pair_rows.append(dict(method_id=mid,domain=domain,matched_events=len(matched),**r))
    pb=pd.DataFrame(building_rows);write_csv(a.out/"nested_stress_building.csv",pb)
    write_csv(a.out/"nested_stress_pool_n_source.csv.gz",pd.DataFrame(cell_rows))
    write_csv(a.out/"nested_stress_class_pair_building.csv.gz",pd.DataFrame(class_rows))
    write_csv(a.out/"nested_stress_support.csv",pd.DataFrame(ledgers))
    write_csv(a.out/"nested_same_pair_changed_background.csv",pd.DataFrame(same_pair_rows))
    numeric=[c for c in pb.select_dtypes(include="number").columns if c not in ["images","matched_pool_n_source_strata"]]
    summary=pb.groupby(["method_id","domain"],observed=True)[numeric].mean().reset_index()
    support=pb.groupby(["method_id","domain"],observed=True).agg(buildings=("building","nunique"),images=("images","sum"),strata=("matched_pool_n_source_strata","sum")).reset_index()
    summary=summary.merge(support,on=["method_id","domain"])
    write_csv(a.out/"nested_stress_summary.csv",summary)
    write_json(a.out/"NESTED_STRESS_RECEIPT.json",clean(dict(
        inputs=hashes,source_panel=NESTED_PANEL,source_history_events=len(nested),
        source_history_images=nested.pool_id.nunique(),source_history_buildings=nested.building.nunique(),
        frozen_labels_unchanged=True,labels_refitted=False,used_for_candidate_selection=False,
        comparison="Same pool/reference/n/entrant-source-pair, different actual fixed backgrounds; never exact-background contrast because A_nested has one pair per core.",
        independence="Historical buildings/images and prior generated team evidence; no new independent image or external blind-test claim.",
        source_script_sha256=sha(Path(__file__)),elapsed_seconds=time.perf_counter()-start)))


if __name__=="__main__":main()
