import pandas as pd

from tools.thesis_main.analysis.worker_exchangeability_20261018 import (
    absolute_profiles, exchange_design, matched_blocks, aggregate_blocks,
)


def test_absolute_profiles_exclude_target_building():
    panel = pd.DataFrame([dict(worker_id='W1', building_id=b, image_id=f'{b}{i}', B8L2=score, D10=score)
        for b, score in [('target', 100), ('a', 20), ('b', 40), ('c', 60)] for i in range(2)])
    result = absolute_profiles(panel, ['target'])
    row = result[result.metric.eq('B8L2')].iloc[0]
    assert row.absolute_Q == 40
    assert row.absolute_n == 6 and row.absolute_supported
    assert 'target' not in row.absolute_training_buildings


def test_nested_background_and_exact_single_replacement():
    profiles = pd.DataFrame([dict(fold='b', metric='B8L2', worker_id=f'W{i:02d}',
        AbsQ3='high' if i < 4 else 'low', RelQ3='high' if i < 4 else 'low',
        RelQT4='higher_faster' if i < 4 else 'lower_slower',
        absolute_Q=80-i, Q_effect=10-i, T_source_effect=i-5) for i in range(20)])
    pool = dict(image_code='b-01', image_id='b_id', building_id='b', scene_bucket='neither_flagged',
        worker_ids=profiles.worker_id.tolist(), original_holdout_member_n=0)
    requests, pairs, support = exchange_design(profiles, {'b-01': pool}, ['b-01'])
    teams = {r['request_id']: r for r in requests}
    for pair in pairs:
        a, b = teams[pair['request_a']], teams[pair['request_b']]
        assert len(set(a['worker_ids']) & set(b['worker_ids'])) == a['k']-1
        assert a['background_worker_ids'] == b['background_worker_ids']
    chains = {}
    for row in requests:
        if row['variant'] == 'anchor':
            chains.setdefault(row['chain_id'], []).append(row)
    for chain in chains.values():
        chain.sort(key=lambda row: row['k'])
        for a,b in zip(chain,chain[1:]):
            assert b['background_worker_ids'][:a['k']-1] == a['background_worker_ids']
    assert len(requests) == 2*3*2*2*4*3


def test_matched_summary_drops_both_v_arms_when_one_is_unavailable():
    rows = []
    for block, values in [('x', (.1,.3)), ('y', (float('nan'),0.))]:
        for kind,v in zip(['same_class','cross_class'],values):
            rows.append(dict(exchange_block_id=block, chain_id=block, image_code='b-1', building_id='b',
                scene_bucket='ordinary', scheme='RelQ3', k=8, anchor_class='high', request_a='a'+block,
                request_b=kind+block, comparison_id=kind+block, swap_kind=kind,
                floor_jaccard_difference=v, B8_delta=1., abs_B8_delta=1., abs_D10_delta=1.,
                node_count_changed=False, annotation_floor_jaccard_distance=.2,
                full_geometry_equal=False, node_content_equal=False, floor_geometry_equal=False))
    blocks = matched_blocks(pd.DataFrame(rows))
    summary = aggregate_blocks(blocks,['image_code','scheme','k']).iloc[0]
    assert summary.V_blocks == 1 and summary.Q_blocks == 2
    assert summary.same_V == .1 and summary.cross_V == .3
    assert summary.same_node_changed_rate == 0
    assert summary.same_full_geometry_equal_rate == 0


def test_frozen_real_design_has_same_background_single_exchange_and_nested_sizes():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'research/workers/worker_exchangeability_20261018/TEAM_REQUESTS.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    requests = {r['request_id']:r for r in data['requests']}
    assert len(requests) == 3840 and len(data['comparisons']) == 2560
    assert data['personal_quality_axes'] == ['absolute_Q','relative_Q']
    for p in data['comparisons']:
        a,b = requests[p['request_a']],requests[p['request_b']]
        assert set(a['worker_ids']) - set(b['worker_ids']) == {p['entrant_a']}
        assert set(b['worker_ids']) - set(a['worker_ids']) == {p['entrant_b']}
        assert a['background_worker_ids'] == b['background_worker_ids']
    anchors = pd.DataFrame(r for r in requests.values() if r['variant']=='anchor')
    for _,d in anchors.groupby('chain_id'):
        assert sorted(d.k)==[6,8,12,16]
        d=d.sort_values('k')
        last=d.iloc[-1].background_worker_ids
        assert all(last[:r.k-1] == r.background_worker_ids for r in d.itertuples())


def test_delivered_transfer_preserves_discovery_check_pair_and_missing_geometry():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / 'research/workers/worker_exchangeability_20261018'
    pairs=pd.read_csv(path/'exchange_analysis.csv').set_index('comparison_id')
    transfer=pd.read_csv(path/'background_transfer.csv')
    assert len(transfer)==1280
    for row in transfer.itertuples():
        a,b=pairs.loc[row.comparison_id_discovery],pairs.loc[row.comparison_id_check]
        assert (a.image_code,a.k,a.entrant_a,a.entrant_b,a.triplet_id,a.swap_kind)==(
            b.image_code,b.k,b.entrant_a,b.entrant_b,b.triplet_id,b.swap_kind)
        assert a.background_id==0 and b.background_id==1
        assert row.discover_small_floor_001==(pd.notna(a.floor_jaccard_difference) and a.floor_jaccard_difference<=.01)
    assert pairs[pairs.B8L2_difference.isna()].B8_delta.isna().all()
    assert pairs[pairs.full_geometry_equal.isna()].both_complete.eq(False).all()
