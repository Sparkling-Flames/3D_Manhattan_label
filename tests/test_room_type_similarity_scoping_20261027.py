import pandas as pd
import pytest

from tools.thesis_main.analysis.room_type_similarity_scoping_20261027 import (
    make_frame, ordinary_quality, image_quality,
)


def record(i, label=None, **changes):
    row = dict(object_id=f'o{i}', image_id=f'i{i}', image_code=f'c{i}', worker_id=f'w{i}',
               building_id='b', condition='manual', quality_usable=True,
               quality_use='ordinary_primary', B8L2=80., D10=81., current_class='简单',
               is_oos=False, is_doorway=False,
               image_evidence={'room_spatial_classification': {'coarse_type': label}})
    row.update(changes)
    return row


def metadata(i, label):
    return dict(image_id=f'i{i}', room_spatial_classification={'coarse_type': label},
                room_classification_sources={'coarse_type': 'test'})


def test_room_type_is_separate_from_doorway_oos_and_unknown():
    rows = [record(1), record(2, '无法判断'), record(3, '卫浴', is_doorway=True),
            record(4, '卫浴', is_oos=True, is_doorway=True),
            record(5, '卫浴', quality_usable=False)]
    frame = make_frame(rows, [metadata(1, None), metadata(2, '无法判断')]
                       + [metadata(i, '卫浴') for i in (3, 4, 5)])
    assert frame.room_type_display.tolist() == ['未记录', '无法判断', '卫浴', '卫浴', '卫浴']
    assert frame.layer.tolist() == ['ordinary', 'ordinary', 'doorway', 'oos', 'ordinary']
    assert ordinary_quality(frame).object_id.tolist() == ['o1', 'o2']
    with pytest.raises(AssertionError, match='room_label_drift'):
        make_frame([record(1, '卫浴')], [metadata(1, '卧室')])


def test_image_equal_mean_does_not_overweight_more_annotated_image():
    frame = pd.DataFrame(dict(condition=['manual'] * 4, image_id=['a', 'a', 'a', 'b'],
        image_code=['a', 'a', 'a', 'b'], building_id=['x'] * 4,
        room_type_display=['卫浴'] * 4, current_class=['简单'] * 4,
        object_id=['1', '2', '3', '4'], worker_id=['w1', 'w2', 'w3', 'w1'],
        B8L2=[100., 100., 100., 0.], D10=[100., 100., 100., 0.]))
    means = image_quality(frame)
    assert means.Q_mean.mean() == 50.
    assert frame.B8L2.mean() == 75.
