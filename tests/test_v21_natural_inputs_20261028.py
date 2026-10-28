import pandas as pd
import pytest
from tools.thesis_main.analysis.prepare_v21_natural_inputs_20261028 import overlay, METRICS
from tools.thesis_main.analysis.prepare_v21_natural_inputs_20261028 import repair_new_space_deferred


def test_new_space_deferred_repair_uses_saved_status_and_rejects_unknown_gap():
    frame = pd.DataFrame(dict(k=[1, 2, 3], stratum=['new_space256'] * 3,
        policy_deferred=[None] * 3, score_status=['scoreable', 'two_person_deferred', 'fusion_exception']))
    assert repair_new_space_deferred(frame)
    assert frame.policy_deferred.tolist() == [False, True, False]
    assert not repair_new_space_deferred(frame)
    frame['policy_deferred'] = None
    frame.loc[2, 'score_status'] = 'two_person_deferred'
    with pytest.raises(AssertionError, match='disagree'):
        repair_new_space_deferred(frame)
    frame['stratum'] = 'old24'
    with pytest.raises(AssertionError, match='unexpected'):
        repair_new_space_deferred(frame)


def test_unavailable_replaces_old_score_and_repeated_paths_keep_weight():
    frame = pd.DataFrame([dict(team_key='a', k=3, B8L2=80., complete_evaluable=True),
                          dict(team_key='b', k=2, B8L2=None, complete_evaluable=False)])
    patches = pd.DataFrame([dict(team_key='a', score_status='invalid_full_geometry',
                                **{c: None for c in METRICS})]).set_index('team_key')
    out = overlay(frame, patches).set_index('team_key')
    assert pd.isna(out.loc['a', 'B8L2'])
    assert out.loc['a', 'score_failure_nonpolicy']
    assert not out.loc['b', 'score_failure_nonpolicy']
    links = pd.DataFrame({'team_key': ['a', 'a', 'b']})
    assert len(links.join(out, on='team_key', validate='many_to_one')) == 3


def test_saved_new_space_rates_keep_actual_denominators_and_deferred_k2():
    import numpy as np
    from tools.thesis_main.analysis.rebuild_v21_20261028 import OUT
    curve = pd.read_csv(OUT / 'natural_results/NATURAL_CURVES.csv.gz', low_memory=False)
    curve = curve[curve.cohort.eq('new_space256')]
    assert curve.pool_id.nunique() == 34 and len(curve) == 852
    rate_counts = {'failure_rate': 'failure_paths', 'incomplete_rate': 'incomplete_paths',
        'actual_consensus_failure_rate': 'actual_consensus_failure_paths',
        'output_unscoreable_rate': 'output_unscoreable_paths',
        'reference_unavailable_rate': 'reference_unavailable_paths'}
    for pid, rows in curve.groupby('pool_id'):
        import json
        receipt=json.loads((OUT / 'natural_analysis/pool_checkpoints' / (pid+'__DONE.json')).read_text(encoding='utf8'))
        assert receipt['deferred_schema']=='explicit_k2_v1'
        raw = pd.read_csv(OUT / 'natural_inputs' / (pid + '.csv.gz'), low_memory=False)
        assert raw.policy_deferred.eq(raw.k.eq(2)).all()
        assert set(raw.score_status) <= {'complete_conditional', 'two_person_deferred', 'no_connection', 'below_four', 'invalid_floor'}
        for r in rows.itertuples():
            d = raw[raw.k.eq(r.k)]
            assert len(d) == 256
            if r.k == 2:
                assert r.policy_deferred_paths == 256 and r.nondeferred_attempts == 0
                assert all(pd.isna(getattr(r, c)) for c in rate_counts)
                continue
            assert r.nondeferred_attempts == r.actual_executed_nondeferred_paths == 256
            assert r.failure_paths == d.B8L2.isna().sum()
            assert r.actual_consensus_failure_paths == d.score_status.isin(['no_connection', 'below_four']).sum()
            assert r.output_unscoreable_paths == d.score_status.eq('invalid_floor').sum()
            assert np.isclose(r.Q_mean, d.B8L2.mean(), equal_nan=True)
            for metric, count in rate_counts.items():
                assert abs(getattr(r, metric) - getattr(r, count) / 256) < 1e-14
    intervals = pd.read_csv(OUT / 'natural_results/NATURAL_INTERVALS.csv.gz', low_memory=False)
    single=curve[curve.pool_n.eq(1)]
    assert len(single)==1 and single.unique_teams.eq(1).all()
    assert not intervals.pool_id.isin(single.pool_id).any()
    lookup = curve.set_index(['pool_id', 'k'])
    for r in intervals[intervals.cohort.eq('new_space256')].itertuples():
        for metric in ['failure', 'incomplete', 'actual_consensus_failure', 'output_unscoreable']:
            expected = lookup.at[(r.pool_id, r.k_to), metric + '_rate'] - lookup.at[(r.pool_id, r.k_from), metric + '_rate']
            assert np.isclose(getattr(r, metric + '_delta'), expected, atol=1e-14, equal_nan=True)
    summary = pd.read_csv(OUT / 'natural_results/SUPPORT_STRATIFIED_SUMMARY.csv.gz')
    selected = summary[(summary.support=='added') & (summary.panel=='available_at_k') & (summary.layer=='ordinary_manual') & (summary.k==3) & (summary.metric=='actual_consensus_failure_rate')]
    assert len(selected)==2 and selected.images.eq(29).all() and selected.missing_images.eq(0).all()
    import sys
    from tools.thesis_main.analysis.prepare_v21_natural_inputs_20261028 import EXT
    sys.path.insert(0, str(EXT / 'analysis_precision26'))
    from precision_core import METRICS, bootstrap_weights
    pid = 'B6ByNegPMKs-37__manual__v21_246'
    raw = pd.read_csv(OUT / 'natural_inputs' / (pid + '.csv.gz'), low_memory=False)
    rows = raw[raw.k.eq(4)].set_index('path_id').sort_index()
    weights = bootstrap_weights(pid, 'new_space256', 256, 2000, 2026102607)
    failures = rows.score_status.isin(['no_connection', 'below_four']).to_numpy(float)
    with np.load(OUT / 'natural_analysis/bootstrap_cache' / (pid + '.npz')) as saved:
        np.testing.assert_allclose(saved['curve_new_space256'][:, 3, METRICS.index('actual_consensus_failure_rate')], weights @ failures / 256, atol=1e-14)
