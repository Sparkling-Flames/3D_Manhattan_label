"""Populate missing expression fields from saved geometry; no fusion/scoring.

Only the three inherited expression diagnostics and their contrasts are changed.
Total scores, quality components, eligibility, labels and event sets are untouched.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from compare_saved_exchanges import HERE, INPUTS, sha

INPUT=HERE.parent/"inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz"
FIELDS=["fusion_turn_n","fusion_short_turn_edges","fusion_redundancy_n"]


def save(df,path):
    t=path.with_name(path.name+".tmp")
    df.to_csv(t,index=False,encoding="utf-8-sig",compression={"method":"gzip","compresslevel":3} if path.name.endswith(".gz") else None)
    t.replace(path)


def replace_columns(path,new,key):
    old=pd.read_csv(path,low_memory=False)
    fields=[f for f in new if f not in key]
    result=old.drop(columns=[f for f in fields if f in old]).merge(new,on=key,how="left",validate="one_to_one")
    assert len(result)==len(old)
    save(result,path)


def main():
    ep=pd.read_csv(INPUT).set_index("team_key")
    receipts=[]
    for name in INPUTS:
        folder=HERE/name
        d=pd.read_csv(folder/"EXACT_EVENT_LINKS.csv.gz",low_memory=False)
        valid=pd.read_csv(folder/"EVENT_OUTCOMES.csv.gz",usecols=["event_id","three_scores_available"])
        d=d.merge(valid,on="event_id",validate="one_to_one")
        o=pd.DataFrame({"event_id":d.event_id})
        for f in FIELDS:
            a,b,c=[pd.Series(ep[f].reindex(d["team_"+arm]).to_numpy(),index=d.index) for arm in "ABC"]
            good=d.three_scores_available&a.notna()&b.notna()&c.notna()
            for pre,v in [("same",b-a),("cross",c-a),("net",c-b),("symmetric",c-(a+b)/2),
                          ("within_abs",(b-a).abs()),("cross_abs",(c-a).abs()),
                          ("symmetric_cross_abs",((c-a).abs()+(c-b).abs())/2)]:o[pre+"_"+f]=v.where(good)
            o["abs_advantage_"+f]=o["symmetric_cross_abs_"+f]-o["within_abs_"+f]
        save(o,folder/"EVENT_EXPRESSION_SUPPLEMENT.csv.gz")
        replace_columns(folder/"EVENT_OUTCOMES.csv.gz",o,["event_id"])
        keys=["condition_id","pool_id","building","image","difficulty","source_class","target_class","background_key"]
        e=d.merge(o,on="event_id").drop_duplicates(["condition_id","actual_oriented_ABC"])
        metrics=[f for f in o if f!="event_id"]
        bg=e.groupby(keys,dropna=False)[metrics].mean().reset_index()
        cells=bg.groupby(keys[:-1],dropna=False)[metrics].mean().reset_index()
        images=cells.groupby(["condition_id","building","image","difficulty"],dropna=False)[metrics].mean().reset_index()
        buildings=images.groupby(["condition_id","building"],dropna=False)[metrics].mean().reset_index()
        for filename,frame,key in [("BACKGROUND_EFFECTS.csv.gz",bg,keys),("CLASS_PAIR_CELL_EFFECTS.csv.gz",cells,keys[:-1]),
                                   ("IMAGE_EFFECTS.csv.gz",images,["condition_id","building","image","difficulty"]),
                                   ("BUILDING_EFFECTS.csv.gz",buildings,["condition_id","building"])]:
            replace_columns(folder/filename,frame,key)
        sums=buildings.groupby("condition_id")[metrics].mean().reset_index()
        replace_columns(folder/"CONDITION_COMPARISON.csv",sums,["condition_id"])
        long=[]
        for cid,g in e.groupby("condition_id"):
            b=buildings[buildings.condition_id.eq(cid)];im=images[images.condition_id.eq(cid)];back=bg[bg.condition_id.eq(cid)]
            for metric in metrics:
                v=b[metric].dropna();iv=im[metric].dropna();bv=back[metric].dropna()
                long.append(dict(condition_id=cid,metric=metric,mean_building_equal=v.mean(),mean_image_equal=iv.mean(),
                    known_rows=int(g[metric].notna().sum()),known_backgrounds=len(bv),known_images=len(iv),known_buildings=len(v),
                    positive_backgrounds=int(bv.gt(0).sum()),negative_backgrounds=int(bv.lt(0).sum()),
                    positive_images=int(iv.gt(0).sum()),negative_images=int(iv.lt(0).sum()),zero_images=int(iv.eq(0).sum()),
                    positive_buildings=int(v.gt(0).sum()),negative_buildings=int(v.lt(0).sum()),
                    background_p10=bv.quantile(.1),background_p50=bv.median(),background_p90=bv.quantile(.9),image_sd=iv.std(),building_sd=v.std()))
        old=pd.read_csv(folder/"ALL_METRICS_DENOMINATORS.csv.gz")
        save(pd.concat([old[~old.metric.isin(metrics)],pd.DataFrame(long)],ignore_index=True),folder/"ALL_METRICS_DENOMINATORS.csv.gz")
        receipts.append({"batch":name,"events":len(o),"known_common_turn_events":int(o.net_fusion_turn_n.notna().sum())})
        print("expression saved",name,len(o),flush=True)
    for name,src in [("ALL_CONDITIONS.csv","CONDITION_COMPARISON.csv"),("ALL_CONDITION_METRICS.csv.gz","ALL_METRICS_DENOMINATORS.csv.gz"),
                     ("ALL_IMAGE_EFFECTS.csv.gz","IMAGE_EFFECTS.csv.gz"),("ALL_BUILDING_EFFECTS.csv.gz","BUILDING_EFFECTS.csv.gz"),
                     ("ALL_BACKGROUND_EFFECTS.csv.gz","BACKGROUND_EFFECTS.csv.gz")]:
        save(pd.concat([pd.read_csv(HERE/b/src,low_memory=False) for b in INPUTS],ignore_index=True),HERE/name)
    (HERE/"EXPRESSION_SUPPLEMENT_RECEIPT.json").write_text(json.dumps({"input":str(INPUT.relative_to(HERE.parents[3])),
        "input_sha256":sha(INPUT),"endpoint_keys":len(ep),"fields":FIELDS,"new_fusion_calls":0,"quality_or_labels_changed":False,
        "exact_geometry_rule":"inherited frozen expression routine: near-collinear <=5deg; short edges <4% perimeter; corners-minus-redundancy turns",
        "batches":receipts},ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":main()
