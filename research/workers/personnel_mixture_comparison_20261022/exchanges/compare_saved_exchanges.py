"""Unify ALL saved closure directions, scales and backgrounds; no fusion calls.

Real data v2. All labels, requests and endpoint values are inherited unchanged.
The output adds actual set-derived replacement sizes, exact count-vector changes,
all-direction comparisons and source/target member variability at fixed D.
Run from anywhere: python compare_saved_exchanges.py
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = ROOT / "research/workers/personnel_exchange_closure_20261022"
SCALAR = OLD / "delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz"
INPUTS = {
    "manual_joint_A": "manual_joint/EVENTS_REGISTERED.csv.gz",
    "manual_joint_B": "manual_joint/phase_b_highq_slower/EVENTS_REGISTERED.csv.gz",
    "manual_structure": "structure/ALL_EVENTS_REGISTERED.csv.gz",
    "semi_joint": "semi/EVENTS_REGISTERED_ALL.csv.gz",
}
COMPONENTS = [
    "B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter",
    "omission", "extension", "height_mean_ratio", "nodes", "ref_node_recall_9", "ref_edge_recall_9",
    "diag_wall_coverage_03", "diag_wall_coverage_05", "diag_corner_recall_05", "geometry_area_h2",
    "height_mean_h", "top_y_mean_px", "bottom_y_mean_px", "fusion_turn_n", "fusion_short_turn_edges",
    "fusion_redundancy_n", "minimum_support", "unselected_groups_n", "selected_support_min",
]
ENDPOINT_FIELDS = COMPONENTS + [
    "team_key", "pool_id", "k", "complete_evaluable", "score_status", "source_time_known_n",
    "source_time_total_seconds", "time_source_kinds", "member_workers", "centroid_x_h", "centroid_z_h",
]
CONDITION_FIELDS = ["analysis_batch", "method_id", "condition", "tier", "source_domain",
                    "study_group", "direction_role", "n", "actual_m_AB", "actual_m_AC", "actual_m_BC", "design"]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def save(df, name):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig", compression="gzip" if name.endswith(".gz") else None)
    tmp.replace(p)
    return str(p.relative_to(ROOT))


def bools(s):
    return s.astype(str).str.lower().eq("true")


def members(value):
    return frozenset(str(value).split("|")) if pd.notna(value) and str(value) else frozenset()


def counts(value):
    return {p.split(":")[0]: int(p.split(":")[1]) for p in str(value).split("|") if ":" in p}


def prepare_requests(name, path):
    d = pd.read_csv(path, low_memory=False).fillna("")
    d["analysis_batch"] = name
    if "study_group" not in d:
        d["study_group"] = d["stage"].replace({
            "closure_finite_reservoir": "all_registered_directions",
            "phase_b_selected_condition_new_backgrounds": "selected_Qmax_new_backgrounds",
            "semi_closure_source_partition_expansion": "source_partition_expansion",
            "semi_closure_configuration_completion": "configuration_completion",
        })
    if "training_QT_direction" in d:
        d["direction_role"] = d.training_QT_direction
        if name == "semi_joint":
            # Fold-local class IDs are NEVER pooled; semantics are history-defined.
            d["direction_role"] += np.where(pd.to_numeric(d.class_center_delta_turn_history) >= .25,
                                            "__more_turns", "__ordinary_expression")
    else:
        d["direction_role"] = d.source_semantics + "→" + d.target_semantics
    d["source_request_file"] = str(path.relative_to(ROOT))
    d["source_row_zero_based"] = np.arange(len(d))
    # Every member set is parsed once, not once per event occurrence.
    cache = {}
    for col in ["A_member_workers", "B_member_workers", "C_member_workers", "common_background",
                "outgoing_block_X", "same_count_block_Y", "changed_count_block_Z"]:
        for v in d[col].unique(): cache[v] = members(v)
    sets = {c: d[c].map(cache) for c in ["A_member_workers", "B_member_workers", "C_member_workers",
           "common_background", "outgoing_block_X", "same_count_block_Y", "changed_count_block_Z"]}
    for a, b in [("A", "B"), ("A", "C"), ("B", "C")]:
        d[f"actual_m_{a}{b}"] = [len(x-y) for x,y in zip(sets[a+"_member_workers"],sets[b+"_member_workers"])]
        assert np.all(d[f"actual_m_{a}{b}"] == pd.to_numeric(d[f"m_{a}{b}"]))
    d["actual_XY_overlap"] = [len(x&y) for x,y in zip(sets["outgoing_block_X"],sets["same_count_block_Y"])]
    d["actual_XZ_overlap"] = [len(x&y) for x,y in zip(sets["outgoing_block_X"],sets["changed_count_block_Z"])]
    d["actual_YZ_overlap"] = [len(x&y) for x,y in zip(sets["same_count_block_Y"],sets["changed_count_block_Z"])]
    d["background_member_count"] = sets["common_background"].map(len)
    strict = d[["actual_XY_overlap","actual_XZ_overlap","actual_YZ_overlap"]].eq(0).all(axis=1)
    d["design"] = np.where(strict, "strict_disjoint_ABC", "legacy_overlapping_blocks_ABC")
    acounts, bcounts, ccounts = [d[col].map(counts) for col in ["A_counts","B_counts","C_counts"]]
    d["source_class_count_A"] = [a.get(c,0) for a,c in zip(acounts,d.source_class)]
    d["source_class_count_D"] = d.source_class_count_A - d.actual_m_AC
    d["target_class_count_D"] = [a.get(c,0) for a,c in zip(acounts,d.target_class)]
    for label, left,right in [("AB",acounts,bcounts),("AC",acounts,ccounts),("BC",bcounts,ccounts)]:
        d["seat_change_r_"+label] = [.5*sum(abs(a.get(k,0)-b.get(k,0)) for k in a.keys()|b.keys()) for a,b in zip(left,right)]
    d["replace_fraction_team"] = d.actual_m_AC / pd.to_numeric(d.n)
    d["replace_fraction_source_in_A"] = d.actual_m_AC / d.source_class_count_A.replace(0,np.nan)
    # Normalize exact background, independent of legacy ID formats.
    d["background_key"] = [hashlib.sha256((p+";"+"|".join(sorted(s))).encode()).hexdigest()[:20]
                            for p,s in zip(d.pool_id,sets["common_background"])]
    d["condition_id"] = d[CONDITION_FIELDS].astype(str).agg(";".join,axis=1).map(
        lambda x: hashlib.sha256(x.encode()).hexdigest()[:20])
    # A physical ABC can be registered again on an n/m path. Keep every registered
    # row; independent exposure counts are computed using the actual endpoint sets.
    d["actual_physical_ABC"] = [hashlib.sha256((p+";"+";".join(sorted([a,b]))+";"+c).encode()).hexdigest()[:20]
                                for p,a,b,c in zip(d.pool_id,d.team_A,d.team_B,d.team_C)]
    d["actual_oriented_ABC"] = [hashlib.sha256((a+";"+b+";"+c).encode()).hexdigest()[:20]
                                for a,b,c in zip(d.team_A,d.team_B,d.team_C)]
    return d


def outcomes(d, ep):
    arms = {a: ep.reindex(d["team_"+a]).reset_index(drop=True) for a in "ABC"}
    assert all(x.team_key.notna().all() for x in arms.values()), "Requested endpoint missing"
    out = {"event_id":d.event_id, "actual_oriented_ABC":d.actual_oriented_ABC,
           "actual_physical_ABC":d.actual_physical_ABC,"condition_id":d.condition_id}
    complete = np.logical_and.reduce([bools(arms[a].complete_evaluable) for a in "ABC"])
    scored = np.logical_and.reduce([pd.to_numeric(arms[a].B8L2,errors="coerce").notna() for a in "ABC"])
    out["three_scores_available"] = scored
    out["three_complete_evaluable"] = complete
    source = [arms[a].time_source_kinds.fillna("").astype(str) for a in "ABC"]
    comparable = source[0].eq(source[1]) & source[0].eq(source[2]) & source[0].ne("") & ~source[0].str.contains("|",regex=False)
    for a,x in arms.items():
        assert x.k.astype(int).eq(d.n.astype(int)).all()
        comparable &= pd.to_numeric(x.source_time_known_n).eq(d.n.astype(int)) & pd.to_numeric(x.source_time_total_seconds).gt(0)
        out[a+"_failure"] = ~bools(x.complete_evaluable)
        out[a+"_score_status"] = x.score_status
        out[a+"_B8L2"] = pd.to_numeric(x.B8L2,errors="coerce")
        out[a+"_D10"] = pd.to_numeric(x.D10,errors="coerce")
        out[a+"_recorded_seconds"] = pd.to_numeric(x.source_time_total_seconds,errors="coerce")
    out["recorded_time_comparable"] = comparable
    out["recorded_time_source"] = source[0].where(comparable)
    for f in COMPONENTS:
        a,b,c = [pd.to_numeric(arms[t][f],errors="coerce") for t in "ABC"]
        valid = scored & a.notna() & b.notna() & c.notna()
        for pre,v in [("same",b-a),("cross",c-a),("net",c-b),("symmetric",c-(a+b)/2)]:
            out[pre+"_"+f] = v.where(valid)
        if f in ["B8L2","D10","nodes","fusion_turn_n","height_mean_h","top_y_mean_px","bottom_y_mean_px"]:
            out["within_abs_"+f] = (b-a).abs().where(valid)
            out["cross_abs_"+f] = (c-a).abs().where(valid)
            out["symmetric_cross_abs_"+f] = ((c-a).abs()+(c-b).abs()).div(2).where(valid)
            out["abs_advantage_"+f] = (out["symmetric_cross_abs_"+f]-out["within_abs_"+f]).where(valid)
    for pre,(aa,bb) in {"same":("A","B"),"cross":("A","C"),"net":("B","C")}.items():
        out[pre+"_recorded_time_logratio"] = np.log(out[bb+"_recorded_seconds"]/out[aa+"_recorded_seconds"]).where(comparable)
        out[pre+"_centroid_distance_h"] = np.hypot(
            pd.to_numeric(arms[bb].centroid_x_h,errors="coerce")-pd.to_numeric(arms[aa].centroid_x_h,errors="coerce"),
            pd.to_numeric(arms[bb].centroid_z_h,errors="coerce")-pd.to_numeric(arms[aa].centroid_z_h,errors="coerce")).where(complete)
        out[pre+"_area_abs_logratio"] = np.abs(np.log(
            pd.to_numeric(arms[bb].geometry_area_h2,errors="coerce")/pd.to_numeric(arms[aa].geometry_area_h2,errors="coerce"))).where(complete)
    out["symmetric_recorded_time_logratio"] = np.log(out["C_recorded_seconds"]/((out["A_recorded_seconds"]+out["B_recorded_seconds"])/2)).where(comparable)
    for f in ["centroid_distance_h","area_abs_logratio"]:
        out["symmetric_cross_"+f] = (out["cross_"+f]+out["net_"+f])/2
        out["abs_advantage_"+f] = out["symmetric_cross_"+f]-out["same_"+f]
    for pre in ["same","cross","net","symmetric"]:
        q=out[pre+"_B8L2"]
        for threshold in [1,5,10]: out[pre+f"_loss_gt{threshold}"] = q.lt(-threshold).astype(float).where(q.notna())
        out[pre+"_Q_up"] = q.gt(0).astype(float).where(q.notna())
        out[pre+"_time_down"] = out[pre+"_recorded_time_logratio"].lt(0).astype(float).where(comparable)
        out[pre+"_QT_both_improve"] = (q.gt(0)&out[pre+"_recorded_time_logratio"].lt(0)).astype(float).where(q.notna()&comparable)
    return pd.DataFrame(out)


def aggregate(d,o,name):
    # Registered path duplicates and A/B mirror rows are explicitly marked;
    # duplicates of the same oriented triple in a single condition count once.
    joined=d.merge(o,on=["event_id","actual_oriented_ABC","actual_physical_ABC","condition_id"],validate="one_to_one")
    joined=joined.drop_duplicates(["condition_id","actual_oriented_ABC"])
    numeric=[c for c in o if c not in ["event_id","actual_oriented_ABC","actual_physical_ABC","condition_id"]
             and pd.api.types.is_numeric_dtype(o[c]) and not c.endswith("_recorded_seconds") and c not in ["A_B8L2","B_B8L2","C_B8L2","A_D10","B_D10","C_D10"]]
    keys=["condition_id","pool_id","building","image","difficulty","source_class","target_class","background_key"]
    bg=joined.groupby(keys,dropna=False)[numeric].mean().reset_index()
    exposures=joined.groupby(keys,dropna=False).agg(registered_rows=("event_id","size"),physical_ABC=("actual_physical_ABC","nunique"),
        unique_A=("team_A","nunique"),unique_B=("team_B","nunique"),unique_C=("team_C","nunique"),
        target_class_count_D=("target_class_count_D","first"),source_class_count_D=("source_class_count_D","first"),
        source_class_count_A=("source_class_count_A","first"),replace_fraction_source_in_A=("replace_fraction_source_in_A","first"),
        background_members=("common_background","first")).reset_index()
    bg=bg.merge(exposures,on=keys,validate="one_to_one")
    cells=bg.groupby(keys[:-1],dropna=False)[numeric].mean().reset_index()
    ims=cells.groupby(["condition_id","building","image","difficulty"],dropna=False)[numeric].mean().reset_index()
    blds=ims.groupby(["condition_id","building"],dropna=False)[numeric].mean().reset_index()
    for frame,label in [(bg,"background"),(cells,"class_pair_cell"),(ims,"image"),(blds,"building")]:
        save(frame,f"{name}/{label.upper()}_EFFECTS.csv.gz")
    rows,long=[] ,[]
    for cid,g in joined.groupby("condition_id",sort=True):
        first=g.iloc[0]
        ib=ims[ims.condition_id.eq(cid)]; bb=blds[blds.condition_id.eq(cid)]; gb=bg[bg.condition_id.eq(cid)]
        row={f:first[f] for f in CONDITION_FIELDS}
        row.update(condition_id=cid, registered_rows=int(d.condition_id.eq(cid).sum()),unique_oriented_ABC=len(g),
                   physical_ABC=g.actual_physical_ABC.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
                   backgrounds=g[["pool_id","background_key"]].drop_duplicates().shape[0],fold_class_pairs=g[["pool_id","source_class","target_class"]].drop_duplicates().shape[0],
                   three_scored_rows=int(g.three_scores_available.sum()),time_comparable_rows=int(g.recorded_time_comparable.sum()),
                   seat_change_r_AC_min=g.seat_change_r_AC.min(),seat_change_r_AC_max=g.seat_change_r_AC.max(),
                   replacement_fraction_team=first.replace_fraction_team,
                   source_replaced_fraction_min=g.replace_fraction_source_in_A.min(),source_replaced_fraction_max=g.replace_fraction_source_in_A.max(),
                   target_in_background_min=g.target_class_count_D.min(),target_in_background_max=g.target_class_count_D.max(),
                   weighting="unique oriented ABC -> exact D -> fold class pair -> image -> building equal")
        for metric in numeric:
            values=bb[metric].dropna(); iv=ib[metric].dropna(); bv=gb[metric].dropna()
            row[metric]=values.mean()
            long.append(dict(condition_id=cid,metric=metric,mean_building_equal=values.mean(),mean_image_equal=iv.mean(),
                             known_rows=int(g[metric].notna().sum()),known_backgrounds=len(bv),known_images=len(iv),known_buildings=len(values),
                             positive_backgrounds=int(bv.gt(0).sum()),negative_backgrounds=int(bv.lt(0).sum()),
                             positive_images=int(iv.gt(0).sum()),negative_images=int(iv.lt(0).sum()),zero_images=int(iv.eq(0).sum()),
                             positive_buildings=int(values.gt(0).sum()),negative_buildings=int(values.lt(0).sum()),
                             background_p10=bv.quantile(.1),background_p50=bv.median(),background_p90=bv.quantile(.9),
                             image_sd=iv.std(),building_sd=values.std()))
        for pre in ["same","cross","net","symmetric"]:
            row[pre+"_recorded_time_pct"]=100*np.expm1(row[pre+"_recorded_time_logratio"])
        for level,frame in [("image",ib),("building",bb),("background",gb)]:
            for metric in ["net_B8L2","cross_B8L2","symmetric_B8L2","abs_advantage_B8L2","net_recorded_time_logratio"]:
                v=frame[metric].dropna();row[f"{level}_{metric}_positive"]=int(v.gt(0).sum());row[f"{level}_{metric}_negative"]=int(v.lt(0).sum());row[f"{level}_{metric}_known"]=len(v)
        for arm in "ABC":
            u=g[["team_"+arm,arm+"_failure"]].drop_duplicates()
            row[arm+"_unique_endpoints"]=len(u);row[arm+"_failed_unique_endpoints"]=int(u[arm+"_failure"].sum())
        pairs=g.drop_duplicates(["team_B","team_C"])
        row["distinct_BC_pairs"]=len(pairs);row["distinct_scored_BC_pairs"]=int(pairs.net_B8L2.notna().sum())
        for th in [5,10]:row[f"distinct_BC_net_loss_gt{th}"]=int(pairs.net_B8L2.lt(-th).sum())
        rows.append(row)
    save(pd.DataFrame(rows),f"{name}/CONDITION_COMPARISON.csv")
    save(pd.DataFrame(long),f"{name}/ALL_METRICS_DENOMINATORS.csv.gz")
    # Source and target variability are separate. A singleton C block is unknown,
    # NEVER reported as evidence of zero target-member variability.
    var=[]
    for key,g in joined.groupby(keys,dropna=False):
        row=dict(zip(keys,key)); row["physical_ABC"]=g.actual_physical_ABC.nunique()
        for arm,cols in [("source",[("team_A","A_B8L2"),("team_B","B_B8L2")]),("target",[("team_C","C_B8L2")])]:
            teams=pd.concat([g[[t,v]].rename(columns={t:"team",v:"Q"}) for t,v in cols]).drop_duplicates("team")
            vals=teams.Q.dropna();row[arm+"_teams"]=len(teams);row[arm+"_scored_teams"]=len(vals)
            row[arm+"_Q_sd"]=vals.std() if len(vals)>1 else np.nan
            row[arm+"_Q_range"]=vals.max()-vals.min() if len(vals)>1 else np.nan
            row[arm+"_Q_p10"]=vals.quantile(.1);row[arm+"_Q_p90"]=vals.quantile(.9)
        row["Q_net_min"]=g.net_B8L2.min();row["Q_net_max"]=g.net_B8L2.max()
        row["net_positive_fraction"]=g.net_B8L2.gt(0).where(g.net_B8L2.notna()).mean()
        var.append(row)
    save(pd.DataFrame(var),f"{name}/FIXED_BACKGROUND_MEMBER_VARIATION.csv.gz")
    return pd.DataFrame(rows),pd.DataFrame(long),ims,blds,bg


def main():
    ep=pd.read_csv(SCALAR,usecols=ENDPOINT_FIELDS,low_memory=False).set_index("team_key",drop=False)
    assert ep.index.is_unique
    expression=HERE.parent/"inputs/CLOSURE_ENDPOINT_EXPRESSIONS.csv.gz"
    if expression.exists():
        # These diagnostics were missing in the delivered scalar union. They
        # are derived from its exact saved geometry by the inherited routine.
        extra=pd.read_csv(expression).set_index("team_key")
        ep.update(extra[["fusion_turn_n","fusion_short_turn_edges","fusion_redundancy_n"]])
    receipt={"source_commit":"ef148c82df18582228b2d23837faa2659e79eba7","underlying_data_version":"real_v2",
             "endpoint_file":str(SCALAR.relative_to(ROOT)),"endpoint_sha256":sha(SCALAR),"endpoint_rows":len(ep),
             "new_fusion_calls":0,"new_scoring_calls":0,"batches":{}}
    if expression.exists():receipt["expression_input"]={"file":str(expression.relative_to(ROOT)),"sha256":sha(expression)}
    combined=[];metrics=[];images=[];buildings=[];backgrounds=[]
    for name,relative in INPUTS.items():
        path=OLD/relative
        d=prepare_requests(name,path)
        save(d,f"{name}/EXACT_EVENT_LINKS.csv.gz")
        o=outcomes(d,ep)
        save(o,f"{name}/EVENT_OUTCOMES.csv.gz")
        sums,long,im,bl,bg=aggregate(d,o,name)
        combined.append(sums);metrics.append(long);images.append(im);buildings.append(bl);backgrounds.append(bg)
        receipt["batches"][name]={"source":str(path.relative_to(ROOT)),"sha256":sha(path),"registered_rows":len(d),
                                  "physical_ABC":d.actual_physical_ABC.nunique(),"conditions":len(sums),"status":"saved"}
        (HERE/"STAGE_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
        save(pd.concat(combined,ignore_index=True),"ALL_CONDITIONS.csv")
        save(pd.concat(metrics,ignore_index=True),"ALL_CONDITION_METRICS.csv.gz")
        print(name,receipt["batches"][name],flush=True)
    save(pd.concat(images,ignore_index=True),"ALL_IMAGE_EFFECTS.csv.gz")
    save(pd.concat(buildings,ignore_index=True),"ALL_BUILDING_EFFECTS.csv.gz")
    save(pd.concat(backgrounds,ignore_index=True),"ALL_BACKGROUND_EFFECTS.csv.gz")
    (HERE/"METRIC_CONTRACT.json").write_text(json.dumps({
        "same":"B-A","cross":"C-A","net":"C-B","symmetric":"C-(A+B)/2",
        "within_abs":"abs(B-A)","cross_abs":"abs(C-A)","symmetric_cross_abs":"(abs(C-A)+abs(C-B))/2",
        "abs_advantage":"symmetric_cross_abs-within_abs; larger means cross-class changes more, not better",
        "quality_denominator":"Each metric observed at A,B,C AND all three Q available; failures preserved separately.",
        "geometric_distance_denominator":"Three complete endpoints; centroid and floor-area change, not reference error.",
        "time":"sum of existing per-response recorded seconds; all n known; same single time_source_kinds at A/B/C; log ratios aggregated then expm1; not newly measured production elapsed time",
        "weighting":"unique oriented ABC -> exact D -> fold-local source/target pair -> image -> building equal",
        "mirror_rows":"Semi A/B mirrors retained as orientations; physical counts and unique endpoints supplied; symmetric metric orientation-invariant",
        "unknown_variability":"Less than two scored source/target teams within fixed D => SD/range NA, not zero",
        "selection":"All saved closure directions and scales retained; class IDs joined only within target-building-excluded folds.",
        "failure":"1 - complete_evaluable; raw unique endpoint counts and event-referenced rates both supplied.",
    },ensure_ascii=False,indent=2)+"\n")


if __name__=="__main__":main()
