"""Rescore saved current discrimination endpoints and enumerate event coverage."""
import argparse,csv,gzip,json
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from .rebuild_v21_20261028 import ROOT,OUT,read
from .rescore_v21_same_room_20261028 import score,diagnostic_modules,unpack
from .scope_quality_scoring_20261016 import scoring_engine

TARGET=OUT/'discrimination_endpoint_rescore'
BASE=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked'
SOURCES=[('screen','02B/results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz','02B/results/screen/NATIVE_ENDPOINT_GEOMETRY.json.gz'),('confirm','04B/results/batch02/ENDPOINT_SCALARS.csv.gz','04C/results/batch02/ENDPOINT_GEOMETRY.json.gz'),('size','05/results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz','05/results/size_paths/NATIVE_ENDPOINT_GEOMETRY.json.gz'),('tail','05/results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz','05/results/large_team_ac_tail/NATIVE_ENDPOINT_GEOMETRY.json.gz')]
EVENTS=['02A/results/screen/EVENT_METRICS.csv.gz','04A1/results/confirm/EVENT_METRICS.csv.gz','04A2/results/reverse_screen/EVENT_METRICS.csv.gz','04A2/results/reverse_confirm/EVENT_METRICS.csv.gz','05/results/size_paths/EVENT_METRICS.csv.gz','05/results/large_team_ac_tail/EVENT_METRICS.csv.gz']
METRICS=['B8L2','D10','WQ','A10','iou_2d','IoU3D100','S_bottom_deg','dir','Hmean','Hcenter','omission','extension','nodes','ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9','diag_corner_recall_05','diag_wall_coverage_03','diag_wall_coverage_05']

def rows(path):
    with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)

def inventory():
    TARGET.mkdir(parents=True,exist_ok=True)
    ids={r['pool_id'] for r in read(OUT/'pools/DEPENDENCIES.json') if r['action']=='reuse_geometry_rescore'}
    pools={r['pool_id']:r for r in read(OUT/'pools/INPUT_SNAPSHOT.json')['images']};assert ids<=set(pools)
    items={};source_stats={};conflicts=[]
    for label,scalar_path,geom_path in SOURCES:
        scalars={}
        for r in rows(BASE/scalar_path):
            if r['pool_id'] in ids:
                assert r['team_key'] not in scalars;scalars[r['team_key']]=r
        with gzip.open(BASE/geom_path,'rt',encoding='utf8') as f:geoms=[r for r in json.load(f) if r['pool_id'] in ids]
        keys=[g['team_key'] for g in geoms];assert len(keys)==len(set(keys))
        missing_geom=sorted(scalars.keys()-set(keys));missing_scalar=sorted(set(keys)-scalars.keys())
        source_stats[label]=dict(scalar_file=scalar_path,geometry_file=geom_path,scalar_rows=len(scalars),geometry_rows=len(geoms),missing_geometry=missing_geom,missing_scalar=missing_scalar)
        for g in geoms:
            key=g['team_key']
            if key not in scalars:continue
            a=scalars[key];workers=unpack(a['member_workers']);objects=unpack(a['member_object_ids']);k=int(a['k']);assert len(set(workers))==len(set(objects))==k and a['pool_id']==g['pool_id']
            item=dict(team_key=key,pool_id=a['pool_id'],k=k,member_workers=workers,member_set_key='|'.join(sorted(workers)),member_object_ids=a['member_object_ids'],reference_id=pools[a['pool_id']]['meta']['reference_id'],original_reference_id=a['reference_id'],original_reference_version=a['reference_version'],original_score_status=a['score_status'],original_complete_evaluable=a['complete_evaluable']=='True',original_metrics={c:a.get(c) for c in METRICS},geometry=g.get('geometry'),source_scalar=[scalar_path],source_geometry=[geom_path],study='current_discrimination')
            if key not in items:items[key]=item
            else:
                old=items[key];fields=['pool_id','k','member_set_key','original_reference_id','original_score_status','original_complete_evaluable','geometry']
                if any(old[c]!=item[c] for c in fields) or set(unpack(old['member_object_ids']))!=set(objects):conflicts.append(key)
                else:old['source_scalar'].append(scalar_path);old['source_geometry'].append(geom_path)
        print('read source',label,len(scalars),flush=True)
    conflicts=set(conflicts)
    # Event references include cached teams, not just native endpoints in the four geometry files.
    event_teams={};event_counts={};event_source_counts=Counter()
    for event_path in EVENTS:
        path=BASE/event_path;header=pd.read_csv(path,nrows=0).columns.tolist()
        columns=['pool_id','event_id']+[f'{a}_{v}' for a in 'ABC' for v in ['team_key','members','B8L2','D10','failed','incomplete'] if f'{a}_{v}' in header]
        columns += [x for x in header if x.startswith(('n10_','strict_tail_')) and x.endswith('_team_key')]
        total=0
        for df in pd.read_csv(path,usecols=columns,dtype=str,chunksize=20000,keep_default_na=False):
            for r in df[df.pool_id.isin(ids)].to_dict('records'):
                total+=1
                for a in 'ABC':
                    key=r.get(a+'_team_key','')
                    if not key:continue
                    members=unpack(r.get(a+'_members',''));d=event_teams.setdefault(key,dict(team_key=key,pool_id=r['pool_id'],member_workers=members,old_scoreable=False,old_failure_flags=[],event_sources=[]))
                    assert d['pool_id']==r['pool_id'] and (not d['member_workers'] or set(d['member_workers'])==set(members)),(event_path,key)
                    if not d['member_workers']:d['member_workers']=members
                    d['old_scoreable'] |= bool(r.get(a+'_B8L2',''));d['old_failure_flags'].append(r.get(a+'_failed',''));d['event_sources'].append(event_path)
                for col in columns:
                    if col.startswith(('n10_','strict_tail_')) and col.endswith('_team_key') and r.get(col):
                        key=r[col];event_teams.setdefault(key,dict(team_key=key,pool_id=r['pool_id'],member_workers=[],old_scoreable=False,old_failure_flags=[],event_sources=[]));event_teams[key]['event_sources'].append(event_path)
        event_counts[event_path]=total;print('read events',event_path,total,flush=True)
    for k,event in event_teams.items():
        event['event_sources']=sorted(set(event['event_sources']));event['old_failure_flags']=sorted(set(event['old_failure_flags']))
        if k in items and event['member_workers']:assert set(event['member_workers'])==set(items[k]['member_workers'])
    available=[r for k,r in items.items() if k not in conflicts and r['geometry'] is not None]
    scoredkeys={r['team_key'] for r in available}
    missing=[]
    for key,r in event_teams.items():
        if key in scoredkeys:continue
        old=items.get(key)
        if old:
            r.update(member_workers=old['member_workers'],member_object_ids=old['member_object_ids'],original_score_status=old['original_score_status']);r['old_scoreable'] |= bool(old['original_metrics'].get('B8L2'))
        elif r['member_workers']:
            byworker={x['worker_id']:x['object_id'] for x in pools[r['pool_id']]['records']}
            assert set(r['member_workers'])<=set(byworker);r['member_object_ids']=[byworker[x] for x in r['member_workers']]
        r['reason']='conflicting_geometry' if key in conflicts else 'geometry_not_found_in_four_sources';missing.append(r)
    for name,data in [('INPUT_TEAMS.jsonl.gz',available),('MISSING_EVENT_TEAMS.jsonl.gz',missing)]:
        with gzip.open(TARGET/name,'wt',encoding='utf8') as f:
            for row in sorted(data,key=lambda x:x['team_key']):f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    status_by_source=defaultdict(Counter)
    for row in available:
        for source in row['source_scalar']:status_by_source[source][row['original_score_status']]+=1
    checks=dict(source_pools_with_geometry=len({r['pool_id'] for r in available}),original_status_by_scalar_source={k:dict(v) for k,v in status_by_source.items()},affected_pools=len(ids),sources=source_stats,unique_source_teams=len(items),geometry_conflicts=sorted(conflicts),geometry_teams_available=len(available),event_counts=event_counts,event_unique_teams=len(event_teams),missing_event_teams=len(missing),missing_event_scoreable=sum(r['old_scoreable'] for r in missing),missing_event_identity_unknown=sum(not r['member_workers'] for r in missing),no_fusion=True)
    (TARGET/'COVERAGE.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(checks,ensure_ascii=False),flush=True)

def shard(payload):
    number,items=payload;path=TARGET/'shards'/f'{number:05d}.jsonl.gz'
    if path.exists():raise FileExistsError(path)
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')};fr,gd=diagnostic_modules()
    with scoring_engine() as (engine,models):values=[score(r,refs[r['reference_id']],engine,models,fr,gd) for r in items]
    temp=path.with_suffix('.writing')
    with gzip.open(temp,'wt',encoding='utf8') as f:
        for r in values:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    temp.replace(path);return len(values)

def matched_boundaries(points,reference):
    fields=['matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg','matched_ref_pair_fraction']
    result={k:None for k in fields}
    if points is None or len(points)<6:return result
    p=np.asarray(points,float);r=np.asarray(reference,float)
    az=((p[::2,0,None]-r[None,::2,0]+512)%1024-512)*360/1024
    i,j=linear_sum_assignment(np.abs(az));ok=np.abs(az[i,j])<=9;i,j=i[ok],j[ok]
    result['matched_ref_pair_fraction']=len(i)/(len(r)//2)
    if len(i):
        result.update(matched_ref_top_abs_deg=float(np.abs(p[2*i,1]-r[2*j,1]).mean()*180/512),matched_ref_bottom_abs_deg=float(np.abs(p[2*i+1,1]-r[2*j+1,1]).mean()*180/512),matched_ref_horizontal_abs_deg=float(np.abs(az[i,j]).mean()))
    return result

def add_boundary_diagnostics():
    refs={r['target_id']:r for r in read(OUT/'reference_catalog.json')}
    with gzip.open(TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:items={r['team_key']:r for r in map(json.loads,f)}
    count=0;unavailable=0
    for path in sorted((TARGET/'shards').glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:rows=[json.loads(x) for x in f]
        for row in rows:
            src=items[row['team_key']];assert src['reference_id']==row['reference_id']
            points=(src['geometry'] or {}).get('points');v=matched_boundaries(points,refs[row['reference_id']]['points_1024x512'])
            row['reference_dependent_diagnostics'].update(v);count+=int(points is not None);unavailable+=int(points is None)
        temp=path.with_suffix('.boundary')
        with gzip.open(temp,'wt',encoding='utf8') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
        temp.replace(path)
    checks=read(TARGET/'CHECKS.json');assert count+unavailable==checks['teams']
    checks['matched_boundary_diagnostics']={'computed':count,'not_applicable_no_points':unavailable,'threshold_degrees':9};(TARGET/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('matched boundary diagnostics',count,'no points',unavailable,flush=True)

def run(jobs):
    (TARGET/'shards').mkdir(parents=True,exist_ok=True)
    with gzip.open(TARGET/'INPUT_TEAMS.jsonl.gz','rt',encoding='utf8') as f:items=[json.loads(x) for x in f]
    blocks=[(i//200,items[i:i+200]) for i in range(0,len(items),200)];total=0
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures=[executor.submit(shard,b) for b in blocks]
        for i,f in enumerate(as_completed(futures),1):
            total+=f.result()
            if i%20==0:print('discrimination shards',i,'/',len(blocks),flush=True)
    states=Counter();diagnostics=Counter()
    for n,_ in blocks:
        with gzip.open(TARGET/'shards'/f'{n:05d}.jsonl.gz','rt',encoding='utf8') as f:
            for line in f:
                r=json.loads(line);states[r['rescore_state']]+=1;diagnostics[r['reference_dependent_diagnostics_status']]+=1
    assert total==len(items)
    (TARGET/'CHECKS.json').write_text(json.dumps(dict(teams=total,shards=len(blocks),states=states,diagnostics=diagnostics,new_fusion=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8');print('done',total,dict(states),dict(diagnostics),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--part',choices=['inventory','score','boundary_diagnostics'],required=True);ap.add_argument('--jobs',type=int,default=4);a=ap.parse_args()
    if a.part=='inventory':inventory()
    elif a.part=='score':run(a.jobs)
    else:add_boundary_diagnostics()
