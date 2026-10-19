#!/usr/bin/env python3
"""Package the completed Part A report/code/tables without mutating science.

Two data archives are independently assembled by package_data_zips.py.
Only expanded per-fold reverse probability tables are optional here: exact
classes, calibrations, all candidates and selected wide predictions remain.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, os, re, zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
OUT=ROOT.parent/'deliverables_personnel_A_20261019'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def classify(p):
    s=p.relative_to(ROOT).as_posix();parts=p.relative_to(ROOT).parts
    if '__pycache__' in parts or p.suffix=='.pyc':return False,'regenerable Python bytecode'
    if '.writing' in p.name or p.name.endswith('.lock'):return False,'unpublished temporary output or execution lock; never scientific input'
    if 'export_recovery' in parts:return False,'failed historical export preserved in local work; repair receipts and complete canonical exports are included'
    if parts[0]=='reverse' and p.name=='predictions.csv.gz' and 'folds' in parts:
        return False,'expanded all-candidate probability cache; reconstruct from saved classes/calibration and exact common events using reproducibility/reexport_reverse_predictions.py or the unified refit level; selected aliases are fully retained in assessment/EVENT_PREDICTIONS_WIDE.csv.gz'
    if parts[0]=='presentation' and parts[1] in ['release_cache','qa_runtime','qa_preview']:return False,'download or local browser-testing dependency cache; checked image subset, manifests, final canvases and viewer are included'
    if p.name=='personnel_types_part_a_preview.html':return False,'superseded development preview; final self-contained viewer retained'
    if parts[0]=='reproducibility' and p.name in ['PACKAGE_REPORT_CODE_MANIFEST.json','FINAL_DELIVERY_CHECKS.json','CODE_FILES_SHA256.json','package_report_code.log']:
        return False,'package-level receipt emitted after archive construction; saved beside ZIP and not recursively inside itself'
    return True,'deliver'

def candidates():
    wanted=[]
    for p in ROOT.iterdir():
        if p.is_file() and p.suffix in ['.py','.md','.html','.json']:wanted.append(p)
    for folder in ['input','forward','reverse','assessment','presentation','reproducibility']:
        wanted.extend(p for p in (ROOT/folder).rglob('*') if p.is_file())
    return sorted(set(wanted),key=lambda p:p.relative_to(ROOT).as_posix())

def check_file(p):
    rec={'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
    if p.suffix=='.gz':
        count=0
        with gzip.open(p,'rb') as f:
            for b in iter(lambda:f.read(2**20),b''):count+=len(b)
        rec.update(gzip_crc_full_read=True,uncompressed_bytes=count)
    elif p.suffix=='.json':
        json.loads(p.read_text(encoding='utf-8'));rec['python_json_readable']=True
    return rec

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--overwrite',action='store_true',help='replace only the named derived ZIP/receipt, never scientific files');a=ap.parse_args()
    OUT.mkdir(exist_ok=True)
    dest=OUT/'PartA_01_Report_Code_Tables.zip'
    if dest.exists() and not a.overwrite:raise SystemExit('Named derived ZIP already exists; use explicit --overwrite after checking intended publication.')
    # Exclude own post-run receipts before enumeration. No source deletions.
    include=[];omitted=[]
    for p in candidates():
        yes,reason=classify(p)
        if yes:
            if p.is_symlink():raise RuntimeError('Unexpected deliverable symlink '+str(p))
            include.append(p)
        elif 'package-level receipt' not in reason:
            if p.is_symlink():omitted.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.lstat().st_size,'symlink_target':os.readlink(p),'reason':reason})
            else:omitted.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p),'reason':reason})
    archive_omissions={'all_scientific_candidates_preserved':True,'all_selected_event_predictions_preserved':True,'omitted_files':omitted,
       'expanded_reverse_predictions_expected_rows':19779954,'expanded_reverse_predictions_expected_methods':69,
       'rebuild_expanded_predictions':'python work_personnel_typing_A_20261019/reproducibility/reexport_reverse_predictions.py --execute --output-dir /tmp/partA-reverse-predictions (new directory); use repeatable --fold to select folds, otherwise all 22; alternatively run the unified refit level in a new workspace',
       'source_images':'7 case originals retained; release archives omitted; per-image/asset SHA and exact download descriptions in presentation/'}
    save(HERE/'OMITTED_DERIVED_CACHES.json',archive_omissions)
    include=[p for p in candidates() if classify(p)[0]]
    files=[]
    for i,p in enumerate(include,1):
        files.append(check_file(p))
        if i%100==0:print('checked',i,'/',len(include),flush=True)
    # Full package manifest (except itself) is included inside the archive.
    save(HERE/'CODE_FILES_SHA256.json',{'algorithm':'SHA256','root':ROOT.name,'files':files,'self_excluded':True})
    manifest_path=HERE/'CODE_FILES_SHA256.json'
    include=[p for p in include if p!=manifest_path]+[manifest_path]
    include.sort(key=lambda p:p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for i,p in enumerate(include,1):
            arc=ROOT.name+'/'+p.relative_to(ROOT).as_posix();z.write(p,arcname=arc)
            if i%150==0:print('packed',i,'/',len(include),flush=True)
    with zipfile.ZipFile(dest) as z:
        names=z.namelist();assert len(names)==len(set(names))==len(include)
        assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts and n.startswith(ROOT.name+'/') for n in names)
        bad=z.testzip();assert bad is None,bad
        expected={ROOT.name+'/'+p.relative_to(ROOT).as_posix():p for p in include}
        for n in names:
            h=hashlib.sha256()
            with z.open(n) as f:
                for b in iter(lambda:f.read(2**20),b''):h.update(b)
            assert h.hexdigest()==sha(expected[n]),n
    assert dest.stat().st_size<450*2**20,'Split archive before publication rather than silently drop results'
    receipt={'created_utc':datetime.now(timezone.utc).isoformat(),'zip':dest.name,'zip_bytes':dest.stat().st_size,'zip_sha256':sha(dest),
       'included_file_count':len(include),'uncompressed_bytes':sum(p.stat().st_size for p in include),'omitted_file_count':len(omitted),
       'gzip_files_full_crc_read':sum('gzip_crc_full_read'in f for f in files),'json_files_python_read':sum('python_json_readable'in f for f in files),
       'zip_full_crc_pass':True,'zip_per_file_sha_match_source':True,'relative_unique_safe_paths':True,'all_scientific_methods_unchanged':True,
       'manifest_inside':'reproducibility/CODE_FILES_SHA256.json','omissions_inside':'reproducibility/OMITTED_DERIVED_CACHES.json'}
    save(OUT/'PACKAGING_REPORT_CODE_MANIFEST.json',receipt);save(HERE/'PACKAGE_REPORT_CODE_MANIFEST.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
