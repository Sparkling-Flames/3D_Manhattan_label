"""Native state-only replay of the pre-registered nested vote subset.

Saved quality remains the original baseline measurement. No new reference,
native parameter, semantic necessity label, or output-selected sample is used.
"""
from __future__ import annotations
import os
for _v in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[_v]="1"
from collections import defaultdict
import argparse,concurrent.futures,json,math
from pathlib import Path
import sys,time
import numpy as np
import pandas as pd
import design_baseline as d
ROOT=d.ROOT
sys.path.insert(0,str(ROOT/"interchangeability_20261020/independent"))
import pair_diagnostics as px
import fusion_runner as fr


def same_array(a,b):
    if a is None or b is None:return a is None and b is None,0. if a is None and b is None else None
    aa,bb=np.asarray(a,float),np.asarray(b,float)
    if aa.shape!=bb.shape:return False,None
    err=float(np.max(np.abs(aa-bb))) if aa.size else 0.
    return err<=1e-10,err


def run_pool(pid,steps,pool,requests,blocks,runs,restored):
    started=time.monotonic();fe=fr.init_engine(restored)
    rec={r["worker_id"]:r for r in pool["records"]};cached=fr.read(Path(runs)/"pools"/(pid+".json.gz"));teams={r["team_key"]:r for r in cached["teams"]}
    wanted={e[k]+"__"+arm for e in steps for k in ("event_before","event_after") for arm in "ABC"}
    keys={requests[rid]["team_key"]:requests[rid]["worker_ids"] for rid in wanted};states={};maxerr=0.
    with fe.cached_matching():
        for key,workers in keys.items():
            state=fe.compact(fe.fuse([rec[w] for w in sorted(workers)],gap=fe.WORKING_GAP)["automatic"])
            assert {m["id"] for g in state["identity_groups"] for m in g["members"]}=={rec[w]["id"] for w in workers}
            for field in ("points","footprint"):
                okay,error=same_array(state["candidate"].get(field),(teams[key].get("geometry") or {}).get(field));assert okay,(pid,key,field,error);maxerr=max(maxerr,error or 0.)
            assert state["n"]==teams[key]["k"] and len(state["node_consensus"]["nodes"])==teams[key]["nodes"]
            states[key]=state
    geometry_cache={};rows=[]
    for e in steps:
        for arm in "ABC":
            qa,qb=[requests[e[k]+"__"+arm] for k in ("event_before","event_after")]
            old,new=states[qa["team_key"]],states[qb["team_key"]];a,b=teams[qa["team_key"]],teams[qb["team_key"]]
            assert set(qb["worker_ids"])-set(qa["worker_ids"])=={e["added_worker"]}
            transition=fe.transition(old,new)
            part=lambda state:{frozenset((m["id"],m["pair_index"]) for m in g["members"]):g for g in state["identity_groups"]}
            pa,pb=part(old),part(new);oa=set().union(*pa) if pa else set();ob=set().union(*pb) if pb else set();shared=oa&ob
            restricted={k&shared:g for k,g in pb.items() if k&shared};losses=[]
            for members,g in pa.items():
                if members<=shared and members in restricted:
                    z=restricted[members]
                    if g["selected"] and not z["selected"]:
                        losses.append(dict(old_observations=[list(x) for x in sorted(members)],support_before=g["support"],support_after=z["support"],threshold_before=old["minimum_support"],threshold_after=new["minimum_support"],support_unchanged=g["support"]==z["support"]))
            assert len(losses)==transition["unchanged_identity_vote_losses"]
            r=dict(e,arm=arm,team_before=qa["team_key"],team_after=qb["team_key"],added_source=rec[e["added_worker"]]["origin"],nodes_before=a["nodes"],nodes_after=b["nodes"],node_count_change=b["nodes"]-a["nodes"],B8L2_before=a.get("B8L2"),B8L2_after=b.get("B8L2"),B8L2_change=(b["B8L2"]-a["B8L2"]) if a.get("B8L2") is not None and b.get("B8L2") is not None else None,complete_before=bool(a.get("complete_evaluable")),complete_after=bool(b.get("complete_evaluable")),score_status_before=a["score_status"],score_status_after=b["score_status"],**transition,unchanged_support_loss_groups_n=sum(x["support_unchanged"] for x in losses),loss_bookkeeping_json=json.dumps(losses,sort_keys=True,separators=(",",":")),old_observation_partition_unchanged=transition["changed_coidentity_pairs"]==0,threshold_only_selection_loss_supported=bool(transition["changed_coidentity_pairs"]==0 and transition["threshold_increased"] and losses and all(x["support_unchanged"] for x in losses)))
            # BASELINE_SPEC allows adjacent geometry only when both endpoints
            # are in its original metadata-selected shape event subset. Vote
            # identity bookkeeping remains registered for every mechanism step.
            if e["shape_registered_both_endpoints"]:
                r.update(px.geometry_metrics(a,b,cache=geometry_cache))
            rows.append(r)
    return rows,dict(pool_id=pid,registered_steps=len(steps),native_replayed_unique_teams=len(keys),geometry_max_absolute_difference=maxerr,seconds=time.monotonic()-started)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--folder",type=Path,default=Path(__file__).parent);ap.add_argument("--runs",type=Path);ap.add_argument("--jobs",type=int,default=2);ap.add_argument("--restored",type=Path,default=ROOT/"restored");a=ap.parse_args();out=a.folder;spec=fr.read(out/"MECHANISM_SPEC.json");payload=fr.read(out/"REQUESTS.json.gz");assert d.sha(out/"REQUESTS.json.gz")==spec["baseline_request_sha256"]
    req={r["request_id"]:r for r in payload["requests"]};blocks={b["block_id"]:b for b in payload["blocks"]};pools={p["pool_id"]:p for p in fr.read(d.SNAPSHOT)["images"]};by=defaultdict(list)
    shape_event=pd.read_csv(out/"EVENT_DESIGN.csv.gz",usecols=["event_id","shape_registered"]).set_index("event_id").shape_registered.to_dict()
    for e0 in spec["steps"]:
        e=dict(e0,shape_registered_both_endpoints=bool(shape_event[e0["event_before"]] and shape_event[e0["event_after"]]))
        by[e["pool_id"]].append(e)
    rows=[];receipts=[];start=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        jobs=[]
        for pid,steps in by.items():
            rids={s[k]+"__"+arm for s in steps for k in ("event_before","event_after") for arm in "ABC"}
            jobs.append(ex.submit(run_pool,pid,steps,pools[pid],{rid:req[rid] for rid in rids},blocks,a.runs or out/"native_runs",a.restored))
        for f in concurrent.futures.as_completed(jobs):
            rr,receipt=f.result();rows+=rr;receipts.append(receipt);print(json.dumps(receipt),flush=True)
    assert len(rows)==3*spec["selected_step_n"]
    rows=sorted(rows,key=lambda r:(r["target"],r["pool_id"],r["block_id"],r["n_before"],r["arm"]))
    result=out/"results";result.mkdir(exist_ok=True);d.save_csv(result/"MECHANISM_STEPS.csv.gz",rows)
    D=pd.DataFrame(rows);F=D[D.n_before.ge(3)].copy();summary=[]
    metric=["changed_coidentity_pairs","unchanged_identity_vote_losses","unchanged_identity_vote_gains","unchanged_support_loss_groups_n","old_observation_partition_unchanged","threshold_only_selection_loss_supported","node_count_change","B8L2_change","bottom_y_absdiff_deg_p95","top_y_absdiff_deg_p95","boundary_total_height_abs_logratio_p95","geometry_shape_main"]
    # Equal images and buildings, first combine sampled n,m chains within image.
    for key,g in F.groupby(["target","arm","threshold_increased"]):
        r=dict(zip(["target","arm","threshold_increased"],key));r.update(steps=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),shape_registered_steps=int(g.shape_registered_both_endpoints.sum()),shape_registered_images=g.loc[g.shape_registered_both_endpoints,"pool_id"].nunique(),shape_registered_buildings=g.loc[g.shape_registered_both_endpoints,"building"].nunique());r.update(g.groupby(["building","pool_id"])[metric].mean().groupby("building").mean().mean().to_dict());summary.append(r)
    d.save_csv(result/"MECHANISM_SUMMARY.csv",summary)
    d.save_json(result/"MECHANISM_REPLAY_RECEIPT.json",dict(schema=spec["schema"],spec_sha256=d.sha(out/"MECHANISM_SPEC.json"),code_sha256=d.sha(Path(__file__)),state_only_replay=True,baseline_scores_used_without_rescoring=True,all_endpoint_native_geometries_match=True,native_replayed_unique_teams=sum(r["native_replayed_unique_teams"] for r in receipts),all_registered_arm_steps=len(rows),formal_n_before_ge3_arm_steps=len(F),all_registered_adjacent_shape_arm_steps=int(D.shape_registered_both_endpoints.sum()),formal_registered_adjacent_shape_arm_steps=int(F.shape_registered_both_endpoints.sum()),adjacent_shape_qualification="Only steps with both endpoints in original BASELINE_SPEC shape subset; other registered steps retain native vote bookkeeping and missing supplementary geometry.",images=D.pool_id.nunique(),buildings=D.building.nunique(),geometry_max_absolute_difference=max(r["geometry_max_absolute_difference"] for r in receipts),by_pool=receipts,seconds=time.monotonic()-start,interpretation="Threshold-only selection loss flag pertains to unchanged old observation group identities/support. Coordinates, new member identity, composition and visibility can still change; no necessary-wall semantics are established."))


if __name__=="__main__":main()
