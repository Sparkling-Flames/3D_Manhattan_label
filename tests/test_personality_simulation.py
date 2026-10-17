import copy
import math

import numpy as np
import pytest

from tools.thesis_main.analysis import simulate_annotators as base
from tools.thesis_main.analysis.simulator_personality_inputs import bind_rows, checked_points, fit_profiles
from tools.thesis_main.analysis.personality_annotator_sampler import fit_personality, mixture_pools, transfer, generate
from tools.thesis_main.analysis.personality_simulation_review import contrast, calibration_errors, matched_comparison


def rectangle(shift=0):
    return [[(x + shift) % 1024, y] for x in (64, 320, 576, 832) for y in (150, 370)]


def binding_fixture():
    obj = dict(object_id='obj', image_id='im', worker_id='W001', condition='manual', building_id='A',
               source=dict(project=1, task=2, annotation=3), links_zero_based=[[0, 1], [2, 3], [4, 5], [6, 7]],
               points_1024x512=rectangle(), independent_vote_eligible=True, ring_confirmed=True,
               order_status='human_confirmed', ordered_source_point_indices=list(range(8)))
    gate = dict(record_id='R1', object_id='obj', image_id='im', worker_id='W001', condition='manual',
                role='manual_development_candidate', original_holdout=False, personnel_barriers=[], context_barriers=[])
    inv = dict(gate, building_id='A', project_id='1', runtime_task_id='2', raw_annotation_id='3',
               time_training_eligible='True', time_usable='True', time_seconds='45', time_context='task')
    score = dict(gate, building_id='A', reference_id='ref', score_status='full', WQ='80', IoU3D100='90',
                 same_target_unconfirmed='False', same_target_quality_hold='False', latest_step_reference_pending='False',
                 iou_2d='.9', S_bottom_deg='1', dir='0', Hmean='.1', Hcenter='.01')
    return [obj, dict(object_id='ref', image_id='im')], [gate], [inv], [score]


def test_current_identity_and_authorized_pairing_are_preserved():
    objects, gates, inv, scores = binding_fixture()
    before = copy.deepcopy(objects)
    rows, ledger = bind_rows(objects, gates, inv, scores)
    assert rows[0]['annotation_id'] == 'obj' and rows[0]['worker_id'] == '1'
    assert rows[0]['points'] == rectangle() and rows[0]['ring_confirmed']
    assert rows[0]['source_point_indices'] == list(range(8))
    assert rows[0]['WQ'] == 80 and rows[0]['active_time_seconds'] == 45
    assert objects == before
    objects[0]['links_zero_based'] = []
    rows, ledger = bind_rows(objects, gates, inv, scores)
    assert rows == [] and not ledger[0]['paired_points_available']


@pytest.mark.parametrize('field,value', [('worker_id', 'W002'), ('object_id', 'other'), ('reference_id', 'absent')])
def test_identity_and_reference_mismatches_fail_closed(field, value):
    objects, gates, inv, scores = binding_fixture()
    scores[0][field] = value
    with pytest.raises(ValueError):
        bind_rows(objects, gates, inv, scores)


def test_original_holdout_is_never_reinstated():
    objects, gates, inv, scores = binding_fixture()
    gates[0]['original_holdout'] = True
    rows, ledger = bind_rows(objects, gates, inv, scores)
    assert not rows and not ledger[0]['eligible_manual']


def test_reference_image_and_pair_source_identities_are_checked():
    objects, gates, inv, scores = binding_fixture()
    objects[1]['image_id'] = 'different_image'
    with pytest.raises(ValueError, match='reference_image_mismatch'):
        bind_rows(objects, gates, inv, scores)
    objects[1]['image_id'] = 'im'
    objects[0]['ordered_source_point_indices'] = [0] * 8
    with pytest.raises(ValueError, match='source_point_identity_mismatch'):
        bind_rows(objects, gates, inv, scores)


def test_pending_reference_keeps_quality_missing_without_losing_time():
    objects, gates, inv, scores = binding_fixture()
    scores[0]['same_target_quality_hold'] = 'True'
    rows, _ = bind_rows(objects, gates, inv, scores)
    assert rows[0]['WQ'] is None and rows[0]['IoU3D100'] is None
    assert rows[0]['active_time_seconds'] == 45


def training_fixture():
    rows, models = [], {}
    for building in 'ABCD':
        for image in range(4):
            iid = building + str(image)
            models[iid] = {f: dict(points=rectangle(), layout_id=f) for f in base.FAMILIES}
            for w, effect in [('1', -8.), ('2', 0.), ('3', 8.)]:
                rows.append(dict(annotation_id=iid + ':' + w, record_id=iid + ':' + w, image_id=iid,
                    building_id=building, worker_id=w, reference_id='reference:' + iid,
                    WQ=60 + image + effect, IoU3D100=80 + effect / 2,
                    active_time_seconds=math.expm1(4 + image / 10 - effect / 20), time_context='time:' + iid,
                    source={}, points=rectangle(int(w))))
    return rows, models


def test_task_effect_profiles_have_support_and_keep_boundary_uncertain():
    rows, _ = training_fixture()
    profiles = fit_profiles(rows, 'D')
    assert profiles['3']['quality'] == 'higher'
    assert profiles['1']['quality'] == 'lower'
    assert profiles['2']['quality'] == 'uncertain'
    assert profiles['3']['speed'] == 'faster'
    assert profiles['1']['speed'] == 'slower'
    assert profiles['1']['axes']['quality']['contexts'] == 12


def test_conflicting_WQ_and_IoU_does_not_create_a_good_label():
    rows, _ = training_fixture()
    for row in rows:
        row['IoU3D100'] = 160 - row['IoU3D100']
    profiles = fit_profiles(rows, 'D')
    assert profiles['3']['quality'] == 'uncertain'
    assert profiles['3']['quality_reason'] == 'WQ_IoU_sign_conflict'


def test_missing_quality_is_not_a_zero_score():
    rows, _ = training_fixture()
    for row in rows:
        if row['worker_id'] == '3':
            row['WQ'] = row['IoU3D100'] = None
    profiles = fit_profiles(rows, 'D')
    assert profiles['3']['quality'] == 'uncertain'
    assert not profiles['3']['axes']['quality']


def test_personal_sample_below_three_is_still_used_probabilistically():
    pool = [dict(worker_id=w, annotation_id='a' + w) for w in ('1', '2', '3')]
    profiles = {w: dict(quality='higher', prototype='higher:faster') for w in ('1', '2', '3')}
    pools, weights = mixture_pools(pool, '1', profiles)
    assert len(pools['personal']) == 1
    assert weights['personal'] == pytest.approx(1 / 9)
    assert weights['prototype'] > 0
    assert sum(weights.values()) == pytest.approx(1)


def test_observed_deletion_pattern_and_vertical_mismatch_are_not_repaired():
    donor = dict(count_offset=-1, kept_pairs=[0, 2, 3], delta=np.zeros((3, 2, 2)).tolist())
    donor['delta'][0][0][0] = 5
    result, status = transfer(rectangle(), donor, [100, 100])
    assert status == 'transferred' and len(result) == 6
    assert result[0, 0] == rectangle()[0][0] + 5
    assert 'vertical_pair_mismatch' in base.geometry_status(result)


def test_addition_and_numerical_failure_are_explicit():
    donor = dict(count_offset=1, kept_pairs=[0, 1, 2, 3], delta=np.zeros((4, 2, 2)).tolist())
    points, status = transfer(rectangle(), donor, [1000, 1000])
    assert status == 'unsupported_addition' and np.array_equal(points, rectangle())
    donor['count_offset'] = 0
    donor['delta'][0][0][1] = -500
    points, status = transfer(rectangle(), donor, [1000, 1000])
    assert status == 'numeric_invalid_retained' and not base.parsed(points)


def test_target_building_answers_scores_times_cannot_change_any_generation():
    rows, models = training_fixture()
    first = fit_personality(rows, models, 'D')
    changed = copy.deepcopy(rows)
    for row in changed:
        if row['building_id'] == 'D':
            row.update(points=rectangle(80), WQ=0., IoU3D100=0., active_time_seconds=99999.)
    second = fit_personality(changed, models, 'D')
    for key in ('learned', 'profiles', 'donors', 'caps', 'training_annotation_ids'):
        assert first[key] == second[key]
    a = generate(models['D0'], first, ['1', '2', '3'], 42, 'D0')
    b = generate(models['D0'], second, ['1', '2', '3'], 42, 'D0')
    assert a == b
    assert all(r['residual_donor_building_id'] != 'D' and r['time_donor_building_id'] != 'D' for r in a)
    assert all(r['synthetic'] and r['quality_version'] == 'WQ-LS08-20261014' for r in a)


def test_quality_contrast_keeps_references_separate_and_weights_images_once():
    rows = []
    for building in 'ABC':
        for ref in ('r1', 'r2'):
            for group, value in [('higher', 80), ('lower', 60)]:
                rows.append(dict(image_id=building, reference_id=ref, building_id=building,
                    variant='hierarchical', source_quality=group, WQ=value))
    pairs, summary = contrast(rows)
    assert len(pairs) == 6 and summary['paired_images'] == 3
    assert summary['building_equal_WQ_gap'] == 20
    assert summary['numerical_quality_signal']


def test_worker_calibration_requires_exact_worker_image_reference_binding():
    real = [dict(image_id='im', reference_id='ref', worker_id='1', WQ=80, points=rectangle(), building_id='A')]
    sample = dict(image_id='im', source_worker_profile_id='1', variant='hierarchical', source_quality='higher',
                  points=rectangle(), evaluation=[dict(reference_id='other', WQ=1), dict(reference_id='ref', WQ=None)])
    rows = calibration_errors([sample], real)
    assert len(rows) == 1 and rows[0]['generated_WQ'] is None and rows[0]['WQ_absolute_error'] is None


def test_matched_comparison_does_not_drop_unscorable_rows():
    common = dict(image_id='im', reference_id='ref', source_worker_profile_id='1', building_id='A', source_quality='higher')
    rows = matched_comparison([dict(common, variant='current_baseline', WQ=80), dict(common, variant='hierarchical', WQ=None)])
    assert len(rows) == 1 and not rows[0]['common_evaluable']
    assert rows[0]['delta_WQ'] is None
