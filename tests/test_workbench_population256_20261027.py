"""256/32展示合同：读取保存结果，不再运行原生融合或重抽。"""
import pytest
from tools.thesis_main.analysis import build_research_workbench_v2_20261019 as builder


@pytest.fixture(scope='module')
def saved():
    return builder.population256_tables()[0]


def test_exact_anchors_statuses_and_independent_batches(saved):
    rows = saved['population256__hybrid_images']
    assert len(rows) == 6290
    assert len({(r['pool_id'], r['k']) for r in rows}) == len(rows)
    assert {r['cohort'] for r in rows} == {'pooled256'}
    deferred = [r for r in rows if r['k'] == 2]
    assert deferred and all(r['estimator'] == 'contract_deferred_k2' and r['Q_mean'] is None for r in deferred)
    full = [r for r in rows if r['k'] == r['pool_n']]
    assert len(full) == 194 and all(r['estimator'] == 'exact_finite_uniform_marginal' for r in full)
    assert all(r['Q_sd_display'] == 0 for r in full if r['Q_mean'] is not None)
    assert sum(r['actual_consensus_failure_rate'] == 1 for r in full if r['layer'] == 'ordinary_manual') == 1
    assert sum(r['actual_consensus_failure_rate'] == 1 for r in full if r['layer'] == 'doorway_manual') == 6
    batches = saved['population256__batch_images']
    for cohort, count in [('pooled256', 256), ('new208', 208), ('stage1_104', 104), ('stage2_104', 104)]:
        chosen = [r for r in batches if r['cohort'] == cohort]
        assert chosen and all(r['paths_attempted'] == count for r in chosen)


def test_changed_doorway_direction_and_separate_support(saved):
    rows = [r for r in saved['population256__interval_summary'] if r['cohort'] == 'pooled256'
            and r['panel'] == 'interval_eligible' and r['layer'] == 'doorway_manual'
            and r['weighting'] == 'image_equal']
    q = next(r for r in rows if r['interval'] == '6_to_10' and r['metric'] == 'marginal_Q_delta')
    assert q['estimate'] == pytest.approx(-1.0064484396) and q['negative_images'] == 12
    q = next(r for r in rows if r['interval'] == '20_to_30' and r['metric'] == 'marginal_Q_delta')
    fail = next(r for r in rows if r['interval'] == '20_to_30' and r['metric'] == 'actual_consensus_failure_delta')
    assert (q['images'], q['positive_images'], q['negative_images']) == (15, 8, 7)
    assert fail['images'] == 16 and fail['estimate'] == pytest.approx(.09130859375)


def test_policy32_is_not_256_and_joint_time_support_is_separate(saved):
    rows = [r for r in saved['population256__policy_summary'] if r['version'] == 'pooled32'
            and r['phase'] == 'early_3_to_half' and r['difficulty'] == '全部' and r['weighting'] == 'image_equal']
    q = [r for r in rows if r['metric'] == 'paired_Q_delta']
    assert [r['images'] for r in q] == [157] * 4
    assert [r['path_valid_replicates'] for r in q] == [2000, 1998, 1976, 1999]
    assert [r['images'] for r in rows if r['metric'] == 'labor_ratio_legal'] == [115, 94, 72, 117]
    fast = next(r for r in rows if r['policy'] == 'joint_fast_first' and r['metric'] == 'labor_ratio_legal')
    assert fast['estimate'] == pytest.approx(.786092, abs=1e-6)
    assert all(r['base_paths'] == 32 for r in saved['population256__policy_images'] if r['version'] == 'pooled32')


def test_first_view_projections_retain_values_and_full_exports(saved):
    full = saved['population256__batch_images']
    display = saved['population256__batch_display']
    assert len(full) == len(display)
    assert all(all(row[k] == original[k] for k in row) for row, original in zip(display, full))
    for display_name, source, metric in [('geometry_floor_images', 'geometry_images', 'V_floor'),
                                         ('geometry_floor_fixed', 'geometry_fixed', 'V_floor'),
                                         ('policy_q_support', 'policy_support', 'paired_Q_delta')]:
        assert saved['population256__' + display_name] == [r for r in saved['population256__' + source] if r['metric'] == metric]


def test_offline_packager_references_stay_in_archive():
    from tools.thesis_main.analysis.update_research_workbench_zip_20261027 import local_reference
    assert local_reference('site/index.html', '../data/a.csv?download=1') == 'data/a.csv'
    assert local_reference('site/index.html', '#module=images') is None
    assert local_reference('site/index.html', 'https://example.org/a') is None
    with pytest.raises(ValueError):
        local_reference('index.html', '../outside.csv')
