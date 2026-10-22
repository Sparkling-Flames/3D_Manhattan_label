"""New parent-fixed × actual-m/r comparison of recovered complete n20 events.

Reads narrow columns from the 20261021 full events, never their duplicated
endpoint geometry. The main purpose is to separate m_AB=m_AC from often smaller
m_BC, and fine-within-parent changes from changes crossing the coarse parent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
OUT=HERE/"legacy_n20"
OUT.mkdir(exist_ok=True)
IDS=["pool_id","image","building","condition","layer","difficulty","method_id","tier","event_id",
     "event_mode","within_parent_fine_change","n","m_AB","m_AC","m_BC","physical_triple_id",
     "team_A","team_B","team_C","composition_A","composition_B","composition_C",
     "parent_composition_A","parent_composition_C","common_background","outgoing_block_X",
     "same_count_block_Y","changed_count_block_Z","A_member_workers","B_member_workers","C_member_workers",
     "all_scored","all_complete","A_failure","B_failure","C_failure"]
FIELDS=["B8L2","D10","iou_2d","IoU3D100","S_bottom_deg","dir","Hmean","Hcenter","omission","extension",
        "nodes","height_mean_h","height_mean_ratio","top_y_mean_px","bottom_y_mean_px","ref_node_recall_9","ref_edge_recall_9"]
GEOM=["floor_jaccard_difference","mean_height_prism_pair_difference","structure_bound_cyclic_deg",
      "centroid_distance_h","floor_area_abs_log_ratio"]
METRICS=[p+"_"+f for p in ["same","cross","net"] for f in FIELDS]
METRICS += [p+"_"+f for p in ["within","cross","net"] for f in GEOM]
METRICS += ["common_quality_within_abs","common_quality_cross_abs","abs_Q_change_advantage","stable_advantage",
            "stable_D10_advantage","net_failure_difference"]


def save(df,name):
    p=OUT/name;t=p.with_name(p.name+".tmp")
    df.to_csv(t,index=False,encoding="utf-8-sig",compression={"method":"gzip","compresslevel":3} if name.endswith(".gz") else None)
    t.replace(p)


def b(s):return s.astype(str).str.lower().eq("true")
def counts(x):return {p.split(":")[0]:int(p.split(":")[1]) for p in str(x).split("|") if ":" in p}
def mem(x):return frozenset(str(x).split("|"))


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--source",type=Path,required=True);args=ap.parse_args()
    inputs=sorted((args.source/"manual/checkpointed_manual/shards").glob("*_EVENTS.csv.gz"))
    inputs+=sorted((args.source/"semi/results_semi").glob("*EVENTS.csv.gz"))
    assert inputs
    needed=IDS+METRICS+[a+"_source_time_total_seconds" for a in "ABC"]
    needed += [f"endpoint_{a}__{f}" for a in "ABC" for f in ["time_source_kinds","source_time_known_n"]]
    data=[];manifest=[]
    for i,p in enumerate(inputs,1):
        d=pd.read_csv(p,usecols=lambda x:x in needed,low_memory=False)
        d["source_shard"]=str(p.relative_to(args.source));d["source_row_zero_based"]=np.arange(len(d))
        data.append(d);manifest.append({"source_shard":str(p.relative_to(args.source)),"rows":len(d),"bytes":p.stat().st_size})
        if i%30==0:print("read",i,"files",sum(len(x) for x in data),"rows",flush=True)
    d=pd.concat(data,ignore_index=True)
    assert not d.event_id.duplicated().any()
    for c in ["all_scored","all_complete","within_parent_fine_change","A_failure","B_failure","C_failure"]:d[c]=b(d[c])
    sets={}
    for c in ["A_member_workers","B_member_workers","C_member_workers","common_background","outgoing_block_X","same_count_block_Y","changed_count_block_Z"]:
        cache={s:mem(s) for s in d[c].dropna().unique()};sets[c]=d[c].map(cache)
    for a,z in [("A","B"),("A","C"),("B","C")]:
        d["actual_m_"+a+z]=[len(x-y) for x,y in zip(sets[a+"_member_workers"],sets[z+"_member_workers"])]
        assert d["actual_m_"+a+z].eq(d["m_"+a+z]).all()
    d["YZ_member_overlap"]=[len(x&y) for x,y in zip(sets["same_count_block_Y"],sets["changed_count_block_Z"])]
    d["design"]=np.where(d.YZ_member_overlap.gt(0),"legacy_YZ_overlap_ABC","strict_disjoint_ABC")
    ac,bc,cc=[d[c].map(counts) for c in ["composition_A","composition_B","composition_C"]]
    d["seat_change_r_AC"]=[sum(abs(x.get(k,0)-y.get(k,0)) for k in x.keys()|y.keys())/2 for x,y in zip(ac,cc)]
    d["seat_change_r_AB"]=[sum(abs(x.get(k,0)-y.get(k,0)) for k in x.keys()|y.keys())/2 for x,y in zip(ac,bc)]
    assert d.seat_change_r_AB.eq(0).all()
    d["parent_fixed"]=[x==y for x,y in zip(d.parent_composition_A.map(counts),d.parent_composition_C.map(counts))]
    assert (~d.tier.eq("fine")|d.parent_fixed.eq(d.within_parent_fine_change)).all()
    d["replacement_fraction_team"]=d.actual_m_AC/d.n
    d["category_fraction_team"]=d.seat_change_r_AC/d.n
    qvalid=d.all_scored
    for f in METRICS:
        d[f]=pd.to_numeric(d[f],errors="coerce")
        d.loc[~qvalid,f]=np.nan
    # Same/cross magnitudes are at equal m from A. C-B m remains explicit.
    d["symmetric_Q"]=.5*(d.cross_B8L2+d.net_B8L2)
    d["symmetric_cross_abs_Q"]=(d.cross_B8L2.abs()+d.net_B8L2.abs())/2
    d["symmetric_abs_Q_advantage"]=d.symmetric_cross_abs_Q-d.same_B8L2.abs()
    kinds=[d[f"endpoint_{a}__time_source_kinds"].fillna("").astype(str) for a in "ABC"]
    tok=kinds[0].eq(kinds[1])&kinds[0].eq(kinds[2])&kinds[0].ne("")&~kinds[0].str.contains("|",regex=False)
    for a in "ABC":tok &= pd.to_numeric(d[f"endpoint_{a}__source_time_known_n"]).eq(d.n)&pd.to_numeric(d[a+"_source_time_total_seconds"]).gt(0)
    d["time_three_source_compatible"]=tok
    for p,(a,z) in {"same":("A","B"),"cross":("A","C"),"net":("B","C")}.items():
        d[p+"_recorded_time_logratio"]=np.log(d[z+"_source_time_total_seconds"]/d[a+"_source_time_total_seconds"]).where(tok)
        d[p+"_loss_gt5"]=d[p+"_B8L2"].lt(-5).astype(float).where(qvalid)
    d["background_key"]=[hashlib.sha256((p+";"+"|".join(sorted(bg))).encode()).hexdigest()[:20] for p,bg in zip(d.pool_id,sets["common_background"])]
    metric=METRICS+["symmetric_Q","symmetric_cross_abs_Q","symmetric_abs_Q_advantage"]
    metric += [a+"_recorded_time_logratio" for a in ["same","cross","net"]]+[a+"_loss_gt5" for a in ["same","cross","net"]]+[a+"_failure" for a in "ABC"]
    # Three plans: full m/r response, same-m aggregate (m_BC disclosed), parent
    # fixed fine classes. No change to original class definition or labels.
    dims=["condition","method_id","tier","parent_fixed","design","n","actual_m_AB","actual_m_AC","actual_m_BC","seat_change_r_AC"]
    save(d[IDS+["source_shard","source_row_zero_based","actual_m_AB","actual_m_AC","actual_m_BC","YZ_member_overlap","design","seat_change_r_AC","parent_fixed","replacement_fraction_team","category_fraction_team","background_key"]].drop(columns=["all_scored","all_complete","A_failure","B_failure","C_failure"]),"EXACT_EVENT_LINKS.csv.gz")
    save(d[["event_id","all_scored","all_complete","time_three_source_compatible"]+metric],"EVENT_OUTCOMES.csv.gz")
    images=d.groupby(dims+["building","image","difficulty"],dropna=False)[metric].mean().reset_index()
    buildings=images.groupby(dims+["building"],dropna=False)[metric].mean().reset_index()
    save(images,"IMAGE_M_R_COMPARISON.csv.gz");save(buildings,"BUILDING_M_R_COMPARISON.csv.gz")
    # Exact source data are retained above. This broad response table does not
    # pretend that different image supports are a controlled m intervention.
    coarse=["condition","method_id","tier","parent_fixed","n","actual_m_AC"]
    im=d.groupby(coarse+["building","image"],dropna=False)[metric].mean().reset_index()
    bl=im.groupby(coarse+["building"],dropna=False)[metric].mean().reset_index()
    rows=[]
    for key,g in bl.groupby(coarse,dropna=False):
        r=dict(zip(coarse,key));sub=d;ims=im
        for f,v in r.items():sub=sub[sub[f].eq(v)];ims=ims[ims[f].eq(v)]
        r.update(g[metric].mean().to_dict());r.update(events=len(sub),images=sub.image.nunique(),buildings=sub.building.nunique(),
                physical_ABC=sub.physical_triple_id.nunique(),strict_disjoint_events=int(sub.design.eq("strict_disjoint_ABC").sum()),
                m_BC_min=sub.actual_m_BC.min(),m_BC_max=sub.actual_m_BC.max(),r_min=sub.seat_change_r_AC.min(),r_max=sub.seat_change_r_AC.max())
        for label,df in [("image",ims),("building",g)]:
            for metricname in ["abs_Q_change_advantage","net_B8L2","cross_B8L2","net_recorded_time_logratio"]:
                z=df[metricname].dropna();r[label+"_"+metricname+"_known"]=len(z);r[label+"_"+metricname+"_positive"]=int(z.gt(0).sum())
        for pre in ["same","cross","net"]:r[pre+"_recorded_time_pct"]=100*np.expm1(r[pre+"_recorded_time_logratio"])
        rows.append(r)
    save(pd.DataFrame(rows),"PARENT_FIXED_M_RESPONSE.csv")
    save(im,"IMAGE_PARENT_FIXED_M_RESPONSE.csv.gz");save(bl,"BUILDING_PARENT_FIXED_M_RESPONSE.csv.gz")
    save(pd.DataFrame(manifest),"SOURCE_SHARDS.csv")
    (OUT/"RECEIPT.json").write_text(json.dumps({"source_commit":"ef148c82df18582228b2d23837faa2659e79eba7","data":"real_v2",
        "rows":len(d),"by_condition":d.condition.value_counts().to_dict(),"source_shards":len(inputs),"new_fusion_calls":0,
        "primary_comparison":"same and cross relative to A have equal actual m; net C-B may have smaller m and is explicitly reported",
        "ranking_warning":"response m groups have different available image/support, not a controlled scale path",
        "support":"saved limited member panels, not all member sets in each feasible count vector"},ensure_ascii=False,indent=2)+"\n")
    print("saved",len(d),"events and",len(rows),"m/parent conditions",flush=True)


if __name__=="__main__":main()
