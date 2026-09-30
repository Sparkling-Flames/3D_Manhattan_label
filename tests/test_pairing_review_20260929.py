from tools.thesis_main.analysis.build_pairing_review_20260929 import OUT, ROOT, read


def test_pairing_sources_preserve_pre_average_points_and_scope():
    import json
    data=json.loads((OUT/'data.js').read_text(encoding='utf-8').removeprefix('window.PAIRING_DATA=').removesuffix(';'))
    source={o['object_id']:o for o in read(OUT/'source_objects.json')['objects']}
    assert len(data['cases'])==len(source)==34 and len(data['images'])==22
    assert sum(len(r['points'])%2 for r in data['cases'])==3
    for r in data['cases']:
        o=source[r['object_id']]
        assert r['points']==o['before_preprocessing_points'] and r['labels']==o['point_labels']
        assert r['initial_pairs']==(o['links_zero_based'] or [])
    page=(OUT/'index.html').read_text(encoding='utf-8')
    assert 'order_studio' not in page and '只配对，不排序' in page
    assert '只修正有问题的点对' in page and '本图检查完成' in page
    assert '允许局部或空集合' in read(OUT/'field_contract.json')['pairs']
