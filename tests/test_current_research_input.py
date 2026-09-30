"""最终数据接入不改变裁决、坐标和点身份。"""
from collections import Counter

import pytest

from tools.thesis_main.data_prep import materialize_current_research_input as m


def test_current_input_roundtrip_and_boundaries():
    d = m.load_current_input()
    source = m.indexed(m.read(m.SOURCE)['objects'], 'object_id')
    objects = m.indexed(d['objects'], 'object_id')
    assert set(source) == set(objects)
    assert d['summary']['objects'] == dict(annotation=3152, gt_original=259, gt_manual_revision=30)
    assert d['summary']['cleaning'] == dict(retained=2923, retained_pending=11, excluded_by_review=85, historical_not_accepted=133)
    assert d['summary']['borrowed_annotations'] == 2
    assert d['summary']['duplicate_groups'] == 12
    assert Counter(i['population'] for i in d['images']) == dict(research_annotation_image=259, manual_gt_reference_only=2)
    assert sum(o['ring_confirmed'] for o in objects.values()) == 1295
    assert objects['dd72228423710274']['point_labels'] == source['dd72228423710274']['point_labels']
    assert objects['8f2f8f8bfdaec3360646']['cleaning_disposition'] == 'retained'
    assert objects['new_93_3587_7182_W010']['geometry']['status'] == 'representation_limited'
    assert not objects['new_95_3660_7273_W034']['independent_vote_eligible']
    assert not objects['new_94_3635_6925_W031']['independent_vote_eligible']
    for oid, o in objects.items():
        for k in ('preprocessed_points', 'before_preprocessing_points', 'links_zero_based', 'point_labels', 'original_export_indices'):
            assert o[k] == source[oid][k]
        assert o['method_evaluability'] == 'not_assessed_per_method'
        if o['preprocessing_status'] == 'ready':
            assert o['points_1024x512'] == [o['preprocessed_points'][i] for i in o['ordered_source_point_indices']]
            assert sorted(o['ordered_source_point_indices']) == list(range(len(o['point_labels'])))
            assert o['matterport_links_zero_based'] == [[i, i + 1] for i in range(0, len(o['point_labels']), 2)]
        else:
            assert o['points_1024x512'] is None
        if not o['ring_confirmed']:
            assert o['order_record'] is None
        if o['object_kind'] == 'annotation':
            assert o['main_quality_gate']['status'] == o['worker_quality_gate']
            if o['cleaning_disposition'] != 'retained':
                assert not o['independent_vote_eligible']


def test_reject_bad_inputs():
    with pytest.raises(ValueError, match='duplicate_key'):
        m.indexed([{'id': 'same'}, {'id': 'same'}], 'id')
    with pytest.raises(ValueError, match='invalid_boolean'):
        m.typed({'b': 'unknown'}, bool_fields=('b',))
