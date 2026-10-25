import numpy as np
import pandas as pd

from tools.thesis_main.analysis.audit_population_precision_policy_20261025 import aggregate, common_k_mask, fixed_mean, statistics, linear_p10, FIELDS, METRICS


def test_linear_p10_matches_numpy_with_missing_paths():
    values = np.random.default_rng(3).normal(size=(7, 16, 5))
    values[:, :3, 2] = np.nan
    np.testing.assert_allclose(linear_p10(values), np.nanquantile(values, .1, axis=1))


def test_common_k_is_frozen_across_batches():
    values = np.array([[[1.], [np.nan], [3.]], [[2.], [4.], [6.]], [[1.5], [4.], [4.5]]])
    mask = common_k_mask(values)[:, 0]
    assert mask.tolist() == [True, False, True]
    assert fixed_mean(values[1, :, 0], mask, 0) == 4


def test_bootstrap_cannot_drop_a_missing_fixed_k():
    draws = np.array([[1., 3.], [1., np.nan]])
    result = fixed_mean(draws, np.array([True, True]), 1)
    assert result[0] == 2
    assert np.isnan(result[1])
    assert np.isnan(np.mean(result))


def test_aggregate_does_not_drop_missing_image_from_bootstrap():
    point = np.zeros((2, 4, len(METRICS)))
    point[:, 0, 0] = [10, 30]
    boot = np.repeat(point[:, None], 2, axis=1)
    boot[1, 1, 0, 0] = np.nan
    meta = pd.DataFrame({'pool_id': ['a', 'b'], 'building': ['A', 'B'], 'difficulty': ['简单', '简单']})
    rows = aggregate(point, boot, meta, 'old8', 'policy', np.random.default_rng(1), 2)
    row = next(r for r in rows if r['difficulty'] == '全部' and r['phase'] == 'early_3_to_half' and r['metric'] == 'paired_Q_delta' and r['weighting'] == 'image_equal')
    assert row['estimate'] == 20
    assert row['path_valid_replicates'] == 1
    assert row['path_invalid_replicates'] == 1
    assert row['path_interval_status'] == 'conditional_on_estimable_draws'


def test_failure_keeps_all_attempts_while_quality_and_time_use_support():
    n = {key: np.ones((1, 2, 1), dtype=float) for key in FIELDS}
    p = {key: value.copy() for key, value in n.items()}
    n['B8L2'][:] = [[[50.], [np.nan]]]
    p['B8L2'][:] = [[[60.], [70.]]]
    n['D10'][:] = [[[55.], [np.nan]]]
    p['D10'][:] = [[[65.], [75.]]]
    n['score_failure_nonpolicy'][:] = [[[0.], [1.]]]
    p['score_failure_nonpolicy'][:] = 0
    n['source_time_total_seconds'][:] = 10
    p['source_time_total_seconds'][:] = 20
    p['labor_kind_code'][0, 1, 0] = 2
    values = statistics(n, p)[0, 0]
    assert values[METRICS.index('paired_Q_delta')] == 10
    assert values[METRICS.index('failure_delta')] == -.5
    assert values[METRICS.index('labor_ratio_legal')] == 2
    assert np.isnan(values[METRICS.index('Q_sd_delta_common_ddof1')])
