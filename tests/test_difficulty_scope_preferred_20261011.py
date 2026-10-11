import pytest

from tools.thesis_main.analysis.difficulty_scope_preferred_20261011 import choose_target, classify, build, OUT, read


def candidate(role, h):
    return dict(role=role, features=dict(H=h))


def test_scope_preference_is_not_minimum_score():
    old, new = candidate('selected_gt', 0), candidate('confirmed_scope', 2)
    assert choose_target([old, new]) is old
    old['features']['H'] = 3
    assert choose_target([old, new]) is new
    new['features']['H'] = 0
    assert choose_target([old, new]) is new
    old['features']['H'] = 0
    assert choose_target([old, new]) is new


def test_geometry_is_not_photo_inference():
    assert classify(6, 'low', False) == '简单'
    assert classify(4, 'high', False) == '困难'
    assert classify(12, 'moderate', False) == '中等'
    assert classify(4, 'undetermined', False) == '待复核'
    assert classify(4, 'low', True) == '单列'
    with pytest.raises(AssertionError):
        classify(4, 'missing', False)


def test_all_images_and_provenance():
    rows = build()
    assert len(rows) == len({r['image_id'] for r in rows}) == 259
    assert sum(len(r['candidates']) == 2 for r in rows) == 33
    assert sum(r['current_class'] == '单列' for r in rows) == 42
    assert all(r['reviewed'] and r['evidence'] and r['target_version'] for r in rows)
    assert all(r['selected'] == choose_target(r['candidates']) for r in rows)
    by = {r['image']: r for r in rows}
    assert by['jtcxE69GiFV-05']['current_class'] == '待复核'
    assert by['rPc6DW4iMge-05']['H'] > 0
    assert by['rPc6DW4iMge-05']['current_class'] == '中等'
    assert by['q9vSo1VnCiC-11']['current_class'] == '简单'
    assert by['x8F5xyUWy9e-09']['conditional_difficulty'] == '简单'
