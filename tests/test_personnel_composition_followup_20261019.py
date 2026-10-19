import pandas as pd
import pytest

from tools.thesis_main.analysis.personnel_composition_followup_20261019 import building_mean, validate_event


def test_building_weights_and_missing_are_separate():
    rows = pd.DataFrame({'building': ['a', 'a', 'a', 'b'],
                         'pool_id': ['x', 'x', 'y', 'z'],
                         'value': [0., 20., None, 30.]})
    assert building_mean(rows, 'value') == 20.
    assert rows.value.notna().sum() == 3


def test_actual_background_and_class_composition():
    event = {'k': 3, 'm': 1, 'A_workers': ['x', 'y', 'a'],
             'B_workers': ['x', 'y', 'b'], 'C_workers': ['x', 'y', 'c'],
             'core_workers': ['x', 'y']}
    labels = {'x': 'low', 'y': 'high', 'a': 'high', 'b': 'high', 'c': 'low'}
    validate_event(event, labels)
    with pytest.raises(ValueError):
        validate_event(dict(event, B_workers=['x', 'b', 'b']), labels)
    with pytest.raises(ValueError):
        validate_event(dict(event, B_workers=['x', 'y', 'c']), labels)
    with pytest.raises(ValueError):
        validate_event(dict(event, C_workers=['x', 'y', 'unknown']), labels)
    with pytest.raises(ValueError):
        validate_event(dict(event, core_workers=['x', 'a']), labels)
