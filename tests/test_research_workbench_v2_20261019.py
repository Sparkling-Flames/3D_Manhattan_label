import pytest

from tools.thesis_main.analysis.build_research_workbench_v2_20261019 import pack_annotation, validate_objects


def test_v2_uses_final_geometry_and_preserves_missing_raw_and_floor_only():
    obj = dict(object_id='new', image_id='i', worker_id='W100', condition='manual',
               points_1024x512=[[1, 2], [1, 3]], original_export_points=None,
               before_preprocessing_points=[[0, 2], [2, 3]], ring_confirmed=False,
               cleaning_disposition='retained')
    score = dict(object_id='new', image_id='i', rescore_target_id='floor',
                 quality_usable=False, B8L2=None, full_score_state='reference_floor_only')
    result = pack_annotation(obj, score, {'floor'})
    assert result['points'] == obj['points_1024x512']
    assert result['raw_points'] is None
    assert result['before_preprocessing_points'] == obj['before_preprocessing_points']
    assert result['target_id'] == 'floor'
    assert result['quality']['B8L2'] is None
    assert result['ring_confirmed'] is False
    with pytest.raises(ValueError, match='reference'):
        pack_annotation(obj, score, set())


def test_display_requires_exact_object_inventory_not_partial_join():
    objects = [dict(object_id='a', image_id='i', object_kind='annotation')]
    validate_objects(objects, [dict(object_id='a', image_id='i')])
    with pytest.raises(ValueError, match='inventory'):
        validate_objects(objects, [])
    with pytest.raises(ValueError, match='duplicate'):
        validate_objects(objects, [dict(object_id='a'), dict(object_id='a')])
