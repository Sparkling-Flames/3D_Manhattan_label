import copy
import pytest
from tools.thesis_main.data_prep.intake_workers_v2_20261019 import audit,geometry_checks,preprocess_record

def record():
    return dict(annotation_id=1,image_id='i',image_code='I',worker_id='W100',condition='manual',scope='in_scope',
        points_1024x512=[[10,100],[11,400],[200,100],[201,400],[600,100],[601,400],[900,100],[901,400]],
        matterport_links_zero_based=[[0,1],[2,3],[4,5],[6,7]],boundary_next_pair_indices=[1,2,3,0],
        geometry_status='valid',active_time_seconds=10)

def test_excluded_same_task_never_becomes_second_retained_vote():
    r=record();e=copy.deepcopy(r);e.update(annotation_id=2,exclusion_reason='user_review')
    rows=audit([r],[e],{'i':'I'})
    assert rows[1]['disposition']=='excluded_by_user' and rows[1]['matching_retained_annotation_id']==1
    assert rows[0]['quality_status']=='not_scored_reference_and_eligibility_pending'
    with pytest.raises(AssertionError):audit([r,e],[],{'i':'I'})

def test_pair_coverage_and_single_ring_required_but_points_never_edited():
    r=record();before=copy.deepcopy(r);flags,gap=geometry_checks(r)
    assert flags==[] and gap==1 and r==before
    r['boundary_next_pair_indices']=[1,0,3,2]
    assert 'not_single_boundary_cycle' in geometry_checks(r)[0]
    r['matterport_links_zero_based'][-1]=[0,1]
    assert 'incomplete_or_repeated_pairing' in geometry_checks(r)[0]


def test_shared_x_reuses_periodic_midpoint_and_preserves_y_identity_and_input():
    r=record();r['points_1024x512'][:2]=[[1022,100],[2,400]];before=copy.deepcopy(r)
    out=preprocess_record(r)
    assert out['preprocessing_status']=='ready'
    assert out['preprocessed_points'][:2]==[[0,100],[0,400]]
    assert out['preprocessed_points'][2:4]==[[200.5,100],[200.5,400]]
    assert [p[1] for p in out['preprocessed_points']]==[p[1] for p in r['points_1024x512']]
    assert r==before
    again=copy.deepcopy(r);again['points_1024x512']=out['preprocessed_points']
    assert preprocess_record(again)['preprocessed_points']==out['preprocessed_points']


@pytest.mark.parametrize('issue',['odd','unverified','antipodal','triangle'])
def test_preprocessing_does_not_guess_pairs_or_change_exclusion(issue):
    r=record();r['exclusion_reason']='user_review'
    if issue=='odd':r['points_1024x512'].append([44,200])
    if issue=='unverified':r['geometry_status']='pairing_unverified'
    if issue=='antipodal':r['points_1024x512'][:2]=[[0,100],[512,400]]
    if issue=='triangle':
        r['points_1024x512']=r['points_1024x512'][:6]
        r['matterport_links_zero_based']=r['matterport_links_zero_based'][:3]
        r['boundary_next_pair_indices']=[1,2,0];r['geometry_status']='below_four_pairs'
    before=copy.deepcopy(r);out=preprocess_record(r)
    assert r==before
    assert out['preprocessing_status']==('ready' if issue=='triangle' else 'blocked')
    assert (out['preprocessed_points'] is None)==(issue!='triangle')
    if issue=='triangle':
        row=audit([], [r], {'i':'I'})[0]
        assert row['disposition']=='excluded_by_user' and row['preprocessing_status']=='ready'
