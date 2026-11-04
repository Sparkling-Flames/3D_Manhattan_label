"""Attach native diagnostic states to already saved, exact legacy teams.

Saved core scalars and geometry remain authoritative. Replayed states must pass
the repository's existing scalar/status/ERP/topology parity contract.
"""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,concurrent.futures,gzip,json,sys,time
from pathlib import Path
import pandas as pd
from mechanism_core import ROOT,OUT,COMMIT,sha,digest,read_json,iter_jsonl,save_json,save_csv

def init_worker():
    global rt,em,mod,engine
    sys.path.insert(0,str(ROOT/'research/workers/personnel_ac_v21_20261030/stage02_engine/code'))
    sys.path.insert(0,str(ROOT/'research/workers/personnel_ac_v21_20261030/stage06_cases/code'))
    import ac_endpoint_runtime as rt
    import export_ac_mechanisms as em
    mod=rt.load_engine(ROOT);engine=mod.Engine(full_state=True);engine.__enter__()

def worker(payload):
    pool,oldrows,force=payload;engine.reset_pool();rows=[];start=time.monotonic();new=0
    for before in oldrows:
        dest=OUT/'trace_endpoints'/(before['team_key']+'.json.gz')
        assert before.get('input_pool_sha256') in (None,'',rt.digest(pool)),('changed pool',pool['pool_id'])
        assert before.get('reference_sha256') in (None,'',rt.digest(pool['reference'])),('changed reference',pool['pool_id'])
        if dest.exists() and not force:
            prior=read_json(dest)
            assert prior.get('full_state') is not None
            assert prior['trace_source_endpoint_sha256']==rt.digest(before),'Saved source endpoint changed.'
            check=prior['trace_replay_parity'];check=dict(check,trace_cache_reused=True)
        else:
            after=engine.evaluate(pool,sorted(before['member_workers']))
            geom=after.get('geometry')
            if geom is not None:
                extra=engine.scorecache.get(engine.fr.digest([after['k']==2,after.get('nodes'),geom]))
                if extra:after.update(extra)
            check=em.validate_trace(before,after,pool,rt)
            prior=em.preserve_saved_endpoint_with_trace(before,after,check,rt)
            prior.update(trace_source_endpoint_sha256=rt.digest(before),trace_only_replay_existing_team=True,
                         additional_new_physical_team=False,trace_current_source_commit=COMMIT,
                         trace_core_metrics_preserved=True)
            save_json(dest,prior);new+=1
            check=dict(check,trace_cache_reused=False)
        rows.append(check)
    return dict(pool_id=pool['pool_id'],endpoints=len(oldrows),replayed_now=new,seconds=time.monotonic()-start,checks=rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--selection',default=str(OUT/'DIAGNOSTIC_SAMPLE.csv.gz'));ap.add_argument('--jobs',type=int,default=4);ap.add_argument('--force',action='store_true',help='Re-evaluate the already registered native endpoints even when their diagnostic trace cache exists.');args=ap.parse_args()
    sample=pd.read_csv(args.selection,keep_default_na=False,low_memory=False)
    case_run=Path(args.selection).name=='CASE_SELECTION.csv'
    keys=set(sample.A_team_key)|set(sample.C_team_key)
    saved={r['team_key']:r for r in iter_jsonl(OUT/'source/SAVED_LEGACY_ENDPOINTS.jsonl.gz') if r['team_key'] in keys}
    assert set(saved)==keys
    source=ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json'
    delivered=OUT/'source/DIAGNOSTIC_POOLS.json.gz'
    snapshot=read_json(source) if source.exists() else read_json(delivered)
    pools={p['pool_id']:p for p in snapshot['images'] if p['pool_id'] in set(sample.pool_id)}
    assert set(pools)==set(sample.pool_id)
    previous=OUT/'source/DIAGNOSTIC_POOLS.json.gz'
    previous_pools={p['pool_id']:p for p in read_json(previous)['images']} if previous.exists() else {}
    for pid,p in pools.items():
        if pid in previous_pools:assert digest(previous_pools[pid])==digest(p)
    previous_pools.update(pools);save_json(previous,dict(source_path=str(source.relative_to(ROOT)),source_sha256=sha(source) if source.exists() else snapshot['source_sha256'],images=[previous_pools[pid] for pid in sorted(previous_pools)]))
    payload=[(pools[pid],[saved[k] for k in sorted(keys) if saved[k]['pool_id']==pid],args.force) for pid in sorted(pools)]
    start=time.monotonic();done=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs,initializer=init_worker) as ex:
        futures=[ex.submit(worker,x) for x in payload]
        for f in concurrent.futures.as_completed(futures):
            result=f.result();done.append(result)
            save_json(OUT/'source/REPLAY_PROGRESS.json',dict(pools_done=len(done),pools_requested=len(payload),endpoints=sum(x['endpoints'] for x in done),seconds=time.monotonic()-start))
            if len(done)%20==0:print(json.dumps(dict(pools_done=len(done),endpoints=sum(x['endpoints'] for x in done),seconds=time.monotonic()-start)),flush=True)
    checks=[r for p in done for r in p['checks']]
    prefix='CASE_' if case_run else ''
    save_json(OUT/(prefix+'TRACE_SCALAR_GEOMETRY_PARITY.json'),checks)
    save_csv(OUT/(prefix+'TRACE_PARITY_SUMMARY.csv'),[{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in checks])
    receipt=dict(selection_path=str(Path(args.selection).resolve().relative_to(ROOT)),selection_sha256=sha(args.selection),selected_pairs=len(sample),unique_saved_endpoints=len(keys),
                 pools=len(pools),replayed_now=sum(x['replayed_now'] for x in done),reused_trace_cache=len(keys)-sum(x['replayed_now'] for x in done),
                 new_physical_teams=0,scientific_endpoint_outcomes_changed=0,source_main=COMMIT,
                 all_saved_core_metrics_geometry_preserved=True,all_ERP_topology_ids_status_Q_availability_identical=True,
                 full_geometry_hash_exact_n=sum(x['full_geometry_json_hash_identical'] for x in checks),
                 maximum_score_field_difference=max(x['maximum_difference'] for x in checks),
                 maximum_derived_footprint_roundoff=max(x['maximum_derived_footprint_difference'] for x in checks),
                 seconds=time.monotonic()-start,jobs=args.jobs,
                 note='Native evaluation is solely diagnostic replay of registered physical teams; original core endpoint values are retained. No new comparison team, scoring rule, connection or geometry edit.')
    save_json(OUT/(prefix+'NATIVE_REPLAY_RECEIPT.json'),receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
