"""Exact path-weighted geometry U-statistics for the 2026-10-26 extension.

Only saved geometry is read. The frozen fusion, qualification and metric inputs
are unchanged. Completely identical coordinate arrays share one distance
calculation; every random path retains its original sampling multiplicity.
"""
from __future__ import annotations
import argparse,collections,concurrent.futures,csv,gzip,hashlib,io,json,math,os,pickle,sys,time
from pathlib import Path
for dep in ['/tmp/hohonet_deps']:
    if Path(dep).exists():sys.path.insert(0,dep)
import numpy as np
import pandas as pd
from safe_io import atomic_bytes,install_safe_csv_writer
install_safe_csv_writer()

METRICS=['V_floor','V_centroid_h','V_height_h','V_turn5','V_nodes']
META=['pool_id','image','image_id','building','condition','layer','difficulty','pool_n']
KEEP=['team_key','pool_id','complete_floor_evaluable','height_mean_h','floor_turn5_n','nodes']
COHORTS={
 'old48':{'old24','prior_new24'},
 'stage1_104':{'extension_stage1_104'},
 'stage2_104':{'extension_stage2_104'},
 'new208':{'extension_stage1_104','extension_stage2_104'},
 'pooled152':{'old24','prior_new24','extension_stage1_104'},
 'pooled256':{'old24','prior_new24','extension_stage1_104','extension_stage2_104'},
 'prior96':{'old24','prior_new24','prior_focus48'},
 'all_history304':{'old24','prior_new24','prior_focus48','extension_stage1_104','extension_stage2_104'},
}


def file_sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save_json(path,obj):
    atomic_bytes(path,json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False).encode())


def save_pickle(path,obj):atomic_bytes(path,pickle.dumps(obj,protocol=5))


def array_items(path,chunk_size=1<<20):
    """Stream the old top-level geometry array and consume its gzip trailer."""
    decoder=json.JSONDecoder()
    with gzip.open(path,'rt',encoding='utf-8') as f:
        buf='';pos=0;started=False;eof=False
        while True:
            if not eof and (not buf or pos>=len(buf)):
                buf=f.read(chunk_size);pos=0;eof=not bool(buf)
            while pos<len(buf) and buf[pos].isspace():pos+=1
            if not started:
                if pos==len(buf):
                    if eof:raise ValueError('Empty JSON array')
                    continue
                assert buf[pos]=='[';pos+=1;started=True
            while pos<len(buf) and (buf[pos].isspace() or buf[pos]==','):pos+=1
            if pos<len(buf) and buf[pos]==']':
                if (buf[pos+1:]+f.read()).strip():raise ValueError('JSON trailer')
                return
            try:obj,end=decoder.raw_decode(buf,pos)
            except json.JSONDecodeError:
                if eof:raise
                more=f.read(chunk_size);eof=not bool(more);buf=buf[pos:]+more;pos=0;continue
            yield obj;pos=end


def bool_true(value):
    return value is True or isinstance(value,(int,np.integer)) and value==1 or str(value).lower()=='true'


def slim_geometry(value):
    if not isinstance(value,dict):return None
    return {'footprint':value.get('footprint')}


def read_scalar_rows(path,pools=None):
    result={}
    for d in pd.read_csv(path,usecols=KEEP,chunksize=30000):
        if pools is not None:d=d[d.pool_id.isin(pools)]
        for r in d.to_dict('records'):
            assert r['team_key'] not in result
            r['complete_floor_evaluable']=bool_true(r['complete_floor_evaluable'])
            result[r['team_key']]=r
    return result


def prepare(study,population,prior):
    """Build disposable per-pool geometry caches from actual delivered files."""
    out=study/'analysis_geometry26';cache=out/'cache/baseline';cache.mkdir(parents=True,exist_ok=True)
    orders=pd.read_csv(population/'design/EXACT_ORDER_DESIGN.csv.gz',low_memory=False)
    orders=orders[orders.policy.eq('natural_random')&orders.layer.isin(['ordinary_manual','doorway_manual'])].copy()
    metas=orders.groupby('pool_id',sort=False).first().reset_index()[META]
    assert len(metas)==194
    old_links=pd.read_csv(population/'results/PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    old_links=old_links[old_links.path_id.isin(orders.path_id)][['pool_id','path_id','k','team_key']].copy()
    old_links['batch']='old24'
    prior_links=pd.read_csv(prior/'design/NEW_PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    prior_links=prior_links[prior_links.policy.eq('natural_random')][['pool_id','path_id','k','team_key','batch']].copy()
    prior_links['batch']=prior_links.batch.replace({'balanced_new24':'prior_new24','focus_new48':'prior_focus48'})
    assert set(prior_links.batch)<= {'prior_new24','prior_focus48'}
    links=pd.concat([old_links,prior_links],ignore_index=True)
    assert not links.duplicated(['path_id','k']).any()
    links.to_csv(out/'BASELINE_NATURAL_LINKS.csv.gz',index=False)
    metas.to_csv(out/'POOL_META.csv',index=False)
    pools=set(metas.pool_id)
    scalar_old=study/'inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz'
    if not scalar_old.exists():scalar_old=population/'results/ENDPOINT_SCALARS.csv.gz'
    scalar_prior=study/'inputs_cache26/precision25/NEW_ENDPOINT_SCALARS.csv.gz'
    geo_prior=study/'inputs_cache26/precision25/NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz'
    geo_old=population/'results/ENDPOINT_GEOMETRY.json.gz'
    for path in [scalar_old,scalar_prior,geo_prior,geo_old]:
        if not path.exists():raise FileNotFoundError(path)
    stamps={str(x.resolve()):file_sha(x) for x in [scalar_old,scalar_prior,geo_old,geo_prior]}
    receipt=cache/'INPUT_RECEIPT.json'
    if receipt.exists() and json.loads(receipt.read_text()).get('inputs')==stamps:
        print('BASELINE_CACHE_REUSED',flush=True);return
    rows=read_scalar_rows(scalar_old,pools)
    old_scalar_n=len(rows);seen=set()
    for r in array_items(geo_old):
        key=r['team_key']
        if key in rows:
            rows[key]['geometry']=slim_geometry(r.get('geometry'));seen.add(key)
    missing_old=set(rows)-seen
    eligible_missing=[key for key in missing_old if rows[key]['complete_floor_evaluable']]
    assert not eligible_missing,('old eligible geometry missing',len(eligible_missing),eligible_missing[:2])
    pd.DataFrame([dict(team_key=k,pool_id=rows[k]['pool_id'],complete_floor_evaluable=False,
        geometry_source_status='no_old_geometry_record_for_noncomplete_endpoint') for k in sorted(missing_old)],
        columns=['team_key','pool_id','complete_floor_evaluable','geometry_source_status']).to_csv(out/'BASELINE_NONCOMPLETE_WITHOUT_GEOMETRY.csv',index=False)
    prior_rows=read_scalar_rows(scalar_prior,pools);prior_seen=set()
    with gzip.open(geo_prior,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);key=r['team_key']
            if key in prior_rows:
                assert key not in prior_seen
                prior_rows[key]['geometry']=slim_geometry(r.get('geometry'));prior_seen.add(key)
    assert prior_seen==set(prior_rows)
    assert not set(rows)&set(prior_rows)
    rows.update(prior_rows)
    by=collections.defaultdict(dict)
    for key,r in rows.items():by[r['pool_id']][key]=r
    for pid,dd in by.items():save_pickle(cache/(pid+'.pkl'),dd)
    missing=set(links.team_key)-set(rows);assert not missing,len(missing)
    save_json(receipt,dict(inputs=stamps,pools=len(by),baseline_paths=links.path_id.nunique(),baseline_prefixes=len(links),
        old_scalar_teams=old_scalar_n,prior_new_scalar_teams=len(prior_rows),cached_teams=len(rows),
        all_geometry_sources_read_to_eof=True,old_noncomplete_without_geometry_record=len(missing_old),
        eligible_geometry_missing=0,only_footprints_and_saved_scalar_diagnostics_kept=True,new_fusions=0))
    print('BASELINE_CACHE_COMPLETE',len(by),len(rows),flush=True)


def distance_matrices(team_keys,rows):
    """Exact identical-footprint dedup; expansion preserves every path weight."""
    import shapely
    from shapely.geometry import Polygon
    eligible={};geometries=[];geometry_index={};geometry_for_team={}
    for key in dict.fromkeys(team_keys):
        r=rows[key]
        floor=(r.get('geometry') or {}).get('footprint')
        if not bool_true(r.get('complete_floor_evaluable')) or floor is None or len(floor)<3:continue
        xy=np.asarray(floor,dtype='<f8')
        if xy.ndim!=2 or xy.shape[1]!=2 or not np.isfinite(xy).all():continue
        fingerprint=(xy.shape,xy.tobytes())
        if fingerprint not in geometry_index:
            poly=Polygon(xy)
            if not poly.is_valid or not math.isfinite(poly.area) or poly.area<=0:continue
            geometry_index[fingerprint]=len(geometries);geometries.append(poly)
        gi=geometry_index[fingerprint];eligible[key]=r;geometry_for_team[key]=gi
    n=len(team_keys);out={m:np.full((n,n),np.nan) for m in METRICS}
    positions=np.array([i for i,k in enumerate(team_keys) if k in eligible],dtype=int)
    known=[team_keys[i] for i in positions]
    count=len(known);g=len(geometries)
    diagnostic={'paths':n,'eligible_unique_teams':len(eligible),'unique_exact_footprints':g,
        'distinct_polygon_pair_evaluations':g*(g-1)//2,'team_pair_evaluations_without_footprint_dedup':len(eligible)*(len(eligible)-1)//2}
    if not count:return out,diagnostic
    lookup=np.array([geometry_for_team[k] for k in known])
    polys=np.asarray(geometries,dtype=object);area=shapely.area(polys)
    center=shapely.get_coordinates(shapely.centroid(polys))
    distances=np.zeros((g,g),dtype=float)
    ii,jj=np.triu_indices(g,1)
    if len(ii):
        inter=shapely.area(shapely.intersection(polys[ii],polys[jj]))
        dist=1-inter/(area[ii]+area[jj]-inter)
        distances[ii,jj]=dist;distances[jj,ii]=dist
    out['V_floor'][np.ix_(positions,positions)]=distances[np.ix_(lookup,lookup)]
    centers=center[lookup]
    out['V_centroid_h'][np.ix_(positions,positions)]=np.linalg.norm(centers[:,None,:]-centers[None,:,:],axis=2)
    for metric,field in [('V_height_h','height_mean_h'),('V_turn5','floor_turn5_n'),('V_nodes','nodes')]:
        x=np.array([eligible[k].get(field,np.nan) if eligible[k].get(field) is not None else np.nan for k in known],float)
        out[metric][np.ix_(positions,positions)]=np.abs(x[:,None]-x[None,:])
    return out,diagnostic


def ustat(d,exact=False):
    n=len(d);valid=np.isfinite(np.diag(d));q=int(valid.sum())
    base=dict(attempted_paths=n,valid_paths=q,valid_pairs=q*(q-1)//2)
    if q==0:return dict(base,mean=np.nan,mcse=np.nan,metric_status='no_valid_geometry'),np.full(n,np.nan)
    a=np.array(d,float,copy=True);np.fill_diagonal(a,0.)
    total=float(np.nansum(a))
    if exact:
        base['valid_pairs']=q*q
        return dict(base,mean=total/(q*q),mcse=0.,metric_status='exact_finite',exact_pair_denominator=q*q,
            exact_sampling_target='two independent uniform valid teams; same-team draws retained'),np.full(n,total/(q*q))
    if q<2:return dict(base,mean=np.nan,mcse=np.nan,metric_status='fewer_than_two_valid_paths'),np.full(n,np.nan)
    theta=total/(q*(q-1));leave=np.full(n,theta)
    if q<3:
        leave[valid]=np.nan
        return dict(base,mean=theta,mcse=np.nan,metric_status='point_only_two_valid_paths'),leave
    leave[valid]=(total-2*np.nansum(a[valid],axis=1))/((q-1)*(q-2))
    se=float(np.sqrt((n-1)/n*np.sum((leave-leave.mean())**2)))
    return dict(base,mean=theta,mcse=se,metric_status='estimable'),leave


def read_new_pool(study,pid,through_stage):
    rows={};parts_read=0
    for stage in range(1,through_stage+1):
        directory=study/f'new_endpoints26/stage{stage}/parts'/pid
        if not (directory/'POOL_RECEIPT.json').exists():raise FileNotFoundError(directory/'POOL_RECEIPT.json')
        for scalar in sorted(directory.glob('part_*.scalars.csv.gz')):
            part=read_scalar_rows(scalar)
            geo=scalar.with_name(scalar.name.replace('.scalars.csv.gz','.geometry_compact.jsonl.gz'))
            if not geo.exists():raise FileNotFoundError(geo)
            seen=set()
            with gzip.open(geo,'rt',encoding='utf-8') as f:
                for line in f:
                    r=json.loads(line);key=r['team_key'];assert key in part and key not in seen
                    part[key]['geometry']=slim_geometry(r.get('geometry'));seen.add(key)
            assert seen==set(part)
            assert not set(rows)&set(part)
            rows.update(part);parts_read+=1
    return rows,parts_read


def registered_links(study,pools,through_stage):
    """Use verified atomic per-pool registration shards, never the quarantined
    long-stream global prefix export from the early registration attempt."""
    receipt=study/'design26/REGISTRATION_RECEIPT.json'
    if not receipt.exists():raise FileNotFoundError(receipt)
    frames=[]
    for stage in range(1,through_stage+1):
        for pid in sorted(pools):
            path=study/f'design26/links_by_pool/stage{stage}'/(pid+'.csv.gz')
            d=pd.read_csv(path,low_memory=False)
            d=d[d.policy.eq('natural_random')]
            assert set(d.pool_id)=={pid}
            assert set(d.batch)=={f'extension_stage{stage}_104'}
            assert d.path_id.nunique()==104,(pid,stage,d.path_id.nunique())
            assert not d.duplicated(['path_id','k']).any()
            frames.append(d[['pool_id','path_id','k','team_key','batch']])
    return pd.concat(frames,ignore_index=True)


def one_pool(study,out,pid,meta,links,through_stage):
    started=time.monotonic()
    with (out/'cache/baseline'/(pid+'.pkl')).open('rb') as f:rows=pickle.load(f)
    new,new_parts=read_new_pool(study,pid,through_stage)
    assert not set(rows)&set(new)
    rows.update(new)
    present=set(links.batch)
    cohorts={k:v for k,v in COHORTS.items() if v<=present}
    if 'prior_focus48' not in present:
        cohorts.pop('prior96',None);cohorts.pop('all_history304',None)
    stats=[];jack={};dedup=[];missing=[]
    for k,g in links.groupby('k',sort=True):
        k=int(k);g=g.sort_values('path_id').reset_index(drop=True)
        absent=~g.team_key.isin(rows)
        if absent.any():
            missing.extend(g.loc[absent,['pool_id','path_id','k','team_key','batch']].to_dict('records'));continue
        if k==2:
            for cohort,batches in cohorts.items():
                own=g[g.batch.isin(batches)]
                for metric in METRICS:
                    stats.append(dict(meta,cohort=cohort,k=k,metric=metric,mean=np.nan,mcse=np.nan,
                        attempted_paths=len(own),valid_paths=0,valid_pairs=0,unique_teams=own.team_key.nunique(),
                        metric_status='two_person_policy_deferred',full_pool_endpoint=False))
            continue
        matrices,diagnostic=distance_matrices(g.team_key.tolist(),rows)
        dedup.append(dict(pool_id=pid,k=k,through_stage=through_stage,**diagnostic))
        for cohort,batches in cohorts.items():
            mask=g.batch.isin(batches).to_numpy();own=g[mask]
            for metric,mat in matrices.items():
                result,leave=ustat(mat[np.ix_(mask,mask)])
                stats.append(dict(meta,cohort=cohort,k=k,metric=metric,unique_teams=own.team_key.nunique(),
                    full_pool_endpoint=k==int(meta['pool_n']),**result))
                jack[(cohort,k,metric)]=(own.path_id.tolist(),leave,result['mean'])
    if missing:raise ValueError(('missing executed geometry',pid,len(missing),missing[:2]))
    N=int(meta['pool_n']);pairs={(k,k+1) for k in range(3,N)}
    pairs.update([(1,3),(3,6),(6,10),(10,20),(20,30),(30,35),(1,N),(3,N),(6,N),(10,N),(20,N),(30,N),(35,N),(N-1,N)])
    intervals=[]
    for a,b in sorted(pairs):
        # A pool whose full size equals a fixed starting k has a genuine zero
        # change when that endpoint is valid. Keep it for fixed-support
        # comparisons to actual full population; invalid full stays missing.
        if a>b or b>N or a>N:continue
        for cohort in cohorts:
            for metric in METRICS:
                left=jack.get((cohort,a,metric));right=jack.get((cohort,b,metric))
                if left is None or right is None:continue
                li,lv,lmean=left;ri,rv,rmean=right
                assert li==ri
                n=len(li);delta=float(rmean-lmean);diff=rv-lv
                se=float(np.sqrt((n-1)/n*np.sum((diff-diff.mean())**2))) if np.isfinite(diff).all() else np.nan
                intervals.append(dict(meta,cohort=cohort,k_from=a,k_to=b,metric=metric,delta=delta,mcse=se,
                    paired_paths=n,interval_status='estimable' if np.isfinite(se) else 'not_estimable',
                    adjacent_step=b==a+1,ends_at_actual_full=b==N,
                    same_endpoint=a==b))
    stage_dir=out/f'checkpoints/stage{through_stage}';stage_dir.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(stats).to_csv(stage_dir/(pid+'.precision.csv.gz'),index=False)
    pd.DataFrame(intervals).to_csv(stage_dir/(pid+'.intervals.csv.gz'),index=False)
    pd.DataFrame(dedup).to_csv(stage_dir/(pid+'.dedup.csv.gz'),index=False)
    receipt=dict(pool_id=pid,through_stage=through_stage,geometry_rows=len(stats),interval_rows=len(intervals),
        cached_teams=len(rows),new_scalar_geometry_parts_read=new_parts,uncomputed_links=0,
        unique_polygon_pairs=sum(x['distinct_polygon_pair_evaluations'] for x in dedup),
        team_pairs_without_footprint_dedup=sum(x['team_pair_evaluations_without_footprint_dedup'] for x in dedup),
        elapsed_seconds=time.monotonic()-started,point_estimator='path-frequency U statistic',
        mcse='delete-one-whole-path jackknife',new_fusions=0)
    save_json(stage_dir/(pid+'.receipt.json'),receipt)
    return receipt


def run(study,out,stage,jobs,once,pool_filter=None):
    old=pd.read_csv(out/'BASELINE_NATURAL_LINKS.csv.gz',low_memory=False)
    use_pools=set(old.pool_id) if pool_filter is None else pool_filter
    new=registered_links(study,use_pools,stage)
    links=pd.concat([old,new],ignore_index=True)
    assert not links.duplicated(['path_id','k']).any()
    metas=pd.read_csv(out/'POOL_META.csv').set_index('pool_id').to_dict('index')
    by={pid:g for pid,g in links.groupby('pool_id',sort=True) if pool_filter is None or pid in pool_filter}
    check=out/f'checkpoints/stage{stage}';check.mkdir(parents=True,exist_ok=True)
    done={pid for pid in by if (check/(pid+'.receipt.json')).exists()}
    print('GEOMETRY_RESUME',stage,len(done),len(by),flush=True)
    with concurrent.futures.ProcessPoolExecutor(max_workers=jobs) as ex:
        while len(done)<len(by):
            ready=[pid for pid in by if pid not in done and all((study/f'new_endpoints26/stage{s}/parts'/pid/'POOL_RECEIPT.json').exists() for s in range(1,stage+1))]
            if ready:
                todo={ex.submit(one_pool,study,out,pid,dict(pool_id=pid,**metas[pid]),by[pid],stage):pid for pid in ready}
                for fut in concurrent.futures.as_completed(todo):
                    r=fut.result();done.add(r['pool_id']);print('GEOMETRY_DONE',stage,len(done),len(by),r['pool_id'],round(r['elapsed_seconds'],2),flush=True)
                save_json(out/f'PROGRESS_STAGE{stage}.json',dict(through_stage=stage,completed_pools=len(done),candidate_pools=len(by),completed_ids=sorted(done)))
            if once:break
            if len(done)<len(by):time.sleep(15)
    if done==set(by):
        target=out/f'results_stage{stage}';target.mkdir(exist_ok=True)
        for suffix,name in [('precision','GEOMETRY_PATH_PRECISION'),('intervals','GEOMETRY_PAIRED_INTERVAL_PRECISION'),('dedup','GEOMETRY_DISTANCE_COMPUTE_ACCOUNTING')]:
            df=pd.concat([pd.read_csv(check/(pid+f'.{suffix}.csv.gz')) for pid in sorted(done)],ignore_index=True)
            df.to_csv(target/(name+'.csv.gz'),index=False)
        receipts=[json.loads((check/(pid+'.receipt.json')).read_text()) for pid in sorted(done)]
        save_json(target/'RUN_RECEIPT.json',dict(through_stage=stage,pools=len(done),new_fusions=0,uncomputed_links=0,
            exact_polygon_pairs=sum(r['unique_polygon_pairs'] for r in receipts),
            uncollapsed_team_pairs=sum(r['team_pairs_without_footprint_dedup'] for r in receipts),
            sum_worker_seconds=sum(r['elapsed_seconds'] for r in receipts),all_pool_receipts_present=True))
        print('GEOMETRY_ALL_COMPLETE',stage,len(done),flush=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',type=Path,required=True);ap.add_argument('--population',type=Path)
    ap.add_argument('--prior',type=Path);ap.add_argument('--prepare',action='store_true');ap.add_argument('--stage',type=int,choices=[1,2],default=2)
    ap.add_argument('--jobs',type=int,default=1);ap.add_argument('--once',action='store_true');ap.add_argument('--pool',action='append')
    a=ap.parse_args();root=a.study.resolve();out=root/'analysis_geometry26';out.mkdir(exist_ok=True)
    if a.prepare:
        if a.population is None or a.prior is None:ap.error('--prepare requires --population and --prior')
        prepare(root,a.population.resolve(),a.prior.resolve())
    else:run(root,out,a.stage,a.jobs,a.once,set(a.pool) if a.pool else None)


if __name__=='__main__':main()
