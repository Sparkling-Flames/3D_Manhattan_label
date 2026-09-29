"""Research runner invariants; these are not semantic correctness tests."""
import copy
import numpy as np
import pytest

from tools.label_studio.panorama_studio.geometry import project_pixel
from tools.thesis_main.analysis.research_round_20260929 import (
    reconstruct, visible_wall_mask, summarize_replays, validate_panel, candidate_geometry,
)


def record(points, identity="A1", heights=2.7):
    heights = np.broadcast_to(heights, (len(points),))
    paired = [[project_pixel([x, h-1, z], 1024, 512),
               project_pixel([x, -1, z], 1024, 512)] for (x,z),h in zip(points,heights)]
    return dict(id=identity, worker=identity, condition="manual", points=np.array(paired).reshape(-1,2).tolist(),
                cleaning="retained", independent=True, consensus_eligible=True, quality_candidate=True,
                order_status="human_confirmed", geometry_status="surface_valid")


SQUARE = [[-2,-2],[2,-2],[2,2],[-2,2]]


def test_explicit_ring_preserved_and_collinear_stop_not_deleted():
    a=record(SQUARE); b=record([[-2,-2],[0,-2],[2,-2],[2,2],[-2,2]])
    original=copy.deepcopy(b)
    ga,gb=reconstruct(a),reconstruct(b)
    np.testing.assert_allclose(ga['floor'], SQUARE, atol=1e-10)
    assert len(gb['floor'])==5 and b==original
    assert np.array_equal(visible_wall_mask(ga,128,64),visible_wall_mask(gb,128,64))
    assert candidate_geometry(b)['pair_count']==5


def test_order_matters_and_invalid_is_not_repaired():
    a=record([SQUARE[i] for i in [0,2,1,3]])
    g=reconstruct(a)
    assert g['status']=='unavailable' and 'invalid_footprint' in g['reason']
    with pytest.raises(ValueError):visible_wall_mask(g,128,64)


def test_rotation_reversal_and_height_effect():
    a=record(SQUARE);b=record(SQUARE[::-1]);c=record(SQUARE,heights=3.5)
    assert np.array_equal(visible_wall_mask(reconstruct(a),128,64),visible_wall_mask(reconstruct(b),128,64))
    assert not np.array_equal(visible_wall_mask(reconstruct(a),128,64),visible_wall_mask(reconstruct(c),128,64))


def test_replay_missing_votes_ties_and_no_mutation():
    group=[record(SQUARE,str(i)) for i in range(3)]
    masks={'0':np.array([[1,0],[1,0]],bool),'1':np.array([[0,1],[0,1]],bool)}
    before={k:v.copy() for k,v in masks.items()}
    refs={'original':np.ones((2,2),bool)}
    rows=summarize_replays(group,masks,refs,seeds=8)
    full={r['method']:r for r in rows if r['k']==3}
    assert full['mv50']['used_k_mean']==2 and full['mv50']['iou_mean']==1
    assert full['mv_strict']['iou_mean']==0 and full['medoid']['iou_mean']==.5
    for key in masks:assert np.array_equal(masks[key],before[key])
    other=summarize_replays(group,masks,{'original':np.zeros((2,2),bool)},seeds=8)
    assert [(x['k'],x['method'],x['change_mean']) for x in rows]==[(x['k'],x['method'],x['change_mean']) for x in other]


def test_no_duplicate_independent_person_and_no_missing_eligibility():
    a=record(SQUARE);b=copy.deepcopy(a);b['id']='B'
    image=dict(code='building-01',building='building',scene={},annotations=[a,b],references=[])
    panel=dict(schema='layout_research_panel_v1',images=[image])
    with pytest.raises(ValueError,match='duplicate_independent'):validate_panel(panel)
    b['independent']=False
    validate_panel(panel)
    del b['consensus_eligible']
    with pytest.raises(ValueError,match='missing_record_fields'):validate_panel(panel)


def test_wrong_hemisphere_and_height_outlier_are_visible():
    a=record(SQUARE);a['points'][0][1]=260
    assert reconstruct(a)['status']=='unavailable'
    b=record(SQUARE,heights=[2.7,2.7,2.7,8.])
    g=candidate_geometry(b)
    assert g['height_relative_spread']>1 and g['height_mad_relative']==pytest.approx(0,abs=1e-12)


def test_public_projection_keeps_reference_only_images_and_no_private_fields():
    import json
    from tools.thesis_main.data_prep.project_public_research_20260929 import project
    im=dict(image_code='B-01',building_id='B',room_id='',annotations=1,population='research_annotation_image',
            oos_status='not_recorded',doorway_status='not_recorded',coverage='incomplete',comment='PRIVATE_CANARY')
    o=dict(object_id='PRIVATE_OBJECT',object_kind='annotation',image_code='B-01',worker_id='PRIVATE_WORKER',
           points_1024x512=record(SQUARE)['points'],order_status='confirmed',geometry={'status':'surface_valid','issues':[]},
           ordered_source_point_indices=list(range(8)),ordered_source_point_labels=[],preprocessing_status='ready',
           ring_confirmed=True,main_consensus_gate={'status':'main_candidate'},main_quality_gate={'status':'candidate_pending_geometry'},
           condition='manual',cleaning_disposition='retained',independent_vote_eligible=False,
           independent_vote_reasons=['borrowed_points_not_independent_complete_response'],scene_category='ordinary',
           borrowed_point_provenance=[{'private':'PRIVATE_CANARY'}])
    ref=copy.deepcopy(o);ref.update(object_kind='gt_manual_revision',object_id='PRIVATE_GT',image_code='B-02')
    refim=dict(im,image_code='B-02',population='reference_only',annotations=0)
    del refim['oos_status']
    src=dict(objects=[o,ref],images=[im,refim],schema='integration',contract_version='v1',coordinate_frame='1024x512',preprocessing='shared_x')
    panel,mapping=project(src)
    assert 'PRIVATE_' not in json.dumps(panel)
    assert mapping['workers']['PRIVATE_WORKER']=='P001'
    assert len(panel['images'])==2 and len(panel['images'][1]['references'])==1
    assert not panel['images'][0]['annotations'][0]['independent']
