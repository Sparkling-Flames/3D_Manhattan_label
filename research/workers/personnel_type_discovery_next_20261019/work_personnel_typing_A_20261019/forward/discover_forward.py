#!/usr/bin/env python3
"""Create all frozen forward partitions, then select only inside training folds."""
from __future__ import annotations
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
import argparse, gzip, hashlib, json, time, uuid
from itertools import combinations
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from sklearn.model_selection import KFold
from sklearn.tree import DecisionTreeClassifier, export_text

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/"reverse"))
from selection_common import attach_relation, fit_calibrator, predict_calibrator, building_brier, one_se_choice
from multiview_partition import partition_features, simple_explanation
from atomic_exports import csv_verified

KS=(4,6,8,10)
FAMILIES=("full","minus_difficulty","minus_semi","minus_scope","minus_structure","QT_only")
DIFFS=("easy","medium","hard")
PANEL="Pro_exact_fixed_background_v1"


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(a) for a in x]
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x


def js(path,obj):Path(path).write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2,allow_nan=False)+"\n")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def family_domains(all_domains,family):
    if family=="QT_only":return {k:v for k,v in all_domains.items() if k in ("Q","T")}
    removed=family.removeprefix("minus_") if family.startswith("minus_") else None
    return {k:v for k,v in all_domains.items() if k!=removed}


def conditional_labels(frame,labels,k):
    """Nested base class + observed-difficulty split, fixed without target data."""
    f=frame.set_index("worker_id");out=[];splits=[]
    m=labels.set_index("worker_id").class_id
    for diff in DIFFS:
        known=f[f[f"{diff}_supported"] & f.core_supported].copy()
        known["base"]=m.reindex(known.index)
        known["contrast"]=known[f"theta_{diff}"]-known.q_beta
        parts={}
        for c,g in known[known.base.ne("unknown")].groupby("base"):
            neg=g[g.contrast<0];pos=g[g.contrast>=0]
            separation=float(pos.contrast.mean()-neg.contrast.mean()) if len(neg) and len(pos) else np.nan
            split=len(neg)>=2 and len(pos)>=2 and separation>=3
            for w,r in g.iterrows():parts[w]=str(c)+(":up" if r.contrast>=0 else ":down") if split else str(c)
            splits.append({"difficulty":diff,"K":k,"base_class_id":c,"n_supported":len(g),
                           "n_negative":len(neg),"n_nonnegative":len(pos),"contrast_mean_separation":separation,"split":split})
        for w in frame.worker_id:
            out.append({"worker_id":w,"difficulty":diff,"class_id":parts.get(w,"unknown"),
                        "unknown_reason":"" if w in parts else "core_or_difficulty_support_below_gate"})
    return pd.DataFrame(out),splits


def build_partitions(metric="B8L2"):
    start=time.time();suffix="" if metric=="B8L2" else "_D10"
    features=pd.read_csv(HERE/f"worker_features_by_training_set{suffix}.csv.gz")
    sets=json.loads((HERE/"TRAINING_SETS.json").read_text())
    assert set(features.train_key)==set(sets["sets"]),"All registered training sets must finish first"
    domains=json.loads((HERE/"FEATURE_DOMAINS.json").read_text())
    labels=[];pairs=[];diagnostics=[];transforms={};conditional_splits=[]
    for n,(train_key,f) in enumerate(features.groupby("train_key",sort=False),1):
        transforms[train_key]={}
        for family in FAMILIES:
            dd=family_domains(domains,family)
            result=partition_features(f,dd,ks=KS,method_id="fw_"+family)
            transforms[train_key][family]=result.transforms
            lab=result.labels.copy();lab["family"]=family;lab["train_key"]=train_key;lab["difficulty"]="all"
            lab["method_id"]=[f"fw_{family}_K{k}" for k in lab.K]
            labels.append(lab)
            pair=result.pairs.copy();pair["train_key"]=train_key;pair["family"]=family;pairs.append(pair)
            dia=result.diagnostics.copy();dia["train_key"]=train_key;dia["family"]=family;diagnostics.append(dia)
            if family=="full":
                for k in KS:
                    cond,split=conditional_labels(f,lab[lab.K.eq(k)],k)
                    cond["K"]=k;cond["family"]="base_plus_difficulty";cond["method_id"]=f"fw_base_plus_difficulty_K{k}";cond["train_key"]=train_key
                    labels.append(cond)
                    conditional_splits.extend([dict(x,train_key=train_key) for x in split])
        print(json.dumps({"partition_training_set":n,"total":features.train_key.nunique(),"train_key":train_key}),flush=True)
    labs=pd.concat(labels,ignore_index=True)
    labs=labs.merge(features[["train_key","worker_id","core_images","core_buildings","core_tasks","core_supported"]],on=["train_key","worker_id"],validate="many_to_one")
    csv_verified(labs,HERE/f"candidate_labels_by_training_set{suffix}.csv.gz")
    alias=pd.DataFrame(sets["aliases"])
    alias=alias[alias.inner_group.isna()].drop(columns=["inner_group","inner_validation_buildings"])
    outer=alias.merge(labs,on="train_key",validate="many_to_many")
    outer["condition"]="ordinary_manual"
    csv_verified(outer,HERE/f"candidate_classes_by_fold{suffix}.csv.gz")
    csv_verified(pd.concat(pairs,ignore_index=True),HERE/f"historical_feature_pair_relations{suffix}.csv.gz")
    csv_verified(pd.concat(diagnostics,ignore_index=True),HERE/f"partition_diagnostics{suffix}.csv")
    csv_verified(pd.DataFrame(conditional_splits),HERE/f"conditional_split_decisions{suffix}.csv.gz")
    js(HERE/f"TRAINED_TRANSFORMS{suffix}.json",transforms)
    js(HERE/f"PARTITION_RECEIPT{suffix}.json",{"metric":metric,"training_sets":features.train_key.nunique(),"candidate_global_families":list(FAMILIES),
          "K":list(KS),"label_rows":len(labs),"outer_label_rows":len(outer),"seconds":time.time()-start,
          "feature_input_sha256":sha(HERE/f"worker_features_by_training_set{suffix}.csv.gz"),"code_sha256":sha(__file__),
          "read_fusion_outcomes":False,"conditional_labels_require_only_observed_frozen_difficulty":True})


def normalize_events(path):
    columns=["event_id","panel_id","pool_id","image_id","building","difficulty","k","worker_a","worker_b","stable_main"]
    f=pd.read_csv(path,usecols=columns)
    f["difficulty"]=f.difficulty.replace({"简单":"easy","中等":"medium","困难":"hard"})
    if not pd.api.types.is_bool_dtype(f.stable_main):
        f["stable_main"]=f.stable_main.astype(str).map({"True":True,"False":False,"true":True,"false":False,"1":True,"0":False})
    assert f.stable_main.notna().all() and f.event_id.is_unique
    return f


def label_mapping(lab):
    if lab.difficulty.eq("all").all():return lab.set_index("worker_id").class_id.to_dict(),"global"
    return lab.set_index(["difficulty","worker_id"]).class_id.to_dict(),"difficulty"


def calibrated_state_to_json(c):
    return {"global":c["global"],"k":c["k"],"cells":[[*k,v]for k,v in c["cells"].items()],
            "rates":[[*k,v]for k,v in c["rates"].items()],"support":[[*k,v]for k,v in c["support"].items()]}


def select_and_predict(event_file,implementation="original"):
    start=time.time();events=normalize_events(event_file);old=events[events.panel_id.eq(PANEL)].copy()
    assert len(old)==270370,"Training panel requires the exact whole old registered panel"
    labels=pd.read_csv(HERE/"candidate_labels_by_training_set.csv.gz")
    sets=json.loads((HERE/"TRAINING_SETS.json").read_text());aliases=pd.DataFrame(sets["aliases"])
    methods=labels[["method_id","family","K"]].drop_duplicates().sort_values(["K","family"])
    # Prespecified simplicity tie: fewer base classes, then fewer feature domains;
    # conditional refinement is later than all global candidates at the same K.
    tie={"QT_only":0,"minus_difficulty":1,"minus_semi":2,"minus_scope":3,"minus_structure":4,"full":5,"base_plus_difficulty":6}
    complexity=methods.copy();complexity["complexity_order"]=complexity.K
    complexity["tie_order"]=complexity.family.map(tie)
    cache=HERE/"inner_brier";cache.mkdir(exist_ok=True)
    look={(t,m):g for (t,m),g in labels.groupby(["train_key","method_id"])}
    all_scores=[];selection_rows=[];choices=[];selected_classes=[];calibrators={};calibration_rows=[]
    pred_path=HERE/"event_predictions.csv.gz"
    pred_tmp=HERE/("event_predictions.csv.gz."+uuid.uuid4().hex+".writing")
    prediction_rows=0
    with gzip.open(pred_tmp,"wt",encoding="utf8",newline="") as handle:
        written=False
        for n,(fold_id,fg) in enumerate(aliases.groupby("fold_id",sort=False),1):
            base=fg[fg.inner_group.isna()].iloc[0];train_buildings=sets["sets"][base.train_key]
            train=old[old.building.isin(train_buildings)]
            saved=cache/f"{fold_id}.csv"
            if saved.exists():scores=pd.read_csv(saved)
            else:
                inner_scores=[]
                for _,inner in fg[fg.inner_group.notna()].iterrows():
                    bs=sets["sets"][inner.train_key]
                    discovery=train[train.building.isin(bs)]
                    valid=train[train.building.isin(inner.inner_validation_buildings)]
                    assert not set(discovery.building)&set(valid.building)
                    for method in methods.method_id:
                        lm,domain=label_mapping(look[(inner.train_key,method)])
                        rel_train=attach_relation(discovery,lm,domain)
                        model=fit_calibrator(discovery,rel_train)
                        rel_valid=attach_relation(valid,lm,domain)
                        pred=predict_calibrator(model,valid,rel_valid)
                        b=building_brier(valid,pred);b["method_id"]=method;b["fold_id"]=fold_id;b["inner_group"]=int(inner.inner_group)
                        inner_scores.append(b)
                scores=pd.concat(inner_scores,ignore_index=True);scores.to_csv(saved,index=False)
            all_scores.append(scores)
            chosen,selection=one_se_choice(scores,complexity[["method_id","complexity_order","tie_order"]])
            selection["fold_id"]=fold_id;selection_rows.append(selection)
            chose_family=methods.set_index("method_id").loc[chosen,"family"]
            choice={"fold_id":fold_id,"heldout_building":base.heldout_building,"method_id":"forward_selected","candidate_method":chosen,"family":chose_family,
                    "K":int(methods.set_index("method_id").loc[chosen,"K"]),"train_key":base.train_key,"selection_panel":PANEL}
            choices.append(choice)
            selected_by_alias={"forward_selected":chosen}
            for family,g in methods.groupby("family"):
                cand,sel=one_se_choice(scores[scores.method_id.isin(g.method_id)],complexity[complexity.method_id.isin(g.method_id)][["method_id","complexity_order","tie_order"]])
                selected_by_alias["forward_"+family]=cand
            # Full-model K ablations are also saved, separating dropped features from
            # each ablation family's independently selected granularity.
            main_k=int(methods.set_index("method_id").loc[chosen,"K"])
            for family in FAMILIES:
                selected_by_alias["forward_"+family+"_mainK"]=f"fw_{family}_K{main_k}"
            calibrators[fold_id]={}
            test=events.iloc[:0] if fold_id=="FULL" else events[events.building.eq(fold_id)]
            for alias,method in selected_by_alias.items():
                lab=look[(base.train_key,method)].copy();lab["candidate_method"]=method;lab["method_id"]=alias
                lab["fold_id"]=fold_id;lab["heldout_building"]=base.heldout_building;lab["condition"]="ordinary_manual"
                selected_classes.append(lab)
                lm,domain=label_mapping(lab);rtrain=attach_relation(train,lm,domain);model=fit_calibrator(train,rtrain)
                calibrators[fold_id][alias]={"candidate_method":method,**calibrated_state_to_json(model)}
                for cell,rate in model["rates"].items():
                    calibration_rows.append({"fold_id":fold_id,"method_id":alias,"candidate_method":method,"k":cell[0],"difficulty":cell[1],"relation":cell[2],"stable_probability":rate,"training_buildings":model["support"][cell]})
                if len(test):
                    relation=attach_relation(test,lm,domain);pred=predict_calibrator(model,test,relation)
                    out=test[["event_id","panel_id","building","image_id","k","difficulty"]].copy()
                    out["fold_id"]=fold_id;out["method_id"]=alias;out["candidate_method"]=method
                    out["probability"]=pred;out["predicted_relation"]=relation
                    out.to_csv(handle,index=False,header=not written);written=True;prediction_rows+=len(out)
            print(json.dumps({"selected_fold":n,"fold_id":fold_id,"candidate":chosen}),flush=True)
    with pred_tmp.open("rb") as stream:os.fsync(stream.fileno())
    readback_rows=sum(len(chunk) for chunk in pd.read_csv(pred_tmp,compression="gzip",chunksize=100000))
    assert readback_rows==prediction_rows
    os.replace(pred_tmp,pred_path)
    pd.concat(all_scores,ignore_index=True).to_csv(HERE/"inner_validation_building_scores.csv.gz",index=False,compression="gzip")
    pd.concat(selection_rows,ignore_index=True).to_csv(HERE/"candidate_selection_process.csv",index=False)
    pd.DataFrame(choices).to_csv(HERE/"selected_methods.csv",index=False)
    csv_verified(pd.concat(selected_classes,ignore_index=True),HERE/"selected_classes_by_fold.csv.gz")
    pd.DataFrame(calibration_rows).to_csv(HERE/"frozen_training_calibration.csv",index=False)
    js(HERE/"FROZEN_CALIBRATORS.json",calibrators)
    js(HERE/"SELECTION_PREDICTION_RECEIPT.json",{"main_training_events":len(old),"all_evaluation_events":len(events),"buildings":events.building.nunique(),
              "candidate_methods":len(methods),"folds_including_full":len(choices),"probability_file":"event_predictions.csv.gz","prediction_rows":prediction_rows,"prediction_readback_passed":True,
              "event_source_sha256":sha(event_file),"selection_code_sha256":sha(ROOT/"reverse/selection_common.py"),
              "class_discovery_code_sha256":sha(__file__),"seconds":time.time()-start,"aggregation_implementation":implementation,
              "fast_sidecar_sha256":sha(HERE/"selection_fast.py") if implementation=="fast" else None,
              "outer_results_used_for_selection":False,"new_panel_used_for_selection":False})


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--stage",choices=["partition","select"],required=True);ap.add_argument("--metric",choices=["B8L2","D10"],default="B8L2");ap.add_argument("--events",default=str(ROOT/"events/common_events.csv.gz"));ap.add_argument("--implementation",choices=["original","fast"],default="original");args=ap.parse_args()
    if args.implementation=="fast":
        receipt=json.loads((HERE/"FAST_SELECTION_PARITY.json").read_text())
        assert receipt["passed"] and receipt["fast_sidecar_sha256"]==sha(HERE/"selection_fast.py")
        import selection_fast
        global fit_calibrator,predict_calibrator,building_brier
        fit_calibrator=selection_fast.fit_calibrator;predict_calibrator=selection_fast.predict_calibrator;building_brier=selection_fast.building_brier
    if args.stage=="partition":build_partitions(args.metric)
    else:select_and_predict(Path(args.events),args.implementation)


if __name__=="__main__":main()
