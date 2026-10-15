import pandas as pd
import pytest

from tools.thesis_main.analysis.descriptive_statistics_20261015 import describe, attach_scores


def test_describe_keeps_missing_and_image_equal_weight():
    frame = pd.DataFrame({'image_id': ['a', 'a', 'b', 'c'],
                          'worker_id': ['1', '2', '1', '3'],
                          'reference_id': ['ra', 'ra', 'rb', None],
                          'WQ': [10., 30., 90., None]})
    result = describe(frame, 'WQ')
    assert result['n_records'] == 4
    assert result['n_valid'] == 3 and result['n_missing'] == 1
    assert result['mean'] == pytest.approx(130 / 3)
    assert result['image_equal_mean'] == 55
    assert result['median'] == 30
    assert result['n_valid_images'] == 2
    assert describe(frame.iloc[3:], 'WQ')['mean'] is None


def test_score_join_rejects_reference_drift_and_duplicates():
    common = dict(record_id='r', object_id='o', image_id='i', worker_id='w',
                  reference_id='ref', condition='manual', WQ='20')
    binding = pd.DataFrame([common])
    scores = pd.DataFrame([{**common, 'Q_A10': '22', 'Q_B8L2': '23', 'Q_WQ': '20', 'Q_IoU3D': '30'}])
    assert attach_scores(binding, scores).iloc[0].B8L2 == 23
    with pytest.raises(AssertionError, match='reference_id'):
        attach_scores(binding, scores.assign(reference_id='different'))
    with pytest.raises(pd.errors.MergeError):
        attach_scores(binding, pd.concat([scores, scores]))
