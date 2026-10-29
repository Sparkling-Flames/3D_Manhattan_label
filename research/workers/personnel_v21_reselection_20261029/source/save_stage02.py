from pathlib import Path
import zipfile,json,hashlib,gzip,os
w=Path('/workspace/scratch/fe955c3c772c/personnel_v21_research_20261029')
exclude={'MAIN41_LABELS_ALL_LOBO.csv.gz','MAIN41_FROZEN_RECEIPT.json','BASELINE20_LABELS_ALL_LOBO.csv.gz','FORWARD33_LABELS_ALL_LOBO.csv.gz','build.log','target_rfuse_build.log','FILE_MANIFEST.json'}
files=[]
for root in ['classification','stage02','experiment']:
 for p in (w/root).rglob('*'):
  if not p.is_file() or '__pycache__' in p.parts or p.name in exclude or p.name.endswith(('.log','.tmp','.writing','.pyc')):continue
  rel=p.relative_to(w)
  if root=='classification' and ('folds' in rel.parts or 'inputs' in rel.parts):continue
  if root=='experiment' and not (p.suffix=='.py' and len(rel.parts)==2):continue
  files.append(p)
manifest=[]
for p in files:
 if p.name.endswith('.gz'):
  with gzip.open(p,'rb') as f:
   while f.read(1024*1024):pass
 b=p.read_bytes();manifest.append({'path':str(p.relative_to(w)),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(w/'stage02/FILE_MANIFEST.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False));files.append(w/'stage02/FILE_MANIFEST.json')
out=w/'deliverables/HOHONET_v21_阶段02_45套候选名单与形成代码_20261029.zip';tmp=out.with_suffix('.writing')
with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p in sorted(files):z.write(p,str(p.relative_to(w)))
with tmp.open('rb') as f:os.fsync(f.fileno())
tmp.replace(out)
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(set(z.namelist()))
receipt={'file':str(out),'bytes':out.stat().st_size,'files':len(files),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'stage':'candidate_labels_frozen_before_team_outcomes','methods':45,'folds':23,'labels':64170,'actual_complete':True}
(w/'deliverables/STAGE02_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
req={'uploads':[{'local_path':str(out),'purpose':'create_library_file','library_artifact_type':'other'},{'local_path':str(w/'stage02/CANDIDATE_FORMATION_AND_SCOPE_ZH.md'),'purpose':'create_library_file','library_artifact_type':'report'},{'local_path':str(w/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz'),'purpose':'create_library_file','library_artifact_type':'other'}]}
(w/'deliverables/UPLOAD_STAGE02.json').write_text(json.dumps(req,ensure_ascii=False));print(json.dumps(receipt,ensure_ascii=False))
