from pathlib import Path
import concurrent.futures as cf,gzip,json,hashlib,urllib.request,urllib.parse,time
W=Path('/workspace/scratch/fe955c3c772c/personnel_v21_research_20261029'); R=W.parent/'HOHONET_v21_20261029'
commit='a476461d7ede8db95da43de4139e612c05e618bc'
tree=json.load(gzip.open(W/'source/GITHUB_TREE_SIZES.json.gz','rt'))['tree']
meta={r['path']:r for r in tree if r.get('type')=='blob'}
paths=['research/workers/personnel_mixture_comparison_20261022/configurations/'+x for x in ['PANELS_USED.csv','PANEL_TEAMS.csv.gz','TEAM_MEMBERS.csv.gz','ENDPOINT_OUTCOMES_manual.csv.gz','ENDPOINT_OUTCOMES_semi.csv.gz']]
paths+=['research/workers/dstruct_composition_bridge_20261026/build_bridge.py','research/data/releases/v2.1/composition_variance/CHECKS.json']
paths += [r['path'] for r in tree if r.get('type')=='blob' and r['path'].startswith('research/data/releases/v2.1/composition_rescore/') and ('__manual__' in r['path'] or r['path'].endswith('REUSED_ENDPOINTS.jsonl.gz'))]
paths=sorted(set(paths));(W/'source/COMPOSITION_FETCH_PLAN.json').write_text(json.dumps(paths,indent=2))
def fetch(path):
 p=R/path;m=meta.get(path,{});b=p.read_bytes() if p.exists() else b''
 if not (b and len(b)==m.get('size') and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==m.get('sha')):
  u='https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/'+commit+'/'+urllib.parse.quote(path)
  for i in range(4):
   try:
    with urllib.request.urlopen(u,timeout=90) as r:b=r.read()
    if m:assert len(b)==m['size'] and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==m['sha'],path
    p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.downloading');tmp.write_bytes(b);tmp.replace(p);break
   except Exception:
    if i==3:raise
    time.sleep(i+1)
 return {'path':path,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'commit':commit}
rows=[]
with cf.ThreadPoolExecutor(max_workers=12) as ex:
 for r in ex.map(fetch,paths):
  rows.append(r)
  if len(rows)%100==0:print(f'{len(rows)}/{len(paths)} files',flush=True)
(W/'source/COMPOSITION_FETCH_RECEIPT.json').write_text(json.dumps(rows,indent=2))
print(json.dumps({'files':len(rows),'bytes':sum(r['bytes'] for r in rows),'done':True}),flush=True)
