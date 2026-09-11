import copy
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.build_scene_image_exploration import expand_judgments, inventory, apply_coarse_review

ROOT = Path(__file__).resolve().parents[1]


def test_complete_visual_review_and_user_confirmations():
    raw = inventory(ROOT)
    decisions = json.loads((ROOT / 'analysis_results/scene_image_exploration_20260910_v1/ai_visual_judgments.json').read_text(encoding='utf8'))
    rows = expand_judgments(raw, decisions)
    assert len(rows) == 648
    assert len({r['image_id'] for r in rows}) == 648
    assert all(r['review_basis'] == 'contact_sheet_visual_first_pass' for r in rows)
    assert sum(bool(r['prior_user_room']) for r in rows) == 5
    assert {r['prior_user_room'] for r in rows if r['prior_user_room']} == {'r1', 'r2'}
    assert all(r['user_type'] == '' for r in rows)
    assert all(r['user_doorway'] == '' and r['user_artifact'] == '' for r in rows)
    assert all(r['ai_doorway'] == 'not_reviewed' for r in rows)
    assert all(r['ai_coarse_type'] for r in rows)
    assert {r['ai_coarse_type'] for r in rows if r['ai_type'] == 'X'} == {'mixed_unknown'}
    coarse = {}
    for name in ('coarse_recheck_part1.json', 'coarse_recheck_part2.json'):
        part = json.loads((ROOT / 'analysis_results/scene_image_exploration_20260910_v1' / name).read_text(encoding='utf8'))
        assert not set(coarse) & set(part)
        coarse.update(part)
    apply_coarse_review(rows, coarse)
    assert all(r['coarse_review_basis'] == 'second_pass_image_visual_review' for r in rows)
    assert any(r['ai_type'] == 'X' and r['ai_coarse_type'] != 'mixed_unknown' for r in rows)
    assert sum(bool(r['prior_user_room']) for r in rows) == 5


def test_missing_or_duplicate_assignment_is_rejected():
    raw = [dict(image_id='b_one', building='b', number=1, split='test', path='one.png'),
           dict(image_id='b_two', building='b', number=2, split='test', path='two.png')]
    decision = {'b': {'groups': [['B', '1 2', 'same bed/window']], 'threshold': '', 'possible': '', 'note': ''}}
    assert len(expand_judgments(raw, decision)) == 2
    missing = copy.deepcopy(decision)
    missing['b']['groups'][0][1] = '1'
    with pytest.raises(ValueError):
        expand_judgments(raw, missing)
    duplicate = copy.deepcopy(decision)
    duplicate['b']['singles'] = {'1': 'W'}
    with pytest.raises(ValueError):
        expand_judgments(raw, duplicate)


def test_unknown_boundary_number_is_rejected():
    raw = [dict(image_id='b_one', building='b', number=1, split='test', path='one.png')]
    decision = {'b': {'groups': [], 'singles': {'1': 'U'}, 'threshold': '2', 'possible': '', 'note': ''}}
    with pytest.raises(ValueError):
        expand_judgments(raw, decision)


def test_coarse_review_uses_new_visual_decisions_and_rejects_missing_coverage():
    rows = [dict(building='b', number=1, ai_type='X', ai_coarse_type='mixed_unknown', user_type='我的类别', user_room='r1')]
    decisions = {'b': {'codes': 'W', 'notes': {'1': '近景卫浴明确，门外走道不决定类型'}}}
    apply_coarse_review(rows, decisions)
    assert rows[0]['ai_coarse_type'] == 'bathroom'
    assert rows[0]['coarse_review_basis'] == 'second_pass_image_visual_review'
    assert rows[0]['ai_type'] == 'X' and rows[0]['user_type'] == '我的类别'
    assert rows[0]['user_room'] == 'r1'
    with pytest.raises(ValueError):
        apply_coarse_review(rows, {})
    with pytest.raises(ValueError):
        apply_coarse_review(rows, {'b': {'codes': 'W W'}})
    with pytest.raises(ValueError):
        apply_coarse_review(rows, {'b': {'codes': '?'}})
