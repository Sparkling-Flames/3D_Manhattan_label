"""Outcome-selected illustration candidates, kept separate from frozen tests.

Only original discovery buildings are inspected here. The complete baseline
grid and its counterexamples remain in result tables; choosing illustrations
does not define or validate a new personnel rule.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
import design_baseline as d


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,np.generic):return clean(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--folder",type=Path,default=Path(__file__).parent);a=ap.parse_args();folder=a.folder;result=folder/"results"
    E=pd.read_csv(result/"EVENT_RESULTS.csv.gz");D=E[E.historical_phase.eq("discovery")&E.k.ge(3)].copy()
    payload=d.fr.read(folder/"REQUESTS.json.gz");requests={r["request_id"]:r for r in payload["requests"]};blocks={b["block_id"]:b for b in payload["blocks"]}
    pools={p["pool_id"]:p for p in d.fr.read(d.SNAPSHOT)["images"]};rows=[];ledger=[]
    mainfields=["net_Q","net_D10","history_Q_C_minus_B","core_history_q_beta"]
    armfields=[f"{a}_{m}" for a in "ABC" for m in ("B8L2","D10","nodes","score_status","omission","extension","complete_evaluable")]
    pairfields=[f"{p}_{m}" for p in ("within","cross") for m in ("joint_stable_strict","joint_stable_main","joint_stable_wide","geometry_noQ_main","geometry_shape_main","abs_B8L2_change","floor_jaccard_difference","node_count_difference","structure_bound_cyclic_deg","mean_height_prism_pair_iou","bottom_y_absdiff_deg_p95","bottom_y_absdiff_deg_max","top_y_absdiff_deg_p95","inferred_total_height_mean_abs_logratio","true_corner_F1_main","wall_coverage_symmetric_min_main","different_original_nodes_shape_main_passes","geometry_shape_main_and_prism_proxy_iou_lt_095")]
    def event_info(e):
        e=dict(e);pid=e["pool_id"];p=pools[pid];recs={r["worker_id"]:r for r in p["records"]};b=blocks[e["block_id"]]
        value={k:e.get(k) for k in ["event_id","block_id","target","historical_phase","pool_id","image","building","difficulty","reference_id","k","m","draw","block_new_n","block_v1_n","core_n","core_counts","A_counts","B_counts","C_counts","shape_registered"]+mainfields+armfields+pairfields}
        value["requests"]={arm:dict(request_id=e["event_id"]+"__"+arm,team_key=requests[e["event_id"]+"__"+arm]["team_key"],workers=[dict(worker_id=w,origin=recs[w]["origin"],object_id=recs[w]["object_id"],id=recs[w]["id"]) for w in requests[e["event_id"]+"__"+arm]["worker_ids"]]) for arm in "ABC"}
        value["replacement_blocks"]=b["blocks"];value["common_core"]=b["core_order"][:int(e["k"])-int(e["m"])];value["native_pool_path"]=str((folder/"native_runs/pools"/(pid+".json.gz")).relative_to(d.ROOT))
        other=D[D.target.eq(e["target"])&D.pool_id.eq(pid)&D.k.eq(e["k"])&D.m.eq(e["m"])&D.event_id.ne(e["event_id"])]
        value["other_registered_draw_same_pool_n_m"]=[{k:z[k] for k in ["event_id","block_id","draw","block_new_n","block_v1_n"]+mainfields+pairfields} for z in other.to_dict("records")]
        return value
    def choose(name,definition,eligible,ranking,ascending=False):
        for target in ("G","R"):
            g=eligible[eligible.target.eq(target)].copy()
            ledger.append(dict(category=name,target=target,definition=definition,eligible_events=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),ranking=ranking,ascending=ascending,limit=1))
            if len(g):
                e=g.sort_values([ranking,"event_id"],ascending=[ascending,True],kind="stable").iloc[0]
                rows.append(dict(category=name,definition=definition,event=event_info(e)))
    complete=D.A_complete_evaluable&D.B_complete_evaluable&D.C_complete_evaluable
    geometric=D[complete&D.within_joint_stable_main&~D.cross_geometry_noQ_main].copy()
    geometric["floor_contrast"]=geometric.cross_floor_jaccard_difference-geometric.within_floor_jaccard_difference
    choose("class_geometric_contrast","A/B main passes; A/C no-Q geometry fails; same exact core,n,m and source counts.",geometric,"floor_contrast")
    # Preserve extreme one-draw illustrations above, and separately locate
    # multi-person changes that repeat in both actually registered block draws.
    repeated=[]
    for _,g in D[D.m.ge(2)].groupby(["target","pool_id","k","m"]):
        if len(g)!=2 or g.draw.nunique()!=2:continue
        if g.within_joint_stable_main.all() and (~g.cross_geometry_noQ_main).all():
            z=g.sort_values("draw").iloc[0].to_dict()
            z["two_draw_mean_floor_contrast"]=float((g.cross_floor_jaccard_difference-g.within_floor_jaccard_difference).mean())
            repeated.append(z)
    repeated=pd.DataFrame(repeated) if repeated else D.iloc[:0].copy().assign(two_draw_mean_floor_contrast=[])
    choose("both_draws_multi_person_geometric_contrast","m>=2; both registered member/background draws have A/B main pass and A/C no-Q fail; rank mean geometric contrast across the two draws. Their source vectors are retained separately.",repeated,"two_draw_mean_floor_contrast")
    qonly=D[complete&D.within_joint_stable_main&~D.cross_joint_stable_main&D.cross_geometry_noQ_main].copy()
    qonly["Q_contrast"]=qonly.cross_abs_B8L2_change-qonly.within_abs_B8L2_change
    choose("quality_only_legacy_cross_break","A/B main passes; A/C main fails but legacy no-Q passes, so its main failure is explained by the Q threshold.",qonly,"Q_contrast")
    same=D[complete&D.within_abs_B8L2_change.le(2)&~D.within_geometry_noQ_main]
    choose("same_composition_similar_Q_different_geometry","A/B scores within 2 but legacy no-Q geometry fails; same composition is not overall interchangeable.",same,"within_floor_jaccard_difference")
    improve=D[complete&D.history_Q_C_minus_B.lt(-2)&D.net_Q.ge(5)&D.net_D10.ge(5)]
    choose("lower_historical_Q_block_improves_this_image","C block historical Q at least 2 below B, yet B8 and D10 improve by at least 5 on this image; illustrative conditional contribution, not learned selection success.",improve,"net_Q")
    failure=D[D.A_complete_evaluable&D.B_complete_evaluable&~D.C_complete_evaluable]
    choose("cross_class_fusion_failure","A/B are evaluable; changed class C is not; failures retained and not zero-imputed.",failure,"B_B8L2")
    for pair in ("within","cross"):
        shape=D[D.shape_registered&complete]
        redundant=shape[shape[pair+"_different_original_nodes_shape_main_passes"].eq(True)]
        choose(pair+"_different_nodes_shape_equivalent","Registered shape criterion passes with different original node counts; inspect true corners and collinearity before interpretation.",redundant,pair+"_floor_jaccard_difference",True)
        depth=shape[shape[pair+"_geometry_shape_main_and_prism_proxy_iou_lt_095"].eq(True)]
        choose(pair+"_shape_passes_depth_proxy_changes","Registered shape passes but mean-height prism proxy IoU < .95; proxy is not exact full 3D IoU.",depth,pair+"_mean_height_prism_pair_iou",True)
    mechanism=[];mp=result/"MECHANISM_STEPS.csv.gz"
    if mp.exists():
        M=pd.read_csv(mp);M=M[M.n_before.ge(3)&M.event_before.isin(D.event_id)]
        F=M[M.threshold_only_selection_loss_supported.eq(True)]
        for target in ("G","R"):
            for direction,mask,ascending in (("quality_improves",F.B8L2_change.gt(2),False),("quality_worsens",F.B8L2_change.lt(-2),True)):
                g=F[F.target.eq(target)&mask];ledger.append(dict(category="threshold_"+direction,target=target,definition="Registered nested step; old shared observation partition unchanged; threshold increases; selected groups lose selection with unchanged support; Q moves by more than 2.",eligible_arm_steps=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),ranking="B8L2_change",ascending=ascending,limit=1))
                if len(g):
                    z=g.sort_values(["B8L2_change","event_before","arm"],ascending=[ascending,True,True]).iloc[0].to_dict()
                    mechanism.append(dict(category="threshold_"+direction,step=z,before=event_info(D[D.event_id.eq(z["event_before"])].iloc[0]),after=event_info(D[D.event_id.eq(z["event_after"])].iloc[0])))
    output=dict(schema="known_baseline_discovery_illustration_candidates_v1",request_sha256=d.sha(folder/"REQUESTS.json.gz"),code_sha256=d.sha(Path(__file__)),selection_is_outcome_exploratory=True,phase="Original discovery buildings only; entire v2 previously explored. No claim of external blind validation.",ledger=ledger,candidates=rows,mechanism_candidates=mechanism,limits="Categories retain selected positive and counterexamples. Extreme ranking chooses visible illustrations, not representative effect estimates. Read n,m phase tables for prevalence; do not interpret number of replayed teams as independent images.")
    d.save_json(result/"DISCOVERY_CASE_CANDIDATES.json",clean(output))
    d.save_csv(result/"CASE_SELECTION_LEDGER.csv",ledger)
    print(json.dumps(dict(candidates=len(rows),mechanism_candidates=len(mechanism),unique_event_ids=len({x["event"]["event_id"] for x in rows}),result=str(result/"DISCOVERY_CASE_CANDIDATES.json"))))


if __name__=="__main__":main()
