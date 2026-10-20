#!/usr/bin/env python3
"""Discovery-only, post-selection identity sensitivity of 8 fixed directions.

Deleting events is descriptive: background/n/image support can change. This
does not estimate a causal person effect and does not refit any class. The
empty support of saturated 4-person same-class m2 blocks is kept explicitly.
"""
from pathlib import Path
import json
import sys

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze_reverse_discovery as rev

METRICS=["within_joint_stable_main","cross_joint_stable_main","gap_joint_stable_main",
    "within_geometry_noQ_main","cross_geometry_noQ_main","gap_geometry_noQ_main",
    "within_geometry_shape_main","cross_geometry_shape_main","gap_geometry_shape_main",
    "net_B8L2_change","net_D10_change","within_abs_B8L2_change","cross_abs_B8L2_change",
    "within_floor_jaccard_difference","cross_floor_jaccard_difference",
    "net_diag_wall_coverage_05_delta","net_diag_corner_recall_05_delta","A_complete","B_complete","C_complete"]


def summarize(g):
    out={"events":len(g),"images":g.pool_id.nunique(),"buildings":g.building.nunique(),
        "status":"observed" if len(g) else "no_remaining_event",
        "unique_teams":len(set(g.A_team_key)|set(g.B_team_key)|set(g.C_team_key)),
        "quality_finite_events":g.net_B8L2_change.notna().sum()}
    if not len(g):
        out.update({m:None for m in METRICS});return out
    byimg=g.groupby(["building","pool_id"])[METRICS].mean()
    byb=byimg.groupby("building").mean()
    out.update(byb.mean().to_dict())
    for m in ["gap_joint_stable_main","gap_geometry_shape_main","net_B8L2_change"]:
        out[m+"_positive_buildings"]=(byb[m]>0).sum()
        out[m+"_negative_buildings"]=(byb[m]<0).sum()
    return out


def main():
    proposals=json.load(open(HERE/"RECOMMENDED_DIRECTIONS.json"))
    assert proposals["assessment_outcomes_read"] is False
    members=pd.read_csv(HERE/"event_member_index.csv.gz")
    selected=[]
    for r in proposals["proposals"]:
        take=members[(members.method_id==r["method_id"])&(members.context_id==r["context_id"])&
            (members.outgoing_class==r["outgoing_class"])&(members.incoming_class==r["incoming_class"])&
            (members.n>=3)&(members.m>=2)].copy()
        take["proposal_id"]=r["proposal_id"];selected.append(take)
    members=pd.concat(selected,ignore_index=True)
    assert members.phase.eq("discovery").all()
    cols=["event_id","A_team_key","B_team_key","C_team_key"]+METRICS
    data=pd.concat([pd.read_csv(rev.ROOT/"interchangeability_20261020/discovery/reverse_metrics/event_parts"/(pid+".csv.gz"),usecols=cols)
        for pid in sorted(members.pool_id.unique())],ignore_index=True)
    frame=members.merge(data,on="event_id",validate="one_to_one")
    rows=[];blocks=[]
    for r in proposals["proposals"]:
        base=frame[frame.proposal_id.eq(r["proposal_id"])]
        for scope,g in [("all_primary",base),("m2_n11_17",base[(base.m==2)&base.n.between(11,17)])]:
            meta={"proposal_id":r["proposal_id"],"scope":scope,"method_id":r["method_id"],"context_id":r["context_id"],
                "outgoing_class":r["outgoing_class"],"incoming_class":r["incoming_class"]}
            rows.append(dict(meta,removal_role="none",worker_id="all",**summarize(g)))
            for role,cols in [("any_replaceable_block",["outgoing_workers","within_incoming","cross_incoming"]),("cross_block_only",["cross_incoming"])]:
                workers=r["outgoing_members"]+r["incoming_members"] if role=="any_replaceable_block" else r["incoming_members"]
                for w in workers:
                    present=pd.Series(False,index=g.index)
                    for col in cols:present|=g[col].str.split("|").apply(lambda a:w in a)
                    rows.append(dict(meta,removal_role=role,worker_id=w,**summarize(g[~present])))
            for block,z in g.groupby("cross_incoming"):
                blocks.append(dict(meta,cross_incoming=block,**summarize(z)))
    rev.write_csv(HERE/"SELECTED_MEMBER_REMOVAL_DESCRIPTIVE.csv.gz",pd.DataFrame(rows))
    rev.write_csv(HERE/"SELECTED_CROSS_BLOCK_SUPPORT.csv.gz",pd.DataFrame(blocks))
    rev.write_json(HERE/"SELECTED_MEMBER_STRESS_RECEIPT.json",rev.clean({
        "phase":"discovery","assessment_outcomes_read":False,"class_refit":False,
        "input_recommendation_sha256":rev.sha(HERE/"RECOMMENDED_DIRECTIONS.json"),
        "input_member_index_sha256":rev.sha(HERE/"event_member_index.csv.gz"),"script_sha256":rev.sha(Path(__file__)),
        "candidate_rows":len(rows),"cross_block_rows":len(blocks),
        "removal":"Exclude all events containing specified worker in indicated replaceable block roles; fixed background is not removed.",
        "causal_status":"Descriptive sensitivity only: n/core/image/building distribution can change after deletion. Not a causal worker contribution or a held-out-worker test.",
        "capacity":"For out-class size4 with m2, A/B consume all4 distinct people; deleting any such replaceable worker leaves no event. Missing result is explicitly not zero.",
    }))


if __name__=="__main__":main()
