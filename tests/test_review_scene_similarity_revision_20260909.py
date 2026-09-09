import pytest
from tools.thesis_main.analysis.review_scene_similarity_revision_20260909 import source_identity, pair_summary, replay_pairs


def test_panorama_identity_not_source_view_count():
    uid='a'*32
    assert source_identity(f'./data/mp_sb/houseA/{uid}.jpg','pano') == f'houseA_{uid}'
    assert {source_identity(f'/data/houseA/undistorted_color_images/{uid}_i1_{i}.jpg','single') for i in range(6)} == {f'houseA_{uid}'}
    assert source_identity(f'/data/houseB/undistorted_color_images/{uid}_i1_0.jpg','single') != f'houseA_{uid}'
    with pytest.raises(ValueError):source_identity(f'/houseA/wrong/{uid}.jpg','single')


def test_pair_weighting_does_not_turn_replicates_into_images():
    records=[]
    for a,b,d,reps in [('A','B',0,200),('A','B',0,200),('A','C',.9,1)]:
        records.append(dict(building_relation='different',class_relation='same',left_building=a,right_building=b,
            left_image=a,right_image=b,curve_distance=d,shared_replicates=reps))
    result=pair_summary(records)[0]
    assert result['image_pairs']==3 and result['building_blocks']==2
    assert result['pair_equal_mean']==pytest.approx(.3)
    assert result['block_equal_mean']==pytest.approx(.45)
    assert result['pair_replicate_records']==401


def test_shared_replicates_averaged_before_curve_distance():
    data=[]
    for context,values in [('a',[0,.2]),('b',[.2,0])]:
        for rep,value in enumerate(values):
            data.append(dict(context_key=context,image_id=context,building_id=context,replicate=rep,k=3,value=value))
    result=replay_pairs(data,{'a':1,'b':1})[0]
    assert result['curve_distance']==0
    assert result['shared_replicates']==2
    with pytest.raises(ValueError):replay_pairs(data+[data[0]],{})
