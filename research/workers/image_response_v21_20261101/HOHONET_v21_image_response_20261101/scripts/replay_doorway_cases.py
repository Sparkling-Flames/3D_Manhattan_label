#!/usr/bin/env python3
"""Recover only three missing full-state traces; require exact cached-endpoint parity."""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
from pathlib import Path
import hashlib,json,sys,time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'stage04_doorway_cases/replay_engine'
sys.path.insert(0,str(ROOT/'vendor'));sys.path.insert(0,str(ENGINE))
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse,WORKING_GAP
from tools.thesis_main.analysis.wall_consensus_v1_process_20261017 import cached_matching
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.wall_consensus_quality_20261015 import measured
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores
from prepare_doorway_cases import save,clean


def field_equal(a,b,tol=1e-8):
    if a is None or b is None:return a is None and b is None
    if isinstance(a,(float,int)) and not isinstance(a,bool):
        return isinstance(b,(float,int)) and abs(float(a)-float(b))<=tol
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(field_equal(x,y,tol) for x,y in zip(a,b))
    if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(field_equal(a[k],b[k],tol) for k in a)
    return a==b


def main():
    root=ROOT;out=root/'stage04_doorway_cases';design=json.loads((out/'CASE_DESIGN_BEFORE_REPLAY.json').read_text())
    records=json.loads((out/'inputs/FROZEN_CASE_RECORDS.json').read_text())
    refs={r['target_id']:r for r in json.loads((out/'inputs/FINAL_CASE_REFERENCES.json').read_text())}
    assert WORKING_GAP==7.5
    request_hash=hashlib.sha256((out/'CASE_DESIGN_BEFORE_REPLAY.json').read_bytes()).hexdigest()
    ledger=[]
    enginedir=ENGINE/'research/statistics/b8l2_shared_v6_20261016/inputs'
    with cached_matching(),scoring_engine(enginedir/'measurement_engine.zip',enginedir/'working_models.py') as (engine,models):
        for request in design['endpoint_requests']:
            folder=out/'cases'/request['case_id'];side=request['side']
            saved=json.loads((root/request['saved_endpoint']).read_text())
            source_geometry=saved['geometry'];source_nodes=int(saved['nodes'])
            source_support=saved.get('node_supports')
            start=time.perf_counter()
            checkpoint=folder/(side+'_VERIFIED_FULL_TRACE.json')
            prior=json.loads(checkpoint.read_text()) if checkpoint.exists() else None
            reused_checkpoint=bool(prior and prior.get('all_parity') and prior.get('request_file_sha256')==request_hash)
            if request['diagnostic_replay_required'] and reused_checkpoint:
                state=prior['full_state'];score=prior['score'];kind='new_diagnostic_replay'
            elif request['diagnostic_replay_required']:
                team=[records[oid] for oid in request['member_object_ids_in_source_order']]
                assert len(team)==request['k']==len({r['worker'] for r in team})
                state=fuse(team,gap=WORKING_GAP)['automatic'];kind='new_diagnostic_replay'
                ref=refs[request['target_id']]
                score=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
                full=request['k']!=2 and len(state['node_consensus']['nodes'])>=4 and state['candidate'].get('geometry_status')=='ok'
                finite=all(score.get(c) is not None and np.isfinite(score[c]) for c in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter'])
                score.update(dual_scores(score,models) if full and finite else dict(B8L2=None,D10=None,IoU3D100=None))
                score['complete_evaluable']=bool(full and finite)
            else:
                cached=json.loads((folder/(side+'_CACHED_FULL_TRACE.json')).read_text())
                state=cached['full_state'];kind='reused_exact_saved_full_trace'
                assert cached['comparison_to_saved_endpoint']['all_parity']
                # The archived full-state export stores a prior parity receipt,
                # not target score values. Verify Q against today's same target
                # from the saved state, without another fusion run.
                ref=refs[request['target_id']]
                score=measured(engine,state,dict(floor=ref['floor_xz_h'],points=ref['points_1024x512']))
                score.update(dual_scores(score,models))
                score['complete_evaluable']=cached['replay_endpoint_without_state']['complete_evaluable']
            state=clean(state);score=clean(score)
            checks={}
            for c in ['points','footprint','feature_ids','ring_confirmed','order_status','geometry_status','status','reason']:
                checks['geometry_'+c]=field_equal(source_geometry.get(c),state['candidate'].get(c))
            checks['n']=int(state['n'])==request['k']
            checks['minimum_support']=state['minimum_support']==saved['minimum_support']
            checks['nodes']=len(state['node_consensus']['nodes'])==source_nodes
            selected_support=[g['support'] for g in state['identity_groups'] if g['selected']]
            checks['selected_support_multiset']=sorted(selected_support)==sorted(source_support) if source_support is not None else None
            checks['complete_evaluable']=bool(score['complete_evaluable'])==bool(request['saved_scalar']['complete_evaluable'])
            for q in ['B8L2','D10','IoU3D100']:
                checks[q+'_parity']=field_equal(score.get(q),request['saved_scalar'].get(q),1e-7)
            parity=all(v is not False for v in checks.values())
            payload={'request':request,'request_file_sha256':request_hash,'trace_kind':kind,'full_state':state,
                     'score':score,'comparison_to_current_saved_endpoint':checks,'all_parity':parity,
                     'elapsed_seconds':time.perf_counter()-start,'gap':WORKING_GAP,'MV50':'>=50% of all independent members',
                     'execution_checkpoint_reused':reused_checkpoint,
                     'new_scientific_team':False,'new_natural_path':False,'saved_endpoint_replaced':False}
            save(folder/(side+'_VERIFIED_FULL_TRACE.json'),payload)
            ledger.append({'case_id':request['case_id'],'side':side,'source_key':request['source_key'],'k':request['k'],
                           'trace_kind':kind,'all_parity':parity,**checks,'elapsed_seconds':payload['elapsed_seconds']})
            print(request['case_id'],side,kind,'parity',parity,'failed',[k for k,v in checks.items() if v is False],flush=True)
    pd.DataFrame(ledger).to_csv(out/'DIAGNOSTIC_REPLAY_LEDGER.csv',index=False)
    save(out/'DIAGNOSTIC_REPLAY_RECEIPT.json',{'request_sha256':request_hash,
         'new_diagnostic_replays':sum(x['trace_kind']=='new_diagnostic_replay' for x in ledger),
         'reused_full_states':sum(x['trace_kind']=='reused_exact_saved_full_trace' for x in ledger),
         'new_scientific_teams':0,'new_natural_paths':0,'all_parity':all(x['all_parity'] for x in ledger),
         'source_commit':design['source_commit'],'recorded_rule_changes':0})
    assert all(x['all_parity'] for x in ledger),'No failed replay may be used as mechanism evidence.'
if __name__=='__main__':main()
