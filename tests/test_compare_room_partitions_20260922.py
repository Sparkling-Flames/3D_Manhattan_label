import pandas as pd
import pytest

from tools.thesis_main.analysis.compare_room_partitions_20260922 import align_predictions


def test_room_comparison_requires_identical_targets_and_sources():
    old = pd.DataFrame([dict(variant='raw', cut=25.6, metric='core3_mass', kind='comparable_same',
        image_id='i', building='b', family='r', N=8, source_codes='j', source_N='8',
        outcome_exposed=False, value=.5)])
    new = old.copy()
    new['value'] = .75
    assert len(align_predictions(old, new)) == 1  # Measuring a changed target is explicit.
    with pytest.raises(ValueError):
        align_predictions(old, new.iloc[:0])
    new['source_codes'] = 'other'
    with pytest.raises(ValueError):
        align_predictions(old, new)
