import copy

import numpy as np

from tools.thesis_main.analysis import simulate_annotators as sim


def rectangle(shift=0):
    return [[(x + shift) % 1024, y] for x in [64, 320, 576, 832] for y in [150, 370]]


def bank():
    return {family: dict(name=family, layout_id=family, points=rectangle(i * 40))
            for i, family in enumerate(sim.FAMILIES)}


def record(iid, building, worker='1', shift=0):
    return dict(image_id=iid, building_id=building, worker_id=worker,
                annotation_id=iid + ':' + worker, points=rectangle(shift))


def test_seam_cycle_and_direction_preserve_distance_and_residual():
    p = np.asarray(rectangle(960)).reshape(-1, 2, 2)
    q = np.roll(p[::-1], 2, axis=0).reshape(-1, 2)
    assert sim.distance(p.reshape(-1, 2), q) < 1e-5
    assert np.allclose(sim.residual(p.reshape(-1, 2), q), 0)
    shifted = q.copy()
    shifted[:, 0] = (shifted[:, 0] + 2) % 1024
    assert np.allclose(sim.residual(p.reshape(-1, 2), shifted)[:, 0], 2)


def test_point_pair_endpoint_order_does_not_change_unordered_distance():
    p = np.asarray(rectangle()).reshape(-1, 2, 2)
    assert sim.distance(p.reshape(-1, 2), p[:, ::-1].reshape(-1, 2)) < 1e-5


def test_heldout_answer_changes_cannot_change_simulations():
    models = {'train': bank(), 'target': bank(), 'other_target_room': bank()}
    rows = [record('train', 'A'), record('target', 'B'), record('other_target_room', 'B')]
    first = sim.fit_holdout(rows, models, 'B')
    changed = copy.deepcopy(rows)
    changed[1]['points'] = rectangle(120)
    changed[2]['points'] = rectangle(220)
    second = sim.fit_holdout(changed, models, 'B')
    assert first == second
    assert first['training_annotation_ids'] == ['train:1']
    a = sim.simulate(models['target'], first, ['1', 'unseen_worker'], 'worker', 17, 'target')
    b = sim.simulate(models['target'], second, ['1', 'unseen_worker'], 'worker', 17, 'target')
    assert a == b
    assert all(x['residual_donor_building_id'] != 'B' for x in a)


def test_equal_heads_share_credit_without_arbitrary_persona():
    models = {'train': {f: dict(name=f, layout_id=f, points=rectangle()) for f in sim.FAMILIES}}
    learned = sim.fit([record('train', 'A')], models)
    assert np.allclose(learned['profiles']['1'], [1 / 3] * 3)
    assert np.allclose(learned['pooled'], [1 / 3] * 3)


def test_different_workers_learn_different_preferences():
    models = {f'i{i}': bank() for i in range(12)}
    rows = [record(iid, 'A', worker, shift) for iid in models for worker, shift in [('1', 0), ('2', 80)]]
    learned = sim.fit(rows, models)
    assert learned['profiles']['1'][0] > learned['profiles']['2'][0]
    assert learned['profiles']['2'][2] > learned['profiles']['1'][2]


def test_invalid_outputs_preserved_and_not_exported_as_valid_points():
    bad = rectangle()
    bad[0][1] = -30
    assert not sim.parsed(bad)
    sample = dict(simulation_id='bad', points=bad, geometry_status=sim.geometry_status(bad))
    scores = sim.comparison([rectangle(), rectangle(2)], [sample, sample])
    assert scores['basic_parse_failure_rate'] == 1
    assert scores['human_to_sim_nearest_deg'] == 180
    result = sim.ls_task('target', {'image_url': 'example.png'}, [sample])
    assert result['predictions'] == []
    assert result['data']['omitted_unparseable_simulations'] == ['bad']
    assert result['data']['synthetic'] is True


def test_predictions_are_not_human_annotations_or_scope_answers():
    sample = dict(simulation_id='synthetic', points=rectangle())
    task = sim.ls_task('target', {'image_url': 'example.png'}, [sample])
    assert 'annotations' not in task
    assert all(r['type'] == 'keypointlabels' for r in task['predictions'][0]['result'])
    assert task['predictions'][0]['result'][0]['value']['x'] == 6.25


def test_frozen_random_seed_is_repeatable_and_distinct_between_images():
    assert sim.seed_for(42, 'x', 'worker') == sim.seed_for(42, 'x', 'worker')
    assert sim.seed_for(42, 'x', 'worker') != sim.seed_for(42, 'y', 'worker')
