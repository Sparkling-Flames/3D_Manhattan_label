from dataclasses import asdict
import json
import pandas as pd
import pytest

from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import choose_binding, dual_scores, model_parameters
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import OUT, ROOT


def test_d10_changes_only_direction_scale_and_keeps_l2():
    with scoring_engine() as (_, models):
        b, d = model_parameters(models)
        assert {k for k in asdict(b) if asdict(b)[k] != asdict(d)[k]} == {'version', 'direction_scale_deg'}
        assert d.pooling_order == 2 and d.direction_scale_deg == 10
        values = dict(iou_2d=.8, S_bottom_deg=2, dir=8, Hmean=.1, Hcenter=.05)
        result = dual_scores(values, models)
        assert result['D10'] > result['B8L2']
        values['dir'] = 0
        result = dual_scores(values, models)
        assert result['D10'] == result['B8L2']
        values['Hcenter'] = None
        with pytest.raises(ValueError):
            dual_scores(values, models)


def test_existing_binding_hold_survives_and_new_multiple_scope_stays_pending():
    fresh = dict(chosen_target_id='sole', binding_status='sole_admitted_space', pool_source_workers=5)
    old = dict(chosen_target_id='', binding_status='pending_target', pool_source_workers=2)
    result = choose_binding(fresh, old)
    assert result['chosen_target_id'] == '' and result['pool_source_workers'] == 5
    fresh.update(chosen_target_id='', binding_status='pending_multiple_admitted_spaces')
    assert choose_binding(fresh, None)['chosen_target_id'] == ''


def test_only_unresolved_geometric_gap_can_receive_new_route():
    fresh = dict(chosen_target_id='routed', binding_status='local_differentiating_structure')
    old = dict(chosen_target_id='', binding_status='pending_multiple_admitted_spaces')
    assert choose_binding(fresh, old)['chosen_target_id']=='routed'
    old.update(binding_status='explicit_manual_target',chosen_target_id='manual')
    assert choose_binding(fresh, old)['chosen_target_id']=='manual'
    old.update(binding_status='pending_manual_evidence_geometry_changed',chosen_target_id='')
    assert choose_binding(fresh, old)['chosen_target_id']==''


def test_delivery_keeps_diagnostic_scores_out_of_quality_and_old_values_unchanged():
    rows = pd.read_csv(OUT/'shared_records.csv')
    old = pd.read_csv(ROOT/'research/statistics/b8l2_usage_v6_20261016/quality_records.csv')
    assert len(rows) == 3222 and rows.object_id.is_unique
    qualified = rows[rows.quality_usable]
    assert not qualified.is_oos.any()
    assert rows.loc[~rows.quality_usable,['B8L2','D10']].isna().all().all()
    matched = old[['object_id','B8L2']].merge(qualified[['object_id','B8L2']],on='object_id',validate='one_to_one')
    assert len(matched) == len(old) and (matched.B8L2_x-matched.B8L2_y).abs().max() < 1e-8
    new = rows[rows.new_batch]
    assert new.target_binding_unique.all()
    floor_only = new[new.calculation_status.eq('floor_only_computed')]
    assert len(floor_only)==6
    assert floor_only[['B8L2','D10','diagnostic_B8L2','diagnostic_D10']].isna().all().all()
    bindings = pd.read_csv(OUT/'shared_bindings.csv')
    local = bindings[bindings.object_id.isin(new.object_id) & bindings.local_routing_evidence.notna()]
    assert len(local)==19 and local.local_routing_evidence.map(json.loads).map(
        lambda r:not r['quality_or_height_used_for_route'] and bool(r['uncertainty'])).all()
    assert len(new[new.quality_usable])==63
    held = rows[rows.image_code.eq('b8cTxDM8gDG-04')]
    assert len(held) and not held.quality_usable.any()
    assert all('current_user_review_pending' in json.loads(r) for r in held.quality_exclusion_reasons)
    assert rows.loc[rows.new_batch,'task_worker_active_seconds'].sum() == 5205
    assert rows.loc[rows.new_batch,'target_matched_time_seconds'].isna().all()
    frozen = pd.read_csv(ROOT/'research/statistics/b8l2_usage_v6_20261016/shared_records.csv')
    held_ids=set(frozen.loc[frozen[['same_target_quality_hold','latest_step_reference_pending','original_holdout']]
        .eq(True).any(axis=1), 'object_id'])
    assert not rows.loc[rows.object_id.isin(held_ids),'quality_usable'].any()
    assert rows.B8L2.notna().equals(rows.D10.notna())
    assert rows.analysis_layer.notna().all() and rows.difficulty_analysis_eligible.notna().all()
