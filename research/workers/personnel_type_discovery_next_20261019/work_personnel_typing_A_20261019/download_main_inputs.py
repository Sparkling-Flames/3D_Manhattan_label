#!/usr/bin/env python3
"""Download immutable, public GitHub source and compact core, preserving bytes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib, json, time, urllib.request, urllib.parse

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / 'main_personnel_A_20261019'
OUT = ROOT / 'work_personnel_typing_A_20261019' / 'input'
PIN = 'dafa73ac7d8ada9a7f5c0e483d695adcbd916550'
PREFIX = 'research/workers/pro_personnel_v2_archive_20261019/'
BASE = f'https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/{PIN}/'
tree = json.loads((OUT/'github_tree.json').read_text())['tree']
sources = json.loads((DEST/PREFIX/'SOURCE_FILES.json').read_text())
source_map = {r['path']:r for r in sources}
files = {r['path']:r for r in tree if r['type']=='blob' and (r['path'].startswith(PREFIX) or r['path'] in source_map)}

def fetch(item):
    path, row = item
    dest = DEST/path
    data = dest.read_bytes() if dest.is_file() else None
    for attempt in range(5):
        try:
            if data is None:
                with urllib.request.urlopen(BASE+urllib.parse.quote(path), timeout=120) as r:
                    data = r.read()
            blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            sha = hashlib.sha256(data).hexdigest()
            if blob != row['sha']:
                raise ValueError('git blob checksum mismatch: '+path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return {'path':path,'bytes':len(data),'sha256':sha,'git_blob':blob,'frozen_source':path in source_map,'matches_archive_source':sha == source_map[path]['sha256'] if path in source_map else None}
        except Exception:
            data = None
            if attempt==4:
                raise
            time.sleep(min(1+attempt,4))

items = sorted(files.items(), key=lambda x: (0 if any(v in x[0] for v in ['fusion_engine.py','compare_fusions.py','pool_io.py','INPUT_SNAPSHOT','REQUESTS_INITIAL','assignments.csv','records_geometry.csv','records_flat.csv','run_profiles.py']) else 1, x[1]['size']))
rows = []
start=time.time()
with ThreadPoolExecutor(16) as ex:
    futures={ex.submit(fetch,r):r[0] for r in items}
    for i,f in enumerate(as_completed(futures),1):
        rows.append(f.result())
        if i%150==0:
            print(json.dumps({'completed':i,'total':len(files),'seconds':round(time.time()-start,1)}),flush=True)
receipt={'main_commit':PIN,'bytes':sum(r['bytes'] for r in rows),'files':sorted(rows,key=lambda x:x['path']),'elapsed_seconds':time.time()-start,'collection_pipeline_reproduced':False}
(OUT/'MAIN_DOWNLOAD_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'complete':len(rows),'bytes':receipt['bytes'],'seconds':round(receipt['elapsed_seconds'],1)}),flush=True)
