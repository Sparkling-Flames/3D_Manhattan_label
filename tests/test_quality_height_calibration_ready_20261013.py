import copy

import numpy as np
import pytest

from tools.thesis_main.analysis import quality_height_calibration_ready_20261013 as q


def test_height_modes_keep_floor_and_decompose_mean_and_shape():
    e = q.engine()
    g = q.rectangle(1, 4)
    original = copy.deepcopy(g)
    for offsets in ([.2]*4, [-.2, .2, .2, -.2], [.4, 0, 0, 0]):
        row = q.control(g, offsets, e)
        assert row['metrics']['Hmean'] == pytest.approx(row['exact_Hm'], abs=1e-10)
        assert row['metrics']['Hcenter'] == pytest.approx(row['exact_Hc'], abs=5e-6)
    spike = q.control(g, [.4, 0, 0, 0], e)
    assert spike['metrics']['Hmean'] > 0 and spike['metrics']['Hcenter'] > 0
    assert g == original


def test_bounded_candidates_change_one_height_scale_only():
    e = q.engine()
    configs = q.configurations(e, q.read(q.OUT/'DESIGN.json'))
    base = configs['main']
    assert len(configs) == 5
    for name, config in configs.items():
        changed = {k for k in config if config[k] != base[k]}
        assert changed <= {'global_scale', 'local_scale'}
        assert len(changed) == (0 if name == 'main' else 1)


def test_evidence_does_not_turn_component_preference_into_overall_label():
    data = dict(rows=[dict(id='a', building_id='x'), dict(id='b', building_id='y')],
                grades=[dict(id='a', grade=1), dict(id='b', grade=2)],
                constraints=[dict(dimension='self_geometry_without_reference',
                                  evidence_type='explicit_direction', preferred_record_id='b', other_record_id='a')])
    result = q.evidence(data, np.array([90., 80.]))
    assert result['explicit_overall'] == []
    assert result['weak_grade_pairs'] == 1 and result['weak_grade_inversions'] == 0
    assert all(r['weak_grade_pairs'] == 0 for r in result['leave_one_evidence_building_out'])


def test_output_contract_preserves_fit_and_diagnostic_boundary():
    prep = q.read(q.OUT/'PREPARATION.json')
    result = q.read(q.OUT/'COMPARISON.json')
    controls = q.read(q.OUT/'CONTROLS.json')
    ids = {r['record_id'] for r in prep['records_ledger']}
    assert len(ids) == 574 and ids == {r['record_id'] for r in result['records']}
    assert not ids.intersection(r['record_id'] for r in result['historical_diagnostics'])
    assert sum(r['severe_exception'] for r in result['historical_diagnostics']) == 9
    assert len(controls['records']) == prep['new_control_count']+prep['reused_control_count'] == 110
    assert result['selection']['promoted'] is False
    assert all(s['passes_explicit_overall_gate'] for s in result['summary'].values())
    stair = next(r for r in result['recent_shape_diagnostics'] if r['record_id']=='R00977')
    assert 'candidate_components' not in stair
    for row in result['records']:
        assert set(row['candidate_components']) == set(result['configs'])
        assert all(np.isfinite(v['score']) for v in row['candidate_components'].values())
