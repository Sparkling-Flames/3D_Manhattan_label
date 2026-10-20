"""Read original frozen endpoint geometries; never refusion or repair them."""
import os
for k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:os.environ[k]='1'
import json,gzip,sys,time,hashlib,argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'audit_corner'))
from corner_distance import corner_compare
P=ROOT/'unpacked'; S=P/'interchangeability_20261020'; A=ROOT/'restored/work_personnel_typing_A_20261019/events'
OUT=Path(__file__).resolve().parent/'corner_history';OUT.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def process(pid):
    out=OUT/(pid+'.csv.gz')
    receipt=OUT/(pid+'.receipt.json')
    if out.exists() and receipt.exists():
        saved=json.loads(receipt.read_text())
        try:
            cached=pd.read_csv(out)
            if len(cached)==saved['rows'] and saved['corner_code_sha256']==sha(ROOT/'audit_corner/corner_distance.py'):return {'pool_id':pid,'cached':True,'rows':len(cached)}
        except Exception:pass
    t=time.perf_counter();d=A/'native_runs/pools'/pid
    states=json.load(gzip.open(d/'states.json.gz','rt'));assert states['context']['git_commit']=='82c6164b0d4630de5316199c92aa405930973168' and states['context']['N1_applied']==False
    geometry={r['team_id']:r['automatic'].get('candidate') for r in states['states']}
    results=json.load(gzip.open(d/'request_results.json.gz','rt'))['results']; teams={r['team_id']:dict(r,geometry=geometry[r['team_id']]) for r in results}
    f=pd.read_csv(A/'comparisons'/pid/'events.csv.gz');f=f[f.panel_id.eq('Pro_exact_fixed_background_v1')]; rows=[]
    for r in f.itertuples(index=False):
        a,b=teams[r.team_id_a],teams[r.team_id_b]
        for k in ['pool_id','image_id','reference_id','reference_version']:assert a[k]==b[k],(pid,k)
        m,_=corner_compare(a,b)
        row={k:getattr(r,k) for k in ['event_id','panel_id','pool_id','image','building','k','background_id','worker_a','worker_b','entrant_origin_a','entrant_origin_b','joint_stable_main','joint_stable_wide','both_complete','abs_B8L2_change','node_count_difference']}
        row.update(m);rows.append(row)
    pd.DataFrame(rows).to_csv(out,index=False,compression={'method':'gzip','mtime':0})
    rec={'pool_id':pid,'rows':len(rows),'elapsed_seconds':time.perf_counter()-t,'states_sha256':sha(d/'states.json.gz'),'events_sha256':sha(A/'comparisons'/pid/'events.csv.gz'),'corner_code_sha256':sha(ROOT/'audit_corner/corner_distance.py')}
    (OUT/(pid+'.receipt.json')).write_text(json.dumps(rec,indent=2)); return rec
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int);ap.add_argument('--jobs',type=int,default=4);args=ap.parse_args()
    hist=set(json.load(open(P/'analysis/composition/SPLIT.json'))['history_buildings']); pids=sorted(p.name for p in (A/'comparisons').iterdir() if p.name.split('-',1)[0] in hist)
    if args.limit:pids=pids[:args.limit]
    t=time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.jobs) as e:
        for rec in e.map(process,pids):print(json.dumps(rec),flush=True)
    print(json.dumps({'pools':len(pids),'total_seconds':time.perf_counter()-t}),flush=True)
