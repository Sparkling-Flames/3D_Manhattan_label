"""Package completed effect batches, keeping endpoints separate from events."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'deliverables';OUT.mkdir(exist_ok=True)

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(4*1024*1024),b''):h.update(x)
 return h.hexdigest()

def pack(name,files):
 files=sorted(set(files)|{ROOT/'STAGE04_README.md'})
 records=[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
 dest=OUT/(name+'.zip')
 with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
  for p in files:z.write(p,p.relative_to(ROOT),compress_type=zipfile.ZIP_STORED if p.suffix in ('.gz','.zip','.png') else zipfile.ZIP_DEFLATED)
  z.writestr('PACKAGE_MANIFEST.json',json.dumps(records,ensure_ascii=False,indent=2))
 return {'archive':str(dest),'files':len(files),'bytes':dest.stat().st_size,'sha256':sha(dest)}

def stagefiles(stages):
 fs=[]
 for s in stages:
  complete=json.loads((ROOT/'results'/s/'COMPLETION.json').read_text());assert complete['complete']
  fs.extend([ROOT/'results'/s/'EVENT_METRICS.csv.gz',ROOT/'results'/s/'COMPLETION.json'])
  fs.extend(p for p in (ROOT/'design'/s).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
 return fs+[ROOT/'run_native.py',ROOT/'measure_events.py',ROOT/'register_exchange.py']

receipts=[]
receipts.append(pack('HOHONET_换类区分度_阶段04A1_前向扩展与7选6完整事件_20261025',stagefiles(['confirm','target_omissions'])))
receipts.append(pack('HOHONET_换类区分度_阶段04A2_反推四方法完整事件_20261025',stagefiles(['reverse_screen','reverse_confirm'])))
meta=[ROOT/'results/batch02'/p for p in ['COMPLETION.json','REQUEST_COVERAGE.json','RUN_PROGRESS.json']]
receipts.append(pack('HOHONET_换类区分度_阶段04B_202694端点标量_20261025',meta+[ROOT/'results/batch02/ENDPOINT_SCALARS.csv.gz']))
receipts.append(pack('HOHONET_换类区分度_阶段04C_202694端点几何_20261025',meta+[ROOT/'results/batch02/ENDPOINT_GEOMETRY.json.gz']))
(OUT/'STAGE04_PACKAGE_RECEIPTS.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
(OUT/'UPLOAD_STAGE04.json').write_text(json.dumps({'uploads':[{'local_path':x['archive'],'purpose':'create_library_file','library_artifact_type':'other'} for x in receipts]},ensure_ascii=False))
print(json.dumps(receipts,ensure_ascii=False))
