"""Post-registration mechanism analysis: exact same-class target-member swaps.

These are cached C endpoint pairs inside the registered n20 m3/m4 reservoirs.
Their actual turnover is one; they explain large-block member sensitivity and
are explicitly not substituted for the main m3/m4 class-exchange experiment.
"""
from __future__ import annotations
import itertools
import math
import pandas as pd
from register_design import HERE, h, write, save
from evaluate_registered import load_pool, previous


def main():
    e = pd.read_csv(HERE / "EVENTS_COMPLETE.csv.gz", low_memory=False)
    e = e[e.n.eq(20) & e.m_AB.isin([3,4]) & e.training_QT_direction.eq("q_up__faster")]
    labels = pd.read_csv(HERE / "INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz")
    labels = labels.set_index(["heldout_building", "worker_id"])
    rows = []
    for pool, pg in e.groupby("pool_id"):
        needed = set(pg.team_C)
        teams, _ = load_pool(pool, needed)
        assert needed <= teams.keys()
        for panel, g in pg.groupby("panel_id"):
            points = g[["team_C", "changed_count_block_Z"]].drop_duplicates().to_dict("records")
            meta = g.iloc[0]
            for left, right in itertools.combinations(points, 2):
                lset, rset = [set(x["changed_count_block_Z"].split("|")) for x in [left,right]]
                if len(lset-rset) != 1:
                    continue
                out, inc = next(iter(lset-rset)), next(iter(rset-lset))
                lo, li = labels.loc[(meta.building,out)], labels.loc[(meta.building,inc)]
                if (lo.t_history, out) > (li.t_history, inc):
                    left,right = right,left
                    out,inc = inc,out
                    lo,li = li,lo
                a,b = teams[left["team_C"]],teams[right["team_C"]]
                assert lo.coarse_label == li.coarse_label
                common = sorted(set(a["member_workers"]) & set(b["member_workers"]))
                assert len(common) == 19
                row=dict(pair_id=h("target_member_swap",a["team_key"],b["team_key"])[:24],pool_id=pool,image=meta.image,
                         building=meta.building,panel_id=panel,n=20,actual_m=1,original_class_block_m=int(meta.m_AB),
                         target_class=meta.target_class,from_worker=out,to_worker=inc,
                         semantic_direction="faster_historical_member_to_slower_historical_member_within_target_class",
                         team_from=a["team_key"],team_to=b["team_key"],
                         members_from="|".join(a["member_workers"]),members_to="|".join(b["member_workers"]),
                         exact_common_background="|".join(common),class_seat_turnover=0,
                         historical_Q_in_minus_out=li.q_history-lo.q_history,
                         historical_logT_in_minus_out=li.t_history-lo.t_history,
                         historical_complex_turn_in_minus_out=li.complex_turn_history-lo.complex_turn_history,
                         from_failure=not bool(a.get("complete_evaluable")),to_failure=not bool(b.get("complete_evaluable")),
                         analysis_role="exploratory mechanism within fully registered target subsets; not a new large-block trial")
                for f in previous.COMPONENTS+previous.EXTRA:
                    x,y=a.get(f),b.get(f)
                    row["from_"+f]=x
                    row["to_"+f]=y
                    row["change_"+f]=y-x if previous.finite(x) and previous.finite(y) else None
                aT,bT=a.get("source_time_total_seconds"),b.get("source_time_total_seconds")
                row["recorded_time_logratio"]=math.log(bT/aT) if aT and bT and a.get("time_source_kinds")==b.get("time_source_kinds") else None
                rows.append(row)
    result=pd.DataFrame(rows).drop_duplicates("pair_id")
    write(HERE/"TARGET_WITHIN_CLASS_EXACT_SWAPS.csv.gz",result)
    metrics=["change_B8L2","change_D10","change_nodes","change_S_bottom_deg","change_ref_node_recall_9","change_ref_edge_recall_9",
             "recorded_time_logratio","from_failure","to_failure"]
    panel=result.groupby(["from_worker","to_worker","original_class_block_m","building","image","panel_id"])[metrics].mean().reset_index()
    image=panel.groupby(["from_worker","to_worker","original_class_block_m","building","image"])[metrics].mean().reset_index()
    building=image.groupby(["from_worker","to_worker","original_class_block_m","building"])[metrics].mean().reset_index()
    write(HERE/"TARGET_WITHIN_CLASS_SWAP_IMAGES.csv",image)
    write(HERE/"TARGET_WITHIN_CLASS_SWAP_BUILDINGS.csv",building)
    summary=[]
    for (a,b,m),g in building.groupby(["from_worker","to_worker","original_class_block_m"]):
        im=image[(image.from_worker==a)&(image.to_worker==b)&(image.original_class_block_m==m)]
        r=dict(from_worker=a,to_worker=b,original_class_block_m=m,actual_m=1,images=len(im),buildings=len(g),
               positive_images=int((im.change_B8L2>0).sum()),known_images=int(im.change_B8L2.notna().sum()),
               positive_buildings=int((g.change_B8L2>0).sum()),known_buildings=int(g.change_B8L2.notna().sum()))
        r.update({k:g[k].mean() for k in metrics})
        summary.append(r)
    write(HERE/"TARGET_WITHIN_CLASS_SWAP_SUMMARY.csv",pd.DataFrame(summary))
    focus=result[(result.from_worker=="W126")&(result.to_worker=="W130")].sort_values("change_B8L2",ascending=False)
    write(HERE/"W126_TO_W130_EXACT_CASES.csv",focus.drop_duplicates(["image","original_class_block_m"]).head(12))
    save(HERE/"TARGET_SWAP_ANALYSIS_RECEIPT.json",dict(unique_pairs=len(result),native_fusion_calls=0,
            main_class_experiment_not_replaced=True,actual_turnover=1,all_class_seat_turnovers=0,
            stage="secondary explanatory analysis of already registered target member subsets"))


if __name__=="__main__":
    main()
