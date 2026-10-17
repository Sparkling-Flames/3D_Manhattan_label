import copy
import json

import numpy as np

from tools.thesis_main.analysis import simulated_response_metadata as meta
from tools.thesis_main.analysis import simulate_annotators as s1
from tools.thesis_main.analysis import simulate_annotators_opt as opt


def rectangle():
    return [[x, y] for x in (64, 320, 576, 832) for y in (150, 370)]


def donor():
    return dict(worker_id='1', building_id='A', condition='semi', raw_condition='semi',
                canonical_annotation_id='donor', initial_points_json=json.dumps(rectangle()),
                final_points_json=json.dumps(rectangle()), initial_point_count='8',
                initial_structurally_valid='true', final_structurally_valid='true')


def fixture():
    bank = {f: dict(points=rectangle(), layout_id=f) for f in s1.FAMILIES}
    learned = opt.fit_holdout([dict(image_id='train', building_id='A', worker_id='1',
        annotation_id='train', points=rectangle())], {'train': bank}, 'B')
    sample = opt.simulate_v2(bank, learned, ['1'], 'worker', 2, 'target')[0]
    time = dict(worker_id='1', building_id='A', condition='semi', canonical_annotation_id='time',
                active_time_seconds='42', lead_time_seconds='56', raw_final_point_count='8',
                time_active_time_formal_available='true', active_time_owner_valid_status='owner_valid_complete')
    scope = dict(worker_id='1', building_id='A', condition='semi', canonical_annotation_id='scope', worker_scope='oos')
    return sample, bank, dict(time=[time], semi=[donor()], scope=[scope])


def test_only_complete_formal_finite_time_is_eligible():
    _, _, evidence = fixture()
    r = evidence['time'][0]
    assert meta.eligible_time(r)
    for changes in [dict(active_time_seconds='nan'), dict(active_time_seconds='0'),
                    dict(active_time_owner_valid_status='partial_session_coverage_excluded_from_speed'),
                    dict(time_active_time_formal_available='false')]:
        assert not meta.eligible_time(dict(r, **changes))


def test_semi_empirical_copy_and_metadata_trace():
    sample, bank, evidence = fixture()
    r = meta.augment(sample, bank, evidence, 'B', 'semi', 1)
    assert r['semi_status'] == 'empirical_copy'
    assert r['model_copy'] and r['active_time_seconds'] == 42
    assert r['timing_status'] == 'simulated_empirical'
    assert r['worker_scope_response'] == 'oos'
    assert r['scope_status'] == 'simulated'
    assert r['synthetic'] and r['review_required']
    assert r['semi_donor_building_id'] == r['time_donor_building_id'] == r['scope_donor_building_id'] == 'A'


def test_deletion_is_transferred_to_model_and_stays_valid():
    d = donor()
    d['final_points_json'] = json.dumps(rectangle()[:-2])
    points, status = meta.transfer_semi(rectangle(), d)
    assert status == 'empirical_edit'
    assert len(points) == 6
    assert s1.geometry_status(points) == 'basic_checks_passed_not_certified'


def test_unsupported_addition_does_not_claim_success():
    d = donor()
    d['initial_points_json'] = json.dumps(rectangle()[:-2])
    points, status = meta.transfer_semi(rectangle()[:-2], d)
    assert status == 'unsupported_addition'
    assert np.array_equal(points, rectangle()[:-2])


def test_all_metadata_excludes_target_building():
    sample, bank, evidence = fixture()
    for rows in evidence.values():
        rows[0]['building_id'] = 'B'
    r = meta.augment(sample, bank, evidence, 'B', 'semi', 1)
    assert r['semi_status'] == 'no_training_evidence'
    assert r['active_time_seconds'] is None
    assert r['worker_scope_response'] is None
    changed = copy.deepcopy(evidence)
    changed['time'][0]['active_time_seconds'] = '999'
    changed['scope'][0]['worker_scope'] = 'in_scope'
    changed['semi'][0]['final_points_json'] = json.dumps(rectangle()[:-2])
    assert r == meta.augment(sample, bank, changed, 'B', 'semi', 1)


def test_condition_does_not_borrow_other_condition_time_or_scope():
    sample, bank, evidence = fixture()
    r = meta.augment(sample, bank, evidence, 'B', 'manual', 1)
    assert r['semi_status'] == 'not_applicable'
    assert r['active_time_seconds'] is None
    assert r['scope_status'] == 'not_simulated'


def test_metadata_sampling_is_repeatable():
    sample, bank, evidence = fixture()
    assert meta.augment(sample, bank, evidence, 'B', 'semi', 7) == meta.augment(sample, bank, evidence, 'B', 'semi', 7)
