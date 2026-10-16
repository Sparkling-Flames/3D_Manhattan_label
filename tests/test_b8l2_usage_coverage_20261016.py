import pandas as pd
import pytest

from tools.thesis_main.analysis.b8l2_usage_coverage_20261016 import build_usage_coverage, scene_flags


def row(oid, **changes):
    result = dict(object_id=oid, worker_id='w', image_id='i'+oid, condition='manual',
        cleaning_disposition='retained', independent_vote_eligible=True, pool_source_workers=3,
        gt_error_excluded=False, is_doorway=False, is_oos=False,
        quality_usable=True, quality_exclusion_reasons=[], diagnostic_B8L2=50.,
        calculation_status='full_computed', full_score_state='computed', full_input_available=True,
        floor_input_available=True, reference_full_available=True, target_binding_unique=True)
    result.update(changes)
    return result


def test_scene_flags_do_not_invent_worker_choice_or_use_source_condition():
    flags = scene_flags(dict(scene='unflagged', doorway_status='not_recorded',
                             oos_subtype='not_recorded', condition='oos'))
    assert flags['scene_bucket'] == 'neither_flagged' and not flags['is_oos']
    assert flags['worker_unmarkable_choice'] == 'unknown_not_independently_recorded'
    both = scene_flags(dict(scene='oos_and_doorway', doorway_status='none', oos_subtype='not_recorded'))
    assert both['scene_bucket'] == 'both'


def test_exclusive_reason_and_overlapping_hits_keep_excluded_workers_and_scene_denominator():
    data = pd.DataFrame([
        row('a', worker_id='excluded', cleaning_disposition='historical_not_accepted',
            independent_vote_eligible=False, pool_source_workers=2, is_oos=True,
            quality_usable=False, quality_exclusion_reasons=['old_exclusion', 'old_exclusion']),
        row('b', is_doorway=True),
        row('c', is_oos=True, quality_usable=False, quality_exclusion_reasons=['oos_diagnostic_only']),
        row('d', is_doorway=True, is_oos=True, quality_usable=False,
            quality_exclusion_reasons=['oos_diagnostic_only']), row('e')])
    out = build_usage_coverage(data)
    records = out['record_reason_audit'].set_index('object_id')
    assert records.loc['a', 'primary_reason'] == 'old_cleaning_excluded'
    worker = out['worker_usage_summary'].set_index('worker_id').loc['excluded']
    assert worker.n_submissions == 1 and worker.n_old_cleaning_excluded == 1
    assert worker.n_source_pool_below3 == 1 and worker.n_oos_full_diagnostic == 1
    assert out['worker_primary_reasons'].n_records.sum() == len(data)
    assert set(records.scene_bucket) == {'neither_flagged', 'doorway_only', 'oos_only', 'both'}
    raw = out['worker_reason_hits'].query("reason_kind == 'raw_quality_exclusion' and reason == 'old_exclusion'")
    assert raw.iloc[0].n_records == 1
    assert not any('mean' in c for c in out['worker_usage_summary'])


def test_calculation_states_and_missing_scores_are_not_imputed_or_lost():
    data = pd.DataFrame([
        row('a'),
        row('b', calculation_status='floor_only_computed', full_score_state='pending_reference',
            reference_full_available=False, diagnostic_B8L2=None, quality_usable=False),
        row('c', calculation_status='input_uncomputable', full_score_state='input_uncomputable',
            full_input_available=False, floor_input_available=False, diagnostic_B8L2=None, quality_usable=False),
        row('d', calculation_status='pending_target', full_score_state='pending_target',
            target_binding_unique=False, diagnostic_B8L2=None, quality_usable=False),
        row('e', calculation_status='pending_reference', full_score_state='pending_reference',
            reference_full_available=False, diagnostic_B8L2=None, quality_usable=False),
        row('f', calculation_status='measurement_failed', full_score_state='measurement_failed',
            diagnostic_B8L2=None, quality_usable=False),
        row('g', calculation_status='not_run', full_score_state='not_run', diagnostic_B8L2=None,
            quality_usable=False)])
    out = build_usage_coverage(data)
    worker = out['worker_usage_summary'].iloc[0]
    assert worker.n_submissions == 7 and worker.n_quality_usable == 1
    assert worker.n_full_computed == worker.n_floor_only_computed == worker.n_not_run == 1
    assert worker.n_full_diagnostic_available == 1
    assert worker.n_full_score_pending_reference == 2
    assert worker.ratio_quality_usable == pytest.approx(1/7)
    assert out['worker_calculation_status'].n_records.sum() == 7
    with pytest.raises(ValueError, match='OOS'):
        build_usage_coverage(pd.DataFrame([row('bad', is_oos=True)]))
