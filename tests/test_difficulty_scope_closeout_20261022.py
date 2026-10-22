import pandas as pd
from tools.thesis_main.analysis.difficulty_scope_closeout_20261022 import direction_counts, target_relation


def test_unknown_target_is_not_same_or_different_scope():
    assert target_relation(None, 'target') == 'missing_identity'
    assert target_relation('reference', None) == 'missing_identity'
    assert target_relation('target', 'target') == 'same_target'
    assert target_relation('other', 'target') == 'different_target'


def test_missing_outcome_does_not_enter_direction_denominator():
    s = direction_counts(pd.Series([-1., 2., 0., None]))
    assert s == dict(images_total=4, images_observed=3, images_missing=1,
                     negative=1, positive=1, tied=1)
