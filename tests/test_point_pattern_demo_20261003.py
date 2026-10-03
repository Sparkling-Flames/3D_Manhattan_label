import copy

import numpy as np
import pytest

from tools.thesis_main.analysis.point_pattern_demo_20261003 import build_patterns


def record(index, dx=0., top=105., bottom=390., reverse=False):
    pairs = np.array([[[x+dx, top], [x+dx, bottom]] for x in (2., 250., 510., 760.)])
    pairs[:, :, 0] %= 1024
    if reverse:
        pairs = np.roll(pairs[::-1], 2, axis=0)
    return dict(id=f'R{index}', worker=f'P{index}', points=pairs.reshape(-1, 2).tolist(),
                source_pair_indices=[7, 3, 9, 2], order_status='confirmed', ring_confirmed=True)


def test_patterns_preserve_ring_and_singletons_and_fuse_complete_periodic_pairs():
    records = [record(0, -4), record(1), record(2, 4, reverse=True)]
    frozen = copy.deepcopy(records)
    view = build_patterns(records)[0]
    assert records == frozen
    assert len(view['clusters']) == 1
    group = view['clusters'][0]
    assert group['support'] == 3
    assert group['representative'] == 'R1'
    candidate = group['candidate']
    assert candidate['status'] == 'ok'
    pairs = np.array(candidate['points']).reshape(-1, 2, 2)
    assert np.allclose(pairs, np.array(records[1]['points']).reshape(-1, 2, 2))
    assert np.array_equal(pairs[:, 0, 0], pairs[:, 1, 0])
    assert candidate['point_support_counts'] == [3]*4
    assert len(candidate['footprint']) == 4
    assert view['all_members_candidate'] == candidate
    assert build_patterns(records[::-1]) == [view]
    single = build_patterns([records[2]])[0]['clusters'][0]
    assert single['candidate']['points'] == records[2]['points']
    assert single['candidate']['source_pair_maps'][0]['source_pair_indices'] == [7, 3, 9, 2]


def test_top_and_bottom_both_affect_groups_and_gt_cannot_select_a_pattern():
    records = [record(0), record(1, top=140), record(2, bottom=430)]
    original = build_patterns(records)
    assert len(original[0]['clusters']) == 3
    assert original[0]['all_members_candidate']['status'] == 'unavailable'
    assert original[0]['all_members_candidate']['reason'] == 'multiple_annotation_patterns_no_cross_structure_fusion'
    for r in records:
        r['gt'] = {'points': record(99)['points'], 'iou': 1 if r['id'] == 'R2' else 0}
        r['quality_score'] = 999
    assert build_patterns(records) == original
    with pytest.raises(TypeError):
        build_patterns(records, references={'original': record(99)})
    bad = copy.deepcopy(records)
    bad[1]['worker'] = bad[0]['worker']
    with pytest.raises(ValueError, match='duplicate_worker'):
        build_patterns(bad)


def test_different_counts_and_unavailable_points_are_kept_in_denominator():
    a, b, c = record(0), record(1), record(2)
    b['points'] = b['points'] + [[870., 105.], [870., 390.]]
    b['source_pair_indices'] += [11]
    c['points'] = None
    view = build_patterns([a, b, c])[0]
    assert view['k'] == 3
    assert sum(g['support'] for g in view['clusters']) == 3
    assert sorted(len(g['members']) for g in view['clusters']) == [1, 1, 1]
    assert next(g for g in view['clusters'] if g['members'] == ['R2'])['candidate']['status'] == 'unavailable'
    assert view['all_members_candidate']['status'] == 'unavailable'
