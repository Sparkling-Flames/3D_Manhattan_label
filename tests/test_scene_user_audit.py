import copy

import pytest

from tools.thesis_main.analysis.build_scene_user_audit import assemble, render


def test_audit_preserves_source_and_rejects_incomplete_or_invalid_join():
    raw = [dict(image_id='b_abc', building='b', split='valid', path='data/a.png', number=1)]
    user = dict(schema='scene_user_review_v2', saved_at='now', rows=[dict(image_id='b_abc', building='b', split='valid', user_room='r1', user_type='<自定义>', user_doorway='确认', user_artifact='未见明显异常', user_status='已复核', user_note='test')])
    part = dict(reviewed=[dict(image_id='b_abc', doorway_assessment='更像非门洞', reason='墙端', original_viewed=True)], issues=[])
    before = copy.deepcopy(user)
    result = assemble(user, raw, [part])
    assert user == before
    assert result['source_user'] == before
    assert result['cases'][0]['images'][0]['user'] == user['rows'][0]
    assert result['summary']['dispute_cases'] == 1
    assert '&lt;自定义&gt;' in render(result)
    assert 'data-field="user_room"' in render(result)
    assert 'user_audit_status' in render(result)
    assert 'source.rows.map' in render(result)
    for invalid in [dict(reviewed=[], issues=[]), dict(reviewed=[{**part['reviewed'][0], 'image_id':'missing'}], issues=[])]:
        with pytest.raises(ValueError):
            assemble(user, raw, [invalid])
