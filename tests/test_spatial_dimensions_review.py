import copy
import pytest
from tools.thesis_main.analysis.build_spatial_dimensions_review import merge_dimensions, attach_oos, apply_chat_review


def test_dimensions_preserve_human_and_oos_scope():
    source = [dict(image_id='a', spatial_classification={'coarse_type':'厨房与用餐'},
                   review_history=[{'stage':'initial','values':{'note':'原评论'}}]), dict(image_id='b')]
    before = copy.deepcopy(source)
    proposal = dict(functional_regions=['厨房','用餐'], main_space='厨房为主',
                    relations=[dict(region_a='厨房',region_b='用餐',relation='无明显建筑分隔',evidence='连续围合')],
                    relation_scope_note='',reason='沿用记录',review_basis='carried_visual_record',
                    evidence_refs=['review_a.json'],needs_original_followup=False,
                    human_comparison='互补',human_conflicts=[],uncertainties=[])
    rows = merge_dimensions(source,[dict(image_id=i,**proposal) for i in ['a','b']])
    assert source==before and rows[0]['review_history']==before[0]['review_history']
    assert rows[0]['spatial_classification']['coarse_type']=='厨房与用餐'
    assert not rows[0]['new_spatial_review']['human_conflicts']
    events=[dict(event_id='g',state='局部待定位',image_ids=[],context_image_ids=['a','b']),
            dict(event_id='i',state='疑似',image_ids=['a'],context_image_ids=['a','b'])]
    attach_oos(rows,events)
    assert rows[0]['oos_review']['image_event_ids']==['i']
    assert rows[1]['oos_review']['image_event_ids']==[]
    assert rows[1]['oos_review']['context_event_ids']==['g']
    with pytest.raises(ValueError,match='覆盖'):
        merge_dimensions(source,[dict(image_id='a',**proposal)])


def test_chat_confirmation_preserves_history_and_limits_oos():
    rows=[dict(image_id=i,building='wc2JMjhGNzB',spatial_classification={'coarse_type':'起居与休闲'},
               new_spatial_review={'human_conflicts':['原争议']}) for i in ['a','b','c']]
    events=[dict(event_id='old',state='明确OOS',image_ids=['b'],context_image_ids=['b'])]
    apply_chat_review(rows,events,dict(source='用户对话',decisions=[dict(image_id='a',coarse_type='通行与连接',basis='用户认可')],
        oos_image_ids=['b'],oos_quote='这个疑似oos'))
    assert rows[0]['spatial_classification']['coarse_type']=='起居与休闲'
    assert rows[0]['current_coarse_review']['value']=='通行与连接'
    assert rows[0]['resolved_spatial_conflicts']==['原争议'] and not rows[0]['new_spatial_review']['human_conflicts']
    assert rows[1]['oos_review']['latest_explicit_opinion']=='疑似'
    assert rows[1]['oos_review']['image_event_ids']==['old','chat:20260913:wc-suspected']
    assert rows[1]['new_spatial_review']['human_conflicts']==['原争议']
    assert not rows[2]['oos_review']['image_event_ids']
