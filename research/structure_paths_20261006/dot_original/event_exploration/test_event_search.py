import copy,json,math
import numpy as np
import pytest
from event_search import *
from controls import record,path_from_floor
from run_exploration import banks

SQUARE=[[-2,-2],[2,-2],[2,2],[-2,2]]

@pytest.mark.parametrize('factor',[2,4,8])
def test_turn_events_and_geometry_preserved_under_subdivision(factor):
    r=record('A',SQUARE);before=copy.deepcopy(r);q,v=subdivide(r,factor)
    for metric in ('top','bottom','pair'):
        e=event_map(q,metric)
        assert e['status']=='resolved_numeric_domain'
        assert e['events']==[i*factor for i in range(4)]
    assert v['maximum_arc_additivity_error_deg']<1e-8
    assert r==before
    assert np.array_equal(np.asarray(q['points']).reshape(-1,2,2)[::factor],np.asarray(r['points']).reshape(-1,2,2))


def test_original_fixed_hop_failure_and_event_recovery():
    saved=json.loads((SOURCE/'results/controls/fixed_hop_subdivision_counterexample.json').read_text())
    old,event,D,ix=banks(saved['records']);i=ix[('A',0)];j=ix[('B',0)]
    assert old.witness(i,j,'pair',5,D)==saved['result']
    z=event.witness(i,j,'pair',5,D)
    assert saved['result']['status']=='not_witnessed' and z['status']=='witnessed'
    assert any(max(l['steps'])>2 for l in z['legs'] if l['status']=='accept')


def test_straight_source_focus_is_kept_even_when_not_an_event():
    floor=[[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]]
    rs=[record('A',floor),record('B',floor)]
    _,base,D,ix=banks(rs);z=base.witness(ix[('A',1)],ix[('B',1)],'pair',5,D)
    assert 1 not in event_map(rs[0],'pair')['events']
    assert z['status']=='witnessed' and z['focal_observations_retained']
    dense=[subdivide(r,4)[0] for r in rs];_,probe,E,jx=banks(dense)
    zz=probe.witness(jx[('A',4)],jx[('B',4)],'pair',5,E)
    assert event_signature(base,z)==event_signature(probe,zz)


def test_top_only_turn_enters_pair_union_without_bottom_identity_vote():
    floor=[[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]]
    r=record('A',floor);r['points'][2][1]-=.1
    assert 1 not in event_map(r,'bottom')['events']
    assert 1 in event_map(r,'top')['events']
    assert 1 in event_map(r,'pair')['events']
    q,_=subdivide(r,4)
    assert 4 not in event_map(q,'bottom')['events']
    assert 4 in event_map(q,'pair')['events']


def test_straight_continuation_not_equal_to_antiparallel_backtrack():
    # Vertex1 immediately reverses the just-traversed arc. It remains an event.
    r=record('A',[[-2,-2],[0,-2],[-2,-2],[2,2],[-2,2]])
    e=event_map(r,'pair');assert e['status']=='resolved_numeric_domain'
    assert 1 in e['events']
    assert min(e['vertices'][1]['turn_deg'].values())>179.999


def test_zero_length_arc_is_unresolved_not_silently_removed():
    r=record('A',[[-2,-2],[-2,-2],[2,-2],[2,2],[-2,2]])
    assert event_map(r,'pair')['status']=='unresolved_degenerate_domain'
    s=copy.deepcopy(r);s.update(id='B',worker='B')
    _,event,D,ix=banks([r,s]);z=event.witness(ix[('A',0)],ix[('B',0)],'pair',5,D)
    assert z['status']=='domain_unresolved' and not z['witnesses']


def test_near_antipodal_arc_is_unresolved():
    q=np.array([[[512.,256.],[512.,256.]],[[0.,256.],[0.,256.]],[[700.,200.],[700.,300.]]])
    r=record('A',SQUARE);r['points']=q.reshape(-1,2).tolist()
    assert event_map(r,'pair')['status']=='unresolved_degenerate_domain'


def test_near_collinearity_threshold_is_not_certified():
    r=record('A',[[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]])
    # Numerically construct a tiny perturbation around the fixed tolerance.
    r['points'][2][1]+=1e-7
    e=event_map(r,'pair')
    assert e['status']=='unresolved_near_collinearity_threshold'


def test_genuine_small_bump_is_retained():
    r=record('A',[[-2,-2],[0,-2.0001],[2,-2],[2,2],[-2,2]])
    e=event_map(r,'pair');assert e['status']=='resolved_numeric_domain'
    assert 1 in e['events']


def test_arc_cap_is_not_replaced_by_a_hop_cap_and_cycle_excluded():
    rs=[subdivide(record(x,SQUARE),8)[0] for x in ('A','B')]
    _,event,D,ix=banks(rs);z=event.witness(ix[('A',0)],ix[('B',0)],'pair',5,D)
    assert z['status']=='witnessed'
    for w in z['witnesses']:
        ll=[z['legs'][i] for i in w['leg_indices']]
        assert all(sum(l['steps'][j] for l in ll)<32 for j in (0,1))
        for l in ll:
            for pid in l['paths']:
                assert max(event.paths[pid]['spherical_lengths_deg'].values())<=120
    assert any(max(l['steps'])==8 for l in z['legs'] if l['status']=='accept')
    assert all(len(p['points'])==2*(p['edge_count']+1) for p in event.public_paths())


def test_same_worker_cannot_supply_two_independent_witness_donors():
    rs=[record('A',SQUARE)]
    _,event,D,ix=banks(rs)
    assert event.witness(ix[('A',0)],ix[('A',1)],'pair',179,D)['status']=='same_person'


def test_completed_finite_matrix_has_no_signature_mismatches():
    path=HERE/'results/verification.json'
    if not path.exists():pytest.skip('run the bounded experiment before this artifact check')
    v=json.loads(path.read_text())
    assert v['total_variant_settings']==504 and v['nonbaseline_invariance_comparisons']==432
    assert v['invariance_mismatches']==[] and v['unresolved_event_domains']==0
    assert v['source_files_unchanged'] and not v['identity_or_vote_updates_performed']
