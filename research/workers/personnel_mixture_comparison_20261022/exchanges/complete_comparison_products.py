"""Finish small comparison products from saved stages, without rescoring."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from compare_saved_exchanges import HERE,OLD,save,CONDITION_FIELDS,INPUTS


def main():
    conditions=pd.read_csv(HERE/"ALL_CONDITIONS.csv")
    common=[];variations=[]
    for name in INPUTS:
        links=pd.read_csv(HERE/name/"EXACT_EVENT_LINKS.csv.gz",low_memory=False)
        fields=["event_id","three_scores_available","recorded_time_comparable"]
        fields += [p+"_"+m for p in ["same","cross","net","symmetric"] for m in ["B8L2","D10","recorded_time_logratio"]]
        outcomes=pd.read_csv(HERE/name/"EVENT_OUTCOMES.csv.gz",usecols=fields)
        joint=links.merge(outcomes,on="event_id",validate="one_to_one")
        good=joint.three_scores_available & joint.recorded_time_comparable
        j=joint[good].drop_duplicates(["condition_id","actual_oriented_ABC"])
        keys=["condition_id","pool_id","building","image","source_class","target_class","background_key"]
        metric=[x for x in fields if x not in ["event_id","three_scores_available","recorded_time_comparable"]]
        bg=j.groupby(keys,dropna=False)[metric].mean().reset_index()
        cells=bg.groupby(keys[:-1],dropna=False)[metric].mean().reset_index()
        im=cells.groupby(["condition_id","building","image"],dropna=False)[metric].mean().reset_index()
        bl=im.groupby(["condition_id","building"],dropna=False)[metric].mean().reset_index()
        for cid,g in bl.groupby("condition_id"):
            x=j[j.condition_id.eq(cid)];i=im[im.condition_id.eq(cid)]
            row={"condition_id":cid,"joint_common_rows":len(x),"joint_common_images":i.image.nunique(),"joint_common_buildings":len(g)}
            row.update(g[metric].mean().to_dict())
            for p in ["same","cross","net","symmetric"]:
                row[p+"_recorded_time_pct"]=100*np.expm1(row[p+"_recorded_time_logratio"])
                row[p+"_Q_up_images"]=int(i[p+"_B8L2"].gt(0).sum())
                row[p+"_Q_up_buildings"]=int(g[p+"_B8L2"].gt(0).sum())
                row[p+"_time_down_images"]=int(i[p+"_recorded_time_logratio"].lt(0).sum())
                row[p+"_time_down_buildings"]=int(g[p+"_recorded_time_logratio"].lt(0).sum())
            common.append(row)
        variation=pd.read_csv(HERE/name/"FIXED_BACKGROUND_MEMBER_VARIATION.csv.gz")
        for cid,g in variation.groupby("condition_id"):
            row={"condition_id":cid,"fixed_background_class_pairs":len(g)}
            for arm in ["source","target"]:
                v=g[g[arm+"_scored_teams"].gt(1)]
                row[arm+"_replicated_backgrounds"]=len(v)
                row[arm+"_singleton_or_unscored_backgrounds"]=len(g)-len(v)
                row[arm+"_max_unique_teams"]=g[arm+"_teams"].max()
                if len(v):
                    ims=v.groupby(["building","image"])[[arm+"_Q_sd",arm+"_Q_range"]].mean()
                    bs=ims.groupby("building").mean()
                    row[arm+"_replicated_images"]=len(ims);row[arm+"_replicated_buildings"]=len(bs)
                    row.update({k+"_building_equal":value for k,value in bs.mean().items()})
            variations.append(row)
    meta=conditions[["condition_id"]+CONDITION_FIELDS]
    save(meta.merge(pd.DataFrame(common),on="condition_id",how="left"),"COMMON_QT_CONDITIONS.csv")
    save(meta.merge(pd.DataFrame(variations),on="condition_id",how="left"),"TARGET_AND_SOURCE_MEMBER_VARIATION.csv")
    # Preserve large combinatorial capacities as source strings, avoiding float
    # rounding of integer spaces > 2**53. Stage and overlapping capacity scopes
    # remain separate and must not be summed as independent universe sizes.
    capacity=[]
    for stage,path in [
        ("manual_joint_A",OLD/"manual_joint/CAPACITY_ALL_N_M.csv.gz"),
        ("manual_joint_B",OLD/"manual_joint/phase_b_highq_slower/CAPACITY.csv"),
        ("manual_structure",OLD/"structure/CAPACITY_AND_COVERAGE.csv.gz"),
        ("semi_joint",OLD/"semi/CAPACITY_ALL_ATTEMPTS.csv")]:
        c=pd.read_csv(path,dtype=str,keep_default_na=False);c.insert(0,"analysis_batch",stage)
        c.insert(1,"source_capacity_file",str(path.relative_to(HERE.parents[3])));capacity.append(c)
    save(pd.concat(capacity,ignore_index=True),"ALL_FEASIBLE_CAPACITY_AND_REGISTRATION.csv.gz")
    # Selection is a transparent interpretation aid. It never removes rows from
    # complete comparisons and it is not an optimization trained on new data.
    choice=conditions[["condition_id"]+CONDITION_FIELDS+["images","buildings","net_B8L2","cross_B8L2","within_abs_B8L2","symmetric_cross_abs_B8L2","net_recorded_time_pct","image_net_B8L2_positive","image_net_B8L2_negative","image_net_B8L2_known","building_net_B8L2_positive","building_net_B8L2_known","A_failed_unique_endpoints","B_failed_unique_endpoints","C_failed_unique_endpoints","A_unique_endpoints","B_unique_endpoints","C_unique_endpoints"]].copy()
    def use(r):
        majority=r.image_net_B8L2_positive>r.image_net_B8L2_known/2
        negative=r.image_net_B8L2_negative>r.image_net_B8L2_known/2 and r.net_B8L2<0
        known=r.image_net_B8L2_known
        if known<5:return "补充：容量或图片支持较小，保留方向和几何/时间作用"
        if majority and r.net_B8L2>1 and r.net_recorded_time_pct<0:return "重点：多数图片定向升质与记录时间收益"
        if majority and r.net_B8L2>1:return "重点：定向质量/结构改变；时间按同源子集说明"
        if negative:return "重点对照：多数图片负向，说明换类风险/取舍"
        if r.net_recorded_time_pct<-3:return "效率用途；质量均值、正向比例与尾部单独报告"
        if abs(r.net_B8L2)<1:return "补充：总体Q变化较小，关注局部/几何或成员波动"
        return "补充：均值与多数方向不一致，保留异质性"
    choice["interpretive_selection"]=choice.apply(use,axis=1)
    choice["selection_stage"]="posthoc internal descriptive comparison; no conditions deleted"
    save(choice,"ALL_CONDITIONS_SELECTION_REASONS.csv")
    print("saved common QT, target variability, capacities and all-condition selection",flush=True)


if __name__=="__main__":main()
