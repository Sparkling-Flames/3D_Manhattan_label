#!/usr/bin/env python3
"""Explain and audit frozen direct-swap classes using history inputs only.

Class profiles and relation tails are in-sample descriptions, not held-out
class efficacy. Leave-one-building fits diagnose training-label sensitivity.
No class is renamed/reordered by its explanatory variables.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

from learn_swap_types import (MIN_CLASS, OLD_PANEL, SEED, clean, domain_mask,
    fit_labels, load_history, make_graph, pair_building_table, sha,
    write_csv, write_json)

FEATURES = [
    "q_beta", "q_abs_mean", "q_abs_p10", "q_abs_sd", "q_residual_p10",
    "q_residual_sd", "pair_count_effect", "pair_count_residual_sd",
    "bottom_y_effect", "top_y_effect", "height_log_effect",
    "t_source_origin_effect", "t_log_residual_tail", "source_time_median",
    "theta_easy", "theta_medium", "theta_hard", "hard_minus_easy",
    "hard_minus_medium", "semi_old_error_nonedit_effect",
    "semi_new_error_nonedit_effect", "semi_old_edit_effect",
    "semi_new_edit_effect", "scope_out_effect", "scope_gold_n",
]
SUPPORT_FIELDS = [
    "core_supported", "core_tasks", "core_buildings", "hard_supported",
    "hard_tasks", "hard_buildings", "t_supported", "t_records",
    "t_buildings", "semi_old_error_nonedit_supported",
    "semi_old_error_nonedit_records", "semi_new_error_nonedit_supported",
    "semi_new_error_nonedit_records", "semi_old_edit_supported",
    "semi_old_edit_records", "semi_new_edit_supported",
    "semi_new_edit_records", "scope_supported", "scope_records",
    "scope_gold_n",
]
RISK_FIELDS = ["stable_main", "stable_geometry", "stable_wide", "failure",
               "continuous_loss", "abs_B8L2_change", "prism_distance",
               "floor_jaccard_difference", "node_different", "mean_endpoint_Q"]


def finite_stats(values):
    x = np.asarray(values, float); x = x[np.isfinite(x)]
    if not len(x):
        return dict(n=0, mean=np.nan, p10=np.nan, p50=np.nan, p90=np.nan)
    return dict(n=len(x), mean=x.mean(), p10=np.quantile(x, .1),
                p50=np.median(x), p90=np.quantile(x, .9))


def eta_squared(values, labels):
    x = np.asarray(values, float); y = np.asarray(labels)
    keep = np.isfinite(x); x=x[keep]; y=y[keep]
    if len(x)<2 or np.var(x)==0:
        return np.nan
    total=np.square(x-x.mean()).sum()
    return sum(np.sum(y==c)*(x[y==c].mean()-x.mean())**2
               for c in sorted(set(y)))/total


def explain(manifest, labels, features, relations):
    profiles=[]; associations=[]; risk_rows=[]
    f=features.set_index("worker_id")
    for mid, spec in manifest.items():
        if spec["full_history_status"]!="ok":
            continue
        roster={w:c for c, ws in spec["classes"].items() for w in ws}
        workers=sorted(roster); ff=f.loc[workers]
        classes=np.asarray([roster[w] for w in workers])
        origins=ff.person_origin.to_numpy()
        assoc=dict(method_id=mid,domain=spec["domain"],workers=len(workers),
                   k=spec["requested_k"],minimum_class=min(spec["class_sizes"].values()),
                   source_nmi=normalized_mutual_info_score(origins,classes))
        counts=pd.crosstab(classes,origins).to_numpy(float)
        expected=counts.sum(axis=1)[:,None]*counts.sum(axis=0)[None,:]/counts.sum()
        assoc["source_cramers_v"]=(np.sqrt(np.divide(np.square(counts-expected),expected,
            out=np.zeros_like(counts),where=expected>0).sum()/counts.sum())
            if counts.shape[1]>1 else np.nan)
        for feature in FEATURES:
            assoc[feature+"_eta2"]=eta_squared(ff[feature], classes)
        associations.append(assoc)
        pair=relations[relations.domain.eq(spec["domain"])].copy()
        for c, ws in spec["classes"].items():
            part=f.loc[ws]
            row=dict(method_id=mid,domain=spec["domain"],class_id=c,
                     workers="|".join(ws),n_workers=len(ws),
                     new_workers=int(part.person_origin.eq("new").sum()),
                     v1_workers=int(part.person_origin.eq("v1").sum()),
                     evidence_role="full-history descriptive explanation; not validation")
            for feature in FEATURES:
                for stat,value in finite_stats(part[feature]).items():
                    row[feature+"_"+stat]=value
            for feature in SUPPORT_FIELDS:
                row[feature+"_sum"]=pd.to_numeric(part[feature],errors="coerce").sum(min_count=1)
            profiles.append(row)
            p=pair[pair.worker_a.isin(ws)&pair.worker_b.isin(ws)]
            kp=p[p.relation_known.eq(True)]
            rr=dict(method_id=mid,domain=spec["domain"],class_id=c,n_workers=len(ws),
                    possible_pairs=len(ws)*(len(ws)-1)//2, observed_pairs=len(p),
                    supported_pairs=len(kp),unknown_pairs=len(ws)*(len(ws)-1)//2-len(kp),
                    evidence_role="full-history observed unshrunk pair means; in-sample")
            for feature in RISK_FIELDS:
                for stat,value in finite_stats(kp[feature]).items():
                    rr[feature+"_"+stat]=value
            if len(kp):
                worst=kp.sort_values(["stable_main","worker_a","worker_b"]).iloc[0]
                rr.update(worst_main_pair_a=worst.worker_a,worst_main_pair_b=worst.worker_b,
                          worst_main_pair_rate=worst.stable_main,
                          worst_main_pair_images=worst.images,worst_main_pair_buildings=worst.buildings)
            risk_rows.append(rr)
    return pd.DataFrame(profiles),pd.DataFrame(associations),pd.DataFrame(risk_rows)


def class_pair_table(spec, relations):
    mapper={w:c for c,ws in spec["classes"].items() for w in ws}
    p=relations[relations.domain.eq(spec["domain"])].copy()
    p["class_a"]=p.worker_a.map(mapper);p["class_b"]=p.worker_b.map(mapper)
    p=p[p.class_a.notna()&p.class_b.notna()]
    pair=np.sort(p[["class_a","class_b"]].to_numpy(),axis=1)
    p["class_a"],p["class_b"]=pair[:,0],pair[:,1]
    rows=[]
    for (a,b),g in p.groupby(["class_a","class_b"]):
        known=g[g.relation_known.eq(True)]
        possible=(len(spec["classes"][a])*(len(spec["classes"][a])-1)//2 if a==b
                  else len(spec["classes"][a])*len(spec["classes"][b]))
        row=dict(method_id=spec["method_id"],domain=spec["domain"],class_a=a,class_b=b,
                 same=a==b,possible_pairs=possible,observed_pairs=len(g),
                 supported_pairs=len(known),unknown_pairs=possible-len(known),
                 evidence_role="full-history observed unshrunk person-pair means; in-sample")
        for feature in RISK_FIELDS:
            for stat,value in finite_stats(known[feature]).items():
                row[feature+"_"+stat]=value
        rows.append(row)
    return rows


def lobo(specs, data, split, full_labels, gate):
    rows=[]; sensitivities=[]; graphs={}
    for domain in sorted({s["domain"] for s in specs}):
        df=data.loc[domain_mask(data,domain)]
        pb=pair_building_table(df)
        graphs[domain]=(df,pb,make_graph(df,pb))
    for spec in specs:
        mid=spec["method_id"]; domain=spec["domain"]
        df,pb,fullgraph=graphs[domain]
        reference={w:c for c,ws in spec["classes"].items() for w in ws}
        for prior in [0,1,3]:
            graph=fullgraph if prior==1 else make_graph(df,pb,prior=prior)
            labs,status=fit_labels(graph,spec["representation"],spec["algorithm"],
                spec["requested_k"],SEED+spec["requested_k"],gate)
            row=dict(method_id=mid,domain=domain,prior_equivalent_buildings=prior,status=status)
            if labs is not None:
                ref=np.asarray([reference[w] for w in graph["workers"]]);ari=adjusted_rand_score(ref,labs)
                same_a=ref[:,None]==ref[None,:];same_b=labs[:,None]==labs[None,:]
                tri=np.triu_indices(len(labs),1)
                row.update(ari=ari,pair_flip_fraction=np.mean(same_a[tri]!=same_b[tri]),
                           class_sizes="|".join(map(str,np.bincount(labs))))
                if prior==1:
                    assert ari==1, (mid,"public full-fit labels failed exact graph reconstruction")
            sensitivities.append(row)
        for dropped in split["history_buildings"]:
            train=df[~df.building.eq(dropped)]; trainpb=pb[~pb.building.eq(dropped)]
            graph=make_graph(train,trainpb)
            labs,status=fit_labels(graph,spec["representation"],spec["algorithm"],
                spec["requested_k"],SEED+spec["requested_k"],gate)
            row=dict(method_id=mid,domain=domain,dropped_building=dropped,status=status,
                     full_workers=len(reference),remaining_supported_workers=len(graph["workers"]),
                     dropped_worker_support=len(set(reference)-set(graph["workers"])))
            if labs is not None:
                ref=np.asarray([reference[w] for w in graph["workers"]])
                tri=np.triu_indices(len(labs),1)
                row.update(ari=adjusted_rand_score(ref,labs),
                    pair_flip_fraction=np.mean((ref[:,None]==ref[None,:])[tri]!=(labs[:,None]==labs[None,:])[tri]),
                    class_sizes="|".join(map(str,np.bincount(labs))))
            rows.append(row)
        print(json.dumps({"audit_lobo_method":mid,"done_buildings":10}),flush=True)
    return pd.DataFrame(rows),pd.DataFrame(sensitivities)


def relation_nontransitivity(relations):
    """Global graph evidence; unequal edge opportunities remain visible."""
    rows=[];examples=[]
    for domain,p in relations.groupby("domain"):
        p=p[p.relation_known.eq(True)]
        workers=sorted(set(p.worker_a)|set(p.worker_b)); idx={w:i for i,w in enumerate(workers)}
        n=len(workers); known=np.zeros((n,n),bool)
        for a,b in p[["worker_a","worker_b"]].itertuples(index=False,name=None):
            known[idx[a],idx[b]]=known[idx[b],idx[a]]=True
        for metric in ["stable_main","stable_geometry"]:
            P=np.full((n,n),np.nan)
            support={}
            for r in p.itertuples(index=False):
                a,b=idx[r.worker_a],idx[r.worker_b]
                P[a,b]=P[b,a]=getattr(r,metric)
                support[tuple(sorted([a,b]))]=(int(r.images),int(r.buildings))
            for threshold in [.65,.8]:
                low=threshold-.15; good=P>=threshold
                closed=0;wedges=0;unknown_closing=0;violations=[]
                for center in range(n):
                    for a,c in itertools.combinations(np.flatnonzero(good[center]),2):
                        if not known[a,c]:
                            unknown_closing+=1;continue
                        wedges+=1
                        if P[a,c]>=threshold:closed+=1
                        if P[a,c]<=low:
                            violations.append((min(P[a,center],P[center,c])-P[a,c],a,center,c))
                rows.append(dict(domain=domain,metric=metric,stable_threshold=threshold,
                    closing_bad_threshold=low,workers=n,supported_pairs=len(p),
                    supported_good_wedges=wedges,unknown_closing_edge_wedges=unknown_closing,
                    closed_good_wedges=closed,material_nontransitive_wedges=len(violations),
                    material_nontransitive_fraction=len(violations)/wedges if wedges else np.nan,
                    evidence_role="full-history aggregate edges; different edge opportunities, not a same-context claim"))
                for margin,a,b,c in sorted(violations,reverse=True)[:3]:
                    examples.append(dict(domain=domain,metric=metric,stable_threshold=threshold,
                        a=workers[a],b=workers[b],c=workers[c],p_ab=P[a,b],p_bc=P[b,c],p_ac=P[a,c],margin=margin,
                        support_ab=support[tuple(sorted([a,b]))],support_bc=support[tuple(sorted([b,c]))],
                        support_ac=support[tuple(sorted([a,c]))]))
    return pd.DataFrame(rows),examples


def same_context_nontransitivity(data):
    """Exact real A/B/C outcomes on identical image,n,core; no estimated edge."""
    rows=[];examples=[]
    # Main and no-Q geometry conditions share the same full entrant graph. This
    # pass uses ordinary history only; source/difficulty/n strata stay explicit.
    for keys,g in data.groupby(["panel_id","building","pool_id","k","background_id"],sort=True):
        workers=sorted(set(g.worker_a)|set(g.worker_b));idx={w:i for i,w in enumerate(workers)};n=len(workers)
        assert len(g)==n*(n-1)//2,(keys,"not a complete actual entrant panel")
        ai=g.worker_a.map(idx).to_numpy();bi=g.worker_b.map(idx).to_numpy()
        for metric in ["stable_main","stable_geometry"]:
            A=np.zeros((n,n),dtype=np.int64);A[ai,bi]=A[bi,ai]=g[metric].to_numpy(dtype=np.int64)
            degree=A.sum(axis=1);wedges=int((degree*(degree-1)//2).sum())
            two=A@A
            open_count=int(two[np.triu(~A.astype(bool),1)].sum())
            row=dict(panel_id=keys[0],building=keys[1],pool_id=keys[2],k=keys[3],background_id=keys[4],
                     difficulty=g.difficulty.iloc[0],metric=metric,entrant_workers=n,
                     actual_pairs=len(g),good_wedges=wedges,nontransitive_wedges=open_count,
                     nontransitive_fraction=open_count/wedges if wedges else np.nan)
            rows.append(row)
            # Keep one deterministic exact triple per metric/building for review.
            if open_count and not any(e["metric"]==metric and e["building"]==keys[1] for e in examples):
                a,c=next((a,c) for a,c in itertools.combinations(range(n),2) if not A[a,c] and two[a,c]>0)
                b=int(np.flatnonzero((A[a]>0)&(A[c]>0))[0])
                edges=[]
                for x,y in [(a,b),(b,c),(a,c)]:
                    wa,wb=sorted([workers[x],workers[y]])
                    r=g[(g.worker_a==wa)&(g.worker_b==wb)].iloc[0]
                    edges.append({name:r[name] for name in ["event_id","worker_a","worker_b","team_id_a","team_id_b",
                        "member_workers_a","member_workers_b","B8L2_a","B8L2_b","abs_B8L2_change",
                        "floor_jaccard_difference","node_count_difference","structure_bound_cyclic_deg",
                        "stable_main","stable_geometry"]})
                examples.append(dict(metric=metric,building=keys[1],pool_id=keys[2],k=keys[3],background_id=keys[4],
                    a=workers[a],b=workers[b],c=workers[c],background_members=g.background_members.iloc[0],edges=edges))
    contexts=pd.DataFrame(rows)
    # A context with no two-good-edge opportunity has undefined rate, not zero.
    pn=contexts.groupby(["panel_id","building","pool_id","k","difficulty","metric"],observed=True)["nontransitive_fraction"].mean().reset_index()
    image=pn.groupby(["panel_id","building","pool_id","difficulty","metric"],observed=True)["nontransitive_fraction"].mean().reset_index()
    building=image.groupby(["panel_id","building","metric"],observed=True)["nontransitive_fraction"].mean().reset_index()
    return contexts,building,examples


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path.cwd())
    ap.add_argument("--fit",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--shortlist",type=Path);ap.add_argument("--supplemental-events",type=Path)
    ap.add_argument("--lobo",action="store_true");ap.add_argument("--nontransitivity",action="store_true")
    args=ap.parse_args();root=args.root.resolve();args.out.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    manifest=json.load(open(args.fit/"METHOD_MANIFEST.json"));labels=pd.read_csv(args.fit/"worker_labels.csv.gz")
    registration=json.load(open(args.fit/"REGISTRATION.json"))
    features=pd.read_csv(root/"analysis/forward/results/features_train.csv.gz")
    assert set(features.train_key)=={"history_d199d7b13dccfe7e"}
    relations=pd.read_csv(args.fit/"historical_pair_relations.csv.gz")
    profiles,assoc,risks=explain(manifest,labels,features,relations)
    write_csv(args.out/"class_explanations.csv.gz",profiles)
    write_csv(args.out/"method_feature_association.csv.gz",assoc)
    write_csv(args.out/"class_history_relation_tails.csv.gz",risks)
    specs=[]
    if args.shortlist:
        shortlist=json.load(open(args.shortlist))
        specs=[manifest[s["method_id"] if isinstance(s,dict) else s] for s in shortlist["methods"]]
        write_csv(args.out/"selected_class_pair_history.csv",pd.DataFrame([r for s in specs for r in class_pair_table(s,relations)]))
    if args.lobo or args.nontransitivity:
        frame,split,input_audit=load_history(root,args.supplemental_events)
        panels=registration.get("source_panels_for_learning",[registration.get("source_panel_for_learning")])
        data=frame[frame.panel_id.isin(panels)].copy()
        if args.lobo:
            assert specs
            folds,sens=lobo(specs,data,split,labels,registration["opportunity"].get("each_class_known_pair_fraction_min",0))
            write_csv(args.out/"lobo_label_stability.csv",folds)
            write_csv(args.out/"opportunity_shrinkage_sensitivity.csv",sens)
        if args.nontransitivity:
            table,examples=relation_nontransitivity(relations)
            write_csv(args.out/"aggregate_relation_nontransitivity.csv",table)
            write_json(args.out/"aggregate_nontransitivity_examples.json",clean(examples))
            contexts,building,actual_examples=same_context_nontransitivity(data)
            write_csv(args.out/"actual_context_nontransitivity.csv.gz",contexts)
            write_csv(args.out/"actual_nontransitivity_building.csv",building)
            write_json(args.out/"actual_nontransitivity_examples.json",clean(actual_examples))
    write_json(args.out/"AUDIT_EXPLANATION_RECEIPT.json",clean(dict(
        source_labels_sha256=sha(args.fit/"worker_labels.csv.gz"),
        source_manifest_sha256=sha(args.fit/"METHOD_MANIFEST.json"),
        source_features_sha256=sha(root/"analysis/forward/results/features_train.csv.gz"),
        source_script_sha256=sha(Path(__file__)),
        explanation_role="descriptive history features only; no relabeling and no selected-outcome refinement",
        lobo_role="training-label sensitivity across old history buildings; not target efficacy validation",
        minimum_class_size=MIN_CLASS,profile_rows=len(profiles),valid_methods=len(assoc),
        opportunity_semantics="finite/support counts retained; missing opportunities are not zero ability",
        same_context_nontransitivity_role="engineering thresholds need not be transitive; this diagnoses boundary/graph limits, not impossible useful conditional classes",
        elapsed_seconds=time.perf_counter()-start)))


if __name__=="__main__":main()
