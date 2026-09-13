import copy
import pytest
from tools.thesis_main.analysis.summarize_open_layout_recheck import merge


def test_review_requires_coverage_and_keeps_human_classification():
    old=dict(image_id='a',building='b',number=1,path='a.png',group_codes=[],
             spatial_classification={'coarse_type':'卧室'},spatial_ai_proposal={'coarse_type':'开放复合空间'},
             all_user_notes=[],spatial_field_sources={'coarse_type':'人工'})
    registry={'images':[old]};before=copy.deepcopy(registry)
    row=dict(image_id='a',verdict='支持开放复合',reason='原图两区连续',functions=['起居','用餐'],view_basis='original')
    result=merge(registry,[{'rows':[row]}],{'rows':[]})
    assert registry==before and result[0]['prior_adopted']['coarse_type']=='卧室'
    assert not result[0]['adopted_classification_changed']
    with pytest.raises(ValueError,match='全量复核'):
        merge(registry,[{'rows':[row,row]}],{'rows':[]})
    row['view_basis']='contact_sheet'
    with pytest.raises(ValueError,match='原图复核'):
        merge(registry,[{'rows':[row]}],{'rows':[]})
