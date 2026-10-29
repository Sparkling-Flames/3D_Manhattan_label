from pathlib import Path
import gzip,hashlib,json,os,zipfile
w=Path(__file__).resolve().parents[1];out=w/'deliverables';out.mkdir(exist_ok=True)
assert json.loads((w/'analysis/global_screen_summary/SUMMARY_RECEIPT.json').read_text())['events']==69485
assert json.loads((w/'analysis/global_screen_compact/COMPLETE.json').read_text())['full_event_row_coverage']
core=[
 'stage05','classification/MAIN45_LABELS_ALL_LOBO.csv.gz','classification/MAIN45_FROZEN_RECEIPT.json','classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',
 'experiment/global_screen_design/EVENTS_EXACT.csv.gz','experiment/global_screen_design/REQUESTS.csv.gz','experiment/global_screen_design/DESIGN.json','experiment/global_screen_design/FROZEN_REGISTRATION_INPUTS.json','experiment/global_screen_design/EVENT_SEAT_FRACTIONS.csv.gz',
 'experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz','experiment/global_screen_endpoints/CUMULATIVE_COMPLETION.json','experiment/global_screen_endpoints/RUN_PLAN.json',
 'analysis/global_screen_compact/EVENT_EFFECTS_COMPLETE.csv.gz','analysis/global_screen_compact/PAIR_GEOMETRY.csv.gz','analysis/global_screen_compact/EVENT_PAIR_LINKS.csv.gz','analysis/global_screen_compact/ENDPOINT_REFERENCE_DIAGNOSTICS.csv.gz','analysis/global_screen_compact/COMPLETE.json','analysis/global_screen_compact/OVERALL_COUNTS.json',
 'analysis/global_screen/MEASUREMENT_RECEIPT.json','targets/POOL_TARGET_CONDITIONS.csv','source/RUNTIME_VERSIONS.json',
 'deliverables/GLOBAL_ENDPOINT_ALL_BATCHES_COVERAGE.json','stage01/OLD_FORMATION_AND_SELECTION_ZH.md','stage01/OLD_26_DOMAIN_SUBSET_STAGE_COUNTS.csv','stage01/old_sources/DOMAIN_SUBSET_COVERAGE_26x2.csv','stage01/old_sources/DOMAIN_COVERAGE_RETRIEVAL.json']
core += [str(p.relative_to(w)) for p in (w/'experiment').glob('*.py')]
core += [str(p.relative_to(w)) for p in (w/'analysis').glob('*.py')]
core += ['experiment/REPRODUCTION_COMMANDS.md','experiment/FOCUSED_DESIGN_CONTRACT.md']
summ=['analysis/global_screen_summary','analysis/global_size_paths','experiment/global_screen_size_paths','experiment/capacity_main45_manual','experiment/global_screen_capacity/SCREEN_POOL_FRAME.csv','experiment/global_screen_design/REGISTERED_COVERAGE.csv.gz','experiment/global_screen_design/METHOD_N_M_REGISTERED_CAPACITY.csv','experiment/focused_selection']

def pack(name,entries):
 files={}
 for rel in entries:
  p=w/rel
  if not p.exists():raise FileNotFoundError(p)
  for f in (p.rglob('*') if p.is_dir() else [p]):
   if f.is_file() and '__pycache__' not in f.parts and not f.name.endswith(('.tmp','.writing','.log','.pyc')):files[str(f.relative_to(w))]=f
 manifest=[{'path':r,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for r,f in sorted(files.items())]
 dest=out/name;tmp=dest.with_suffix('.writing')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
  for r,f in sorted(files.items()):z.write(f,r,compress_type=zipfile.ZIP_STORED if f.suffix=='.gz' else zipfile.ZIP_DEFLATED)
  z.writestr('STAGE05_PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
 with tmp.open('rb') as h:os.fsync(h.fileno())
 tmp.replace(dest)
 with zipfile.ZipFile(dest) as z:
  assert len(z.namelist())==len(set(z.namelist())) and z.testzip() is None
  for n in z.namelist():
   if n.endswith('.gz'):gzip.decompress(z.read(n))
 rec={'file':str(dest),'bytes':dest.stat().st_size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'files':len(files)+1,'zip_crc_ok':True,'gzip_readable':True}
 print(json.dumps(rec,ensure_ascii=False),flush=True);return rec

r=[pack('HOHONET_v21_阶段05A_全局严格事件与去重端点标量_20261029.zip',core),pack('HOHONET_v21_阶段05B_45法全比较与规模路径_20261029.zip',summ)]
(out/'STAGE05_RECEIPTS.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
(out/'UPLOAD_STAGE05.json').write_text(json.dumps({'uploads':[{'local_path':x['file'],'purpose':'create_library_file','library_artifact_type':'other'} for x in r]+[{'local_path':str(w/'stage05/README.md'),'purpose':'create_library_file','library_artifact_type':'report'},{'local_path':str(w/'stage05/ALL7356_CONDITIONS_KEY_RESULTS.csv'),'purpose':'create_library_file','library_artifact_type':'other'}]},ensure_ascii=False))
