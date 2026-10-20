#!/usr/bin/env python3
"""Portable full history-feature and forward-label rebuild with explicit inputs.

Large audited records and archived estimator code remain in the external,
SHA-verified restored directory. No raw export preprocessing is performed.
"""
from __future__ import annotations
import argparse, datetime, gzip, importlib.util, json, os, shutil, subprocess, sys
from pathlib import Path
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[key]="1"
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_designs import read, write, sha, rows_sha

HERE=Path(__file__).resolve().parent
STUDY="interchangeability_20261020"

def run(cmd,cwd,log):
    with log.open("w") as f:
        p=subprocess.run([str(x) for x in cmd],cwd=cwd,env=dict(os.environ),stdout=f,stderr=subprocess.STDOUT,check=False)
    if p.returncode:raise RuntimeError(log.read_text()[-8000:])

def normalized_labels(df):
    return [dict(worker_id=str(r.worker_id),method_id=str(r.method_id),domain=str(r.domain),
                 class_id=str(r.class_id),known=str(r.known).lower() in ["true","1","1.0"])
            for r in df.itertuples()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--package-root",type=Path,required=True)
    ap.add_argument("--restored",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--inputs",type=Path,default=HERE/"FORWARD_FEATURE_INPUTS.json")
    a=ap.parse_args();root=a.package_root.resolve();restored=a.restored.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    manifest=read(a.inputs);stage=out/"portable_input";stage.mkdir(exist_ok=True)
    for spec in manifest["package_inputs"]:
        source=root/spec["source"];dest=stage/spec["stage"]
        assert sha(source)==spec["sha256"],"Changed package input "+str(source)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or sha(dest)!=spec["sha256"]:shutil.copyfile(source,dest)
    for spec in manifest["restored_inputs"]:
        source=restored/spec["source"];dest=stage/spec["stage"]
        assert sha(source)==spec["sha256"],"Changed restored input "+str(source)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.is_symlink():assert dest.resolve()==source.resolve()
        elif dest.exists():raise RuntimeError("Expected external-input symlink: "+str(dest))
        else:dest.symlink_to(source)
    features=out/"reconstructed";features.mkdir(exist_ok=True)
    script=stage/STUDY/"forward/audit_and_features.py"
    # Absolute paths preserve the scientific code's provenance-relative layout.
    cmd=[sys.executable,script,"--repo",stage/"repo","--prior",stage/"analysis",
         "--followup",stage/STUDY/"reproduction/feature_support","--out",features]
    run(cmd,stage,out/"feature_rebuild.log")
    import numpy as np
    import pandas as pd
    old=pd.read_csv(stage/STUDY/"forward/features_train.csv.gz").sort_values("worker_id").reset_index(drop=True)
    new=pd.read_csv(features/"features_train.csv.gz").sort_values("worker_id").reset_index(drop=True)
    assert list(old.columns)==list(new.columns) and len(old)==len(new)
    differences=[]
    for column in old:
        left,right=old[column],new[column]
        if pd.api.types.is_numeric_dtype(left) and not pd.api.types.is_bool_dtype(left):
            x,y=left.to_numpy(float),right.to_numpy(float)
            equal=bool(np.allclose(x,y,rtol=0,atol=1e-9,equal_nan=True))
            maximum=float(np.nanmax(np.abs(x-y))) if np.isfinite(x-y).any() else None
        else:
            equal=bool(left.fillna("NA").eq(right.fillna("NA")).all());maximum=None
        differences.append(dict(field=column,equal=equal,max_abs_difference=maximum))
    assert all(x["equal"] for x in differences),[x for x in differences if not x["equal"]]
    # Run the original full entry, including metadata-only historical/target
    # capacity ledgers; no target fusion or quality enters classification.
    build=stage/STUDY/"forward/build_candidates.py"
    command2=[sys.executable,build,"--features",features/"features_train.csv.gz","--repo",stage/"repo",
              "--split",stage/"analysis/composition/SPLIT.json","--out",features]
    run(command2,stage,out/"candidate_rebuild.log")
    arows=normalized_labels(pd.read_csv(stage/STUDY/"forward/worker_labels.csv.gz",keep_default_na=False))
    brows=normalized_labels(pd.read_csv(features/"worker_labels.csv.gz",keep_default_na=False))
    assert rows_sha(arows)==rows_sha(brows)
    oldm=read(stage/STUDY/"forward/method_manifest.json");newm=read(features/"method_manifest.json")
    assert set(oldm["methods"])==set(newm["methods"])
    for mid,m in oldm["methods"].items():
        n=newm["methods"][mid]
        for key in ("partition_sha256","class_sizes","known_workers","capacity"):
            assert m.get(key)==n.get(key),(mid,key)
    receipt=dict(schema="portable_full_forward_rebuild_audit_v1",finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        package_root=str(root),external_restored=str(restored),inputs_manifest_sha256=sha(a.inputs),
        history_buildings=oldm["history_buildings"],worker_rows=len(new),feature_columns=len(new.columns),feature_tolerance_absolute=1e-9,
        all_features_equal=True,all_labels_equal=True,label_rows=len(arows),method_count=len(newm["methods"]),
        all_partition_sizes_known_sets_and_capacities_equal=True,canonical_labels_sha256=rows_sha(arows),
        original_features_file_sha256=sha(stage/STUDY/"forward/features_train.csv.gz"),
        rebuilt_features_file_sha256=sha(features/"features_train.csv.gz"),
        commands=[[str(x) for x in cmd],[str(x) for x in command2]],
        feature_comparison=differences,
        no_raw_export_reprocessing=True,target_building_outcomes_not_used_for_training=True,
        output_note="Transient gzip container/header may differ; numeric features, full label definitions, capacities and class member sets are checked explicitly. Do not package portable_input, duplicated restored sources, or rebuild caches.")
    write(out/"FORWARD_FULL_REBUILD_RECEIPT.json",receipt)
    print(json.dumps({k:receipt[k] for k in ["worker_rows","feature_columns","all_features_equal","all_labels_equal","label_rows","method_count","all_partition_sizes_known_sets_and_capacities_equal"]}),flush=True)

if __name__=="__main__":main()
