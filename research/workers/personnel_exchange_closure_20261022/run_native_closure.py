"""Incremental adapter to frozen real-v2 fusion; exact endpoint reuse, no rule change."""
from __future__ import annotations
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import argparse,gzip,hashlib,json,sys,time
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PREVIOUS=ROOT/'research/workers/personnel_effective_exchange_conditions_20261022'
sys.path.insert(0,str(PREVIOUS/'expanded_blocks'))
import run_native as frozen
sys.path.insert(0,str(PREVIOUS/'joint_exchange'))
from evaluate_joint import typed
gs=frozen.gs
NATIVE=HERE/'native'
FROZEN_WORKER=frozen.worker

def durable_save(path,value):
    """One fsynced byte write; verify checkpoint before publishing its name."""
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(gs.clean(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if p.suffix=='.gz':data=gzip.compress(data,compresslevel=5,mtime=0)
    tmp=p.with_name(p.name+'.tmp')
    with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    assert hashlib.sha256(tmp.read_bytes()).digest()==hashlib.sha256(data).digest()
    os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def final_path(bid,pid,keys):
    return NATIVE/'runtime'/bid/(pid+'.FINAL_'+gs.digest(sorted(keys))[:16]+'.json.gz')

def closure_worker(payload):
    """Original evaluation calls; immutable final files separate from checkpoints."""
    bid,pool,requests,times=payload;pid=pool['pool_id'];needs={r['team_key']:r for r in requests}
    checkpoint=NATIVE/'runtime'/bid/(pid+'.json.gz');final=final_path(bid,pid,needs);rows={};ph=gs.digest(pool)
    if final.exists():
        rows={r['team_key']:r for r in gs.read(final)['teams']}
        assert set(rows)==set(needs)
        return dict(pool_id=pid,requested=len(needs),new_native=0,reused=0,resumed=len(rows),seconds=0.,complete=sum(bool(r.get('complete_evaluable')) for r in rows.values()))
    if checkpoint.exists():
        data=gs.read(checkpoint);assert data['pool_input_sha256']==ph
        rows={r['team_key']:r for r in data['teams']};assert set(rows)<=set(needs)
    initially=len(rows);oldkeys={k for k,r in needs.items() if str(r['cached']).lower() in ('true','1') and k not in rows};reused=reused_rows(pid,oldkeys)
    fe,fr,sg,_=gs.setup_engine();scorecache={};diag={};t0=time.monotonic();nc=rc=0
    def body():return dict(batch_id=bid,pool_id=pid,pool_input_sha256=ph,underlying_data_version='v2',research_round='personnel_exchange_closure_20261022',fusion_gap=fe.WORKING_GAP,teams=list(rows.values()))
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,q in needs.items():
            if key in rows:continue
            if key in reused:
                row=dict(reused[key]);row['prior_endpoint_origin']=row.get('endpoint_origin');row['endpoint_origin']='reused_exact_prior_team_closure_20261022';rc+=1
                if 'source_time_known_n' not in row:row=frozen.native.enrich(row,pool,times,sg,diag)
            else:
                row=fr.evaluate_one(pool,q['member_workers'].split('|'),engine,models,score_cache=scorecache)
                row=frozen.native.enrich(row,pool,times,sg,diag);row['endpoint_origin']='new_native_closure_20261022_real_v2';nc+=1
            assert row['team_key']==key and row['k']==int(q['n'])
            row.update(underlying_data_version='v2',closure_batch_id=bid,exchange_batch_id=bid);rows[key]=row
            if (nc+rc)%300==0:gs.save(checkpoint,body())
    assert set(rows)==set(needs)
    gs.save(final,body())
    assert {r['team_key'] for r in gs.read(final)['teams']}==set(needs)
    return dict(pool_id=pid,requested=len(needs),new_native=nc,reused=rc,resumed=initially,seconds=time.monotonic()-t0,complete=sum(bool(r.get('complete_evaluable')) for r in rows.values()))

def export_batch(bid):
    folder=NATIVE/'batches'/bid;req=pd.read_csv(folder/'REQUESTS.csv.gz',keep_default_na=False);rows=[]
    for pid,g in req.groupby('pool_id'):
        p=final_path(bid,pid,g.team_key);data=gs.read(p);rr=data['teams'];assert {r['team_key'] for r in rr}==set(g.team_key);rows.extend(rr)
    assert len(rows)==req.team_key.nunique()==len(req)
    sr=frozen.write_csv(folder/'ENDPOINT_SCALARS.csv.gz',[frozen.native.scalar_row(r) for r in rows])
    gr=frozen.write_csv(folder/'ENDPOINT_GEOMETRY.csv.gz',[frozen.prior.compact(r) for r in rows],frozen.prior.GEOMETRY_FIELDS)
    from collections import Counter
    receipt=dict(status='complete',batch_id=bid,underlying_data_version='v2',research_round='closure_20261022',requested=len(req),exported=len(rows),missing=0,states=dict(Counter(r.get('score_status') for r in rows)),origins=dict(Counter(r.get('endpoint_origin') for r in rows)),scalars=sr,geometry=gr,failures_retained=True,exact_membership_retained=True,unchanged_native_fusion_scoring=True,immutable_final_checkpoints=True)
    gs.save(folder/'COMPLETION.json',receipt);print(json.dumps(receipt),flush=True)

def prepare_cache():
    """Restore compact published rows to typed pool caches, without fusion."""
    dest=NATIVE/'reused';dest.mkdir(parents=True,exist_ok=True)
    pairs=[(PREVIOUS/'joint_exchange/ALL_USED_ENDPOINT_SCALARS.csv.gz',PREVIOUS/'joint_exchange/ALL_USED_ENDPOINT_GEOMETRY.csv.gz')]
    pairs.extend((p,p.with_name('ENDPOINT_GEOMETRY.csv.gz')) for p in sorted((PREVIOUS/'expanded_blocks/batches').glob('*/ENDPOINT_SCALARS.csv.gz')) if p.with_name('ENDPOINT_GEOMETRY.csv.gz').exists())
    extra=HERE/'ADDITIONAL_CACHE_PAIRS.json'
    if extra.exists():pairs.extend((ROOT/x['scalar'],ROOT/x['geometry']) for x in gs.read(extra))
    complete=dest/'CACHE_MANIFEST.json';signature=[(str(a.relative_to(ROOT)),frozen.prior.sha(a),frozen.prior.sha(b)) for a,b in pairs]
    if complete.exists() and gs.read(complete)['sources']==[list(x) for x in signature]:return
    rows={}
    for a,b in pairs:
        for chunk in pd.read_csv(a,dtype=str,keep_default_na=False,chunksize=15000):
            for r in chunk.to_dict('records'):
                k=r['team_key'];v=typed(r)
                if k in rows:
                    assert [rows[k].get(f) for f in ('B8L2','D10','nodes')]==[v.get(f) for f in ('B8L2','D10','nodes')]
                    continue
                rows[k]=v
        for chunk in pd.read_csv(b,dtype=str,keep_default_na=False,chunksize=15000):
            for r in chunk.to_dict('records'):
                rows[r['team_key']]['geometry']=json.loads(r['geometry_json']) if r['geometry_json'] else None
    by={}
    for k,r in rows.items():
        assert 'geometry' in r
        by.setdefault(r['pool_id'],[]).append(r)
    index=[]
    for pid,rr in by.items():
        gs.save(dest/(pid+'.json.gz'),dict(pool_id=pid,teams=rr))
        index.extend(dict(team_key=r['team_key'],pool_id=pid,cache_source=str((dest/(pid+'.json.gz')).relative_to(ROOT))) for r in rr)
    frozen.write_csv(dest/'CACHE_INDEX.csv.gz',index)
    gs.save(complete,dict(sources=signature,unique_endpoints=len(rows),pools=len(by),native_calls=0))
    print(json.dumps(dict(cache_restored=len(rows),pools=len(by))),flush=True)

def cache_index():
    p=NATIVE/'reused/CACHE_INDEX.csv.gz';out={}
    if p.exists():out.update(pd.read_csv(p).set_index('team_key').cache_source.to_dict())
    for p in sorted((NATIVE/'batches').glob('*/ENDPOINT_SCALARS.csv.gz')):
        if (p.parent/'COMPLETION.json').exists():out.update((str(k),str(p.relative_to(ROOT))) for k in pd.read_csv(p,usecols=['team_key']).team_key)
    return out

def reused_rows(pid,keys):
    out={}
    if not keys:return out
    p=NATIVE/'reused'/(pid+'.json.gz')
    if p.exists():out.update((r['team_key'],r) for r in gs.read(p)['teams'] if r['team_key'] in keys)
    for p in sorted((NATIVE/'runtime').glob('*/'+pid+'*.json.gz')):
        if not (NATIVE/'batches'/p.parent.name/'COMPLETION.json').exists():continue
        out.update((r['team_key'],r) for r in gs.read(p)['teams'] if r['team_key'] in keys)
    assert keys<=out.keys(),('unavailable_reuse',pid,len(keys-out.keys()))
    return out

def configure():
    gs.save=durable_save
    frozen.HERE=NATIVE;frozen.STUDY=HERE;frozen.cache_index=cache_index;frozen.reused_rows=reused_rows;frozen.worker=closure_worker;frozen.export=export_batch

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['cache','plan','run','run-all']);ap.add_argument('--request');ap.add_argument('--prefix');ap.add_argument('--batch');ap.add_argument('--batch-size',type=int,default=3500);ap.add_argument('--jobs',type=int,default=3);a=ap.parse_args()
    configure()
    if a.action=='cache':prepare_cache()
    elif a.action=='plan':frozen.plan(a.request,a.prefix,a.batch_size)
    elif a.action=='run':frozen.run(a.batch,a.jobs)
    else:
        for bid in pd.read_csv(NATIVE/(a.prefix+'_BATCH_PLAN.csv')).batch_id:frozen.run(bid,a.jobs)

if __name__=='__main__':main()
