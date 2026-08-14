"""Diagnostic-only Calibration decision-readiness addendum."""
from __future__ import annotations
import argparse, json, math, random, sys
from collections import defaultdict
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis import process_calibration_dual_track as base
from tools.thesis_main.analysis import process_calibration_dual_track_v2 as v2
from tools.thesis_main.analysis.c1_task_adjusted_quality import normal_normal_empirical_bayes

SEED=20260815; REPS=1000
ROLE={"analysis_role":"diagnostic_pre_stage3","scientific_conclusion_prohibited":True,"formal_profile_frozen":False,"formal_policy_frozen":False,"block3_generated":False}
P=lambda *parts: ROOT.joinpath(*parts)
PATHS={
 "block1_canonical":P("analysis_results","c2a_rp_block1_reestimate_20260810_v1","c2a_rp_block1_canonical_submissions.csv"),
 "block1_risk":P("analysis_results","c2a_rp_block1_reestimate_20260810_v2","c2b_plus_c2a_rp_block1_risk_slope_evidence.csv"),
 "c2b_risk":P("analysis_results","c2b_closeout_20260806_final","c2b_canonical_risk_slope_evidence.csv"),
 "cumulative_snapshot":P("analysis_results","c2a_rp_block2_diagnostics_20260814_v1","source_evidence_snapshot.csv"),
 "crosswalk":P("analysis_results","c2a_rp_block2_diagnostics_20260814_v1","reference_registry_crosswalk.csv"),
 "c1_profile":P("analysis_results","c1_a_batch_freeze_20260802_v17","c1_a_batch_inputs","c1_three_track_worker_state_formal.csv"),
 "c2b_profile":P("analysis_results","c2b_closeout_20260806_final","post_c2b_worker_profile.csv"),
 "block1_profile":P("analysis_results","c2a_rp_block1_reestimate_20260810_v2","post_c2a_rp_block1_worker_profile.csv"),
 "block2_summary":P("analysis_results","c2a_rp_block2_reestimate_20260814_v1","c2a_rp_block2_reestimate_summary.json"),
 "family":P("analysis_results","full_materialization_pre_v1_audit_20260810_v1","worker_p1_family_component_eligibility.csv"),
 "risk_readiness":P("analysis_results","full_materialization_pre_v1_audit_20260810_v1","worker_risk_component_readiness.csv"),
 "v3_oof":P("analysis_results","calibration_dual_track_processing_20260815_v3","conditional_out_of_fold_predictions.csv"),
 "procedure":P("docs","thesis_main","FULL_MATERIALIZATION_PROCEDURE_v1.json"),
 "contract":P("docs","thesis_main","PAPER_A_METHOD_CONTRACT_CURRENT.json"),
}
def tag(row:dict[str,Any])->dict[str,Any]: return {**ROLE,**row}
def sha(path:Path)->str: return base.sha256_file(path)

def reconciliation(out:Path)->None:
    canonical=pd.read_csv(PATHS["block1_canonical"],dtype=str).fillna(""); risk=pd.read_csv(PATHS["block1_risk"],dtype=str).fillna(""); risk=risk[risk.evidence_stage.eq("C2A_RP_BLOCK1")]
    chain=f"Block1: {len(canonical)} canonical; {canonical.canonical_valid.str.lower().eq('true').sum()} canonical-valid; {risk.eligibility_status.eq('eligible').sum()} risk-eligible; {risk.eligibility_status.eq('not_evaluable').sum()} not-evaluable"
    risk=risk.set_index("canonical_annotation_id")
    cross=pd.read_csv(PATHS["crosswalk"],dtype=str).fillna(""); xmap={(r.evidence_stage,r.base_task_id):r for _,r in cross.iterrows()}; rows=[]
    for _,row in canonical.iterrows():
        rr=risk.loc[row.canonical_annotation_id] if row.canonical_annotation_id in risk.index else None; key=("C2A_RP_BLOCK1",row.base_task_id); ref=xmap.get(key)
        status="conflict_frozen_artifact_semantics" if rr is not None and str(rr.canonical_valid).lower()!=str(row.canonical_valid).lower() else "reported"
        rows.append(tag({"canonical_submission_id":row.canonical_annotation_id,"worker_id":row.worker_id,"base_task_id":row.base_task_id,"canonical_status":row.canonical_valid,"geometry_status":"not_materialized_in_canonical_submission_artifact","reference_status":ref.reference_status if ref is not None else "not_joined_in_this_processing_package","risk_eligibility":rr.eligibility_status if rr is not None else "source_absent","exclusion_reason":rr.ineligibility_reason if rr is not None else row.exclusion_reason,"decision_source_file":str(PATHS["block1_canonical"].relative_to(ROOT))+";"+str(PATHS["block1_risk"].relative_to(ROOT)),"decision_source_sha256":sha(PATHS["block1_canonical"])+";"+sha(PATHS["block1_risk"]),"decision_time":row.reviewed_at,"reconciliation_status":status,"reported_chain":chain}))
    base.write_csv(out/"BLOCK1_ELIGIBILITY_RECONCILIATION.csv",rows)
    six=[r for r in rows if r["risk_eligibility"]=="canonical_invalid"]
    base.write_csv(out/"BLOCK1_CANONICAL_INVALID_SIX_ROWS.csv",six)
    unresolved=[]
    for _,r in cross.iterrows():
        if "unavailable" in r.reference_status: unresolved.append(tag({"case":"reference_unavailable","evidence_stage":r.evidence_stage,"base_task_id":r.base_task_id,"worker_id":"aggregate_workers="+r.workers,"reference_status":r.reference_status,"source":str(PATHS["crosswalk"].relative_to(ROOT)),"sha256":sha(PATHS["crosswalk"])}))
    evidence_inputs=base.load_inputs(); evidence,_=base.build_long_evidence(evidence_inputs,out); evidence=v2.enrich_c2_evidence(evidence,evidence_inputs,out)
    for r in evidence:
        if r.get("stage") in {"C2B","C2A_RP"} and r.get("reference_crosswalk_join_status")=="not_joined_in_this_processing_package": unresolved.append(tag({"case":"crosswalk_not_joined","evidence_stage":r.get("stage"),"canonical_submission_id":r.get("canonical_submission_id"),"worker_id":r.get("worker_id"),"base_task_id":r.get("base_task_id"),"reference_status":"not_joined_in_this_processing_package","source":str(PATHS["crosswalk"].relative_to(ROOT)),"sha256":sha(PATHS["crosswalk"])}))
    current=pd.read_csv(PATHS["cumulative_snapshot"],dtype=str).fillna(""); current=current[(current.evidence_stage=="C2B") & (current.ineligibility_reason=="researcher_confirmed_bad_gt")]
    for _,r in current.iterrows(): unresolved.append(tag({"case":"C2B_157_to_155_researcher_confirmed_bad_gt","canonical_submission_id":r.canonical_annotation_id,"worker_id":r.worker_id,"base_task_id":r.base_task_id,"reference_status":"researcher_confirmed_bad_gt","source":str(PATHS["cumulative_snapshot"].relative_to(ROOT)),"sha256":sha(PATHS["cumulative_snapshot"])}))
    base.write_csv(out/"REFERENCE_CROSSWALK_UNRESOLVED.csv",unresolved)

def _profile(path:Path)->dict[str,float]:
    frame=pd.read_csv(path,dtype=str).fillna(""); return {str(r.worker_id):float(r.Q_GT_EB) for _,r in frame.iterrows() if r.Q_GT_EB!=""}
def _frame(out:Path)->pd.DataFrame:
    inputs=base.load_inputs(); evidence,_=base.build_long_evidence(inputs,out); evidence=v2.enrich_c2_evidence(evidence,inputs,out)
    frame=pd.DataFrame([r for r in evidence if base.truth(r.get("risk_evidence_eligible")) and base.number(r.get("iou_to_reference")) is not None]); frame["quality"]=pd.to_numeric(frame.iou_to_reference); frame["risk"]=pd.to_numeric(frame.risk); frame["stage"]=frame.apply(lambda r:base.analysis_stage(r.to_dict()),axis=1); return frame
def _strong_fit(train:pd.DataFrame,test:pd.DataFrame,profile:dict[str,float],source:Path)->tuple[dict[str,Any],list[dict[str,Any]]]:
    tr,te=train.copy(),test.copy(); tr["qgt"]=tr.worker_id.astype(str).map(profile); te["qgt"]=te.worker_id.astype(str).map(profile)
    if tr.qgt.isna().any() or te.qgt.isna().any(): raise ValueError("snapshot worker coverage missing")
    for field in ("risk","qgt"):
        mean,scale=float(tr[field].mean()),float(tr[field].std(ddof=0)); tr[field+"_z"]=(tr[field]-mean)/scale; te[field+"_z"]=(te[field]-mean)/scale
    basefit=smf.ols("quality ~ risk_z",tr).fit(); strong=smf.ols("quality ~ risk_z + qgt_z",tr).fit(); b=np.asarray(basefit.predict(te)); s=np.asarray(strong.predict(te)); y=te.quality.to_numpy(); records=[]
    for i,(_,r) in enumerate(te.iterrows()): records.append(tag({"canonical_submission_id":r.canonical_submission_id,"worker_id":r.worker_id,"base_task_id":r.base_task_id,"building_id":r.building_id,"actual":float(y[i]),"baseline_prediction":float(b[i]),"strong_global_prediction":float(s[i]),"profile_snapshot":str(source.relative_to(ROOT)),"profile_snapshot_sha256":sha(source),"scaling_source":"train_fold_only"}))
    metrics=lambda p:{"rmse":float(np.sqrt(np.mean((y-p)**2))),"mae":float(np.mean(abs(y-p))),"spearman":base.corr(y.tolist(),p.tolist(),"spearman")}
    bm,sm=metrics(b),metrics(s); delta=lambda key: sm[key]-bm[key] if isinstance(sm[key],float) and isinstance(bm[key],float) else "not_evaluable_constant_test_outcome_or_prediction"
    return tag({"baseline_formula":"quality ~ risk","strong_global_formula":"quality ~ risk + S_G","strong_global_definition":"S_G=z(Q_GT_EB), training-fold scaling","rows":len(te),"workers":te.worker_id.nunique(),"tasks":te.base_task_id.nunique(),"buildings":te.building_id.nunique(),"baseline_rmse":bm["rmse"],"baseline_mae":bm["mae"],"baseline_spearman":bm["spearman"],"strong_global_rmse":sm["rmse"],"strong_global_mae":sm["mae"],"strong_global_spearman":sm["spearman"],"delta_rmse":delta("rmse"),"delta_mae":delta("mae"),"delta_spearman":delta("spearman"),"profile_snapshot":str(source.relative_to(ROOT)),"profile_snapshot_sha256":sha(source),"formal_profile_status":"nonfinal_snapshot_not_final_pooled_profile"}),records
def strong_validation(out:Path)->pd.DataFrame:
    f=_frame(out); c1,c2b,b1=map(_profile,(PATHS["c1_profile"],PATHS["c2b_profile"],PATHS["block1_profile"])); folds=[("temporal","C2B_to_Block1",f[f.stage.eq("C2B_C2-B")],f[f.stage.eq("C2A_RP_Block1")],c2b,PATHS["c2b_profile"]),("temporal","C2B_Block1_to_Block2",f[f.stage.isin(["C2B_C2-B","C2A_RP_Block1"])],f[f.stage.eq("C2A_RP_Block2")],b1,PATHS["block1_profile"])]
    for kind,field in (("leave_one_base_task_out","base_task_id"),("leave_one_building_out","building_id")):
        for value in sorted(f[field].astype(str).unique()): folds.append((kind,value,f[f[field].astype(str)!=value],f[f[field].astype(str)==value],c1,PATHS["c1_profile"]))
    rows=[]; records=[]
    for kind,name,tr,te,profile,path in folds:
        summary,pred=_strong_fit(tr,te,profile,path); summary.update(validation_kind=kind,fold=name); rows.append(summary)
        for r in pred:r.update(validation_kind=kind,fold=name)
        records+=pred
    base.write_csv(out/"STRONG_GLOBAL_DIRECT_VALIDATION.csv",rows); base.write_csv(out/"STRONG_GLOBAL_OOF_PREDICTIONS.csv",records); return pd.DataFrame(records)
def paired_bootstrap(pred:pd.DataFrame,out:Path,name:str)->None:
    rng=random.Random(SEED); rows=[]
    for kind,group in pred.groupby("validation_kind"):
        y0=group.actual.to_numpy(); b0=group.baseline_prediction.to_numpy(); s0=group.strong_global_prediction.to_numpy(); sb0,ss0=base.corr(y0.tolist(),b0.tolist(),"spearman"),base.corr(y0.tolist(),s0.tolist(),"spearman")
        points={"rmse":float(np.sqrt(np.mean((y0-s0)**2))-np.sqrt(np.mean((y0-b0)**2))),"mae":float(np.mean(abs(y0-s0))-np.mean(abs(y0-b0))),"spearman":ss0-sb0}
        for unit in ("base_task_id","building_id","worker_id"):
            keys=sorted(group[unit].astype(str).unique()); chunks={k:group[group[unit].astype(str)==k] for k in keys}
            vals={m:[] for m in ("rmse","mae","spearman")}; failed=0
            for _ in range(REPS):
                sample=pd.concat([chunks[rng.choice(keys)] for _ in keys]); y=sample.actual.to_numpy(); b=sample.baseline_prediction.to_numpy(); s=sample.strong_global_prediction.to_numpy(); sb,ss=base.corr(y.tolist(),b.tolist(),"spearman"),base.corr(y.tolist(),s.tolist(),"spearman"); data={"rmse":float(np.sqrt(np.mean((y-s)**2))-np.sqrt(np.mean((y-b)**2))),"mae":float(np.mean(abs(y-s))-np.mean(abs(y-b))),"spearman":ss-sb if isinstance(sb,float) and isinstance(ss,float) else math.nan}
                if any(not math.isfinite(x) for x in data.values()): failed+=1; continue
                for metric,value in data.items():vals[metric].append(value)
            for metric,value in vals.items():rows.append(tag({"comparison":name,"validation_kind":kind,"cluster_unit":unit,"metric":"paired_delta_"+metric,"point_estimate":points[metric],"requested_replicates":REPS,"successful_replicates":len(value),"failed_replicates":failed,"seed":SEED,"paired_same_draw":True,"ci_lower":float(np.quantile(value,.025)),"ci_upper":float(np.quantile(value,.975))}))
    base.write_csv(out/"STRONG_GLOBAL_PAIRED_BOOTSTRAP.csv",rows)

def conditional_deltas(out:Path)->None:
    p=pd.read_csv(PATHS["v3_oof"],dtype=str).fillna(""); p[["actual_quality","predicted_quality"]]=p[["actual_quality","predicted_quality"]].astype(float); rows=[]; boot=[]; rng=random.Random(SEED)
    for kind,group in p.groupby("validation_kind"):
        for model in ("P2","worker_x_risk_diagnostic","P3_d_model_feat_local_max","P3_d_model_feat_local_max_residualized_sensitivity"):
            a=group[group.model_name.eq("P1")].set_index("canonical_submission_id"); b=group[group.model_name.eq(model)].set_index("canonical_submission_id"); common=a.index.intersection(b.index)
            if len(common)!=len(a) or len(common)!=len(b): raise ValueError("paired OOF rows differ")
            y=a.loc[common,"actual_quality"].astype(float).to_numpy(); x=a.loc[common,"predicted_quality"].astype(float).to_numpy(); z=b.loc[common,"predicted_quality"].astype(float).to_numpy(); paired=a.loc[common,["base_task_id","building_id","worker_id"]].copy(); paired["actual"]=y; paired["p1"]=x; paired["candidate"]=z; rows.append(tag({"validation_kind":kind,"comparison":model+"_vs_P1","paired_test_rows":len(common),"same_test_rows":True,"delta_rmse":float(np.sqrt(np.mean((y-z)**2))-np.sqrt(np.mean((y-x)**2))),"delta_mae":float(np.mean(abs(y-z))-np.mean(abs(y-x))),"delta_spearman":base.corr(y.tolist(),z.tolist(),"spearman")-base.corr(y.tolist(),x.tolist(),"spearman"),"M2_boundary_status":"boundary_singular retained in pooled association output" if model=="P2" else "not_applicable","interpretation":"exploratory_multiple_candidate_no_winner"}))
            point_rmse=float(np.sqrt(np.mean((y-z)**2))-np.sqrt(np.mean((y-x)**2)))
            for unit in ("base_task_id","building_id","worker_id"):
                keys=sorted(paired[unit].astype(str).unique()); chunks={k:paired[paired[unit].astype(str)==k] for k in keys}; values=[]
                for _ in range(REPS):
                    sample=pd.concat([chunks[rng.choice(keys)] for _ in keys]); values.append(float(np.sqrt(np.mean((sample.actual-sample.candidate)**2))-np.sqrt(np.mean((sample.actual-sample.p1)**2))))
                boot.append(tag({"validation_kind":kind,"comparison":model+"_vs_P1","cluster_unit":unit,"metric":"paired_delta_rmse","point_estimate":point_rmse,"requested_replicates":REPS,"successful_replicates":len(values),"failed_replicates":0,"seed":SEED,"paired_same_draw":True,"ci_lower":float(np.quantile(values,.025)),"ci_upper":float(np.quantile(values,.975))}))
    base.write_csv(out/"CONDITIONAL_PAIRED_MODEL_DELTAS.csv",rows); base.write_csv(out/"CONDITIONAL_PAIRED_BOOTSTRAP.csv",boot)
def family(out:Path)->None:
    f=pd.read_csv(PATHS["family"],dtype=str).fillna(""); rows=[]; missing=[]
    for _,r in f.iterrows():
        gates={"P1_integrity_eligible":r.p1_family_integrity_status,"C1_predictive_validated":r.c1_predictive_status,"C2B_confirmed":r.c2b_confirmation_status,"direction_consistent":r.direction_gate_status,"leave_one_task_out_stable":"not_materialized_in_source_artifact","leave_one_block_out_stable":"not_materialized_in_source_artifact","routing_activation_allowed":r.full_component_eligible}
        status="ready" if base.truth(r.full_component_eligible) else "not_ready_missing_inputs" if "missing" in r.disable_reason else "not_ready"
        rows.append(tag({"worker_id":r.worker_id,"family":r.component_family,"p1_family_integrity_status":r.p1_family_integrity_status,"c1_predictive_status":r.c1_predictive_status,"c2b_confirmation_status":r.c2b_confirmation_status,"support_gate_status":r.support_gate_status,"direction_gate_status":r.direction_gate_status,"shrinkage_status":r.shrinkage_status,"routing_activation_allowed":r.full_component_eligible,"required_chain":";".join(gates),"required_chain_status_json":json.dumps(gates,sort_keys=True),"all_gates_status":status,"disable_reason":r.disable_reason,"source":str(PATHS["family"].relative_to(ROOT)),"sha256":sha(PATHS["family"])}))
    inventory_fields={"P1 family integrity":"p1_family_integrity_status","C1 predictive validation":"c1_predictive_status","C2B confirmation":"c2b_confirmation_status","direction consistency":"direction_gate_status"}
    for family_name in ("undercoverage","adjacent_space_overextension","corner_topology_instability"):
        current=f[f.component_family.eq(family_name)]
        statuses={label:";".join(sorted(current[column].unique())) for label,column in inventory_fields.items()}
        statuses.update({"leave-task stability":"not_materialized_in_source_artifact","leave-block stability":"not_materialized_in_source_artifact","frozen family threshold/activation":"threshold_manifest_not_approved" if current.disable_reason.str.contains("threshold_manifest_not_approved",regex=False).all() else "not_ready"})
        for field,source_statuses in statuses.items():
            missing.append(tag({"family":family_name,"required_input":field,"source_statuses":source_statuses,"status":"source_absent_or_not_materialized_not_negative_evidence","procedure":str(PATHS["procedure"].relative_to(ROOT))}))
    base.write_csv(out/"FAMILY_COMPONENT_CHAIN_STATUS.csv",rows); base.write_csv(out/"FAMILY_MISSING_INPUT_INVENTORY.csv",missing)
def readiness(out:Path)->None:
    latest=json.loads(PATHS["block2_summary"].read_text(encoding="utf-8")); model=latest.get("model_status","source_absent"); closed=latest.get("block2_collection_closed") is True
    terminal_reason=f"latest Block2 collection_closed={str(closed).lower()}; model_status={model}; formal terminal state not materialized"
    risk_reason=f"latest Block2 model_status={model}; worker CI/precision gate and B_u_risk_shrunk not materialized"
    items=[("C1 current-contract recursive binding","conflict",PATHS["c1_profile"],"v17 snapshot predates current recursive binding"),("C2-A-RP terminal closeout","not_ready",PATHS["block2_summary"],terminal_reason),("final pooled profile","source_absent",PATHS["block2_summary"],"latest Block2 is closed but FINAL_POOLED_PROFILE_FROZEN is not materialized"),("Strong Global","not_ready",PATHS["c2b_profile"],"snapshot is not STRONG_GLOBAL_FROZEN"),("undercoverage Full component","not_ready",PATHS["family"],"required chain missing"),("adjacent_space_overextension Full component","not_ready",PATHS["family"],"required chain missing"),("corner_topology_instability Full component","not_ready",PATHS["family"],"required chain missing"),("risk component","not_ready",PATHS["block2_summary"],risk_reason),("V1 task activation/support","source_absent",PATHS["procedure"],"requires terminal calibration artifacts"),("delivery-adjusted quality definition","ready",PATHS["contract"],"normative definition present"),("structural/severe failure outcome definition","ready",PATHS["contract"],"normative definition present")]
    base.write_csv(out/"FINAL_READINESS_MATRIX.csv",[tag({"item":item,"status":status,"evidence_path":str(path.relative_to(ROOT)),"evidence_sha256":sha(path),"reason":reason}) for item,status,path,reason in items])
def rank_uncertainty(out:Path)->None:
    profile=pd.read_csv(PATHS["c1_profile"],dtype=str).fillna(""); workers=profile.worker_id.astype(str).tolist(); means=np.asarray(profile.Q_GT_task_adjusted,dtype=float); cov=np.asarray([[json.loads(r.Q_GT_contrast_covariance_row_json).get(other,0) for other in workers] for _,r in profile.iterrows()]); draws=np.random.default_rng(SEED).multivariate_normal(means,(cov+cov.T)/2+np.eye(len(workers))*1e-12,size=REPS); ranks=defaultdict(list); ses=np.sqrt(np.diag(cov))
    for draw in draws:
        eb,_=normal_normal_empirical_bayes(draw.tolist(),ses.tolist())
        for n,(w,_) in enumerate(sorted(zip(workers,(x["estimate"] for x in eb)),key=lambda x:(-x[1],x[0])),1):ranks[w].append(n)
    base.write_csv(out/"STRONG_GLOBAL_RANK_UNCERTAINTY.csv",[tag({"worker_id":w,"rank_q025":np.quantile(v,.025),"rank_q975":np.quantile(v,.975),"top3_probability":np.mean(np.asarray(v)<=3),"top5_probability":np.mean(np.asarray(v)<=5),"top10_probability":np.mean(np.asarray(v)<=10),"snapshot_worker_coverage":len(workers),"replicates":REPS}) for w,v in ranks.items()])
def run(out:Path)->dict[str,Any]:
    if out.exists():raise FileExistsError(out)
    out.mkdir(parents=True); reconciliation(out); pred=strong_validation(out); paired_bootstrap(pred,out,"Strong_Global_vs_baseline"); conditional_deltas(out); family(out); readiness(out); rank_uncertainty(out)
    inputs=[{"path":str(path.relative_to(ROOT)),"sha256":sha(path)} for path in PATHS.values()]; base.write_json(out/"source_manifest.json",tag({"inputs":inputs,"seed":SEED,"bootstrap_replicates":REPS}))
    b1=pd.read_csv(out/"BLOCK1_ELIGIBILITY_RECONCILIATION.csv"); latest=json.loads(PATHS["block2_summary"].read_text(encoding="utf-8"))
    report=f"# Calibration decision-readiness corrected addendum\n\n- boundary: diagnostic_pre_stage3; scientific_conclusion_prohibited=true\n- Block1: {len(b1)} canonical, {b1.canonical_status.astype(str).str.lower().eq('true').sum()} canonical-valid, {b1.risk_eligibility.eq('eligible').sum()} risk-eligible, {b1.risk_eligibility.eq('not_evaluable').sum()} not-evaluable.\n- Block2: collection_closed={str(latest.get('block2_collection_closed')).lower()}, model_status={latest.get('model_status')}.\n- C2-A-RP formal terminal state, final profile and policy remain unmaterialized.\n- No formal profile/policy freeze and no Block 3 generated.\n\n仅作校正后的数据处理与计算；不作科学结论或政策选择。\n"
    (out/"COMPUTATION_REPORT.md").write_text(report,encoding="utf-8")
    outputs=[{"path":p.name,"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file()]; base.write_json(out/"analysis_manifest.json",tag({"schema_version":"calibration_decision_readiness_v2","seed":SEED,"bootstrap_replicates":REPS,"outputs":outputs,"source_manifest_sha256":sha(out/"source_manifest.json")})); return {"output_dir":str(out),"strong_global_oof_rows":len(pred)}
def main(argv:list[str]|None=None)->int:
    a=argparse.ArgumentParser();a.add_argument("--output-dir",type=Path,required=True);print(json.dumps(run(a.parse_args(argv).output_dir),ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
