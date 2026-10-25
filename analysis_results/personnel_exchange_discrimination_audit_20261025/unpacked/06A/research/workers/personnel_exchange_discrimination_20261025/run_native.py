"""New strict-block requests, unchanged v2 engine; atomic per-pool checkpoints."""
from __future__ import annotations
import argparse, concurrent.futures, gzip, hashlib, importlib.util, json, math, os, sys, time
from pathlib import Path
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[name]='1'
deps=Path(os.environ.get('HOHONET_PYTHON_DEPS','/tmp/hohonet_deps'))
if deps.is_dir():sys.path.insert(0,str(deps))
import numpy as np
import pandas as pd
ROOT=Path(os.environ.get('HOHONET_RESEARCH_ROOT',Path(__file__).resolve().parent)).resolve()
local_repo=ROOT.parent/'HOHONET_exchange_latest'
REPO=Path(os.environ.get('HOHONET_EXCHANGE_REPO',local_repo if local_repo.exists() else ROOT.parents[2]))
legacy_pop=ROOT/'recovery/prior_population/research/workers/personnel_population_curves_v2_20261023'
POP=Path(os.environ.get('HOHONET_PRIOR_POPULATION',legacy_pop if legacy_pop.exists() else ROOT/'runtime/population'))
FROZEN=Path(os.environ.get('HOHONET_FROZEN_ENGINE',REPO/'research/same_room/same_room_large_block_rebuilt_20261023/engine/frozen_repo'))
sys.path.insert(0,str(POP/'code'))
import run_prefix_endpoints as base

def read(p): return base.read(p)
def save(p,v): return base.save(p,v)
def csv(p,v): return base.csv(p,v)
def team_key(pid,ws): return base.team_key(pid,ws)
def setup(): return base.setup(FROZEN)

def compute_pool(pool,needed,out,reused=None):
    gs,fe,fr,sg=setup(); pid=pool['pool_id']; target=Path(out)/'endpoints'/(pid+'.json.gz')
    context=gs.digest(pool); rows={} if reused is None else reused; reused_n=len(rows)
    if target.exists():
        old=read(target); assert old['pool_input_sha256']==context
        rows.update({r['team_key']:r for r in old['teams']})
    before=len(rows); missing=[(key,ws) for key,ws in needed.items() if key not in rows]
    started=time.monotonic(); cache={}; new_n=0
    def checkpoint(done=False):
        save(target,dict(pool_id=pid,pool_input_sha256=context,teams=list(rows.values())))
        save(Path(out)/'progress'/(pid+'.json'),dict(pool_id=pid,requested=len(needed),available=len(set(rows)&set(needed)),new_this_run=new_n,complete=done,seconds=time.monotonic()-started))
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,ws in missing:
            row=fr.evaluate_one(pool,ws,engine,models,score_cache=cache)
            geom=row.get('geometry')
            if geom is not None:
                ck=fr.digest([row['k']==2,row.get('nodes'),geom]); raw=cache.get(ck)
                if raw: row.update(raw)
            row=base.normalize(row,pool);row=base.geometry_enrich(row,pool,fr)
            row['endpoint_origin']='new_native_strict_exchange_20261025'
            assert row['team_key']==key
            rows[key]=row;new_n+=1
            if new_n%250==0:checkpoint()
    checkpoint(True)
    result=dict(pool_id=pid,requested=len(needed),reused_before=before,new_native=new_n,available=len(set(rows)&set(needed)),score_available=sum(rows[k]['score_available'] for k in needed),seconds=time.monotonic()-started)
    save(Path(out)/'receipts'/(pid+'.json'),result);return result

def consolidate(out,needed):
    out=Path(out); scalars=[]; geo=[]; missing=[]
    for pid,keys in needed.items():
        path=out/'endpoints'/(pid+'.json.gz')
        if not path.exists():missing.extend(keys);continue
        rows={r['team_key']:r for r in read(path)['teams']}
        missing.extend(set(keys)-set(rows))
        for key in keys:
            if key not in rows:continue
            r=rows[key];s={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
            for field,v in r.items():
                if isinstance(v,list):s[field]='|'.join(map(str,v))
            scalars.append(s)
            if r.get('geometry') is not None:geo.append(dict(team_key=key,pool_id=pid,geometry=r['geometry'],node_supports=r.get('node_supports')))
    csv(out/'ENDPOINT_SCALARS.csv.gz',pd.DataFrame(scalars));save(out/'ENDPOINT_GEOMETRY.json.gz',geo)
    save(out/'COMPLETION.json',dict(requested=sum(map(len,needed.values())),available=len(scalars),missing=len(missing),missing_keys=missing))
    if missing:raise RuntimeError(f'{len(missing)} missing endpoints')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--requests',required=True);ap.add_argument('--out',required=True);ap.add_argument('--jobs',type=int,default=6);ap.add_argument('--cache-scalar');ap.add_argument('--cache-geometry');ap.add_argument('--consolidate-only',action='store_true');a=ap.parse_args()
    pools={p['pool_id']:p for p in read(POP/'inputs/INPUT_SNAPSHOT.json.gz')['images']}
    req=read(a.requests);req=req.get('requests',req) if isinstance(req,dict) else req
    needed={}
    for r in req:
        ws=r.get('worker_ids',r.get('members'));pid=r['pool_id'];key=team_key(pid,ws)
        assert len(ws)==len(set(ws)) and set(ws)<={x['worker_id'] for x in pools[pid]['records']}
        needed.setdefault(pid,{})[key]=sorted(ws)
    if a.consolidate_only:consolidate(a.out,needed);return
    allkeys={k for keys in needed.values() for k in keys};cache={}
    if a.cache_scalar:
        for chunk in pd.read_csv(a.cache_scalar,low_memory=False,chunksize=30000):
            hit=chunk[chunk.team_key.isin(allkeys)]
            for r in hit.to_dict('records'):
                for field in ('member_workers','member_object_ids'):r[field]=str(r[field]).split('|')
                for field in ('node_supports','ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9'):
                    if field in r and isinstance(r[field],str):r[field]=[int(float(v)) for v in r[field].split('|') if v]
                r=base.clean(r);r['endpoint_origin']='reused_population_20261023';cache[r['team_key']]=r
    if a.cache_geometry and cache:
        for r in read(a.cache_geometry):
            if r['team_key'] in cache:cache[r['team_key']].update(geometry=r['geometry'],node_supports=r.get('node_supports'))
    # A missing historical geometry is not a complete cache hit for this study.
    cache={k:r for k,r in cache.items() if 'geometry' in r or not r.get('score_available')}
    save(Path(a.out)/'REQUEST_COVERAGE.json',dict(request_rows=len(req),unique_teams=len(allkeys),historical_complete_hits=len(cache),new_missing=len(allkeys)-len(cache),pool_count=len(needed),source_commit='972857b2b3f548316be215400e42d6ef6e639250',data='v2'))
    started=time.monotonic();done=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        fut={ex.submit(compute_pool,pools[pid],ns,a.out,{k:cache[k] for k in ns.keys()&cache.keys()}):pid for pid,ns in needed.items()}
        for f in concurrent.futures.as_completed(fut):
            r=f.result();done.append(r);save(Path(a.out)/'RUN_PROGRESS.json',dict(pools_finished=len(done),pools_total=len(needed),seconds=time.monotonic()-started,by_pool=done));print(json.dumps(dict(r,finished=len(done),total=len(needed))),flush=True)
    consolidate(a.out,needed)

if __name__=='__main__':main()
