import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'deliverables';selected=set()
for stage in ['size_paths','large_team_ac_tail']:
    selected.update(p for p in (ROOT/'design'/stage).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for name in ['EVENT_METRICS.csv.gz','COMPLETION.json','NATIVE_ENDPOINT_SCALARS.csv.gz','NATIVE_ENDPOINT_GEOMETRY.json.gz','NATIVE_COMPLETION.json','NATIVE_REQUEST_COVERAGE.json','NATIVE_RUN_PROGRESS.json']:
        p=ROOT/'results'/stage/name
        if p.exists():selected.add(p)
    for p in (ROOT/'analysis'/stage).rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or p.suffix in ('.writing','.tmp','.txt'):continue
        if p.stat().st_size<1100000 or p.name in ['CURVE_BY_IMAGE.csv.gz','CURVE_BY_BUILDING.csv.gz','PATH_BASELINE_CHANGES.csv.gz','PATH_STEP_CHANGES.csv.gz','STEP_BY_IMAGE.csv.gz','FROM_N10_BY_IMAGE.csv.gz','THRESHOLD_GROUP_BY_IMAGE.csv.gz','CURVE_BY_K_BY_IMAGE.csv.gz','CURVE_BY_K_BY_BUILDING.csv.gz','FIXED_N35_BY_N_BY_IMAGE.csv.gz','FIXED_N35_BY_N_BY_BUILDING.csv.gz','FROM_STRICT_TAIL_EXACT.csv.gz','STEP_EXACT.csv.gz']:
            selected.add(p)
selected.update(ROOT/x for x in ['STAGE05_README.md','run_native.py','measure_events.py','measure_ac.py','package_stage05.py'])
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(4*1024*1024),b''):h.update(x)
 return h.hexdigest()
manifest=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(selected)]
archive=OUT/'HOHONET_换类区分度_阶段05_固定块人数路径与28人换7人_20261025.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
 for p in sorted(selected):z.write(p,p.relative_to(ROOT),compress_type=zipfile.ZIP_STORED if p.suffix in ('.gz','.png') else zipfile.ZIP_DEFLATED)
 z.writestr('PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
receipt={'archive':str(archive),'files':len(manifest),'bytes':archive.stat().st_size,'sha256':sha(archive),'status':'both_designs_all_registered_events_computed'}
(OUT/'STAGE05_PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
(OUT/'UPLOAD_STAGE05.json').write_text(json.dumps({'uploads':[{'local_path':str(archive),'purpose':'create_library_file','library_artifact_type':'other'},{'local_path':str(ROOT/'analysis/size_paths/FINDINGS.md'),'purpose':'create_library_file','library_artifact_type':'report'},{'local_path':str(ROOT/'analysis/large_team_ac_tail/FINDINGS.md'),'purpose':'create_library_file','library_artifact_type':'report'}]},ensure_ascii=False))
print(json.dumps(receipt,ensure_ascii=False))
