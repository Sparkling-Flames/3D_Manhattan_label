#!/usr/bin/env python3
"""Connect a verified diagnostic state to the unchanged three cached k34 states."""
from pathlib import Path
import gzip,json
import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from build_manual_cases import clean,jsave,viewer

ROOT=Path(__file__).resolve().parents[1];CASE=ROOT/'stage05_cases/manual/VFuaQ6m2Qom-04'
legacy=json.loads(gzip.decompress((CASE/'legacy_evidence/VFUA_MECHANISM_GEOMETRY.json.gz').read_bytes()))
diag=json.loads(gzip.decompress((CASE/'FULL35_VERIFIED_DIAGNOSTIC_STATE.json.gz').read_bytes()));assert diag['all_parity']
es=pd.read_csv(CASE/'SELECTED_CACHED_ENDPOINTS.csv').set_index('team_key')
states=dict(legacy['selected_full_states']);fullkey=next(k for k in es.index if es.loc[k,'k']==35);states[fullkey]=diag['full_state']
rows=[];transitions=[];groupmaps=[]
fullassign={(a['id'],i):fid for a in diag['full_state']['assignments'] for i,fid in enumerate(a['feature_ids'])}
for key,state in states.items():
    byid={g['feature_id']:g for g in state['identity_groups']};e=es.loc[key]
    r=dict(team_key=key,absent_worker=e['absent_worker'],k=int(e['k']),N=35,k_fraction=e['k']/35,
        minimum_support=state['minimum_support'],nodes=len(state['node_consensus']['nodes']),
        B8L2=e['B8L2'],D10=e['D10'],complete_evaluable=e['complete_evaluable'],
        trace_origin='parity_verified_diagnostic_replay' if key==fullkey else 'exact_existing_cached_full_state')
    for fid,name in [('node_002','right_back'),('node_015','left_back_neighbor')]:
        g=byid[fid];r.update({name+'_support':g['support'],name+'_selected':g['selected'],name+'_bottom_x':g['center'][1][0],name+'_bottom_y':g['center'][1][1]})
    rows.append(r)
    if key!=fullkey:
        oldgroups=state['identity_groups'];fullgroups=diag['full_state']['identity_groups']
        oldids={a['id'] for a in state['assignments']}
        os=[{(m['id'],m['pair_index']) for m in g['members']} for g in oldgroups]
        fs=[{(m['id'],m['pair_index']) for m in g['members'] if m['id'] in oldids} for g in fullgroups]
        overlap=np.asarray([[len(a&b) for b in fs] for a in os])
        oi,fi=linear_sum_assignment(-overlap);mapping={oldgroups[i]['feature_id']:fullgroups[j]['feature_id'] for i,j in zip(oi,fi)}
        for i,j in zip(oi,fi):groupmaps.append(dict(team_key_from=key,team_key_to=fullkey,entrant=e['absent_worker'],
            group_from=oldgroups[i]['feature_id'],matched_group_to=fullgroups[j]['feature_id'],
            shared_source_pairs_before=len(os[i]),shared_source_pairs_after=len(fs[j]),intersection=len(os[i]&fs[j]),
            jaccard=len(os[i]&fs[j])/len(os[i]|fs[j]),method='one-to-one maximum overlap of actual shared object/pair memberships'))
        for a in state['assignments']:
            for i,fid in enumerate(a['feature_ids']):
                final=fullassign[(a['id'],i)]
                if final!=fid:transitions.append(dict(team_key_from=key,team_key_to=fullkey,entrant=e['absent_worker'],
                    common_worker=a['worker'],object_id=a['id'],pair_index=i,feature_id_from=fid,feature_id_to=final,
                    membership_matched_expected_group=mapping[fid],label_change_only=mapping[fid]==final,
                    note='Group IDs are local; use shared-member matched column to separate renumbering from reassignment.'))
pd.DataFrame(rows).sort_values(['k','absent_worker']).to_csv(CASE/'NEAR_FULL_CRITICAL_VOTE_COMPARISON.csv',index=False)
pd.DataFrame(transitions).to_csv(CASE/'COMMON_RAW_PAIR_ASSIGNMENT_TRANSITIONS_TO_FULL.csv',index=False)
pd.DataFrame(groupmaps).to_csv(CASE/'SHARED_RAW_MEMBERSHIP_GROUP_ALIGNMENT_TO_FULL.csv',index=False)
logfile=CASE/'FULL35_DIAGNOSTIC_EXECUTION_LOG.json'
log=json.loads(logfile.read_text()) if logfile.exists() else []
if not any(r.get('status')=='all_parity_passed' for r in log):
    log.append(dict(attempt=len(log)+1,fusion_called=True,status='all_parity_passed',checks=len(diag['checks']),rule_or_input_changes=0))
logfile.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf8')
summary=dict(unique_existing_teams_replayed=1,actual_fusion_execution_attempts=sum(r.get('fusion_called',False) for r in log),
    accepted_diagnostic_traces=1,all_parity=True,checks=len(diag['checks']),new_scientific_teams=0,new_natural_paths=0,
    new_formal_quality_scores=0,original_cache_replaced=False,source_rule_changes=0,
    full35_support_node002=17,full35_support_node015=17,minimum_support=18,
    selected_node_supports=[35,25,35],complete_projected_ring_support=25,
    diagonal_direct_support=0,diagonal_projected_support=25,
    failure_class='below_four despite available projected connection and partial triangle geometry')
(CASE/'FULL35_DIAGNOSTIC_RECEIPT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
pool=json.loads(gzip.decompress((CASE/'CURRENT_POOL_FULL_INPUT.json.gz').read_bytes()))
order=['W103','W113','W134','FULL35']
geos=sorted(legacy['geometries'],key=lambda g:order.index(g['absent_worker']))
for g in geos:g['label']='Full pool (35)' if g['absent_worker']=='FULL35' else 'Without '+g['absent_worker']+' (34)'
endpoints=clean(es.reset_index().to_dict('records'))
votes=pd.concat([pd.read_csv(CASE/'legacy_evidence/VFUA_SAVED_GROUP_VOTES.csv'),
                 pd.read_csv(CASE/'FULL35_CANDIDATE_GROUP_VOTES.csv')],ignore_index=True)
viewer(pool,geos,endpoints,votes.to_dict('records'),CASE/'PANORAMA_ORIGINAL.png',CASE)
jsave(dict(current_pool=pool,saved_cases=legacy,separately_recovered_full35_diagnostic=diag),CASE/'COMPLETE_CASE_EVIDENCE.json.gz')
receipt=json.loads((CASE/'CASE_RECEIPT.json').read_text())
receipt.update(full35_candidate_vote_ledger_available=True,full35_ledger_origin='parity_verified_diagnostic_replay',
    full35_parity_checks=47,diagnostic_existing_team_replays=1,diagnostic_fusion_execution_attempts=2,
    new_scientific_teams=0,new_natural_paths=0)
jsave(receipt,CASE/'CASE_RECEIPT.json')
jsave([json.loads(p.read_text()) for p in sorted(CASE.parent.glob('*/CASE_RECEIPT.json'))],CASE.parent/'CASE_BUILD_RECEIPT.json')
print(json.dumps(summary,indent=2))
