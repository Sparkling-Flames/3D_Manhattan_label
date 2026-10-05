import copy
import json

import pytest
from shapely.geometry import Polygon

from tools.thesis_main.analysis.lee_tile_stage1_20261002 import ROOT
from tools.thesis_main.analysis.point_route_panel_20261005 import build_routes
from tools.thesis_main.analysis.point_route_review_20261006 import connection_review, partial_correspondences


def records():
    path = ROOT/'research/layout_reliability_20261005/pro_original/inputs/rPc6DW4iMge-06.json'
    return json.loads(path.read_text(encoding='utf-8'))['records']


def repeat_source():
    source = next(r for r in records() if r['id'] == 'R01518')
    return source, [dict(copy.deepcopy(source), id=f'control{i}', worker=f'control{i}') for i in range(3)]


def test_unanimous_valid_non_x_ring_keeps_observed_order():
    source, rows = repeat_source()
    before = copy.deepcopy(rows)
    result = build_routes(rows, 5.)['paired']
    review = connection_review(result)
    candidate = review['unanimous']['candidate']
    assert candidate['points'] == source['points']
    assert candidate['ring_confirmed'] is False
    assert review['unanimous']['support'] == 3
    a, b = Polygon(candidate['footprint']), Polygon(result['candidate']['footprint'])
    assert a.intersection(b).area/a.union(b).area == pytest.approx(.7215692890736957)
    assert rows == before


def test_conflicting_observed_orders_do_not_choose_largest_support():
    _, rows = repeat_source()
    pairs = list(zip(rows[2]['points'][::2], rows[2]['points'][1::2]))
    rows[2]['points'] = [p for pair in sorted(pairs, key=lambda pair: pair[0][0]) for p in pair]
    review = connection_review(build_routes(rows, 5.)['paired'])
    assert review['unanimous'] is None
    assert sorted(r['support'] for r in review['observed_orders']) == [1, 2]
    assert review['reason'] == 'no_full_roster_order_agreement'


def test_partial_pairs_survive_an_isolated_endpoint_without_becoming_a_ring():
    result = build_routes(records(), 10.)['split_unique']
    partial = partial_correspondences(result)
    assert result['candidate']['points'] is None
    assert len(partial['pairs']) == 8
    assert [(g['side'], g['degree']) for g in partial['unresolved_endpoints']] == [('top', 0)]
    assert partial['full_pairing_complete'] is False
    assert partial['is_complete_layout'] is False
    assert all(g['center'] and g['joint_support'] <= min(g['top_support'], g['bottom_support']) for g in partial['pairs'])


def test_degree_gate_is_not_reported_as_global_matching_uniqueness():
    rows = []
    for i in range(3):
        pairs = [(128., 80., 400. if i < 2 else 450.)]
        pairs += [(138., 120., 450.)] if i < 2 else []
        pairs += [(x, 120., 390.) for x in (384., 640., 896.)]
        rows.append(dict(id=f'control{i}', worker=f'control{i}', points=[[x, y] for x, t, b in pairs for y in (t, b)]))
    partial = partial_correspondences(build_routes(rows, 2.)['split_unique'])
    assert len(partial['pairs']) == 3
    assert len(partial['unresolved_endpoints']) == 4
    assert partial['matching_uniqueness_assessed'] is False
    assert partial['full_pairing_complete'] is False


def test_review_page_keeps_method_and_reference_outside_payload(tmp_path, monkeypatch):
    from tools.thesis_main.analysis import point_route_review_view_20261006 as viewer
    monkeypatch.setattr(viewer, 'project', lambda r: r.get('view', {}))
    panel = dict(schema='point_route_panel_v1', images=[dict(image='case', image_id='no_photo',
        records=[dict(id='R1', worker='P1', points=[[1, 2], [1, 3]], view={})],
        lee=dict(region=None, status='method_only_sentinel'), states=[],
        extra_candidate='candidate_only_sentinel')])
    inputs = {'candidates.json': panel,
              'review_cases.json': [dict(id='window', image='case', record_ids=['R1'])],
              'evaluations.json': dict(references=[dict(image='case', record=dict(view={'gt': 'reference_only_sentinel'}))])}
    for name, value in inputs.items():
        (tmp_path/name).write_text(json.dumps(value), encoding='utf-8')
    viewer.build(tmp_path)
    review = (tmp_path/'review.html').read_text(encoding='utf-8')
    comparison = (tmp_path/'index.html').read_text(encoding='utf-8')
    assert 'R1' in review
    assert all(s not in review for s in ('method_only_sentinel', 'candidate_only_sentinel', 'reference_only_sentinel'))
    assert 'candidate_only_sentinel' in comparison
    assert 'reference_only_sentinel' not in comparison
    assert 'reference_only_sentinel' in (tmp_path/'evaluation_projection.json').read_text(encoding='utf-8')


def test_feasible_target_triple_can_be_blocked_by_an_existing_worker_assignment():
    from tools.thesis_main.analysis.point_route_review_20261006 import probe_correspondence
    def member(rid, worker, pair_index, x):
        return dict(id=rid, worker=worker, pair_index=pair_index, points=[[x, 120.], [x, 390.]])
    a, b = member('a', 'P1', 0, 100.), member('b', 'P2', 0, 104.)
    c, wrong = member('c', 'P3', 0, 108.), member('c', 'P3', 1, 101.)
    groups = [dict(feature_id='g1', support=2, members=[a, wrong]),
              dict(feature_id='g2', support=2, members=[b, c])]
    before = copy.deepcopy(groups)
    value = probe_correspondence(groups, [('a', 0), ('b', 0), ('c', 0)], 'pair', 5., 12)
    assert value['local_group_feasible'] and not value['same_group']
    assert value['same_worker_merge_conflicts'][0]['worker'] == 'P3'
    assert not any(g['selected'] for g in value['target_groups'])
    assert groups == before
    with pytest.raises(KeyError):
        probe_correspondence(groups, [('a', 99)], 'pair', 5., 12)


def test_bottom_compatibility_does_not_certify_an_upper_target():
    from tools.thesis_main.analysis.point_route_review_20261006 import probe_correspondence
    members = [dict(id=str(i), worker=str(i), pair_index=0, points=[[128., t], [128., 390.]])
               for i, t in enumerate([80., 120., 120.])]
    value = probe_correspondence([dict(feature_id='g', support=3, members=members)],
                                [(str(i), 0) for i in range(3)], 'bottom', 5., 2)
    assert value['same_group'] and value['local_group_feasible']
    assert value['diameters_deg']['bottom'] == 0
    assert value['diameters_deg']['top'] == pytest.approx(40/512*180)
    assert 'physical_identity_confirmed' not in value
