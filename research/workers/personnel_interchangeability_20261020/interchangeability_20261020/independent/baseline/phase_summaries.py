"""Compact phase-separated displays of the unchanged full baseline results."""
from pathlib import Path
import math,json
import pandas as pd,numpy as np
import analyze_baseline as a
import design_baseline as d


def main():
    folder=Path(__file__).parent;out=folder/"results";P=d.fr.read(folder/"REQUESTS.json.gz")
    a.BLOCK_LOOKUP={b["block_id"]:b for b in P["blocks"]}
    D=pd.read_csv(out/"EVENT_RESULTS.csv.gz");D=D[D.k.ge(3)].copy();fields=a.RATE_FIELDS+a.CONTINUOUS
    d.save_csv(out/"PHASE_SUMMARY.csv",a.summarize(D,["target","historical_phase"],fields))
    d.save_csv(out/"PURE_CLASS_PHASE.csv",a.summarize(D[D.core_n.eq(0)],["target","historical_phase"],fields))
    d.save_csv(out/"Q_MATCHED_PHASE.csv",a.summarize(D[D.history_Q_C_minus_B.abs().le(2)],["target","historical_phase"],fields))
    S=D[D.shape_registered].copy();sf=[f"{p}_{m}" for p in ("within","cross") for m in a.SHAPE]
    d.save_csv(out/"SHAPE_MATCHED_PHASE.csv",a.summarize(S,["target","historical_phase"],fields+sf))
    # Cohorts fixed by capacity at the previously published G n17/m8 and R
    # n13/m2 anchors. This isolates changing pool support from shorter-n curves.
    matched=[]
    for target,m,anchor in [("G",8,17),("R",2,13)]:
        T=D[D.target.eq(target)&D.m.eq(m)]
        ids=set(T.loc[T.k.eq(anchor),"block_id"])
        subset=T[T.block_id.isin(ids)&T.k.le(anchor)]
        z=a.summarize(subset,["target","historical_phase","k","m"],fields)
        z["capacity_fixed_at_anchor_n"]=anchor;z["cohort_rule"]="Exactly the registered block chains feasible at the old published anchor; same chains retained at every shorter n>=3."
        matched.append(z)
    d.save_csv(out/"ANCHOR_CAPACITY_FIXED_N_CURVES.csv",pd.concat(matched,ignore_index=True))
    anchor=D[((D.target.eq("G"))&D.k.eq(17)&D.m.eq(8))|((D.target.eq("R"))&D.k.eq(13)&D.m.eq(2))]
    d.save_csv(out/"PUBLISHED_ANCHOR_REPLICATION.csv",a.summarize(anchor,["target","historical_phase","k","m"],fields))
    keys=["target","historical_phase","building","pool_id","k","m"]
    B=D[D.draw.eq(0)].merge(D[D.draw.eq(1)],on=keys,suffixes=("_0","_1"),validate="one_to_one")
    B["same_source_vector"]=B.block_new_n_0.eq(B.block_new_n_1)&B.block_v1_n_0.eq(B.block_v1_n_1)
    for m0 in ["within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main"]:B[m0+"_both_draws"]=B[m0+"_0"]&B[m0+"_1"]
    B["quality_sign_agrees"]=np.where(B.net_Q_0.notna()&B.net_Q_1.notna(),np.sign(B.net_Q_0).eq(np.sign(B.net_Q_1)),np.nan)
    B["quality_both_worsen_ge2"]=np.where(B.net_Q_0.notna()&B.net_Q_1.notna(),B.net_Q_0.le(-2)&B.net_Q_1.le(-2),np.nan)
    B["quality_both_improve_ge2"]=np.where(B.net_Q_0.notna()&B.net_Q_1.notna(),B.net_Q_0.ge(2)&B.net_Q_1.ge(2),np.nan)
    B["net_Q_draw_difference"]=abs(B.net_Q_0-B.net_Q_1)
    bfields=[m0+"_both_draws" for m0 in ["within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main"]]+["quality_sign_agrees","quality_both_worsen_ge2","quality_both_improve_ge2","net_Q_draw_difference"]
    reps=[]
    for key,g in B.groupby(["target","historical_phase","same_source_vector"]):
        r=dict(zip(["target","historical_phase","same_source_vector"],key));r.update(paired_draw_cells=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique());r.update(a.hmean(g,bfields));reps.append(r)
    d.save_csv(out/"DRAW_REPLICATION_PHASE.csv",reps)
    leave=pd.read_csv(out/"PERSON_EXCLUSION.csv");ext=[]
    for key,g in leave.groupby(["target","exclusion"]):
        for metric in ["within_joint_stable_main","cross_joint_stable_main","within_geometry_noQ_main","cross_geometry_noQ_main","net_Q"]:
            col="change_vs_same_retained_nm_pool_baseline_"+metric
            r=dict(target=key[0],exclusion=key[1],metric=metric,workers_examined=g.removed_worker.nunique(),minimum_retained_images=int(g.images.min()),maximum_retained_images=int(g.images.max()),minimum_retained_buildings=int(g.buildings.min()),max_change_vs_same_retained_cells=float(g[col].max()),min_change_vs_same_retained_cells=float(g[col].min()))
            r["max_change_removed_worker"]=g.loc[g[col].idxmax(),"removed_worker"];r["min_change_removed_worker"]=g.loc[g[col].idxmin(),"removed_worker"];ext.append(r)
    d.save_csv(out/"PERSON_EXCLUSION_EXTREMES.csv",ext)
    models=d.fr.read(out/"Q_SOURCE_ADJUSTMENT.json")["models"]
    d.save_json(out/"MODEL_IDENTIFIABILITY_NOTE.json",dict(rank_deficient_models=[dict(target=z["target"],response=z["response"],model=z["model"],rank=z["rank"],columns=z["columns"]) for z in models if z["rank"]<z["columns"]],reason="All R replacement blocks are new-source only, making block_new_fraction constant and collinear with the intercept. Least-squares fitted values/R2 remain defined, but that individual source coefficient and intercept have no separate interpretation. These descriptive fits do not identify a label effect independent of people or quality.",Q_matching="Overall class effects are reported first. Tight historical-Q overlap is limited and is not a reason to discard the original class signal.",output_sha256={p.name:d.sha(p) for p in [out/"PHASE_SUMMARY.csv",out/"SHAPE_MATCHED_PHASE.csv",out/"Q_MATCHED_PHASE.csv",out/"ANCHOR_CAPACITY_FIXED_N_CURVES.csv"]}))
    print(json.dumps(dict(phase_rows=4,formal_events=len(D),Q_matched_events=int(D.history_Q_C_minus_B.abs().le(2).sum()),shape_registered_events=len(S))))


if __name__=="__main__":main()
