import copy

import numpy as np

from tools.thesis_main.analysis.semi_edit_distribution import fit_distribution, generate_edit


def ring(xs=(64, 320, 576, 832), shift=0):
    return [[(x + shift) % 1024, y] for x in xs for y in (140, 370)]


def move_record(annotation_id, worker, building, shift):
    return dict(annotation_id=annotation_id, worker_id=worker, building_id=building,
        image_id=building + '_image', purpose='normal_candidate', behavior='move',
        initial_points=ring(), final_points=ring(shift=shift), final_pairing_verified=True)


def addition_record():
    initial = ring()
    final = ring((64, 192, 320, 576, 832))
    return dict(annotation_id='add1', worker_id='2', building_id='E', image_id='E_image',
        purpose='normal_candidate', behavior='addition', initial_points=initial,
        final_points=final, final_pairing_verified=True)


def test_move_distribution_is_building_excluded_and_keeps_joint_delta_and_cap():
    records = [move_record('a', '1', 'A', 4), move_record('b', '2', 'B', 8),
        move_record('held', '3', 'Z', 40), move_record('trap', '4', 'C', 80)]
    records[-1]['purpose'] = 'trap'
    fitted = fit_distribution(records, 'Z')
    assert fitted['training_annotation_ids'] == ['a', 'b']
    assert fitted['training_buildings'] == ['A', 'B']
    assert len(fitted['moves']) == 2
    assert fitted['cap'][0] > 0
    assert all(len(row['global_delta']) == 3 for row in fitted['moves'])
    assert all(np.asarray(row['local_delta']).shape == (4, 3) for row in fitted['moves'])
    assert all(row['global_delta'][0] > 0 for row in fitted['moves'])


def test_move_model_preserves_joint_horizontal_top_and_bottom_directions():
    initial = np.asarray(ring()).reshape(-1, 2, 2)
    final = initial.copy()
    final[:, :, 0] = (final[:, :, 0] + 9) % 1024
    final[:, 0, 1] += 3
    final[:, 1, 1] -= 5
    record = dict(annotation_id='joint', worker_id='1', building_id='A', image_id='A_image',
        purpose='normal_candidate', behavior='move', initial_points=initial.reshape(-1, 2).tolist(),
        final_points=final.reshape(-1, 2).tolist(), final_pairing_verified=True)
    model = fit_distribution([record], 'Z')['moves'][0]
    assert model['global_delta'] == [9 / 1024, 3 / 512, -5 / 512]
    assert np.allclose(model['local_delta'], 0)


def test_generation_is_repeatable_for_different_proposal_corner_count_and_wraps_seam():
    fitted_distribution = fit_distribution([
        move_record('a', '1', 'A', 8), move_record('b', '2', 'B', 12)], 'Z')
    fitted = dict(heldout='Z', profiles={'3': {'quality': 'uncertain', 'prototype': None}},
        channels={'semi_distribution': fitted_distribution})
    proposal = ring((950, 30, 300, 600, 800))
    before = copy.deepcopy(proposal)
    first, trace = generate_edit(proposal, fitted, '3', 77)
    second, trace2 = generate_edit(proposal, fitted, '3', 77)
    assert first == second and trace == trace2
    assert len(first) == len(proposal)
    assert proposal == before
    assert trace['semi_status'] == 'generated_move'
    assert trace['semi_actual_behavior'] == 'move'
    assert trace['semi_global_source']['building_id'] != 'Z'
    assert all(src['building_id'] != 'Z' for src in trace['semi_local_sources'])
    assert np.all((np.asarray(first).reshape(-1, 2, 2)[:, :, 0] >= 0))
    assert np.all((np.asarray(first).reshape(-1, 2, 2)[:, :, 0] < 1024))
    assert len(first) == 10


def test_addition_is_learned_as_weak_support_and_transfers_fraction_to_new_edge():
    distribution = fit_distribution([move_record('m', '1', 'A', 4), addition_record()], 'Z')
    assert distribution['counts']['addition'] == 1
    assert distribution['additions'][0]['weak_support']
    fitted = dict(heldout='Z', profiles={'2': {'quality': 'uncertain', 'prototype': None}},
        channels={'semi_distribution': distribution})
    output, trace = generate_edit(ring((70, 330, 590, 850)), fitted, '2', 12,
        requested_behavior='addition')
    assert trace['semi_status'] == 'generated_addition'
    assert trace['semi_addition_weak_support']
    assert trace['semi_addition_source']['annotation_id'] == 'add1'
    assert len(output) == 10


def test_heldout_addition_and_unlearned_behavior_fall_back_to_empirical_move():
    records = [move_record('m', '1', 'A', 4), addition_record()]
    no_addition = fit_distribution(records, 'E')
    assert no_addition['counts']['addition'] == 0
    fitted = dict(heldout='E', profiles={'3': {'quality': 'uncertain', 'prototype': None}},
        channels={'semi_distribution': no_addition})
    output, trace = generate_edit(ring(), fitted, '3', 12, requested_behavior='addition')
    assert trace['semi_status'] == 'generated_move_fallback'
    assert trace['semi_actual_behavior'] == 'move'
    assert trace['semi_edit_fallback_reason'] == 'no_building_excluded_addition_evidence'
    assert len(output) == 8
    _, unsupported = generate_edit(ring(), fitted, '3', 12, requested_behavior='deletion')
    assert unsupported['semi_status'] == 'generated_move_fallback'
    assert 'no_normal_training_support:deletion' in unsupported['semi_edit_fallback_reason']


def test_no_move_evidence_is_failure_and_does_not_add_fixed_noise():
    fitted_distribution = fit_distribution([addition_record()], 'E')
    fitted = dict(heldout='E', profiles={}, channels={'semi_distribution': fitted_distribution})
    proposal = ring()
    output, trace = generate_edit(proposal, fitted, '3', 7)
    assert output == proposal
    assert trace['semi_status'] == 'no_learned_move_distribution'


def test_outcome_scores_cannot_change_learned_edit_parameters():
    record = move_record('a', '1', 'A', 8)
    changed = copy.deepcopy(record)
    changed.update(WQ=0, IoU3D100=0, reference_id='target-answer')
    assert fit_distribution([record], 'Z') == fit_distribution([changed], 'Z')
