"""Monte Carlo precision of geometry variation under uniform population paths.

The estimand is E[d(T_k,T'_k) | both floors/metric valid] for two independent
uniform k-person subsets of a frozen pool. A sampled-path U statistic drops
only the same path paired with itself, retaining chance identical teams with
zero distance. Exact finite-population catalogues use M**2 including self-pairs.

No fusion, reference choice or scoring occurs in this program. Source input
geometry and complete-floor eligibility are read from the frozen endpoint table.
"""
from __future__ import annotations
import argparse
import collections
import concurrent.futures
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import sys

for dep in ['/tmp/hohonet_deps', '/tmp/hohonet_precision_deps']:
    if Path(dep).exists(): sys.path.insert(0,dep)
import numpy as np
import pandas as pd
from safe_io import install_safe_csv_writer
install_safe_csv_writer()

METRICS=['V_floor','V_centroid_h','V_height_h','V_turn5','V_nodes']
META=['pool_id','image','image_id','building','condition','layer','difficulty','pool_n']


def array_items(path, chunk_size=1<<20):
    """Stream one top-level JSON array through EOF with the standard decoder."""
    opener=gzip.open if str(path).endswith('.gz') else open
    decoder=json.JSONDecoder()
    with opener(path,'rt',encoding='utf8') as f:
        buf=''; pos=0; started=False; eof=False
        while True:
            if not eof and (not buf or pos>=len(buf)):
                buf=f.read(chunk_size);pos=0;eof=not bool(buf)
            while pos<len(buf) and buf[pos].isspace():pos+=1
            if not started:
                if pos==len(buf):
                    if eof:raise ValueError('Empty JSON')
                    continue
                if buf[pos]!='[':raise ValueError('Expected JSON array')
                pos+=1;started=True
            while pos<len(buf) and (buf[pos].isspace() or buf[pos]==','):pos+=1
            if pos<len(buf) and buf[pos]==']':
                # Consume trailer/gzip footer so corruption cannot be hidden.
                trailer=buf[pos+1:]+f.read()
                if trailer.strip():raise ValueError('Unexpected JSON trailer')
                return
            try:
                value,end=decoder.raw_decode(buf,pos)
            except json.JSONDecodeError:
                if eof:raise
                more=f.read(chunk_size)
                eof=not bool(more)
                buf=buf[pos:]+more;pos=0
                continue
            yield value
            pos=end


def dump_json(path, value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))


def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4<<20),b''):h.update(block)
    return h.hexdigest()


def prepare_compact_new(directory,cache_root):
    """Join the delivered compact geometry to delivered scalars once.

    The large optional full-state files are not required for this route.
    The resulting per-pool pickles are temporary rebuildable analysis caches.
    """
    directory=Path(directory)
    geo=directory/'NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz'
    scalar=directory/'NEW_ENDPOINT_SCALARS.csv.gz'
    if not geo.exists() or not scalar.exists():return directory
    stamp={'geometry_sha256':sha_file(geo),'scalar_sha256':sha_file(scalar)}
    cache=Path(cache_root)/'new_compact_pool_geometry_cache';cache.mkdir(exist_ok=True)
    receipt=cache/'INPUT_RECEIPT.json'
    if receipt.exists() and all(json.loads(receipt.read_text()).get(k)==v for k,v in stamp.items()):return cache
    fields=['team_key','pool_id','complete_floor_evaluable','height_mean_h','floor_turn5_n','nodes']
    rows={}
    for d in pd.read_csv(scalar,usecols=fields,chunksize=25000):
        for r in d.to_dict('records'):
            if r['team_key'] in rows:raise ValueError('Duplicate new scalar team')
            rows[r['team_key']]=r
    seen=set()
    with gzip.open(geo,'rt') as f:
        for line in f:
            r=json.loads(line);key=r['team_key']
            if key not in rows or key in seen:raise ValueError('Compact geometry key mismatch')
            rows[key]['geometry']=r.get('geometry');seen.add(key)
    if seen!=rows.keys():raise ValueError('Incomplete compact geometry/scalar join')
    by=collections.defaultdict(dict)
    for key,r in rows.items():by[r['pool_id']][key]=r
    for pid,dd in by.items():
        target=cache/(pid+'.pkl');temp=target.with_name(target.name+'.tmp')
        with temp.open('wb') as f:pickle.dump(dd,f,protocol=5)
        temp.replace(target)
    dump_json(receipt,dict(stamp,scalar_teams=len(rows),geometry_records=len(seen),pools=len(by),compact_read_to_eof=True,optional_full_state_files_used=False))
    return cache


def prepare(base,out):
    out.mkdir(parents=True,exist_ok=True)
    orders=pd.read_csv(base/'design/EXACT_ORDER_DESIGN.csv.gz',low_memory=False)
    orders=orders[orders.policy.eq('natural_random') & orders.layer.isin(['ordinary_manual','doorway_manual'])]
    links=pd.read_csv(base/'results/PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    links=links[links.path_id.isin(orders.path_id)].copy()
    links['batch']='old24'; links.to_csv(out/'OLD_NATURAL_LINKS.csv.gz',index=False)
    orders.to_csv(out/'OLD_NATURAL_ORDERS.csv.gz',index=False)
    needed=set(links.team_key); rows={};pool_ids=set(orders.pool_id)
    columns=['team_key','pool_id','complete_floor_evaluable','height_mean_h','floor_turn5_n','nodes']
    for d in pd.read_csv(base/'results/ENDPOINT_SCALARS.csv.gz',usecols=columns,chunksize=25000):
        # Additional natural prefixes can reuse an old policy/team endpoint that
        # was not present among the original natural paths.
        rows.update({r['team_key']:r for r in d[d.pool_id.isin(pool_ids)].to_dict('records')})
    geometry_count=0
    for r in array_items(base/'results/ENDPOINT_GEOMETRY.json.gz'):
        key=r['team_key']
        if key in rows:
            rows[key]['geometry']=r['geometry'];geometry_count+=1
    by=collections.defaultdict(dict)
    for key,r in rows.items():by[r['pool_id']][key]=r
    cache=out/'old_pool_geometry_cache';cache.mkdir(exist_ok=True)
    for pid,dd in by.items():
        with (cache/(pid+'.pkl')).open('wb') as f:pickle.dump(dd,f,protocol=5)
    receipt=dict(source='main existing endpoints',pools=len(by),paths=len(orders),prefixes=len(links),requested_natural_teams=len(needed),cached_scalar_teams=len(rows),geometry_teams=geometry_count,new_fusions=0)
    dump_json(out/'PREPARE_RECEIPT.json',receipt)
    print(json.dumps(receipt),flush=True)


def ustat(d,exact_population=False):
    """Return ratio-U mean and delete-one-attempt jackknife.

    Invalid endpoints remain in the attempt count. For a conditional valid-floor
    estimand, deleting an invalid path leaves the ratio unchanged. Missing
    deletes are never manufactured when fewer than 3 valid paths remain.
    """
    n=len(d)
    valid=np.isfinite(np.diag(d));q=int(valid.sum())
    if not q:return dict(mean=np.nan,mcse=np.nan,valid_paths=0,valid_pairs=0,attempted_paths=n),np.full(n,np.nan)
    a=np.asarray(d,float).copy();np.fill_diagonal(a,0.)
    if exact_population:
        # Here each catalogue member appears once with its exact natural weight.
        value=float(np.nansum(a)/(q*q))
        return dict(mean=value,mcse=0.,valid_paths=q,valid_pairs=q*q,attempted_paths=n),np.full(n,value)
    if q<2:return dict(mean=np.nan,mcse=np.nan,valid_paths=q,valid_pairs=0,attempted_paths=n),np.full(n,np.nan)
    total=float(np.nansum(a));theta=total/(q*(q-1))
    leave=np.full(n,theta)
    if q>=3:
        leave[valid]=(total-2*np.nansum(a[valid],axis=1))/((q-1)*(q-2))
        mcse=float(np.sqrt((n-1)/n*np.sum((leave-leave.mean())**2)))
    else:mcse=np.nan;leave[valid]=np.nan
    return dict(mean=float(theta),mcse=mcse,valid_paths=q,valid_pairs=q*(q-1)//2,attempted_paths=n),leave


def distance_matrices(team_keys,rows):
    import shapely
    from shapely.geometry import Polygon
    use=[];polys=[]
    for key in dict.fromkeys(team_keys):
        r=rows.get(key,{})
        g=r.get('geometry') or {};floor=g.get('footprint')
        if not r.get('complete_floor_evaluable') or floor is None or len(floor)<3:continue
        p=Polygon(floor)
        if not p.is_valid or not math.isfinite(p.area) or p.area<=0:continue
        use.append(key);polys.append(p)
    n=len(team_keys);m=len(use)
    answer={x:np.full((n,n),np.nan) for x in METRICS}
    if not m:return answer
    index={k:i for i,k in enumerate(use)}
    ok=np.array([k in index for k in team_keys]);lookup=np.array([index[k] for k in team_keys if k in index])
    areas=np.array([p.area for p in polys]);xy=np.array([[p.centroid.x,p.centroid.y] for p in polys])
    ii,jj=np.triu_indices(m,1);v=np.zeros((m,m))
    if len(ii):
        pp=np.asarray(polys,dtype=object)
        inter=shapely.area(shapely.intersection(pp[ii],pp[jj]))
        delta=1-inter/(areas[ii]+areas[jj]-inter)
        v[ii,jj]=delta;v[jj,ii]=delta
    compact={'V_floor':v,'V_centroid_h':np.linalg.norm(xy[:,None,:]-xy[None,:,:],axis=2)}
    for metric,field in [('V_height_h','height_mean_h'),('V_turn5','floor_turn5_n'),('V_nodes','nodes')]:
        x=np.array([rows[k].get(field,np.nan) if rows[k].get(field) is not None else np.nan for k in use],float)
        compact[metric]=np.abs(x[:,None]-x[None,:])
    ix=np.flatnonzero(ok)
    for metric,a in compact.items():answer[metric][np.ix_(ix,ix)]=a[np.ix_(lookup,lookup)]
    return answer


def read_new_pool(directory,pid):
    directory=Path(directory)
    cached=directory/(pid+'.pkl')
    if cached.exists():
        with cached.open('rb') as f:return pickle.load(f)
    parts=directory/'parts'/pid
    if parts.exists():
        rows={}
        keep=['team_key','pool_id','complete_floor_evaluable','height_mean_h','floor_turn5_n','nodes']
        for receipt_path in sorted(parts.glob('part_*.receipt.json')):
            receipt=json.loads(receipt_path.read_text())
            scalar=parts/receipt['scalar_file']
            part={r['team_key']:r for r in pd.read_csv(scalar,usecols=lambda c:c in keep).to_dict('records')}
            geometry=parts/receipt['geometry_file']
            if set(part)!=set(receipt['team_keys']):raise ValueError('Scalar/receipt team keys differ')
            with gzip.open(geometry,'rt') as f:
                for line in f:
                    r=json.loads(line)
                    if r['team_key'] in part:part[r['team_key']]['geometry']=r.get('geometry')
            rows.update(part)
        return rows
    path=directory/(pid+'.json.gz')
    if not path.exists():return {}
    with gzip.open(path,'rt') as f:data=json.load(f)
    rows=data['teams'] if isinstance(data,dict) else data
    return {r['team_key']:r for r in rows}


def pool_run(pid,meta,links,cache,new_dirs):
    path=Path(cache)/(pid+'.pkl')
    with path.open('rb') as f:rows=pickle.load(f)
    for directory in new_dirs:
        for key,r in read_new_pool(directory,pid).items():rows.setdefault(key,r)
    cohorts={'old24':{'old24'}}
    present=set(links.batch)
    if 'new24' in present:
        cohorts['new24']={'new24'};cohorts['combined48']={'old24','new24'}
    if 'focus48' in present:
        cohorts['focus48']={'focus48'};cohorts['combined96']={'old24','new24','focus48'}
    stats=[];intervals=[];missing=[];jack={}
    for k,g in links.groupby('k',sort=True):
        if int(k)==2:continue
        # Missing newly requested endpoint is not a fusion failure and is kept
        # separately from invalid complete-floor outcomes.
        known=g.team_key.isin(rows)
        missing.extend(g.loc[~known,['pool_id','path_id','k','team_key','batch']].to_dict('records'))
        matrices=distance_matrices(g.team_key.tolist(),rows)
        for cohort,batches in cohorts.items():
            mask=g.batch.isin(batches).to_numpy();own=g[mask]
            if not len(own):continue
            if not own.team_key.isin(rows).all():continue
            for metric,mat in matrices.items():
                a=mat[np.ix_(mask,mask)]
                result,leave=ustat(a)
                common=dict(meta,cohort=cohort,k=int(k),metric=metric,unique_teams=own.team_key.nunique(),full_pool_endpoint=int(k)==int(meta['pool_n']),**result)
                stats.append(common)
                jack[(cohort,int(k),metric)]=(own.path_id.tolist(),leave,result['mean'])
    pairs=[(1,3),(3,4),(4,5),(5,6),(3,6),(6,10),(10,20),(20,30),(30,35),(3,int(meta['pool_n'])),(20,int(meta['pool_n'])),(30,int(meta['pool_n']))]
    for a,b in sorted(set(pairs)):
        if a>=b:continue
        for cohort in cohorts:
            for metric in METRICS:
                left=jack.get((cohort,a,metric));right=jack.get((cohort,b,metric))
                if left is None or right is None:continue
                li,lv,lmean=left;ri,rv,rmean=right
                if li!=ri:
                    if set(li)!=set(ri):continue
                    loc={x:i for i,x in enumerate(ri)};rv=np.array([rv[loc[x]] for x in li])
                delta=float(rmean-lmean)
                dl=rv-lv;n=len(dl)
                se=float(np.sqrt((n-1)/n*np.sum((dl-dl.mean())**2))) if np.isfinite(dl).all() else np.nan
                intervals.append(dict(meta,cohort=cohort,k_from=a,k_to=b,metric=metric,delta=delta,mcse=se,paired_paths=n))
    if new_dirs and not missing:
        # Disposable derived geometry cache avoids parsing large saved full
        # identity states again for the exact-margin comparison. Never package
        # this cache instead of the actual new endpoint geometry/state shards.
        combined=Path(cache).parent/'combined_pool_geometry_cache';combined.mkdir(exist_ok=True)
        target=combined/(pid+'.pkl');tmp=target.with_name(target.name+'.tmp')
        with tmp.open('wb') as f:pickle.dump(rows,f,protocol=5)
        tmp.replace(target)
    return stats,intervals,missing


def run(base,out,new_orders,new_dirs,jobs):
    orders=pd.read_csv(out/'OLD_NATURAL_ORDERS.csv.gz',low_memory=False)
    links=pd.read_csv(out/'OLD_NATURAL_LINKS.csv.gz',low_memory=False)
    if new_orders:
        extra=pd.read_csv(new_orders,low_memory=False)
        extra=extra[extra.policy.eq('natural_random') & extra.pool_id.isin(orders.pool_id)].copy()
        # Caller must supply the exact batch identity; never classify a path
        # according to the outcome or infer completed attempts from scores.
        if 'batch' not in extra:
            raise ValueError('New design requires explicit batch identity')
        extra['batch']=extra.batch.replace({'balanced_new24':'new24','focus_new48':'focus48'})
        if 'k' in extra and 'team_key' in extra:
            xl=extra
        else:
            sys.path.insert(0,str(base/'code'))
            from run_prefix_endpoints import make_links
            xl,_=make_links(extra)
            xl=xl.merge(extra[['path_id','batch']],on='path_id',validate='many_to_one')
        links=pd.concat([links,xl],ignore_index=True)
    assert not links.duplicated(['path_id','k']).any()
    metas=orders.groupby('pool_id').first()[[c for c in META if c!='pool_id']].to_dict('index')
    new_dirs=[prepare_compact_new(x,out) for x in new_dirs]
    records=[];changes=[];missing=[]
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as executor:
        todo={executor.submit(pool_run,pid,dict(pool_id=pid,**metas[pid]),g,out/'old_pool_geometry_cache',new_dirs):pid for pid,g in links.groupby('pool_id',sort=False)}
        for i,future in enumerate(concurrent.futures.as_completed(todo),1):
            ss,dd,mm=future.result();records.extend(ss);changes.extend(dd);missing.extend(mm)
            if i%20==0:print('geometry pools',i,'/',len(todo),flush=True)
    pd.DataFrame(records).to_csv(out/'GEOMETRY_PATH_PRECISION.csv.gz',index=False)
    pd.DataFrame(changes).to_csv(out/'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz',index=False)
    pd.DataFrame(missing,columns=['pool_id','path_id','k','team_key','batch']).to_csv(out/'GEOMETRY_UNCOMPUTED_LINKS.csv.gz',index=False)
    dump_json(out/'RUN_RECEIPT.json',dict(pools=len(metas),geometry_metric_rows=len(records),paired_interval_rows=len(changes),uncomputed_links=len(missing),old_endpoint_source=str(base/'results/ENDPOINT_GEOMETRY.json.gz'),new_endpoint_dirs=[str(x) for x in new_dirs],fusion_calls=0,uncertainty='delete-one-whole-path jackknife conditional valid-floor ratio U statistic'))
    print('DONE geometry',len(records),'intervals',len(changes),'missing',len(missing),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--prepare',action='store_true')
    ap.add_argument('--new-orders')
    ap.add_argument('--new-endpoints-dir',action='append',default=[])
    ap.add_argument('--jobs',type=int,default=3)
    a=ap.parse_args();base=Path(a.base);out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    if a.prepare:prepare(base,out)
    else:run(base,out,a.new_orders,a.new_endpoints_dir,a.jobs)


if __name__=='__main__':main()
