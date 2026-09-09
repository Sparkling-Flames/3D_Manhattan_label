import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.review_multibuilding_thresholds_20260909 import (
    accepted_pairs, common_budget_curves, curve_onsets,
    imputation_sensitivity,
)


def test_pair_acceptance_keeps_count_correspondence_and_both_q_channels():
    pairs = pd.DataFrame({
        'count_compatible': [True, False, True, True, True, True],
        'metric_compatible': [True, True, True, False, True, True],
        'pointwise_correspondence_compatible': [True, True, False, True, True, True],
        'q_boundary': [.95, .99, .99, .99, .96, np.nan],
        'q_wallwall': [.95, .99, .99, .99, .92, .99],
    })
    strict = accepted_pairs(pairs, .95)
    loose = accepted_pairs(pairs, .90)
    assert strict.tolist() == [True, False, False, False, False, False]
    assert loose.tolist() == [True, False, False, False, True, False]
    assert (loose & ~strict).sum() == 1


def test_common_budget_recomputes_onsets_instead_of_comparing_shorter_followup():
    inventory = pd.DataFrame({'image_id': ['a'], 'building_id': ['b'], 'usable_n': [6]})
    shorter = inventory.assign(usable_n=4)
    def curves(values):
        return pd.DataFrame([dict(image_id='a', building_id='b', config='q_0.950',
            k=k, lookahead=1, min_support=2, epsilon=.1, replicates=200,
            stable=int(v * 200), changing=200-int(v * 200), unknown=0,
            stable_lower=v, stable_upper=v) for k, v in enumerate(values, 1)])
    # The later decline exists only beyond the shared observation budget.
    left = curves([0, 1, 1, 0, 0])
    right = curves([0, 1, 1])
    images, paired = common_budget_curves(inventory, shorter, left, right)
    assert images.common_n.tolist() == [4]
    assert paired.k.tolist() == [1, 2, 3]
    assert paired.common_k_max.eq(3).all()
    assert paired.lower_difference.eq(0).all()
    full = curve_onsets(left.assign(people_budget=6))
    shared = curve_onsets(paired.rename(columns={
        'stable_lower_with_workers': 'stable_lower', 'stable_upper_with_workers': 'stable_upper',
        'common_n': 'people_budget'}))
    assert full.onset_status.tolist() == ['not_reached']
    assert shared.identified_onset.tolist() == [2]
    with pytest.raises(ValueError, match='incomplete_curve_nodes'):
        common_budget_curves(inventory, shorter, left.drop(index=1), right)
    with pytest.raises(ValueError, match='building_identity_mismatch'):
        common_budget_curves(inventory, shorter.assign(building_id='wrong'), left, right)


def test_no_imputation_reuse_requires_exact_unchanged_geometry(tmp_path):
    ids = ['q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4',
           'uNb9QFRL6hY_978d7a8eb0794936bd8fd092306e1dc5', 'unchanged']
    inventory = pd.DataFrame({'image_id': ids, 'building_id': ['b']*3, 'usable_n': [3]*3})
    curves = pd.DataFrame([dict(image_id=image, building_id='b', config='q_0.950', k=k,
        lookahead=1, min_support=2, epsilon=.1, replicates=200, stable=200, changing=0,
        unknown=0, stable_lower=1., stable_upper=1.) for image in ids for k in [1, 2]])
    alternate = tmp_path / 'no_imputation'
    for base in [tmp_path, alternate]:
        (base / 'geometry').mkdir(parents=True)
        inventory.to_csv(base / 'image_inventory.csv', index=False)
        pd.DataFrame({'image_id': ids, 'canonical_annotation_id': ['a', 'b', 'c'],
                      'effective_point_count': [8, 8, 8]}).to_csv(base / 'geometry/response_geometry.csv', index=False)
        pd.DataFrame({'image_id': ids, 'left_canonical': ['a', 'b', 'c'], 'right_canonical': ['d', 'e', 'f'],
                      'q_boundary': [.9]*3}).to_csv(base / 'geometry/pairwise_q.csv.gz', index=False)
        pd.DataFrame({'image_id': ids, 'threshold': [.95]*3}).to_csv(base / 'geometry/full_q_partitions.csv', index=False)
    (alternate / 'affected_replay').mkdir()
    curves[curves.image_id.isin(ids[:2])].to_csv(alternate / 'affected_replay/stability_curves.csv', index=False)
    onsets, _, qa = imputation_sensitivity(tmp_path, curves, inventory)
    assert qa['recomputed_image_n'] == 2 and qa['reused_curve_rows'] == 2
    assert len(onsets) == 4
    broken = pd.read_csv(alternate / 'geometry/pairwise_q.csv.gz')
    broken.loc[broken.image_id.eq('unchanged'), 'q_boundary'] = .8
    broken.to_csv(alternate / 'geometry/pairwise_q.csv.gz', index=False)
    with pytest.raises(AssertionError):
        imputation_sensitivity(tmp_path, curves, inventory)
