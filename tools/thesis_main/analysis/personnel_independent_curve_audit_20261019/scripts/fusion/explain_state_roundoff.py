import json,sys
from pathlib import Path
B=Path(__file__).resolve().parents[2]/'extracted/work_v2_20261019/fusion';O=Path(__file__).resolve().parent
sys.path.insert(0,str(B));import fusion_engine as f
from pool_io import read
r=json.loads((O/'SAVED_TEAM_REPLAY.json').read_text());pools={p['pool_id']:p for p in f.load_pools()};diff=[]
def compare(a,b,path=''):
 if type(a)!=type(b):diff.append(dict(path=path,a=a,b=b,type_mismatch=True));return
 if isinstance(a,dict):
  if a.keys()!=b.keys():diff.append(dict(path=path,keys_mismatch=True));return
  for k in a:compare(a[k],b[k],path+'/'+str(k))
 elif isinstance(a,list):
  if len(a)!=len(b):diff.append(dict(path=path,length_mismatch=True));return
  for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
 elif a!=b:diff.append(dict(path=path,a=a,b=b,abs_difference=abs(a-b) if isinstance(a,(int,float)) else None))
rows=[]
for row in r['rows']:
 if row['state_exact_equal']:continue
 p=pools[row['pool_id']];req=next(x for x in read(B/'pools'/p['pool_id']/'requests.json.gz')['requests'] if x['request_id']==row['request_id']);lookup={a['worker_id']:a for a in p['records']}
 state=f.compact(f.fuse([lookup[w] for w in sorted(req['worker_ids'])],gap=f.WORKING_GAP)['automatic']);saved=next(s['automatic'] for s in read(B/'pools'/p['pool_id']/'states.json.gz')['states'] if s['subset']==row.get('subset','|'.join(sorted(lookup[w]['id'] for w in req['worker_ids']))));diff=[];compare(state,saved);rows.append(dict(request_id=row['request_id'],differences=diff))
(O/'STATE_ROUNDOFF_DETAILS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
