import copy

from tools.thesis_main.analysis.point_route_panel_20261005 import build_routes, synthetic_controls


def test_four_pair_inputs_can_lose_one_identity_without_padding_raw_majority():
    rows = copy.deepcopy(synthetic_controls()['top_dispersion'])
    for row, x in zip(rows, (800., 860., 940.)):
        row['points'] = [[v, y] for v in (128., 384., 640., x) for y in (120., 390.)]
    assert all(len(row['points']) == 8 for row in rows)
    routes = build_routes(rows, 1.)
    for route, result in routes.items():
        assert len(result['candidate']['points']) == 6, route
        assert result['status'] == 'geometry_review', route
        assert result['vote_denominator'] == 3
    selected = [g for g in routes['paired']['identity_groups'] if g['selected']]
    assert len(selected) == 3
    assert sum(len(g['members']) for g in routes['paired']['identity_groups']) == 12


def test_single_endpoint_dispersion_and_marginal_joint_support():
    controls = synthetic_controls()
    rows = controls['top_dispersion']
    before = copy.deepcopy(rows)
    routes = build_routes(rows, 1.)
    assert rows == before
    assert routes['paired']['candidate']['status'] == 'unavailable'
    assert len(routes['bottom_anchor']['candidate']['points']) == 8
    assert routes['split_unique']['candidate']['status'] == 'unavailable'
    rows = controls['marginal_joint_vote_counterexample']
    split = build_routes(rows, 1.)['split_unique']
    assert len(split['candidate']['points']) == 8
    assert all((g['top_support'], g['bottom_support'], g['joint_support']) == (6, 6, 2)
               for g in split['paired_identities'])
    assert split['candidate']['point_support_counts'] is None
    assert split['ring_diagnostics']['exact_source_ring_support'] == 2


def test_split_ambiguous_link_is_retained_without_forced_pairing():
    rows = synthetic_controls()['top_dispersion'][:2]
    # n=2: both singleton top identities pass >=50%, one bottom identity passes.
    split = build_routes(rows, 1.)['split_unique']
    assert split['candidate']['points'] is None
    assert split['candidate']['reason'] == 'nonunique_or_missing_endpoint_pairing'
    assert split['pairing_graph']['ambiguous_top_or_bottom']
    assert len(split['pairing_graph']['edges']) == 8
    assert split['vote_denominator'] == 2


def test_split_shared_x_alignment_crosses_seam_without_rewriting_sources():
    rows = synthetic_controls()['top_dispersion']
    for i, row in enumerate(rows):
        row['points'] = [[x, y] for x in ((1022., 2., 6.)[i], 256., 512., 768.) for y in (120., 390.)]
    rows[0]['points'][1][1] = 480.
    rows[2]['points'][0][1] = 200.
    before = copy.deepcopy(rows)
    split = build_routes(rows, 2.)['split_unique']
    g = min(split['paired_identities'], key=lambda g: g['center'][0][0])
    assert g['center'] == [[2., 120.], [2., 390.]]
    assert g['x_adjustment_px'] == [2., -2.]
    assert (g['top_support'], g['bottom_support'], g['joint_support']) == (2, 2, 1)
    assert rows == before
