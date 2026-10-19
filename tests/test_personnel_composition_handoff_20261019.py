import pytest
from tools.thesis_main.analysis.prepare_personnel_composition_handoff_20261019 import validate_pool, class_counts


def test_pool_requires_frozen_points_reference_and_quality():
    row = dict(object_id='o', worker_id='w', image_id='i', reference_id='r', quality_usable=True,
               points_1024x512=[[1, 2]], B8L2=70., D10=71.)
    pool = dict(meta=dict(image_id='i', reference_id='r'),
                records=[dict(object_id='o', worker_id='w', points=[[1, 2]], B8L2=70., D10=71.)])
    validate_pool(pool, {'o': row})
    for key, value in [('reference_id', 'other'), ('points_1024x512', [[2, 2]]), ('B8L2', 0.), ('quality_usable', False)]:
        with pytest.raises(ValueError):
            validate_pool(pool, {'o': dict(row, **{key: value})})


def test_unknown_is_not_a_class_and_duplicate_people_are_rejected():
    assert class_counts([('w1', 'C1'), ('w2', 'unknown'), ('w3', None)]) == {'C1': ['w1'], 'unknown': ['w2', 'w3']}
    with pytest.raises(ValueError):
        class_counts([('w1', 'C1'), ('w1', 'C2')])
