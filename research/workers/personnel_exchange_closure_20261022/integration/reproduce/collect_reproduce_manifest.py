#!/usr/bin/env python3
"""Record actual imported frozen code and explicit reproduction inputs.

Imports setup_engine to locate modules; never calls fusion or quality scoring.
Only this study's code directories and targeted input paths are enumerated.
"""
from __future__ import annotations
import csv
import gzip
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import sys
import zipfile

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
ROOT=STUDY.parents[2]
WORKSPACE=ROOT.parent
for name in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[name]="1"
sys.path.insert(0,str(STUDY))
import run_native_closure as runner


def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def main():
    runner.configure()
    fe,fr,sg,corner=runner.gs.setup_engine()
    gs=runner.gs
    paths={}
    def add(path,role,usage,version="",origin=""):
        p=Path(path).resolve()
        row=paths.setdefault(p,dict(role=set(),usage=set(),version=set(),discovery=set()))
        for key,value in [("role",role),("usage",usage),("version",version),("discovery",origin)]:
            if value:row[key].add(value)
    code_folders=[STUDY,STUDY/"manual_joint",STUDY/"structure",STUDY/"semi",STUDY/"mechanisms",HERE,STUDY/"integration/historical"]
    for folder in code_folders:
        for p in folder.glob("*.py"):
            add(p,"new_study_code","registered design / aggregation / delivery helper","closure_20261022","targeted code folder")
    for name,module in sorted(sys.modules.items()):
        file=getattr(module,"__file__",None)
        if not file:continue
        p=Path(file).resolve()
        if p.suffix==".py" and p.is_relative_to(ROOT):
            add(p,"runtime_imported_code","frozen event, geometry, fusion or quality dependency","actual setup_engine import","sys.modules:"+name)
    for name, obj in [("fusion_engine",fe),("fusion_runner",fr),("summarize_grid",sg),("corner_distance",corner)]:
        p=inspect.getsourcefile(obj)
        add(p,"frozen_core_module",name,"preserved v2 contract","setup_engine returned object __file__/inspect")
    snapshot=gs.FUSION/"INPUT_SNAPSHOT.json.gz"
    with gzip.open(snapshot,"rt",encoding="utf8") as f:
        metadata=json.load(f)
    contract={k:v for k,v in metadata.items() if k!="images"}
    add(snapshot,"frozen_real_input","raw-answer/reference/ring/eligibility source",contract.get("schema",""),"gs.FUSION")
    add(fe.ENGINE/"measurement_engine.zip","frozen_score_archive","B8L2 primary; D10 sensitivity","b8l2_shared_v6_20261016","fusion_engine.ENGINE")
    add(fe.ENGINE/"working_models.py","frozen_score_configuration","working quality formulas/parameters","b8l2_shared_v6_20261016","fusion_engine.ENGINE")
    add(runner.frozen.native.TIME_SOURCE,"recorded_time_input","existing record seconds; source labels retained","not newly measured production time","native.TIME_SOURCE")
    v3=ROOT/"research/workers/personnel_useful_taxonomy_v3_20261021"
    prior=ROOT/"research/workers/personnel_effective_exchange_conditions_20261022"
    old=ROOT/"research/workers/personnel_global_composition_20261021"
    for p,role,usage in [
        (v3/"taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz","inherited_lobo_labels","fold-specific classes, historical features and missing support"),
        (v3/"composition/PANELS.csv","inherited_personnel_domains","formal eligible worker domains/panels"),
        (prior/"screening/CLASS_TRAINING_ROLE_MAP.csv.gz","inherited_structure_role_map","training-only semantic alignment of fold-specific structure labels"),
        (old/"multivariate/continuous_features_lobo.csv.gz","continuous_lobo_baseline","historical Q/T and covariates used by event kernels"),
        (v3/"integration/PHASE1_PHASE2_PHASE3_DOMAIN_COVERAGE_26x2.csv","historical_coverage_reference","26 variable-domain subsets x 2 conditions; historical phase identities"),
        (prior/"joint_exchange/ALL_USED_ENDPOINT_SCALARS.csv.gz","prior_endpoint_cache","prior exact-team reuse and two Semi QT controls"),
        (prior/"joint_exchange/ALL_USED_ENDPOINT_GEOMETRY.csv.gz","prior_endpoint_cache","paired previous geometry"),
    ]:add(p,role,usage,"historical input preserved","explicit registration/evaluator reference")
    selected={
        "manual_joint":["INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz","TRAINING_CLASS_CENTERS.csv","ACTUAL_MEMBER_LABELS.csv.gz","INPUT_NEW_ONLY_DOMAINS.csv","EVENTS_REGISTERED.csv.gz","POLICIES_REGISTERED.csv.gz","TEAM_REQUEST.csv.gz","DESIGN_FREEZE.json"],
        "manual_joint/phase_b_highq_slower":["EVENTS_REGISTERED.csv.gz","POLICIES_REGISTERED.csv.gz","TEAM_REQUEST.csv.gz","DESIGN_FREEZE.json"],
        "structure":["CLASS_LABELS_REUSED.csv.gz","CLASS_ROLES_REUSED.csv","ALL_EVENTS_REGISTERED.csv.gz","ALL_ENDPOINT_REQUESTS.csv.gz","M_PATH_NEW_ENDPOINT_REQUESTS.csv.gz","DESIGN_FREEZE.json"],
        "semi":["INHERITED_LABELS_LOBO.csv.gz","INHERITED_LABELS_LOBO_WITH_UNKNOWN.csv.gz","TRAINING_CLASS_CENTERS.csv","EVENTS_REGISTERED_ALL.csv.gz","CONTINUOUS_QT_CONTROLS.csv.gz","CONFIGURATION_COMPLETION_QT_CONTROLS.csv.gz","TEAM_REQUEST.csv.gz","CONFIGURATION_COMPLETION_TEAM_REQUEST.csv.gz","DESIGN_FREEZE.json","CONFIGURATION_COMPLETION_FREEZE.json"],
    }
    for directory,names in selected.items():
        for name in names:add(STUDY/directory/name,"new_frozen_input","exact design/labels/request; no re-selection needed","closure_20261022","explicit new evaluator/design input")
    for p in sorted((STUDY/"native/batches").glob("*/REQUESTS.csv.gz")):
        add(p,"frozen_endpoint_request","restore exact batch projection or optional native replay","closure_20261022","native/batches/*/REQUESTS.csv.gz")
    for p in sorted((STUDY/"native").glob("*_BATCH_PLAN.csv")):
        add(p,"frozen_batch_plan","optional native runner run-all order","closure_20261022","native/*_BATCH_PLAN.csv")
    for name in ["ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz","ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz","ENDPOINT_SOURCE_INDEX.csv.gz","DELIVERY_RECEIPT.json"]:
        add(STUDY/"delivery/endpoints"/name,"delivered_unique_endpoint_input","preferred complete no-fusion reaggregation input","closure_20261022/v2","deduplicated delivery contract")
    for name in ["ADDITIONAL_CACHE_PAIRS.json","native/additional_reused/ENDPOINT_SCALARS.csv.gz","native/additional_reused/ENDPOINT_GEOMETRY.csv.gz"]:
        add(STUDY/name,"optional_native_reuse_input","small exact historical cache needed only by optional original native replay","closure_20261022","run_native_closure.prepare_cache")
    for name in ["HOHONET_v3_复现代码与必要小输入_20261021.zip","CORE_RESEARCH_CODE_AND_SMALL_EVIDENCE.zip","SMALL_ANALYSIS_INPUTS.zip"]:
        add(WORKSPACE/"source_recovery/library"/name,"historical_code_or_small_input_package","restore original relative paths when absent; keep earlier stage identity","prior research package","existing recovered source catalogue")
    for name in ["REPRODUCE_ZH.md","restore_endpoint_batches.py"]:
        add(HERE/name,"reproduction_delivery","portable readme/helper","closure_20261022","this handoff")
    records=[]
    for p,info in sorted(paths.items(),key=lambda x:str(x[0])):
        record={k:" | ".join(sorted(v)) for k,v in info.items()}
        record.update(path=str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
            absolute_local_path=str(p),exists=p.is_file(),bytes=p.stat().st_size if p.is_file() else "",
            sha256=sha(p) if p.is_file() else "")
        records.append(record)
    out=HERE/"INPUT_CODE_MANIFEST.csv"
    fields=["role","path","absolute_local_path","exists","bytes","sha256","version","usage","discovery"]
    with out.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
    libraries={}
    for name in ["numpy","pandas","scipy","shapely","scikit-learn","matplotlib","Pillow","tqdm","imageio"]:
        try:libraries[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:libraries[name]="not installed"
    with zipfile.ZipFile(fe.ENGINE/"measurement_engine.zip") as archive:
        score_members=archive.namelist()
    environment=dict(python=sys.version,platform=platform.platform(),libraries=libraries,
        threads={k:os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS")},
        repository_main_and_PR23_merge_commit="8bfd3e476bd5ae6edc1424e2c8ea07dd2f69a235",
        prior_v3_source_main_commit="324dba44d0a82d9d64a62965f2e549ee05165417",
        snapshot_contract=contract,working_fusion_gap=fe.WORKING_GAP,
        score_archive_members=score_members,
        native_fusion_calls=0,quality_scoring_calls=0,
        path_discovery="actual setup_engine imports plus explicit study-code/input paths; no whole-repository scan",
        note="Archive/file hashes are the exact execution identity. v3 names identify a research round; underlying data are v2.")
    (HERE/"ENVIRONMENT_AND_CONTRACT.json").write_text(json.dumps(environment,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    receipt=dict(status="complete",files=len(records),missing=[r["path"] for r in records if not r["exists"]],
        manifest_sha256=sha(out),native_fusion_calls=0,quality_scoring_calls=0,
        imported_repo_python_files=sum("runtime_imported_code" in r["role"] for r in records),
        code_discovery="actual loaded modules plus this study's direct code folders",
        prior_package_identity_preserved=True)
    (HERE/"MANIFEST_RECEIPT.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=="__main__":main()
