import pytest
import json

from tools.thesis_main.analysis.difficulty_consensus_20261006 import scene_group, summarize


def test_returned_review_keeps_notes_and_checks_image_identity():
    from tools.thesis_main.analysis.update_difficulty_review_20261006 import apply_review, OUT
    payload=json.loads((OUT/'user_review.json').read_text(encoding='utf-8-sig'))
    identities={r['image_code']:r['image_id'] for r in payload['decisions']}
    meta={code:dict(difficulty='未记录',oos_status='not_recorded',doorway_status='not_recorded') for code in identities}
    result=apply_review(meta,payload,identities)
    assert result['yqstnuAEVhm-34']['difficulty']=='简单'
    assert result['yqstnuAEVhm-34']['review_note']=='也存在不同的标注范围(较少)'
    assert result['yqstnuAEVhm-34']['scene']=='clear'
    assert meta['yqstnuAEVhm-34']['difficulty']=='未记录'
    identities['yqstnuAEVhm-34']='wrong-image'
    with pytest.raises(ValueError,match='图片身份不匹配'):
        apply_review(meta,payload,identities)


def test_scene_axes_keep_overlap_pending_and_unknown_separate():
    assert scene_group(dict(oos_status='confirmed',doorway_status='difficult')) == 'oos_and_doorway'
    assert scene_group(dict(oos_status='not_recorded',doorway_status='difficult')) == 'doorway_difficult'
    assert scene_group(dict(oos_status='confirmed',doorway_status='none')) == 'oos'
    assert scene_group(dict(oos_status='pending',doorway_status='not_recorded')) == 'oos_pending'
    assert scene_group(dict(oos_status='not_recorded',doorway_status='annotatable')) == 'doorway_annotatable'
    assert scene_group(dict(oos_status='not_recorded',doorway_status='not_recorded')) == 'unflagged'


def test_difficulty_comparison_holds_images_fixed_and_excludes_special_scenes():
    meta={i:dict(difficulty='简单',building=b,scene=scene) for i,b,scene in
          [('a','b1','unflagged'),('b','b1','unflagged'),('c','b2','clear'),('d','b2','oos')]}
    rows=[dict(image=i,n=n,k=k,method='mv50',distance=v) for i,n,v in
          [('a',8,.1),('b',8,.3),('c',4,.9),('d',8,1.)] for k in range(1,n+1)]
    out=summarize(rows,meta,8)
    all_rows=[r for r in out if r['scope']=='all']
    assert len(all_rows)==8
    assert {r['images'] for r in all_rows}=={'a|b'}
    assert all(r['mean_distance']==pytest.approx(.2) for r in all_rows)
