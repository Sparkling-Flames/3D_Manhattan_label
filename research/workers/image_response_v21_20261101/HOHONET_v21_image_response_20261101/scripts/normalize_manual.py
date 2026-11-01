#!/usr/bin/env python3
"""Normalize saved v2.1 natural paths, preserving frequencies and original fields.

No fusion, rescoring, exclusions, references or classification are changed.
Original source tables remain in source/repo. k=2 remains the historical deferred
view here; independently computed k=2 overlays are saved in a separate stage.
"""
from __future__ import annotations
import argparse, gzip, hashlib, importlib.util, json, math, os
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd

COMMIT = "e1873bfadc1d0e61499809c91fba9dc39c717f83"
MAIN_STRATA = {"old24", "prior_new24", "new104A", "new104B"}
MAIN_COUNTS = {"old24":24,"prior_new24":24,"new104A":104,"new104B":104}
DIFF_EN = {"简单":"Easy","中等":"Medium","困难":"Hard"}
STRUCT = ["ref_geometry_status","ref_vertices","ref_turn3","ref_turn5","ref_turn10",
          "ref_H","ref_short_edges","ref_short_min_horizontal_deg",
          "ref_min_horizontal_deg","ref_radius_p90_h","has_short","conditional_short_span"]
ALIAS = {"turns":"floor_turn5_n","short_edges_03_h":"floor_short_edge_03_n",
         "floor_area_h2":"floor_area_camera_h2"}
REQUIRED = ["pool_id","image","building","condition","domain","target_id","reference_id",
            "reference_version","N","replicate_id","origin_stratum","k","k_fraction",
            "team_key","member_object_ids","member_workers","B8L2","D10","IoU3D100",
            "complete_output","status_class","quality_valid","nodes","turns",
            "short_turn_edges","floor_area_h2","height_mean_h","S_bottom_deg","dir",
            "Hmean","Hcenter","omission","extension","difficulty","difficulty_en"]
BOOLS = ["complete_evaluable","connection_available","below_four","policy_deferred",
         "score_available","score_failure_nonpolicy","incomplete_nonpolicy"]

def bool_numeric(s):
    if s is None:
        return None
    if pd.api.types.is_bool_dtype(s):
        return s.astype(float)
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s,errors="coerce")
    mapping={"True":1,"False":0,"true":1,"false":0,"TRUE":1,"FALSE":0}
    return pd.to_numeric(s.map(lambda x:mapping.get(x,x)),errors="coerce")

def statuses(d):
    """Exact precedence of archived analyze_natural.status_class, vectorized."""
    s=d.score_status.fillna("").astype(str).str.lower()
    deferred=bool_numeric(d.policy_deferred).eq(1) | d.k.eq(2)
    executed=d.get("endpoint_execution",pd.Series("",index=d.index)).astype(str)
    noexec=executed.eq("not_executed") | s.isin(["not_computed","not_executed","pending","unexecuted"])
    q=pd.to_numeric(d.B8L2,errors="coerce")
    good=np.isfinite(q)
    ref=s.isin(["floor_only_reference","missing_reference","reference_unavailable"]) | s.str.contains(
        "reference_missing|reference_paused|gt_paused|no_reference",regex=True)
    below=bool_numeric(d.below_four).eq(1)
    unformed=s.isin(["fusion_exception","below_four","no_connection"]) | below
    unscore=s.isin(["invalid_floor","invalid_full_geometry","measurement_exception",
                    "invalid_geometry","nonfinite_score","score_error"])
    failure=bool_numeric(d.get("score_failure_nonpolicy",(~good & ~deferred).astype(float))).eq(1)
    conn=bool_numeric(d.connection_available)
    return pd.Series(np.select(
        [deferred,noexec,good,ref,unformed,unscore,failure & conn.eq(0),failure],
        ["contract_deferred_k2","not_executed","scoreable","reference_unavailable",
         "consensus_not_formed","output_unscoreable","consensus_not_formed","failure_other_preserved"],
        default="unclassified_or_missing_status"),index=d.index)

def save_csv(d,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+".writing")
    with gzip.open(temp,"wt",encoding="utf-8-sig",newline="",compresslevel=1) if path.suffix==".gz" else open(
        temp,"w",encoding="utf-8-sig",newline="") as f:
        d.to_csv(f,index=False,lineterminator="\n")
    os.replace(temp,path)
    # Full decompression/readback, including gzip CRC.
    check=pd.read_csv(path,low_memory=False)
    assert len(check)==len(d) and list(check)==list(d),(path,"readback")
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_pool_metadata(release):
    pools={}
    for group,rel in [("main","pools/INPUT_SNAPSHOT.json"),
                      ("extra","admitted_space_extension/pools/INPUT_SNAPSHOT.json")]:
        p=release/rel
        if p.exists():
            doc=json.loads(p.read_text(encoding="utf-8-sig"))
            for pool in doc["images"]:
                pools[pool["pool_id"]]=(group,pool)
    return pools

def frozen_conditions(release):
    p=release/"difficulty_computable_comparison/INPUT_RECORDS.csv.gz"
    d=pd.read_csv(p,usecols=["pool_id","reference_id","difficulty"]+STRUCT)
    for c in ["reference_id","difficulty"]+STRUCT:
        assert d.groupby("pool_id")[c].nunique(dropna=False).le(1).all(),c
    return d.drop_duplicates("pool_id").set_index("pool_id").to_dict("index")

def normalize(path,group,root,metadata,conditions,difficulty_map,blocks):
    raw=pd.read_csv(path,low_memory=False)
    pid=str(raw.pool_id.iloc[0])
    assert raw.pool_id.nunique()==1
    orig_rows=len(raw)
    keep=raw.stratum.isin(MAIN_STRATA|{"new_space256"})
    # Original Semi may legitimately have only 24 or exhaustive 6 paths.
    d=raw.loc[keep].copy()
    assert len(d)>0,(pid,"no adopted strata")
    kind=str(d.condition.iloc[0]);layer=str(d.layer.iloc[0])
    if layer=="doorway_manual":
        return None,{"pool_id":pid,"source_table":str(path.relative_to(root/"source/repo")),
                    "input_rows":orig_rows,"reason":"historical_doorway_replaced_by_current_584_439"}
    meta=metadata.get(pid,(None,{}))[1]
    pm=meta.get("meta",{})
    image=str(pm.get("image",d.image.iloc[0]))
    N=int(pm.get("pool_n",d.pool_n.iloc[0]))
    assert d.pool_n.eq(N).all()
    if group=="extra":
        domain="ordinary_manual_extra_target" if kind=="manual" else "ordinary_semi_secondary"
        target_role="extra_legal_target"
    elif layer.startswith("special"):
        domain="oos_manual_independent" if kind=="manual" else "oos_semi_independent"
        target_role="oos_independent"
    else:
        domain="ordinary_manual_main" if kind=="manual" else "ordinary_semi_secondary"
        target_role="current_primary_target"
    reference=meta.get("reference",{})
    target_id=reference.get("target_id",difficulty_map.get(pid,{}).get("target_id",pm.get("reference_id",d.reference_id.iloc[0])))
    reference_id=pm.get("reference_id",d.reference_id.iloc[0])
    assert d.reference_id.eq(reference_id).all(),(pid,"reference identity differs")
    difficulty=difficulty_map.get(pid,{}).get("image_difficulty",pm.get("difficulty",d.difficulty.iloc[0]))
    version=pm.get("reference_version",d.reference_version.iloc[0])
    # Raw metadata remains explicitly available when current metadata is added.
    for c in ["image","building","condition","difficulty","reference_id","reference_version","pool_n"]:
        d["raw_"+c]=d[c]
    for c,v in dict(image=image,building=pm.get("building",d.building.iloc[0]),condition=kind,
                    difficulty=difficulty,reference_id=reference_id,reference_version=version).items():
        d[c]=v
    d["target_id"]=target_id
    d["N"]=N;d["k"]=d.k.astype(int);d["k_fraction"]=d.k/N
    d["domain"]=domain;d["target_role"]=target_role
    d["origin_stratum"]=d.stratum
    d["original_path_id"]=d.path_id.astype(str)
    d["replicate_id"]=d.origin_stratum.astype(str)+"::"+d.original_path_id
    d["difficulty_en"]=DIFF_EN.get(str(difficulty),str(difficulty))
    d["result_stage"]=np.where(d.k.eq(1),"original_answer",
                               np.where(d.k.eq(2),"historical_two_person_deferred","fused_team"))
    d["source_table"]=str(path.relative_to(root/"source/repo"))
    d["source_git_commit"]=COMMIT
    d["data_release"]="v2.1"
    for c in BOOLS:
        if c not in d:d[c]=np.nan
    # Only reconstruct explicitly derived flags absent in this source format.
    q=pd.to_numeric(d.B8L2,errors="coerce")
    d["quality_valid"]=np.isfinite(q)
    deferred=bool_numeric(d.policy_deferred)
    missing=deferred.isna()
    if missing.any():
        assert d.loc[missing,"score_status"].eq("two_person_deferred").equals(d.loc[missing,"k"].eq(2)),pid
        d.loc[missing,"policy_deferred"]=d.loc[missing,"k"].eq(2)
    d["complete_output"]=bool_numeric(d.complete_evaluable)
    if d.score_failure_nonpolicy.isna().all():
        d["score_failure_nonpolicy"]=(~d.quality_valid & d.k.ne(2))
    d["status_class"]=statuses(d)
    d["labor_complete"]=np.where(pd.to_numeric(d.source_time_known_n,errors="coerce").notna(),
        pd.to_numeric(d.source_time_known_n,errors="coerce").eq(d.k),np.nan)
    for dst,src in ALIAS.items():d[dst]=pd.to_numeric(d[src],errors="coerce") if src in d else np.nan
    # Derive named explanation terms with frozen formula, never overwrite saved Q.
    d=blocks.add_blocks_frame(d,check_existing=True)
    for c in REQUIRED:
        if c not in d:d[c]=np.nan

    # Identity, full paths and nested membership are substantive checks.
    assert not d.duplicated(["replicate_id","k"]).any(),(pid,"duplicate prefix")
    counts=d.groupby("origin_stratum").replicate_id.nunique().to_dict()
    R=d.replicate_id.nunique()
    assert len(d)==R*N,(pid,"missing prefixes")
    assert d.groupby("replicate_id").k.nunique().eq(N).all()
    assert sorted(d.k.unique())==list(range(1,N+1))
    if domain=="ordinary_manual_main":
        expected={"new_space256":256} if set(counts)=={"new_space256"} else MAIN_COUNTS
        assert counts==expected,(pid,counts)
    if group=="extra":assert counts=={"new_space256":256},(pid,counts)
    uniq=d.drop_duplicates("team_key")
    assert uniq.k.groupby(uniq.team_key).nunique().eq(1).all()
    workers={}
    frozen_records=meta.get("records")
    if frozen_records is not None:
        workers={str(r.get("worker",r.get("worker_id"))):str(r["object_id"]) for r in frozen_records}
        assert len(workers)==N
    sets={}
    prohibited=[]
    for r in uniq[["team_key","k","member_workers","member_object_ids"]].itertuples(index=False):
        w=str(r.member_workers).split("|");o=str(r.member_object_ids).split("|")
        assert len(w)==len(set(w))==len(o)==len(set(o))==r.k,(pid,r.team_key,"member count")
        assert not ({"W019","W026"}&set(w)),(pid,r.team_key,"historically excluded worker")
        if workers:
            assert set(w)<=set(workers),(pid,r.team_key,"worker outside frozen pool")
            assert set(o)=={workers[x] for x in w},(pid,r.team_key,"object identity mismatch")
        sets[r.team_key]=set(w)
    fulls=d.loc[d.k.eq(N),"team_key"].unique()
    assert len(fulls)==1,(pid,"more than one full team")
    pool_members=sets[fulls[0]]
    for rid,rg in d.sort_values(["replicate_id","k"]).groupby("replicate_id",sort=False):
        prev=set()
        for team in rg.team_key:
            now=sets[team]
            assert prev<now and len(now-prev)==1,(pid,rid,"not nested")
            prev=now
        assert prev==pool_members,(pid,rid,"wrong full pool")
    # Every repeated physical team retains weight but must retain the same saved score.
    consistent=["k","B8L2","D10","IoU3D100","nodes","floor_turn5_n","score_status"]
    for c in consistent:
        assert d.groupby("team_key")[c].nunique(dropna=False).le(1).all(),(pid,c,"inconsistent repeated team")
    residual=pd.to_numeric(d.get("B8_formula_residual"),errors="coerce")
    max_residual=float(residual.abs().max()) if residual.notna().any() else None
    d=d.sort_values(["origin_stratum","original_path_id","k"],kind="stable").reset_index(drop=True)
    ordered=REQUIRED+[c for c in d if c not in REQUIRED]
    d=d[ordered]
    dest=root/"stage02_normalized/manual/pools"/(pid+".csv.gz")
    sha=save_csv(d,dest)
    exact=R==math.factorial(N) and N<=6 and set(counts)=={"old24"}
    sampling=("exhaustive_permutation" if exact else "uniform_random_nested_paths")
    index=dict(pool_id=pid,image=image,building=d.building.iloc[0],condition=kind,domain=domain,
        target_role=target_role,target_id=target_id,reference_id=reference_id,reference_version=version,
        N=N,difficulty=difficulty,difficulty_en=DIFF_EN.get(str(difficulty),str(difficulty)),
        source_group=group,source_table=str(path.relative_to(root/"source/repo")),
        normalized_file=str(dest.relative_to(root)),absolute_file=str(dest),paths=R,
        rows=len(d),unique_teams=d.team_key.nunique(),origin_strata="|".join(sorted(counts)),
        stratum_counts_json=json.dumps(counts,sort_keys=True),sampling_scheme=sampling,
        path_frequency_preserved=True,source_input_rows=orig_rows,excluded_focused_rows=orig_rows-len(d),
        full_team_key=fulls[0],pool_members="|".join(sorted(pool_members)),
        frozen_snapshot_identity_checked=bool(frozen_records is not None),
        difficulty_source=("paper_evidence_20261030/IMAGE_DIFFICULTY_MAPPING.csv"
                           if pid in difficulty_map else "pools/INPUT_SNAPSHOT.json"),
        k2_view="historical_deferred_overlay_saved_separately",main_analysis_min_k=3,
        normalization_sha256=sha,readback="complete CSV and gzip EOF",
        metadata_source_commit=COMMIT,B8_formula_residual_abs_max=max_residual,
        normalized_columns=len(d.columns))
    for c in STRUCT:index[c]=conditions.get(pid,{}).get(c,np.nan)
    if pid in conditions:
        assert conditions[pid]["reference_id"]==reference_id,(pid,"structure target mismatch")
        assert conditions[pid]["difficulty"]==difficulty,(pid,"structure difficulty mismatch")
        index["structural_condition_source"]="difficulty_computable_comparison/INPUT_RECORDS.csv.gz"
    else:index["structural_condition_source"]="not_available_in_main_condition_table"
    return index,None

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--pool",action="append");ap.add_argument("--sample",action="store_true")
    args=ap.parse_args();root=args.root.resolve()
    release=root/"source/repo/research/data/releases/v2.1"
    out=root/"stage02_normalized/manual";out.mkdir(parents=True,exist_ok=True)
    pools=load_pool_metadata(release);conditions=frozen_conditions(release)
    dm=pd.read_csv(release/"paper_evidence_20261030/IMAGE_DIFFICULTY_MAPPING.csv").set_index("pool_id").to_dict("index")
    block_path=root/"stage00_manual_sources/repo/research/workers/personnel_population_curves_v2_20261023/sampling_extension_20261026/engine26/derive_frozen_blocks.py"
    spec=importlib.util.spec_from_file_location("frozen_blocks_for_normalization",block_path)
    blocks=importlib.util.module_from_spec(spec);spec.loader.exec_module(blocks)
    jobs=[]
    for group,rel in [("main","natural_analysis_restored/inputs"),("main","natural_inputs"),
                      ("extra","admitted_space_extension/natural_inputs")]:
        jobs += [(p,group) for p in sorted((release/rel).glob("*.csv.gz"))]
    if args.pool:jobs=[(p,g) for p,g in jobs if p.name[:-7] in args.pool]
    if args.sample:jobs=[(p,g) for p,g in jobs if p.name.startswith("2t7WUuJeko7-02__manual__")]
    seen=set();indices=[];excluded=[]
    for n,(path,group) in enumerate(jobs,1):
        pid=path.name[:-7]
        assert pid not in seen,("duplicate input pool",pid);seen.add(pid)
        idx,exc=normalize(path,group,root,pools,conditions,dm,blocks)
        if idx:indices.append(idx)
        if exc:excluded.append(exc)
        if n%10==0 or n==len(jobs):
            print(json.dumps({"done":n,"total":len(jobs),"pool":pid,"normalized":len(indices)},ensure_ascii=False),flush=True)
    ix=pd.DataFrame(indices)
    save_csv(ix,out/"POOL_INDEX.csv")
    if excluded:save_csv(pd.DataFrame(excluded),out/"REDIRECTED_HISTORICAL_DOORWAY.csv")
    missing=[]
    for pid,(group,pool) in pools.items():
        if pid not in seen:
            m=pool["meta"]
            missing.append(dict(pool_id=pid,condition=m.get("condition"),layer=m.get("layer"),
                image=m.get("image"),N=m.get("pool_n"),
                reason="source_path_input_not_in_restored_or_updated_set",
                adopted_prior_sampling="original_24_or_exact_preserved_not_assumed_256"))
    if missing:save_csv(pd.DataFrame(missing),out/"UNNORMALIZED_POOL_INVENTORY.csv")
    if not args.pool and not args.sample:
        main_ix=ix[ix.domain.eq("ordinary_manual_main")]
        assert len(main_ix)==main_ix.image.nunique()==206
        assert main_ix.paths.eq(256).all()
        extra=ix[ix.domain.eq("ordinary_manual_extra_target")]
        assert len(extra)==30 and extra.image.nunique()==28
        assert len(excluded)==17
    counts=ix.groupby("domain").agg(pools=("pool_id","size"),images=("image","nunique"),
                                    rows=("rows","sum")).reset_index().to_dict("records")
    receipt=dict(commit=COMMIT,input_files=len(jobs),normalized_pools=len(ix),domains=counts,
        redirected_historical_doorway_pools=len(excluded),unmaterialized_snapshot_pools=len(missing),
        no_fusion=True,no_rescore=True,duplicates_retain_path_weight=True,
        identity_checks="exact counts, frozen object-worker relation when snapshot available, historical W019/W026 absence, nested prefixes, unique full team",
        k2="original deferred values; actual archived k2 handled by separate overlay",
        source_files_untouched=True,scope="sample" if args.sample or args.pool else "all_downloaded_inputs")
    (out/"NORMALIZATION_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf8")
    (out/"SCHEMA.json").write_text(json.dumps(dict(required=REQUIRED,aliases=ALIAS,
        status_classes=["contract_deferred_k2","not_executed","scoreable","reference_unavailable",
            "consensus_not_formed","output_unscoreable","failure_other_preserved","unclassified_or_missing_status"],
        complete_output="saved complete_evaluable numeric 1/0/NA, independent of Q",
        quality_valid="finite saved B8L2 including a genuine zero",
        replicate_id="origin_stratum::original_path_id",
        k1_stage="original_answer",k2_stage="historical_two_person_deferred",
        source_columns="all preserved; replaced metadata also retained as raw_*",
        index_path_columns=["normalized_file relative to study root","absolute_file"],
        difficulty="frozen Chinese grade plus difficulty_en, extra targets inherit explicit image mapping",
        structure_fields=STRUCT),ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=="__main__":main()

