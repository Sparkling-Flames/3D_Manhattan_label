#!/usr/bin/env python3
"""Reuse exact real-v2 teams, calculate registered missing teams, save each batch.

The native fusion, reference, eligibility and scoring routines are imported
unchanged from the preceding completed research. This is an execution adapter.
"""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import argparse, collections, csv, gzip, io, json, sys, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
REPO=STUDY.parents[2]
V3=REPO/'research/workers/personnel_useful_taxonomy_v3_20261021'
sys.path.insert(0,str(V3/'composition'))
import run_multin_batches as prior
from multin_design import gs,OLD,CONT
import run_endpoints as native
import pandas as pd


def write_csv(path, rows, fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(rows,pd.DataFrame):
        data=rows.to_csv(index=False).encode('utf-8-sig')
        expected=len(rows)
    else:
        fields=fields or list(dict.fromkeys(k for r in rows for k in r))
        buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=fields)
        w.writeheader();w.writerows(gs.clean(r) for r in rows)
        data=buf.getvalue().encode('utf-8-sig');expected=len(rows)
    if path.name.endswith('.gz'):data=gzip.compress(data,compresslevel=5,mtime=0)
    tmp=path.with_name(path.name+'.partial')
    with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    op=gzip.open if path.name.endswith('.gz') else open
    with op(tmp,'rt',encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f);head=next(r);n=0
        for row in r:
            assert len(row)==len(head),(path,n);n+=1
    assert n==expected,(path,n,expected)
    os.replace(tmp,path)
    return dict(path=str(path),rows=n,columns=len(head),sha256=prior.sha(path),bytes=path.stat().st_size)


def cache_index():
    out={}
    paths=[OLD/'composition/TEAMS_SCALARS.csv.gz',
        *sorted((CONT/'next_stage/batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz')),
        V3/'composition/delivery/ENDPOINT_KEY_INDEX.csv.gz']
    for p in paths:
        d=pd.read_csv(p,usecols=['team_key'])
        out.update((str(k),str(p.relative_to(REPO))) for k in d.team_key)
    for p in sorted((HERE/'batches').glob('*/ENDPOINT_SCALARS.csv.gz')):
        if not (p.parent/'COMPLETION.json').exists():continue
        d=pd.read_csv(p,usecols=['team_key'])
        out.update((str(k),str(p.relative_to(REPO))) for k in d.team_key)
    return out


def plan(request,prefix,batch_size):
    req=pd.read_csv(request,keep_default_na=False)
    req['n']=req['n'].astype(int)
    if req.team_key.duplicated().any():
        assert not req.groupby('team_key').member_workers.nunique().gt(1).any()
        req=req.drop_duplicates('team_key')
    pools=gs.pool_lookup();cache=cache_index();rows=[]
    pool_hashes={pid:gs.digest(p) for pid,p in pools.items()}
    for r in req.to_dict('records'):
        p=pools[r['pool_id']];ws=r['member_workers'].split('|')
        assert ws==sorted(set(ws)) and len(ws)==r['n']
        assert gs.team_key(r['pool_id'],ws)==r['team_key']
        assert set(ws)<={x['worker_id'] for x in p['records']}
        r.update({k:p['meta'][k] for k in ['image','building','condition','difficulty','layer']})
        r.update(cached=r['team_key'] in cache,cache_source=cache.get(r['team_key'],''),
                 pool_input_sha256=pool_hashes[r['pool_id']],underlying_data_version='v2')
        rows.append(r)
    d=pd.DataFrame(rows).sort_values(['condition','pool_id','team_key'])
    groups=[]
    for cond,cg in d.groupby('condition',sort=True):
        current=[];size=0
        for pid,pg in cg.groupby('pool_id',sort=True):
            for i in range(0,len(pg),batch_size):
                g=pg.iloc[i:i+batch_size]
                if current and size+len(g)>batch_size:
                    groups.append(pd.concat(current));current=[];size=0
                current.append(g);size+=len(g)
        if current:groups.append(pd.concat(current))
    ledger=[]
    for i,g in enumerate(groups,1):
        bid=f'{prefix}_{i:03d}';folder=HERE/'batches'/bid
        dest=folder/'REQUESTS.csv.gz'
        if dest.exists():
            old=pd.read_csv(dest,keep_default_na=False)
            assert set(old.team_key)==set(g.team_key),('changed_registered_batch',bid)
        else:write_csv(dest,g)
        ledger.append(dict(batch_id=bid,condition=g.condition.iloc[0],pools=g.pool_id.nunique(),
             requested=len(g),cached=int(g.cached.sum()),new_required=int((~g.cached).sum())))
    write_csv(HERE/(prefix+'_BATCH_PLAN.csv'),ledger)
    result=dict(status='registered',underlying_data_version='v2',prefix=prefix,
        source_request=str(Path(request).resolve()),source_request_sha256=prior.sha(request),
        unique_teams=len(d),cached=int(d.cached.sum()),new_required=int((~d.cached).sum()),
        batches=ledger,scoring_and_fusion_unchanged=True)
    gs.save(HERE/(prefix+'_PLAN.json'),result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


def reused_rows(pid,keys):
    out={}
    if not keys:return out
    for p in sorted((HERE/'runtime').glob(f'*/{pid}.json.gz')):
        if not (HERE/'batches'/p.parent.name/'COMPLETION.json').exists():continue
        for r in gs.read(p)['teams']:
            if r['team_key'] in keys:out[r['team_key']]=r
        if keys<=out.keys():return out
    missing=keys-out.keys()
    if missing:out.update(prior.find_reused(pid,missing))
    assert keys<=out.keys()
    return out


def worker(payload):
    bid,pool,requests,times=payload;pid=pool['pool_id']
    path=HERE/'runtime'/bid/(pid+'.json.gz')
    needs={r['team_key']:r for r in requests};poolhash=gs.digest(pool);rows={}
    if path.exists():
        old=gs.read(path);assert old['pool_input_sha256']==poolhash
        rows={r['team_key']:r for r in old['teams']}
        assert set(rows)<=needs.keys()
    initially=len(rows)
    oldkeys={k for k,r in needs.items() if str(r['cached']).lower() in ('true','1') and k not in rows}
    reused=reused_rows(pid,oldkeys)
    fe,fr,sg,_=gs.setup_engine();scorecache={};diag={};started=time.monotonic();nc=rc=0
    def checkpoint():
        gs.save(path,dict(batch_id=bid,pool_id=pid,pool_input_sha256=poolhash,
            underlying_data_version='v2',research_round='effective_exchange_conditions_20261022',
            fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,q in needs.items():
            if key in rows:continue
            if key in reused:
                row=dict(reused[key]);row['prior_endpoint_origin']=row.get('endpoint_origin','completed_earlier_research')
                row['endpoint_origin']='reused_exact_team_for_exchange_conditions_20261022';rc+=1
                if 'source_time_known_n' not in row:row=native.enrich(row,pool,times,sg,diag)
            else:
                row=fr.evaluate_one(pool,q['member_workers'].split('|'),engine,models,score_cache=scorecache)
                row=native.enrich(row,pool,times,sg,diag);nc+=1
                row['endpoint_origin']='new_team_for_exchange_conditions_20261022_on_real_v2'
            assert row['team_key']==key and row['k']==int(q['n'])
            row['underlying_data_version']='v2';row['exchange_batch_id']=bid;rows[key]=row
            if (nc+rc)%300==0:checkpoint()
    checkpoint()
    return dict(pool_id=pid,requested=len(needs),new_native=nc,reused=rc,resumed=initially,
        seconds=time.monotonic()-started,complete=sum(bool(r.get('complete_evaluable')) for r in rows.values()))


def export(bid):
    folder=HERE/'batches'/bid;req=pd.read_csv(folder/'REQUESTS.csv.gz',keep_default_na=False)
    expected=set(req.team_key);rows=[]
    for pid,g in req.groupby('pool_id'):
        rr=gs.read(HERE/'runtime'/bid/(pid+'.json.gz'))['teams']
        assert {r['team_key'] for r in rr}==set(g.team_key)
        rows.extend(rr)
    assert len(rows)==len(expected)
    scalars=[dict(native.scalar_row(r),underlying_data_version='v2',exchange_batch_id=bid) for r in rows]
    geometry=[prior.compact(r) for r in rows]
    sr=write_csv(folder/'ENDPOINT_SCALARS.csv.gz',scalars)
    gr=write_csv(folder/'ENDPOINT_GEOMETRY.csv.gz',geometry,prior.GEOMETRY_FIELDS)
    # Exact set verification is an important publication gate, not a repeated
    # recalculation of the already frozen fusion algorithm.
    for path in [folder/'ENDPOINT_SCALARS.csv.gz',folder/'ENDPOINT_GEOMETRY.csv.gz']:
        d=pd.read_csv(path,usecols=['team_key'])
        assert len(d)==len(expected) and set(d.team_key)==expected
    receipt=dict(status='complete',batch_id=bid,underlying_data_version='v2',
        requested=len(expected),exported=len(rows),missing=0,
        states=dict(collections.Counter(r.get('score_status') for r in rows)),
        origins=dict(collections.Counter(r.get('endpoint_origin') for r in rows)),
        scalars=sr,geometry=gr,failures_retained=True,exact_membership_retained=True,
        unchanged_native_fusion_scoring=True)
    gs.save(folder/'COMPLETION.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


def run(bid,jobs):
    folder=HERE/'batches'/bid
    if (folder/'COMPLETION.json').exists():
        print(json.dumps(dict(batch_id=bid,status='already_complete_no_recalculation')),flush=True);return
    d=pd.read_csv(folder/'REQUESTS.csv.gz',keep_default_na=False);pools=gs.pool_lookup()
    td=pd.read_csv(native.TIME_SOURCE)
    times={r['object_id']:r for r in td.to_dict('records')}
    t0=time.monotonic();progress=[]
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        fs=[ex.submit(worker,(bid,pools[pid],g.to_dict('records'),times)) for pid,g in d.groupby('pool_id')]
        for f in as_completed(fs):
            r=f.result();progress.append(r)
            gs.save(folder/'POOL_PROGRESS.json',dict(pools=progress,seconds=time.monotonic()-t0))
            print(json.dumps(dict(batch_id=bid,**r)),flush=True)
    export(bid)
    gs.save(folder/'EXECUTION.json',dict(batch_id=bid,seconds=time.monotonic()-t0,jobs=jobs,
        new_native=sum(r['new_native'] for r in progress),reused=sum(r['reused'] for r in progress),
        resumed=sum(r['resumed'] for r in progress),pools=progress))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','run','run-all','export'])
    p.add_argument('--request');p.add_argument('--prefix');p.add_argument('--batch');p.add_argument('--batch-size',type=int,default=5000);p.add_argument('--jobs',type=int,default=3)
    a=p.parse_args()
    if a.action=='plan':plan(a.request,a.prefix,a.batch_size)
    elif a.action=='run':run(a.batch,a.jobs)
    elif a.action=='export':export(a.batch)
    else:
        for bid in pd.read_csv(HERE/(a.prefix+'_BATCH_PLAN.csv')).batch_id:run(bid,a.jobs)
