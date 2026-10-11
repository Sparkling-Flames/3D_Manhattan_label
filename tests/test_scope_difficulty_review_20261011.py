import copy
import pytest

from tools.thesis_main.analysis.scope_difficulty_review_20261011 import (
    floor_features, assemble, read, ROOT, OUT, PRIOR,
)


def test_straight_vertex_is_not_a_turn_but_near_straight_is_retained():
    square = [[-1, -1], [1, -1], [1, 1], [0, 1], [-1, 1]]
    f = floor_features(square)
    assert (f['N_floor'], f['N_turn'], f['H']) == (5, 4, 0)
    assert f['straight_vertices_1based'] == [4]
    near = copy.deepcopy(square)
    near[3][1] += .001
    assert floor_features(near)['N_turn'] == 5
    assert floor_features(square[::-1])['H'] == 0


def test_invalid_floor_is_not_zero_occlusion():
    assert floor_features([[2, 2], [3, 2], [3, 3], [2, 3]])['H'] is None


def test_real_review_partition_and_unchanged_images():
    old = read(PRIOR / 'review_data.json')
    refs = read(OUT / 'reference_registry_snapshot.json')['records']
    notes = read(OUT / 'visual_decisions.json')['records']
    reviews, current = assemble(old, refs, notes)
    assert len(reviews) == 35 and len(current) == 259
    assert len({r['image_id'] for r in current}) == 259
    revised = {r['image_code'] for r in refs if r['in_current_formal_corpus']}
    baseline = {r['image']: r for r in old}
    assert len(revised) == 33
    for r in current:
        if r['image'] not in revised:
            assert r['current_class'] == baseline[r['image']]['visual']['difficulty_recommendation']
            assert r['scope_review'] is None
    assert all(r['top_boundary_pending'] and not r['reference_ready'] for r in reviews)
    assert all(bool(r['question']) == r['needs_user_review'] for r in reviews)
    assert all(r['scene'] == baseline[r['image']]['scene'] for r in current)


def test_duplicate_or_wrong_image_binding_is_rejected():
    old = read(PRIOR / 'review_data.json')
    refs = read(OUT / 'reference_registry_snapshot.json')['records']
    notes = read(OUT / 'visual_decisions.json')['records']
    with pytest.raises(AssertionError):
        assemble(old, refs, notes + notes[:1])
    bad = copy.deepcopy(refs)
    bad[0]['image_id'] = 'wrong-image'
    with pytest.raises(AssertionError):
        assemble(old, bad, notes)
