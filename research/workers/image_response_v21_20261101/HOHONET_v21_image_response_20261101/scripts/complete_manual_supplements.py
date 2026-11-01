#!/usr/bin/env python3
"""Validate late-downloaded extra-target snapshot and link actual saved k=2 supplement."""
from pathlib import Path
import argparse,json,importlib.util
import numpy as np
import pandas as pd
from normalize_manual import save_csv,REQUIRED,COMMIT

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1]);args=ap.parse_args()
    root=args.root.resolve();release=root/"source/repo/research/data/releases/v2.1"
    out=root/"stage02_normalized/manual"
    ix=pd.read_csv(out/"POOL_INDEX.csv")
    assert len(ix[ix.domain.eq("ordinary_manual_main")])==206
    snap=json.loads((release/"admitted_space_extension/pools/INPUT_SNAPSHOT.json").read_text())
    extras={p["pool_id"]:p for p in snap["images"]}
    audits=[]
    for pid,p in extras.items():
        row=ix[ix.pool_id.eq(pid)]
        assert len(row)==1,pid
        row=row.iloc[0];d=pd.read_csv(root/row.normalized_file,low_memory=False)
        wm={str(r.get("worker",r["worker_id"])):str(r["object_id"]) for r in p["records"]}
        assert len(wm)==row.N==len(p["records"])
        assert d.reference_id.eq(p["meta"]["reference_id"]).all()
        assert d.target_id.eq(p["reference"]["target_id"]).all()
        assert d.reference_version.eq(p["meta"]["reference_version"]).all()
        u=d.drop_duplicates("team_key")
        for r in u[["team_key","member_workers","member_object_ids"]].itertuples(index=False):
            w=set(r.member_workers.split("|"));o=set(r.member_object_ids.split("|"))
            assert w<=set(wm) and o=={wm[x] for x in w},(pid,r.team_key)
        ix.loc[ix.pool_id.eq(pid),"frozen_snapshot_identity_checked"]=True
        audits.append(dict(pool_id=pid,N=len(wm),unique_teams=len(u),rows=len(d),
            object_worker_reference_match=True,difficulty=d.difficulty.iloc[0],
            snapshot_historical_difficulty=p["meta"]["difficulty"],
            difficulty_source="explicit current image mapping, not historical ungraded snapshot"))
    save_csv(pd.DataFrame(audits),out/"EXTRA_SNAPSHOT_IDENTITY_AUDIT.csv")

    paired=pd.read_csv(release/"two_person_natural256/PAIRED_PATH_RESULTS.csv.gz",low_memory=False)
    paired=paired[paired.layer.eq("ordinary_manual")].copy()
    assert paired.pool_id.nunique()==206 and len(paired)==206*256
    assert not paired.duplicated(["pool_id","stratum","path_id"]).any()
    paired["k2_link_key"]=paired.k2_team_key.combine_first(paired.team_key)
    paired["k1_link_key"]=paired.team_key_1.combine_first(paired.saved_key_1)
    paired["k3_link_key"]=paired.team_key_3.combine_first(paired.saved_key_3)
    paired["replicate_id"]=paired.stratum.astype(str)+"::"+paired.path_id.astype(str)
    prefixes=["pool_id","image","building","condition","domain","target_id","reference_id",
        "reference_version","N","k","k_fraction","replicate_id","origin_stratum","original_path_id",
        "team_key","member_workers","member_object_ids","difficulty","difficulty_en","target_role",
        "source_time_total_seconds","source_time_known_n","labor_complete"]
    k2_index=[];checks=[]
    for pid,g in paired.groupby("pool_id",sort=True):
        row=ix[ix.pool_id.eq(pid)].iloc[0]
        d=pd.read_csv(root/row.normalized_file,low_memory=False)
        d2=d[d.k.eq(2)].set_index("replicate_id")
        gg=g.set_index("replicate_id").reindex(d2.index)
        assert gg.k2_link_key.eq(d2.team_key).all(),(pid,"k2 team identity")
        for k,qc,dc,keyc in [(1,"Q1","D1","k1_link_key"),(3,"Q3","D3","k3_link_key")]:
            old=d[d.k.eq(k)].set_index("replicate_id").reindex(d2.index)
            assert old.team_key.eq(gg[keyc]).all(),(pid,k,"adjacent team identity")
            np.testing.assert_allclose(old.B8L2,gg[qc],rtol=0,atol=1e-10,equal_nan=True)
            np.testing.assert_allclose(old.D10,gg[dc],rtol=0,atol=1e-10,equal_nan=True)
        for rid,r in gg.iterrows():
            assert set(d2.loc[rid,"member_workers"].split("|"))=={r["first"],r["entrant_worker"]},(pid,rid)
        ov=d2[[c for c in prefixes if c in d2.columns]].copy().reset_index()
        # Only saved actual k2 quantities are populated. Geometry and complete_evaluable
        # are absent from this table and are not inferred from a finite quality score.
        ov["B8L2"]=gg.k2_B8L2.to_numpy()
        ov["D10"]=gg.k2_D10.to_numpy()
        ov["IoU3D100"]=np.nan
        ov["nodes"]=gg.k2_nodes.to_numpy()
        ov["turns"]=gg.k2_floor_turn5_n.to_numpy()
        ov["floor_turn5_n"]=gg.k2_floor_turn5_n.to_numpy()
        ov["floor_redundant5_n"]=gg.k2_floor_redundant5_n.to_numpy()
        ov["connection_available"]=gg.k2_connection_available.to_numpy()
        ov["score_status"]=gg.k2_score_status.to_numpy()
        ov["geometry_status"]=gg.k2_geometry_reason.to_numpy()
        ov["quality_valid"]=np.isfinite(pd.to_numeric(ov.B8L2,errors="coerce"))
        mapping={"complete_conditional":"scoreable","no_connection":"consensus_not_formed","invalid_floor":"output_unscoreable"}
        assert set(ov.score_status)<=set(mapping)
        ov["status_class"]=ov.score_status.map(mapping)
        ov["complete_output"]=np.nan
        ov["complete_evaluable"]=np.nan
        ov["complete_evaluable_availability"]="not_saved_in_k2_paired_table"
        ov["policy_deferred"]=False
        ov["result_stage"]="independent_two_person_supplement"
        ov["source_table"]="research/data/releases/v2.1/two_person_natural256/PAIRED_PATH_RESULTS.csv.gz"
        ov["source_git_commit"]=COMMIT
        ov["analysis_version"]="v21_actual_k2_saved_supplement"
        for c in ["k2_single_support_nodes","k2_joint_support_nodes","k2_single_support_fraction",
                  "Q1","D1","Q2","Q3","D3","delta_1_2","delta_2_3","first","entrant_worker","third",
                  "team_key_1","team_key_3","k1_link_key","k2_link_key","k3_link_key"]:
            ov[c]=gg[c].to_numpy()
        ov["source_team_key_1"]=ov.team_key_1
        ov["source_team_key_3"]=ov.team_key_3
        ov["team_key_1"]=ov.k1_link_key
        ov["team_key_3"]=ov.k3_link_key
        for c in REQUIRED:
            if c not in ov:ov[c]=np.nan
        dest=out/"k2_overlay"/(pid+".csv.gz")
        digest=save_csv(ov[REQUIRED+[c for c in ov if c not in REQUIRED]],dest)
        ix.loc[ix.pool_id.eq(pid),"k2_overlay_file"]=str(dest.relative_to(root))
        k2_index.append(dict(pool_id=pid,image=row.image,N=int(row.N),paths=len(ov),
            normalized_file=str(dest.relative_to(root)),sha256=digest,
            quality_valid=int(ov.quality_valid.sum()),consensus_not_formed=int(ov.status_class.eq("consensus_not_formed").sum()),
            output_unscoreable=int(ov.status_class.eq("output_unscoreable").sum())))
        checks.append(dict(pool_id=pid,paths=len(ov),k1_k3_scores_and_team_keys_verified=True,
            k2_workers_verified=True,not_used_to_infer_complete_evaluable=True))
    save_csv(pd.DataFrame(k2_index),out/"K2_OVERLAY_INDEX.csv")
    save_csv(pd.DataFrame(checks),out/"K2_OVERLAY_LINKAGE_CHECKS.csv")
    save_csv(ix,out/"POOL_INDEX.csv")
    receipt=dict(commit=COMMIT,extra_snapshot_pools_checked=len(audits),ordinary_main_k2_pools=len(k2_index),
        ordinary_main_k2_paths=sum(x["paths"] for x in k2_index),new_fusions=0,new_scores=0,
        source_values_unchanged=True,k2_not_overwritten_in_main_tables=True,
        k2_complete_evaluable="NA because not present in archived paired table",
        excluded_historical_doorway_k2=True,extra_target_k2="not included in this ordinary-main supplement")
    (out/"SUPPLEMENT_COMPLETION.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=="__main__":main()

