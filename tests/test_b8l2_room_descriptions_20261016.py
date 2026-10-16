import pytest

from tools.thesis_main.analysis.b8l2_room_descriptions_20261016 import build_room_descriptions


def fixture():
    def candidate(name, images):
        return dict(candidate_id=name,image_ids=images,source_group_codes=[name],physical_same_supported=True,
                    comparable_for_prediction=True,oos_pending=False,review_state='explicit_confirmed')
    registry=dict(source='frozen registry',groups=[],candidates=[candidate('G1',['a','b']),candidate('G2',['b','c'])],images=[])
    bundle=dict(data=dict(room_registry=registry))
    records=[]
    for oid,image,worker,score,time in [('1','a','w',0.,10.),('2','a','v',100.,20.),
                                        ('3','b','w',100.,None),('4','c','w',80.,40.)]:
        records.append(dict(object_id=oid,image_id=image,image_code=image,worker_id=worker,condition='manual',
                            analysis_layer='ordinary_current',B8L2=score,active_time_seconds=time,
                            target_matched_time_seconds=time,room_id='G999',pool_analysis_eligible=True))
    return records,bundle


def test_group_weights_unique_workers_and_joint_missing_denominator():
    records,bundle=fixture(); result=build_room_descriptions(records,bundle)
    group=next(row for row in result['room_group_summary'] if row['group_id']=='candidate:G1')
    assert group['B8L2_mean']==pytest.approx(200/3)
    assert group['B8L2_image_equal_mean']==75
    assert group['n_source_workers']==2
    assert group['quality_source_time_n']==2
    assert group['group_kind']=='registered_relation_group'
    views=[r for r in result['room_group_views'] if r['group_id']=='candidate:G1']
    assert {r['image_id'] for r in views}=={'a','b'}


def test_overlapping_groups_do_not_create_transitive_pair_or_physical_room():
    records,bundle=fixture(); result=build_room_descriptions(records,bundle)
    pairs=result['room_direct_pair_registry']
    assert {tuple(row['image_ids']) for row in pairs}=={('a','b'),('b','c')}
    assert all(not row['physical_room_identity_certified'] for row in result['room_group_registry'])
    memberships=result['room_group_memberships']
    assert all(row['n_registered_candidate_groups']==2 for row in memberships if row['image_id']=='b')
    assert not any(row['group_id']=='G999' for row in result['room_group_registry'])


def test_conditions_layers_and_worker_multi_view_remain_separate():
    records,bundle=fixture()
    records.append(dict(records[0],object_id='5',condition='semi',B8L2=40.))
    records.append(dict(records[0],object_id='6',analysis_layer='special_or_pending_separate',B8L2=None))
    result=build_room_descriptions(records,bundle)
    groups=[r for r in result['room_group_summary'] if r['group_id']=='candidate:G1']
    assert len(groups)==3
    worker=next(r for r in result['room_worker_groups'] if r['group_id']=='candidate:G1' and r['worker_id']=='w'
                and r['condition']=='manual' and r['analysis_layer']=='ordinary_current')
    assert worker['n_source_workers']==1 and worker['n_source_images']==2
