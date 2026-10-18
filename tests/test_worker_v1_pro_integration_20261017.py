import json
from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.worker_v1_pro_integration_20261017 import (
    corrected_residual_statement, compatible_clear_scope, pure_focus_prefix,
)


def test_residual_review_includes_both_still_not_right_comments():
    for oid in ['b62a4df9e1645fe7', '717840fe8221eba6']:
        assert corrected_residual_statement(oid, ['这个改了一点模型的预标注,但是还是不太对'], 'changed_coordinates')
        assert not corrected_residual_statement(oid, ['这个改了一点模型的预标注,但是还是不太对'], 'unchanged_coordinates')
    assert corrected_residual_statement('28935ccbb578589d', ['这错误预标注他也没改对'], 'changed_coordinates')
    assert not corrected_residual_statement('other', ['这个改了一点模型的预标注,但是还是不太对'], 'changed_coordinates')


def test_clear_scope_does_not_create_new_gold():
    assert compatible_clear_scope(True, 'in_scope', 'clear', 'not_oos')
    assert not compatible_clear_scope(False, 'in_scope', 'clear', 'not_oos')
    assert not compatible_clear_scope(True, 'in_scope', 'doorway', 'not_oos')
    assert not compatible_clear_scope(True, 'oos', 'clear', 'not_oos')


def test_group_priority_is_not_always_a_pure_group():
    assert pure_focus_prefix(True, 3, 3)
    assert not pure_focus_prefix(True, 2, 3)
    assert not pure_focus_prefix(False, 0, 1)


def test_actual_integration_keeps_denominators_and_original_verdicts():
    out = Path(__file__).resolve().parents[1] / 'research/workers/worker_v1_pro_integration_20261017'
    s = pd.read_csv(out / 'semi_correction_evidence.csv')
    assert len(s) == 574
    assert s.confirmed_initialization_error_opportunity.sum() == 156
    assert s.known_error_unchanged.sum() == 25
    assert s.changed_error_specific_residual_unknown.sum() == 131
    three = s[s.reviewer_residual_after_edit_statement]
    assert set(three.object_id) == {'b62a4df9e1645fe7', '717840fe8221eba6', '28935ccbb578589d'}
    assert three.source_verdict.eq('usable').all()
    assert not three.confirmed_initialization_error_opportunity.any()
    bridge = pd.read_csv(out / 'correction_definition_bridge.csv')
    assert (bridge.old_opportunity & bridge.strong_gold_opportunity).sum() == 144
    assert (bridge.old_opportunity & ~bridge.strong_gold_opportunity).sum() == 144
    assert (~bridge.old_opportunity & bridge.strong_gold_opportunity).sum() == 12
    records = pd.read_csv(out / 'record_evidence.csv')
    assert len(records) == 3222 and records.object_id.is_unique
    f = records.set_index('object_id').loc['f21c670566821ce7']
    assert f.cleaning_disposition == 'excluded_by_review'
    assert f.exclusion_attribution_pending and not f.in_Q_training
    assert f.scope_historical_outcome == 'correct_rejection'
    status = json.loads((out / 'CHECKS.json').read_text(encoding='utf-8'))
    assert status['team_requests'] == 14845 and status['team_completed'] == 14603
    assert status['Q_training'] == 1048 and not status['source_files_changed_during_run']
