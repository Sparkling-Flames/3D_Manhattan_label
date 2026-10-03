import copy
import json

import pytest

from tools.thesis_main.analysis.global_pair_consensus_20261004 import (
    build_global_pair_consensus, build_global_pair_consensuses,
)


def record(worker, xs, offset=0):
    return dict(id='R'+str(worker), worker='P'+str(worker),
                points=[[float((x+offset)%1024), y] for x in xs for y in (120., 390.)],
                source_pair_indices=list(range(len(xs))), order_status='human_confirmed', ring_confirmed=True)


def test_all_people_cross_point_counts_majority_tie_and_provenance():
    # One extra corner is present in exactly half; all four people share the other corners.
    rows=[record(1,[128,384,640,896]),record(2,[128,256,384,640,896]),
          record(3,[128,384,640,896]),record(4,[128,256,384,640,896])]
    before=copy.deepcopy(rows)
    result=build_global_pair_consensuses(rows)
    assert rows==before
    a,b=result['mv50'],result['mv_strict']
    assert a['vote_denominator']==b['vote_denominator']==4
    assert a['candidate']['status']=='ok'
    assert a['candidate']['point_support_counts']==[4,2,4,4,4]
    assert b['candidate']['point_support_counts']==[4]*4
    assert a['candidate']['ring_confirmed'] is False
    assert a['candidate']['order_status']=='default_x_exploratory_unconfirmed'
    assert len(a['assignments'])==4
    for group in a['identity_groups']:
        assert group['support']==len({m['worker'] for m in group['members']})
        assert all(m['source_pair_index']==m['pair_index'] for m in group['members'])
    # Duplicate geometry retains independent people and votes; no whole-annotation clustering.
    assert sorted(g['support'] for g in a['identity_groups'])==[2,4,4,4,4]
    json.dumps(result,allow_nan=False)


def test_periodic_center_and_same_person_nearby_corners_do_not_merge():
    rows=[record(1,[1023,3,300,600]),record(2,[0,4,301,601])]
    result=build_global_pair_consensus(rows,threshold_deg=1.)
    assert len(result['identity_groups'])==4
    assert all(g['support']==2 for g in result['identity_groups'])
    xs=[g['center'][0][0] for g in result['identity_groups']]
    assert any(min(x,1024-x)<1 for x in xs)
    assert len(result['candidate']['points'])==8
    assert all(g['maximum_pair_angle_deg']<=1.+1e-9 for g in result['identity_groups'])


def test_invalid_record_stays_in_denominator_and_insufficient_consensus_is_explicit():
    rows=[record(1,[128,384,640,896])]
    rows += [dict(id='R'+str(i),worker='P'+str(i),points=None) for i in (2,3)]
    result=build_global_pair_consensus(rows)
    assert result['vote_denominator']==3
    assert result['candidate']['status']=='unavailable'
    assert result['candidate']['reason']=='fewer_than_three_majority_pairs'
    assert result['candidate']['points'] is None
    assert len(result['input_issues'])==2
    assert len(result['unmatched_observations'])==4
    assert all(g['support_fraction']==1/3 for g in result['identity_groups'])
    with pytest.raises(ValueError,match='duplicate_worker'):
        build_global_pair_consensus([rows[0],dict(rows[0],id='another')])


def test_complete_linkage_not_chaining_threshold_sensitivity_and_new_ring_diagnostics():
    rows=[record(i,[128,384,640,896],offset) for i,offset in enumerate([0.,6.,12.])]
    low=build_global_pair_consensus(rows,threshold_deg=2.5)
    high=build_global_pair_consensus(rows,threshold_deg=10)
    assert all(g['maximum_pair_angle_deg']<=2.5+1e-8 for g in low['identity_groups'])
    assert len(high['identity_groups'])<len(low['identity_groups'])
    # A confirmed source ring keeps its order, even if new default-x disagrees.
    crossed=record(9,[128,640,384,896])
    mixed=build_global_pair_consensus([record(1,[128,384,640,896]),crossed])
    assert mixed['candidate']['ring_confirmed'] is False
    assert mixed['ring_diagnostics']['source_ring_disagreement_count']==1
    assert mixed['assignments'][1]['source_ring_confirmed'] is True


def test_equal_x_distinct_identities_are_order_failure_not_silently_sorted():
    a=record(1,[128,384,640,896])
    b=record(2,[128,384,640,896])
    b['points'][0][1]=70.
    b['points'][1][1]=440.
    result=build_global_pair_consensus([a,b],threshold_deg=5.)
    assert result['candidate']['status']=='unavailable'
    assert result['candidate']['reason']=='ambiguous_shared_x_order'
    assert result['candidate']['points'] is None
    assert result['ring_diagnostics']['ambiguous_x_pairs']


def test_record_order_ring_rotation_and_reversal_leave_geometry_and_votes_invariant():
    rows=[record(1,[1023,3,300,600]),record(2,[0,4,301,601]),record(3,[1022,2,299,599])]
    baseline=build_global_pair_consensus(rows,threshold_deg=1.)
    changed=copy.deepcopy(rows[::-1])
    for r,order in zip(changed,([1,2,3,0],[3,2,1,0],[2,1,0,3])):
        r['points']=[p for i in order for p in r['points'][2*i:2*i+2]]
        r['source_pair_indices']=[r['source_pair_indices'][i] for i in order]
    moved=build_global_pair_consensus(changed,threshold_deg=1.)
    assert moved['candidate']['points']==baseline['candidate']['points']
    assert moved['candidate']['point_support_counts']==baseline['candidate']['point_support_counts']
    assert moved['ring_diagnostics']['edges']==baseline['ring_diagnostics']['edges']
    assert moved['correspondence_diagnostics']['competing_worker_matches']>0
    assert moved['correspondence_diagnostics']['uniqueness_established'] is False


def test_candidate_needs_ring_review_without_original_edge_majority_and_rejects_bad_geometry():
    rows=[record(i,[128,640,384,896]) for i in range(3)]
    result=build_global_pair_consensus(rows)
    assert result['candidate']['status']=='geometry_review'
    assert result['ring_diagnostics']['unsupported_edge_count']>0
    assert result['ring_diagnostics']['exact_source_ring_support']==0
    assert all(g['support']==3 for g in result['identity_groups'])
    bad=record(1,[128,384,640,896])
    for p in bad['points'][1::2]:p[1]=250.
    result=build_global_pair_consensus([bad])
    assert result['candidate']['status']=='unavailable'
    assert result['candidate']['reason'].startswith('invalid_candidate_ring:')
    assert result['candidate']['points'] is not None
    with pytest.raises(ValueError,match='missing_annotation_fields'):
        build_global_pair_consensus([{'points':None}])
