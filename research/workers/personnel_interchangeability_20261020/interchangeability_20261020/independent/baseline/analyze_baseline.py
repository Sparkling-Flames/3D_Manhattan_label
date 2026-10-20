"""All-event, failure-retaining analysis of the frozen known-direction baseline.

Caches are read pool by pool. This script consumes only precise requested teams.
No label, reference, fusion or pair threshold is fitted or changed here.
"""
from __future__ import annotations
import os
for _v in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[_v]="1"
import argparse
from collections import Counter,defaultdict
import gzip,hashlib,json,math
from pathlib import Path
import sys,time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"analysis/composition"))
sys.path.insert(0,str(ROOT/"interchangeability_20261020/independent"))
import fusion_runner as fr
import summarize_grid as sg
import pair_diagnostics as px
import design_baseline as d

LEGACY=("both_complete","abs_B8L2_change","abs_D10_change","floor_jaccard_difference","floor_symdiff_h2","structure_bound_cyclic_deg","node_count_difference","mean_height_prism_pair_iou","height_ratio_pair_abs_logdiff","joint_stable_strict","joint_stable_main","joint_stable_wide")
SHAPE=("geometry_shape_strict","geometry_shape_main","geometry_shape_wide","bottom_y_absdiff_deg_mean","bottom_y_absdiff_deg_p95","bottom_y_absdiff_deg_max","top_y_absdiff_deg_mean","top_y_absdiff_deg_p95","top_y_absdiff_deg_max","radius_abs_logratio_p95","boundary_total_height_abs_logratio_p95","inferred_total_height_mean_abs_logratio","boundary_distance_normalized_p95","boundary_distance_normalized_max","true_corner_count_difference","true_corner_F1_main","wall_coverage_symmetric_min_main","geometry_shape_main_and_prism_proxy_iou_lt_095","different_original_nodes_shape_main_passes","exact_flat_prism_pair_iou")
RATE_FIELDS=[f"{p}_{metric}" for p in ("within","cross") for metric in ("joint_stable_strict","joint_stable_main","joint_stable_wide","geometry_noQ_strict","geometry_noQ_main","geometry_noQ_wide","quality_only_main","both_complete")]
CONTINUOUS=["net_Q","net_D10","cross_minus_within_abs_Q","cross_minus_within_floor_diff","cross_minus_within_node_diff","B_B8L2","C_B8L2","B_nodes","C_nodes","history_Q_C_minus_B","core_history_q_beta"]+[f"{p}_{m}" for p in ("within","cross") for m in ("abs_B8L2_change","floor_jaccard_difference","node_count_difference","structure_bound_cyclic_deg","mean_height_prism_pair_iou")]
BLOCK_LOOKUP={}


def clean(x):return px._clean(x)


def numbers(x):return pd.to_numeric(x,errors="coerce")


def hmean(frame,columns):
    if not len(frame):return {c:None for c in columns}
    cell=["building","pool_id"]+[c for c in ("k","n_before","m") if c in frame.columns]
    first=frame.groupby(cell)[columns].mean().reset_index()
    return first.groupby(["building","pool_id"])[columns].mean().groupby("building").mean().mean().to_dict()


def add_groups(D):
    D["source_mode"]=np.where(D.block_new_n.eq(0),"all_v1",np.where(D.block_v1_n.eq(0),"all_new","mixed"))
    D["replacement_fraction_bin"]=pd.cut(D.replace_fraction,[-1,.25,.5,.75,1.000001],labels=["(0,.25]","(.25,.5]","(.5,.75]","(.75,1]"]).astype(str)
    D["core_incoming_fraction_bin"]=pd.cut(D.core_incoming_fraction,[-1e-9,.25,.5,.75,1.000001],right=False,labels=["[0,.25)","[.25,.5)","[.5,.75)","[.75,1]"]).astype(str)
    D.loc[D.core_n.eq(0),"core_incoming_fraction_bin"]="empty_core"
    D["n_band"]=pd.cut(D.k,[1,2,5,9,13,17,25,100],labels=["2","3-5","6-9","10-13","14-17","18-25","26+"]).astype(str)
    D["history_Q_gap_bin"]=pd.cut(D.history_Q_C_minus_B,[-np.inf,-5,-2,2,5,np.inf],labels=["<-5","[-5,-2)","[-2,2]","(2,5]",">5"]).astype(str)
    return D


def summarize(frame,group,fields):
    rows=[]
    grouper=frame.groupby(group,dropna=False,observed=True) if group else [((),frame)]
    for key,g in grouper:
        if not isinstance(key,tuple):key=(key,)
        r=dict(zip(group,key));q=numbers(g.net_Q);finite=q.dropna()
        r.update(events=len(g),unique_block_chains=g.block_id.nunique(),images=g.pool_id.nunique(),buildings=g.building.nunique(),unique_A_teams=g.A_team_key.nunique(),unique_B_teams=g.B_team_key.nunique(),unique_C_teams=g.C_team_key.nunique(),finite_Q_events=int(q.notna().sum()),finite_Q_images=g.loc[q.notna(),"pool_id"].nunique(),finite_Q_buildings=g.loc[q.notna(),"building"].nunique(),quality_improved_events=int(q.gt(0).sum()),quality_worsened_events=int(q.lt(0).sum()),quality_unchanged_events=int(q.eq(0).sum()),net_Q_event_p10=float(finite.quantile(.1)) if len(finite) else None,net_Q_event_min=float(finite.min()) if len(finite) else None,shape_registered_events=int(g.shape_registered.sum()),distinct_source_vectors=g[["block_new_n","block_v1_n"]].drop_duplicates().shape[0])
        r["unique_actual_teams"]=len(set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key))
        allpeople=set();blockpeople=set()
        for bid,n in g.groupby("block_id").k.max().items():
            b=BLOCK_LOOKUP[bid];ws=set(sum(b["blocks"].values(),[]));blockpeople.update(ws);allpeople.update(ws);allpeople.update(b["core_order"][:int(n)-b["m"]])
        r["distinct_workers"]=len(allpeople);r["distinct_replacement_workers"]=len(blockpeople)
        units=g.groupby(["building","pool_id","k","m"])[["net_Q","within_joint_stable_main","cross_joint_stable_main"]].mean().groupby(["building","pool_id"]).mean()
        building_units=units.groupby("building").mean()
        for prefix,u in (("image",units),("building",building_units)):
            qv=u.net_Q.dropna();gap=u.within_joint_stable_main-u.cross_joint_stable_main
            r["quality_improved_"+prefix+"s"]=int(qv.gt(0).sum());r["quality_worsened_"+prefix+"s"]=int(qv.lt(0).sum());r["quality_unchanged_"+prefix+"s"]=int(qv.eq(0).sum())
            r["quality_improved_ge2_"+prefix+"s"]=int(qv.ge(2).sum());r["quality_worsened_ge2_"+prefix+"s"]=int(qv.le(-2).sum())
            r["within_more_stable_"+prefix+"s"]=int(gap.gt(0).sum());r["cross_more_stable_"+prefix+"s"]=int(gap.lt(0).sum());r["same_stable_rate_"+prefix+"s"]=int(gap.eq(0).sum())
        r["net_Q_image_p10"]=float(units.net_Q.quantile(.1)) if units.net_Q.notna().any() else None
        r.update(hmean(g,fields))
        if "within_joint_stable_main" in r:r["within_minus_cross_joint_main"]=r["within_joint_stable_main"]-r["cross_joint_stable_main"]
        if "within_geometry_noQ_main" in r:r["within_minus_cross_geometry_noQ_main"]=r["within_geometry_noQ_main"]-r["cross_geometry_noQ_main"]
        for arm in "ABC":
            deferred=g[arm+"_score_status"].eq("two_person_deferred")
            r[arm+"_not_complete_evaluable_events"]=int((~g[arm+"_complete_evaluable"]).sum());r[arm+"_quality_missing_events"]=int(g[arm+"_B8L2"].isna().sum())
            r[arm+"_two_person_deferred_events"]=int(deferred.sum())
            r[arm+"_nondeferred_failure_events"]=int((~g[arm+"_complete_evaluable"]&~deferred).sum())
        rows.append(r)
    return pd.DataFrame(rows)


def adjusted_models(D):
    """Descriptive weighted regressions, never a causal independent class effect."""
    results=[]
    for target,G in D.groupby("target"):
        for response in ("net_Q","cross_minus_within_abs_Q","cross_minus_within_floor_diff"):
            for mode,cols in [("counts_source",["k","m","core_incoming_fraction","block_new_fraction","core_history_q_beta"]),("plus_block_historical_Q",["k","m","core_incoming_fraction","block_new_fraction","core_history_q_beta","history_Q_C_minus_B"])]:
                g=G.copy();g["core_incoming_fraction"]=g.core_incoming_fraction.fillna(0.)
                g["block_new_fraction"]=g.block_new_n/g.m
                g=g.dropna(subset=[response]+cols)
                if not len(g):continue
                # Each image has unit weight in its building, each building unit total.
                counts=g.groupby(["pool_id","k","m"]).size();nm=g[["pool_id","k","m"]].drop_duplicates().groupby("pool_id").size();ib=g.groupby("building").pool_id.nunique()
                w=np.array([1/counts[(p,n,m)]/nm[p]/ib[b] for p,n,m,b in zip(g.pool_id,g.k,g.m,g.building)],float)
                numeric=g[cols].astype(float)
                categorical=pd.get_dummies(g[["building","difficulty"]],drop_first=True,dtype=float)
                X=np.column_stack([np.ones(len(g)),numeric.to_numpy(),categorical.to_numpy()]);names=["intercept"]+cols+list(categorical.columns);y=g[response].to_numpy(float)
                sw=np.sqrt(w);beta,_,rank,_=np.linalg.lstsq(X*sw[:,None],y*sw,rcond=None);pred=X@beta
                denom=np.sum(w*(y-np.average(y,weights=w))**2)
                r=dict(target=target,response=response,model=mode,events=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),rank=int(rank),columns=len(names),weighted_R2=1-float(np.sum(w*(y-pred)**2))/denom if denom>0 else None)
                for n,b in zip(names,beta):r["coef_"+n]=float(b)
                results.append(r)
    return results


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--folder",type=Path,default=Path(__file__).parent);ap.add_argument("--runs",type=Path);ap.add_argument("--output",type=Path);a=ap.parse_args();folder=a.folder.resolve();runs=a.runs or folder/"native_runs";out=a.output or folder/"results";out.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    freeze=fr.read(folder/"DESIGN_FREEZE.json");spec=fr.read(folder/"BASELINE_SPEC.json");assert d.sha(folder/"REQUESTS.json.gz")==freeze["request_sha256"]
    for path,h in spec["source_sha256"].items():assert d.sha(ROOT/path)==h
    design=pd.read_csv(folder/"EVENT_DESIGN.csv.gz");payload=fr.read(folder/"REQUESTS.json.gz");requests={r["request_id"]:r for r in payload["requests"]};blockmap={b["block_id"]:b for b in payload["blocks"]}
    global BLOCK_LOOKUP;BLOCK_LOOKUP=blockmap
    requested=set(r["team_key"] for r in requests.values());rows=[];shape_rows=[];nested=[];allteams=set();unique_status=Counter();used_workers=set();complete_unique=0;missing=[];seen_geometry_different_duplicates=0;by_pool_receipt=[]
    for pid,g in design.groupby("pool_id",sort=True):
        path=runs/"pools"/(pid+".json.gz")
        if not path.exists():missing.append(pid);continue
        cache=fr.read(path);teams={t["team_key"]:t for t in cache["teams"]};needed={getattr(e,arm+"_team_key") for e in g.itertuples() for arm in "ABC"}
        assert needed<=teams.keys(),pid
        for key in needed:
            t=teams[key];unique_status[t["score_status"]]+=1;allteams.add(key);used_workers.update(t["member_workers"]);complete_unique+=bool(t.get("complete_evaluable"))
        signatures={key:sg.signature(teams[key]) for key in needed};geometry_cache={}
        for e in g.to_dict("records"):
            row=dict(e);ar={arm:teams[e[arm+"_team_key"]] for arm in "ABC"};metadata={}
            for arm,t in ar.items():
                rq=requests[e["event_id"]+"__"+arm]
                assert t["member_workers"]==rq["worker_ids"] and t["k"]==e["k"] and t["reference_id"]==e["reference_id"]
                assert t.get("minimum_support",(e["k"]+1)//2)==e["expected_minimum_support"]
                for metric in ("B8L2","D10","IoU3D100","nodes","complete_evaluable","complete_floor_evaluable","score_status","omission","extension","height_mean_ratio","half_vote_nodes","unselected_groups_n","minority_observations_n"):
                    row[arm+"_"+metric]=t.get(metric)
            for name,arm in (("within","B"),("cross","C")):
                metrics=sg.pair_metrics(ar["A"],ar[arm],signatures[ar["A"]["team_key"]],signatures[ar[arm]["team_key"]])
                assert metrics["turnover"]==e["m"] and metrics["new_n_change"]==0
                for metric in LEGACY:row[name+"_"+metric]=metrics[metric]
                for label,q,f,s in (("strict",1,.02,2),("main",2,.05,3),("wide",5,.10,5)):
                    row[name+"_geometry_noQ_"+label]=bool(metrics["both_complete"] and metrics["node_count_difference"]==0 and metrics["floor_jaccard_difference"] is not None and metrics["floor_jaccard_difference"]<=f and metrics["structure_bound_cyclic_deg"] is not None and metrics["structure_bound_cyclic_deg"]<=s)
                    row[name+"_quality_only_"+label]=bool(metrics["both_complete"] and metrics["abs_B8L2_change"] is not None and metrics["abs_B8L2_change"]<=q)
                if e["shape_registered"]:
                    z=px.pair_metrics(ar["A"],ar[arm],cache=geometry_cache)
                    for metric in LEGACY:assert z[metric]==metrics[metric] or (isinstance(z[metric],float) and abs(z[metric]-metrics[metric])<1e-12)
                    shape_rows.append(dict(event_id=e["event_id"],block_id=e["block_id"],target=e["target"],historical_phase=e["historical_phase"],pool_id=pid,building=e["building"],difficulty=e["difficulty"],k=e["k"],m=e["m"],pair=name,**z))
                    for metric in SHAPE:row[name+"_"+metric]=z.get(metric)
                else:
                    for metric in SHAPE:row[name+"_"+metric]=None
            row["net_Q"]=sg.delta(ar["B"],ar["C"],"B8L2");row["net_D10"]=sg.delta(ar["B"],ar["C"],"D10")
            for key,a1,a2 in [("cross_minus_within_abs_Q","cross_abs_B8L2_change","within_abs_B8L2_change"),("cross_minus_within_floor_diff","cross_floor_jaccard_difference","within_floor_jaccard_difference"),("cross_minus_within_node_diff","cross_node_count_difference","within_node_count_difference")]:row[key]=row[a1]-row[a2] if row[a1] is not None and row[a2] is not None else None
            row["history_Q_C_minus_B"]=e["C_block_history_q_beta"]-e["B_block_history_q_beta"]
            rows.append(row)
        # Integer-n neighbours: same blocks, one actual core member added.
        for bid,bg in g.groupby("block_id"):
            bg=bg.sort_values("k")
            for before,after in zip(bg.to_dict("records"),bg.iloc[1:].to_dict("records")):
                assert after["k"]==before["k"]+1
                for arm in "ABC":
                    ta,tb=teams[before[arm+"_team_key"]],teams[after[arm+"_team_key"]]
                    assert set(tb["member_workers"])-set(ta["member_workers"])=={after["added_core_worker"]}
                    r=dict(target=before["target"],block_id=bid,pool_id=pid,building=before["building"],difficulty=before["difficulty"],historical_phase=before["historical_phase"],m=before["m"],arm=arm,n_before=before["k"],n_after=after["k"],added_worker=after["added_core_worker"],added_class=after["added_core_class"],added_source=after["added_core_source"],threshold_increased=after["expected_minimum_support"]>before["expected_minimum_support"],node_count_change=sg.delta(ta,tb,"nodes"),B8L2_change=sg.delta(ta,tb,"B8L2"),D10_change=sg.delta(ta,tb,"D10"),complete_before=bool(ta.get("complete_evaluable")),complete_after=bool(tb.get("complete_evaluable")),quality_available_before=ta.get("B8L2") is not None,quality_available_after=tb.get("B8L2") is not None,half_vote_nodes_before=ta.get("half_vote_nodes"),floor_jaccard_difference=None)
                    pa,pb=signatures[ta["team_key"]]["floor"],signatures[tb["team_key"]]["floor"]
                    if pa is not None and pb is not None:r["floor_jaccard_difference"]=1-pa.intersection(pb).area/pa.union(pb).area
                    nested.append(r)
        by_pool_receipt.append(dict(pool_id=pid,events=len(g),requested_unique=len(needed),actual_teams_read=len(teams),context=cache["context"],native_file_sha256=d.sha(path)))
        print(json.dumps(dict(pool_id=pid,events=len(rows),shape_pairs=len(shape_rows),seconds=round(time.monotonic()-started,1))),flush=True)
    assert not missing,"Not all requested pools computed: "+repr(missing)
    assert allteams==requested and len(rows)==freeze["events"] and len(shape_rows)==2*freeze["shape_registered_events"]
    Dall=add_groups(pd.DataFrame(rows));d.save_csv(out/"EVENT_RESULTS.csv.gz",Dall)
    d.save_csv(out/"SHAPE_PAIR_RESULTS.csv.gz",shape_rows);d.save_csv(out/"NESTED_STEPS.csv.gz",nested)
    fields=RATE_FIELDS+CONTINUOUS
    d.save_csv(out/"ALL_ATTEMPTED_OVERALL.csv",summarize(Dall,["target"],fields))
    d.save_csv(out/"TWO_PERSON_DEFERRED.csv",summarize(Dall[Dall.k.eq(2)],["target","m"],fields))
    D=Dall[Dall.k.ge(3)].copy() # inherited native n=2 policy, never a new success filter
    specs={"OVERALL":["target"],"N_M":["target","k","m"],"N_M_PHASE":["target","historical_phase","k","m"],"N_M_DIFFICULTY":["target","difficulty","k","m"],"N_M_SOURCE":["target","source_mode","k","m"],"SOURCE_VECTOR":["target","k","m","block_new_n","block_v1_n"],"CORE_PROPORTION":["target","n_band","replacement_fraction_bin","core_incoming_fraction_bin"],"CORE_N_M":["target","k","m","core_incoming_fraction_bin"],"BUILDING":["target","building"],"DIFFICULTY":["target","difficulty"],"SOURCE":["target","source_mode"],"Q_GAP":["target","history_Q_gap_bin"]}
    for name,keys in specs.items():d.save_csv(out/(name+".csv"),summarize(D,keys,fields))
    # Exact per-image rates are sufficient to reconstruct the balanced n,m curves.
    d.save_csv(out/"PER_IMAGE_N_M.csv.gz",summarize(D,["target","building","pool_id","difficulty","historical_phase","k","m"],fields))
    d.save_csv(out/"Q_MATCHED_SUPPORT.csv",summarize(D[D.history_Q_C_minus_B.abs()<=2],["target","n_band","m"],fields))
    S=D[D.shape_registered].copy();sf=[f"{p}_{m}" for p in ("within","cross") for m in SHAPE]
    for name,keys in {"SHAPE_N_M":["target","k","m"],"SHAPE_SOURCE":["target","source_mode"],"SHAPE_DIFFICULTY":["target","difficulty"]}.items():d.save_csv(out/(name+".csv"),summarize(S,keys,fields+sf))
    # The second draw was registered before all baseline fusions, not selected
    # as a confirmatory winner. Summaries keep only cells with both actual draws.
    pairkeys=["target","building","pool_id","difficulty","k","m"]
    DD=D[D.draw.eq(0)].merge(D[D.draw.eq(1)],on=pairkeys,suffixes=("_0","_1"),validate="one_to_one")
    DD["same_source_vector"]=DD.block_new_n_0.eq(DD.block_new_n_1)&DD.block_v1_n_0.eq(DD.block_v1_n_1)
    bothq=DD.net_Q_0.notna()&DD.net_Q_1.notna()
    DD["net_Q_direction_agreement"]=np.where(bothq,np.sign(DD.net_Q_0)==np.sign(DD.net_Q_1),np.nan)
    DD["net_Q_contrast_abs_difference"]=abs(DD.net_Q_0-DD.net_Q_1)
    for name in ("within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main"):
        DD[name+"_both_draws"]=DD[name+"_0"]&DD[name+"_1"]
    dr=[];dm=["net_Q_direction_agreement","net_Q_contrast_abs_difference","net_Q_0","net_Q_1"]+[n+"_both_draws" for n in ("within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main")]
    for key,g in DD.groupby(["target","k","m","same_source_vector"]):
        z=dict(zip(["target","k","m","same_source_vector"],key));z.update(paired_draw_cells=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),finite_quality_draw_pairs=int((g.net_Q_0.notna()&g.net_Q_1.notna()).sum()));z.update(hmean(g,dm));dr.append(z)
    d.save_csv(out/"DRAW_REPLICATION.csv",dr)
    # Leave-one-worker exclusions are descriptive robustness, with exact support.
    person=[]
    for target,T in D.groupby("target"):
        bs={b["block_id"]:b for b in payload["blocks"] if b["target"]==target}
        for mode in ("any_team","replacement_blocks"):
            membership={}
            for bid,b in bs.items():
                base=set(sum(b["blocks"].values(),[]))
                for e in T[T.block_id==bid].itertuples():membership[e.event_id]=base|set(b["core_order"][:e.k-e.m]) if mode=="any_team" else base
            for worker in sorted(used_workers):
                subset=T[[worker not in membership[x] for x in T.event_id]]
                if len(subset)==len(T):continue
                z=summarize(subset,[],fields).to_dict("records")
                comparable=T.merge(subset[["pool_id","k","m"]].drop_duplicates(),on=["pool_id","k","m"],how="inner")
                prior=hmean(comparable,["within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main","net_Q"])
                matched={"same_retained_nm_pool_baseline_"+k:v for k,v in prior.items()}
                if z:
                    matched.update({"change_vs_same_retained_nm_pool_baseline_"+k:z[0][k]-v if v is not None and z[0][k] is not None else None for k,v in prior.items()})
                person.append(dict(target=target,removed_worker=worker,exclusion=mode,excluded_events=len(T)-len(subset),**(z[0] if z else dict(events=0,images=0,buildings=0)),**matched))
    d.save_csv(out/"PERSON_EXCLUSION.csv",person)
    d.save_json(out/"Q_SOURCE_ADJUSTMENT.json",dict(models=adjusted_models(D),interpretation="Within one fixed direction, these are descriptive building-weighted fits and Q-matched support. They do not establish an independent causal label effect or out-of-sample predictor. No personnel labels or metric thresholds are changed."))
    NDall=pd.DataFrame(nested);ND=NDall[NDall.n_before.ge(3)].copy();ND["node_lost"]=np.where(ND.node_count_change.notna(),ND.node_count_change.lt(0),np.nan);ND["quality_worse"]=np.where(ND.B8L2_change.notna(),ND.B8L2_change.lt(0),np.nan)
    nested_summary=[]
    for key,g in ND.groupby(["target","arm","m","n_before","threshold_increased"]):
        z=dict(zip(["target","arm","m","n_before","threshold_increased"],key));z.update(steps=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),quality_finite_steps=int(g.B8L2_change.notna().sum()));z.update(hmean(g,["node_count_change","node_lost","B8L2_change","quality_worse","floor_jaccard_difference","complete_after"]));nested_summary.append(z)
    d.save_csv(out/"NESTED_SUMMARY.csv",nested_summary)
    receipt=dict(schema="known_baseline_all_event_analysis_v1",all_requested_events_and_teams_consumed=True,request_sha256=freeze["request_sha256"],analyzer_sha256=d.sha(Path(__file__)),all_attempted_events=len(Dall),formal_n_ge_3_events=len(D),two_person_deferred_events=int(Dall.k.eq(2).sum()),unique_teams=len(allteams),images=D.pool_id.nunique(),buildings=D.building.nunique(),workers=len(used_workers),complete_unique_teams=complete_unique,unique_score_status_counts=dict(unique_status),formal_shape_registered_events=len(S),all_attempted_shape_pairs=len(shape_rows),nested_steps=len(nested),native_pool_sources=by_pool_receipt,independence="Same known55 people,96 v2 images,12 already explored nonhistory buildings. Neither33,332 events nor99,779 teams are independent images.",weights="First average block draws in each pool,n,m cell, then cells within image, images within building, buildings within stratum. Overall averages describe this enumerated n,m grid, not natural recruitment frequencies.",continuous_missing="No zero imputation; nondeferred stability failures stay False in attempted-event denominators; numeric summaries report available support. Native n=2 two_person_deferred is separated; formal tables n>=3, all-attempted table retained.",seconds=time.monotonic()-started)
    d.save_json(out/"ANALYSIS_RECEIPT.json",receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!="native_pool_sources"},ensure_ascii=False))


if __name__=="__main__":main()
