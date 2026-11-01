#!/usr/bin/env python3
"""One diagnostic full-state replay, accepted only if it matches the frozen full35 endpoint."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
from pathlib import Path
import gzip,hashlib,json,sys,time
import numpy as np,pandas as pd

ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'stage05_cases/manual/VFuaQ6m2Qom-04'
ENGINE=ROOT/'stage04_doorway_cases/replay_engine'
sys.path.insert(0,str(ROOT/'vendor'));sys.path.insert(0,str(ENGINE))
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse,WORKING_GAP
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured
from build_manual_cases import clean,jsave

def eq(a,b,tol=1e-10):
    if a is None or b is None:return a is None and b is None
    if isinstance(a,(int,float,np.number)) and not isinstance(a,bool):
        return isinstance(b,(int,float,np.number)) and abs(float(a)-float(b))<=tol
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(eq(x,y,tol) for x,y in zip(a,b))
    if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(eq(a[k],b[k],tol) for k in a)
    return a==b

def main():
    assert WORKING_GAP==7.5
    poolfile=CASE/'CURRENT_POOL_FULL_INPUT.json.gz';pool=json.loads(gzip.decompress(poolfile.read_bytes()))
    legacyfile=CASE/'legacy_evidence/VFUA_MECHANISM_GEOMETRY.json.gz';legacy=json.loads(gzip.decompress(legacyfile.read_bytes()))
    savedgeo=next(g for g in legacy['geometries'] if g['absent_worker']=='FULL35')
    scalar=clean(pd.read_csv(CASE/'TRACED_ENDPOINT_METRICS.csv').query('k == 35').iloc[0].to_dict())
    source_scalar=clean(pd.read_csv(CASE/'SELECTED_CACHED_ENDPOINTS.csv').query('k == 35').iloc[0].to_dict())
    objects=scalar['member_object_ids'].split('|');lookup={r['object_id']:r for r in pool['records']}
    team=[lookup[o] for o in objects]
    assert len(team)==35==len({r['worker'] for r in team})==len(lookup)
    design=dict(source_commit='e1873bfadc1d0e61499809c91fba9dc39c717f83',
        purpose='Recover missing candidate-group/assignment/connection trace for the already observed unique full35 endpoint.',
        pool_id=pool['pool_id'] if 'pool_id' in pool else pool['meta']['pool_id'],team_key=scalar['team_key'],k=35,N=35,
        member_object_ids_in_cached_order=objects,member_workers=[r['worker'] for r in team],gap=7.5,
        pool_input_sha256=hashlib.sha256(poolfile.read_bytes()).hexdigest(),
        saved_geometry_file_sha256=hashlib.sha256(legacyfile.read_bytes()).hexdigest(),
        engine_receipt=str((ROOT/'stage04_doorway_cases/REPLAY_CODE_FETCH_RECEIPT.json').relative_to(ROOT)),
        engine_receipt_sha256=hashlib.sha256((ROOT/'stage04_doorway_cases/REPLAY_CODE_FETCH_RECEIPT.json').read_bytes()).hexdigest(),
        expected_minimum_support=18,expected_nodes=3,expected_selected_supports=[35,25,35],
        acceptance='Every saved geometry field, input identity, selected support, node count, available partial score and output state must match; otherwise no mechanism claim.',
        geometry_tolerance=1e-10,partial_score_tolerance=1e-8,new_scientific_teams=0,new_paths=0,
        reference_changed=False,source_answers_changed=False,fusion_rules_changed=False,replace_saved_endpoint=False)
    designfile=CASE/'FULL35_DIAGNOSTIC_DESIGN_BEFORE_REPLAY.json'
    if designfile.exists():assert json.loads(designfile.read_text())==design,'Frozen replay request changed.'
    else:jsave(design,designfile)
    designhash=hashlib.sha256(designfile.read_bytes()).hexdigest()
    outfile=CASE/'FULL35_VERIFIED_DIAGNOSTIC_STATE.json.gz';cached=None
    if outfile.exists():
        cached=json.loads(gzip.decompress(outfile.read_bytes()))
        assert cached['request_sha256']==designhash
    start=time.perf_counter()
    if cached and cached.get('all_parity'):
        state=cached['full_state'];score=cached['diagnostic_partial_measurement'];execution='reused_verified_checkpoint'
    else:
        with cached_matching():state=fuse(team,gap=7.5)['automatic']
        enginedir=ENGINE/'research/statistics/b8l2_shared_v6_20261016/inputs'
        with scoring_engine(enginedir/'measurement_engine.zip',enginedir/'working_models.py') as (engine,models):
            ref=pool['reference'];score=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
        execution='new_diagnostic_replay'
    state=clean(state);score=clean(score)
    checks={}
    for key,value in savedgeo['geometry'].items():checks['geometry_'+key]=eq(value,state['candidate'].get(key))
    checks.update(n=state['n']==35,minimum_support=state['minimum_support']==18,
        nodes=len(state['node_consensus']['nodes'])==3,
        identity_groups=len(state['identity_groups'])==int(source_scalar['identity_groups_n']),
        unselected_groups=sum(not g['selected'] for g in state['identity_groups'])==int(source_scalar['unselected_groups_n']),
        selected_supports=[g['support'] for g in state['identity_groups'] if g['selected']]==[35,25,35],
        exact_object_identity={a['id'] for a in state['assignments']}==set(objects),
        exact_worker_identity={a['worker'] for a in state['assignments']}==set(design['member_workers']),
        below_four=len(state['node_consensus']['nodes'])<4 and scalar['score_status']=='below_four',
        complete_evaluable_false=not bool(scalar['complete_evaluable']) and len(state['node_consensus']['nodes'])<4,
        B8L2_missing=scalar['B8L2'] is None,D10_missing=scalar['D10'] is None,IoU3D100_missing=scalar['IoU3D100'] is None)
    for key in ['iou_2d','S_bottom_deg','dir','omission','extension']:
        checks['partial_'+key]=eq(scalar[key],score.get(key),1e-8)
    for g in state['identity_groups']:
        n=len({a['worker'] for a in state['assignments'] if g['feature_id'] in a['feature_ids']})
        checks['assignment_votes_'+g['feature_id']]=n==g['support'] and (2*n>=35)==g['selected']
    parity=all(checks.values())
    payload=dict(request_sha256=designhash,execution_kind=execution,all_parity=parity,checks=checks,
        full_state=state,diagnostic_partial_measurement=score,formal_quality=dict(B8L2=None,D10=None,IoU3D100=None),
        formal_status='below_four',new_scientific_teams=0,new_paths=0,new_unique_endpoints=0,
        diagnostic_fusion_runs=1,new_formal_quality_scores=0,elapsed_seconds=time.perf_counter()-start,
        source_endpoint_replaced=False)
    jsave(payload,outfile)
    pd.DataFrame([dict(check=k,passed=v) for k,v in checks.items()]).to_csv(CASE/'FULL35_DIAGNOSTIC_PARITY.csv',index=False)
    print(json.dumps(dict(all_parity=parity,failed=[k for k,v in checks.items() if not v],
                         groups=len(state['identity_groups']),elapsed_seconds=payload['elapsed_seconds']),indent=2),flush=True)
    assert parity,'Rejected diagnostic replay: do not use its candidate ledger as mechanism evidence.'
    votes=[];assignments=[];edges=[]
    for g in state['identity_groups']:
        votes.append(dict(team_key=scalar['team_key'],feature_id=g['feature_id'],support=g['support'],
            selected=g['selected'],minimum_support=state['minimum_support'],
            top_x=g['center'][0][0] if g['center'] else None,top_y=g['center'][0][1] if g['center'] else None,
            bottom_x=g['center'][1][0] if g['center'] else None,bottom_y=g['center'][1][1] if g['center'] else None,
            member_workers='|'.join(m['worker'] for m in g['members']),member_object_ids='|'.join(m['id'] for m in g['members']),
            trace_origin='parity_verified_diagnostic_replay'))
    for a in state['assignments']:
        for i,fid in enumerate(a['feature_ids']):assignments.append(dict(team_key=scalar['team_key'],
            worker=a['worker'],object_id=a['id'],pair_index=i,feature_id=fid))
    for edge in state['ring_diagnostics']['edges']:edges.append(dict(team_key=scalar['team_key'],**edge))
    pd.DataFrame(votes).to_csv(CASE/'FULL35_CANDIDATE_GROUP_VOTES.csv',index=False)
    pd.DataFrame(assignments).to_csv(CASE/'FULL35_RAW_ASSIGNMENTS.csv',index=False)
    pd.DataFrame(edges).to_csv(CASE/'FULL35_CONNECTION_EDGES.csv',index=False)
    jsave(state['ring_diagnostics'],CASE/'FULL35_RING_DIAGNOSTICS.json')
if __name__=='__main__':main()
