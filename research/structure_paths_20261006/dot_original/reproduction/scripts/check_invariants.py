"""Read-only checks independent of published summary counters."""
from pathlib import Path
import json,gzip,hashlib,math,sys
from collections import Counter
import numpy as np
source,out,dest=map(Path,sys.argv[1:4])
def load(p):return json.loads(Path(p).read_text())
def jsonl(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
checks=Counter();counts=Counter();max_distance_error=0.;notes=[]
for f in sorted((source/'inputs').glob('*.json')):
    if f.name=='human_review.json':continue
    im=load(f);image=im['image'];records={r['id']:r for r in im['records']};nodes=load(out/image/'nodes.json')
    # Roster identity and raw points match the supplied earlier delivery exactly.
    assert f.read_bytes()==(source/'upstream/prior_point_correspondence/inputs'/f.name).read_bytes()
    checks['unchanged_prior_input_files']+=1
    assert len(nodes)==sum(len(r['points'])//2 for r in records.values())
    assert len({(n['id'],n['pair_index']) for n in nodes})==len(nodes)
    for n in nodes:
        r=records[n['id']];k=n['pair_index']
        assert n['points']==r['points'][2*k:2*k+2]
        assert n['worker']==r['worker']
        assert n['source_pair_index']==r['source_pair_indices'][k]
        assert n['source_point_indices']==r['source_point_indices'][2*k:2*k+2]
        checks['immutable_source_nodes']+=1
    # Independent vector/angular distance, rather than the baseline haversine routine.
    pp=np.array([n['points'] for n in nodes]);mat={}
    for name,j in [('top',0),('bottom',1)]:
        u=(pp[:,j,0]/1024-.5)*2*np.pi;v=(.5-pp[:,j,1]/512)*np.pi
        vv=np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]
        mat[name]=np.degrees(np.arctan2(np.linalg.norm(np.cross(vv[:,None],vv[None,:]),axis=-1),vv@vv.T))
    mat['pair']=np.maximum(mat['top'],mat['bottom'])
    for metric in ['pair','top','bottom']:
        for tau in [5,9,12]:
            state=load(out/image/f'{metric}_{tau}.json')
            assert state['source_unchanged'] is True and state['vote_denominator']==len(records)
            policies=[state['raw_MV'],state['path_witness_MV'],load(out/'analysis'/f'{image}_{metric}_{tau}_three_state.json')]
            for policy in policies:
                allnodes=[];selected=0
                for g in policy['groups']:
                    ix=g['node_indices'];allnodes+=ix;workers=[nodes[i]['worker'] for i in ix]
                    assert g['support']==len(ix)==len(set(workers))
                    assert g['support_workers']==workers
                    assert g['selected']==(len(ix)>=math.ceil(len(records)/2))
                    assert mat[metric][np.ix_(ix,ix)].max()<=tau+1e-9
                    for s in ['pair','top','bottom']:
                        err=abs(mat[s][np.ix_(ix,ix)].max()-g['marginal_diameters_deg'][s])
                        max_distance_error=max(max_distance_error,float(err));assert err<1e-9
                    checks['valid_full_pool_identity_groups']+=1;selected+=g['selected']
                assert sorted(allnodes)==list(range(len(nodes)))
                assert policy['ring']['selected_pair_count']==selected
                assert policy['ring']['minimum_four_pairs_enforced'] is False
                assert len(policy['ring']['x_diagnostic']['points'])==2*selected
                checks['complete_partitions_with_unfilled_actual_votes']+=1
            ledger=jsonl(out/image/f'{metric}_{tau}_path_evidence.jsonl.gz')
            actual={tuple(r['nodes']) for r in ledger}
            expected={(i,j) for i in range(len(nodes)) for j in range(i+1,len(nodes))
                      if nodes[i]['worker']!=nodes[j]['worker'] and mat[metric][i,j]<=tau+1e-10}
            assert actual==expected and len(actual)==len(ledger)
            counts['all_logged_cross_worker_candidate_pairs']+=len(ledger)
            counts['numerically_unresolved_witness_rows']+=sum(r['status']=='numerically_unresolved' for r in ledger)
            checks['exhaustive_declared_candidate_ledgers']+=1
    paths=load(out/image/'source_path_catalogue.json')
    for p in paths:
        r=records[p['id']];n=len(r['points'])//2;ix=p['processed_pair_indices']
        assert ix==[(ix[0]+p['direction_relative_to_source']*k)%n for k in range(p['edge_count']+1)]
        assert p['edge_count'] in [1,2]
        assert p['points']==[pt for k in ix for pt in r['points'][2*k:2*k+2]]
        assert p['source_pair_indices']==[r['source_pair_indices'][k] for k in ix]
        assert [z['pair_index'] for z in p['internal_observations']]==ix[1:-1]
        checks['source_path_order_and_interiors_preserved']+=1
    for tau in [5,9,12]:
        state=load(out/image/f'pair_{tau}.json');groups={g['feature_id']:g for g in state['raw_MV']['groups']}
        for c in jsonl(out/'patches'/f'{image}_{tau}_candidate_rings.jsonl.gz'):
            base=np.array(records[c['base_record']]['points']).reshape(-1,2,2)
            donor=np.array(records[c['donor_record']]['points']).reshape(-1,2,2)[c['donor_path_used_order']].copy()
            gs=[groups[k] for k in c['anchor_group_ids']]
            donor[0]=gs[0]['center']['points'];donor[-1]=gs[1]['center']['points']
            expected=np.concatenate([donor,base[c['base_context_retained_indices']]],axis=0)
            assert np.array_equal(expected.reshape(-1,2),np.array(c['points']))
            anchor=base.copy();ix=c['base_processed_path'];anchor[ix[0]]=donor[0];anchor[ix[-1]]=donor[-1]
            assert np.array_equal(anchor.reshape(-1,2),np.array(c['anchor_only_control_points']))
            assert c['base_internal_vertices_removed_in_candidate_only']==ix[1:-1]
            assert c['whole_candidate_support']=='not_established'
            assert c['vote_denominator_unchanged']==len(records)
            assert c['voting_role']=='not_an_independent_vote'
            assert c['anchor_supports']==[g['support'] for g in gs]
            checks['candidate_construction_and_support_scope']+=1
            counts[image+':'+str(tau)+':'+c['post_center_compatibility_status']]+=1
for name in ['analysis/automatic_candidates_frozen_before_human_read.json','evaluation/pre_reference_candidate_digest.json']:
    manifest=load(out/name)
    assert all(hashlib.sha256((out/k).read_bytes()).hexdigest()==digest for k,digest in manifest.items())
    checks['valid_saved_pre_read_hash_manifests']+=1
first=load(dest/'source_before.json');last=load(dest/'source_after.json')
existing_changed=[p for p in first if last.get(p)!=first[p]];added=sorted(set(last)-set(first))
assert not existing_changed
integrity={'existing_published_files':len(first),'changed_or_missing_existing_files':existing_changed,
           'added_files_observed_during_concurrent_checks':added,'all_additions_python_cache':all('__pycache__' in p for p in added)}
(dest/'source_integrity.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2)+'\n')
summary={'checks':dict(checks),'counts':dict(counts),'max_independent_vector_haversine_diameter_difference_deg':max_distance_error,
         'source_integrity':integrity,'scope':'Four supplied previous-image rosters only; no missing latest-local data or semantic truth inferred.'}
(dest/'invariant_checks.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
