"""图像的全人数前缀回放；候选稳定规则和未知状态显式保留。"""
import argparse
import csv
import gzip
import json
import sys
import time
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import partition

BASE = ROOT / 'analysis_results/multibuilding_threshold_stability_20260909_v1'
OUT = BASE / 'replay'
QS = (.975, .95, .925, .90, .85, .80)
CONFIGS = tuple(f'q_{q:.3f}' for q in QS) + ('ospa30_t6',)
EPS = (.05, .10, .20)
ORDERS = ROOT / 'analysis_results/building_holdout_exploration_20260908_v1/census/global_worker_orders.jsonl'


def changes(left, right):
    common = set().union(*left)
    total = set().union(*right)
    k, j = len(common), len(total)
    if not k or not common <= total or sum(map(len, left)) != k or sum(map(len, right)) != j:
        raise ValueError('partitions must contain distinct nested people')
    overlap = [[len(a & b) for b in right] for a in left]
    choose2 = lambda n: n * (n - 1) // 2
    before = sum(choose2(len(g)) for g in left)
    after = sum(choose2(len(g & common)) for g in right)
    both = sum(choose2(n) for row in overlap for n in row)
    return dict(membership=(before + after - 2 * both) / choose2(k) if k > 1 else 0.,
                shares=.5 * sum(abs(len(g & common) / k - len(g) / j) for g in right),
                promotions=[sum(len(g & common) < m <= len(g) for g in right) for m in (1, 2, 3)])


def window_state(deltas, prefix_support, min_support, epsilon):
    if not prefix_support[min_support - 1] or any(d is None for d in deltas):
        return 'unknown'
    return 'stable' if all(d['membership'] <= epsilon + 1e-12 and d['shares'] <= epsilon + 1e-12
                           and d['promotions'][min_support - 1] == 0 for d in deltas) else 'changing'


def replay(geometry_dir=BASE / 'geometry', out=OUT, *, lookaheads=(3, 5), min_workers=1,
           configs=CONFIGS, orders_path=ORDERS, image_ids=None):
    started = time.perf_counter()
    geometry_dir, out = Path(geometry_dir), Path(out)
    if not lookaheads or any(not isinstance(h, int) or h < 1 for h in lookaheads) or len(set(lookaheads)) != len(lookaheads):
        raise ValueError('lookaheads must be distinct positive integers')
    if not isinstance(min_workers, int) or min_workers < 1:
        raise ValueError('min_workers must be a positive integer')
    if not configs or len(set(configs)) != len(configs) or set(configs) - set(CONFIGS):
        raise ValueError('unknown_or_duplicate_configs')
    lookaheads = tuple(sorted(lookaheads))
    responses = pd.read_csv(geometry_dir / 'response_geometry.csv', dtype={'worker_id': str})
    pairs = pd.read_csv(geometry_dir / 'pairwise_q.csv.gz')
    response_fields = {'image_id', 'building_id', 'canonical_annotation_id', 'worker_id',
                       'q_geometry_valid', 'effective_point_count'}
    pair_fields = {'image_id', 'left_canonical', 'right_canonical', 'count_compatible', 'ospa30',
                   'pointwise_correspondence_compatible', 'metric_compatible', 'q_boundary', 'q_wallwall'}
    if response_fields - set(responses) or pair_fields - set(pairs):
        raise ValueError('missing_geometry_fields')
    if responses[list(response_fields)].isna().any().any() or responses.canonical_annotation_id.duplicated().any() or responses.duplicated(['image_id', 'worker_id']).any():
        raise ValueError('invalid_response_identity_or_missing_value')
    for frame, fields in [(responses, ['q_geometry_valid']),
                          (pairs, ['count_compatible', 'pointwise_correspondence_compatible', 'metric_compatible'])]:
        for field in fields:
            values = frame[field].astype(str).str.lower()
            if not values.isin(['true', 'false']).all():
                raise ValueError(f'invalid_boolean:{field}')
            frame[field] = values.eq('true')
    input_images, input_responses = responses.image_id.nunique(), len(responses)
    if image_ids is not None:
        if not image_ids or len(set(image_ids)) != len(image_ids):
            raise ValueError('image_ids must be nonempty and distinct')
        missing = set(image_ids) - set(responses.image_id)
        if missing:
            raise ValueError(f'missing_image_ids:{sorted(missing)}')
        responses = responses[responses.image_id.isin(image_ids)].copy()
    responses = responses[responses.groupby('image_id').worker_id.transform('size') >= min_workers].copy()
    if image_ids is not None and set(responses.image_id) != set(image_ids):
        raise ValueError('requested_images_below_min_workers')
    if responses.empty:
        raise ValueError('no_images_meet_min_workers')
    orders = [json.loads(line) for line in Path(orders_path).read_text(encoding='utf8').splitlines()]
    assert len(orders) == 200 and len({r['replicate'] for r in orders}) == 200
    out.mkdir(parents=True, exist_ok=True)
    plan = dict(status='exploratory_not_frozen', selection=f'input geometry images with >= {min_workers} distinct people; no q/stability selection',
        scope='all stages pooled; assistance_exposure=none; confirmed effective points; no same-image worker duplicates',
        geometry_dir=str(geometry_dir.resolve()), orders_path=str(Path(orders_path).resolve()),
        min_workers=min_workers, requested_image_ids=list(image_ids) if image_ids is not None else None,
        configs=list(configs), hard_effective_point_count_gate=True,
        q_geometry='historical pairing assumption; invalid geometry makes the containing prefix unknown',
        orders='200 existing global worker orders projected to each image; no within-image H/V budget truncation',
        windows=lookaheads, supports=[1, 2, 3], epsilons=EPS,
        stable='Every following j=k+1..k+h has unique partition; old-person pair relation change and share TV <=epsilon; no cluster first reaches m relative to k; at least one m-supported cluster already at k.',
        support_promotion='Includes a previously singleton cluster gaining its second supporter when m=2; not just clusters wholly absent at k.',
        unknown='Any required non-unique, truncated or invalid-geometry partition, or no m-supported prefix cluster.',
        bounds='stable/200 to (stable+unknown)/200; missing-state bounds, not confidence intervals',
        limit='finite-window retrospective replay; stable multiple clusters allowed; not accuracy, online stopping or proof of perpetual stability')
    (out / 'METHOD_PLAN.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf8')
    curves, members = [], []
    counts = Counter(subset_partitions=0, prefix_uses=0, window_metrics=0)
    window_fields = ['image_id', 'config', 'replicate', 'k', 'lookahead', 'status', 'max_membership', 'max_shares',
                     'prefix_support_1', 'prefix_support_2', 'prefix_support_3', 'promotion_1', 'promotion_2', 'promotion_3']
    part_fields = ['image_id', 'config', 'subset_mask', 'status', 'candidate_partition_count', 'clusters_positions_json']
    curve_fields = ['image_id', 'building_id', 'config', 'k', 'lookahead', 'min_support', 'epsilon',
                    'replicates', 'stable', 'changing', 'unknown', 'stable_lower', 'stable_upper', 'stable_single', 'stable_multi']
    with gzip.open(out / 'window_metrics.csv.gz', 'wt', newline='', encoding='utf8') as ws, \
         gzip.open(out / 'subset_partitions.csv.gz', 'wt', newline='', encoding='utf8') as ps:
        ww, pw = csv.DictWriter(ws, fieldnames=window_fields), csv.DictWriter(ps, fieldnames=part_fields)
        ww.writeheader(); pw.writeheader()
        for image_no, (image_id, rows) in enumerate(responses.groupby('image_id', sort=True), 1):
            rows = rows.sort_values('canonical_annotation_id').reset_index(drop=True)
            n, building = len(rows), rows.building_id.iloc[0]
            if rows.building_id.nunique() != 1:
                raise ValueError(f'building_identity_mismatch:{image_id}')
            ids = rows.canonical_annotation_id.tolist()
            pos = {key: i for i, key in enumerate(ids)}
            worker_pos = dict(zip(rows.worker_id, range(n)))
            invalid = set(rows.index[~rows.q_geometry_valid])
            qm, om = np.full((n, n), 1e6), np.full((n, n), 1e6)
            np.fill_diagonal(qm, 0); np.fill_diagonal(om, 0)
            pg = pairs[pairs.image_id == image_id]
            expected_pairs = set(combinations(sorted(ids), 2))
            actual_pairs = [tuple(sorted((p.left_canonical, p.right_canonical))) for p in pg.itertuples()]
            if len(pg) != len(expected_pairs) or set(actual_pairs) != expected_pairs:
                raise ValueError(f'pair_coverage:{image_id}')
            for p in pg.itertuples():
                a, b = pos[p.left_canonical], pos[p.right_canonical]
                if p.count_compatible != (rows.effective_point_count.iloc[a] == rows.effective_point_count.iloc[b]):
                    raise ValueError(f'point_count_gate_mismatch:{image_id}')
                if p.count_compatible:
                    assert np.isfinite(p.ospa30)
                    om[a, b] = om[b, a] = p.ospa30
                    if p.pointwise_correspondence_compatible:
                        assert p.metric_compatible and np.isfinite(p.q_boundary) and np.isfinite(p.q_wallwall)
                        qm[a, b] = qm[b, a] = 1 - min(p.q_boundary, p.q_wallwall)
            for i, row in rows.iterrows():
                members.append(dict(image_id=image_id, building_id=building, position=i,
                    canonical_annotation_id=row.canonical_annotation_id, worker_id=row.worker_id,
                    effective_point_count=row.effective_point_count, q_geometry_valid=row.q_geometry_valid))
            for config, matrix, threshold, invalid_positions in [(f'q_{q:.3f}', qm, 1 - q, invalid) for q in QS] + [('ospa30_t6', om, 6., set())]:
                if config not in configs:
                    continue
                cache, aggregate = {}, defaultdict(Counter)
                for order in orders:
                    sequence = [worker_pos[str(w)] for w in order['worker_ids'] if str(w) in worker_pos]
                    assert len(sequence) == n and len(set(sequence)) == n
                    trajectory = {}
                    mask = 0
                    for k, p in enumerate(sequence, 1):
                        mask |= 1 << p
                        if mask not in cache:
                            ix = sorted(sequence[:k])
                            if invalid_positions.intersection(ix):
                                result = dict(status='unknown_geometry', clusters=[], candidate_partition_count=0)
                            else:
                                result = partition(matrix[np.ix_(ix, ix)], threshold)
                                result = dict(status=result['status'], candidate_partition_count=result['candidate_partition_count'],
                                              clusters=[set(ix[j] for j in g) for g in result['clusters']])
                            cache[mask] = result
                            pw.writerow(dict(image_id=image_id, config=config, subset_mask=mask,
                                status=result['status'], candidate_partition_count=result['candidate_partition_count'],
                                clusters_positions_json=json.dumps([sorted(g) for g in result['clusters']], separators=(',', ':'))))
                            counts['subset_partitions'] += 1
                        trajectory[k] = cache[mask]
                        counts['prefix_uses'] += 1
                    for k in range(1, n - min(lookaheads) + 1):
                        prefix = trajectory[k]
                        support = [sum(len(g) >= m for g in prefix['clusters']) for m in (1, 2, 3)] if prefix['status'] == 'unique' else [0, 0, 0]
                        deltas = [changes(prefix['clusters'], trajectory[j]['clusters'])
                                  if prefix['status'] == trajectory[j]['status'] == 'unique' else None
                                  for j in range(k + 1, min(k + max(lookaheads), n) + 1)]
                        for h in lookaheads:
                            if k + h > n:
                                continue
                            ds = deltas[:h]
                            evaluated = all(d is not None for d in ds)
                            max_member = max(d['membership'] for d in ds) if evaluated else None
                            max_share = max(d['shares'] for d in ds) if evaluated else None
                            promotions = [max(d['promotions'][m] for d in ds) for m in range(3)] if evaluated else [None] * 3
                            ww.writerow(dict(image_id=image_id, config=config, replicate=order['replicate'], k=k, lookahead=h,
                                status='evaluated' if evaluated else 'unknown_partition', max_membership=max_member, max_shares=max_share,
                                **{f'prefix_support_{m}': support[m - 1] for m in (1, 2, 3)},
                                **{f'promotion_{m}': promotions[m - 1] for m in (1, 2, 3)}))
                            counts['window_metrics'] += 1
                            for m in (1, 2, 3):
                                for eps in EPS:
                                    state = window_state(ds, support, m, eps)
                                    aggregate[k, h, m, eps][state] += 1
                                    if state == 'stable':
                                        aggregate[k, h, m, eps]['stable_multi' if len(prefix['clusters']) > 1 else 'stable_single'] += 1
                for (k, h, m, eps), c in sorted(aggregate.items()):
                    assert c['stable'] + c['changing'] + c['unknown'] == 200
                    curves.append(dict(image_id=image_id, building_id=building, config=config, k=k, lookahead=h,
                        min_support=m, epsilon=eps, replicates=200, stable=c['stable'], changing=c['changing'], unknown=c['unknown'],
                        stable_lower=c['stable'] / 200, stable_upper=(c['stable'] + c['unknown']) / 200,
                        stable_single=c['stable_single'], stable_multi=c['stable_multi']))
            print(f'{image_no}/{responses.image_id.nunique()} images complete; {counts["window_metrics"]} replay windows', flush=True)
    pd.DataFrame(curves, columns=curve_fields).to_csv(out / 'stability_curves.csv', index=False)
    pd.DataFrame(members).to_csv(out / 'image_members.csv', index=False)
    qa = dict(status='passed', images=responses.image_id.nunique(), responses=len(responses), replicates=len(orders),
              input_images=input_images, input_responses=input_responses, min_workers=min_workers,
              image_ids=sorted(responses.image_id.unique()),
              images_without_windows=int((responses.groupby('image_id').size() <= min(lookaheads)).sum()),
              windows=lookaheads, configs=len(configs), config_names=list(configs), curve_rows=len(curves), **counts,
              all_stages_pooled=True, hard_effective_point_count_gate=True, elapsed_seconds=time.perf_counter() - started,
              no_silent_q_invalid_removal=True, original_coordinates_modified=False, full_prefix_person_budget=True)
    (out / 'QA.json').write_text(json.dumps(qa, indent=2), encoding='utf8')
    print(json.dumps(qa), flush=True)
    return qa


def short_window_check(replay_dir, out):
    """高人数图中，短窗口状态与同一前缀的 h5 状态配对；不拟合或筛选图像。"""
    started = time.perf_counter()
    replay_dir, out = Path(replay_dir), Path(out)
    configs, ks, short_h = ('q_0.950', 'q_0.925', 'ospa30_t6'), (2, 3, 4), (1, 2, 3)
    states = ('stable', 'changing', 'unknown')
    members = pd.read_csv(replay_dir / 'image_members.csv',
        usecols=['image_id', 'building_id', 'canonical_annotation_id', 'worker_id'], dtype={'worker_id': str})
    if members.isna().any().any() or members.duplicated(['image_id', 'worker_id']).any() or members.canonical_annotation_id.duplicated().any():
        raise ValueError('invalid_replay_member_identity')
    sizes = members.groupby('image_id').size()
    eligible = sizes[sizes >= 16]
    if eligible.empty or (members.groupby('image_id').building_id.nunique() != 1).any():
        raise ValueError('no_dense_images_or_building_identity_mismatch')
    key = ['image_id', 'config', 'k', 'replicate']
    fields = key + ['lookahead', 'status', 'max_membership', 'max_shares', 'prefix_support_2', 'promotion_2']
    chunks, scanned = [], 0
    for chunk in pd.read_csv(replay_dir / 'window_metrics.csv.gz', usecols=fields, chunksize=100000):
        scanned += len(chunk)
        part = chunk[chunk.image_id.isin(eligible.index) & chunk.config.isin(configs) &
                     chunk.k.isin(ks) & chunk.lookahead.isin((*short_h, 5))].copy()
        if part.empty:
            continue
        if not part.status.isin(['evaluated', 'unknown_partition']).all():
            raise ValueError('unexpected_window_status')
        support = part.prefix_support_2.to_numpy()
        if not np.isfinite(support).all() or (support < 0).any() or not np.equal(support, np.floor(support)).all():
            raise ValueError('invalid_prefix_support')
        evaluated = part.status.eq('evaluated')
        metrics = part.loc[evaluated, ['max_membership', 'max_shares', 'promotion_2']].to_numpy()
        if not np.isfinite(metrics).all() or (metrics < 0).any() or (metrics[:, :2] > 1 + 1e-12).any() or not np.equal(metrics[:, 2], np.floor(metrics[:, 2])).all():
            raise ValueError('invalid_evaluated_window_metrics')
        # The stored maxima are sufficient for the same universal per-j rule used by window_state.
        part['state'] = [window_state(
            [dict(membership=r.max_membership, shares=r.max_shares, promotions=[0, r.promotion_2, 0])]
                if r.status == 'evaluated' else [None], [0, r.prefix_support_2, 0], 2, .10)
            for r in part.itertuples()]
        chunks.append(part[key + ['lookahead', 'state']])
    if not chunks:
        raise ValueError('incomplete_window_pairing:no_selected_rows')
    selected = pd.concat(chunks, ignore_index=True)
    if selected.duplicated(key + ['lookahead']).any():
        raise ValueError('duplicate_window_pairing')
    paired = selected.pivot(index=key, columns='lookahead', values='state')
    coverage = paired.groupby(key[:3]).size()
    expected = pd.MultiIndex.from_product([eligible.index, configs, ks], names=key[:3])
    if set(paired.columns) != {1, 2, 3, 5} or paired.isna().any().any() or len(coverage) != len(expected) or not coverage.reindex(expected).eq(200).all() or paired.index.get_level_values('replicate').nunique() != 200:
        raise ValueError('incomplete_window_pairing')
    paired = paired.reset_index()
    count_fields = [f'early_{a}_later_{b}_n' for a in states for b in states]
    tables = []
    for h in short_h:
        table = paired.groupby(key[:3] + [h, 5]).size().unstack([h, 5], fill_value=0)
        table = table.reindex(columns=pd.MultiIndex.from_product([states, states]), fill_value=0)
        table.columns = count_fields
        tables.append(table.reset_index().assign(lookahead=h))
    counts = pd.concat(tables, ignore_index=True)
    impossible = ['early_changing_later_stable_n', 'early_unknown_later_stable_n', 'early_unknown_later_changing_n']
    if counts[impossible].to_numpy().any():
        raise ValueError('nested_window_state_inconsistency')
    counts['building_id'] = counts.image_id.map(members.groupby('image_id').building_id.first())
    counts['usable_n'] = counts.image_id.map(eligible)

    def rates(frame):
        frame = frame.copy()
        frame['paired_n'] = frame[count_fields].sum(axis=1)
        frame['early_stable_n'] = frame[[f'early_stable_later_{s}_n' for s in states]].sum(axis=1)
        frame['early_stable_later_evaluable_n'] = frame.early_stable_later_stable_n + frame.early_stable_later_changing_n
        for state in states:
            frame[f'early_stable_to_later_{state}_rate'] = frame[f'early_stable_later_{state}_n'] / frame.early_stable_n.replace(0, np.nan)
        frame['early_stable_to_later_stable_rate_among_evaluable'] = frame.early_stable_later_stable_n / frame.early_stable_later_evaluable_n.replace(0, np.nan)
        return frame.assign(later_lookahead=5, min_support=2, epsilon=.10)

    detail = rates(counts).sort_values(['image_id', 'config', 'k', 'lookahead'])
    groups = counts.groupby(['config', 'k', 'lookahead'])
    summary = rates(groups[count_fields].sum().reset_index()).assign(summary_level='k_h_config', images=len(eligible))
    pooled = rates(counts.groupby('config')[count_fields].sum().reset_index()).assign(
        summary_level='config_all_k_h', images=len(eligible))
    summary = pd.concat([summary, pooled], ignore_index=True)
    out.mkdir(parents=True, exist_ok=True)
    detail.to_csv(out / 'image_state_counts.csv', index=False)
    summary.to_csv(out / 'summary.csv', index=False)
    qa = dict(status='passed', source_replay_dir=str(replay_dir.resolve()), source_rows_scanned=scanned,
        selected_window_rows=len(selected), images=len(eligible), image_ids=sorted(eligible.index),
        excluded_low_n_images=int((sizes < 16).sum()), min_workers=16, configs=configs, k=ks,
        short_lookaheads=short_h, later_lookahead=5, min_support=2, epsilon=.10, replicates=200,
        paired_rows=len(paired) * len(short_h), detail_rows=len(detail), summary_rows=len(summary),
        short_max_total_people=7, long_max_total_people=9, long_window_includes_early_window=True,
        nested_window_state_consistency=True,
        independent_validation=False, low_n_images_filtered_by_results=False, fitted_prediction_model=False,
        original_coordinates_modified=False, elapsed_seconds=time.perf_counter() - started,
        status_rule='复用 window_state；每个窗口使用已保存的最大成员关系变化、最大份额变化、最大m2支持晋升及前缀支持；未知保持 unknown。',
        rate_denominators='三个 early_stable_to_later_*_rate 均以 early_stable_n 为分母，未知独列；among_evaluable 仅以 early_stable_later_evaluable_n 为分母。分母0时为空。',
        dependence='同一图、同一人员排列、同一k配对；h5包含短窗口，并非独立的新样本。k/h及人员排列重复使用响应。汇总计数不是独立样本量。',
        interpretation='只检查2–4人前缀后的1–3人短窗口状态在延长至5人窗口时怎样变化，不据此筛选低N图，不作为新场景预测模型或真实采集停止保证。',
        files={'image_state_counts.csv':'每图×配置×k×短h的3×3状态计数、人数、条件率和明确分母。',
               'summary.csv':'按配置×k×短h汇总，另按配置合并全部k/h；计数与条件率使用相同分母定义。'})
    (out / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf8')
    return qa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--geometry-dir', type=Path, default=BASE / 'geometry')
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--lookaheads', nargs='+', type=int, default=(3, 5))
    parser.add_argument('--min-workers', type=int, default=1)
    parser.add_argument('--configs', nargs='+', choices=CONFIGS, default=CONFIGS)
    parser.add_argument('--image-ids', nargs='+')
    args = parser.parse_args()
    replay(args.geometry_dir, args.out, lookaheads=args.lookaheads, min_workers=args.min_workers,
           configs=args.configs, image_ids=args.image_ids)


if __name__ == '__main__':
    main()
