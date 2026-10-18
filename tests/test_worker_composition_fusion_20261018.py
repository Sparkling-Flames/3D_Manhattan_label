import copy
from pathlib import Path

import pytest
import pandas as pd

from tools.thesis_main.analysis import worker_composition_fusion_20261018 as replay


def test_member_geometry_reuse_invalidates_only_changed_member_and_reference():
    old = {'records': [{'id': 'R1', 'worker': 'P1', 'points': [[1, 2]], 'source_pair_indices': [0]},
                       {'id': 'R2', 'worker': 'P2', 'points': [[3, 4]], 'source_pair_indices': [0]}],
           'reference': {'target_id': 'old'}}
    current = copy.deepcopy(old)
    current['records'][0]['points'][0][1] = 20
    assert replay.changed_records(old, current) == {'R1'}
    states = {'R1': {}, 'R2': {}, 'R1|R2': {}}
    assert set(replay.compatible_states(states, replay.changed_records(old, current))) == {'R2'}
    current = copy.deepcopy(old)
    current['reference']['target_id'] = 'new'
    assert replay.changed_records(old, current) == set()
    assert not replay.same_measurement_reference(old, current)


def test_request_identity_keeps_order_but_geometry_key_is_member_set():
    records = [{'id': 'R2', 'worker_id': 'W2'}, {'id': 'R1', 'worker_id': 'W1'}]
    selected, key = replay.resolve_members({'worker_ids': ['W2', 'W1'], 'k': 2}, records)
    assert key == 'R1|R2'
    assert [r['worker_id'] for r in selected] == ['W1', 'W2']
    with pytest.raises(ValueError, match='duplicate'):
        replay.resolve_members({'worker_ids': ['W1', 'W1'], 'k': 2}, records)
    with pytest.raises(ValueError, match='missing'):
        replay.resolve_members({'worker_ids': ['W3'], 'k': 1}, records)


def test_quality_mask_preserves_existing_binding_and_holdout():
    im = {'layer': 'ordinary', 'reference': {'target_id': 'target'}}
    selected = [{'chosen_target_id': 'target', 'quality_usable': True, 'original_holdout': False}]
    assert replay.quality_flags(im, selected) == (True, True, True)
    selected[0]['original_holdout'] = True
    assert replay.quality_flags(im, selected) == (True, True, False)
    selected[0]['chosen_target_id'] = ''
    assert replay.quality_flags(im, selected) == (False, False, False)
    selected[0]['chosen_target_id'] = 'target'
    im['layer'] = 'oos_diagnostic'
    assert replay.quality_flags(im, selected) == (True, False, False)


def test_fixed_background_exchange_rejects_reordering_and_multiple_replacements():
    a = dict(worker_ids=['W1', 'W2', 'W3', 'W4', 'W5', 'W6'], k=6, image_code='im', condition='manual')
    b = dict(a, worker_ids=['W1', 'W2', 'W3', 'W4', 'W5', 'W7'])
    assert replay.single_exchange_meta(a, b) == dict(shared_workers=5, outgoing_worker='W6', incoming_worker='W7')
    with pytest.raises(ValueError, match='single_person'):
        replay.single_exchange_meta(a, dict(a, worker_ids=list(reversed(a['worker_ids']))))
    with pytest.raises(ValueError, match='single_person'):
        replay.single_exchange_meta(a, dict(b, worker_ids=['W1', 'W2', 'W3', 'W4', 'W7', 'W8']))
    with pytest.raises(ValueError, match='same_pool'):
        replay.single_exchange_meta(a, dict(b, image_code='other'))
    with pytest.raises(ValueError, match='background'):
        replay.single_exchange_meta(dict(a, background_worker_ids=['W1'], entrant_worker_id='W6'), b)


def test_strict_geometry_content_ignores_ring_origin_but_detects_top_change():
    pairs = [[[10, 100], [10, 400]], [[260, 100], [260, 400]],
             [[510, 100], [510, 400]], [[760, 100], [760, 400]]]
    floor = [[-1, -1], [-1, 1], [1, 1], [1, -1]]
    def state(order):
        return dict(candidate=dict(points=[p for i in order for p in pairs[i]], footprint=[floor[i] for i in order],
                                   geometry_status='ok'), node_consensus={'nodes': [{'points': pairs[i]} for i in order]})
    a, b = state([0, 1, 2, 3]), state([1, 0, 3, 2])
    assert replay.geometry_content_comparison(a, b) == dict(floor_geometry_equal=True, full_geometry_equal=True, node_content_equal=True)
    c = copy.deepcopy(b)
    c['candidate']['points'][0][1] += 1
    result = replay.geometry_content_comparison(a, c)
    assert result['floor_geometry_equal'] and not result['full_geometry_equal'] and not result['node_content_equal']
    c['candidate']['geometry_status'] = 'invalid'
    assert replay.geometry_content_comparison(a, c)['full_geometry_equal'] is None


def test_actual_replay_keeps_k2_missing_and_geometry_pointer(tmp_path, monkeypatch):
    points = [[80, 120], [80, 380], [300, 120], [300, 380],
              [570, 120], [570, 380], [810, 120], [810, 380]]
    records = [dict(id='R'+str(i), worker='P'+str(i), worker_id='W'+str(i), object_id='O'+str(i),
                    points=points, source_pair_indices=list(range(4)), ring_confirmed=False,
                    chosen_target_id='ref', quality_usable=True, original_holdout=False,
                    source_time_seconds=None) for i in range(3)]
    reference = dict(target_id='ref', reference_version='test', points_1024x512=points,
                     floor_xz_h=replay.reconstruct(records[0])['floor'].tolist(), full_reference_available=True)
    im = dict(pool_id='sample__manual', image='sample', image_id='sample-id', building='sample-building',
              condition='manual', layer='ordinary', difficulty='test', scene='clear', records=records, reference=reference)
    monkeypatch.setattr(replay, 'OUT', tmp_path/'output')
    monkeypatch.setattr(replay, 'ROOT', tmp_path)
    monkeypatch.setattr(replay, 'OLD', tmp_path/'old')
    monkeypatch.setattr(replay, 'PRIOR_COMPOSITION', tmp_path/'prior')
    monkeypatch.setattr(replay, 'load_cache', lambda im: ({}, {}, {}, set()))
    replay.run_pool(im, [dict(request_id='test'+str(k), request_family='fine_composition',
                             worker_ids=['W'+str(i) for i in range(k)], k=k) for k in (2, 3)])
    frame = pd.read_csv(tmp_path/'output/pools/sample__manual/team_results.csv')
    two = frame[frame.k.eq(2)].iloc[0]
    three = frame[frame.k.eq(3)].iloc[0]
    assert two.score_status == 'two_person_deferred' and pd.isna(two.B8L2)
    assert three.complete_evaluable and 0 < three.B8L2 <= 100
    assert three.iou2d100 == pytest.approx(100)
    assert three.source_time_available == False
    assert three.source_time_missing_n == 3 and three.target_time_missing_n == 3
    assert pd.isna(three.source_time_known_sum)
    assert three.data_release == 'v1'
    assert Path(tmp_path/three.geometry_source).exists()
