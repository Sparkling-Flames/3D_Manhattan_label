"""Exhaustive saved-endpoint pairs, matching actual shared background and m.

This is a paired-ensemble comparison, not a newly registered ABC experiment.
For each finite D+6/12 panel, enumerate every unordered team pair once. Compare
same versus different full class-count vectors only within the EXACT member
intersection (shared background) and the same actual replacement size m.
No new fusion; no favorable-composition selection; no pooling Manual/Semi effects.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
CONFIG=HERE.parent/"configurations"
OUT=HERE/"finite_pair_comparison"
OUT.mkdir(parents=True,exist_ok=True)
POP=np.array([int(i).bit_count() for i in range(4096)],dtype=np.int8)


def write(df,name):
    p=OUT/name;t=p.with_name(p.name+".tmp")
    df.to_csv(t,index=False,encoding="utf-8-sig",compression={"method":"gzip","compresslevel":3} if name.endswith(".gz") else None)
    t.replace(p)


def numeric(x): return pd.to_numeric(x,errors="coerce").to_numpy(float)


def metrics_for_pairs(ep,ii,jj):
    result={}
    quality_valid=np.isfinite(numeric(ep.B8L2))
    both=quality_valid[ii]&quality_valid[jj]
    for f in ["B8L2","D10","iou_2d","IoU3D100","S_bottom_deg","dir","Hmean","Hcenter",
              "omission","extension","nodes","fusion_turn_n","fusion_short_turn_edges","fusion_redundancy_n",
              "height_mean_h","height_mean_ratio","top_y_mean_px","bottom_y_mean_px","ref_node_recall_9","ref_edge_recall_9"]:
        x=numeric(ep[f]);diff=np.abs(x[jj]-x[ii]);diff[~both]=np.nan;result["abs_"+f]=diff
    t=numeric(ep.recorded_time_total_seconds);source=ep.time_source_kinds.fillna("").to_numpy(str)
    eligible=ep.recorded_time_eligible.astype(str).str.lower().eq("true").to_numpy()
    ok=eligible[ii]&eligible[jj]&(source[ii]==source[jj])&(t[ii]>0)&(t[jj]>0)
    with np.errstate(invalid="ignore",divide="ignore"):
        lt=np.abs(np.log(t[jj]/t[ii]));lt[~ok]=np.nan
    result["abs_recorded_logtime"]=lt
    for f in ["centroid_x_h","centroid_z_h"]:
        x=numeric(ep[f]);result[f]=x[jj]-x[ii]
    result["centroid_distance_h"]=np.hypot(result.pop("centroid_x_h"),result.pop("centroid_z_h"))
    result["centroid_distance_h"][~both]=np.nan
    a=numeric(ep.geometry_area_h2)
    with np.errstate(divide="ignore",invalid="ignore"):
        v=np.abs(np.log(a[jj]/a[ii]));v[~both]=np.nan;result["abs_logarea"]=v
    fail=ep.failure.astype(str).str.lower().eq("true").to_numpy()
    result["any_endpoint_failure"]=(fail[ii]|fail[jj]).astype(float)
    result["exactly_one_endpoint_failure"]=(fail[ii]!=fail[jj]).astype(float)
    result["both_endpoint_failure"]=(fail[ii]&fail[jj]).astype(float)
    return result


def sum_count(code,values,size):
    valid=np.isfinite(values)
    return np.bincount(code[valid],weights=values[valid],minlength=size),np.bincount(code[valid],minlength=size)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--condition",choices=["manual","semi"],required=True);args=ap.parse_args()
    panels=pd.read_csv(CONFIG/"PANELS_USED.csv");panels=panels[panels.condition.eq(args.condition)]
    teams=pd.read_csv(CONFIG/"PANEL_TEAMS.csv.gz")
    links=pd.read_csv(CONFIG/"TEAM_CONFIGURATION_LINKS.csv.gz")
    census=pd.read_csv(CONFIG/"PANEL_CONFIGURATION_CENSUS.csv.gz")
    ep=pd.read_csv(CONFIG/f"ENDPOINT_OUTCOMES_{args.condition}.csv.gz",low_memory=False).set_index("team_key",drop=False)
    descriptions=census.set_index("configuration_id").class_counts.map(json.loads).to_dict()
    panelmap={p:g for p,g in teams.groupby("panel_id")}
    linkmap={(p,m):g for (p,m),g in links.groupby(["panel_id","method"])}
    summaries=[];responses=[];coverage=[];background_chunks=[]
    for pi,panel in enumerate(panels.itertuples(index=False),1):
        pteam=panelmap[panel.panel_id].sort_values("team_key").reset_index(drop=True)
        assert len(pteam)==924 and pteam.team_key.is_unique
        variables=str(panel.variable_workers).split("|");vi={w:i for i,w in enumerate(variables)}
        masks=np.array([sum(1<<vi[w] for w in value.split("|")) for value in pteam.selected_variable_workers],dtype=np.uint16)
        assert len(set(masks))==924 and np.all(POP[masks]==6)
        ii,jj=np.triu_indices(len(pteam),1)
        shared=masks[ii]&masks[jj]
        ms=6-POP[shared]
        endpoints=ep.reindex(pteam.team_key).reset_index(drop=True)
        assert endpoints.team_key.notna().all()
        pairmetrics=metrics_for_pairs(endpoints,ii,jj)
        base=dict(panel_id=panel.panel_id,pool_id=panel.pool_id,image=panel.image,building=panel.building,
                  condition=panel.condition,difficulty=panel.difficulty,n=int(panel.n),source_domain=panel.source_domain)
        for method in ["V3_BEHAVIOR","V3_JOINT_QT"]:
            lk=linkmap.get((panel.panel_id,method))
            if lk is None:continue
            vectors={};valids={};configuration_codes={};configuration_names={}
            for tier in ["coarse","fine"]:
                x=lk[lk.tier.eq(tier)].set_index("team_key").configuration_id.reindex(pteam.team_key)
                known=x.notna().to_numpy();valids[tier]=known[ii]&known[jj]
                codes,names=pd.factorize(x,sort=True)
                configuration_codes[tier]=codes;configuration_names[tier]=np.asarray(names)
                d=[descriptions.get(k,{}) for k in x];classes=sorted(set().union(*(z.keys() for z in d)))
                mat=np.array([[z.get(c,0) for c in classes] for z in d],dtype=np.int16)
                vectors[tier]=(np.abs(mat[ii]-mat[jj]).sum(axis=1)//2).astype(np.int8)
            for view in ["coarse","fine_all_changes","fine_parent_fixed"]:
                tier="coarse" if view=="coarse" else "fine"
                r=vectors[tier];valid=valids[tier].copy()
                if view=="fine_parent_fixed":valid &= valids["coarse"]&(vectors["coarse"]==0)
                kept=np.flatnonzero(valid);r0=r[kept];m0=ms[kept];d0=shared[kept]
                changed=r0>0
                # The fine increment also holds the WHOLE coarse count vector
                # fixed ACROSS the two pair ensembles, not merely inside each
                # pair. Thus each stratum is exact D (+coarse vector if fine).
                raw=d0.astype(np.int64)
                if view=="fine_parent_fixed":
                    raw+=(configuration_codes["coarse"][ii[kept]]+1)*4096
                strata,inverse=np.unique(raw,return_inverse=True)
                stratum_masks=(strata%4096).astype(int)
                stratum_m=6-POP[stratum_masks]
                code=inverse*2+changed.astype(int)
                design_count=np.bincount(code,minlength=2*len(strata)).reshape(-1,2)
                detail=pd.DataFrame({"variable_background_mask":stratum_masks,"actual_m":stratum_m,
                                     "same_vector_pairs":design_count[:,0],"changed_vector_pairs":design_count[:,1]})
                for f,value in {**base,"method":method,"classification_view":view}.items():detail[f]=value
                if view=="fine_parent_fixed":
                    detail["fixed_parent_configuration_id"]=configuration_names["coarse"][(strata//4096-1).astype(int)]
                else:detail["fixed_parent_configuration_id"]=""
                detail["stratum_has_both_relations"]=(design_count[:,0]>0)&(design_count[:,1]>0)
                for m in range(1,7):
                    ds=np.flatnonzero(stratum_m==m)
                    cnt=design_count[ds];validbg=(cnt[:,0]>0)&(cnt[:,1]>0)
                    coverage.append({**base,"method":method,"classification_view":view,"actual_m":m,
                        "replacement_fraction_team":m/int(panel.n),"possible_unordered_pairs_in_original_panel":math.comb(924,2),
                        "known_label_pair_rows":int(np.sum(m0==m)),"same_vector_pairs":int(cnt[:,0].sum()),
                        "changed_vector_pairs":int(cnt[:,1].sum()),"all_exact_backgrounds":int((cnt.sum(axis=1)>0).sum()),
                        "backgrounds_with_both_relations":int(validbg.sum()),"matched_same_pairs":int(cnt[validbg,0].sum()),
                        "matched_changed_pairs":int(cnt[validbg,1].sum()),"full_unordered_pair_enumeration":True,
                        "background_count_is_D_plus_parent_vector":view=="fine_parent_fixed",
                        "design":"matched_pair_ensembles_at_exact_shared_D_and_m"})
                for metric,allv in pairmetrics.items():
                    v=allv[kept];sums,counts=sum_count(code,v,2*len(strata))
                    sums=sums.reshape(-1,2);counts=counts.reshape(-1,2)
                    with np.errstate(invalid="ignore",divide="ignore"):means=sums/counts
                    if metric in ["abs_B8L2","abs_D10","abs_fusion_turn_n","abs_recorded_logtime","any_endpoint_failure"]:
                        for ai,arm in enumerate(["same","changed"]):
                            detail[f"{metric}_{arm}_mean"]=means[:,ai]
                            detail[f"{metric}_{arm}_pairs"]=counts[:,ai]
                    for m in range(1,7):
                        ds=np.flatnonzero(stratum_m==m);c=counts[ds];mu=means[ds]
                        matched=(c[:,0]>0)&(c[:,1]>0)
                        delta=mu[matched,1]-mu[matched,0]
                        row={**base,"method":method,"classification_view":view,"actual_m":m,"metric":metric,
                             "matched_backgrounds":int(matched.sum()),"matched_same_pairs":int(c[matched,0].sum()),
                             "matched_changed_pairs":int(c[matched,1].sum()),
                             "same_mean":float(mu[matched,0].mean()) if matched.any() else np.nan,
                             "changed_mean":float(mu[matched,1].mean()) if matched.any() else np.nan,
                             "changed_minus_same":float(delta.mean()) if len(delta) else np.nan,
                             "background_changed_larger":int(np.sum(delta>0)),"background_changed_smaller":int(np.sum(delta<0)),
                             "background_equal":int(np.sum(delta==0)),"delta_p10":np.quantile(delta,.1) if len(delta) else np.nan,
                             "delta_p90":np.quantile(delta,.9) if len(delta) else np.nan,
                             "unmatched_all_same_mean":sums[ds,0].sum()/c[:,0].sum() if c[:,0].sum() else np.nan,
                             "unmatched_all_changed_mean":sums[ds,1].sum()/c[:,1].sum() if c[:,1].sum() else np.nan}
                        summaries.append(row)
                    # Exact replacement m and category seats r form separate axes.
                    mr=m0.astype(np.int64)*7+r0.astype(int)
                    ss,cc=sum_count(mr,v,49)
                    for m in range(1,7):
                        for seat in range(m+1):
                            k=m*7+seat
                            if cc[k]:responses.append({**base,"method":method,"classification_view":view,"actual_m":m,
                                                       "seat_change_r":seat,"metric":metric,"pair_count":int(cc[k]),"mean":ss[k]/cc[k]})
                background_chunks.append(detail)
        if pi%10==0 or pi==len(panels):
            write(pd.DataFrame(summaries),f"{args.condition}_PANEL_MATCHED_PAIR_METRICS.csv.gz")
            write(pd.DataFrame(coverage),f"{args.condition}_PAIR_COVERAGE.csv.gz")
            write(pd.DataFrame(responses),f"{args.condition}_M_R_RESPONSE.csv.gz")
            if background_chunks:
                write(pd.concat(background_chunks,ignore_index=True),f"{args.condition}_BACKGROUND_STRATA_{pi:03d}.csv.gz")
                background_chunks=[]
            print(args.condition,pi,"of",len(panels),"saved",flush=True)
    result=pd.DataFrame(summaries)
    metrics=["same_mean","changed_mean","changed_minus_same"]
    group=["condition","method","classification_view","n","actual_m","metric"]
    ims=result.groupby(group+["building","image","difficulty"],dropna=False)[metrics].mean().reset_index()
    bs=ims.groupby(group+["building"],dropna=False)[metrics].mean().reset_index()
    write(ims,f"{args.condition}_IMAGE_COMPARISON.csv.gz");write(bs,f"{args.condition}_BUILDING_COMPARISON.csv.gz")
    means=bs.groupby(group,dropna=False)[metrics].mean().reset_index()
    bcounts=bs.groupby(group,dropna=False).agg(known_buildings=("changed_minus_same","count"),
        changed_larger_buildings=("changed_minus_same",lambda x:int(x.gt(0).sum())),
        changed_smaller_buildings=("changed_minus_same",lambda x:int(x.lt(0).sum()))).reset_index()
    icounts=ims.groupby(group,dropna=False).agg(known_images=("changed_minus_same","count"),
        changed_larger_images=("changed_minus_same",lambda x:int(x.gt(0).sum())),
        changed_smaller_images=("changed_minus_same",lambda x:int(x.lt(0).sum()))).reset_index()
    output=means.merge(bcounts,on=group).merge(icounts,on=group)
    write(output,f"{args.condition}_SUMMARY.csv")
    (OUT/f"{args.condition}_RECEIPT.json").write_text(json.dumps({"panels_evaluated":len(panels),
        "unordered_pair_exposures_before_label_masks":int(len(panels)*math.comb(924,2)),"new_fusion_calls":0,
        "design":"complete unordered pairs within each saved 12-choose-6 panel, exact intersection/background matched",
        "unknown_labels":"omitted explicitly by existing configuration links; all known-label pairs enumerated",
        "independence":"pairs reuse endpoints; images/buildings are support; no pair-count significance tests",
        "aggregation":"within exact D and m separate same/changed pair means -> matched D equal -> panel -> image -> building equal",
        "pair_orientation":"unordered absolute differences, no artificial signed effect from lexicographic order",
        "fine_increment":"fine_parent_fixed holds the identical full coarse count vector across same/different fine-vector ensembles, within exact D and m",
        "fine_parent_stratification_version":2,
        "background_details":"BACKGROUND_STRATA shards preserve every D/m (and coarse vector for fine increment) with all pair counts and core quality/time/structure differences; variable mask is decoded against PANELS_USED.variable_workers",
        "data_version":"real_v2","source_commit":"ef148c82df18582228b2d23837faa2659e79eba7"},ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":main()
