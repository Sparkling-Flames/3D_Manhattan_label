#!/usr/bin/env python3
"""History-CV source and source-preserving capacity baselines.

Training folds, worker eligibility, real held-out anchors, n weighting and
source composition are identical to the direct-risk candidate. No full-history
Q-derived labels are used as an inner-fold baseline. Random draws preserve the
exact source count of every candidate class, hence also every class capacity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

from learn_swap_types import (SEED, clean, domain_mask, evaluate, fit_labels,
    load_history, make_graph, make_inner_folds, pair_building_table, sha,
    write_csv, write_json)

BASE_SEED=2026102005
METRICS=["stable_main","stable_geometry","stable_wide","continuous_loss","failure"]


def factor(frame):
    if not len(frame):
        return np.array([],dtype=int),frame.copy()
    codes,unique=pd.factorize(pd.MultiIndex.from_frame(frame),sort=True)
    table=unique.to_frame(index=False)
    table.columns=frame.columns
    return codes,table


class FastAnchors:
    """Exact numpy implementation of the original pandas evaluator's means."""
    def __init__(self,frame,workers):
        mapper={w:i for i,w in enumerate(workers)}
        a=frame.worker_a.map(mapper);b=frame.worker_b.map(mapper)
        keep=a.notna()&b.notna();d=frame.loc[keep]
        self.a=a[keep].to_numpy(int);self.b=b[keep].to_numpy(int)
        self.metrics=d[METRICS].to_numpy(float)
        assert np.isfinite(self.metrics).all()
        self.bg,bg=factor(d[["building","pool_id","k","background_id"]])
        self.pn,pn=factor(bg[["building","pool_id","k"]])
        self.pi,pi=factor(pn[["building","pool_id"]])
        self.pb,pb=factor(pi[["building"]])
        self.nbg,self.npn,self.npi,self.npb=len(bg),len(pn),len(pi),len(pb)
        self.buildings=pb.building.tolist()
        self.background_buildings=bg.building.to_numpy()

    @staticmethod
    def reduce(values,codes,n):
        dims=values.shape[1:]
        if not len(values):
            return np.full((n,)+dims,np.nan)
        flat=values.reshape(len(values),-1)
        result=np.full((n,flat.shape[1]),np.nan)
        for j in range(flat.shape[1]):
            finite=np.isfinite(flat[:,j]);den=np.bincount(codes[finite],minlength=n)
            num=np.bincount(codes[finite],weights=flat[finite,j],minlength=n)
            np.divide(num,den,out=result[:,j],where=den>0)
        return result.reshape((n,)+dims)

    def common_mask(self,labels):
        same=labels[self.a]==labels[self.b]
        counts=np.bincount(2*self.bg+same,minlength=2*self.nbg).reshape(self.nbg,2)
        return (counts[:,0]>0)&(counts[:,1]>0)

    def evaluate(self,labels,common_mask=None):
        same=labels[self.a]==labels[self.b]
        groups=2*self.bg+same
        counts=np.bincount(groups,minlength=2*self.nbg).reshape(self.nbg,2)
        value=np.full((self.nbg,2,len(METRICS)),np.nan)
        common=(counts[:,0]>0)&(counts[:,1]>0)
        if common_mask is not None:
            common &= common_mask
        for j in range(len(METRICS)):
            sums=np.bincount(groups,weights=self.metrics[:,j],minlength=2*self.nbg).reshape(self.nbg,2)
            np.divide(sums,counts,out=value[:,:,j],where=counts>0)
        value[~common]=np.nan
        pn=self.reduce(value,self.pn,self.npn)
        pi=self.reduce(pn,self.pi,self.npi)
        pb=self.reduce(pi,self.pb,self.npb)
        rows=[]
        for i,building in enumerate(self.buildings):
            if not np.isfinite(pb[i]).any():continue
            r=dict(building=building)
            for j,metric in enumerate(METRICS):
                r["within_"+metric]=pb[i,1,j];r["between_"+metric]=pb[i,0,j]
            r["gap_main"]=r["within_stable_main"]-r["between_stable_main"]
            r["gap_geometry"]=r["within_stable_geometry"]-r["between_stable_geometry"]
            r["gap_continuous"]=r["between_continuous_loss"]-r["within_continuous_loss"]
            r["within_bad_wide"]=1-r["within_stable_wide"]
            r["selection_score"]=(r["gap_main"]+.5*r["gap_geometry"]+.25*r["gap_continuous"]
                                   -.5*r["within_bad_wide"]-.1*r["within_failure"])
            rows.append(r)
        return rows

    def paired(self,candidate,baseline):
        common=self.common_mask(candidate)&self.common_mask(baseline)
        a={r["building"]:r for r in self.evaluate(candidate,common)}
        b={r["building"]:r for r in self.evaluate(baseline,common)}
        assert set(a)==set(b)
        rows=[]
        for building in sorted(a):
            r=dict(building=building,matched_backgrounds=int(np.sum(common&(self.background_buildings==building))))
            for key,value in a[building].items():
                if key=="building":continue
                r["candidate_"+key]=value;r["baseline_"+key]=b[building][key]
                r["delta_"+key]=value-b[building][key]
            rows.append(r)
        return rows


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path.cwd())
    ap.add_argument("--fit",type=Path,required=True);ap.add_argument("--shortlist",type=Path,required=True)
    ap.add_argument("--supplemental-events",type=Path);ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--random-draws",type=int,default=40)
    args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    manifest=json.load(open(args.fit/"METHOD_MANIFEST.json"))
    shortlist=json.load(open(args.shortlist));specs=[manifest[x["method_id"] if isinstance(x,dict) else x] for x in shortlist["methods"]]
    registration=json.load(open(args.fit/"REGISTRATION.json"));gate=registration["opportunity"].get("each_class_known_pair_fraction_min",0)
    frame,split,inputaudit=load_history(args.root,args.supplemental_events)
    panels=registration.get("source_panels_for_learning",[registration.get("source_panel_for_learning")])
    data=frame[frame.panel_id.isin(panels)].copy()
    sources=pd.read_csv(args.root/"analysis/forward/results/features_train.csv.gz",usecols=["worker_id","person_origin"]).set_index("worker_id").person_origin.to_dict()
    rows=[];paired_rows=[];ledger=[];cache={};parity=[]
    for domain in sorted({s["domain"] for s in specs}):
        df=data.loc[domain_mask(data,domain)];pb=pair_building_table(df)
        cache[domain]=[]
        for fi,held in enumerate(make_inner_folds(split["history_buildings"])):
            train=df[~df.building.isin(held)];test=df[df.building.isin(held)]
            graph=make_graph(train,pb[~pb.building.isin(held)])
            cache[domain].append((fi,graph,test,FastAnchors(test,graph["workers"])))
    for spec in specs:
        mid=spec["method_id"];domain=spec["domain"]
        method_seed=int(hashlib.sha256(mid.encode()).hexdigest()[:12],16)
        for fi,graph,test,fast in cache[domain]:
            labels,status=fit_labels(graph,spec["representation"],spec["algorithm"],spec["requested_k"],SEED+fi*1000+spec["requested_k"],gate)
            ledger.append(dict(method_id=mid,domain=domain,fold=fi,status=status,training_workers=len(graph["workers"])))
            if labels is None:continue
            actual=fast.evaluate(labels);reference,_=evaluate(test,graph["workers"],labels)
            lookup={r["building"]:r for r in actual}
            maximum=0.
            for r in reference.to_dict("records"):
                assert r["building"] in lookup
                for key,value in lookup[r["building"]].items():
                    if key=="building":continue
                    maximum=max(maximum,abs(value-r[key]))
            assert len(actual)==len(reference) and maximum<1e-10,(mid,fi,maximum)
            parity.append(dict(method_id=mid,fold=fi,maximum_abs_difference=maximum,building_rows=len(actual)))
            for r in actual:rows.append(dict(method_id=mid,domain=domain,fold=fi,baseline="observed_direct_types",draw=0,**r))
            origin=np.asarray([sources[w] for w in graph["workers"]])
            source_labels=np.asarray([0 if s=="v1" else 1 for s in origin])
            source_rows=fast.evaluate(source_labels)
            if not source_rows:
                ledger.append(dict(method_id=mid,domain=domain,fold=fi,status="source_only_has_no_same_anchor_between_class_comparison",
                                   training_workers=len(origin)))
            for r in source_rows:rows.append(dict(method_id=mid,domain=domain,fold=fi,baseline="source_only",draw=0,**r))
            for r in fast.paired(labels,source_labels):
                paired_rows.append(dict(method_id=mid,domain=domain,fold=fi,baseline="source_only",draw=0,**r))
            rng=np.random.default_rng(BASE_SEED+method_seed+fi*100000)
            for draw in range(args.random_draws):
                random=labels.copy()
                for source in sorted(set(origin)):
                    indices=np.flatnonzero(origin==source)
                    random[indices]=rng.permutation(labels[indices])
                    assert np.array_equal(np.bincount(random[indices],minlength=spec["requested_k"]),
                                          np.bincount(labels[indices],minlength=spec["requested_k"]))
                for r in fast.evaluate(random):
                    rows.append(dict(method_id=mid,domain=domain,fold=fi,baseline="random_source_preserving_class_capacity",draw=draw,**r))
                for r in fast.paired(labels,random):
                    paired_rows.append(dict(method_id=mid,domain=domain,fold=fi,baseline="random_source_preserving_class_capacity",draw=draw,**r))
        print(json.dumps({"baseline_method_complete":mid,"elapsed_seconds":round(time.perf_counter()-start,1)}),flush=True)
    results=pd.DataFrame(rows);write_csv(args.out/"inner_baseline_building_draws.csv.gz",results)
    write_csv(args.out/"inner_baseline_ledger.csv",pd.DataFrame(ledger))
    write_csv(args.out/"fast_aggregation_parity.csv",pd.DataFrame(parity))
    metrics=[c for c in results.select_dtypes(include="number").columns if c not in ["fold","draw"]]
    # All draws first retain their building-equal metric. Quantiles across
    # permutations are randomization variation, not image confidence intervals.
    bydraw=results.groupby(["method_id","domain","baseline","draw"],observed=True)[metrics].mean().reset_index()
    support=results.groupby(["method_id","domain","baseline","draw"],observed=True).agg(buildings=("building","nunique"),folds=("fold","nunique")).reset_index()
    bydraw=bydraw.merge(support,on=["method_id","domain","baseline","draw"])
    write_csv(args.out/"inner_baseline_draw_summary.csv",bydraw)
    summary=[]
    for (mid,domain,base),g in bydraw.groupby(["method_id","domain","baseline"]):
        r=dict(method_id=mid,domain=domain,baseline=base,draws=len(g),
               buildings_min=g.buildings.min(),buildings_max=g.buildings.max())
        for metric in metrics:
            r[metric+"_mean"]=g[metric].mean()
            r[metric+"_p05"]=g[metric].quantile(.05)
            r[metric+"_p95"]=g[metric].quantile(.95)
        summary.append(r)
    write_csv(args.out/"inner_baseline_summary.csv",pd.DataFrame(summary))
    paired=pd.DataFrame(paired_rows)
    write_csv(args.out/"inner_baseline_matched_anchor_building.csv.gz",paired)
    pmetrics=[c for c in paired.select_dtypes(include="number").columns if c not in ["fold","draw","matched_backgrounds"]]
    pdraw=paired.groupby(["method_id","domain","baseline","draw"],observed=True)[pmetrics].mean().reset_index()
    psupport=paired.groupby(["method_id","domain","baseline","draw"],observed=True).agg(buildings=("building","nunique"),matched_backgrounds=("matched_backgrounds","sum")).reset_index()
    pdraw=pdraw.merge(psupport,on=["method_id","domain","baseline","draw"])
    write_csv(args.out/"inner_baseline_matched_anchor_draw.csv",pdraw)
    write_json(args.out/"BASELINE_RECEIPT.json",clean(dict(
        labels_sha256=sha(args.fit/"worker_labels.csv.gz"),shortlist_sha256=sha(args.shortlist),
        source_script_sha256=sha(Path(__file__)),seed=BASE_SEED,random_draws=args.random_draws,
        randomization="Within each training-source cohort permute the fitted labels, preserving every class's new/v1 counts and capacity exactly.",
        evaluation="Same eligible worker cohort and heldout real anchors as candidate; exactly same bg -> n -> image -> building weighting, every contrast requires both within/between pairs on that anchor.",
        matched_anchor_comparison="Separate paired tables restrict candidate and baseline to the intersection of anchors supporting both within/between relations under BOTH partitions; all deltas use identical anchors.",
        source_only="Known source metadata, no quality response. A one-source domain cannot create a source between-class contrast; recorded unavailable.",
        no_full_history_Q_baseline=True,no_discovery_validation_outcomes_loaded=True,
        maximum_fast_vs_original_difference=max(x["maximum_abs_difference"] for x in parity),
        interpretation="Internal history selection/audit only. Random-draw quantiles are not independent image confidence intervals; post-selection results require outer target checks.",
        elapsed_seconds=time.perf_counter()-start)))


if __name__=="__main__":main()
