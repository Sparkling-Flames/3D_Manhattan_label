#!/usr/bin/env python3
"""Evaluate registered structure ABCs from central frozen endpoints only.

No calls to fuse or scoring_engine are made. The existing complete_event kernel
is reused, including frozen pair geometry and the comparable-time contract.
Each fully available pool is saved immediately; --allow-partial resumes safely.
"""
from __future__ import annotations
import argparse, json, math, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
from register_structure import HERE, ROOT, PRIOR, gs, h, sha, write, save
sys.path.insert(0,str(PRIOR/'joint_exchange'))
from evaluate_joint import complete_event, expression, EXTRA, typed

HIST=ROOT/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz'
NATIVE=HERE.parent/'native'
HISTORY_FIELDS=['turn_history','short_history','redundancy_history','area_history','height_history',
                'simple_turn_history','complex_turn_history','complex_short_history']

def source_pairs():
    # A completion marker is required for new batches, so a running writer is
    # never mistaken for a complete cache. Central reused subsets are atomic.
    out=[]
    paths=list((NATIVE/'batches').glob('structure_*/ENDPOINT_SCALARS.csv.gz'))+list((NATIVE/'batches').glob('mpath_*/ENDPOINT_SCALARS.csv.gz'))
    for p in sorted(paths):
        g=p.with_name('ENDPOINT_GEOMETRY.csv.gz')
        if g.exists() and (p.parent/'COMPLETION.json').exists():out.append((p,g))
    for p in sorted(NATIVE.glob('*REUSED*SCALARS.csv.gz')):
        g=p.with_name(p.name.replace('SCALARS','GEOMETRY'))
        if g.exists():out.append((p,g))
    # The full unique subset from this new experiment may be exported centrally.
    for p in sorted(NATIVE.glob('STRUCTURE*SCALARS.csv.gz')):
        g=p.with_name(p.name.replace('SCALARS','GEOMETRY'))
        if g.exists():out.append((p,g))
    return out

def load_teams(keys):
    teams={};refs=[];provenance=[]
    for scalar,geo in source_pairs():
        added=set()
        for chunk in pd.read_csv(scalar,dtype=str,keep_default_na=False,chunksize=20000):
            for r in chunk[chunk.team_key.isin(keys)].to_dict('records'):
                key=r['team_key'];item=typed(r)
                if key in teams:
                    assert [teams[key].get(k) for k in ['B8L2','D10','nodes']]==[item.get(k) for k in ['B8L2','D10','nodes']]
                    continue
                teams[key]=item;added.add(key)
                provenance.append(dict(team_key=key,scalar_file=str(scalar.relative_to(ROOT)),geometry_file=str(geo.relative_to(ROOT))))
        if not added:continue
        for chunk in pd.read_csv(geo,dtype=str,keep_default_na=False,chunksize=20000):
            for r in chunk[chunk.team_key.isin(added)].to_dict('records'):
                teams[r['team_key']]['geometry']=json.loads(r['geometry_json']) if r['geometry_json'] else None
        refs.append(dict(scalar_file=str(scalar.relative_to(ROOT)),geometry_file=str(geo.relative_to(ROOT)),loaded=len(added),
                         scalar_sha256=sha(scalar),geometry_sha256=sha(geo)))
        if keys<=teams.keys():break
    for key,t in teams.items():
        assert 'geometry' in t,(key,'geometry_missing')
        t.update(dict(zip(EXTRA,expression(t['geometry']))))
    return teams,refs,provenance

def finite(v):return isinstance(v,(int,float,np.number)) and np.isfinite(v)

def add_structure_histories(e,req,features):
    for block,key in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z'),('D','common_background')]:
        ws=req[key].split('|') if req[key] else []
        for f in HISTORY_FIELDS:
            values=[features.get((req['building'],w),{}).get(f,np.nan) for w in ws]
            values=pd.to_numeric(pd.Series(values,dtype='object'),errors='coerce')
            e[f'{block}_history_{f}']=float(values.mean()) if len(values) and values.notna().all() else None
            e[f'{block}_{f}_known_n']=int(values.notna().sum())
    for prefix,a,b in [('same','X','Y'),('cross','X','Z'),('net','Y','Z')]:
        for f in HISTORY_FIELDS:
            x,y=e[f'{a}_history_{f}'],e[f'{b}_history_{f}']
            e[f'{prefix}_history_{f}_difference']=y-x if finite(x) and finite(y) else None
    # Background seats are direct design variables, independent of target score.
    s,t,o=map(int,req['background_stratum'].split('|'))
    e['background_source_seats']=s;e['background_target_seats']=t;e['background_other_seats']=o
    e['replacement_fraction']=e['m']/e['n']
    e['background_target_fraction']=t/(e['n']-e['m']) if e['n']>e['m'] else None
    e['background_target_band']=('low_0_to_1_3' if e['background_target_fraction']<1/3 else
                                 'middle_1_3_to_2_3' if e['background_target_fraction']<2/3 else 'high_2_3_to_1')
    for prefix,arm in [('same','B'),('cross','C'),('net','C')]:
        q=e.get(prefix+'_B8L2')
        e[prefix+'_loss_gt10_or_destination_failure']=int(e[arm+'_failure'] or q < -10) if e[arm+'_failure'] or finite(q) else None
    return e

def run(allow_partial=False):
    start=time.monotonic()
    request_path=HERE/('ALL_EVENTS_REGISTERED.csv.gz' if (HERE/'ALL_EVENTS_REGISTERED.csv.gz').exists() else 'EVENTS_REGISTERED.csv.gz')
    requests=pd.read_csv(request_path,dtype=str,keep_default_na=False)
    keys=set(requests.team_A)|set(requests.team_B)|set(requests.team_C)
    teams,refs,provenance=load_teams(keys)
    write(HERE/'results/ENDPOINT_SOURCES.csv',refs);write(HERE/'results/USED_ENDPOINT_INDEX.csv.gz',provenance)
    missing=keys-set(teams)
    if missing and not allow_partial:
        save(HERE/'results/PENDING.json',dict(required=len(keys),available=len(teams),missing=len(missing)))
        raise RuntimeError(f'{len(missing)} central endpoints not yet available; use --allow-partial for checkpoints')
    _,_,sg,corner=gs.setup_engine()
    histories=pd.read_csv(HIST);hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    features=pd.read_csv(HERE/'CLASS_LABELS_REUSED.csv.gz',keep_default_na=False)
    features={(r['heldout_building'],r['worker_id']):r for r in features.to_dict('records') if r['heldout_building']!='ALL'}
    ledger=[];pending=[];frames=[]
    for pid,req in requests.groupby('pool_id',sort=True):
        needed=set(req.team_A)|set(req.team_B)|set(req.team_C)
        path=HERE/'results/pools'/f'{h(pid)[:20]}.csv.gz'
        if path.exists():
            existing=pd.read_csv(path,low_memory=False)
            assert set(existing.event_id)<=set(req.event_id)
        else:existing=pd.DataFrame()
        done=set(existing.event_id) if len(existing) else set()
        ready=req[~req.event_id.isin(done)&req.team_A.isin(teams)&req.team_B.isin(teams)&req.team_C.isin(teams)]
        d=existing
        if len(ready):
            pairs={};signatures={};out=[]
            for request in ready.to_dict('records'):
                ev=complete_event(request,teams,pairs,signatures,hist,sg,corner,'manual')
                ev['minimum_support']=math.ceil(ev['n']/2)
                for arm in 'ABC':
                    t=teams[ev['team_'+arm]]
                    for f in ['half_vote_nodes','node_supports','connection_available','order_tied','order_status','geometry_status','geometry_reason']:
                        v=t.get(f)
                        ev[arm+'_'+f]='|'.join(map(str,v)) if isinstance(v,list) else v
                # Preserve opaque identifiers that might happen to be all digits.
                for k in ['cell_id','panel_id','anchor_id','linked_n_path_id','linked_n_reference_panel','linked_m_path_id','linked_m_reference_event']:
                    if k in request:ev[k]=request[k]
                out.append(add_structure_histories(ev,request,features))
            new=pd.DataFrame(out);d=pd.concat([existing,new],ignore_index=True) if len(existing) else new
            assert not d.event_id.duplicated().any()
            write(path,d)
            save(path.with_suffix('.json'),dict(pool_id=pid,registered=len(req),evaluated=len(d),unique_endpoints=len(needed),
                reused_evaluated_events=len(existing),new_evaluated_events=len(ready),pair_geometries_new=len(pairs),
                request_ids_sha256=h(sorted(req.event_id)),result_sha256=sha(path),native_fusion_calls=0))
        if len(d)<len(req):
            pending.append(dict(pool_id=pid,registered_events=len(req),pending_events=len(req)-len(d),missing_endpoints=len(needed-set(teams))))
        if not len(d):continue
        frames.append(d);ledger.append(dict(pool_id=pid,file=str(path.relative_to(HERE)),events=len(d),sha256=sha(path)))
        print(json.dumps(dict(pool=pid,events=len(d),complete_ABC=int(d.all_complete.sum()))),flush=True)
    write(HERE/'results/POOL_RESULTS.csv',ledger);write(HERE/'results/PENDING_POOLS.csv',pending)
    E=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    if len(E):
        assert not E.event_id.duplicated().any()
        write(HERE/'EVENTS_COMPLETE.csv.gz',E)
    receipt=dict(complete=not pending,registered_events=len(requests),completed_events=len(E),pending_events=sum(x['pending_events'] for x in pending),
        required_endpoints=len(keys),available_endpoints=len(teams),missing_endpoints=len(missing),native_fusion_calls=0,
        source_event_file=str(request_path.relative_to(ROOT)),source_event_sha256=sha(request_path),result_sha256=sha(HERE/'EVENTS_COMPLETE.csv.gz') if len(E) else None,
        pair_metric_kernel=str((PRIOR/'joint_exchange/evaluate_joint.py').relative_to(ROOT)),history_source_sha256=sha(HIST),
        evaluator_sha256=sha(Path(__file__)),elapsed_seconds=time.monotonic()-start)
    save(HERE/'results/COMPLETION.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--allow-partial',action='store_true');args=ap.parse_args();run(args.allow_partial)
