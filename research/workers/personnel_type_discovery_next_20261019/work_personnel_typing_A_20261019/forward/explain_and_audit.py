#!/usr/bin/env python3
"""Explanation fidelity, building-perturbation stability and class support.

No class or feature is changed by these diagnostics. They do not read outcomes.
"""
from __future__ import annotations
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
import argparse,hashlib,json
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from sklearn.model_selection import KFold
from sklearn.tree import DecisionTreeClassifier,export_text

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
SEED=20261019


def safe(x):
    if isinstance(x,dict):return {str(k):safe(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v)for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
    return x


def writejs(path,x):Path(path).write_text(json.dumps(safe(x),ensure_ascii=False,indent=2,allow_nan=False)+"\n")


def pair_metrics(a,b):
    a=np.asarray(a);b=np.asarray(b);n=len(a)
    if n<2:return {"n_workers":n,"ARI":None,"pair_accuracy":None,"same_pair_jaccard":None,"same_pair_recall":None}
    ix=np.triu_indices(n,1);x=a[ix[0]]==a[ix[1]];y=b[ix[0]]==b[ix[1]]
    return {"n_workers":n,"ARI":float(adjusted_rand_score(a,b)),"pair_accuracy":float(np.mean(x==y)),
            "same_pair_jaccard":float(np.sum(x&y)/np.sum(x|y))if np.any(x|y)else None,
            "same_pair_recall":float(np.sum(x&y)/np.sum(x))if np.any(x)else None,
            "n_reference_same_pairs":int(np.sum(x)),"n_prediction_same_pairs":int(np.sum(y))}


def fit_rule(frame,label,columns):
    known=label[label.class_id.ne("unknown")].set_index("worker_id").class_id
    f=frame.set_index("worker_id").reindex(known.index)
    x=f[[c for c in columns if c in f]].apply(pd.to_numeric,errors="coerce")
    x=x.loc[:,x.notna().sum()>=6]
    med=x.median();x=x.fillna(med)
    model=DecisionTreeClassifier(max_depth=3,min_samples_leaf=3,random_state=SEED)
    model.fit(x,known)
    return model,list(x.columns),med,x,known


def coobserved_support(records,buildings,workers):
    q=records[records.building_id.isin(buildings)&records.quality_usable&records.condition.eq("manual")&records.quality_use.eq("ordinary_primary")]
    images=sorted(q.image_id.unique());wi={w:i for i,w in enumerate(workers)};im={x:i for i,x in enumerate(images)}
    X=np.zeros((len(workers),len(images)),dtype=np.int16)
    for w,i in zip(q.worker_id,q.image_id):X[wi[w],im[i]]=1
    common=X@X.T;bs=np.zeros_like(common)
    for b,g in q.groupby("building_id"):
        cols=[im[x]for x in g.image_id.unique()];bs+=(X[:,cols]@X[:,cols].T>0)
    return common,bs


def class_stability_and_pair_support():
    sets=json.loads((HERE/"TRAINING_SETS.json").read_text());recs=pd.read_csv(HERE/"records_flat.csv")
    labels=pd.read_csv(HERE/"candidate_classes_by_fold.csv.gz")
    allpairs=[];ar=[];worker_rows=[];class_support=[]
    workers=sorted(labels.worker_id.unique());idx={w:i for i,w in enumerate(workers)}
    pair_cache={t:coobserved_support(recs,bs,workers)for t,bs in sets["sets"].items()}
    for (method,domain),g in labels.groupby(["method_id","difficulty"]):
        full=g[g.fold_id.eq("FULL")].set_index("worker_id").class_id
        co={(a,b):[] for a,b in combinations(workers,2)}
        for fold,f in g.groupby("fold_id"):
            lm=f.set_index("worker_id").class_id
            if fold!="FULL":
                known=[w for w in workers if lm[w]!="unknown" and full[w]!="unknown"]
                ar.append({"method_id":method,"difficulty":domain,"fold_id":fold,**pair_metrics(full.loc[known],lm.loc[known])})
                for a,b in combinations(known,2):co[(a,b)].append(lm[a]==lm[b])
                for w in known:
                    fullpeers=set(full[full.eq(full[w])].index)-{w}
                    foldpeers=set(lm[lm.eq(lm[w])].index)-{w}
                    knownothers=set(known)-{w};fullpeers &= knownothers;foldpeers &= knownothers
                    worker_rows.append({"method_id":method,"difficulty":domain,"fold_id":fold,"worker_id":w,
                         "same_class_peer_jaccard":len(fullpeers&foldpeers)/len(fullpeers|foldpeers)if fullpeers|foldpeers else np.nan,
                         "full_class_peers":len(fullpeers),"fold_class_peers":len(foldpeers)})
            tk=f.train_key.iloc[0];common,bs=pair_cache[tk]
            for c,h in f[f.class_id.ne("unknown")].groupby("class_id"):
                members=sorted(h.worker_id);pp=list(combinations(members,2));valid=[(a,b)for a,b in pp if common[idx[a],idx[b]]>=3 and bs[idx[a],idx[b]]>=2]
                class_support.append({"method_id":method,"fold_id":fold,"difficulty":domain,"class_id":c,"members":"|".join(members),
                    "n_workers":len(members),"potential_within_pairs":len(pp),"pairs_with_3_images_2_buildings":len(valid),
                    "workers_with_a_supported_same_class_partner":len(set(v for p in valid for v in p)),
                    "min_common_images":min([common[idx[a],idx[b]]for a,b in pp],default=0),
                    "min_common_buildings":min([bs[idx[a],idx[b]]for a,b in pp],default=0),
                    "singleton":len(members)==1,"doubleton":len(members)==2})
        fullkey=g[g.fold_id.eq("FULL")].train_key.iloc[0];ci,cb=pair_cache[fullkey]
        for (a,b),values in co.items():
            allpairs.append({"method_id":method,"difficulty":domain,"worker_a":a,"worker_b":b,
                  "full_same_class":bool(full[a]==full[b])if full[a]!="unknown"and full[b]!="unknown"else None,
                  "n_known_outer_folds":len(values),"same_class_fraction":float(np.mean(values))if values else np.nan,
                  "n_common_images_full":int(ci[idx[a],idx[b]]),"n_common_buildings_full":int(cb[idx[a],idx[b]])})
    pd.DataFrame(allpairs).to_csv(HERE/"cross_fold_pair_stability.csv.gz",index=False,compression="gzip")
    pd.DataFrame(ar).to_csv(HERE/"cross_fold_partition_stability.csv",index=False)
    pd.DataFrame(worker_rows).to_csv(HERE/"worker_class_peer_stability.csv.gz",index=False,compression="gzip")
    pd.DataFrame(class_support).to_csv(HERE/"class_replacement_support.csv.gz",index=False,compression="gzip")
    writejs(HERE/"CLASS_SUPPORT_STABILITY_RECEIPT.json",{"candidate_methods":labels.method_id.nunique(),"coassignment_rows":len(allpairs),"class_rows":len(class_support),
        "support_definition":"same image in same training building, not same-building attendance on different images; descriptive 3-shared-images/2-shared-buildings gate does not retroactively redefine classes", "outcomes_read":False})


def explanations():
    features=pd.read_csv(HERE/"worker_features_by_training_set.csv.gz")
    labels=pd.read_csv(HERE/"candidate_labels_by_training_set.csv.gz")
    chosen=pd.read_csv(HERE/"selected_classes_by_fold.csv.gz")
    sets=json.loads((HERE/"TRAINING_SETS.json").read_text());aliases=pd.DataFrame(sets["aliases"])
    domains=json.loads((HERE/"FEATURE_DOMAINS.json").read_text());columns=[x for y in domains.values()for x in y]
    fmap={t:g for t,g in features.groupby("train_key")};lmap={(t,m,d):g for (t,m,d),g in labels.groupby(["train_key","method_id","difficulty"])}
    descriptions={};fidelity=[];crossfold=[];predictions=[];feature_summary=[];cache={}
    for (fold,alias,diff),lab in chosen.groupby(["fold_id","method_id","difficulty"]):
        tk=lab.train_key.iloc[0];candidate=lab.candidate_method.iloc[0];f=fmap[tk]
        ck=(tk,candidate,diff)
        if ck not in cache:
            model,cols,med,x,y=fit_rule(f,lab,columns)
            trainpred=model.predict(x);cvpred=pd.Series(index=y.index,dtype=object)
            for tr,te in KFold(n_splits=5,shuffle=True,random_state=SEED).split(x):
                # Recompute explanation-only imputation inside each worker split.
                raw=f.set_index("worker_id").reindex(y.index)[cols]
                allowed=[c for c in raw if raw.iloc[tr][c].notna().sum()>=6]
                raw=raw[allowed]
                fill=raw.iloc[tr].median()
                m=DecisionTreeClassifier(max_depth=3,min_samples_leaf=3,random_state=SEED)
                m.fit(raw.iloc[tr].fillna(fill),y.iloc[tr]);cvpred.iloc[te]=m.predict(raw.iloc[te].fillna(fill))
            result={"training_accuracy":float(np.mean(trainpred==y)),"cross_worker_accuracy":float(np.mean(cvpred==y)),
                    "majority_class_accuracy":float(y.value_counts(normalize=True).iloc[0]),
                    "training":pair_metrics(y,trainpred),"cross_worker":pair_metrics(y,cvpred),"n_features":len(cols),
                    "rules":export_text(model,feature_names=cols,decimals=4),
                    "nonzero_feature_importance":{c:float(v)for c,v in zip(cols,model.feature_importances_)if v>0},
                    "limit":"surrogate fidelity to a discovered historical partition, not future-task behavior accuracy"}
            cache[ck]=(model,cols,med,x,y,trainpred,cvpred,result)
        model,cols,med,x,y,trainpred,cvpred,result=cache[ck]
        prefix={"fold_id":fold,"method_id":alias,"candidate_method":candidate,"difficulty":diff}
        descriptions["|".join([fold,alias,diff])]={**prefix,**result}
        fidelity.append({**prefix,"training_accuracy":result["training_accuracy"],"cross_worker_accuracy":result["cross_worker_accuracy"],
                         "majority_class_accuracy":result["majority_class_accuracy"],
                         "training_ARI":result["training"]["ARI"],"cross_worker_ARI":result["cross_worker"]["ARI"],
                         "n_workers":len(y),"n_features":len(cols)})
        for w,pr,cvr in zip(y.index,trainpred,cvpred):predictions.append({**prefix,"worker_id":w,"class_id":y[w],"rule_class_id":pr,"cross_worker_rule_class_id":cvr})
        marked=f.merge(lab[["worker_id","class_id"]],on="worker_id",validate="one_to_one")
        for c,g in marked[marked.class_id.ne("unknown")].groupby("class_id"):
            for col in columns:
                vals=g[col].dropna()
                feature_summary.append({**prefix,"class_id":c,"feature":col,"class_workers":len(g),"observed_workers":len(vals),
                       "mean":vals.mean(),"median":vals.median(),"p10":vals.quantile(.1),"p90":vals.quantile(.9)})
        if fold!="FULL":
            for _,inner in aliases[aliases.fold_id.eq(fold)&aliases.inner_group.notna()].iterrows():
                ilab=lmap[(inner.train_key,candidate,diff)];ff=fmap[inner.train_key]
                mm,cc,im,xx,yy=fit_rule(ff,ilab,columns)
                known=sorted(set(yy.index)&set(y.index));raw=f.set_index("worker_id").reindex(known)[cc]
                pp=mm.predict(raw.fillna(im));outer_y=y.reindex(known)
                internal=ilab.set_index("worker_id").class_id.reindex(known)
                crossfold.append({**prefix,"inner_group":int(inner.inner_group),
                  **{"rule_"+k:v for k,v in pair_metrics(outer_y,pp).items()},
                  **{"partition_"+k:v for k,v in pair_metrics(outer_y,internal).items()},
                  "interpretation":"training-building perturbation rule fidelity; no target-building actual behavior"})
    writejs(HERE/"EXPLANATORY_RULES.json",descriptions)
    pd.DataFrame(fidelity).to_csv(HERE/"explanation_fidelity.csv",index=False)
    pd.DataFrame(predictions).to_csv(HERE/"explanation_worker_predictions.csv.gz",index=False,compression="gzip")
    pd.DataFrame(crossfold).to_csv(HERE/"explanation_building_perturbation.csv.gz",index=False,compression="gzip")
    pd.DataFrame(feature_summary).to_csv(HERE/"class_feature_summary.csv.gz",index=False,compression="gzip")
    writejs(HERE/"EXPLANATION_RECEIPT.json",{"rule_contexts":len(descriptions),"unique_fitted_rules":len(cache),
            "cross_worker_rule_folds":5,"building_perturbations":len(crossfold),"class_outcomes_used":False,
            "rule_definition":"depth<=3,minleaf>=3, deterministic worker folds; imputation only inside explanation fitting", "type_reassignment_after_explanation":False})


if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--stage",choices=["stability","explain"],required=True);args=ap.parse_args()
    if args.stage=="stability":class_stability_and_pair_support()
    else:explanations()
