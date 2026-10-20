#!/usr/bin/env python3
"""Rebuild exact registered member designs in an isolated, minimal file layout.

This is a packaging/reproduction audit, not an experiment. Frozen labels,
references, scoring, outcomes and registered comparisons are not changed.
Native fusion is intentionally delegated to the separate core replay contract.
"""
from __future__ import annotations
import argparse, collections, csv, datetime, gzip, hashlib, importlib.util, io
import json, os, shutil, subprocess, sys, time
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

HERE = Path(__file__).resolve().parent
STUDY = "interchangeability_20261020"
SNAP_REL = "work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
F_LABEL = STUDY + "/forward/worker_labels.csv.gz"
R_LABEL = STUDY + "/reverse/mixed_fit/worker_labels.csv.gz"
RL_LABEL = STUDY + "/reverse/legacy_fit/worker_labels.csv.gz"
OLD_R = "analysis/reverse/worker_labels.csv.gz"
SPLIT = "analysis/composition/SPLIT.json"

# Small, explicit dependencies. No whole repository, model cache or native pool
# directory is copied into the audit layout. Restored frozen input stays external.
REQUIRED = [
    SPLIT, OLD_R, "analysis/forward/results/features_train.csv.gz",
    "analysis/composition/design_compositions.py", "analysis/composition/design_screen.py",
    "analysis/composition/fusion_runner.py", "analysis/composition/summarize_grid.py",
    "analysis/composition/geometry_diagnostics.py",
    *[STUDY + "/code/" + f for f in ["design_history_panel.py", "design_blocks.py", "design_nested_new2.py",
        "design_condition_transfer.py", "design_mixed_challenge.py", "design_ratio_grid.py", "design_ratio_replication.py"]],
    STUDY + "/REGISTRATION.json", STUDY + "/discovery/FORWARD_SPEC.json", STUDY + "/discovery/REVERSE_SPEC.json",
    STUDY + "/assessment/DIRECTION_SPEC.json", STUDY + "/assessment/NESTED_NEW2_SPEC.json", STUDY + "/assessment/ASSESSMENT_FREEZE.json",
    F_LABEL, R_LABEL, RL_LABEL, STUDY + "/forward/features_train.csv.gz", STUDY + "/forward/method_manifest.json",
    STUDY + "/forward/build_candidates.py", STUDY + "/forward/audit_and_features.py",
    STUDY + "/forward/common_panel/design_common_panel.py",
    STUDY + "/independent/baseline/design_baseline.py", STUDY + "/independent/pair_diagnostics.py",
    STUDY + "/independent/METRIC_CONTRACT.json", STUDY + "/ratio_grid/RATIO_REPLICATION_FREEZE.json",
]

DESIGNS = [
    dict(id="forward_wide", kind="blocks", original=STUDY+"/discovery/forward_requests.json.gz", spec=STUDY+"/discovery/FORWARD_SPEC.json", labels=[F_LABEL, OLD_R]),
    dict(id="reverse_wide", kind="blocks", original=STUDY+"/discovery/reverse_requests.json.gz", spec=STUDY+"/discovery/REVERSE_SPEC.json", labels=[RL_LABEL, R_LABEL]),
    dict(id="fixed_directions", kind="blocks", original=STUDY+"/assessment/direction_requests.json.gz", spec=STUDY+"/assessment/DIRECTION_SPEC.json", labels=[F_LABEL, RL_LABEL, R_LABEL, OLD_R]),
    dict(id="nested_new2", kind="nested", original=STUDY+"/assessment/nested_new2_requests.json.gz"),
    dict(id="condition_all", kind="condition", original=STUDY+"/condition_transfer/requests.json.gz"),
    dict(id="condition_discovery", kind="condition_phase", phase="discovery", original=STUDY+"/condition_transfer/discovery_requests.json.gz"),
    dict(id="condition_assessment", kind="condition_phase", phase="assessment", original=STUDY+"/condition_transfer/assessment_requests.json.gz"),
    dict(id="mixed_discovery", kind="mixed", phase="discovery", original=STUDY+"/mixed_challenge/discovery_requests.json.gz"),
    dict(id="mixed_assessment", kind="mixed", phase="assessment", original=STUDY+"/independent/mixed_challenge/assessment_requests.json.gz"),
    dict(id="ratio_discovery", kind="ratio", original=STUDY+"/ratio_grid/discovery_requests.json.gz"),
    dict(id="ratio_new_members", kind="ratio_replication", phase="replication", original=STUDY+"/ratio_grid/replication_requests.json.gz"),
    dict(id="ratio_assessment", kind="ratio_replication", phase="assessment", original=STUDY+"/ratio_grid/assessment_requests.json.gz"),
    dict(id="common26_discovery", kind="common", phase="discovery", seed=2026102013, original=STUDY+"/forward/common_panel/common_requests.json.gz", sidecar=STUDY+"/forward/common_panel/common_anchors.json.gz"),
    dict(id="common26_assessment", kind="common", phase="assessment", seed=2026102025, original=STUDY+"/forward/common_panel/assessment/common_requests.json.gz", sidecar=STUDY+"/forward/common_panel/assessment/common_anchors.json.gz"),
    dict(id="reverse_history_panel", kind="history", original=STUDY+"/history_panel/history_requests.json.gz", sidecar=STUDY+"/history_panel/history_anchors.json.gz"),
    dict(id="known_GR_baseline", kind="baseline", original=STUDY+"/independent/baseline/REQUESTS.json.gz", csv_sidecar=STUDY+"/independent/baseline/EVENT_DESIGN.csv.gz"),
    dict(id="local_P05_census", kind="retained", original=STUDY+"/ratio_grid/local_census/requests.json.gz", note="Exact small request retained; all 3,752 teams enumerated in the original outcome-motivated one-image mechanism census. No new census or validation claim."),
    dict(id="W132_mechanism_probe", kind="retained", original=STUDY+"/assessment/w132_probe_requests.json.gz", note="Exact small request retained; original registered W132 member mechanism probe, not a newly learned classifier."),
]

def read(path):
    raw = Path(path).read_bytes()
    return json.loads(gzip.decompress(raw) if str(path).endswith(".gz") else raw)

def write(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()
    data = gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw
    tmp = path.with_name(path.name+".tmp"); tmp.write_bytes(data); tmp.replace(path)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def rows_sha(rows):
    values = sorted(canonical(x) for x in rows)
    h = hashlib.sha256()
    for v in values: h.update(v.encode()); h.update(b"\n")
    return h.hexdigest()

def team_key(pid, workers):
    # The native key uses default ensure_ascii=True; worker IDs are ASCII.
    h=hashlib.sha256(json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return pid+"__"+h[:20]

def fingerprint(path, sidecar=None, csv_sidecar=None):
    d=read(path); rr=d.get("requests",[])
    canonical_requests=[]
    for r in rr:
        ws=sorted(r.get("worker_ids",r.get("workers",[]))); n=int(r.get("k",len(ws)))
        assert len(ws)==len(set(ws))==n, (path,r.get("request_id"))
        if r.get("team_key"): assert r["team_key"]==team_key(r["pool_id"],ws)
        canonical_requests.append([r["pool_id"],ws,n])
    unique={canonical(r):r for r in canonical_requests}
    result=dict(request_rows=len(rr), unique_teams=len(unique),
        canonical_request_multiset_sha256=rows_sha(canonical_requests),
        canonical_unique_teams_sha256=rows_sha(unique.values()),
        pools=len({r["pool_id"] for r in rr}))
    for key in ("events","anchors","paths","blocks","links","rule_links","ledger"):
        if isinstance(d.get(key),list):
            result[key+"_rows"]=len(d[key]); result[key+"_sha256"]=rows_sha(d[key])
    if sidecar:
        extra=read(sidecar)
        for key in ("anchors","paths","blocks","events"):
            if isinstance(extra.get(key),list):
                result["sidecar_"+key+"_rows"]=len(extra[key]); result["sidecar_"+key+"_sha256"]=rows_sha(extra[key])
    if csv_sidecar:
        raw=gzip.decompress(Path(csv_sidecar).read_bytes()).decode() if str(csv_sidecar).endswith(".gz") else Path(csv_sidecar).read_text()
        er=list(csv.DictReader(io.StringIO(raw)))
        result["csv_events_rows"]=len(er); result["csv_events_sha256"]=rows_sha(er)
    return result

def known_maps(root):
    import pandas as pd
    maps={}
    for rel in [F_LABEL, R_LABEL, RL_LABEL, OLD_R]:
        df=pd.read_csv(root/rel)
        if "known" in df: df=df[df.known.astype(str).str.lower().isin(["true","1","1.0"])]
        df=df[df.class_id.notna()]
        for (mid,domain),g in df.groupby(["method_id","domain"]):
            m=dict(zip(g.worker_id,g.class_id.astype(str)))
            assert (mid,domain) not in maps or maps[mid,domain]==m
            maps[mid,domain]=m
    return maps

def check_event_members(path, pools, maps):
    d=read(path); rr=d.get("requests",[])
    by={team_key(r["pool_id"],r["worker_ids"]):r for r in rr}
    for r in rr:
        assert r["pool_id"] in pools
        assert set(r["worker_ids"]) <= set(pools[r["pool_id"]]["origins"])
    count=0
    for e in d.get("events",[]):
        if "A_workers" not in e:
            if "workers" in e and "team_key" in e:
                assert sorted(e["workers"])==sorted(by[e["team_key"]]["worker_ids"])
            continue
        pid=e["pool_id"]; n=int(e.get("n",e.get("k"))); m=int(e["m"])
        arms=[set(e[a+"_workers"]) for a in "ABC"]; core=set(e["core_workers"])
        assert all(len(w)==n for w in arms)
        assert arms[0]&arms[1]==arms[0]&arms[2]==core
        assert len(core)==n-m and len(arms[0]-arms[1])==len(arms[0]-arms[2])==m
        assert e["reference_id"]==pools[pid]["reference_id"]
        mapping=maps[e["method_id"],e["domain"]]
        for a,w in zip("ABC",arms):
            tk=team_key(pid,w); assert tk==e[a+"_team_key"] and tk in by
            got=dict(collections.Counter(mapping.get(x,"outside_group") for x in w))
            expected={c:int(v) for c,v in e[a+"_counts"].items() if v}
            assert got==expected,(e["event_id"],a,got,expected)
        assert e["A_counts"]==e["B_counts"] and e["A_counts"]!=e["C_counts"]
        sc=[collections.Counter(pools[pid]["origins"][w] for w in arm-core) for arm in arms]
        assert (sc[0]==sc[1]==sc[2]) == e["actual_source_match"]
        count+=1
    return dict(request_rows_members_available=len(rr),ABC_events_checked=count,checks="Each n/m, exact common core, A/B/C team key and workers, class counts, source-count equality and frozen reference ID.")

def record_expected(root, dest):
    entries=[]
    for spec in DESIGNS:
        path=root/spec["original"]
        if not path.exists():
            raise FileNotFoundError(path)
        f=fingerprint(path,root/spec["sidecar"] if spec.get("sidecar") else None,root/spec["csv_sidecar"] if spec.get("csv_sidecar") else None)
        entries.append(dict(spec,original_file_sha256=sha(path),original_bytes=path.stat().st_size,expected=f))
    required=list(REQUIRED)+[s["original"] for s in DESIGNS if s["kind"]=="retained"]
    files=[dict(path=p,bytes=(root/p).stat().st_size,sha256=sha(root/p)) for p in required]
    snap=root/"restored"/SNAP_REL
    out=dict(schema="exact_member_design_reproduction_fingerprints_v1",recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        no_new_science=True, snapshot_sha256=sha(snap), snapshot_relative_to_restored=SNAP_REL,
        required_files=files, designs=entries,
        hash_contract="UTF-8 JSON sorted object keys with compact separators, rows sorted lexicographically by canonical JSON and newline-delimited SHA256. Unique-team and request-multiset fingerprints both retained. Full event fields and relation/ledger sidecars checked; generated timestamps, gzip header and input path spelling are not scientific member identities.")
    write(dest,out)
    print(json.dumps(dict(recorded=len(entries),small_inputs=len(files),input_bytes=sum(f["bytes"] for f in files)),ensure_ascii=False),flush=True)

def stage_inputs(source, stage, restored, expected):
    stage.mkdir(parents=True,exist_ok=True)
    for item in expected["required_files"]:
        src=source/item["path"]
        assert src.is_file(),str(src)
        assert sha(src)==item["sha256"],"Changed frozen input: "+str(src)
        dest=stage/item["path"];dest.parent.mkdir(parents=True,exist_ok=True)
        if not dest.exists() or sha(dest)!=item["sha256"]: shutil.copyfile(src,dest)
    link=stage/"restored"
    if link.is_symlink(): assert link.resolve()==restored.resolve()
    elif link.exists(): raise RuntimeError("Audit layout restored entry is not the expected symlink")
    else: link.symlink_to(restored.resolve(),target_is_directory=True)
    snapshot=stage/"restored"/SNAP_REL
    assert sha(snapshot)==expected["snapshot_sha256"],"Frozen snapshot SHA mismatch"
    return snapshot

def run_command(cmd,cwd,log):
    begin=time.monotonic(); log.parent.mkdir(parents=True,exist_ok=True)
    with log.open("w") as f:
        p=subprocess.run([str(x) for x in cmd],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,env=dict(os.environ),check=False)
    if p.returncode:
        raise RuntimeError("Generator failed: "+str(cmd[1])+"\n"+log.read_text()[-6000:])
    return round(time.monotonic()-begin,3)

def construct(spec, stage, results, snapshot, generated):
    name,kind=spec["id"],spec["kind"]; outdir=results/name; outdir.mkdir(parents=True,exist_ok=True)
    output=outdir/"requests.json.gz"; side=None; csvside=None
    base=["--snapshot",snapshot,"--split",stage/SPLIT]
    code=stage/STUDY/"code"; py=sys.executable
    duration=0.; commands=[]
    def execute(cmd):
        nonlocal duration
        commands.append([str(x) for x in cmd]);duration+=run_command(cmd,stage,outdir/"generator.log")
    if kind=="blocks":
        cmd=[py,code/"design_blocks.py",*base,"--spec",stage/spec["spec"],"--out",output]
        for lab in spec["labels"]:cmd += ["--labels",stage/lab]
        execute(cmd)
    elif kind=="nested":
        execute([py,code/"design_nested_new2.py",*base,"--labels",stage/R_LABEL,"--spec",stage/STUDY/"assessment/NESTED_NEW2_SPEC.json","--freeze",stage/STUDY/"assessment/ASSESSMENT_FREEZE.json","--out",output])
    elif kind=="condition":
        execute([py,code/"design_condition_transfer.py",*base,"--labels",stage/F_LABEL,"--out",output])
    elif kind=="condition_phase":
        full=read(generated["condition_all"]); phase=spec["phase"]
        events=[e for e in full["events"] if e["phase"]==phase]
        keys={e[a+"_team_key"] for e in events for a in "ABC"}
        split=dict(full,events=events,requests=[r for r in full["requests"] if r["request_id"] in keys],
            links=[r for r in full["links"] if r["phase"]==phase],ledger=[r for r in full["ledger"] if r.get("phase")==phase])
        split["spec"]=dict(full["spec"],phase=phase);write(output,split)
    elif kind=="mixed":
        execute([py,code/"design_mixed_challenge.py",*base,"--labels",stage/F_LABEL,"--labels",stage/R_LABEL,"--phase",spec["phase"],"--out",output])
    elif kind=="ratio":
        execute([py,code/"design_ratio_grid.py",*base,"--labels",stage/F_LABEL,"--labels",stage/R_LABEL,"--out",output])
    elif kind=="ratio_replication":
        execute([py,code/"design_ratio_replication.py",*base,"--labels",stage/F_LABEL,"--labels",stage/R_LABEL,"--freeze",stage/STUDY/"ratio_grid/RATIO_REPLICATION_FREEZE.json","--old-requests",generated["ratio_discovery"],"--phase",spec["phase"],"--out",output])
    elif kind=="common":
        execute([py,stage/STUDY/"forward/common_panel/design_common_panel.py",*base,"--labels",stage/F_LABEL,"--manifest",stage/STUDY/"forward/method_manifest.json","--phase",spec["phase"],"--seed",spec["seed"],"--label-seed",2026102013,"--out",outdir])
        output=outdir/"common_requests.json.gz";side=outdir/"common_anchors.json.gz"
    elif kind=="history":
        execute([py,code/"design_history_panel.py",*base,"--out",outdir]);output=outdir/"history_requests.json.gz";side=outdir/"history_anchors.json.gz"
    elif kind=="baseline":
        execute([py,stage/STUDY/"independent/baseline/design_baseline.py","--out",outdir,"--budget",100000])
        output=outdir/"REQUESTS.json.gz";csvside=outdir/"EVENT_DESIGN.csv.gz"
    elif kind=="retained":
        shutil.copyfile(stage/spec["original"],output)
    else:raise ValueError(kind)
    return output,side,csvside,duration,commands

def verify_forward_labels(stage, results):
    import pandas as pd
    folder=stage/STUDY/"forward";sys.path.insert(0,str(folder))
    spec=importlib.util.spec_from_file_location("reproduction_build_forward",folder/"build_candidates.py")
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    fixed=pd.read_csv(folder/"worker_labels.csv.gz",keep_default_na=False)
    catalog=mod.define_candidates(pd.read_csv(folder/"features_train.csv.gz"))
    rebuilt=pd.DataFrame(catalog.rows)
    def rows(frame):
        out=[]
        for r in frame.to_dict("records"):
            out.append(dict(worker_id=str(r["worker_id"]),method_id=str(r["method_id"]),domain=str(r["domain"]),
                class_id=str(r["class_id"]),known=str(r["known"]).lower() in ["true","1","1.0"]))
        return out
    a,b=rows(fixed),rows(rebuilt)
    assert rows_sha(a)==rows_sha(b),"Forward classification changed when rebuilt from frozen history features"
    manifest=read(folder/"method_manifest.json")
    for mid,m in catalog.methods.items():
        old=manifest["methods"][mid]
        assert m["partition_sha256"]==old["partition_sha256"] and m["class_sizes"]==old["class_sizes"]
        assert sorted(m["known_workers"])==sorted(old["known_workers"])
    out=dict(status="reconstructed_equal",history_feature_sha256=sha(folder/"features_train.csv.gz"),
        frozen_labels_file_sha256=sha(folder/"worker_labels.csv.gz"),canonical_labels_sha256=rows_sha(a),
        rows=len(a),methods=len(catalog.methods),target_outcomes_read=False,
        boundary="Rebuilds all forward candidate labels from already independently audited history-only features. Does not rerun raw feature extraction or the reverse history pair learning.")
    write(results/"FORWARD_LABEL_RECONSTRUCTION.json",out);return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--package-root",type=Path,required=True)
    ap.add_argument("--restored",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--expected",type=Path,default=HERE/"DESIGN_FINGERPRINTS.json")
    ap.add_argument("--record-reference",action="store_true",help="Packaging author only: fingerprint original frozen requests without reading any fusion outcomes")
    ap.add_argument("--only",nargs="*",help="Optional named subset; the receipt states all omissions")
    ap.add_argument("--skip-forward-label-rebuild",action="store_true")
    a=ap.parse_args();root=a.package_root.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if a.record_reference:
        record_expected(root,a.expected);return
    expected=read(a.expected)
    stage=out/"portable_input";snapshot=stage_inputs(root,stage,a.restored,expected)
    selected=expected["designs"]
    if a.only:
        wanted=set(a.only)
        if any(x in wanted for x in ["condition_discovery","condition_assessment"]):wanted.add("condition_all")
        if any(x in wanted for x in ["ratio_new_members","ratio_assessment"]):wanted.add("ratio_discovery")
        unknown=wanted-{s["id"] for s in selected};assert not unknown,unknown
        selected=[s for s in selected if s["id"] in wanted]
    payload=read(snapshot)
    pools={p["pool_id"]:dict(reference_id=p["meta"]["reference_id"],origins={r["worker_id"]:r["origin"] for r in p["records"]}) for p in payload["images"]}
    del payload
    maps=known_maps(stage);results=out/"reconstructed";results.mkdir(exist_ok=True)
    receipt=dict(schema="actual_isolated_design_rebuild_audit_v1",started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        package_root=str(root),external_restored=str(a.restored.resolve()),staged_small_input_files=len(expected["required_files"]),
        snapshot_sha256=sha(snapshot),expected_manifest_sha256=sha(a.expected),designs=[],omitted_designs=[s["id"] for s in expected["designs"] if s not in selected],
        no_native_fusion_run=True,no_new_experiment=True)
    generated={}
    for spec in selected:
        name=spec["id"];print("Rebuilding "+name,flush=True)
        try:
            path,side,csvside,seconds,commands=construct(spec,stage,results,snapshot,generated)
            got=fingerprint(path,side,csvside)
            differences={k:dict(expected=spec["expected"].get(k),observed=got.get(k)) for k in set(spec["expected"])|set(got) if spec["expected"].get(k)!=got.get(k)}
            checks=check_event_members(path,pools,maps)
            status="retained_exact_request_equal" if spec["kind"]=="retained" else "reconstructed_equal"
            if differences:status="fingerprint_mismatch"
            row=dict(id=name,status=status,kind=spec["kind"],seconds=seconds,observed=got,semantic_member_checks=checks,differences=differences,commands=commands,
                reconstructed_request=str(path.relative_to(out)))
            if spec["kind"]=="retained":row["exact_file_sha_equal"]=sha(path)==spec["original_file_sha256"]
            generated[name]=path
        except Exception as exc:
            row=dict(id=name,status="failed",error=type(exc).__name__+": "+str(exc))
        receipt["designs"].append(row);write(out/"DESIGN_REBUILD_RECEIPT.json",receipt)
        print(json.dumps({k:row[k] for k in ["id","status","seconds"] if k in row},ensure_ascii=False),flush=True)
    if not a.skip_forward_label_rebuild:
        try:receipt["forward_label_rebuild"]=verify_forward_labels(stage,results)
        except Exception as exc:receipt["forward_label_rebuild"]=dict(status="failed",error=type(exc).__name__+": "+str(exc))
    else:receipt["forward_label_rebuild"]=dict(status="explicitly_not_run")
    good={"reconstructed_equal","retained_exact_request_equal"}
    receipt["all_selected_designs_equal"]=all(r["status"] in good for r in receipt["designs"])
    receipt["all_named_designs_covered"]=not receipt["omitted_designs"]
    receipt["finished_utc"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt["notes"]=["Fingerprints compare original full registered requests, not only successful teams or selected cases.",
        "Retained exact requests are clearly distinguished from regenerated designs.","Repeated teams across events, methods and phases do not increase independent image support.",
        "The staged restored symlink is an external prerequisite; do not package it or generated caches."]
    write(out/"DESIGN_REBUILD_RECEIPT.json",receipt)
    print(json.dumps(dict(all_selected_equal=receipt["all_selected_designs_equal"],designs=len(receipt["designs"]),omitted=receipt["omitted_designs"],forward_labels=receipt["forward_label_rebuild"]["status"]),ensure_ascii=False),flush=True)
    if not receipt["all_selected_designs_equal"] or receipt["forward_label_rebuild"]["status"]=="failed":sys.exit(1)

if __name__=="__main__":main()
