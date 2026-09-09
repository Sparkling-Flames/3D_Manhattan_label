from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import changes, window_state

import json
from itertools import combinations

import pandas as pd
import pytest

from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import replay, short_window_check


def test_support_promotion_and_multimodal_stability():
    # An old singleton becoming supported must be detected, even without a new identity.
    d = changes([{0, 1}, {2}], [{0, 1}, {2, 3}])
    assert d['membership'] == 0
    assert d['promotions'] == [0, 1, 0]
    assert window_state([d], [2, 1, 0], 2, .2) == 'changing'
    d = changes([{0, 1}, {2, 3}], [{0, 1, 4}, {2, 3, 5}])
    assert window_state([d], [2, 2, 0], 2, .1) == 'stable'
    d = changes([{0, 1}, {2, 3}], [{0, 1}, {2, 3}, {4}])
    assert window_state([d], [2, 2, 0], 1, .2) == 'changing'
    assert window_state([d], [2, 2, 0], 2, .2) == 'stable'
    assert window_state([d], [2, 0, 0], 2, .2) == 'unknown'
    assert window_state([None], [2, 2, 0], 2, .2) == 'unknown'
    # Same people change from together to separate: 1 of the 3 old pairs changes.
    d = changes([{0, 1}, {2}], [{0}, {1}, {2, 3}])
    assert abs(d['membership'] - 1 / 3) < 1e-12


def test_short_windows_scope_and_input_coverage(tmp_path):
    geometry = tmp_path / 'geometry'
    geometry.mkdir()
    responses, pairs = [], []
    for image, n in [('one', 1), ('three', 3), ('six', 6)]:
        for i in range(n):
            responses.append(dict(image_id=image, building_id='b', canonical_annotation_id=f'{image}_{i}',
                worker_id=str(i), effective_point_count=4, q_geometry_valid=True))
        for i, j in combinations(range(n), 2):
            pairs.append(dict(image_id=image, left_canonical=f'{image}_{i}', right_canonical=f'{image}_{j}',
                count_compatible=True, ospa30=0., pointwise_correspondence_compatible=True,
                metric_compatible=True, q_boundary=1., q_wallwall=1.))
    pd.DataFrame(responses).to_csv(geometry / 'response_geometry.csv', index=False)
    pd.DataFrame(pairs).to_csv(geometry / 'pairwise_q.csv.gz', index=False)
    orders = tmp_path / 'orders.jsonl'
    orders.write_text('\n'.join(json.dumps(dict(replicate=i, worker_ids=list(range(6)))) for i in range(200)))
    out = tmp_path / 'short'
    qa = replay(geometry, out, lookaheads=(1, 2, 3), configs=('q_0.950', 'ospa30_t6'), orders_path=orders)
    curves = pd.read_csv(out / 'stability_curves.csv')
    assert qa['images'] == 3 and qa['responses'] == 10 and qa['images_without_windows'] == 1
    assert set(curves.config) == {'q_0.950', 'ospa30_t6'}
    assert set(curves.lookahead) == {1, 2, 3} and 'one' not in set(curves.image_id)
    short = curves[(curves.image_id == 'three') & (curves.config == 'q_0.950') &
                   (curves.min_support == 2) & (curves.epsilon == .1)]
    assert set(zip(short.k, short.lookahead)) == {(1, 1), (2, 1), (1, 2)}
    assert (short.loc[short.k == 1, 'unknown'] == 200).all()
    assert short.loc[short.k == 2, 'stable'].tolist() == [200]
    filtered = tmp_path / 'filtered'
    qa = replay(geometry, filtered, min_workers=4, configs=('q_0.950',), orders_path=orders, image_ids=('six',))
    curves = pd.read_csv(filtered / 'stability_curves.csv')
    assert qa['images'] == 1 and qa['responses'] == 6 and set(curves.lookahead) == {3, 5}
    assert qa['image_ids'] == ['six'] and qa['input_images'] == 3
    assert set(curves.image_id) == {'six'}
    with pytest.raises(ValueError, match='missing_image_ids'):
        replay(geometry, tmp_path / 'missing', image_ids=('missing',), orders_path=orders)
    with pytest.raises(ValueError, match='requested_images_below_min_workers'):
        replay(geometry, tmp_path / 'below', image_ids=('three',), min_workers=4, orders_path=orders)
    # A repeated pair cannot substitute for an absent pair, even at the correct row count.
    pairs[-1] = pairs[-2]
    pd.DataFrame(pairs).to_csv(geometry / 'pairwise_q.csv.gz', index=False)
    with pytest.raises(ValueError, match='pair_coverage'):
        replay(geometry, tmp_path / 'bad', min_workers=4, configs=('q_0.950',), orders_path=orders)
    pd.DataFrame(responses[:1]).to_csv(geometry / 'response_geometry.csv', index=False)
    pd.DataFrame(pairs).iloc[:0].to_csv(geometry / 'pairwise_q.csv.gz', index=False)
    out = tmp_path / 'singleton'
    qa = replay(geometry, out, lookaheads=(1,), configs=('q_0.950',), orders_path=orders)
    assert qa['window_metrics'] == 0 and qa['images_without_windows'] == 1
    assert pd.read_csv(out / 'stability_curves.csv').empty
    assert len(pd.read_csv(out / 'image_members.csv')) == 1


def test_early_stability_can_change_when_a_new_cluster_gains_support(tmp_path):
    replay_dir = tmp_path / 'replay'
    replay_dir.mkdir()
    pd.DataFrame([dict(image_id=image, building_id='b', canonical_annotation_id=f'{image}_{w}', worker_id=str(w))
                  for image, n in [('dense', 16), ('small', 3)] for w in range(n)]).to_csv(
                      replay_dir / 'image_members.csv', index=False)
    prefix = [{0, 1}, {2}]
    later = [[{0, 1, 3}, {2}], [{0, 1, 3}, {2, 4}], [{0, 1, 3, 5}, {2, 4}],
             [{0, 1, 3, 5, 6}, {2, 4}], [{0, 1, 3, 5, 6, 7}, {2, 4}]]
    deltas = [changes(prefix, p) for p in later]
    assert window_state(deltas[:1], [2, 1, 0], 2, .1) == 'stable'
    assert window_state(deltas, [2, 1, 0], 2, .1) == 'changing'
    rows = []
    for config in ['q_0.950', 'q_0.925', 'ospa30_t6']:
        for replicate in range(200):
            for k in [2, 3, 4]:
                for h in [1, 2, 3, 5]:
                    ds = deltas[:h] if replicate == 0 and k == 3 else [dict(membership=0., shares=0., promotions=[0, 0, 0])]
                    unknown = k == 3 and (replicate == 2 or (replicate == 1 and h > 1))
                    rows.append(dict(image_id='dense', config=config, replicate=replicate, k=k, lookahead=h,
                        status='unknown_partition' if unknown else 'evaluated', prefix_support_2=1,
                        max_membership=None if unknown else max(d['membership'] for d in ds),
                        max_shares=None if unknown else max(d['shares'] for d in ds),
                        promotion_2=None if unknown else max(d['promotions'][1] for d in ds)))
    pd.DataFrame(rows).to_csv(replay_dir / 'window_metrics.csv.gz', index=False)
    out = tmp_path / 'check'
    qa = short_window_check(replay_dir, out)
    counts = pd.read_csv(out / 'image_state_counts.csv')
    row = counts[(counts.config == 'q_0.950') & (counts.k == 3) & (counts.lookahead == 1)].iloc[0]
    assert qa['images'] == 1 and qa['excluded_low_n_images'] == 1 and len(counts) == 27
    assert row.early_stable_later_stable_n == 197
    assert row.early_stable_later_changing_n == 1 and row.early_stable_later_unknown_n == 1
    assert row.early_unknown_later_unknown_n == 1
    assert row.early_stable_n == 199 and row.early_stable_later_evaluable_n == 198
    assert row.early_stable_to_later_stable_rate == pytest.approx(197 / 199)
    assert row.early_stable_to_later_unknown_rate == pytest.approx(1 / 199)
    assert qa['long_window_includes_early_window'] and not qa['independent_validation']
    pd.DataFrame(rows[:-1]).to_csv(replay_dir / 'window_metrics.csv.gz', index=False)
    with pytest.raises(ValueError, match='incomplete_window_pairing'):
        short_window_check(replay_dir, tmp_path / 'bad')
