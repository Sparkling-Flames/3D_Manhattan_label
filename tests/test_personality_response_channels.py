import copy
import json
from pathlib import Path

import numpy as np
import pytest

from tools.thesis_main.analysis import simulate_annotators as base
from tools.thesis_main.analysis.personality_annotator_sampler import generate, fit_personality
from tools.thesis_main.analysis.personality_response_channels import (
    semi_transfer, sample_scope, sample_lead_time, fit_channels, normal_semi, validate_identity, positive, paired)
from tools.thesis_main.analysis.export_synthetic_label_studio import export_samples, synthetic_worker


def rect(shift=0):
    return [[(x + shift) % 1024, y] for x in (64, 320, 576, 832) for y in (150, 370)]


def donor(**values):
    return dict(annotation_id='d', worker_id='1', building_id='B', image_id='B1', condition='semi',
        initial_points=rect(), final_points=rect(2), final_pairing_verified=True,
        behavior='move', active_time_seconds=10, lead_time_seconds=20, time_context='B1|semi', weight=1., **values)


def fitted():
    d = donor()
    return dict(heldout='A', profiles={'1': dict(quality='uncertain', speed='uncertain', axes={})},
        channels=dict(semi=[d], times=[d], scope=[dict(d, condition='manual', response='in_scope', scene='clear')],
            scenes={'A1': 'clear'}, disputes={'A1': {}}, lead_effects={'manual': {}, 'semi': {}}, source_sha256={}))


@pytest.mark.parametrize('value', [None, '', 'nan', 'inf', '-1', 0])
def test_invalid_time_is_missing(value):
    assert positive(value) is None


def test_identity_join_fails_closed():
    a = dict(worker_id='1', image_id='A1', building_id='A', condition='semi')
    b = dict(a, worker_id='W001')
    validate_identity(a, b)
    b['image_id'] = 'other'
    with pytest.raises(ValueError, match='identity_mismatch'):
        validate_identity(a, b)


def test_only_current_normal_semi_allowed():
    gate = dict(role='semi_secondary_candidate', trap_status='confirmed_nontrap', original_holdout=False,
                personnel_barriers=[], context_barriers=[])
    assert normal_semi(gate)
    for value in ('confirmed_trap', 'unknown'):
        assert not normal_semi(dict(gate, trap_status=value))
    assert not normal_semi(dict(gate, original_holdout=True))


@pytest.mark.parametrize('behavior,final,status', [('copy', rect(), 'empirical_copy'),
    ('move', rect(2), 'empirical_edit'), ('deletion_and_move', rect(2)[:6], 'empirical_edit'),
    ('addition', rect() + [[950, 150], [950, 370]], 'unsupported_addition')])
def test_observed_semi_behavior(behavior, final, status):
    d = donor(); d.update(behavior=behavior, final_points=final)
    original = copy.deepcopy(d)
    output, actual = semi_transfer(rect(), d)
    assert actual == status and d == original
    if status == 'unsupported_addition':
        assert output == rect()
    if behavior == 'deletion_and_move':
        assert len(output) == 6


def test_ambiguous_pairing_is_not_guessed():
    d = donor(); d['final_pairing_verified'] = False
    assert semi_transfer(rect(), d)[1] == 'ambiguous_donor_pairing'
    assert not paired(rect()[::-1])


def test_bad_geometry_retained_instead_of_hidden():
    d = donor(); d['final_points'] = [[x, y - 500] for x, y in rect()]
    points, status = semi_transfer(rect(), d)
    assert min(y for x, y in points) < 0
    assert points != rect()


def test_scope_local_distribution_and_independent_variant():
    f = fitted()
    f['channels']['scope'].append(dict(donor(), image_id='A1', building_id='A', response='oos', scene='clear'))
    row = dict(image_id='A1', condition='semi', source_worker_profile_id='1')
    output = sample_scope(row, f, 42)
    assert output == sample_scope(row, f, 42)
    assert output['worker_scope_response'] == 'oos' and output['scope_pool'] == 'image_response_distribution'
    assert output['scope_variant'] in ('small', 'large') and not output['scope_geometry_bound']
    assert output['scope_condition_fallback'] is False


def test_scope_priors_exclude_building_and_record_cross_condition():
    f = fitted()
    row = dict(image_id='A2', condition='semi', source_worker_profile_id='1')
    out = sample_scope(row, f, 42)
    assert out['scope_pool'] == 'cross_condition_prior'
    assert out['scope_condition_fallback'] and out['scope_donor_building_id'] == 'B'


def test_lead_joint_donor_and_supported_shift():
    f = fitted(); row = dict(condition='semi', source_worker_profile_id='1', time_donor_annotation_id='d')
    out = sample_lead_time(row, f, 42)
    assert out['lead_time_seconds'] == pytest.approx(20) and out['lead_time_pool'] == 'active_time_joint_donor'
    f['channels']['lead_effects']['semi'] = {'1': dict(effect=.3, supported=True)}
    assert sample_lead_time(row, f, 42)['lead_time_status'] == 'simulated_task_effect'
    f['channels']['times'] = []
    assert sample_lead_time(row, f, 42)['lead_time_status'] == 'missing_evidence'


def test_channels_cannot_change_manual_geometry_or_select_heldout_donors():
    models = {iid: {family: dict(points=rect(), layout_id=family) for family in base.FAMILIES} for iid in ('A1', 'B1')}
    records = [dict(annotation_id='r', record_id='R1', worker_id='1', image_id='B1', building_id='B', points=rect(1),
        WQ=None, IoU3D100=None, active_time_seconds=None, reference_id=None, time_context=None)]
    f = fit_personality(records, models, 'A')
    before = generate(models['A1'], f, ['1'], 42, 'A1')[0]
    c = fitted()['channels']; c['semi'].append(dict(donor(), building_id='A'))
    fit_channels(c, f)
    after = generate(models['A1'], f, ['1'], 42, 'A1')[0]
    assert (before['points'], before['model_family']) == (after['points'], after['model_family'])
    semi = generate(models['A1'], f, ['1'], 42, 'A1', condition='semi')[0]
    assert semi['semi_donor_building_id'] == 'B'
    assert semi['initialization_trace']['manual_residual_applied'] is False
    assert semi['initial_points'] == rect() and semi['final_points'] == semi['points']


def export_fixture():
    return dict(simulation_id='sim', image_id='A1', condition='manual', source_worker_profile_id='1',
        points=rect(), synthetic=True, lead_time_seconds=20., lead_time_status='empirical', worker_scope_response='in_scope')


def test_export_reads_with_existing_parsers_and_isolates_workers(tmp_path):
    sample = export_fixture()
    exported, summary = export_samples([sample], {'A1': dict(image_url='image.png')}, tmp_path)
    assert exported == {'sim'} and summary['exported_annotations'] == 1
    task = json.loads((tmp_path / 'label_studio_synthetic.json').read_text())[0]
    annotation = task['annotations'][0]
    assert annotation['completed_by'].startswith('S_') and annotation['synthetic'] is True
    assert annotation['lead_time'] == 20 and annotation['worker_scope_response'] == 'in_scope'
    assert synthetic_worker('1', 'manual') != synthetic_worker('1', 'semi')


@pytest.mark.parametrize('field,value', [('points', [[0, -1]] * 8), ('lead_time_seconds', None), ('worker_scope_response', None)])
def test_export_rejects_without_silent_repair(tmp_path, field, value):
    sample = export_fixture(); sample[field] = value
    before = copy.deepcopy(sample)
    exported, summary = export_samples([sample], {'A1': dict(image_url='image.png')}, tmp_path)
    assert not exported and summary['rejected'] == 1 and sample == before


def test_export_unsupported_semi_is_not_counted_as_success(tmp_path):
    sample = dict(export_fixture(), condition='semi', semi_status='unsupported_addition')
    exported, summary = export_samples([sample], {'A1': dict(image_url='image.png')}, tmp_path)
    assert not exported and summary['rejected'] == 1


def test_generated_semi_move_is_exportable_and_keeps_synthetic_trace(tmp_path):
    sample = dict(export_fixture(), condition='semi', semi_status='generated_move',
        semi_generation_method='semi_edit_distribution_v2', synthetic=True,
        semi_global_source=dict(annotation_id='donor-1', pool='pooled', purpose='normal_candidate'),
        semi_local_sources=[dict(annotation_id='donor-2', pool='personal', purpose='normal_candidate')])
    exported, summary = export_samples([sample], {'A1': dict(image_url='image.png')}, tmp_path)
    assert exported == {'sim'} and summary['rejected'] == 0
    ledger = (tmp_path / 'private_worker_ledger.csv').read_text()
    assert 'semi_edit_distribution_v2' in ledger and 'normal_candidate' in ledger


def test_no_learned_move_status_remains_export_rejection(tmp_path):
    sample = dict(export_fixture(), condition='semi', semi_status='no_learned_move_distribution')
    exported, summary = export_samples([sample], {'A1': dict(image_url='image.png')}, tmp_path)
    assert not exported and summary['rejected'] == 1


def test_lead_invalid_shift_is_explicit_not_clamped():
    f = fitted()
    f['profiles']['2'] = dict(quality='uncertain', speed='uncertain', axes={})
    f['channels']['lead_effects']['semi'] = {'1': dict(effect=0., supported=True), '2': dict(effect=1000., supported=True)}
    row = dict(condition='semi', source_worker_profile_id='2')
    out = sample_lead_time(row, f, 42)
    assert out['lead_time_seconds'] is None and out['lead_time_status'] == 'invalid_effect_shift'


def test_scope_missing_remains_explicit():
    f = fitted(); f['channels']['scope'] = []
    out = sample_scope(dict(image_id='A1', condition='manual', source_worker_profile_id='1'), f, 42)
    assert out['worker_scope_response'] is None and out['scope_status'] == 'missing_evidence'
    assert out['scope_variant'] in ('small', 'large')


def test_fill_panel_counts_distinct_workers_per_arm():
    from tools.thesis_main.analysis.personality_incremental_run import target_panel
    sources = dict(records=[dict(image_id='custom', worker_id='1')] * 3,
        gates=[dict(image_id='custom')], models={})
    channels = dict(semi=[dict(image_id='custom', worker_id='2')] * 2)
    panel = target_panel(sources, channels, ['manual', 'semi'], 'fill-to-eight', False)
    custom = [r for r in panel if r['image_id'] == 'custom']
    assert len(custom) == 2
    assert all(r['current_allowed_real_people'] == 1 and r['requested_synthetic'] == 7 for r in custom)
    assert len({r['image_id'] for r in panel if r['candidate_166']}) == 166


def test_private_ledger_keeps_rejected_records(tmp_path):
    sample = dict(export_fixture(), lead_time_seconds=None)
    export_samples([sample], {'A1': dict(image_url='image.png')}, tmp_path)
    text = (tmp_path / 'private_worker_ledger.csv').read_text()
    assert 'rejected' in text and 'missing_valid_lead_time' in text
