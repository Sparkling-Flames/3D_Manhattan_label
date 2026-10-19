#!/usr/bin/env python3
"""Full candidate, full inner-fold parity before activating exact fast sidecar."""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS","1")
os.environ.setdefault("OMP_NUM_THREADS","1")
import json,time,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import discover_forward as pipeline
import selection_common as original
import selection_fast as fast

H=Path(__file__).resolve().parent;R=H.parent


def main():
    start=time.time();e=pipeline.normalize_events(R/"events/common_events.csv.gz");e=e[e.panel_id.eq(pipeline.PANEL)]
    labels=pd.read_csv(H/"candidate_labels_by_training_set.csv.gz");sets=json.loads((H/"TRAINING_SETS.json").read_text());aliases=pd.DataFrame(sets["aliases"])
    methods=labels[["method_id","family","K"]].drop_duplicates().sort_values(["K","family"])
    tie={"QT_only":0,"minus_difficulty":1,"minus_semi":2,"minus_scope":3,"minus_structure":4,"full":5,"base_plus_difficulty":6}
    cm=methods.assign(complexity_order=methods.K,tie_order=methods.family.map(tie))[["method_id","complexity_order","tie_order"]]
    look={(t,m):g for (t,m),g in labels.groupby(["train_key","method_id"])}
    rows=[];choices=[];all_orig=[];all_fast=[]
    outer=next(x for x in aliases.fold_id.unique()if x!="FULL" and (H/"inner_brier"/f"{x}.csv").exists())
    for fold in ["FULL",outer]:
        af=aliases[aliases.fold_id.eq(fold)]
        for _,inner in af[af.inner_group.notna()].iterrows():
            tr=e[e.building.isin(sets["sets"][inner.train_key])];va=e[e.building.isin(inner.inner_validation_buildings)]
            pt=fast.EncodedPanel(tr);pv=fast.EncodedPanel(va)
            for method in methods.method_id:
                lm,domain=pipeline.label_mapping(look[(inner.train_key,method)])
                rt=original.attach_relation(tr,lm,domain);rv=original.attach_relation(va,lm,domain)
                m0=original.fit_calibrator(tr,rt);m1=pt.fit(rt)
                assert m0["support"]==m1["support"]
                errors=[abs(m0["global"]-m1["global"])]
                for part in ["k","cells","rates"]:
                    assert set(m0[part])==set(m1[part])
                    errors.extend(abs(m0[part][k]-m1[part][k])for k in m0[part])
                p0=original.predict_calibrator(m0,va,rv);p1=pv.predict(m1,rv)
                b0=original.building_brier(va,p0);b1=pv.brier(p1)
                assert list(b0.building)==list(b1.building)
                erp=float(np.max(np.abs(p0-p1)));erb=float(np.max(np.abs(b0.brier-b1.brier)))
                assert max(errors+[erp,erb])<1e-12
                b0["method_id"]=method;b0["fold_id"]=fold;b0["inner_group"]=int(inner.inner_group);all_orig.append(b0)
                b1["method_id"]=method;b1["fold_id"]=fold;b1["inner_group"]=int(inner.inner_group);all_fast.append(b1)
                rows.append({"fold_id":fold,"inner_group":int(inner.inner_group),"method_id":method,"train_events":len(tr),"valid_events":len(va),
                             "max_rate_difference":max(errors),"max_prediction_difference":erp,"max_building_brier_difference":erb,"support_exact":True})
            print(json.dumps({"parity_fold":fold,"inner_group":int(inner.inner_group),"candidate_count":len(methods)}),flush=True)
        so=pd.concat([x for x in all_orig if x.fold_id.iloc[0]==fold]);sf=pd.concat([x for x in all_fast if x.fold_id.iloc[0]==fold])
        a,aa=original.one_se_choice(so,cm);b,bb=original.one_se_choice(sf,cm);assert a==b
        old=pd.read_csv(H/"inner_brier"/f"{fold}.csv")
        merged=sf.merge(old,on=["building","method_id","fold_id","inner_group"],suffixes=("_fast","_existing"),validate="one_to_one")
        assert len(merged)==len(sf)==len(old)
        prior_delta=float(np.max(np.abs(merged.brier_fast-merged.brier_existing)));assert prior_delta<1e-12
        choices.append({"fold_id":fold,"original_selected":a,"fast_selected":b,"max_existing_completed_fold_difference":prior_delta})
    # Prediction must not use validation outcome, despite the panel storing it
    # separately for evaluation and unused baseline convenience arrays.
    poison=va.copy();poison["stable_main"]=~poison.stable_main
    assert np.array_equal(fast.EncodedPanel(poison).predict(m1,rv),pv.predict(m1,rv))
    df=pd.DataFrame(rows);df.to_csv(H/"FAST_SELECTION_PARITY.csv",index=False)
    receipt={"passed":True,"full_candidate_inner_evaluations":len(df),"candidate_count":len(methods),"folds":["FULL",outer],
             "rates_predictions_building_brier_tolerance":1e-12,"max_rate_difference":float(df.max_rate_difference.max()),
             "max_prediction_difference":float(df.max_prediction_difference.max()),"max_building_brier_difference":float(df.max_building_brier_difference.max()),
             "selected_methods":choices,"validation_outcome_poison_predictions_exactly_unchanged":True,
             "original_selector_sha256":hashlib.sha256((R/"reverse/selection_common.py").read_bytes()).hexdigest(),
             "fast_sidecar_sha256":hashlib.sha256((H/"selection_fast.py").read_bytes()).hexdigest(),
             "seconds":time.time()-start,"scientific_definition_changed":False}
    (H/"FAST_SELECTION_PARITY.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,indent=2))


if __name__=="__main__":main()
