"""Read-only, commit-pinned public repository input retrieval; verifies Git blob hashes."""
import concurrent.futures, hashlib, json, pathlib, time, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMIT = '82c6164b0d4630de5316199c92aa405930973168'
DEST = ROOT / 'repo_main_20261019'
TREE = json.loads((ROOT/'work_v2_20261019/input/github_tree.json').read_text())['tree']
PREFIXES = ['research/statistics/v2_evidence_audit_20261019/',
 'research/statistics/v2_integrated_analysis_20261019/',
 'research/workers/pro_personnel_v2_20261019/']
EXACT = ['docs/thesis_main/v2数据研究台与Pro推进_20261019.md',
 'docs/thesis_main/Pro_v2人员细类与反向分簇研究提示词_20261019.md',
 'research/statistics/b8l2_shared_v6_20261016/inputs/measurement_engine.zip',
 'research/statistics/b8l2_shared_v6_20261016/inputs/working_models.py']

def selected(x):
 p=x['path']
 return x['type']=='blob' and (any(p.startswith(z) for z in PREFIXES) or p in EXACT or
   p.endswith('AGENTS.md') or (p.startswith('tools/thesis_main/') and p.endswith(('.py','.js'))))

def fetch(x):
 p=DEST/x['path'];p.parent.mkdir(parents=True,exist_ok=True)
 def digest(b): return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
 if p.exists() and digest(p.read_bytes())==x['sha']:
  b=p.read_bytes();status='verified_existing'
 else:
  url='https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/'+COMMIT+'/'+urllib.parse.quote(x['path'],safe='/')
  for attempt in range(4):
   try:
    b=urllib.request.urlopen(url,timeout=45).read()
    if len(b)!=x['size'] or digest(b)!=x['sha']: raise ValueError('Git blob content mismatch: '+x['path'])
    p.write_bytes(b);status='downloaded';break
   except Exception:
    if attempt==3: raise
    time.sleep(1+attempt)
 return {'path':x['path'],'bytes':len(b),'git_blob_sha1':x['sha'],'sha256':hashlib.sha256(b).hexdigest(),'status':status}

if __name__=='__main__':
 items=[x for x in TREE if selected(x)];results=[]
 print(json.dumps({'commit':COMMIT,'files':len(items),'bytes':sum(x['size'] for x in items)}),flush=True)
 # Core evidence precedes optional reusable code, so readers can start promptly.
 items.sort(key=lambda x:(0 if any(x['path'].startswith(z) for z in PREFIXES) or x['path'] in EXACT else 1,x['path']))
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
  futures={ex.submit(fetch,x):x for x in items}
  for f in concurrent.futures.as_completed(futures):
   try: results.append(f.result())
   except Exception as e:
    results.append({'path':futures[f]['path'],'error':str(e)})
   if len(results)%50==0: print('verified',len(results),flush=True)
 manifest={'commit':COMMIT,'tree_sha':'b372f4bbf0b27f422de853c375dd99d6ec829ab4','files':sorted(results,key=lambda x:x['path'])}
 (ROOT/'work_v2_20261019/input/DOWNLOAD_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 failures=[x for x in results if 'error' in x]
 print(json.dumps({'complete':len(results),'failures':failures},ensure_ascii=False),flush=True)
 if failures: raise SystemExit(1)
