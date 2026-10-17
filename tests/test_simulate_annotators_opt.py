import copy

import numpy as np

from tools.thesis_main.analysis import simulate_annotators as s1
from tools.thesis_main.analysis import simulate_annotators_opt as opt
from tools.thesis_main.analysis.evaluate_simulated_pilot import footprint_iou


def polygon(n=4, shift=0):
    return [[float((x + shift) % 1024), float(y)]
            for x in np.linspace(64, 960, n, endpoint=False) for y in (150, 370)]


def bank(n=4):
    return {f: dict(points=polygon(n), layout_id=f) for f in s1.FAMILIES}


def training():
    models = {f't{i}': bank() for i in range(5)}
    human = [dict(image_id=i, building_id='A', worker_id='1', annotation_id=i,
                  points=polygon(4, 1)) for i in models]
    return human, models


def test_normalized_profile_and_personal_donors():
    h, m = training()
    learned = opt.fit_holdout(h, m, 'B')
    for spelling in ('W001', '001', 1):
        row = opt.simulate_v2(bank(), learned, ['virtual'], 'worker', 42, 'target',
                             worker_profile_map={'virtual': spelling})[0]
        assert row['source_worker_profile_id'] == '1'
        assert row['profile_found']
        assert row['residual_source'] == 'personal_empirical_residual'
        assert row['profile_fallback_reason'] is None
        assert row['residual_applied']


def test_missing_profile_is_explicit():
    h, m = training()
    row = opt.simulate_v2(bank(), opt.fit_holdout(h, m, 'B'), ['missing'], 'worker', 42, 'target')[0]
    assert not row['profile_found']
    assert row['profile_fallback_reason'] == 'profile_missing'
    assert row['residual_source'] == 'pooled_empirical_residual'


def test_small_personal_pool_really_uses_pooled_donors():
    h, m = training()
    learned = opt.fit_holdout(h, m, 'B')
    for f in s1.FAMILIES:
        ds = [d for d in learned['donors'] if d['family'] == f]
        for d in ds[1:]:
            d['worker_id'] = '2'
    r = opt.simulate_v2(bank(), learned, ['1'], 'worker', 5, 'target')[0]
    assert r['personal_donor_count'] == 1
    assert r['profile_fallback_reason'] == 'insufficient_personal_donors'


def test_target_count_trims_larger_model():
    h, m = training()
    learned = opt.fit_holdout(h, m, 'B')
    rows = opt.simulate_v2(bank(6), learned, ['1'], 'worker', 5, 'target', count_mode=True)
    assert len(rows[0]['points']) == 8
    assert rows[0]['target_pairs'] == 4
    assert rows[0]['count_status'] == 'sampled'
    assert s1.geometry_status(rows[0]['points']) == 'basic_checks_passed_not_certified'


def test_unsupported_addition_keeps_explicit_status():
    h, m = training()
    learned = opt.fit_holdout(h, m, 'B')
    learned['worker_pair_counts']['1'] = [8] * 3
    r = opt.simulate_v2(bank(), learned, ['1'], 'worker', 5, 'target', count_mode=True)[0]
    assert r['count_status'] == 'unsupported_addition'
    assert r['target_pairs'] == 8
    assert len(r['points']) == 8


def test_all_training_counts_used_even_without_residual_donor():
    h, m = training()
    h.append(dict(h[0], annotation_id='different_count', points=polygon(7)))
    learned = opt.fit_holdout(h, m, 'B')
    assert 7 in learned['worker_pair_counts']['1']
    assert not any(d['point_count'] == 14 for d in learned['donors'])


def test_holdout_answers_cannot_affect_profiles_counts_or_samples():
    h, m = training()
    h.append(dict(h[0], image_id='target', building_id='B', annotation_id='heldout'))
    m['target'] = bank()
    before = opt.fit_holdout(h, m, 'B')
    changed = copy.deepcopy(h)
    changed[-1]['points'] = polygon(8, 50)
    after = opt.fit_holdout(changed, m, 'B')
    assert before == after
    assert opt.simulate_v2(bank(), before, ['1'], 'worker', 9, 'target') == opt.simulate_v2(bank(), after, ['1'], 'worker', 9, 'target')


def test_paired_random_streams_preserve_family_selection():
    h, m = training()
    learned = opt.fit_holdout(h, m, 'B')
    a = opt.simulate_v2(bank(), learned, ['1', '2'], 'worker', 9, 'target', cap=8, no_x_collapse=False, tries=1)
    b = opt.simulate_v2(bank(), learned, ['1', '2'], 'worker', 9, 'target', cap=24, scale=1.5, tries=1)
    assert [r['model_family'] for r in a] == [r['model_family'] for r in b]


def test_empty_donor_pool_marks_model_copy():
    h, m = training()
    learned = opt.fit_holdout(h, m, 'B')
    learned['donors'] = []
    r = opt.simulate_v2(bank(), learned, ['1'], 'worker', 9, 'target')[0]
    assert r['model_copy']
    assert not r['residual_applied']
    assert r['residual_fallback_reason'] == 'no_matching_donors'


def test_fixed_family_control_keeps_personal_residual_policy():
    h, m = training()
    r = opt.simulate_v2(bank(), opt.fit_holdout(h, m, 'B'), ['1'], 'worker', 9,
                        'target', fixed_family='HoHoNet')[0]
    assert r['model_family'] == 'HoHoNet'
    assert r['residual_source'] == 'personal_empirical_residual'


def test_reference_iou_is_one_for_identical_geometry():
    assert abs(footprint_iou(polygon(), polygon()) - 1.) < 1e-12
