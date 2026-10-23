"""Deduplicated native endpoint computation with checkpointed pool shards."""
from __future__ import annotations
import argparse,collections,concurrent.futures,math,os,time,shutil
from pathlib import Path
import numpy as np
import pandas as pd
from global_study import *

TIME_SOURCE=ROOT/'research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz'
NAMESPACE='endpoints'

def available_endpoints():
    full,partial,ledger=existing_cache()
    for folder in ('benchmark_endpoints','runtime/endpoints'):
        for path in sorted((OUT/folder).glob('*.json.gz')):
            payload=read(path)
            for row in payload['teams']:
                if folder=='benchmark_endpoints' and row['team_key'] not in full:row['endpoint_origin']='new_benchmark_this_round'
                full[row['team_key']]=row
    return full,partial,ledger

def pool_endpoints(pid,base=None):
    rows={} if base is None else dict(base)
    for folder in ('benchmark_endpoints','runtime/endpoints','runtime/priority_endpoints'):
        path=OUT/folder/(pid+'.json.gz')
        if path.exists():
            for row in read(path)['teams']:
                if folder=='benchmark_endpoints' and row['team_key'] not in rows:row['endpoint_origin']='new_benchmark_this_round'
                rows[row['team_key']]=row
    return rows

def benchmark_keys():
    return {r['team_key'] for path in (OUT/'benchmark_endpoints').glob('*.json.gz') for r in read(path)['teams']}

def classify_endpoint_origin(key,full,partial,history,benchmarked):
    # Establish provenance from exact source indexes, not a missing legacy
    # row's fallback string. Benchmark rows saved before provenance fields
    # existed are still new calculations unless their set was historical.
    if key in full:return 'historical_full_geometry_cache'
    if key in history:return 'historical_endpoint_regenerated_for_missing_geometry'
    if key in partial:return 'scalar_cache_enriched'
    if key in benchmarked:return 'new_benchmark_this_round'
    return 'new_endpoint_this_round'

def worker_pool(pool,requests,reused,checkpoint_every=500):
    fe,fr,sg,_=setup_engine();pid=pool['pool_id'];target=OUT/'runtime'/NAMESPACE/(pid+'.json.gz')
    reused=pool_endpoints(pid,reused)
    rows=dict(reused);cache={};new_n=0;start=time.monotonic();need={q['team_key']:q['member_workers'] for q in requests}
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,ws in need.items():
            if key in rows:continue
            row=fr.evaluate_one(pool,ws,engine,models,score_cache=cache)
            row['endpoint_origin']='native_new_or_scalar_cache_enriched';rows[key]=row;new_n+=1
            if new_n%checkpoint_every==0:
                save(target,dict(pool_id=pid,pool_input_sha256=digest(pool),fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    save(target,dict(pool_id=pid,pool_input_sha256=digest(pool),fusion_gap=fe.WORKING_GAP,teams=list(rows.values())))
    return dict(pool_id=pid,requested=len(need),reused=len(need)-new_n,new_native=new_n,
       score_available=sum(rows[k].get('B8L2') is not None for k in need),seconds=time.monotonic()-start)

def enrich(row,pool,times,sg,diag_cache):
    row=dict(row);row['endpoint_origin']=row.get('endpoint_origin','unclassified_runtime_endpoint')
    records={r['worker_id']:r for r in pool['records']};own=[records[w] for w in row['member_workers']]
    for key,newkey in [('source_active_time_seconds','source'),('target_matched_time_seconds','target')]:
        v=[times.get(r['object_id'],{}).get(key) for r in own]
        v=[None if x is None or pd.isna(x) else float(x) for x in v];known=[x for x in v if x is not None and math.isfinite(x)]
        row[newkey+'_time_known_n']=len(known);row[newkey+'_time_total_seconds']=sum(known) if len(known)==len(own) else None
        row[newkey+'_time_known_sum_seconds']=sum(known)
        row[newkey+'_parallel_active_seconds']=max(known) if len(known)==len(own) and known else None
    row['time_source_kinds']='|'.join(sorted({str(times.get(r['object_id'],{}).get('time_source_kind','unknown')) for r in own}))
    row['time_source_table']=str(TIME_SOURCE.relative_to(ROOT))
    sig=sg.signature(row,pool['reference']['floor_xz_h'],diag_cache)
    for key,value in sig.items():
        if key.startswith('diag_') and not isinstance(value,(dict,list,np.ndarray)):row[key]=value
    poly=sig.get('floor')
    if poly is not None:
        row['geometry_area_h2']=poly.area;row['centroid_x_h']=poly.centroid.x;row['centroid_z_h']=poly.centroid.y
        row['bounds_min_x_h'],row['bounds_min_z_h'],row['bounds_max_x_h'],row['bounds_max_z_h']=poly.bounds
    geo=row.get('geometry') or {};p=geo.get('points')
    if p is not None:
        pp=np.asarray(p,float)
        if pp.ndim==2 and pp.shape[1]==2 and len(pp)%2==0:
            with np.errstate(divide='ignore',invalid='ignore'):
                rr=1/np.tan(np.pi*(pp[1::2,1]/512-.5));h=1+rr*np.tan(np.pi*(.5-pp[::2,1]/512))
            if np.all(np.isfinite(h)):
                row['height_mean_h']=float(np.mean(h));row['height_min_h']=float(np.min(h));row['height_max_h']=float(np.max(h))
            row['top_y_mean_px']=float(pp[::2,1].mean());row['bottom_y_mean_px']=float(pp[1::2,1].mean())
    qs=[r.get('B8L2') for r in own];qs=[q for q in qs if q is not None and math.isfinite(q)]
    row['target_individual_B8L2_known_n']=len(qs)
    if len(qs)==len(own):
        row['target_individual_B8L2_mean']=float(np.mean(qs));row['target_individual_B8L2_min']=float(min(qs))
    return clean(row)

def scalar_row(row):
    s={k:v for k,v in row.items() if not isinstance(v,(list,dict))}
    s['member_workers']='|'.join(row['member_workers']);s['member_object_ids']='|'.join(row['member_object_ids'])
    s['node_supports']='|'.join(map(str,row.get('node_supports',[])))
    for name in ('ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9'):
        value=row.get(name);s[name]='|'.join(map(str,value)) if isinstance(value,list) else None
    return s

def summarize(requests):
    pools=pool_lookup();full,partial,ledger=existing_cache();fe,fr,sg,_=setup_engine()
    times={r['object_id']:r for r in pd.read_csv(TIME_SOURCE).to_dict('records')}
    required={r['team_key'] for r in requests};by=collections.defaultdict(set)
    for row in requests:by[row['pool_id']].add(row['team_key'])
    historical_path=OUT/'HISTORICAL_TEAM_KEYS.txt.gz'
    history=set(gzip.open(historical_path,'rt').read().splitlines()) if historical_path.exists() else set()
    benchmarked=benchmark_keys()
    cols=set();missing=[];states=collections.Counter();origins=collections.Counter();total=0;complete=0;index=[]
    scalar_folder=OUT/'runtime/scalars';scalar_folder.mkdir(parents=True,exist_ok=True)
    for pid,keys in sorted(by.items()):
        base={key:r for key,r in full.items() if r['pool_id']==pid};available=pool_endpoints(pid,base)
        missing.extend(keys-available.keys());cache={};scalars=[]
        for key in sorted(keys & available.keys()):
            row=enrich(available[key],pools[pid],times,sg,cache)
            row['endpoint_origin']=classify_endpoint_origin(key,full,partial,history,benchmarked)
            row['historical_583261_set_overlap']=key in history
            row['historical_complete_geometry_cache']=key in full
            row['historical_scalar_cache']=key in partial
            s=scalar_row(row)
            scalars.append(s);states[row.get('score_status')]+=1;origins[row['endpoint_origin']]+=1;complete+=bool(row.get('complete_evaluable'))
        frame=pd.DataFrame(scalars);cols.update(frame.columns);total+=len(frame)
        path=scalar_folder/(pid+'.csv.gz');csv(path,frame)
        semantic_fields=['pool_id','reference_id','reference_version','member_workers','member_object_ids','k','nodes','complete_evaluable','geometry','minimum_support','node_supports','ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9',*fr.SCORE_KEYS]
        semantic=digest([(key,{name:available[key].get(name) for name in semantic_fields}) for key in sorted(keys & available.keys())])
        geometry_path=OUT/'runtime/endpoints'/(pid+'.json.gz')
        index.append(dict(pool_id=pid,requested=len(keys),complete_endpoints=len(frame),scalar_shard=str(path.relative_to(OUT)),geometry_shard=f'runtime/endpoints/{pid}.json.gz',
            input_pool_sha256=digest(pools[pid]),required_endpoint_semantic_sha256=semantic,raw_cache_sha256=hashlib.sha256(geometry_path.read_bytes()).hexdigest() if geometry_path.exists() else None,
            semantic_hash_excludes_elapsed_timing=True))
    # Streaming concatenation avoids holding all geometries and their JSON
    # serialization in memory. Geometry stays in reproducible per-pool caches.
    fields=sorted(cols);target=OUT/'TEAMS_SCALARS.csv.gz';tmp=target.with_name(target.name+'.tmp')
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='') as stream:
        first=True
        for item in index:
            frame=pd.read_csv(OUT/item['scalar_shard'],low_memory=False).reindex(columns=fields)
            frame.to_csv(stream,index=False,header=first);first=False
    tmp.replace(target);csv(OUT/'ENDPOINT_SHARD_INDEX.csv',pd.DataFrame(index))
    save(OUT/'ENDPOINT_COMPLETION.json',dict(requested_unique=len(required),available_unique=total,missing_unique=len(missing),
        missing_keys=sorted(missing),score_status_counts=dict(states),endpoint_origin_counts=dict(origins),complete_evaluable=complete,
        failed_endpoints_retained=True,time_source=str(TIME_SOURCE.relative_to(ROOT)),geometry_storage='per-pool runtime checkpoints; final delivery retains necessary selected cases only'))
    return total

def incremental_summary(requests):
    """Append already-computed capacity supplements; retain prior scalar rows.

    This is used only after a full streaming summary has finished. It performs
    no native fusion and enriches only newly requested keys. It also merges
    supplemental priority rows into their canonical per-pool geometry shards.
    """
    pools=pool_lookup();full,partial,_=existing_cache();fe,fr,sg,_=setup_engine()
    times={r['object_id']:r for r in pd.read_csv(TIME_SOURCE).to_dict('records')}
    history=set(gzip.open(OUT/'HISTORICAL_TEAM_KEYS.txt.gz','rt').read().splitlines())
    benchmarked=benchmark_keys()
    by=collections.defaultdict(set)
    for r in requests:by[r['pool_id']].add(r['team_key'])
    old_index={r['pool_id']:r for r in pd.read_csv(OUT/'ENDPOINT_SHARD_INDEX.csv').to_dict('records')}
    cols=set();states=collections.Counter();origins=collections.Counter();index=[];added=0;total=0;complete=0;appended=[]
    base_columns=pd.read_csv(OUT/'TEAMS_SCALARS.csv.gz',nrows=0).columns.tolist()
    save(OUT/'runtime/ENDPOINT_COMPLETION_PRE_V3.json',read(OUT/'ENDPOINT_COMPLETION.json'))
    for pid,keys in sorted(by.items()):
        path=OUT/'runtime/scalars'/(pid+'.csv.gz')
        frame=pd.read_csv(path,low_memory=False)
        old=set(frame.team_key)
        if old-keys:raise ValueError('incremental request unexpectedly removed prior endpoints')
        missing=keys-old
        if missing:
            available=pool_endpoints(pid,{k:r for k,r in full.items() if r['pool_id']==pid})
            if missing-available.keys():raise ValueError(('supplement not yet computed',pid))
            cache={};extra=[]
            for key in sorted(missing):
                row=enrich(available[key],pools[pid],times,sg,cache)
                row['endpoint_origin']=classify_endpoint_origin(key,full,partial,history,benchmarked)
                row['historical_583261_set_overlap']=key in history;row['historical_complete_geometry_cache']=key in full;row['historical_scalar_cache']=key in partial
                extra.append(scalar_row(row))
            appended.extend(extra)
            frame=pd.concat([frame,pd.DataFrame(extra)],ignore_index=True).sort_values('team_key');csv(path,frame)
            save(OUT/'runtime/endpoints'/(pid+'.json.gz'),dict(pool_id=pid,pool_input_sha256=digest(pools[pid]),fusion_gap=fe.WORKING_GAP,teams=list(available.values())))
            added+=len(missing)
        assert set(frame.team_key)==keys
        cols.update(frame.columns);states.update(frame.score_status);origins.update(frame.endpoint_origin);total+=len(frame);complete+=int(frame.complete_evaluable.eq(True).sum())
        record=old_index[pid];record['requested']=len(keys);record['complete_endpoints']=len(frame);record['scalar_shard']=str(path.relative_to(OUT));record['geometry_shard']=f'runtime/endpoints/{pid}.json.gz'
        # The final hash-only pass regenerates scope-specific hashes.
        for key in ('required_endpoint_semantic_sha256','raw_cache_sha256','scalar_shard_sha256'):record.pop(key,None)
        index.append(record)
    fields=sorted(cols);target=OUT/'TEAMS_SCALARS.csv.gz';tmp=target.with_name(target.name+'.tmp')
    if set(fields)<=set(base_columns):
        # RFC1952 concatenated gzip members are a single CSV stream to Python
        # and Pandas. Preserve all prior compressed rows and append only the
        # 63 supplement rows, without a second header or a second UTF-8 BOM.
        shutil.copyfile(target,tmp)
        raw=pd.DataFrame(appended).reindex(columns=base_columns).to_csv(index=False,header=False).encode('utf-8')
        with tmp.open('ab') as stream:stream.write(gzip.compress(raw,compresslevel=5,mtime=0))
    else:
        with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='') as stream:
            first=True
            for item in index:
                frame=pd.read_csv(OUT/item['scalar_shard'],low_memory=False).reindex(columns=fields)
                frame.to_csv(stream,index=False,header=first);first=False
    tmp.replace(target);csv(OUT/'ENDPOINT_SHARD_INDEX.csv',pd.DataFrame(index))
    save(OUT/'ENDPOINT_COMPLETION.json',dict(requested_unique=len(requests),available_unique=total,missing_unique=0,missing_keys=[],
        score_status_counts=dict(states),endpoint_origin_counts=dict(origins),complete_evaluable=complete,failed_endpoints_retained=True,
        time_source=str(TIME_SOURCE.relative_to(ROOT)),geometry_storage='per-pool runtime checkpoints; final delivery retains necessary selected cases only',
        capacity_v3_incremental_enrichment_rows=added,capacity_v3_native_fusion_evaluations_during_summary=0))
    print(json.dumps(dict(final_scalar_rows=total,incremental_enrichment_rows=added,fusion_evaluations=0)),flush=True)
    return total

def main():
    global NAMESPACE
    p=argparse.ArgumentParser();p.add_argument('--requests',type=Path,default=OUT/'ENDPOINT_REQUESTS.json.gz');p.add_argument('--jobs',type=int,default=6);p.add_argument('--summarize-only',action='store_true');p.add_argument('--incremental-summary',action='store_true');p.add_argument('--skip-summary',action='store_true');p.add_argument('--namespace',choices=['endpoints','priority_endpoints'],default='endpoints');a=p.parse_args();NAMESPACE=a.namespace
    requests=read(a.requests)['requests']
    if a.incremental_summary:incremental_summary(requests);return
    if a.summarize_only:summarize(requests);return
    pools=pool_lookup();full,partial,ledger=existing_cache();by=collections.defaultdict(list)
    for row in requests:
        if row['team_key']!=team_key(row['pool_id'],row['member_workers']):raise ValueError('noncanonical request')
        by[row['pool_id']].append(row)
    start=time.monotonic();done=[];receipt_path=OUT/('PRIORITY_RUN_RECEIPT.json' if NAMESPACE=='priority_endpoints' else 'RUN_RECEIPT.json')
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        fs={}
        for pid,rr in by.items():
            wanted={r['team_key'] for r in rr};reuse={key:full[key] for key in wanted&full.keys()}
            fs[ex.submit(worker_pool,pools[pid],rr,reuse)]=pid
        for f in concurrent.futures.as_completed(fs):
            receipt=f.result();done.append(receipt)
            save(receipt_path,dict(jobs=a.jobs,pools_finished=len(done),pools_total=len(by),seconds=time.monotonic()-start,by_pool=done))
            print(json.dumps(dict(receipt,pools_finished=len(done),pools_total=len(by),elapsed=time.monotonic()-start)),flush=True)
    if not a.skip_summary:summarize(requests)
    save(receipt_path,dict(jobs=a.jobs,pools_finished=len(done),pools_total=len(by),seconds=time.monotonic()-start,
        total_new_native=sum(x['new_native'] for x in done),total_reused=sum(x['reused'] for x in done),by_pool=done,
        request_sha256=hashlib.sha256(a.requests.read_bytes()).hexdigest()))
    save(OUT/'runtime'/('RUN_'+a.requests.name.replace('.json.gz','.json')),read(receipt_path))

if __name__=='__main__':main()
