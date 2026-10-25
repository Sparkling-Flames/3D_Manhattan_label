"""保存结果的展示合同；不重跑融合/评分/抽样。"""
import pytest
from tools.thesis_main.analysis import build_research_workbench_v2_20261019 as builder


@pytest.fixture(scope='module')
def saved():
    return builder.population_precision_tables()[0]


def test_hybrid_schema_and_deferred_missing_are_preserved(saved):
    assert len(saved) == 14
    rows = saved['population_precision__hybrid_images']
    assert len(rows) == 6290
    assert len({(r['pool_id'], r['k']) for r in rows}) == len(rows)
    deferred = [r for r in rows if r['estimator'] == 'contract_deferred_k2']
    assert deferred and all(r['k'] == 2 and r['Q_mean'] is None for r in deferred)
    assert {r['estimator'] for r in rows} == {'contract_deferred_k2', 'exact_finite_uniform_marginal', 'balanced48_uniform_random_permutation_prefixes'}
    versions = saved['population_precision__batch_images']
    assert {r['version'] for r in versions} == {'old24', 'new24', 'pooled48', 'focus96'}
    assert all(r['layer'] in {'ordinary_manual', 'doorway_manual'} for r in versions)


def test_policy_uses_corrected_fixed_support_and_invalid_replicates(saved):
    rows = [r for r in saved['population_precision__policy_key'] if r['batch'] == 'combined16']
    assert len(rows) == 4
    expected = {'joint_highq_first': (7.671565, 997), 'structure_moreturn_first': (6.127311, 939),
                'joint_fast_first': (-1.742024, 818), 'structure_dominant_first': (-1.943602, 731)}
    for r in rows:
        value, valid = expected[r['policy']]
        assert r['estimate'] == pytest.approx(value, abs=1e-6)
        assert r['images'] == 157 and r['path_valid_replicates'] == valid
        assert r['path_invalid_replicates'] + valid == 1000
        assert r['path_interval_status'] == 'conditional_on_estimable_draws'
    joint = [r for r in saved['population_precision__policy_summary'] if r['batch'] == 'combined16'
             and r['phase'] == 'early_3_to_half' and r['metric'] == 'labor_ratio_legal'
             and r['difficulty'] == '全部' and r['weighting'] == 'image_equal']
    assert [r['images'] for r in joint] == [116, 96, 73, 119]


def test_wc2_catalogue_does_not_turn_path_frequency_into_uniform_team_weight(saved):
    teams = saved['population_precision__wc2_teams']
    assert len(teams) == 28 and len({r['team_key'] for r in teams}) == 28
    low = [r for r in teams if r['score_peak'] == 'low']
    assert len(low) == 4 and sum(r['combined96_path_count'] for r in low) == 7
    assert all(r['finite_uniform_weight'] == pytest.approx(1/28) for r in teams)
    assert sum(r['combined96_path_count'] for r in teams) == 96
    exact = next(r for r in saved['population_precision__wc2_weights'] if r['sample'] == 'exact_uniform_28_teams')
    assert exact['P10_linear'] == pytest.approx(52.406206944032334)
    assert any(r['paired_Q_delta'] is not None for r in saved['population_precision__paired_intervals'])
