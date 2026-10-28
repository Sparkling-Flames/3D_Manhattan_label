import pandas as pd
import pytest

from tools.thesis_main.analysis.summarize_admitted_space_descriptive_20261029 import image_equal


def test_target_then_image_weighting_and_missing():
    data = pd.DataFrame([
        {'condition': 'manual', 'image_id': 'i1', 'reference_id': 'a', 'B8L2': 10},
        {'condition': 'manual', 'image_id': 'i1', 'reference_id': 'a', 'B8L2': 20},
        {'condition': 'manual', 'image_id': 'i1', 'reference_id': 'b', 'B8L2': 45},
        {'condition': 'manual', 'image_id': 'i2', 'reference_id': 'a', 'B8L2': 80},
        {'condition': 'manual', 'image_id': 'i2', 'reference_id': 'b', 'B8L2': None},
    ])
    result = image_equal(data, ['condition'], 'B8L2').iloc[0]
    assert result.B8L2 == pytest.approx(55)
    assert (result.B8L2_records, result.B8L2_targets, result.B8L2_images) == (4, 3, 2)


def test_personnel_image_weighting_preserves_unequal_support():
    data = pd.DataFrame([
        {'worker_id': 'w1', 'image_id': 'i1', 'reference_id': 'a', 'D10': 20},
        {'worker_id': 'w1', 'image_id': 'i1', 'reference_id': 'b', 'D10': 60},
        {'worker_id': 'w1', 'image_id': 'i2', 'reference_id': 'a', 'D10': 80},
        {'worker_id': 'w2', 'image_id': 'i1', 'reference_id': 'a', 'D10': None},
    ])
    result = image_equal(data, ['worker_id'], 'D10')
    assert result.worker_id.tolist() == ['w1']
    assert result.iloc[0].D10 == pytest.approx(60)
