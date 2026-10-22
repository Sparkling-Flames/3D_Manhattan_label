#!/usr/bin/env python3
"""Evaluate every registered finite-population ABC with the frozen event kernel.

Reads completed native batches only. Every image/direction is committed
separately. Exports full event metrics without triplicating endpoint scalars;
the exact endpoint keys and separate geometry/scalar batches are sufficient
to reconstruct every comparison. No native fusion or scoring is called.
"""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import argparse,json,sys,time,collections
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import pandas as pd,numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));from run_native import gs,write_csv,prior,REPO
sys.path.insert(0,str(HERE.parent/'joint_exchange'))
from evaluate_joint import complete_event,expression,EXTRA,COMPONENTS,OLD,typed

def ready_sources():
    sources=collections.defaultdict(list)
    for c in sorted((HERE/'batches').glob('*/COMPLETION.json')):
        d=pd.read_csv(c.parent/'REQUESTS.csv.gz',usecols=['pool_id','team_key'])
        for pid,g in d.groupby('pool_id'):
            sources[pid].append(dict(path=str(HERE/'runtime'/c.parent.name/(pid+'.json.gz')),keys=set(g.team_key),
                scalar=str(c.parent/'ENDPOINT_SCALARS.csv.gz'),geometry=str(c.parent/'ENDPOINT_GEOMETRY.csv.gz')))
    return sources

def read_endpoint_source(source,keys,prefer_exported=False):
    """Restore events from delivered endpoint files without any fusion call.

    The optional runtime is a scratch acceleration cache. It is intentionally
    not required by the deliverable. The same frozen scalar parser is already
    used by the joint-condition experiment.
    """
    if not prefer_exported and Path(source['path']).exists():
        return {r['team_key']:r for r in gs.read(source['path'])['teams'] if r['team_key'] in keys}
    teams={}
    for chunk in pd.read_csv(source['scalar'],dtype=str,keep_default_na=False,chunksize=20000):
        for row in chunk[chunk.team_key.isin(keys)].to_dict('records'):
            teams[row['team_key']]=typed(row)
    for chunk in pd.read_csv(source['geometry'],dtype=str,keep_default_na=False,chunksize=20000):
        for row in chunk[chunk.team_key.isin(teams)].to_dict('records'):
            teams[row['team_key']]['geometry']=json.loads(row['geometry_json']) if row['geometry_json'] else None
    assert all('geometry' in t for t in teams.values())
    return teams

def worker(payload):
    part,sources=payload;cell=part['cell_id'];out=HERE/'results'/cell
    dest=out/'EVENTS_COMPLETE.csv.gz';req=pd.read_csv(REPO/part['path'],dtype=str,keep_default_na=False)
    assert prior.sha(REPO/part['path'])==part['sha256']
    keys=set(req.team_A)|set(req.team_B)|set(req.team_C);teams={};t0=time.monotonic()
    for p in sources:teams.update(read_endpoint_source(p,keys))
    assert keys<=teams.keys(),('missing_team',cell)
    for t in teams.values():t.update(dict(zip(EXTRA,expression(t.get('geometry')))))
    _,_,sg,corner=gs.setup_engine()
    histories=pd.read_csv(OLD/'multivariate/continuous_features_lobo.csv.gz')
    hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    pairs={};signatures={};rows=[]
    for r in req.to_dict('records'):rows.append(complete_event(r,teams,pairs,signatures,hist,sg,corner,'manual'))
    d=pd.DataFrame(rows);assert len(d)==len(req) and set(d.event_id)==set(req.event_id)
    receipt=write_csv(dest,d)
    # Panel means are compact re-aggregation inputs; inferential replication
    # remains at image/building level, not the many dependent member choices.
    metrics=[c for c in d if c.startswith(('same_','cross_','net_','common_quality_','common_geometry_',
        'common_expression_','within_','abs_Q_change_advantage','stable_','time_abs_variation_advantage'))
        and pd.api.types.is_numeric_dtype(d[c]) and not c.endswith(('_counts','_workers'))]
    metrics+=['A_failure','B_failure','C_failure','A_B8L2','B_B8L2','C_B8L2','A_D10','B_D10','C_D10']
    metrics=list(dict.fromkeys(c for c in metrics if c in d))
    summaries=[]
    context=['cell_id','pool_id','image','building','condition','difficulty','layer','method_id','tier','n','m_AB',
        'source_class','target_class','source_role','target_role','selected_family','training_turn_difference',
        'training_turn_direction','background_index','member_design','overlap_priority_seed_image']
    for panel,g in d.groupby('panel_id',sort=True):
        row={k:g.iloc[0][k] for k in context};row.update(panel_id=panel,events=len(g),physical_triples=g.physical_triple_id.nunique(),
            unique_endpoints=len(set(g.team_A)|set(g.team_B)|set(g.team_C)),all_complete=int(g.all_complete.sum()),
            all_scored=int(g.all_scored.sum()),recorded_time_common=int(g.recorded_time_single_source.sum()))
        for m in metrics:
            v=pd.to_numeric(g[m],errors='coerce').dropna();row[m]=float(v.mean()) if len(v) else None;row[m+'__valid']=len(v)
            if m in ['same_B8L2','cross_B8L2','net_B8L2','abs_Q_change_advantage','net_recorded_time_pct']:
                row[m+'__median']=float(v.median()) if len(v) else None
                row[m+'__positive']=float((v>0).mean()) if len(v) else None
                row[m+'__negative']=float((v<0).mean()) if len(v) else None
        summaries.append(row)
    sr=write_csv(out/'PANEL_SUMMARY.csv.gz',summaries)
    result=dict(status='complete',cell_id=cell,registered_events=len(req),exported_events=len(d),missing_events=0,
        unique_endpoints=len(keys),physical_triples=d.physical_triple_id.nunique(),pair_geometries=len(pairs),
        all_failures_retained=True,seconds=time.monotonic()-t0,native_fusion_calls=0,scoring_calls=0,
        event_result=receipt,panel_summary=sr,request_sha256=part['sha256'])
    gs.save(out/'COMPLETION.json',result)
    return {k:v for k,v in result.items() if k not in ['event_result','panel_summary']}

def run(jobs,watch):
    idx=pd.read_csv(HERE/'REGISTERED_EVENT_PARTS.csv',keep_default_na=False).to_dict('records')
    while True:
        done={p.parent.name for p in (HERE/'results').glob('*/COMPLETION.json')}
        remaining=[p for p in idx if p['cell_id'] not in done]
        if not remaining:break
        sources=ready_sources();ready=[]
        for p in remaining:
            req=pd.read_csv(REPO/p['path'],usecols=['team_A','team_B','team_C'])
            keys=set(req.team_A)|set(req.team_B)|set(req.team_C)
            ss=sources.get(p['pool_id'],[]);have=set().union(*(q['keys'] for q in ss)) if ss else set()
            if keys<=have:ready.append((p,ss))
        gs.save(HERE/'EVALUATION_PROGRESS.json',dict(completed_cells=len(done),pending_cells=len(remaining),ready_cells=len(ready),
            registered_cells=len(idx),fusion_calls=0))
        if ready:
            with ProcessPoolExecutor(max_workers=jobs) as ex:
                for f in as_completed([ex.submit(worker,p) for p in ready]):print(json.dumps(f.result()),flush=True)
        elif watch:time.sleep(15)
        else:break
        if not watch:break
    done=[];summaries=[]
    for p in sorted((HERE/'results').glob('*/COMPLETION.json')):
        r=gs.read(p);done.append({k:v for k,v in r.items() if k not in ['event_result','panel_summary']})
        summaries.append(pd.read_csv(p.parent/'PANEL_SUMMARY.csv.gz'))
    if done:write_csv(HERE/'EVALUATED_EVENT_PARTS.csv',done)
    if summaries:write_csv(HERE/'PANEL_EFFECTS_COMPLETE.csv.gz',pd.concat(summaries,ignore_index=True))
    gs.save(HERE/'EVALUATION_RECEIPT.json',dict(registered_cells=len(idx),complete_cells=len(done),
        registered_events=sum(int(p['events']) for p in idx),complete_events=sum(int(p['exported_events']) for p in done),
        fully_complete=len(done)==len(idx),underlying_data_version='v2',native_fusion_calls=0,scoring_calls=0))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jobs',type=int,default=2);p.add_argument('--watch',action='store_true');a=p.parse_args();run(a.jobs,a.watch)
