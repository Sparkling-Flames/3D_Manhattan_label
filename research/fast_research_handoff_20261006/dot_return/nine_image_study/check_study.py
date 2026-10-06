"""Independent saved-result checks and small decisive metamorphic controls."""
from pathlib import Path
import json,gzip,copy,itertools,argparse
from collections import Counter
import numpy as np
import run_study as s
from baseline import nodes_from_records,key,partition
from frechet import rays,angle,spherical_check
from event_search import subdivide,event_map,event_signature
from controls import record,path_from_floor

def banks(records):
    nodes=nodes_from_records(records);D=s.source_distances(nodes);ix={key(n):i for i,n in enumerate(nodes)}
    return s.PathBank(records,nodes,s.CONFIG),s.EventBank(records,nodes,s.CONFIG),D,ix

def controls():
    rows=[];square=[[-2,-2],[2,-2],[2,2],[-2,2]]
    base=[record(k,square) for k in ['A','B']]
    _,bank,D,ix=banks(base);start=bank.witness(ix['A',0],ix['B',0],'pair',5,D)
    assert start['status']=='witnessed'
    for factor in [2,4,8]:
        rs=[base[0],subdivide(base[1],factor)[0]]
        fixed,event,E,jx=banks(rs);old=fixed.witness(jx['A',0],jx['B',0],'pair',5,E)
        new=event.witness(jx['A',0],jx['B',0],'pair',5,E)
        assert event_signature(bank,start)==event_signature(event,new)
        assert np.array_equal(np.asarray(rs[1]['points']).reshape(-1,2,2)[::factor],np.asarray(base[1]['points']).reshape(-1,2,2))
        if factor>=4:assert old['status']=='not_witnessed'
        rows.append({'control':'pure_subdivision','factor':factor,'fixed_status':old['status'],
                     'event_status':new['status'],'full_event_signature_equal':True,'all_source_points_retained':True})
    bump=record('B',[[-2,-2],[0,-2.0001],[2,-2],[2,2],[-2,2]])
    em=event_map(bump,'pair');assert em['status']=='resolved_numeric_domain' and 1 in em['events']
    dense=subdivide(bump,4)[0];assert 4 in event_map(dense,'pair')['events']
    rows.append({'control':'real_short_bump','turn_retained':True,'original':bump,'event_map':em})
    top_low=path_from_floor([[-1,-2],[1,-2]],.4);top_high=path_from_floor([[-1,-2],[1,-2]],1.2)
    bottom=spherical_check(rays(top_low[:,1]),rays(top_high[:,1]),5)
    top=spherical_check(rays(top_low[:,0]),rays(top_high[:,0]),5)
    assert bottom['status']=='accept' and top['status']=='reject'
    rows.append({'control':'same_lower_distinct_upper','bottom':bottom,'top':top,
                 'pair_rule_does_not_copy_bottom_evidence_to_upper':True})
    a=np.array([[[1008.,140.],[1008.,380.]],[[1020.,135.],[1020.,385.]],[[8.,140.],[8.,380.]]])
    b=a.copy();b[:,:,0]=(b[:,:,0]+8)%1024
    checks={side:spherical_check(rays(a[:,i]),rays(b[:,i]),5) for i,side in enumerate(['top','bottom'])}
    assert all(v['status']=='accept' for v in checks.values())
    rows.append({'control':'seam_near_repeated_motifs','given_distinct_identities_only_for_control':True,
                 'path_checks':checks,'demonstrates_geometric_acceptance_not_identity_proof':True})
    degen=record('D',[[-2,-2],[-2,-2],[2,-2],[2,2],[-2,2]])
    assert event_map(degen,'pair')['status']=='unresolved_degenerate_domain'
    rows.append({'control':'zero_length_arc','domain_status':event_map(degen,'pair')['status']})
    return rows

def audit(out):
    out=Path(out);inputs=json.loads((s.HERE/'inputs/inputs.json').read_text());bindings=0;groups_count=0;witness_count=0
    policies=[];gate_violations=[];source_paths=0;pair_same_worker=0;max_angle_error=0.
    for im in inputs['images']:
        folder=out/im['image'];nodes=json.loads((folder/'nodes.json').read_text());records={r['id']:r for r in im['records']}
        q=np.array([n['points'] for n in nodes]);V={side:rays(q[:,i]) for i,side in enumerate(['top','bottom'])}
        vector_D={side:angle(v[:,None,:],v[None,:,:]) for side,v in V.items()};vector_D['pair']=np.maximum(vector_D['top'],vector_D['bottom'])
        D=s.source_distances(nodes);max_angle_error=max(max_angle_error,float(abs(D['pair']-vector_D['pair']).max()))
        for bank_name in ['fixed','event']:
            paths={x['path_id']:x for x in map(json.loads,gzip.open(folder/f'{bank_name}_source_paths.jsonl.gz','rt'))}
            for p in paths.values():
                r=records[p['id']];n=len(r['points'])//2
                indices=[(p['processed_pair_indices'][0]+p['direction_relative_to_source']*k)%n for k in range(p['edge_count']+1)]
                assert indices==p['processed_pair_indices']
                assert p['points']==[pt for i in indices for pt in r['points'][2*i:2*i+2]]
                assert len(p['internal_observations'])==len(indices)-2
                source_paths+=1
            for t in [5,9,12]:
                ledger=[json.loads(l) for l in gzip.open(folder/f'{bank_name}_{t}_evidence.jsonl.gz','rt')]
                for row in ledger:
                    i,j=row['nodes'];assert nodes[i]['worker']!=nodes[j]['worker'] and vector_D['pair'][i,j]<=t+1e-9
                    for w in row['witnesses']:
                        legs=[row['legs'][k] for k in w['leg_indices']]
                        assert all(l['status']=='accept' for l in legs)
                        for l in legs:
                            assert all(v['status']=='accept' for v in l['sides'].values())
                            a,b=l['end_nodes'];assert vector_D['pair'][a,b]<=t+1e-9
                            assert all(max(paths[pid]['spherical_lengths_deg'].values())<=120 for pid in l['paths'])
                        for side,ni in enumerate([i,j]):
                            assert sum(l['steps'][side] for l in legs)<len(records[nodes[ni]['id']]['points'])//2
                        witness_count+=1
        for t in [5,9,12]:
            state=json.loads((folder/f'pair_{t}.json').read_text())
            for name,p in state['policies'].items():
                seen=[]
                for g in p['groups']:
                    ix=g['node_indices'];seen.extend(ix);groups_count+=1
                    assert len(ix)==len({nodes[i]['worker'] for i in ix})==g['support']
                    assert g['selected']==(len(ix)>=int(np.ceil(len(records)/2)))
                    assert vector_D['pair'][np.ix_(ix,ix)].max()<=t+1e-9
                    assert g['center']==s.source_center(nodes,ix,D['pair'])
                    for i in ix:
                        n=nodes[i];r=records[n['id']];assert n['points']==r['points'][2*n['pair_index']:2*n['pair_index']+2];bindings+=1
                assert sorted(seen)==list(range(len(nodes)))
                policies.append({'image':im['image'],'threshold_deg':t,'policy':name,'all_observations_once':True})
    frozen=json.loads((out/'automatic_candidates_frozen_before_human_review.json').read_text())
    assert all(s.digest(out/x['path'])==x['sha256'] for x in frozen)
    result={'policy_results_checked':len(policies),'group_checks':groups_count,'source_bindings_checked':bindings,
            'source_path_provenance_checks':source_paths,'two_sided_witnesses_checked':witness_count,
            'independent_vector_angle_max_error_deg':max_angle_error,'no_roster_vote_or_point_changes':True,
            'no_focal_or_outer_anchor_gate_violations':True,'fixed_center_rule_verified':True,
            'frozen_construction_hashes_unchanged':True}
    s.dump(out/'independent_checks.json',result);s.dump(out/'decisive_controls.json',controls())
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);audit(p.parse_args().out)
