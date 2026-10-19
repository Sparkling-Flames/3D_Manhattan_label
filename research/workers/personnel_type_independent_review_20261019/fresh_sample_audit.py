import os,sys,json,gzip,pathlib,hashlib,collections,time
os.environ['OPENBLAS_NUM_THREADS']='1'
P=pathlib.Path('/workspace/shared/personnel_partA_audit_20261019/extracted/work_personnel_typing_A_20261019')
sys.path[:0]=['/workspace/shared/pro_inventory_20261019/runtime_deps',str(P/'events')]
import run_events as re
fe=re.fe
out=P.parents[1]/'independent_fresh'; out.mkdir(exist_ok=True)
fe.OUT=out
pools={p['pool_id']:p for p in re.pool_io.load_pools()}
reqs=re.pool_io.read(P/'events/REQUESTS.json.gz')['requests']
groups=collections.defaultdict(list)
for r in reqs:
 p=pools[r['pool_id']];groups[(p['meta'].get('difficulty'),r['k'])].append(r)
selected=[]
for key,rows in sorted(groups.items(),key=str):
 selected.extend(sorted(rows,key=lambda r:hashlib.sha256(r['request_id'].encode()).hexdigest())[:2])
# Explicit report failure/large-change cases, preselected separately from hash sample.
import csv
caseimgs={'uNb9QFRL6hY-60','q9vSo1VnCiC-30','VFuaQ6m2Qom-04'}
with gzip.open(P/'events/common_events.csv.gz','rt',encoding='utf-8-sig') as f:
 for r in csv.DictReader(f):
  if r.get('event_id') in {'Aevt_f99b413d697b78327906e786','Aevt_00ad805fb67507539ac62dc6','Aevt_e202c3387762f386bbb5ad7b'}:
   wanted={r['request_a'],r['request_b']};selected.extend(x for x in reqs if x['request_id'] in wanted)
selected=list({r['request_id']:r for r in selected}.values()); bypool=collections.defaultdict(list)
for r in selected:bypool[r['pool_id']].append(r)
receipts=[];comparisons=[]
for pid,rs in bypool.items():
 receipt=fe.run_pool(pools[pid],rs);receipts.append(receipt)
 old={r['request_id']:r for r in re.pool_io.read(P/'events/native_runs/pools'/pid/'request_results.json.gz')['results']}
 new=re.pool_io.read(out/'pools'/pid/'request_results.json.gz')['results']
 for r in new:
  o=old[r['request_id']]; diff={}
  for k in ['B8L2','D10','nodes','geometry_status','order_status','complete_evaluable','member_workers','reference_id','reference_version']:
   a,b=r.get(k),o.get(k)
   if isinstance(a,(float,int)) and not isinstance(a,bool) and isinstance(b,(float,int)):
    if abs(a-b)>1e-9:diff[k]=[a,b]
   elif a!=b:diff[k]=[a,b]
  comparisons.append({'request_id':r['request_id'],'diff':diff,'B8L2':r.get('B8L2'),'old_B8L2':o.get('B8L2')})
 print(pid,len(rs),receipt['new_fusions'],flush=True)
result={'selection':'2 SHA256-smallest requests per difficulty and k, plus 3 disclosed report case pairs','n_requests':len(selected),'receipts':receipts,'comparisons':comparisons,'mismatches':sum(bool(r['diff']) for r in comparisons),'new_fusions':sum(r['new_fusions'] for r in receipts),'exceptions':sum(len(r['exceptions']) for r in receipts)}
(out/'RESULT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('receipts','comparisons')}))
