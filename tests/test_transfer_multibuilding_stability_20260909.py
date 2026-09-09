import json

import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.transfer_multibuilding_stability_20260909 import (
    CONFIGS, onset, interval_error, transfer,
)


def test_unknown_bounds_persistent_onset_and_disjoint_image_transfer(tmp_path):
    lo, hi = interval_error(np.array([0.]), np.array([1.]), np.array([0.]), np.array([1.]))
    assert lo.tolist() == [0.] and hi.tolist() == [1.]
    assert onset([.9, .7, .9], [.9, .7, .9]) == (3, 3, 3, 'identified')
    assert onset([0, 0], [1, 1]) == (1, None, None, 'unknown')
    assert onset([.2, .4], [.4, .6]) == (None, None, None, 'not_reached')
    inventory, curves = [], []
    for building in ['a', 'b']:
        for number in range(2):
            image = f'{building}{number}'
            inventory.append(dict(image_id=image, building_id=building, usable_n=16, dense_ge16=True))
            for config in CONFIGS:
                for k in range(1, 12):
                    value = int(k >= (3 if building == 'a' else 5))
                    curves.append(dict(image_id=image, building_id=building, config=config, k=k,
                        lookahead=5, min_support=2, epsilon=.1, replicates=200,
                        stable=value * 200, changing=(1 - value) * 200, unknown=0,
                        stable_lower=value, stable_upper=value))
    qa = transfer(pd.DataFrame(inventory), pd.DataFrame(curves), tmp_path)
    folds = pd.read_csv(tmp_path / 'folds.csv.gz')
    assert qa['fold_rows'] == 28 and qa['building_n'] == 2
    assert (folds.same_error_lower == 0).all() and (folds.same_error_upper == 0).all()
    assert (folds.outside_error_lower > 0).all()
    assert (folds.N_identified_pairs == 1).all() and (folds.N_absolute_error_sum == 0).all()
    assert (folds.outside_N_MAE_identified == 2).all()
    for row in folds.itertuples():
        source, target = json.loads(row.source_images_json), json.loads(row.target_images_json)
        assert not set(source) & set(target)
        assert set(source + target) == {f'{row.building_id}0', f'{row.building_id}1'}
    for row in pd.read_csv(tmp_path / 'baseline_groups.csv').itertuples():
        assert all(not image.startswith(row.building_id) for image in json.loads(row.source_images_json))
    unknown = pd.DataFrame(curves).assign(stable=0, changing=0, unknown=200, stable_lower=0, stable_upper=1)
    transfer(pd.DataFrame(inventory), unknown, tmp_path)
    unresolved = pd.read_csv(tmp_path / 'folds.csv.gz')
    assert (unresolved.same_error_lower == 0).all() and (unresolved.same_error_upper == 1).all()
    assert (unresolved.predicted_N_status == 'unknown').all() and (unresolved.N_identified_pairs == 0).all()
    assert unresolved.predicted_N_guaranteed.isna().all() and (unresolved.target_N_both_finite_n == 0).all()


def test_short_window_transfer_selects_people_budget_and_configs(tmp_path):
    inventory, curves = [], []
    for building in ['a', 'b']:
        for number, n in enumerate([1, 3, 4]):
            image = f'{building}{number}'
            inventory.append(dict(image_id=image, building_id=building, usable_n=n, dense_ge16=False))
            for config in CONFIGS:
                for k in range(1, n):
                    curves.append(dict(image_id=image, building_id=building, config=config, k=k,
                        lookahead=1, min_support=2, epsilon=.1, replicates=200, stable=200,
                        changing=0, unknown=0, stable_lower=1., stable_upper=1.))
    inventory, curves = pd.DataFrame(inventory), pd.DataFrame(curves)
    qa = transfer(inventory, curves, tmp_path, lookahead=1, min_workers=1, configs=('q_0.950', 'ospa30_t6'))
    folds = pd.read_csv(tmp_path / 'folds.csv.gz')
    assert qa['selected_images'] == 4 and qa['fold_rows'] == 8
    assert set(folds.config) == {'q_0.950', 'ospa30_t6'}
    assert (folds.common_people_budget == 3).all() and (folds.k_max == 2).all()
    assert (folds.lookahead == 1).all()
    missing = curves.drop(curves[(curves.image_id == 'a1') & (curves.config == 'q_0.950')].index[0])
    with pytest.raises(ValueError, match='incomplete_curve_nodes'):
        transfer(inventory, missing, tmp_path / 'bad', lookahead=1, min_workers=1, configs=('q_0.950',))
