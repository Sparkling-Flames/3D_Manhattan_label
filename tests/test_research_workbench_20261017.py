import json
from tools.thesis_main.analysis.build_research_workbench_20261017 import pack_image, pack_pool, read_table


def test_geometry_requires_matching_object_target_and_scores(tmp_path):
    image = dict(image_id='i', image_code='I', original_path='photo.png', thumbnail_path='photo.png',
                 annotations=[dict(object_id='a', target_id='t', points=[[1,2]], quality={'B8L2':80.,'D10':81.}, quality_usable=True)], references=[])
    scores = {'a': dict(object_id='a', image_id='i', rescore_target_id='t', B8L2=80., D10=81., quality_usable=True)}
    assert pack_image(image,scores,tmp_path)['annotations'][0]['geometry_compatible']
    scores['a']['rescore_target_id']='other'
    result=pack_image(image,scores,tmp_path)
    assert not result['annotations'][0]['geometry_compatible']
    assert result['annotations'][0]['points'] is None
    assert result['photo_status']=='missing'


def test_saved_fusion_is_not_filled_or_reconstructed():
    pool=dict(pool_id='p', image='I', image_id='i', records=[], reference={'target_id':'t'})
    states=dict(pool_id='p',orders=[dict(path_id='r',workers=['w'])],states=[dict(subset='a',automatic={'candidate':{'status':'incomplete','points':None}},origin={})])
    out=pack_pool(pool,states)
    assert out['states'][0]['candidate']['points'] is None
    assert out['orders']==states['orders']
    assert out['reference']['target_id']=='t'


def test_display_parts_preserve_nulls_and_reject_schema_drift(tmp_path):
    (tmp_path/'part.json').write_text(json.dumps(dict(columns=['id','q'],rows=[['0001',None]])),encoding='utf-8')
    index={'tables':[dict(id='t',columns=['id','q'],row_count=1,parts=[{'path':'part.json'}])]}
    assert read_table(tmp_path,index,'t')==[{'id':'0001','q':None}]
    index['tables'][0]['columns']=['q','id']
    import pytest
    with pytest.raises(ValueError,match='columns'):read_table(tmp_path,index,'t')
