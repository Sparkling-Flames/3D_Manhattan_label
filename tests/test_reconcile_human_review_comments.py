import copy
import csv
import io
import json
from pathlib import Path

import pytest

from tools.thesis_main.data_prep.reconcile_human_review_comments import FIELDS, reconcile, csv_value, attach_scope_readings, attach_supplements


def test_scope_readings_keep_quotes_expectations_and_quality_separate():
    root = Path(__file__).resolve().parents[1] / 'analysis_results/human_review_reconciliation_20260907_v1'
    bundle = json.loads((root / '原始问卷备份.json').read_text(encoding='utf-8'))
    rows = [dict(case_id=r['case_id'], human_record=r) for r in bundle['records']]
    readings = json.loads((root / 'scope_comment_readings.json').read_text(encoding='utf-8'))
    before = copy.deepcopy(bundle)
    attach_scope_readings(rows, readings)
    by_case = {r['case_id']:r['scope_reading'] for r in rows}
    assert bundle == before
    w2 = next(s for s in by_case['V09']['scope_statements'] if s['target'].startswith('W2'))
    assert w2['scope_label'] == 'enclosed' and not w2['annotation_ids']
    assert any('不是标的特别准确' == q['quote'] for q in by_case['V09']['quality_excerpts'])
    assert all(s['scope_label'] is None for s in by_case['V45']['scope_statements'])
    assert any('跨门' in s['quote'] for s in by_case['V45']['scope_statements'])
    assert all(s['scope_label'] is None for s in by_case['V22']['scope_statements'])
    assert by_case['V08']['scope_statements'] == []
    bad = copy.deepcopy(readings)
    bad[0]['scope_statements'][0]['quote'] = '不存在的人工评语'
    with pytest.raises(ValueError, match='quote'):
        attach_scope_readings(rows, bad)
    bad = copy.deepcopy(readings)
    bad[0]['scope_statements'][0]['scope_label'] = 'extended'
    with pytest.raises(ValueError, match='semantic'):
        attach_scope_readings(rows, bad)
    bad = copy.deepcopy(readings)
    bad[0]['scope_statements'][0]['final_user_decision'] = True
    with pytest.raises(ValueError, match='decision'):
        attach_scope_readings(rows, bad)


def test_next_actions_do_not_turn_all_prior_opinions_into_repeat_reviews():
    root = Path(__file__).resolve().parents[1] / 'analysis_results/human_review_reconciliation_20260907_v1'
    notes = json.loads((root / 'visual_followup_notes.json').read_text(encoding='utf-8'))
    assert len(notes) == len({r['case_id'] for r in notes}) == 50
    assert not any(r['next_action']['required_now'] for r in notes)
    assert not any(r['next_action']['actor'] == 'user' for r in notes)
    for r in notes:
        action = r['next_action']
        assert action['actor'] in ('user', 'assistant', 'rule', 'none')
        assert not action['required_now'] or action['actor'] == 'user'
        assert action['task'] and action['how_to_answer']
        assert r['final_user_decision'] is None


def test_human_supplements_preserve_original_answers_and_uncertainty():
    root = Path(__file__).resolve().parents[1] / 'analysis_results/human_review_reconciliation_20260907_v1'
    raw = json.loads((root/'原始问卷备份.json').read_text(encoding='utf-8'))['records']
    rows = [dict(case_id=r['case_id'], image_id=r['image_id'], human_record=r) for r in raw]
    before = copy.deepcopy(raw)
    supplements = json.loads((root/'human_supplements_20260908.json').read_text(encoding='utf-8'))
    attach_supplements(rows, supplements)
    assert raw == before
    assert len([r for r in rows if 'human_supplement' in r]) == 4
    by_case = {r['case_id']:r for r in rows}
    assert by_case['V48']['human_record']['answers']['scope'] == 'multiple_candidates'
    assert '就是不跨过' in by_case['V48']['human_supplement']['original_text']
    assert '我也不知道' in by_case['V27']['human_supplement']['original_text']
    assert all(not s['final_geometry_adjudicated'] for s in supplements)
    bad = copy.deepcopy(supplements)
    bad[0]['image_id'] = 'wrong'
    with pytest.raises(ValueError, match='identity'):
        attach_supplements(rows, bad)
    with pytest.raises(ValueError, match='duplicate'):
        attach_supplements(rows, supplements + supplements)


def test_preserves_uncertain_completed_answers_and_checks_csv_identity():
    answers = dict(visibility='clear', scope='uncertain', human_difference='scope',
                   annotation_assessment='all_questionable', oos_assessment='',
                   oos_reason='', factors=['scope', 'reference'], notes='=备注,"保留"\n仍不确定', status='reviewed')
    record = dict(case_id='V01', image_id='image1', answers=answers,
                  updated_at='2026-09-07', ai_advice_opened=True)
    bundle = dict(schema='panorama_human_review_v1', records=[record])
    before = copy.deepcopy(bundle)
    row = {key: csv_value(answers.get(key, record.get(key))) for key in FIELDS}
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerow(row)
    stream.seek(0)
    rows = list(csv.DictReader(stream))
    notes = [dict(case_id='V01', final_user_decision=None, evidence_viewed=['03_comparison.jpg'])]
    joined, differences = reconcile(bundle, rows, {'V01': 'image1'}, notes)
    assert not differences and bundle == before
    assert joined[0]['human_record'] == record
    assert joined[0]['final_user_decision'] is None
    assert joined[0]['human_record']['answers']['status'] == 'reviewed'
    rows[0]['scope'] = 'one_clear'
    _, differences = reconcile(bundle, rows, {'V01': 'image1'}, notes)
    assert differences == [dict(case_id='V01', field='scope', json_csv_value='uncertain', csv_value='one_clear')]
    with pytest.raises(ValueError, match='identity'):
        reconcile(bundle, rows, {'V01': 'other'}, notes)
    with pytest.raises(ValueError, match='duplicate'):
        reconcile(bundle, rows + rows, {'V01': 'image1'}, notes)
    with pytest.raises(ValueError, match='duplicate'):
        reconcile({**bundle, 'records': [record, record]}, rows, {'V01': 'image1'}, notes)
    with pytest.raises(ValueError, match='final'):
        reconcile(bundle, rows, {'V01': 'image1'}, [{**notes[0], 'final_user_decision': 'confirmed'}])


def test_saved_twelve_proposals_only_claim_ground_geometry_not_author_intent():
    from shapely.geometry import Polygon
    from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers
    root = Path(__file__).resolve().parents[1]
    review = root / 'analysis_results/uncertainty_visual_review_20260907_v1'
    check = root / 'analysis_results/human_review_reconciliation_20260907_v1/proposal_geometry_checks.json'
    audit, _ = helpers()
    proposals = {(r['case_id'], r['variant']): r for r in json.loads((review / 'preview_adjustment_proposals.json').read_text(encoding='utf-8')) if 'panel' in r}
    rows = json.loads(check.read_text(encoding='utf-8'))['rows']
    assert len(rows) == len(proposals) == 12
    for row in rows:
        p = proposals[row['case_id'], row['variant']]
        source = json.loads((review / 'cases' / row['case_id'] / (row['variant'] + '_source.json')).read_text(encoding='utf-8'))
        assert p['original_points'] == source['points']
        assert sorted(p['old_point_id_for_new_index']) == list(range(len(source['points'])))
        assert p['preview_points'] == [source['points'][i] for i in p['old_point_id_for_new_index']]
        for prefix, points in [('export_list', p['original_points']), ('proposal', p['preview_points'])]:
            floor, _, _ = audit.lift(points)
            poly = Polygon(floor[:, [0, 2]])
            assert row[prefix + '_floor_valid'] == poly.is_valid
            assert row[prefix + '_floor_boundary_simple'] == poly.exterior.is_simple
        assert not row['proposal_is_user_approved']
        assert not row['full_3d_surface_intersections_tested']
