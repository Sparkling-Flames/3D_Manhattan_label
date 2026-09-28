"""独立复核Pro分簇返回：穷举小图目标、共享x敏感性及重放抽样误差。"""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/cluster_validation_received_20260922/audit'


def wilson(p, n):
    z = 1.959963984540054
    center = (p + z*z/(2*n)) / (1 + z*z/n)
    half = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return center-half, center+half


def brute_affinity(d, cut):
    """小图枚举全部满足直径约束的集合分区，不调用整数规划。"""
    n = len(d)
    weight = np.maximum(0, 1-d/cut)**2
    best, leaves = 0., 0

    def visit(i, groups, score):
        nonlocal best, leaves
        if i == n:
            best = max(best, score)
            leaves += 1
            return
        for g in groups:
            if all(d[i, j] <= cut for j in g):
                added = sum(weight[i, j] for j in g)
                g.append(i)
                visit(i+1, groups, score+added)
                g.pop()
        visit(i+1, groups+[[i]], score)

    visit(0, [], 0.)
    return best, leaves


def json_differences(a, b):
    result = dict(float_differences=0, max_absolute_float_difference=0., other=[])

    def visit(x, y, path):
        if isinstance(x, dict) and isinstance(y, dict) and x.keys() == y.keys():
            for k in x:
                visit(x[k], y[k], path + '/' + k)
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for i, (u, v) in enumerate(zip(x, y)):
                visit(u, v, path + '/' + str(i))
        elif x != y:
            if isinstance(x, float) and isinstance(y, float):
                result['float_differences'] += 1
                result['max_absolute_float_difference'] = max(result['max_absolute_float_difference'], abs(x-y))
            else:
                result['other'].append(dict(path=path, original=x, local=y))

    visit(a, b, '')
    return result


def main(package, recomputed):
    OUT.mkdir(parents=True, exist_ok=True)
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    sys.path.insert(0, str(package / 'code'))
    import core as c
    _, records, views, _, _ = c.load()
    spec = importlib.util.spec_from_file_location('candidate_partition', package / 'code/02_partition.py')
    ap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ap)
    with gzip.open(ROOT / 'analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz', 'rt', encoding='utf8') as f:
        local = {r['canonical_annotation_id']: r for r in map(json.loads, f)}
    for v in views.values():
        for cid in v['ids']:
            assert local[cid]['worker_id'] == records[cid]['row']['worker_id']
            assert local[cid]['image_id'] == v['image_id']
            np.testing.assert_array_equal(local[cid]['effective_points_1024x512'], records[cid]['p'])
    members = {r['image_id']: r for r in read(package / 'results/affinity_corpus_memberships.json')}
    with gzip.open(package / 'results/distance_variants.json.gz', 'rt') as f:
        matrices = json.load(f)
    small, changes, lower_bounds = [], [], []
    for iid, v in views.items():
        d = np.round(v['d'], 8)
        old = members[iid]
        assert old['ids'] == v['ids']
        if v['N'] >= 8:
            near = d <= 25.6
            np.fill_diagonal(near, False)
            isolated = int(sum(near.sum(1) == 0))
            count_unique = int(sum((d < 1e6).sum(1) == 1))
            labels, _ = c.part(d, v['ids'], 'complete', 25.6)
            singletons = int(sum(np.unique(labels, return_counts=True)[1] == 1))
            lower_bounds.append(dict(image_id=iid, code=v['code'], N=v['N'],
                forced_singletons=isolated, count_unique=count_unique,
                geometry_isolated=isolated-count_unique, complete_singletons=singletons,
                partition_singletons=singletons-isolated,
                max_possible_repeated_mass=(v['N']-isolated)/v['N']))
        if v['N'] <= 8:
            best, leaves = brute_affinity(d, 25.6)
            assert np.isclose(best, old['objective'], atol=1e-8, rtol=0), iid
            small.append(dict(code=v['code'], N=v['N'], partitions=leaves, objective=best))
        snapped = np.asarray(matrices['snap02'][iid])
        new, info = ap.affinity_partition(snapped, v['ids'], 25.6, 'quadratic', time_limit=10)
        assert info['certified'] and new is not None, iid
        old_labels = np.array(old['labels'])
        a, b = np.triu_indices(v['N'], 1)
        changed = (old_labels[a] == old_labels[b]) != (new[a] == new[b])
        changes.append(dict(code=v['code'], N=v['N'],
            pair_edge_changes=int(sum((v['d'][a, b] <= 25.6) != (snapped[a, b] <= 25.6))),
            coassignment_changes=int(sum(changed)), changed_members=len(set(a[changed]) | set(b[changed]))))
    pd.DataFrame(small).to_csv(OUT / 'small_image_exhaustive_check.csv', index=False)
    change = pd.DataFrame(changes)
    change.to_csv(OUT / 'candidate_shared_x_sensitivity.csv', index=False)
    bound = pd.DataFrame(lower_bounds)
    bound.to_csv(OUT / 'diameter_partition_singleton_lower_bound.csv', index=False)
    replay = pd.read_csv(package / 'results/consensus_replay_per_image.csv')
    replay = replay[(replay.variant == 'raw') & (replay.method == 'complete') & (replay.cut == 25.6) &
                    (replay.J == 3) & (replay.m == 2) & (replay.tail_fraction == .1) & (replay.h == 3)].copy()
    replay['mc_low'], replay['mc_high'] = wilson(replay.success_fraction.to_numpy(), replay.orders.to_numpy())
    replay.to_csv(OUT / 'replay_monte_carlo_intervals.csv', index=False)
    reference_files = {p.name for p in (package / 'results').iterdir() if p.is_file() and ('.csv' in p.name or '.json' in p.name)}
    actual_files = {p.name for p in (recomputed / 'results').iterdir() if p.is_file() and ('.csv' in p.name or '.json' in p.name)}
    assert reference_files == actual_files, (reference_files-actual_files, actual_files-reference_files)
    reproduction = read(recomputed / 'RECOMPUTATION_CHECK.json')
    differences = [r for r in reproduction['comparison'] if not r['pass']]
    difference_details = {}
    for r in differences:
        name = r['file']
        if '.json' not in name:
            raise AssertionError('需审查新的CSV差异：' + name)
        def read_result(p):
            if p.suffix == '.gz':
                with gzip.open(p, 'rt', encoding='utf8') as f:
                    return json.load(f)
            return read(p)
        difference_details[name] = json_differences(read_result(package / 'results' / name), read_result(recomputed / 'results' / name))
    preview_diffs = {}
    for name in ['preview_mechanism_summary.json']:
        a, b = read(package / 'results' / name), read(recomputed / 'results' / name)
        preview_diffs[name] = {k: dict(original=a.get(k), local=b.get(k)) for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
    summary = dict(source_effective_points_and_workers_equal=2444,
        results_inventory_equal=len(reference_files), reproduction=reproduction,
        explicit_differences=differences, preview_metadata_differences=preview_diffs,
        difference_details=difference_details,
        exhaustive_small_images=len(small), feasible_partitions_enumerated=sum(x['partitions'] for x in small),
        diameter_lower_bound=dict(images=len(bound), responses=int(bound.N.sum()),
            forced_singletons=int(bound.forced_singletons.sum()),
            count_unique=int(bound.count_unique.sum()), geometry_isolated=int(bound.geometry_isolated.sum()),
            complete_singletons=int(bound.complete_singletons.sum()), partition_singletons=int(bound.partition_singletons.sum()),
            images_cannot_reach90=int((bound.max_possible_repeated_mass < .9-1e-10).sum()),
            scope='固定当前点对应、点数硬门和25.6两两直径条件；是图论下界，不说明这些作答语义错误或人员质量差'),
        candidate_snap02=dict(images_changed=int((change.coassignment_changes > 0).sum()),
            coassignment_changes=int(change.coassignment_changes.sum()), members=int(change.changed_members.sum()),
            images_changed_without_edge_changes=int(((change.coassignment_changes > 0) & (change.pair_edge_changes == 0)).sum())),
        mc_only=dict(images=len(replay), point_estimate_ge80=int((replay.success_fraction >= .8).sum()),
            lower95_ge80=int((replay.mc_low >= .8).sum()), upper95_ge80=int((replay.mc_high >= .8).sum()),
            scope='逐图Wilson区间只针对固定人群下80次顺序抽样；不反映新人员泛化或方法误差，也不是同时置信带'),
        limitations='新候选共享x敏感性仍是开发探针；最优目标不等于语义正确。未更改原始数据、算法默认值或人工审核。')
    (OUT / 'INDEPENDENT_CHECK.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'reproduction'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--recomputed', type=Path, required=True)
    args = parser.parse_args()
    main(args.package.resolve(), args.recomputed.resolve())
