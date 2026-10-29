"""Slim storage wrapper around the UNCHANGED, pinned native fusion and scorer.

Only final geometry, direct measurements and exact team identities are retained.
Intermediate identity/assignment states are computed in memory and discarded.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures, gzip, hashlib, json, math, os, sys, time
from pathlib import Path
for _v in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[_v]='1'
import numpy as np
from scipy.optimize import linear_sum_assignment

SCORE_KEYS=['score_status','B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','height_mean_ratio']
FE=None
def init_engine(restored):
    global FE
    root=Path(restored).resolve()/'work_personnel_typing_A_20261019/recovered'
    os.environ['PERSONNEL_V2_REPOSITORY']=str(root/'repo_main_20261019')
    sys.path.insert(0,str(root/'work_v2_20261019/fusion'))
    import fusion_engine
    FE=fusion_engine
    return FE

def read(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return json.load(f)
def write(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    b=gzip.compress(raw,compresslevel=5,mtime=0) if p.suffix=='.gz' else raw
    tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_bytes(b);tmp.replace(p)
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def team_key(pool_id,workers):return pool_id+'__'+digest(sorted(workers))[:20]

def reference_structure(points,ref):
    """Diagnostic node/adjacency recall only, not a new quality score or semantic GT."""
    out={}
    if points is None:
        return {f'ref_{k}_{t}':None for t in [5,9] for k in ['node_recall','edge_recall','matched_nodes','matched_edges']}
    a=np.asarray(points,float);b=np.asarray(ref,float)
    if len(a)<6 or len(a)%2 or len(b)%2:return out
    costs=np.maximum(FE.angular(a[::2],b[::2]),FE.angular(a[1::2],b[1::2]))
    ii,jj=linear_sum_assignment(costs)
    for t in [5,9]:
        mapping={int(i):int(j) for i,j in zip(ii,jj) if costs[i,j]<=t}
        edges=[];nr=len(b)//2;na=len(a)//2
        for i in range(na):
            j=(i+1)%na
            if i in mapping and j in mapping:
                u,v=mapping[i],mapping[j]
                if (u-v)%nr in [1,nr-1]:edges.append(min(u,v)*nr+max(u,v))
        out.update({f'ref_node_recall_{t}':len(mapping)/nr,f'ref_edge_recall_{t}':len(set(edges))/nr,f'ref_matched_nodes_{t}':sorted(mapping.values()),f'ref_matched_edges_{t}':sorted(set(edges))})
    return out

def evaluate_one(pool,workers,engine,models,score_cache=None,full_state=False):
    fe=FE;by={r['worker_id']:r for r in pool['records']};ws=sorted(workers)
    assert len(ws)==len(set(ws)) and set(ws)<=by.keys()
    selected=[by[w] for w in ws];ids=[r['id'] for r in selected]
    row=dict(pool['meta'],team_key=team_key(pool['pool_id'],ws),member_workers=ws,member_object_ids=[r['object_id'] for r in selected],k=len(ws),new_n=sum(r['origin']=='new' for r in selected),old_n=sum(r['origin']=='v1' for r in selected))
    for key,prefix in [('source_time_seconds','source'),('target_time_seconds','target')]:
        v=[r.get(key) for r in selected];known=[float(x) for x in v if x is not None and math.isfinite(float(x))]
        row[prefix+'_time_known_n']=len(known);row[prefix+'_time_total_seconds']=sum(known) if len(known)==len(ws) else None
    t=time.monotonic();state=None
    try:
        state=fe.compact(fe.fuse(selected,gap=fe.WORKING_GAP)['automatic'])
        assert {m['id'] for g in state['identity_groups'] for m in g['members']}==set(ids)
        assert state['n']==len(ws)
    except (ValueError,ArithmeticError,RuntimeError,TypeError) as e:row.update(fusion_error=type(e).__name__+':'+str(e))
    row['fusion_seconds']=time.monotonic()-t
    if state is None:
        row.update(fe.empty_summary(len(ws)),score_status='fusion_exception',B8L2=None,D10=None,geometry=None)
        return fe.clean(row)
    row.update(fe.summarize_state(state));t=time.monotonic()
    try:
        ck=digest([state['n']==2,len(state['node_consensus']['nodes']),state['candidate']])
        if score_cache is not None and ck in score_cache:score=score_cache[ck]
        else:
            score=fe.compute_score(state,pool,engine,models)
            if score_cache is not None:score_cache[ck]=score
        row.update({k:score.get(k) for k in SCORE_KEYS})
    except (ValueError,ArithmeticError,RuntimeError,TypeError) as e:row.update(score_status='measurement_exception',B8L2=None,D10=None,score_error=type(e).__name__+':'+str(e))
    row['score_seconds']=time.monotonic()-t
    c=state['candidate'];ns=state['node_consensus']['nodes']
    row.update(geometry=c,reference_nodes=len(pool['reference']['points_1024x512'])//2,minimum_support=state['minimum_support'],node_supports=[n['support'] for n in ns],identity_groups_n=len(state['identity_groups']),unselected_groups_n=sum(not g['selected'] for g in state['identity_groups']),minority_observations_n=sum(g['support'] for g in state['identity_groups'] if not g['selected']))
    supports=[n['support']/state['n'] for n in ns];row['selected_support_min']=min(supports) if supports else None
    row.update(reference_structure(c.get('points'),pool['reference']['points_1024x512']))
    if full_state:row['full_state']=state
    return fe.clean(row)

def run_pool(restored,pool,requests,out):
    fe=init_engine(restored);t=time.monotonic();target=Path(out)/'pools'/(pool['pool_id']+'.json.gz')
    ctx={'pool_digest':digest(pool),'fusion_gap':fe.WORKING_GAP,'main_commit':'e572eb73bedc4fe9056df838e458bab83c3fa423','science_commit':fe.COMMIT,'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if target.exists():
        previous=read(target);assert previous['context']==ctx,'changed computation context';rows={r['team_key']:r for r in previous['teams']}
    else:rows={}
    initial=len(rows);needed={team_key(pool['pool_id'],q['worker_ids']):q['worker_ids'] for q in requests}
    cache={}
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,ws in needed.items():
            if key in rows:continue
            rows[key]=evaluate_one(pool,ws,engine,models,cache)
    write(target,{'context':ctx,'teams':list(rows.values())})
    receipt=dict(pool_id=pool['pool_id'],requests=len(requests),requested_unique=len(needed),new_teams=len(rows)-initial,total_cached_teams=len(rows),score_available=sum(rows[k].get('B8L2') is not None for k in needed),seconds=time.monotonic()-t)
    return receipt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--restored',type=Path,required=True);ap.add_argument('--requests',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--jobs',type=int,default=5);a=ap.parse_args()
    fe=init_engine(a.restored);pools={p['pool_id']:p for p in fe.load_pools()};q=read(a.requests);requests=q['requests'];seen=set();by=collections.defaultdict(list)
    for r in requests:
        assert r['request_id'] not in seen;seen.add(r['request_id']);assert len(r['worker_ids'])==len(set(r['worker_ids']))==r['k'];assert set(r['worker_ids'])<={x['worker_id'] for x in pools[r['pool_id']]['records']}
        by[r['pool_id']].append(r)
    start=time.monotonic();done=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        fs={ex.submit(run_pool,a.restored,pools[pid],rs,a.out):pid for pid,rs in by.items()}
        for f in concurrent.futures.as_completed(fs):
            r=f.result();done.append(r);print(json.dumps(dict(r,done=len(done),pools=len(by),elapsed=round(time.monotonic()-start,1))),flush=True)
    write(a.out/('RUN_'+a.requests.name.replace('.json.gz','')+'.json'),dict(request_file=str(a.requests),request_sha256=hashlib.sha256(a.requests.read_bytes()).hexdigest(),request_rows=len(requests),unique_teams=len({team_key(r['pool_id'],r['worker_ids']) for r in requests}),new_fusions=sum(r['new_teams'] for r in done),seconds=time.monotonic()-start,jobs=a.jobs,by_pool=done))

if __name__=='__main__':main()
