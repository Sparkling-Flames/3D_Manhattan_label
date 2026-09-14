import pytest

from tools.thesis_main.analysis.image_portrait.build_bundle import make_folds, unique, validate_folds


def test_identity_and_conservative_room_folds():
    images = [dict(image_id=i, building=b) for i, b in [('a','X'),('b','X'),('c','X'),('d','Y'),('e','Y')]]
    groups = [dict(image_ids=['a','b'], relation_status='supported'),
              dict(image_ids=['d','e'], relation_status='supported'),
              dict(image_ids=['b','c'], relation_status='pending')]
    rooms, folds = make_folds(images, groups)
    assert make_folds(images, groups) == (rooms, folds)
    assert not any(f['test'] == ['a'] for f in folds)
    room = next(f for f in folds if f['design'] == 'leave_supported_room_conservative')
    assert room['test'] == ['d','e'] and room['train'] == ['a','b','c']
    with pytest.raises(ValueError, match='duplicate'):
        unique(images + images[:1], 'image_id')
    bad = dict(room, train=['a','d'])
    with pytest.raises(ValueError, match='overlapping'):
        validate_folds(images, [bad])
