"""Compute only missing deterministic v2 prefix sets; retain each order separately.

The fusion, preprocessing, reference, ring and B8L2/D10 code is imported unchanged
from the recorded repository. Atomic pool checkpoints make partial work reusable.
"""
from __future__ import annotations
import argparse, collections, concurrent.futures, gzip, hashlib, io, json, math, os, sys, time
from pathlib import Path
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name] = '1'
if Path('/tmp/hohonet_deps').exists():
    sys.path.insert(0,'/tmp/hohonet_deps')
import numpy as np
import pandas as pd
from shapely.geometry import Polygon

def clean(v):
    if isinstance(v,dict): return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,np.ndarray)): return [clean(x) for x in v]
    if isinstance(v,np.generic): return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v): return None
    return v

def atomic_bytes(path,b):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('wb') as f: f.write(b);f.flush();os.fsync(f.fileno())
    tmp.replace(path)
    # Persist the directory entry as well as the bytes for durable checkpoints.
    if os.name != 'nt':
        directory_fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory_fd)
        finally:os.close(directory_fd)

def save(path,v):
    b=json.dumps(clean(v),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    atomic_bytes(path,gzip.compress(b,compresslevel=3,mtime=0) if str(path).endswith('.gz') else b)

def csv(path,d):
    raw=d.to_csv(index=False).encode('utf-8-sig')
    packed=gzip.compress(raw,compresslevel=3,mtime=0) if str(path).endswith('.gz') else raw
    atomic_bytes(path,packed)

def read(path):
    with (gzip.open(path,'rt',encoding='utf-8-sig') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig')) as f:return json.load(f)

def team_key(pid,ws):
    digest=hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
    return pid+'__'+digest

def setup(repo):
    repo=Path(repo);sys.path.insert(0,str(repo/'research/workers/personnel_global_composition_20261021/composition'))
    import global_study as gs
    fe,fr,sg,corner=gs.setup_engine()
    return gs,fe,fr,sg

def normalize(row,pool):
    r=clean(dict(row));ws=r['member_workers']
    if isinstance(ws,str):ws=ws.split('|')
    r['member_workers']=sorted(ws);r['team_key']=team_key(pool['pool_id'],ws)
    by={x['worker_id']:x for x in pool['records']};own=[by[w] for w in r['member_workers']]
    r.update(pool['meta']);r['k']=len(ws);r['minimum_support']=math.ceil(len(ws)/2)
    r['member_object_ids']=[x['object_id'] for x in own]
    r['reference_nodes']=len(pool['reference']['points_1024x512'])//2
    for prefix,key in [('source','source_time_seconds'),('target','target_time_seconds')]:
        values=[x.get(key) for x in own];known=[float(v) for v in values if v is not None and math.isfinite(float(v))]
        r[prefix+'_time_known_n']=len(known)
        r[prefix+'_time_known_sum_seconds']=sum(known) if known else None
        r[prefix+'_time_total_seconds']=sum(known) if len(known)==len(ws) else None
    r['time_source_kinds']='|'.join(sorted({x['time_source_kind'] for x in own if x['source_time_seconds'] is not None}))
    r['new_n']=sum(x['origin']=='new' for x in own);r['old_n']=sum(x['origin']=='v1' for x in own)
    for target,old in [('identity_groups_n','identity_group_n'),('unselected_groups_n','nonselected_group_n'),('selected_support_min','selected_node_support_min')]:
        if r.get(target) is None:r[target]=r.get(old)
    r['score_available']=r.get('B8L2') is not None
    r['policy_deferred']=len(ws)==2
    r['score_failure_nonpolicy']=(not r['policy_deferred']) and not r['score_available']
    r['incomplete_nonpolicy']=(not r['policy_deferred']) and not bool(r.get('complete_evaluable'))
    r['reference_node_shortfall']=max(0,r['reference_nodes']-r['nodes']) if r.get('nodes') is not None else None
    return r

def geometry_enrich(row,pool,fr):
    r=row;g=r.get('geometry') or {};points=g.get('points');floor=g.get('footprint')
    r['geometry_available']=bool(g)
    if points is not None:
        pp=np.asarray(points,float);r['candidate_pair_count']=len(pp)//2
        if pp.ndim==2 and pp.shape[1]==2 and len(pp)%2==0:
            with np.errstate(divide='ignore',invalid='ignore'):
                radius=1/np.tan(np.pi*(pp[1::2,1]/512-.5))
                heights=1+radius*np.tan(np.pi*(.5-pp[::2,1]/512))
            if np.isfinite(heights).all():
                r.update(height_mean_h=float(heights.mean()),height_min_h=float(heights.min()),height_max_h=float(heights.max()),height_sd_h=float(heights.std()))
            r.update(top_y_mean_px=float(pp[::2,1].mean()),bottom_y_mean_px=float(pp[1::2,1].mean()))
        r.update(fr.reference_structure(points,pool['reference']['points_1024x512']))
    if floor is not None and len(floor)>=3:
        a=np.asarray(floor,float);p=Polygon(a)
        if p.is_valid and p.area>0:
            r.update(floor_area_camera_h2=float(p.area),centroid_x_h=float(p.centroid.x),centroid_z_h=float(p.centroid.y))
            edge=np.roll(a,-1,axis=0)-a;lens=np.linalg.norm(edge,axis=1)
            prev=np.roll(edge,1,axis=0);dot=(prev*edge).sum(axis=1);cross=prev[:,0]*edge[:,1]-prev[:,1]*edge[:,0]
            turns=np.degrees(np.arctan2(np.abs(cross),dot))
            r.update(floor_turn5_n=int((turns>5).sum()),floor_redundant5_n=int((turns<=5).sum()),
                     floor_short_edge_03_n=int((lens<.3).sum()),floor_short_edge_05_n=int((lens<.5).sum()),floor_edge_min_h=float(lens.min()))
    return clean(r)

def compute_pool(repo,out,pool,needed,reused,checkpoint=200):
    gs,fe,fr,sg=setup(repo);pid=pool['pool_id'];folder=Path(out)/'endpoints';target=folder/(pid+'.json.gz')
    rows={k:normalize(v,pool) for k,v in reused.items()};initial_keys=set(rows)
    if target.exists():
        saved=read(target)
        assert saved['pool_input_sha256']==gs.digest(pool)
        rows.update({r['team_key']:r for r in saved['teams']})
    missing=[(k,ws) for k,ws in needed.items() if k not in rows]
    start=time.monotonic();new_n=0;cache={};fusion_s=0;score_s=0
    def checkpoint_write(done=False):
        save(target,dict(pool_id=pid,pool_input_sha256=gs.digest(pool),teams=[rows[k] for k in needed if k in rows]))
        save(Path(out)/'progress'/(pid+'.json'),dict(pool_id=pid,requested=len(needed),available=len(set(needed)&rows.keys()),new_this_run=new_n,new_pending=len(missing)-new_n,complete=done,seconds=time.monotonic()-start))
    with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
        for key,ws in missing:
            r=fr.evaluate_one(pool,ws,engine,models,score_cache=cache)
            g=r.get('geometry')
            if g is not None:
                ck=fr.digest([r['k']==2,r.get('nodes'),g]);raw=cache.get(ck)
                if raw:r.update(raw)
            r=normalize(r,pool);r['endpoint_origin']='new_native_prefix_20261023'
            r=geometry_enrich(r,pool,fr);rows[key]=r;new_n+=1
            fusion_s+=r.get('fusion_seconds',0);score_s+=r.get('score_seconds',0)
            if new_n%checkpoint==0:checkpoint_write()
    checkpoint_write(done=True)
    result=dict(pool_id=pid,requests=len(needed),reused_historical=len(initial_keys),new_native=new_n,available=len(needed),seconds=time.monotonic()-start,fusion_seconds=fusion_s,score_seconds=score_s,
                score_available=sum(rows[k]['score_available'] for k in needed),failures_nonpolicy=sum(rows[k]['score_failure_nonpolicy'] for k in needed),policy_deferred=sum(rows[k]['policy_deferred'] for k in needed))
    save(Path(out)/'receipts'/(pid+'.json'),result)
    return result

def make_links(orders):
    links=[];by=collections.defaultdict(dict)
    for r in orders.to_dict('records'):
        ws=r['worker_order'].split('|');target=set(str(r.get('target_members','')).split('|'))-{'','nan'}
        for k in range(1,len(ws)+1):
            current=ws[:k];key=team_key(r['pool_id'],current);by[r['pool_id']][key]=sorted(current)
            links.append(dict(pool_id=r['pool_id'],path_id=r['path_id'],base_path_id=r['base_path_id'],replicate=r['replicate'],policy=r['policy'],k=k,
                team_key=key,order_kind=r['order_kind'],generation=r['generation'],target_capacity=r.get('target_capacity'),
                target_present_n=sum(w in target for w in current),entrant_worker=ws[k-1],paired_for_policy=r.get('paired_for_policy'),
                target_class=r.get('target_class'),method=r.get('method'),tier=r.get('tier'),sample_kind=r.get('sample_kind',r.get('generation'))))
    return pd.DataFrame(links),by

def consolidate(out,orders,pools):
    """Bounded-memory consolidation; the pool shards are the durable authority."""
    out=Path(out);links,needed=make_links(orders);missing=[];columns=set();origin=collections.Counter()
    sharddir=out/'scalar_shards';sharddir.mkdir(parents=True,exist_ok=True)
    geometry_path=out/'ENDPOINT_GEOMETRY.json.gz';geometry_tmp=geometry_path.with_name(geometry_path.name+'.tmp')
    total=0;geometry_count=0;first_geometry=True
    def finish_file(temporary,target):
        with temporary.open('rb') as f:os.fsync(f.fileno())
        temporary.replace(target)
        if os.name != 'nt':
            fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
    geo_stream=gzip.GzipFile(filename=str(geometry_tmp),mode='wb',compresslevel=3,mtime=0)
    geo_stream.write(b'[')
    for pid,keys in needed.items():
        path=out/'endpoints'/(pid+'.json.gz')
        if not path.exists():missing.extend(keys);continue
        rows={r['team_key']:r for r in read(path)['teams']};missing.extend(set(keys)-rows.keys())
        scalar_rows=[];geo_rows=[]
        for key in keys:
            if key not in rows:continue
            r=rows[key];s={k:v for k,v in r.items() if not isinstance(v,(dict,list))}
            s['member_workers']='|'.join(r['member_workers']);s['member_object_ids']='|'.join(r['member_object_ids'])
            for f in ('node_supports','ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9'):
                if isinstance(r.get(f),list):s[f]='|'.join(map(str,r[f]))
            columns.update(s);scalar_rows.append(s);total+=1
            origin[r.get('endpoint_origin') or 'unclassified_pending_enrichment']+=1
            if r.get('geometry') is not None:geo_rows.append(dict(team_key=key,pool_id=pid,geometry=r['geometry'],node_supports=r.get('node_supports')))
        csv(sharddir/(pid+'.csv.gz'),pd.DataFrame(scalar_rows))
        if geo_rows:
            segment=json.dumps(clean(geo_rows),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()[1:-1]
            if not first_geometry:geo_stream.write(b',')
            geo_stream.write(segment);first_geometry=False;geometry_count+=len(geo_rows)
    geo_stream.write(b']');geo_stream.close()
    if missing:
        save(out/'MISSING_REGISTERED_ENDPOINTS.json',dict(count=len(missing),team_keys=missing))
        raise ValueError(f'{len(missing)} requests not yet saved; see MISSING_REGISTERED_ENDPOINTS.json')
    assert total==sum(len(v) for v in needed.values())
    columns=sorted(columns);prefix_columns=list(links.columns)+[c for c in columns if c not in links]
    scalar_path=out/'ENDPOINT_SCALARS.csv.gz';prefix_path=out/'PREFIX_RESULTS.csv.gz'
    scalar_tmp=scalar_path.with_name(scalar_path.name+'.tmp');prefix_tmp=prefix_path.with_name(prefix_path.name+'.tmp')
    scalar_stream=io.TextIOWrapper(gzip.GzipFile(filename=str(scalar_tmp),mode='wb',compresslevel=3,mtime=0),encoding='utf-8-sig',newline='')
    prefix_stream=io.TextIOWrapper(gzip.GzipFile(filename=str(prefix_tmp),mode='wb',compresslevel=3,mtime=0),encoding='utf-8-sig',newline='')
    grouped_links={pid:g for pid,g in links.groupby('pool_id',sort=False)};header=True;prefix_count=0
    for pid in needed:
        d=pd.read_csv(sharddir/(pid+'.csv.gz'),low_memory=False).reindex(columns=columns)
        assert not d.team_key.duplicated().any()
        d.to_csv(scalar_stream,index=False,header=header)
        own=grouped_links[pid];values=[c for c in d if c not in own or c=='team_key']
        joined=own.merge(d[values],on='team_key',how='left',validate='many_to_one').reindex(columns=prefix_columns)
        joined.to_csv(prefix_stream,index=False,header=header);prefix_count+=len(joined);header=False
    scalar_stream.close();prefix_stream.close()
    finish_file(geometry_tmp,geometry_path);finish_file(scalar_tmp,scalar_path);finish_file(prefix_tmp,prefix_path)
    csv(out/'PREFIX_TEAM_LINKS.csv.gz',links)
    assert prefix_count==len(links)
    save(out/'COMPLETION.json',dict(paths=len(orders),prefix_rows=len(links),unique_endpoints=total,geometry_endpoints=geometry_count,new_native=sum(v for k,v in origin.items() if k.startswith('new_native_')),new_native_bulk=origin['new_native_prefix_20261023'],new_native_benchmark=origin['new_native_benchmark_20261023'],sources=dict(origin),missing=0,consolidation='pool-streamed bounded-memory'))
    print('CONSOLIDATED',len(orders),len(links),total,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--orders',required=True);p.add_argument('--cache',action='append',default=[]);p.add_argument('--pool',action='append',help='Optional exact pool_id filter for selected-pool replay');p.add_argument('--out',required=True);p.add_argument('--jobs',type=int,default=7);p.add_argument('--consolidate-only',action='store_true');p.add_argument('--register-only',action='store_true');a=p.parse_args()
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True);gs,fe,fr,sg=setup(a.repo);pools=gs.pool_lookup();orders=pd.read_csv(a.orders,keep_default_na=False)
    if a.pool:
        if set(a.pool)-set(pools):raise ValueError('Unknown pool_id filter')
        orders=orders[orders.pool_id.isin(a.pool)].copy()
    if a.consolidate_only:consolidate(out,orders,pools);return
    links,by=make_links(orders);csv(out/'PREFIX_TEAM_LINKS.csv.gz',links)
    needed=set(links.team_key);cache={};source_counts={}
    for source in a.cache:
        path=Path(source)
        if path.name.endswith('.csv.gz') or path.name.endswith('.csv'):
            d=pd.read_csv(path,low_memory=False);d=d[d.team_key.isin(needed)]
            rows=d.to_dict('records')
        else:
            value=read(path);rows=value if isinstance(value,list) else value.get('teams',[])
        added=0
        for r in rows:
            key=r['team_key']
            if key in needed and key not in cache:cache[key]=r;added+=1
        source_counts[str(path)]=added
    manifest=dict(source_commit='72a44e80c344975962e1071bd54d894dd86bb4b4',data_release='v2',orders=len(orders),prefix_rows=len(links),unique_teams=len(needed),cache_hits=len(cache),new_requests=len(needed)-len(cache),cache_sources=source_counts,by_pool=[dict(pool_id=pid,unique_requests=len(ns),cache_hits=len(ns.keys()&cache.keys())) for pid,ns in by.items()])
    save(out/'REQUEST_COVERAGE.json',manifest);print(json.dumps({k:v for k,v in manifest.items() if k not in ('by_pool','cache_sources')}),flush=True)
    if a.register_only:return
    started=time.monotonic();done=[]
    # Short pools and a diversity of layers finish early; each pool checkpoints independently.
    work=sorted(by,key=lambda pid:(len(by[pid])-len(by[pid].keys()&cache.keys()),pid))
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futures={ex.submit(compute_pool,a.repo,str(out),pools[pid],by[pid],{k:cache[k] for k in by[pid].keys()&cache.keys()}):pid for pid in work}
        for f in concurrent.futures.as_completed(futures):
            r=f.result();done.append(r);save(out/'RUN_PROGRESS.json',dict(pools_finished=len(done),pools_total=len(by),seconds=time.monotonic()-started,by_pool=done))
            print(json.dumps(dict(r,finished=len(done),total=len(by))),flush=True)
    consolidate(out,orders,pools)

if __name__=='__main__':main()
