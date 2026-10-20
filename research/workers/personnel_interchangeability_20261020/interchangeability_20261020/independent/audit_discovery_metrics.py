"""Read-only sensitivity audit of frozen forward/reverse discovery metrics.

Scientific files and classifications are never edited. Actual unordered
pool/reference/team pairs are deduplicated, including duplicates across
classification methods and routes. Native final outputs can be re-evaluated by
the frozen pair API without rerunning fusion or scoring.
"""
from __future__ import annotations
import os
for _v in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):os.environ[_v]="1"
import argparse,gzip,hashlib,json,math,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"analysis/composition"))
sys.path.insert(0,str(Path(__file__).parent/"baseline"))
import fusion_runner as fr
import pair_diagnostics as px
import design_baseline as bd

META=["event_id","phase","method_id","domain","direction","pool_id","reference_id","building","image","difficulty","layer","condition","n","m"]
SYMMETRIC=["both_complete","abs_B8L2_change","abs_D10_change","floor_jaccard_difference","structure_bound_cyclic_deg","node_count_difference","mean_height_prism_pair_iou","height_ratio_pair_abs_logdiff"]+[p+q for p in ("joint_stable_","geometry_noQ_","geometry_shape_") for q in ("strict","main","wide")]+["wall_coverage_symmetric_min_main","true_corner_F1_main","true_corner_count_difference","boundary_distance_normalized_p95","boundary_distance_normalized_max","bottom_y_absdiff_deg_p95","bottom_y_absdiff_deg_max","top_y_absdiff_deg_p95","top_y_absdiff_deg_max","radius_abs_logratio_p95","boundary_total_height_abs_logratio_p95","exact_flat_prism_pair_iou","geometry_shape_main_and_prism_proxy_iou_lt_095","different_original_nodes_shape_main_passes"]
KEY=["pool_id","reference_id","team_lo","team_hi"]


def clean(x):return px._clean(x)


def state(value):
    return np.where(value.ge(2),"improve_ge2",np.where(value.le(-2),"worsen_ge2",np.where(value.notna(),"within2","missing")))


def load_route(route,folder):
    path=folder/(route+"_metrics/event_metrics.csv.gz")
    head=pd.read_csv(path,nrows=0)
    columns=set(META+[a+"_team_key" for a in "ABC"]+[a+"_"+m for a in "ABC" for m in ("B8L2","D10","complete","score_status","nodes")])
    columns.update(p+"_"+m for p in ("within","cross") for m in SYMMETRIC)
    D=pd.read_csv(path,usecols=lambda c:c in columns)
    geometry=[];quality=[]
    for role,left,right in (("within","A","B"),("cross","A","C"),("net","B","C")):
        P=D[META].copy();P["route"]=route;P["role"]=role
        order=D[left+"_team_key"].le(D[right+"_team_key"])
        P["team_lo"]=np.where(order,D[left+"_team_key"],D[right+"_team_key"])
        P["team_hi"]=np.where(order,D[right+"_team_key"],D[left+"_team_key"])
        for score in ("B8L2","D10","nodes"):
            P[score+"_lo"]=np.where(order,D[left+"_"+score],D[right+"_"+score]);P[score+"_hi"]=np.where(order,D[right+"_"+score],D[left+"_"+score])
            P[score+"_change"]=P[score+"_hi"]-P[score+"_lo"]
        P["both_complete"]=D[left+"_complete"]&D[right+"_complete"]
        P["status_lo"]=np.where(order,D[left+"_score_status"],D[right+"_score_status"])
        P["status_hi"]=np.where(order,D[right+"_score_status"],D[left+"_score_status"])
        P["deferred"]=P.status_lo.eq("two_person_deferred")|P.status_hi.eq("two_person_deferred")
        quality.append(P.copy())
        if role!="net":
            for metric in SYMMETRIC:
                source=role+"_"+metric
                if source in D:
                    if metric=="both_complete":assert (P[metric]==D[source]).all()
                    else:P[metric]=D[source]
                else:P[metric]=np.nan
            geometry.append(P)
    return pd.concat(geometry,ignore_index=True),pd.concat(quality,ignore_index=True),dict(route=route,event_file=str(path.relative_to(ROOT)),event_sha256=bd.sha(path),event_rows=len(D),event_ids=D.event_id.nunique(),images=D.image.nunique(),pools=D.pool_id.nunique(),buildings=D.building.nunique(),phases=sorted(D.phase.unique().tolist()),summary_sha256=bd.sha(folder/(route+"_metrics/SUMMARY_RECEIPT.json")))


def verify_repeated(P,fields):
    repeated=P[P.duplicated(KEY,keep=False)].copy();bad=[];maxerr=0.
    if not len(repeated):return dict(duplicate_occurrences=0,distinct_duplicated_pairs=0,max_absolute_difference=0.,mismatch_fields=[])
    for col in fields:
        if col not in repeated:continue
        x=pd.to_numeric(repeated[col],errors="coerce").astype(float)
        g=repeated[KEY].copy();g["x"]=x
        agg=g.groupby(KEY).x.agg(["min","max","count","size"])
        missing=agg["count"].gt(0)&agg["count"].lt(agg["size"])
        diff=agg["max"]-agg["min"];err=float(diff.max()) if diff.notna().any() else 0.;maxerr=max(maxerr,err)
        if missing.any() or diff.gt(1e-10).any():bad.append(dict(field=col,mixed_missing_pairs=int(missing.sum()),numeric_mismatches=int(diff.gt(1e-10).sum()),max_absolute_difference=err))
    return dict(duplicate_occurrences=len(repeated),distinct_duplicated_pairs=repeated[KEY].drop_duplicates().shape[0],max_absolute_difference=maxerr,mismatch_fields=bad)


def support(g):
    return dict(pairs=len(g),images=g.image.nunique(),pools=g.pool_id.nunique(),buildings=g.building.nunique(),finite_Q_pairs=int(g.B8L2_change.notna().sum()),both_complete_pairs=int(g.both_complete.sum()),deferred_pairs=int(g.deferred.sum()))


def masks(g):
    main=g.joint_stable_main.eq(True);noq=g.geometry_noQ_main.eq(True);shape=g.geometry_shape_main.eq(True)
    return {
      "main_pass":main,"noQ_pass":noq,"shape_pass":shape,
      "main_fail_noQ_pass":~main&noq,
      "main_pass_noQ_fail":main&~noq,
      "noQ_fail_shape_pass":~noq&shape,
      "noQ_pass_shape_fail":noq&~shape,
      "main_fail_shape_pass":~main&shape,
      "different_original_nodes_shape_pass":shape&g.node_count_difference.ne(0),
      "same_original_nodes_noQ_fail_shape_pass":shape&~noq&g.node_count_difference.eq(0),
      "shape_pass_prism_proxy_below_095":shape&g.mean_height_prism_pair_iou.lt(.95),
      "shape_pass_prism_proxy_below_090":shape&g.mean_height_prism_pair_iou.lt(.90),
      "shape_pass_bottom_max_gt3deg":shape&g.bottom_y_absdiff_deg_max.gt(3),
      "shape_pass_top_max_gt3deg":shape&g.top_y_absdiff_deg_max.gt(3),
      "shape_pass_boundary_height_p95_ratio_gt1p1":shape&g.boundary_total_height_abs_logratio_p95.gt(math.log(1.1)),
      "noQ_pass_bottom_p95_gt3deg":noq&g.bottom_y_absdiff_deg_p95.gt(3),
      "noQ_pass_top_p95_gt3deg":noq&g.top_y_absdiff_deg_p95.gt(3),
      "noQ_pass_shape_wall_coverage_below_095":noq&g.wall_coverage_symmetric_min_main.lt(.95),
      "noQ_pass_shape_true_corner_F1_below_095":noq&g.true_corner_F1_main.lt(.95),
      "exact_flat_prism_identified":g.exact_flat_prism_pair_iou.notna(),
    }


def summarize_flags(P):
    conf=[];flags=[]
    scopes=[("combined","all",P)]
    scopes += [("route",v,g) for v,g in P.groupby("route")]
    scopes += [("role",v,g) for v,g in P.groupby("role")]
    scopes += [("layer",v,g) for v,g in P.groupby("layer")]
    scopes += [("difficulty",v,g) for v,g in P.groupby("difficulty")]
    for typ,name,G in scopes:
        g=G.drop_duplicates(KEY);r=dict(scope=typ,value=name,**support(g))
        for pattern,z in g.groupby(["joint_stable_main","geometry_noQ_main","geometry_shape_main"],dropna=False):
            conf.append(dict(r,legacy_main=pattern[0],legacy_noQ_main=pattern[1],new_shape_main=pattern[2],pattern_pairs=len(z),pattern_images=z.image.nunique(),pattern_buildings=z.building.nunique()))
        for label,mask in masks(g).items():
            z=g[mask];balanced=float(g.assign(flag=mask.to_numpy(float)).groupby(["building","image"]).flag.mean().groupby("building").mean().mean())
            flags.append(dict(r,flag=label,flag_pairs=len(z),flag_images=z.image.nunique(),flag_buildings=z.building.nunique(),raw_pair_fraction=float(mask.mean()),equal_image_building_fraction=balanced))
    return conf,flags


def quality_summary(Q):
    rows=[]
    for typ,name,G in [("combined","all",Q)]+[("route",v,g) for v,g in Q.groupby("route")]+[("role",v,g) for v,g in Q.groupby("role")]:
        g=G.drop_duplicates(KEY).copy();g["B8_state"]=state(g.B8L2_change);g["D10_state"]=state(g.D10_change)
        for (s1,s2),z in g.groupby(["B8_state","D10_state"]):
            rows.append(dict(scope=typ,value=name,**support(g),B8_state=s1,D10_state=s2,direction_pairs=len(z),direction_images=z.image.nunique(),direction_buildings=z.building.nunique()))
    return rows


def pick_examples(G,Q):
    selected=[]
    categories=[("different_original_nodes_shape_pass","floor_jaccard_difference",True),
      ("noQ_fail_shape_pass","node_count_difference",False),
      ("noQ_pass_shape_fail","bottom_y_absdiff_deg_p95",False),
      ("shape_pass_prism_proxy_below_095","mean_height_prism_pair_iou",True),
      ("shape_pass_bottom_max_gt3deg","bottom_y_absdiff_deg_max",False),
      ("main_fail_noQ_pass","abs_B8L2_change",False)]
    flags=masks(G)
    for label,rank,asc in categories:
        eligible=G[flags[label]].sort_values([rank,"pool_id","team_lo","team_hi"],ascending=[asc,True,True,True])
        for _,row in eligible.drop_duplicates("image").head(2).iterrows():
            selected.append(dict(category=label,eligible_distinct_pairs=len(eligible),ranking=rank,ascending=asc,pair=row.to_dict()))
    opposed=Q[(Q.B8L2_change.ge(2)&Q.D10_change.le(-2))|(Q.B8L2_change.le(-2)&Q.D10_change.ge(2))].copy()
    opposed["disagreement_magnitude"]=abs(opposed.B8L2_change-opposed.D10_change)
    for _,row in opposed.sort_values("disagreement_magnitude",ascending=False).drop_duplicates("image").head(4).iterrows():selected.append(dict(category="B8_D10_material_direction_reversal",eligible_distinct_pairs=len(opposed),ranking="abs(B8_delta-D10_delta)",ascending=False,pair=row.to_dict()))
    return selected,opposed


def recalculate_examples(examples,folder):
    caches={};receipt=[];geometry_caches={}
    for example in examples:
        p=example["pair"];route=p["route"];pid=p["pool_id"];key=route,pid
        if key not in caches:
            path=folder/("native_"+route)/"pools"/(pid+".json.gz")
            data=fr.read(path);caches[key]={t["team_key"]:t for t in data["teams"]};geometry_caches[key]={}
        a,b=[caches[key][p[k]] for k in ("team_lo","team_hi")]
        assert a["pool_id"]==b["pool_id"]==pid and a["reference_id"]==b["reference_id"]==p["reference_id"]
        v=px.pair_metrics(a,b,cache=geometry_caches[key]);errors=[];maxerr=0.
        for metric in SYMMETRIC:
            if metric not in p or pd.isna(p[metric]):continue
            actual=v.get(metric)
            if actual is None:errors.append(metric);continue
            err=abs(float(actual)-float(p[metric]));maxerr=max(maxerr,err)
            if err>1e-10:errors.append(metric)
        for field in ("B8L2","D10"):
            if pd.notna(p[field+"_change"]):
                err=abs(b[field]-a[field]-p[field+"_change"]);maxerr=max(maxerr,err)
                if err>1e-10:errors.append(field+"_change")
        example["exact_workers_lo"]=a["member_workers"];example["exact_workers_hi"]=b["member_workers"]
        example["native_file"]=str((folder/("native_"+route)/"pools"/(pid+".json.gz")).relative_to(ROOT))
        example["recomputed_pair_metrics"]=v
        receipt.append(dict(category=example["category"],pool_id=pid,team_lo=p["team_lo"],team_hi=p["team_hi"],max_absolute_difference=maxerr,mismatch_fields=errors))
    return receipt


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--folder",type=Path,default=ROOT/"interchangeability_20261020/discovery");ap.add_argument("--out",type=Path,default=Path(__file__).parent/"discovery_metric_audit");a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    geometry=[];quality=[];sources=[]
    for route in ("forward","reverse"):
        g,q,source=load_route(route,a.folder);geometry.append(g);quality.append(q);sources.append(source)
        print(json.dumps(dict(loaded=route,event_rows=source["event_rows"],geometry_occurrences=len(g),quality_occurrences=len(q))),flush=True)
    P=pd.concat(geometry,ignore_index=True);Q=pd.concat(quality,ignore_index=True)
    allowed=set(fr.read(ROOT/"analysis/composition/SPLIT.json")["discovery_buildings"])
    assert set(P.building)<=allowed and set(Q.building)<=allowed
    gp=verify_repeated(P,SYMMETRIC+["B8L2_change","D10_change"]);qp=verify_repeated(Q,["B8L2_change","D10_change","both_complete"])
    bd.save_json(a.out/"METRIC_AUDIT_SPEC.json",dict(schema="frozen_discovery_pair_metric_sensitivity_v1",source_files=sources,code_sha256=bd.sha(Path(__file__)),metric_contract_sha256=bd.sha(Path(__file__).parent/"METRIC_CONTRACT.json"),deduplication="Unordered actual team pair within pool and fixed reference, across all method/direction/route occurrences. Route/role subgroup counts deduplicate independently and are not additive.",formal_n="n>=3; n2 deferred separately",quality_reversal="B8 improves >=2 while D10 worsens >=2, or converse. Canonical pair orientation does not alter disagreement.",main_noQ_shape="Original strict/main/wide and frozen noQ/shape unchanged. Disagreements describe metric sensitivity; no replacement of the primary endpoint.",prism="Mean-height prism is a proxy. Exact flat-prism IoU requires identified constant ceiling, missing otherwise. >10% boundary-height and proxy<.90 flags are descriptive diagnostics, not new acceptance rules.",read_boundary="Only forward/reverse discovery metrics and their selected native final rows. No assessment results or raw observations read, no fusion/scoring/reference/classification changed."))
    assert not gp["mismatch_fields"] and not qp["mismatch_fields"],(gp,qp)
    rawg=P.drop_duplicates(KEY);rawq=Q.drop_duplicates(KEY);G=rawg[rawg.n.ge(3)].copy();U=rawq[rawq.n.ge(3)].copy()
    conf,flags=summarize_flags(P[P.n.ge(3)]);bd.save_csv(a.out/"METRIC_CONFUSION.csv",conf);bd.save_csv(a.out/"GEOMETRY_FLAGS.csv",flags)
    bd.save_csv(a.out/"QUALITY_DIRECTION.csv",quality_summary(Q[Q.n.ge(3)]))
    examples,opposed=pick_examples(G,U);checks=recalculate_examples(examples,a.folder)
    bd.save_csv(a.out/"D10_MATERIAL_DIRECTION_REVERSALS.csv",opposed)
    bd.save_json(a.out/"EXAMPLE_PAIRS.json",clean(dict(selection="Outcome-selected illustrations only; all categories and total eligible counts retained. No new validation claim.",examples=examples)))
    patterns=G[["joint_stable_main","geometry_noQ_main","geometry_shape_main"]].value_counts(dropna=False)
    out=dict(schema="frozen_discovery_pair_metric_sensitivity_v1",source_files=sources,all_geometry_occurrences=len(P),all_quality_pair_occurrences=len(Q),all_distinct_geometry_pairs=len(rawg),all_distinct_quality_pairs=len(rawq),formal_geometry=support(G),formal_quality=support(U),n2_distinct_geometry_pairs=int(rawg.n.eq(2).sum()),n2_distinct_quality_pairs=int(rawq.n.eq(2).sum()),distinct_geometry_pairs_in_both_routes=int(P.groupby(KEY).route.nunique().gt(1).sum()),deduplicated_metric_parity=gp,deduplicated_quality_parity=qp,old_main_implies_noQ=bool((~G.joint_stable_main|G.geometry_noQ_main).all()),material_B8_D10_opposite_pairs=len(opposed),material_opposite_images=opposed.image.nunique(),material_opposite_buildings=opposed.building.nunique(),selected_saved_final_recalculations=checks,all_selected_pair_recalculations_match=all(not x["mismatch_fields"] for x in checks),native_fusion_replayed=False,scoring_replayed=False,independence="Distinct actual teams and pairs remain repeated measurements on the same images/people. Use genuine image/building supports, not pair counts, for generalization.",seconds=time.monotonic()-start)
    bd.save_json(a.out/"PAIR_METRIC_AUDIT.json",clean(out));print(json.dumps({k:v for k,v in out.items() if k not in ["source_files","selected_saved_final_recalculations"]},ensure_ascii=False))


if __name__=="__main__":main()
