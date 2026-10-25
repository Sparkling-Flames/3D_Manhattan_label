"""Join registered new observations to exact reused/new deterministic endpoints.

Old endpoints remain a versioned dependency.  NEW_ENDPOINT_SCALARS contains
only endpoints absent from that old scalar source.  The new path-value file
contains every registered path prefix including cached, failed and deferred
ones; absent execution is an error, never an imputed failed/zero-Q result.
"""
from pathlib import Path
import argparse,gc,gzip,hashlib,io,json
import numpy as np
import pandas as pd


def save(frame,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    frame.to_csv(tmp,index=False,compression={'method':'gzip','mtime':0})
    tmp.replace(path)


def csv_eof(path,keys):
    import csv
    seen=set();n=0
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);cols=reader.fieldnames
        for row in reader:
            n+=1;key=tuple(row[k] for k in keys)
            if key in seen:raise ValueError('duplicate output key '+str(key))
            seen.add(key)
    return dict(rows=n,fields=len(cols),unique_key_fields=keys,complete_gzip_read=True)


def compact_geometry(base,expected,benchkeys):
    """Stream committed full states once; retain final geometry and state locator."""
    out=base/'new_endpoints';target=out/'NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz'
    tmp=target.with_name(target.name+'.tmp');seen=set();valid=0;shards=0
    index=pd.read_csv(out/'GEOMETRY_SHARD_INDEX.csv.gz')
    parts=[(out/r['folder']/r['geometry_file'],str(Path(r['folder'])/r['geometry_file']),None)
           for r in index.to_dict('records')]
    for path in sorted((base/'engine/benchmark/parts').glob('*/*.geometry_state.jsonl.gz')):
        pointer='../engine/benchmark/'+str(path.relative_to(base/'engine/benchmark'))
        parts.append((path,pointer,benchkeys))
    fields=('team_key','pool_id','k','score_status','score_available','complete_evaluable',
            'reference_id','reference_version','pool_input_sha256','minimum_support',
            'node_supports','geometry')
    with tmp.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=5,mtime=0) as zipped:
            with io.TextIOWrapper(zipped,encoding='utf-8',newline='') as stream:
                for path,pointer,keep in parts:
                    shards+=1
                    with gzip.open(path,'rt',encoding='utf-8') as f:
                        for lineno,line in enumerate(f,1):
                            row=json.loads(line);key=row['team_key']
                            if keep is not None and key not in keep:continue
                            if key in seen or key not in expected:raise ValueError('geometry key conflict '+key)
                            seen.add(key);x={k:row.get(k) for k in fields}
                            x['full_state_pointer']=pointer+'#L'+str(lineno)
                            stream.write(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
                            valid+=row.get('geometry') is not None
    if seen!=expected:raise ValueError('compact geometry missing registered new endpoints')
    tmp.replace(target)
    # Check the resulting deliverable, including the gzip footer.
    n=0;outkeys=set()
    with gzip.open(target,'rt',encoding='utf-8') as f:
        for line in f:
            row=json.loads(line);n+=1;outkeys.add(row['team_key'])
    assert n==len(expected) and outkeys==expected
    h=hashlib.sha256()
    with target.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return dict(rows=n,geometry_not_null=valid,input_shards_read_to_eof=shards,
        compact_file=target.name,compressed_bytes=target.stat().st_size,sha256=h.hexdigest(),
        all_jsonl_gzip_read_to_eof=True,full_states_retained_separately=True)


def run(base,repo=None):
    design=base/'design';out=base/'new_endpoints'
    repo=base/'repo' if repo is None else repo
    src=repo/'research/workers/personnel_population_curves_v2_20261023'
    deps=pd.read_csv(design/'ENDPOINT_DEPENDENCIES.csv.gz',keep_default_na=False,
                    usecols=['team_key','pool_id','n','pool_n','endpoint_source'])
    oldkeys=set(deps.loc[deps.endpoint_source.eq('inherited_population_20261023'),'team_key'])
    benchkeys=set(deps.loc[deps.endpoint_source.eq('reused_new_benchmark_20261025'),'team_key'])
    newkeys=set(deps.loc[deps.endpoint_source.eq('new_native_required_20261025'),'team_key'])
    columns=['team_key','pool_id','member_workers','member_object_ids','B8L2','D10','below_four','building',
        'complete_evaluable','condition','connection_available','difficulty','floor_redundant5_n','floor_turn5_n',
        'geometry_status','geometry_available','image','image_id','incomplete_nonpolicy','layer','nodes','order_status',
        'policy_deferred','pool_n','reference_id','reference_version','score_available','score_failure_nonpolicy',
        'source_time_known_n','source_time_total_seconds','target_time_known_n','target_time_total_seconds',
        'B8_floor_block','B8_direction_block','B8_height_block','B8_global_height_block','B8_local_height_block',
        'D10_direction_block','S_bottom_deg','dir','Hmean','Hcenter','IoU3D100','iou_2d','omission','extension',
        'height_mean_ratio','height_mean_h','height_sd_h','floor_short_edge_03_n','floor_short_edge_05_n',
        'floor_area_camera_h2','centroid_x_h','centroid_z_h','ref_node_recall_5','ref_edge_recall_5',
        'minimum_support','reference_nodes','reference_node_shortfall','endpoint_origin','score_status',
        'time_source_kinds','top_y_mean_px','bottom_y_mean_px','selected_support_min',
        'geometry_state_pointer','pool_input_sha256','repository_commit']
    old=[]
    for chunk in pd.read_csv(src/'results/ENDPOINT_SCALARS.csv.gz',usecols=lambda c:c in columns,chunksize=40000,low_memory=False):
        old.append(chunk[chunk.team_key.isin(oldkeys)])
    old=pd.concat(old,ignore_index=True);assert set(old.team_key)==oldkeys
    raw=pd.read_csv(out/'ENDPOINT_SCALARS.csv.gz',low_memory=False)
    assert set(raw.team_key)==newkeys
    bench=pd.read_csv(base/'engine/benchmark/ENDPOINT_SCALARS.csv.gz',low_memory=False)
    bench=bench[bench.team_key.isin(benchkeys)].copy();assert set(bench.team_key)==benchkeys
    fresh=pd.concat([raw,bench],ignore_index=True,sort=False)
    assert not fresh.team_key.duplicated().any()
    # Preserve benchmark's real relative state pointer after joining it.
    mask=fresh.team_key.isin(benchkeys)
    for col in ('geometry_shard','geometry_state_pointer'):
        fresh.loc[mask,col]='../engine/benchmark/'+fresh.loc[mask,col].astype(str)
    save(fresh,out/'NEW_ENDPOINT_SCALARS.csv.gz')
    fresh_count=len(fresh)
    account_cols=['team_key','k','layer','score_status','B8L2','D10','score_available',
        'geometry_available','floor_evaluable','complete_floor_evaluable','complete_evaluable',
        'floor_area_camera_h2','policy_deferred','score_failure_nonpolicy']
    counts=fresh.reindex(columns=account_cols).copy()
    counts['record_size_band']=np.select([counts.k.eq(1),counts.k.eq(2)],['k1_single_record','k2_policy_deferred'],default='k_ge_3_multirecord')
    counts['computation_source']=np.where(counts.team_key.isin(benchkeys),'benchmark_new_reused','main_native_run')
    counts['B8L2_available_n']=counts.B8L2.notna().astype(int)
    counts['D10_available_n']=counts.D10.notna().astype(int)
    for col in ['geometry_available','floor_evaluable','complete_floor_evaluable','complete_evaluable','policy_deferred','score_failure_nonpolicy']:
        counts[col+'_n']=(counts[col].eq(True)|counts[col].eq('True')|counts[col].eq(1)).astype(int)
    counts['valid_positive_area_n']=(pd.to_numeric(counts.floor_area_camera_h2,errors='coerce')>0).astype(int)
    status=counts.groupby(['computation_source','layer','record_size_band','score_status'],dropna=False).size().rename('records').reset_index()
    status.to_csv(out/'ENDPOINT_STATUS_COUNTS.csv',index=False)
    aggregation={c:(c,'sum') for c in counts if c.endswith('_n')}
    availability=counts.groupby(['computation_source','layer','record_size_band'],dropna=False).agg(records=('team_key','size'),**aggregation).reset_index()
    availability.to_csv(out/'ENDPOINT_AVAILABILITY_BY_SIZE.csv',index=False)
    progress=json.loads((out/'PROGRESS.json').read_text())
    native_run=json.loads((out/'RUN_RECEIPT.json').read_text())
    accounting=dict(main_native_records=len(raw),benchmark_new_records_used=len(bench),new_main_records=fresh_count,
        main_native_execution_wall_seconds=progress['seconds'],
        main_native_execution_plus_consolidation_wall_seconds=native_run['seconds'],
        main_sum_endpoint_evaluation_wall_seconds=float(raw.native_evaluation_wall_seconds.sum()),
        main_sum_fusion_seconds=float(raw.fusion_seconds.sum()),main_sum_score_seconds=float(raw.score_seconds.sum()),
        jobs=native_run['jobs'],raw_native_geometry_state_rows=native_run['geometry_rows'],
        note='k1 records and k2 deferred records are included in endpoint records; do not call every record a completed multiperson fusion. Summed worker measurements are not wall-clock elapsed time.')
    (out/'EXECUTION_ACCOUNTING.json').write_text(json.dumps(accounting,ensure_ascii=False,indent=2))
    del counts,status,availability
    allrows=pd.concat([old,fresh.reindex(columns=columns)],ignore_index=True,sort=False)
    del raw,bench,fresh
    gc.collect()
    assert set(allrows.team_key)==set(deps.team_key) and not allrows.team_key.duplicated().any()
    allrows=allrows.drop(columns='pool_id')
    links=pd.read_csv(design/'NEW_PREFIX_TEAM_LINKS.csv.gz',low_memory=False,dtype={'seed':str,'master_seed':str})
    values=links.merge(allrows,on='team_key',how='left',validate='many_to_one',indicator=True)
    assert values['_merge'].eq('both').all();values=values.drop(columns='_merge')
    values=values.merge(deps[['team_key','endpoint_source']],on='team_key',how='left',validate='many_to_one')
    save(values,out/'NEW_PREFIX_VALUES_COMPACT.csv.gz')
    exact=pd.read_csv(design/'EXACT_MARGINAL_TEAM_DESIGN.csv.gz',dtype={'finite_team_space':str})
    common=[c for c in allrows.columns if c not in exact.columns or c=='team_key']
    ev=exact.merge(allrows[common],on='team_key',how='left',validate='one_to_one',indicator=True)
    assert ev['_merge'].eq('both').all();ev=ev.drop(columns='_merge')
    save(ev,out/'EXACT_MARGINAL_VALUES.csv.gz')
    summary=values.groupby(['layer','difficulty','policy','batch']).agg(prefix_rows=('team_key','size'),
        paths=('path_id','nunique'),pools=('pool_id','nunique'),buildings=('building','nunique'),
        unique_teams=('team_key','nunique'),scorable=('B8L2','count'),
        nonpolicy_failures=('score_failure_nonpolicy','sum'),policy_deferred=('policy_deferred','sum')).reset_index()
    summary.to_csv(out/'NEW_OBSERVATION_COVERAGE.csv',index=False)
    validation={name:csv_eof(out/name,keys) for name,keys in [
        ('NEW_ENDPOINT_SCALARS.csv.gz',['team_key']),('NEW_PREFIX_VALUES_COMPACT.csv.gz',['path_id','k']),
        ('EXACT_MARGINAL_VALUES.csv.gz',['pool_id','k','team_key'])]}
    receipt=dict(registered_unique_endpoints=len(deps),old_endpoints_reused=len(oldkeys),
        benchmark_new_endpoints_reused=len(benchkeys),new_main_endpoints=len(newkeys),
        new_endpoints_total=fresh_count,prefix_rows=len(values),exact_marginal_rows=len(ev),
        missing_endpoint_links=0,validation=validation,
        interpretation='new path values include exact old-cache endpoints; old data are not duplicated in NEW_ENDPOINT_SCALARS',
        fullN_unique_endpoint_count=int(deps[deps.n.eq(deps.pool_n)].team_key.nunique()))
    (out/'COMPILE_VALUES_READY.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print('Complete value tables written and read to EOF; exporting compact geometry.',flush=True)
    del deps,old,allrows,links,values,exact,ev,summary
    gc.collect()
    receipt['compact_geometry']=compact_geometry(base,newkeys|benchkeys,benchkeys)
    (out/'COMPILE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True)
    p.add_argument('--repo',type=Path,help='Pinned repository root; defaults to BASE/repo')
    a=p.parse_args();run(a.base,a.repo)
