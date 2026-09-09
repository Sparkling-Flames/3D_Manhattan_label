"""复用无序点集缓存，补真正前缀验证、相邻成员变化与逐指标固定支持窗口。"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
import sys
import time
from collections import Counter, defaultdict
from contextlib import ExitStack
from itertools import groupby
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import (
    BASE, PREVIOUS, OUTPUT as CACHE, META, CONFIGS, fixed_distribution, unit_points,
)
from tools.thesis_main.analysis.review_order_free_clusters_20260908 import coassignment_disagreement
from tools.thesis_main.analysis.audit_building_convergence_20260908 import (
    source_annotation_index, ordered_points, require_same_points,
)
from tools.thesis_main.data_prep.prepare_building_holdout_20260908 import splits

OUTPUT = 'analysis_results/building_convergence_evidence_20260908_v1/core'
NODES = [3, 5, 8, 10, 12, 15]
DISTRIBUTION = ['distribution_tv', 'validation_outside_fraction', 'validation_ambiguous_fraction']
STRUCTURE = ['cluster_count', 'supported_historical_cluster_count', 'singleton_response_fraction',
             'training_entropy', 'unique_indicator', 'non_unique_indicator', 'truncated_indicator']
PATH_MEASURES = {
    'full_history_fixed': DISTRIBUTION + ['training_entropy'],
    'prefix_validation': DISTRIBUTION,
    'prefix_structure': STRUCTURE,
    'adjacent_prefix': ['coassignment_disagreement'],
}


def js(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'))


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def finite(x):
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def prefix_validation(matrix, history, validation, clusters, threshold, k, status):
    row = dict(prefix_status=status, training_cluster_support_json='', training_entropy=np.nan,
               observed_historical_cluster_count=np.nan, supported_historical_cluster_count=np.nan,
               historical_largest_share=np.nan, distribution_tv=np.nan,
               validation_outside_fraction=np.nan, validation_ambiguous_fraction=np.nan,
               validation_cluster_support_json='', validation_compatible_cluster_ids_json='',
               singleton_response_fraction=np.nan)
    if status != 'unique':
        return row
    if not validation or not 1 <= k <= len(history):
        raise ValueError('invalid_prefix_support')
    if set(history) & set(validation):
        raise ValueError('history_validation_overlap')
    values = fixed_distribution(matrix, history[:k], validation, clusters, threshold, [k])[0]
    # 此处的“full”只是当前前缀自身，机械为0，不能作为验证指标输出。
    values.pop('prefix_to_full_history_tv')
    values.pop('k')
    row.update(values)
    row['singleton_response_fraction'] = sum(len(g) == 1 for g in clusters) / k
    return row


def adjacent(left, right, history):
    start, end = int(left['k']), int(right['k'])
    if not 2 <= start < end <= len(history):
        raise ValueError('invalid_adjacent_prefix')
    value = np.nan
    if left['status'] == right['status'] == 'unique':
        value = coassignment_disagreement(json.loads(left['prefix_clusters_json']),
                                          json.loads(right['prefix_clusters_json']), history[:start])
    return dict(from_k=start, to_k=end, from_status=left['status'], to_status=right['status'],
                common_member_count=start, coassignment_disagreement=value)


def fixed_mask(support, data, nodes, max_k, measure):
    eligible = [s for s, r in support.items() if int(r['history_n']) >= max_k and int(r['validation_n']) >= 2]
    valid = []
    counts = Counter()
    node_counts = {str(k): 0 for k in nodes}
    for split in eligible:
        rows = [data.get(split, {}).get(k, {}) for k in nodes]
        states = [r.get('status', 'missing') for r in rows]
        counts['non_unique_splits'] += any(s == 'non_unique' or r.get('from_status') == 'non_unique' for s, r in zip(states, rows))
        counts['truncated_splits'] += any(s == 'truncated' or r.get('from_status') == 'truncated' for s, r in zip(states, rows))
        counts['ambiguous_splits'] += any(finite(r.get('validation_ambiguous_fraction')) and float(r['validation_ambiguous_fraction']) > 0 for r in rows)
        is_indicator = measure.endswith('_indicator')
        usable = [finite(r.get(measure)) and (is_indicator or s == 'unique') and
                  (is_indicator or r.get('from_status', 'unique') == 'unique') for r, s in zip(rows, states)]
        for k, good in zip(nodes, usable):
            node_counts[str(k)] += good
        counts['missing_or_nonfinite_splits'] += any(not finite(r.get(measure)) for r in rows)
        if all(usable):
            valid.append(split)
    return dict(all_splits=len(support), support_eligible_splits=len(eligible),
                support_insufficient_splits=len(support)-len(eligible),
                non_unique_splits=counts['non_unique_splits'], truncated_splits=counts['truncated_splits'],
                ambiguous_splits=counts['ambiguous_splits'], missing_or_nonfinite_splits=counts['missing_or_nonfinite_splits'],
                per_node_valid_splits_json=js(node_counts), valid_split_ids=valid)


def audit_inputs(root):
    a = read(root / BASE / 'annotations.csv.gz')
    if not a.canonical_annotation_id.is_unique or a.duplicated(['context_key', 'worker_id']).any():
        raise ValueError('duplicate_canonical_or_worker_context')
    expected = a[['stage', 'block_index', 'base_task_id', 'raw_condition']].agg('|'.join, axis=1)
    assert (expected == a.context_key).all()
    canonical = a.set_index('canonical_annotation_id').to_dict('index')
    versions = [json.loads(x) for x in (root / BASE / 'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len({v['raw_annotation_version_id'] for v in versions}) == len(versions)
    assert {v['canonical_annotation_id'] for v in versions} == set(canonical)
    sources, selected = {}, {}
    for v in versions:
        path = v['source_path']
        if path not in sources:
            sources[path] = source_annotation_index(json.loads((root / path).read_text(encoding='utf-8-sig')))
        key = tuple(str(v[k]) for k in ['runtime_task_id', 'worker_id', 'raw_annotation_id'])
        task, annotation = sources[path][key]
        require_same_points(ordered_points(annotation['result']), v['points_1024x512'])
        assert v['base_task_id'] in json.dumps(task.get('data', {}), ensure_ascii=False)
        if str(v['selected_canonical_version']).lower() == 'true':
            aid = v['canonical_annotation_id']
            assert aid not in selected
            selected[aid] = v
            row = canonical[aid]
            for field in ['runtime_task_id', 'worker_id', 'raw_annotation_id', 'stage', 'block_index', 'raw_condition', 'base_task_id']:
                assert row[field] == str(v[field])
            assert row['raw_export_path'] == path
        else:
            assert str(v['independent_analysis_unit']).lower() == 'false'
    assert set(selected) == set(canonical)
    lineage = read(root / BASE / 'facts/annotation_version_lineage.csv.gz')
    assert set(lineage.raw_annotation_version_id) == {v['raw_annotation_version_id'] for v in versions}
    by_version = {v['raw_annotation_version_id']: v for v in versions}
    for r in lineage.to_dict('records'):
        assert r['canonical_annotation_id'] == by_version[r['raw_annotation_version_id']]['canonical_annotation_id']
    status = read(root / CACHE / 'response_status.csv.gz')
    assert status.canonical_annotation_id.is_unique and set(status.canonical_annotation_id) == set(canonical)
    init = read(root / PREVIOUS / 'initialization_context_index.csv').set_index('context_key').initialization_kind.to_dict()
    for r in status.to_dict('records'):
        aid = r['canonical_annotation_id']
        for field in META[:-1] + ['worker_id']:
            assert r[field] == canonical[aid][field]
        assert r['initialization_kind'] == init[r['context_key']]
        state = 'computable_point_pattern'
        try:
            unit_points(selected[aid]['points_1024x512'])
        except ValueError as exc:
            state = str(exc)
        assert r['status'] == state
        assert int(r['raw_endpoint_count']) == len(selected[aid]['points_1024x512'])
    orders, expected_splits, _ = splits(a)
    saved_orders = [json.loads(x) for x in (root / PREVIOUS / 'census/global_worker_orders.jsonl').read_text(encoding='utf-8').splitlines()]
    assert orders == saved_orders
    schedules = read(root / PREVIOUS / 'census/worker_splits.csv.gz').to_dict('records')
    expected_splits = {r['split_id']: r for r in expected_splits}
    assert len(schedules) == len(expected_splits) and len({r['split_id'] for r in schedules}) == len(schedules)
    for s in schedules:
        e = expected_splits[s['split_id']]
        for field in ['history_worker_ids_json', 'validation_worker_ids_json']:
            assert json.loads(s[field]) == json.loads(e[field])
        for field in ['replicate', 'scheme', 'building_id']:
            assert s[field] == str(e[field])
    a['initialization_kind'] = a.context_key.map(init)
    qa = dict(canonical=len(a), versions=len(versions), raw_export_files=len(sources),
              workers=a.worker_id.nunique(), buildings=a.building_id.nunique(), contexts=a.context_key.nunique(),
              images=a.image_id.nunique(), status_counts=status.status.value_counts().to_dict(),
              global_orders=len(orders), building_splits=len(schedules), raw_export_identity_and_order_verified=True)
    return a, status, schedules, qa


def context_stream(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        previous = ''
        for context, rows in groupby(csv.DictReader(f), key=lambda r: r['context_key']):
            if context <= previous:
                raise ValueError('cache_context_order_or_duplicate')
            previous = context
            yield context, list(rows)


def run(root, out):
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with (out / 'run.log').open('w', encoding='utf-8') as log:
        def progress(message):
            line = f'{time.time()-started:.1f}s {message}'
            print(line, flush=True)
            log.write(line + '\n'); log.flush()
        progress('核对原始导出、canonical谱系及200次全局排列')
        a, status, schedules, qa = audit_inputs(root)
        status.to_csv(out / 'response_status.csv.gz', index=False)
        good = set(status.loc[status.status == 'computable_point_pattern', 'canonical_annotation_id'])
        schedule_by_building = defaultdict(list)
        for s in schedules:
            schedule_by_building[s['building_id']].append(s)
        pairs = read(root / CACHE / 'pairwise_point_distances.csv.gz')
        pair_groups = {c: f for c, f in pairs.groupby('context_key')}
        source_names = ['historical_cluster_definitions.csv.gz', 'prefix_reclustering.csv.gz',
                        'fixed_taxonomy_prefixes.csv.gz', 'split_support.csv.gz']
        streams = {name: iter(context_stream(root / CACHE / name)) for name in source_names}
        heads = {name: next(s, None) for name, s in streams.items()}
        counts = Counter()
        with ExitStack() as stack:
            writers = {}
            def emit(name, row):
                if name not in writers:
                    f = stack.enter_context(gzip.open(out / name, 'wt', encoding='utf-8', newline='', compresslevel=1))
                    writers[name] = csv.DictWriter(f, fieldnames=list(row)); writers[name].writeheader()
                writers[name].writerow(row); counts[name] += 1
            for ordinal, (context, frame) in enumerate(a.groupby('context_key', sort=True)):
                meta = {k: frame.iloc[0][k] for k in META}
                assert all(frame[k].nunique() == 1 for k in META)
                cached = {}
                for name in source_names:
                    head = heads[name]
                    assert head is None or head[0] >= context
                    cached[name] = head[1] if head and head[0] == context else []
                    if cached[name]:
                        heads[name] = next(streams[name], None)
                    for r in cached[name]:
                        assert all(r[k] == meta[k] for k in META)
                ids = frame.loc[frame.canonical_annotation_id.isin(good), 'canonical_annotation_id'].tolist()
                pos = {aid: i for i, aid in enumerate(ids)}
                workers = dict(zip(frame.worker_id, frame.canonical_annotation_id))
                matrices = {metric: np.full((len(ids), len(ids)), np.nan) for metric in ['ospa30', 'ospa60']}
                for d in matrices.values():
                    np.fill_diagonal(d, 0.)
                seen = set()
                if context in pair_groups:
                    for r in pair_groups[context].to_dict('records'):
                        i, j = pos[r['left_canonical']], pos[r['right_canonical']]
                        key = tuple(sorted((i, j)))
                        assert i != j and key not in seen
                        seen.add(key)
                        for metric, d in matrices.items():
                            d[i, j] = d[j, i] = float(r[metric])
                assert len(seen) == len(ids)*(len(ids)-1)//2
                assert all(np.isfinite(d).all() and (d >= 0).all() for d in matrices.values())
                support, groups = {}, {}
                for s in schedule_by_building[meta['building_id']]:
                    hh = [workers[w] for w in json.loads(s['history_worker_ids_json']) if w in workers]
                    vv = [workers[w] for w in json.loads(s['validation_worker_ids_json']) if w in workers]
                    h, v = [x for x in hh if x in pos], [x for x in vv if x in pos]
                    support[s['split_id']] = row = meta | dict(split_id=s['split_id'], replicate=int(s['replicate']), scheme=s['scheme'],
                        history_n=len(h), validation_n=len(v), history_raw_n=len(hh), validation_raw_n=len(vv),
                        history_uncomputable_n=len(hh)-len(h), validation_uncomputable_n=len(vv)-len(v),
                        history_canonical_ids_json=js(h), validation_canonical_ids_json=js(v),
                        history_uncomputable_ids_json=js([x for x in hh if x not in pos]),
                        validation_uncomputable_ids_json=js([x for x in vv if x not in pos]),
                        status='available' if len(h)>=3 and len(v)>=2 else 'history_lt3' if len(h)<3 else 'validation_lt2')
                    groups[s['split_id']] = (h, v)
                    emit('split_support.csv.gz', row)
                old_support = cached['split_support.csv.gz']
                assert len(old_support) == len(support) == len({r['split_id'] for r in old_support})
                for r in old_support:
                    assert all(str(support[r['split_id']][k]) == r[k] for k in ['history_n', 'validation_n', 'status', 'replicate', 'scheme'])
                definitions = {}
                for r in cached['historical_cluster_definitions.csv.gz']:
                    key = (r['split_id'], r['config'])
                    assert key not in definitions
                    h, v = groups[r['split_id']]
                    assert json.loads(r['historical_canonical_ids_json']) == h and json.loads(r['validation_canonical_ids_json']) == v
                    assert int(r['history_n']) == len(h) and int(r['validation_n']) == len(v)
                    definitions[key] = r
                config_map = {c: (m, tau) for c, m, tau in CONFIGS}
                assert set(definitions) == {(sid, c) for sid, s in support.items() if s['status']=='available' for c in config_map}
                prefix_rows = defaultdict(list)
                for r in cached['prefix_reclustering.csv.gz']:
                    prefix_rows[(r['split_id'], r['config'])].append(r)
                full_rows = defaultdict(dict)
                for r in cached['fixed_taxonomy_prefixes.csv.gz']:
                    key = (r['split_id'], r['config']); k = int(r['k'])
                    assert k not in full_rows[key]
                    full_rows[key][k] = r | {'status': 'unique'}
                paths = {c: {p: defaultdict(dict) for p in PATH_MEASURES} for c in config_map}
                for (sid, config), definition in definitions.items():
                    h, v = groups[sid]; metric, tau = config_map[config]
                    base = {k: support[sid][k] for k in META + ['split_id', 'replicate', 'scheme', 'history_n', 'validation_n']}
                    base.update(config=config, metric=metric, threshold_degrees=tau)
                    rows = sorted(prefix_rows[(sid, config)], key=lambda r: int(r['k']))
                    expected_ks = sorted(k for k in set(NODES+[len(h)]) if k <= len(h))
                    assert [int(r['k']) for r in rows] == expected_ks
                    full_state = definition['full_partition_status']
                    assert full_state in ('unique', 'non_unique', 'truncated')
                    if full_state == 'unique':
                        assert sorted(x for g in json.loads(definition['full_clusters_json']) for x in g) == sorted(h)
                        assert sorted(full_rows[(sid, config)]) == expected_ks
                    else:
                        assert not json.loads(definition['full_clusters_json']) and not full_rows[(sid, config)]
                    for i, r in enumerate(rows):
                        k = int(r['k']); state = r['status']; clusters = json.loads(r['prefix_clusters_json'])
                        assert state in ('unique', 'non_unique', 'truncated')
                        assert all(str(base[x]) == str(r[x]) for x in ['history_n', 'validation_n', 'scheme', 'replicate', 'metric'])
                        assert float(r['threshold_degrees']) == tau
                        if state == 'unique':
                            assert sorted(x for g in clusters for x in g) == sorted(h[:k])
                        else:
                            assert not clusters
                        local = [[h.index(x) for x in g] for g in clusters]
                        computed = prefix_validation(matrices[metric], [pos[x] for x in h], [pos[x] for x in v], local, tau, k, state)
                        result = base | dict(k=k, prefix_clusters_json=r['prefix_clusters_json'],
                            prefix_canonical_ids_json=js(h[:k]), validation_canonical_ids_json=js(v)) | computed
                        emit('prefix_validation.csv.gz', result)
                        paths[config]['prefix_validation'][sid][k] = computed | {'status': state}
                        structure = computed | dict(status=state, cluster_count=len(clusters) if state=='unique' else np.nan,
                            unique_indicator=int(state=='unique'), non_unique_indicator=int(state=='non_unique'), truncated_indicator=int(state=='truncated'))
                        paths[config]['prefix_structure'][sid][k] = structure
                        paths[config]['full_history_fixed'][sid][k] = full_rows[(sid, config)].get(k, {'status': full_state})
                        if i:
                            change = adjacent(rows[i-1], r, h)
                            emit('adjacent_prefix_membership.csv.gz', base | change)
                            paths[config]['adjacent_prefix'][sid][k] = change | {'status': state}
                assert set(prefix_rows) == set(definitions)
                for scheme in ['two_thirds', 'sixty_percent']:
                    subset = {s: r for s, r in support.items() if r['scheme'] == scheme}
                    assert len(subset) == 200
                    for config in config_map:
                        for max_k in [5, 8, 15]:
                            nodes = [k for k in NODES if k <= max_k]
                            for path, measures in PATH_MEASURES.items():
                                used_nodes = nodes[1:] if path == 'adjacent_prefix' else nodes
                                data = paths[config][path]
                                for measure in measures:
                                    mask = fixed_mask(subset, data, used_nodes, max_k, measure)
                                    valid = mask.pop('valid_split_ids')
                                    common = meta | dict(scheme=scheme, config=config, max_k=max_k, path=path, measure=measure)
                                    emit('fixed_window_membership.csv.gz', common | dict(nodes_json=js(used_nodes),
                                        from_k_by_to_k_json=js(dict(zip(nodes[1:], nodes[:-1]))) if path=='adjacent_prefix' else '{}',
                                        **mask, valid_splits=len(valid), valid_split_ids_json=js(valid),
                                        support_status='no_support' if not mask['support_eligible_splits'] else 'no_valid_values' if not valid else 'available'))
                                    for sid in valid:
                                        for k in used_nodes:
                                            emit('fixed_window_values.csv.gz', common | dict(split_id=sid, replicate=subset[sid]['replicate'],
                                                k=k, from_k=data[sid][k].get('from_k', ''), value=float(data[sid][k][measure])))
                if ordinal % 10 == 0:
                    progress(f'完成 context {ordinal+1}/{a.context_key.nunique()}；前缀验证 {counts["prefix_validation.csv.gz"]} 行')
            assert all(head is None for head in heads.values())
        qa.update(status='passed', output_rows=dict(counts), configs=CONFIGS, windows=[5, 8, 15],
                  elapsed_seconds=time.time()-started, geometry_cache_reused=True, new_partition_learning=False,
                  mask_reason_flags_overlap=True, prefix_acceptance_changes_with_k=True,
                  formal_protocol_changed=False, independent_experiments=0)
        (out / 'RUN_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
        progress('完成全部输出；未指定停止人数或稳定性阈值')
    return qa


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    run(args.root, args.out or args.root / OUTPUT)
