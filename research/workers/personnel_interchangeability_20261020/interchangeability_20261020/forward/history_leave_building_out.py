#!/usr/bin/env python3
"""History-building removal sensitivity; never a new worker/image validation.

All labels are refitted from the remaining nine history buildings. The main
frozen labels are never overwritten. Only compact label and support summaries
are saved, not per-fold feature/model caches.
"""
from __future__ import annotations

import argparse
import gzip
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score

from audit_and_features import BASE, clean, extend, js, load_module, sha
from build_candidates import define_candidates


def pair_measures(a,b):
    n=len(a)
    if n<2:
        return {}
    ii,jj=np.triu_indices(n,1)
    wa=np.asarray(a)[ii]==np.asarray(a)[jj]
    wb=np.asarray(b)[ii]==np.asarray(b)[jj]
    ua,ub=sorted(set(a)),sorted(set(b))
    cross=np.array([[sum((np.asarray(a)==x)&(np.asarray(b)==y)) for y in ub] for x in ua])
    r,c=linear_sum_assignment(-cross)
    return dict(common_worker_pairs=len(ii),ARI=adjusted_rand_score(a,b),
                pair_coassignment_agreement=float((wa==wb).mean()),
                frozen_within_pairs=int(wa.sum()),
                frozen_within_pairs_retained=float(wb[wa].mean()) if wa.any() else None,
                frozen_between_pairs_retained=float((~wb[~wa]).mean()) if (~wa).any() else None,
                best_label_aligned_worker_fraction=float(cross[r,c].sum()/n))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dir",type=Path,default=Path(__file__).resolve().parent)
    ap.add_argument("--repo",type=Path,default=BASE/"repo")
    ap.add_argument("--prior",type=Path,default=BASE/"current_main_20261020/research/workers/personnel_composition_study_20261019/analysis")
    ap.add_argument("--folds",type=int,default=10)
    args=ap.parse_args()
    original_sha={p.name:sha(p) for p in [args.dir/"worker_labels.csv.gz",args.dir/"method_manifest.json"]}
    fixed=pd.read_csv(args.dir/"worker_labels.csv.gz")
    priorf=pd.read_csv(args.dir/"features_train.csv.gz")
    manifest=json.loads((args.dir/"method_manifest.json").read_text())
    short=json.loads((args.dir/"SHORTLIST.json").read_text())
    methods={x["method_id"] for x in short["items"]}
    for family in short["additional_ablation_families"]:
        methods.update(family["method_ids"])
    buildings=manifest["history_buildings"]
    old=load_module(args.prior/"forward/build_forward.py","old_features_for_history_sensitivity")
    _,fn=old.upstream_functions(args.repo)
    records=json.load(gzip.open(args.repo/old.RECORD_SOURCE,"rt"))["records"]
    # The adopted history filter is applied before any refit.
    records=[r for r in records if r["building_id"] in buildings]
    d,ex=old.flatten(records),fn["extra_frame"](records)
    allrows,foldlabels,receipts=[],[],[]
    for held in buildings[:args.folds]:
        train=[b for b in buildings if b!=held]
        dd,ee=d[d.building_id.isin(train)].copy(),ex[ex.building_id.isin(train)].copy()
        f,meta=fn["_training_features"](dd,ee,priorf.worker_id.tolist(),train)
        f,_=old.conditional_features(dd,f,train,fn,"B8L2")
        f.insert(0,"train_key","history_LOBO_"+held)
        f,_,_,_=extend(f,dd,ee,fn)
        c=define_candidates(f)
        labels=pd.DataFrame(c.rows)
        labels=labels[labels.method_id.isin(methods)].copy()
        labels.insert(0,"removed_history_building",held)
        foldlabels.append(labels)
        for mid in sorted(methods):
            a=fixed[fixed.method_id.eq(mid)]
            b=labels[labels.method_id.eq(mid)]
            fa=a[a.known].set_index("worker_id")
            fb=b[b.known].set_index("worker_id")
            common=sorted(set(fa.index)&set(fb.index))
            lost=sorted(set(fa.index)-set(fb.index))
            gained=sorted(set(fb.index)-set(fa.index))
            req=manifest["methods"][mid]["required_fields"]
            required_people=manifest["methods"][mid]["history_feature_supported_workers"]
            before=priorf.set_index("worker_id").loc[required_people,req].to_numpy(float)
            after=f.set_index("worker_id").loc[required_people,req].to_numpy(float)
            observed_inputs_changed=not np.allclose(before,after,rtol=0,atol=1e-9,equal_nan=True)
            fitting_population_changed=set(fa.index)!=set(fb.index)
            pm=pair_measures(fa.loc[common,"class_id"].tolist(),fb.loc[common,"class_id"].tolist())
            allrows.append(dict(method_id=mid,domain=manifest["methods"][mid]["domain"],
                removed_history_building=held,frozen_known_people=len(fa),refit_known_people=len(fb),
                required_feature_values_changed=observed_inputs_changed,
                fitting_population_changed=fitting_population_changed,
                informative_removal=observed_inputs_changed or fitting_population_changed,
                common_people=len(common),lost_people=len(lost),gained_people=len(gained),
                lost_worker_ids="|".join(lost),gained_worker_ids="|".join(gained),
                known_set_jaccard=len(common)/len(set(fa.index)|set(fb.index)) if len(set(fa.index)|set(fb.index)) else None,
                refit_classes=c.methods[mid]["classes_n"],refit_status=c.methods[mid]["status"],**pm))
        receipts.append(dict(removed_history_building=held,training_buildings=train,
                             history_records=len(dd),formal_quality_history_rows=meta["q_records"],
                             methods=len(methods)))
        print(json.dumps({"completed_fold":held,"folds_completed":len(receipts),"methods":len(methods),
                          "history_Q_rows":meta["q_records"]}),flush=True)
    detail=pd.DataFrame(allrows)
    detail.to_csv(args.dir/"HISTORY_LOBO_per_fold.csv",index=False)
    pd.concat(foldlabels,ignore_index=True).to_csv(args.dir/"HISTORY_LOBO_labels.csv.gz",index=False)
    rows=[]
    for mid,g in detail.groupby("method_id"):
        informative=g[g.informative_removal]
        rows.append(dict(method_id=mid,domain=g.domain.iloc[0],folds=len(g),
            frozen_known_people=g.frozen_known_people.iloc[0],
            refit_known_min=g.refit_known_people.min(),refit_known_max=g.refit_known_people.max(),
            common_people_min=g.common_people.min(),known_set_jaccard_mean=g.known_set_jaccard.mean(),
            ARI_mean=g.ARI.mean(),ARI_min=g.ARI.min(),ARI_max=g.ARI.max(),
            within_pair_retention_mean=g.frozen_within_pairs_retained.mean(),
            within_pair_retention_min=g.frozen_within_pairs_retained.min(),
            best_aligned_people_fraction_mean=g.best_label_aligned_worker_fraction.mean(),
            failed_partition_folds=int(g.refit_classes.lt(2).sum()),
            informative_removal_folds=len(informative),
            informative_folds_with_estimable_ARI=int(informative.ARI.notna().sum()),
            informative_removal_ARI_mean=informative.ARI.mean(),
            informative_removal_ARI_min=informative.ARI.min(),
            informative_failed_partitions=int(informative.refit_classes.lt(2).sum()),
            folds_losing_at_least_20pct_people=int((g.common_people<.8*g.frozen_known_people).sum())))
    pd.DataFrame(rows).to_csv(args.dir/"HISTORY_LOBO_summary.csv",index=False)
    assert original_sha=={p.name:sha(p) for p in [args.dir/"worker_labels.csv.gz",args.dir/"method_manifest.json"]}
    js(args.dir/"HISTORY_LOBO_RECEIPT.json",dict(utc=datetime.now(timezone.utc).isoformat(),
        interpretation="Refit on nine of ten already-adopted historical buildings. Label sensitivity only, not independent new-image or new-worker validation; common-set ARI always accompanies lost/gained support.",
        main_labels_unchanged=original_sha,methods=sorted(methods),folds=receipts,
        target_fusion_outcomes_read=False,code_sha256=sha(Path(__file__))))


if __name__=="__main__":
    main()
