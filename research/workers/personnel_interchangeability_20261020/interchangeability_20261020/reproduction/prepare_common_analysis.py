#!/usr/bin/env python3
"""Prepare unchanged common-panel analysis with frozen registrations and aliases.

Default mode verifies the portable layout and native member support only.
--run sequentially executes the two original summary programs for both phases;
it does not generate new teams, re-fit labels, or alter registered comparisons.
"""
from __future__ import annotations
import argparse, collections, datetime, json, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_designs import read,write,sha,stage_inputs,STUDY,SNAP_REL

HERE=Path(__file__).resolve().parent
COMMON=STUDY+"/forward/common_panel"

def symlink_checked(dest,source):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.is_symlink():assert dest.resolve()==source.resolve()
    elif dest.exists():raise RuntimeError("Existing non-alias path "+str(dest))
    else:dest.symlink_to(source.resolve(),target_is_directory=source.is_dir())

def main():
    ap=argparse.ArgumentParser()
    for name in ["package-root","restored","design-rebuild","native-discovery","native-assessment","out"]:
        ap.add_argument("--"+name,type=Path,required=True)
    ap.add_argument("--run",action="store_true")
    a=ap.parse_args();root=a.package_root.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    stage=out/"portable_input"
    expected=read(root/STUDY/"reproduction/DESIGN_FINGERPRINTS.json")
    snap=stage_inputs(root,stage,a.restored,expected)
    inputs=read(root/STUDY/"reproduction/COMMON_ANALYSIS_INPUTS.json")
    for x in inputs["files"]:
        src=root/x["path"];dst=stage/x["path"]
        assert sha(src)==x["sha256"],str(src)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists() or sha(dst)!=x["sha256"]:shutil.copyfile(src,dst)
    for x in inputs["aliases"]:
        symlink_checked(stage/x["alias"],stage/x["target"])
        assert sha(stage/x["alias"])==x["sha256"]
    snapalias=stage/"repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
    symlink_checked(snapalias,snap)
    reg=read(stage/COMMON/"competitors/COMPETITOR_REGISTRATION.json")
    receipt=dict(schema="portable_common_analysis_preparation_v1",created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scientific_registration_changed=False,analyses_executed=a.run,phases=[])
    rebuild=read(a.design_rebuild/"DESIGN_REBUILD_RECEIPT.json")
    existing={r["id"]:r for r in rebuild["designs"]}
    for phase,native in [("discovery",a.native_discovery),("assessment",a.native_assessment)]:
        name="common26_"+phase;assert existing[name]["status"]=="reconstructed_equal"
        generated=a.design_rebuild/"reconstructed"/name
        panel=stage/COMMON/("assessment" if phase=="assessment" else "")
        original=read(panel/"COMMON_PANEL_REGISTRATION.json")
        assert sha(panel/"COMMON_PANEL_REGISTRATION.json")==reg["phases"][phase]["registration_sha256"]
        for file,key in [("common_requests.json.gz","request_sha256"),("common_anchors.json.gz","anchor_sha256"),("random_labels.csv.gz","random_labels_sha256")]:
            source=generated/file
            assert sha(source)==original[key],(phase,file,"Generated data container no longer equals original frozen registration")
            shutil.copyfile(source,panel/file)
        symlink_checked(panel/"native",native)
        by=collections.defaultdict(list)
        for r in read(panel/"common_requests.json.gz")["requests"]:by[r["pool_id"]].append(r)
        checked=0
        for pid,requests in by.items():
            nt=read(native/"pools"/(pid+".json.gz"));teams={t["team_key"]:t for t in nt["teams"]}
            for r in requests:
                assert sorted(teams[r["request_id"]]["member_workers"])==r["worker_ids"]
                checked+=1
        commands=[
            [sys.executable,stage/COMMON/"summarize_common_panel.py","--panel",panel,"--snapshot",snap,"--labels",stage/STUDY/"forward/worker_labels.csv.gz","--features",stage/STUDY/"forward/features_train.csv.gz"],
            [sys.executable,stage/COMMON/"compare_competitors.py","--phase",phase]]
        for cmd in commands:
            if a.run:
                logfile=out/(phase+"_"+Path(cmd[1]).stem+".log")
                with logfile.open("w") as f:
                    result=subprocess.run([str(x) for x in cmd],cwd=stage,env=dict(os.environ),stdout=f,stderr=subprocess.STDOUT,check=False)
                if result.returncode:raise RuntimeError(logfile.read_text()[-6000:])
        receipt["phases"].append(dict(phase=phase,exact_native_requested_members_checked=checked,pools=len(by),
            registration_sha256=sha(panel/"COMMON_PANEL_REGISTRATION.json"),requests_sha256=sha(panel/"common_requests.json.gz"),
            anchors_sha256=sha(panel/"common_anchors.json.gz"),commands=[[str(x) for x in cmd] for cmd in commands]))
    for source in reg["source_files"].values():
        assert sha(stage/source["labels_path"])==source["labels_sha256"]
        assert sha(stage/source["manifest_path"])==source["manifest_sha256"]
    receipt["all_frozen_file_guards_verified"]=True
    receipt["scope"]="A preparation-only run checks real original native member presence and exact source/registration/request/anchor hashes. It is not another statistical replication; use --run to regenerate summary tables from the existing native geometries."
    write(out/"COMMON_ANALYSIS_PREPARATION_RECEIPT.json",receipt)
    print(json.dumps(dict(prepared=True,analyses_executed=a.run,phases=receipt["phases"]),ensure_ascii=False))

if __name__=="__main__":main()
