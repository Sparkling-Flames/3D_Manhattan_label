"""Read-only evaluation and incremental pool checkpoints for registered ABCs."""
from __future__ import annotations
from joint_design import *
import argparse,csv,sys,time
OLD=ROOT/'research/workers/personnel_global_composition_20261021'
sys.path[:0]=[str(OLD/'continuation_20261021/n20_abc'),str(OLD/'composition')]
from event_kernel import evaluate_one
from evaluate_n20_abc import typed,COMPONENTS
import global_study as gs

EXTRA=['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']

def expression(geometry):
    if not geometry:return [None]*3
    p=np.asarray(geometry.get('footprint') or [],float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():return [None]*3
    edges=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(edges,axis=1);prev=np.roll(edges,1,axis=0);den=np.linalg.norm(prev,axis=1)*length
    if (den<=1e-12).any():return [None]*3
    turn=np.degrees(np.arccos(np.clip((prev*edges).sum(axis=1)/den,-1,1)));redundant=int(np.sum(turn<=5));short=int(np.sum((length/length.sum()<.04)&(turn>=15)&(np.roll(turn,-1)>=15)))
    return [len(p)-redundant,short,redundant]

def sources():
    pairs=[]
    # Portable delivery: prefer the complete unique endpoint subset delivered
    # with this topic. The frozen parser/geometry and mathematics are unchanged.
    compact_scalar=HERE/'ALL_USED_ENDPOINT_SCALARS.csv.gz'
    compact_geometry=HERE/'ALL_USED_ENDPOINT_GEOMETRY.csv.gz'
    if compact_scalar.exists() and compact_geometry.exists():
        pairs.append((compact_scalar,compact_geometry))
    for p in sorted((COMP/'delivery').glob('*_ENDPOINT_SCALARS.csv.gz')):
        geo=p.with_name(p.name.replace('SCALARS','GEOMETRY'))
        if geo.exists():pairs.append((p,geo))
    native=HERE.parent/'expanded_blocks/batches'
    for p in sorted(native.glob('*/ENDPOINT_SCALARS.csv.gz')):
        if (p.parent/'COMPLETION.json').exists():pairs.append((p,p.with_name('ENDPOINT_GEOMETRY.csv.gz')))
    return pairs

def load_teams(keys,condition):
    teams={};refs=[]
    for scalar,geo in sources():
        if ('MANUAL' in scalar.name and condition!='manual') or ('SEMI' in scalar.name and condition!='semi'):continue
        added=set()
        for chunk in pd.read_csv(scalar,dtype=str,keep_default_na=False,chunksize=20000):
            for row in chunk[chunk.team_key.isin(keys)].to_dict('records'):
                key=row['team_key'];item=typed(row)
                if key in teams:
                    assert [teams[key].get(k) for k in ['B8L2','D10','nodes']]==[item.get(k) for k in ['B8L2','D10','nodes']]
                    continue
                teams[key]=item;added.add(key)
        if not added:continue
        for chunk in pd.read_csv(geo,dtype=str,keep_default_na=False,chunksize=20000):
            for r in chunk[chunk.team_key.isin(added)].to_dict('records'):
                teams[r['team_key']]['geometry']=json.loads(r['geometry_json']) if r['geometry_json'] else None
        refs.append(dict(scalar_file=str(scalar.relative_to(ROOT)),geometry_file=str(geo.relative_to(ROOT)),loaded_teams=len(added),scalar_sha256=sha(scalar),geometry_sha256=sha(geo)))
        if keys<=teams.keys():break
    for k,t in teams.items():
        assert 'geometry' in t,(k,'geometry_missing')
        t.update(dict(zip(EXTRA,expression(t['geometry']))))
    return teams,refs

def finite(v):return isinstance(v,(int,float,np.number)) and np.isfinite(v)
def complete_event(req,teams,pairs,signatures,hist,sg,corner,condition):
    e=evaluate_one(req,teams,pairs,signatures,hist,sg,corner,condition)
    # Endpoint scalars are delivered once by exact key, not repeated per event.
    e={k:v for k,v in e.items() if not k.startswith('endpoint_')}
    ts={a:teams[e['team_'+a]] for a in 'ABC'}
    kinds=[t.get('time_source_kinds') for t in ts.values()]
    e['recorded_time_single_source']=len(set(kinds))==1 and all(k and '|' not in k for k in kinds) and all(t.get('source_time_known_n')==e['n'] and finite(t.get('source_time_total_seconds')) and t['source_time_total_seconds']>0 for t in ts.values())
    for a,t in ts.items():
        for f in EXTRA:e[a+'_'+f]=t[f]
        e[a+'_time_source_kinds']=t.get('time_source_kinds');e[a+'_source_time_known_n']=t.get('source_time_known_n');e[a+'_new_n']=t.get('new_n')
    for prefix,a,b in [('same','A','B'),('cross','A','C'),('net','B','C')]:
        v=e.get(prefix+'_source_log_time_ratio');e[prefix+'_recorded_time_logratio']=v if e['recorded_time_single_source'] else None
        e[prefix+'_recorded_time_pct']=100*math.expm1(v) if e['recorded_time_single_source'] and finite(v) else None
        dq=e[prefix+'_B8L2'];dt=e[prefix+'_recorded_time_logratio']
        e[prefix+'_Q_up']=int(dq>0) if finite(dq) else None
        e[prefix+'_time_down']=int(dt<0) if finite(dt) else None
        e[prefix+'_QT_both_improve']=int(dq>0 and dt<0) if finite(dq) and finite(dt) else None
        e[prefix+'_failure_delta']=int(e[b+'_failure'])-int(e[a+'_failure'])
        for f in EXTRA:
            x,y=ts[a][f],ts[b][f];e[prefix+'_'+f]=y-x if finite(x) and finite(y) else None
    for f in ['floor_jaccard_difference','mean_height_prism_pair_difference','structure_bound_cyclic_deg','centroid_distance_h','floor_area_abs_log_ratio','node_count_difference']:
        a,b=e.get('within_'+f),e.get('cross_'+f);ok=e['all_complete'] and finite(a) and finite(b)
        e['common_geometry_within_'+f]=a if ok else None;e['common_geometry_cross_'+f]=b if ok else None;e['common_geometry_advantage_'+f]=b-a if ok else None
    for f in EXTRA:
        a,b=e.get('same_'+f),e.get('cross_'+f);ok=e['all_complete'] and finite(a) and finite(b)
        e['common_expression_within_abs_'+f]=abs(a) if ok else None;e['common_expression_cross_abs_'+f]=abs(b) if ok else None;e['common_expression_advantage_'+f]=abs(b)-abs(a) if ok else None
    e['time_abs_variation_advantage']=abs(e['cross_recorded_time_logratio'])-abs(e['same_recorded_time_logratio']) if e['recorded_time_single_source'] else None
    return e

def run(kind,condition):
    source=HERE/(f'CROSS_{condition.upper()}_EVENTS_REGISTERED.csv.gz' if kind=='cross' else ('NATIVE_EVENTS_REGISTERED.csv.gz' if kind=='native' else 'CACHED_EVENTS_REGISTERED.csv.gz'));requests=pd.read_csv(source,dtype=str,keep_default_na=False);requests=requests[requests.condition.eq(condition)]
    keys=set(requests.team_A)|set(requests.team_B)|set(requests.team_C);teams,refs=load_teams(keys,condition);missing=keys-set(teams)
    dest=HERE/'results'/kind/condition;dest.mkdir(parents=True,exist_ok=True);write(dest/'ENDPOINT_SOURCES.csv',pd.DataFrame(refs))
    print(json.dumps(dict(kind=kind,condition=condition,registered_events=len(requests),endpoints=len(keys),available=len(teams),missing=len(missing))),flush=True)
    _,_,sg,corner=gs.setup_engine();histories=pd.read_csv(OLD/'multivariate/continuous_features_lobo.csv.gz');hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    ledger=[];pending=[];allframes=[]
    for pool,req in requests.groupby('pool_id',sort=True):
        need=set(req.team_A)|set(req.team_B)|set(req.team_C);fname=h('result',kind,condition,pool)[:20]+'.csv.gz';path=dest/'pools'/fname
        if not need<=teams.keys():pending.append(dict(pool_id=pool,events=len(req),missing_teams=len(need-teams.keys())));continue
        if path.exists():
            df=pd.read_csv(path);assert set(df.event_id)==set(req.event_id)
        else:
            pairs={};signatures={};rows=[]
            for r in req.to_dict('records'):rows.append(complete_event(r,teams,pairs,signatures,hist,sg,corner,condition))
            df=pd.DataFrame(rows);assert not df.event_id.duplicated().any();write(path,df)
            save(path.with_suffix('.json'),dict(pool_id=pool,events=len(df),unique_endpoints=len(need),pair_metrics=len(pairs),request_event_ids_sha256=digest(sorted(req.event_id)),result_sha256=sha(path),native_fusion_calls=0))
        ledger.append(dict(pool_id=pool,file=str(path.relative_to(HERE)),events=len(df),sha256=sha(path)));allframes.append(df)
        print(kind,condition,pool,'events',len(df),'complete',int(df.all_complete.sum()),flush=True)
    write(dest/'POOL_RESULTS.csv',pd.DataFrame(ledger));write(dest/'PENDING.csv',pd.DataFrame(pending))
    if allframes:
        E=pd.concat(allframes,ignore_index=True);write(HERE/f'{kind.upper()}_{condition.upper()}_EVENTS_COMPLETE.csv.gz',E)
        used=set(E.team_A)|set(E.team_B)|set(E.team_C)
        scalar=[];geom=[]
        for key in sorted(used):
            r=teams[key];s={k:('|'.join(map(str,v)) if isinstance(v,list) else v) for k,v in r.items() if k!='geometry'};scalar.append(s);geom.append(dict(team_key=key,pool_id=r['pool_id'],member_workers='|'.join(r['member_workers']),geometry_json=json.dumps(r['geometry'],separators=(',',':')) if r['geometry'] else ''))
        write(dest/'ENDPOINT_SCALARS.csv.gz',pd.DataFrame(scalar));write(dest/'ENDPOINT_GEOMETRY.csv.gz',pd.DataFrame(geom))
    receipt=dict(kind=kind,condition=condition,registered_events=len(requests),completed_events=sum(x['events'] for x in ledger),pending_events=sum(x['events'] for x in pending),unique_required_teams=len(keys),available_teams=len(teams),native_fusion_calls=0,source_sha256=sha(source),complete=not pending)
    save(dest/'COMPLETION.json',receipt);print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('kind',choices=['native','cached','cross']);ap.add_argument('condition',choices=['manual','semi']);args=ap.parse_args();run(args.kind,args.condition)
