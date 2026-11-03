"""Critical numerical contracts for the targeted human-order sensitivity update."""
import numpy as np
import pandas as pd

from tools.thesis_main.analysis.evaluate_manual_order_half_qonly_20261104 import (
    image_means, merge_endpoint, scalar_contrasts,
)


def test_hierarchical_weighting_does_not_count_replicates_as_independent_images():
    rows = []
    for background, values in [('D1', [0, 0, 0]), ('D2', [10])]:
        for value in values:
            rows.append(dict(n=14, building='building', image='image', pool_id='pool',
                             block_id='block', background_id=background, value=value))
    result = image_means(pd.DataFrame(rows), ['value'])
    assert result.iloc[0].value == 5  # Two equal backgrounds, not four equal events.


def test_missing_endpoint_preserves_pairwise_support_but_not_triple_contrast():
    result = scalar_contrasts(None, 40, 70)
    assert result['CB'] == 30
    assert np.isnan(result['BA']) and np.isnan(result['CA'])
    assert np.isnan(result['within']) and np.isnan(result['gap'])


def test_patch_preserves_team_identity_votes_and_original_annotation_time():
    old = dict(team_key='team', pool_id='pool', reference_id='reference',
               reference_version='v1', nodes=4, minimum_support=7, B8L2=None,
               member_workers='W001|W002', source_time_total_seconds=60)
    new = dict(team_key='team', pool_id='pool', reference_id='reference',
               reference_version='v1', nodes=4, minimum_support=7, B8L2=85,
               member_workers=['W002', 'W001'], source_time_total_seconds=999)
    result = merge_endpoint(old, new)
    assert result['B8L2'] == 85
    assert result['source_time_total_seconds'] == 60
    assert old['B8L2'] is None


def test_bad_endpoint_identity_is_rejected():
    old = dict(team_key='team', reference_id='original')
    new = dict(team_key='team', reference_id='different')
    try:
        merge_endpoint(old, new)
    except AssertionError:
        pass
    else:
        raise AssertionError('Changing reference identity must not be accepted')
