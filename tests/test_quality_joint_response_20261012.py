from pathlib import Path

import pytest

from tools.thesis_main.analysis.quality_top_height_response_20261012 import read_json, profile_moments
from tools.thesis_main.analysis.quality_joint_response_20261012 import operator_effects, configurations, make_control, run

STUDY=Path(__file__).resolve().parents[1]/'research/quality_top_height_response_20261012'


def candidates():
    return configurations(read_json(STUDY/'inputs.json'),read_json(STUDY/'protocol.json'))


def test_max_can_completely_hide_local_error_while_sum_retains_it():
    m=make_control(1.5,.1,2)['metrics']
    cs=candidates()
    a=operator_effects(m,cs['Q_dbounded1_max_height'])
    b=operator_effects(m,cs['relative2'])
    assert a['local_marginal_points']==pytest.approx(0)
    assert a['local_visibility_fraction']==0
    assert a['local_structurally_blocked']
    assert not b['local_structurally_blocked']
    assert b['local_marginal_points']>0


def test_sum_preserves_loss_but_reciprocal_score_compresses_marginal_drop():
    cs=candidates()
    base=operator_effects(make_control(1,.1,2)['metrics'],cs['relative2'])
    severe=operator_effects(make_control(2,.1,2)['metrics'],cs['relative2'])
    assert severe['local_loss']==base['local_loss']==pytest.approx(.16)
    assert 0<severe['local_visibility_fraction']<.1
    assert severe['local_marginal_points']<base['local_marginal_points']


def test_operator_ablation_zeroes_log_ratio_and_handles_no_local_effect():
    m=make_control(2,0,2)['metrics']
    effect=operator_effects(m,candidates()['log4'])
    assert effect['local_visibility_fraction'] is None
    assert effect['score_both_height_zero']==pytest.approx(100)
    assert effect['global_marginal_points']>0


def test_angular_tradeoff_can_reverse_component_order():
    cs=candidates()
    a,b=(make_control(r,.2,.5) for r in (1,1.2))
    x,y=(operator_effects(c['metrics'],cs['relative4_weakTop']) for c in (a,b))
    assert y['global_loss']>x['global_loss']
    assert y['local_loss']==x['local_loss']
    assert y['top_loss']<x['top_loss']
    assert y['score']>x['score']


def test_control_geometry_is_independent_and_domain_not_scored():
    c=make_control(.8,.1,10)
    a,g=c['annotation'],c['reference']
    assert a['bottom3d']==g['bottom3d']
    assert a['bottom3d'] is not g['bottom3d']
    for geo in (a,g):
        for b,t in zip(geo['bottom3d'],geo['top3d']):
            assert (b[0],b[2])==(t[0],t[2])
    assert profile_moments(a)['mean']==pytest.approx(1.92)
    assert profile_moments(a)['std']/2.4==pytest.approx(.1)
    bad=make_control(.5,.2,2)
    assert bad['status']=='out_of_camera_domain'
    assert bad['metrics'] is None


def test_frozen_replay_keeps_boundaries_and_reports_grid_comparisons():
    out=run(read_json(STUDY/'inputs.json'),read_json(STUDY/'protocol.json'),read_json(STUDY/'results.json'),read_json(STUDY/'joint_response_design.json'))
    assert out['schema']=='quality_joint_response_results_v1'
    assert len(out['controls'])==120
    assert sum(c['status']=='available' for c in out['controls'])==108
    assert len(out['records'])==907 and len(out['coordinate_groups'])==739
    assert out['verification']['maximum_previous_score_delta']<1e-10
    assert out['verification']['previous_score_cells']==8163
    assert set(out['monotonicity'])==set(candidates())
    assert all(p['high_resolution_score_delta']>0 for m in out['monotonicity'].values() for p in m['comparisons'] if p['score_delta']>1e-8)
    assert all(r['human_grade'] is None for r in out['selected_cases'])
