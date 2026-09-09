"""逐楼覆盖、等权曲线、匹配图对与独立回读；不决定收敛人数。"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from itertools import combinations, groupby
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
OLD = 'analysis_results/order_free_cluster_holdout_20260908_v1'
CENSUS = 'analysis_results/building_holdout_exploration_20260908_v1/census'
OUTPUT = 'analysis_results/building_convergence_evidence_20260908_v1'
META = ['context_key', 'image_id', 'building_id', 'stage', 'block_index', 'raw_condition', 'initialization_kind']
STRATA = ['stage', 'block_index', 'raw_condition', 'initialization_kind', 'scheme', 'config', 'max_k', 'path', 'measure']


def save(out, name, frame):
    frame.to_csv(out / name, index=False, float_format='%.12g')


def census(a, lineage, states):
    if not a.canonical_annotation_id.is_unique or a.duplicated(['context_key', 'worker_id']).any():
        raise ValueError('duplicate canonical or worker/context')
    if not states.canonical_annotation_id.is_unique or set(states.canonical_annotation_id) != set(a.canonical_annotation_id):
        raise ValueError('response status identity mismatch')
    if set(lineage.canonical_annotation_id) != set(a.canonical_annotation_id):
        raise ValueError('version lineage identity mismatch')
    a = a.merge(states[['canonical_annotation_id', 'status']], on='canonical_annotation_id', validate='one_to_one')
    a['versions'] = a.canonical_annotation_id.map(lineage.groupby('canonical_annotation_id').size())
    a['computable'] = a.status.eq('computable_point_pattern')
    rows = []
    for building, g in a.groupby('building_id', sort=True):
        row = dict(building_id=building, images=g.image_id.nunique(), contexts=g.context_key.nunique(),
                   workers=g.worker_id.nunique(), canonical_responses=len(g), raw_versions=int(g.versions.sum()),
                   nonindependent_revisions=int(g.versions.sum() - len(g)), computable_responses=int(g.computable.sum()),
                   current20_workers=g[g.current20_member.astype(str).str.lower().eq('true')].worker_id.nunique(),
                   historical_eligibility_counts_json=json.dumps(g.historical_primary_eligibility_status.value_counts().to_dict()),
                   point_status_counts_json=json.dumps(g.status.value_counts().to_dict()))
        for condition in ['manual', 'semi', 'oos']:
            row[condition + '_responses'] = int(g.raw_condition.eq(condition).sum())
        rows.append(row)
    contexts = a.groupby([c for c in META if c in a], sort=True, observed=True).agg(
        raw_workers=('worker_id', 'nunique'), computable_workers=('computable', 'sum'),
        raw_versions=('versions', 'sum')).reset_index()
    return pd.DataFrame(rows), contexts


def summarize_curves(values):
    keys = META + [c for c in STRATA if c not in META] + ['k']
    contexts = values.groupby(keys, observed=True, dropna=False).agg(
        mean=('value', 'mean'), split_q10=('value', lambda x: x.quantile(.1)),
        split_q90=('value', lambda x: x.quantile(.9)), valid_splits=('replicate', 'nunique')).reset_index()
    return contexts, summarize_buildings(contexts)


def summarize_buildings(contexts):
    bkeys = ['building_id'] + STRATA + ['k']
    buildings = contexts.groupby(bkeys, observed=True, dropna=False).agg(
        mean=('mean', 'mean'), context_median=('mean', 'median'),
        context_q10=('mean', lambda x: x.quantile(.1)), context_q90=('mean', lambda x: x.quantile(.9)),
        contexts=('context_key', 'nunique'), images=('image_id', 'nunique'),
        minimum_context_splits=('valid_splits', 'min'), maximum_context_splits=('valid_splits', 'max')).reset_index()
    return buildings


def matched_curve_distances(values):
    """先匹配图对共同排列，再比较各k的均值；楼与楼对分别等权。"""
    f = values[(values.path == 'full_history_fixed') & (values.measure == 'distribution_tv')]
    pairs, summaries = [], []
    for key, data in f.groupby(STRATA, observed=True, dropna=False, sort=True):
        meta = dict(zip(STRATA, key))
        counts = data.groupby('building_id', observed=True).context_key.nunique()
        data = data[data.building_id.isin(counts[counts >= 2].index)]
        groups = {str(c): g for c, g in data.groupby('context_key', observed=True, sort=True)}
        local = []
        for left, right in combinations(groups, 2):
            a, b = groups[left], groups[right]
            if a.duplicated(['replicate', 'k']).any() or b.duplicated(['replicate', 'k']).any():
                raise ValueError('duplicate curve replicate/k')
            shared = sorted(set(a.replicate) & set(b.replicate))
            row = meta | dict(left_context=left, right_context=right,
                              left_building=str(a.building_id.iloc[0]), right_building=str(b.building_id.iloc[0]),
                              shared_replicates=len(shared), shared_replicates_json=json.dumps(shared),
                              status='comparable' if shared else 'no_shared_replicates', curve_distance=np.nan)
            row['pair_type'] = 'within' if row['left_building'] == row['right_building'] else 'between'
            if shared:
                av = a[a.replicate.isin(shared)].groupby('k', observed=True).value.mean()
                bv = b[b.replicate.isin(shared)].groupby('k', observed=True).value.mean()
                if list(av.index) != list(bv.index):
                    raise ValueError('different matched curve nodes')
                row['curve_distance'] = float((av - bv).abs().mean())
            local.append(row)
        pairs.extend(local)
        if not local:
            summaries.append(meta | dict(comparable_buildings=0, within_image_pairs=0, between_image_pairs=0,
                                         within_building_distance=np.nan, between_building_distance=np.nan,
                                         pair_matched_within_distance=np.nan, between_minus_within=np.nan,
                                         descriptive_within_distance=np.nan, descriptive_within_buildings=0,
                                         comparable_building_ids_json='[]', building_pairs=0, minimum_shared_replicates=0))
            continue
        p = pd.DataFrame(local)
        within = p[(p.pair_type == 'within') & p.curve_distance.notna()]
        descriptive_within = within.groupby('left_building').curve_distance.mean()
        buildings = set(within.left_building)
        between = p[(p.pair_type == 'between') & p.curve_distance.notna() &
                    p.left_building.isin(buildings) & p.right_building.isin(buildings)].copy()
        if len(between):
            between['building_pair'] = [tuple(sorted((a, b))) for a, b in zip(between.left_building, between.right_building)]
            between_means = between.groupby('building_pair').curve_distance.mean()
        else:
            between_means = pd.Series(dtype=float)
        common = set(between.left_building) | set(between.right_building)
        within = within[within.left_building.isin(common)]
        within_means = within.groupby('left_building').curve_distance.mean()
        w = within_means.mean()
        matched_within = np.mean([(within_means[a] + within_means[b]) / 2 for a, b in between_means.index]) if len(between_means) else np.nan
        b = between_means.mean()
        summaries.append(meta | dict(comparable_buildings=len(common), within_image_pairs=len(within),
                                     between_image_pairs=len(between), within_building_distance=w,
                                     between_building_distance=b, pair_matched_within_distance=matched_within,
                                     between_minus_within=b-matched_within,
                                     descriptive_within_distance=descriptive_within.mean(), descriptive_within_buildings=len(descriptive_within),
                                     comparable_building_ids_json=json.dumps(sorted(common)),
                                     building_pairs=len(between_means),
                                     minimum_shared_replicates=int(pd.concat([within, between]).shared_replicates.min()) if len(within) else 0))
    return pd.DataFrame(pairs), pd.DataFrame(summaries)


def prepare_coverage(root, out):
    a = pd.read_csv(root / BASE / 'annotations.csv.gz', dtype=str, keep_default_na=False)
    lineage = pd.read_csv(root / BASE / 'facts/annotation_version_lineage.csv.gz', dtype=str, keep_default_na=False)
    if not lineage.raw_annotation_version_id.is_unique:
        raise ValueError('duplicate raw version')
    states = pd.read_csv(root / OLD / 'response_status.csv.gz', dtype=str, keep_default_na=False)
    init = pd.read_csv(root / 'analysis_results/building_holdout_exploration_20260908_v1/initialization_context_index.csv', dtype=str)
    a = a.merge(init[['context_key', 'initialization_kind']], on='context_key', validate='many_to_one')
    if a.initialization_kind.isna().any():
        raise ValueError('missing initialization metadata')
    # 独立检查原始选定版本的点模式状态，不用旧资格/旧几何可算性筛人。
    actual_states = {}
    with (root / BASE / 'raw_annotation_versions.jsonl').open(encoding='utf-8') as stream:
        for row in map(json.loads, stream):
            if str(row['selected_canonical_version']).lower() != 'true':
                continue
            points = np.asarray(row['points_1024x512'], float)
            state = 'computable_point_pattern'
            if not points.size:
                state = 'empty_point_response'
            elif points.ndim != 2 or points.shape[1] != 2:
                state = 'coordinate_shape'
            elif not np.isfinite(points).all() or (points < 0).any() or (points > [1024, 512]).any():
                state = 'coordinate_invalid'
            aid = row['canonical_annotation_id']
            if aid in actual_states:
                raise ValueError('multiple selected raw versions')
            actual_states[aid] = state
    if states.set_index('canonical_annotation_id').status.to_dict() != actual_states:
        raise ValueError('raw point status/cache disagreement')
    buildings, contexts = census(a, lineage, states)
    people = pd.read_csv(root / CENSUS / 'worker_splits.csv.gz', dtype=str)
    good_ids = set(states.loc[states.status == 'computable_point_pattern', 'canonical_annotation_id'])
    lookup = {c: (g.iloc[0], set(g.worker_id), set(g.loc[g.canonical_annotation_id.isin(good_ids), 'worker_id']))
              for c, g in a.groupby('context_key')}
    by_building = {}
    for c, (meta, raw, good) in lookup.items():
        by_building.setdefault(meta.building_id, []).append((c, meta, raw, good))
    support = []
    for r in people.itertuples():
        h, v = set(json.loads(r.history_worker_ids_json)), set(json.loads(r.validation_worker_ids_json))
        if h & v:
            raise ValueError('history/validation worker overlap')
        for c, meta, raw, good in by_building[r.building_id]:
            nh, nv = len(h & good), len(v & good)
            support.append({k: meta[k] for k in META} | dict(split_id=r.split_id, replicate=int(r.replicate), scheme=r.scheme,
                history_raw_n=len(h & raw), validation_raw_n=len(v & raw), history_n=nh, validation_n=nv,
                status='available' if nh >= 3 and nv >= 2 else 'history_lt3' if nh < 3 else 'validation_lt2'))
    support = pd.DataFrame(support)
    previous = pd.read_csv(root / OLD / 'split_support.csv.gz')
    joined = support.merge(previous[['context_key', 'split_id', 'history_n', 'validation_n', 'status']],
                           on=['context_key', 'split_id'], validate='one_to_one', suffixes=('', '_old'))
    if len(joined) != len(support) or len(joined) != len(previous):
        raise ValueError('split support universe mismatch')
    for field in ['history_n', 'validation_n', 'status']:
        if not joined[field].eq(joined[field + '_old']).all():
            raise ValueError('independent split support disagreement: ' + field)
    counts = []
    for keys, g in support.groupby(META + ['scheme'], observed=True, dropna=False):
        row = dict(zip(META + ['scheme'], keys))
        row.update(all_splits=len(g), minimum_history_n=int(g.history_n.min()), maximum_history_n=int(g.history_n.max()),
                   minimum_validation_n=int(g.validation_n.min()), maximum_validation_n=int(g.validation_n.max()),
                   available_splits=int(g.status.eq('available').sum()))
        for n in [5, 8, 15]:
            row[f'window_{n}_support_splits'] = int(((g.history_n >= n) & (g.validation_n >= 2)).sum())
        counts.append(row)
    counts = pd.DataFrame(counts)
    main = counts[counts.scheme == 'two_thirds']
    for col in ['available_splits', 'window_5_support_splits', 'window_8_support_splits', 'window_15_support_splits']:
        count = main[main[col] > 0].groupby('building_id').context_key.nunique()
        buildings[col.replace('_splits', '_contexts')] = buildings.building_id.map(count).fillna(0).astype(int)
    save(out, 'building_coverage.csv', buildings)
    save(out, 'context_coverage.csv', contexts)
    save(out, 'context_split_coverage.csv', counts)
    save(out, 'independent_split_support.csv.gz', support)
    strata = a.merge(states[['canonical_annotation_id', 'status']], on='canonical_annotation_id', validate='one_to_one')
    strata = strata.groupby(['building_id', 'stage', 'block_index', 'raw_condition', 'initialization_kind']).agg(
        contexts=('context_key', 'nunique'), images=('image_id', 'nunique'), workers=('worker_id', 'nunique'),
        canonical_responses=('canonical_annotation_id', 'size'), computable_responses=('status', lambda x: x.eq('computable_point_pattern').sum())).reset_index()
    save(out, 'building_stratum_coverage.csv', strata)
    qa = dict(canonical=len(a), raw_versions=len(lineage), workers=a.worker_id.nunique(), images=a.image_id.nunique(),
              buildings=len(buildings), contexts=len(contexts), independent_raw_point_states=len(actual_states),
              independent_split_support_rows=len(support), historical_eligibility_filter=False,
              point_status_counts=states.status.value_counts().to_dict())
    (out / 'COVERAGE_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    return buildings, contexts, counts


def number(value):
    return float(value) if value not in ('', None) else float('nan')


def context_stream(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as stream:
        for context, rows in groupby(csv.DictReader(stream), key=lambda r: r['context_key']):
            yield context, list(rows)


def audit_core(root, out):
    """从身份、成员集合和直接算术回读，不调用底层前缀/窗口计算函数。"""
    core, review = out / 'core', out / 'review'
    qa = json.loads((core / 'RUN_QA.json').read_text(encoding='utf-8'))
    assert qa['status'] == 'passed'
    a = pd.read_csv(root / BASE / 'annotations.csv.gz', dtype=str)
    good = set(pd.read_csv(root / OLD / 'response_status.csv.gz').query("status == 'computable_point_pattern'").canonical_annotation_id)
    context_workers = {c: dict(zip(g.worker_id, g.canonical_annotation_id)) for c, g in a.groupby('context_key')}
    schedules = {r.split_id: (json.loads(r.history_worker_ids_json), json.loads(r.validation_worker_ids_json))
                 for r in pd.read_csv(root / CENSUS / 'worker_splits.csv.gz', dtype=str).itertuples()}
    support = pd.read_csv(core / 'split_support.csv.gz')
    independent = pd.read_csv(review / 'independent_split_support.csv.gz')
    comparison = support.merge(independent, on=['context_key', 'split_id'], suffixes=('', '_independent'), validate='one_to_one')
    assert len(comparison) == len(support) == len(independent)
    for field in ['history_n', 'validation_n', 'history_raw_n', 'validation_raw_n', 'status']:
        assert comparison[field].eq(comparison[field + '_independent']).all(), field
    identity = {}
    for r in support.itertuples():
        workers = context_workers[r.context_key]
        expected = [[workers[w] for w in order if w in workers and workers[w] in good] for order in schedules[r.split_id]]
        h, v = json.loads(r.history_canonical_ids_json), json.loads(r.validation_canonical_ids_json)
        assert [h, v] == expected
        assert not set(h) & set(v)
        identity[(r.context_key, r.split_id)] = (h, v)
    distances = {}
    for r in pd.read_csv(root / OLD / 'pairwise_point_distances.csv.gz').itertuples():
        key = tuple(sorted((r.left_canonical, r.right_canonical)))
        distances[key] = (r.ospa30, r.ospa60)
    prefix_count = geometry_count = adjacent_count = window_count = value_count = 0
    max_error = 0.
    streams = {
        'prefix': context_stream(core / 'prefix_validation.csv.gz'),
        'full': context_stream(root / OLD / 'fixed_taxonomy_prefixes.csv.gz'),
        'adjacent': context_stream(core / 'adjacent_prefix_membership.csv.gz'),
        'masks': context_stream(core / 'fixed_window_membership.csv.gz'),
        'values': context_stream(core / 'fixed_window_values.csv.gz'),
    }
    heads = {name: next(it, None) for name, it in streams.items()}
    source_support = {c: g for c, g in independent.groupby('context_key')}
    for ordinal, context in enumerate(sorted(context_workers)):
        blocks = {}
        for name, it in streams.items():
            head = heads[name]
            assert head is None or head[0] >= context
            blocks[name] = head[1] if head and head[0] == context else []
            if blocks[name]:
                heads[name] = next(it, None)
        prefix, full, adjacent_values = {}, {}, {}
        for r in blocks['prefix']:
            key = (r['split_id'], r['config'], int(r['k']))
            assert key not in prefix
            h, v = identity[(context, r['split_id'])]
            k = int(r['k'])
            assert json.loads(r['prefix_canonical_ids_json']) == h[:k]
            assert json.loads(r['validation_canonical_ids_json']) == v
            groups = json.loads(r['prefix_clusters_json'])
            state = r['prefix_status']
            assert state in ['unique', 'non_unique', 'truncated']
            if state != 'unique':
                assert not groups and not math.isfinite(number(r['distribution_tv']))
            else:
                flattened = [x for g in groups for x in g]
                assert len(flattened) == len(set(flattened)) == k and set(flattened) == set(h[:k])
                sizes = list(map(len, groups))
                assert sizes == json.loads(r['training_cluster_support_json'])
                choices = json.loads(r['validation_compatible_cluster_ids_json'])
                assert len(choices) == len(v)
                assert all(len(c) == len(set(c)) and all(0 <= j < len(groups) for j in c) for c in choices)
                outside = sum(len(c) == 0 for c in choices)
                ambiguous = sum(len(c) > 1 for c in choices)
                vc = [sum(c == [j] for c in choices) for j in range(len(groups))] + [outside]
                assert vc == json.loads(r['validation_cluster_support_json'])
                expected = dict(validation_outside_fraction=outside / len(v), validation_ambiguous_fraction=ambiguous / len(v),
                                training_entropy=-sum(n / k * math.log(n / k) for n in sizes),
                                singleton_response_fraction=sum(n == 1 for n in sizes) / k,
                                supported_historical_cluster_count=sum(n >= 2 for n in sizes))
                if ambiguous:
                    assert not math.isfinite(number(r['distribution_tv']))
                else:
                    expected['distribution_tv'] = sum(abs(n / k - m / len(v)) for n, m in zip(sizes + [0], vc)) / 2
                for field, expected_value in expected.items():
                    error = abs(number(r[field]) - expected_value)
                    assert error < 1e-10, (field, key, error)
                    max_error = max(max_error, error)
                if int(r['replicate']) in (0, 199):
                    metric = 0 if r['metric'] == 'ospa30' else 1
                    tau = float(r['threshold_degrees'])
                    expected_choices = [[j for j, g in enumerate(groups)
                                         if all(distances[tuple(sorted((person, x)))][metric] <= tau + 1e-12 for x in g)] for person in v]
                    assert choices == expected_choices, key
                    geometry_count += 1
            prefix[key] = r
            prefix_count += 1
        for r in blocks['full']:
            key = (r['split_id'], r['config'], int(r['k']))
            assert key not in full
            full[key] = r
        for r in blocks['adjacent']:
            start, end = int(r['from_k']), int(r['to_k'])
            key = (r['split_id'], r['config'], end)
            left, right = prefix[(r['split_id'], r['config'], start)], prefix[key]
            assert r['from_status'] == left['prefix_status'] and r['to_status'] == right['prefix_status']
            value = float('nan')
            if r['from_status'] == r['to_status'] == 'unique':
                labels = [{person: j for j, g in enumerate(json.loads(t['prefix_clusters_json'])) for person in g} for t in [left, right]]
                common = json.loads(left['prefix_canonical_ids_json'])
                value = sum((labels[0][x] == labels[0][y]) != (labels[1][x] == labels[1][y]) for x, y in combinations(common, 2)) / math.comb(start, 2)
                assert abs(value - number(r['coassignment_disagreement'])) < 1e-10
            else:
                assert not math.isfinite(number(r['coassignment_disagreement']))
            adjacent_values[key] = (start, value)
            adjacent_count += 1
        def measurement(path, measure, key):
            r = prefix.get(key, {})
            state = r.get('prefix_status')
            if path == 'full_history_fixed':
                return number(full.get(key, {}).get(measure))
            if path == 'adjacent_prefix':
                return adjacent_values.get(key, (None, float('nan')))[1]
            if measure.endswith('_indicator'):
                return float(state == measure.removesuffix('_indicator')) if state else float('nan')
            if state != 'unique':
                return float('nan')
            if measure == 'cluster_count':
                return len(json.loads(r['prefix_clusters_json']))
            return number(r.get(measure))
        masks = {}
        for r in blocks['masks']:
            scheme, config, window, path, measure = r['scheme'], r['config'], int(r['max_k']), r['path'], r['measure']
            key = (scheme, config, window, path, measure)
            assert key not in masks
            nodes = json.loads(r['nodes_json'])
            expected_nodes = [k for k in [3, 5, 8, 10, 12, 15] if k <= window]
            if path == 'adjacent_prefix':
                assert json.loads(r['from_k_by_to_k_json']) == {str(b): a for a, b in zip(expected_nodes, expected_nodes[1:])}
                expected_nodes = expected_nodes[1:]
            assert nodes == expected_nodes
            sg = source_support[context]
            sg = sg[sg.scheme == scheme]
            eligible = list(sg.loc[(sg.history_n >= window) & (sg.validation_n >= 2), 'split_id'])
            expected = {sid for sid in eligible if all(math.isfinite(measurement(path, measure, (sid, config, k))) for k in nodes)}
            declared = json.loads(r['valid_split_ids_json'])
            assert len(sg) == int(r['all_splits']) == 200
            assert len(eligible) == int(r['support_eligible_splits'])
            assert len(declared) == len(set(declared)) == int(r['valid_splits'])
            assert set(declared) == expected, (context, key)
            node_counts = {str(k): sum(math.isfinite(measurement(path, measure, (sid, config, k))) for sid in eligible) for k in nodes}
            assert node_counts == json.loads(r['per_node_valid_splits_json'])
            masks[key] = (set(declared), set(nodes), set())
            window_count += 1
        for r in blocks['values']:
            key = (r['scheme'], r['config'], int(r['max_k']), r['path'], r['measure'])
            declared, nodes, seen = masks[key]
            sid, k = r['split_id'], int(r['k'])
            assert sid in declared and k in nodes and (sid, k) not in seen
            seen.add((sid, k))
            expected = measurement(r['path'], r['measure'], (sid, r['config'], k))
            error = abs(float(r['value']) - expected)
            assert error < 1e-10
            if r['path'] == 'adjacent_prefix':
                assert int(r['from_k']) == adjacent_values[(sid, r['config'], k)][0]
            max_error = max(max_error, error)
            value_count += 1
        assert all(len(seen) == len(sids) * len(nodes) for sids, nodes, seen in masks.values())
        if ordinal % 30 == 0:
            print(f'独立审查 {ordinal + 1}/270 context；已核对 {value_count} 固定窗口数值', flush=True)
    assert all(h is None for h in heads.values())
    result = dict(status='passed', core_support_identity_rows=len(support), prefix_identity_arithmetic_rows=prefix_count,
                  prefix_validation_geometry_groups=geometry_count, geometry_sample='replicate 0 and 199, all available contexts/configs/k',
                  adjacent_membership_rows=adjacent_count, fixed_window_masks=window_count, fixed_window_values=value_count,
                  maximum_numeric_difference=max_error, old_outputs_modified=False, stopping_rule_defined=False)
    for filename, n in [('prefix_validation.csv.gz', prefix_count), ('adjacent_prefix_membership.csv.gz', adjacent_count),
                        ('fixed_window_membership.csv.gz', window_count), ('fixed_window_values.csv.gz', value_count)]:
        assert n == qa['output_rows'][filename]
    (review / 'INDEPENDENT_CORE_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def summarize_files(out):
    contexts, comparisons = [], []
    for i, (_, rows) in enumerate(context_stream(out / 'core/fixed_window_values.csv.gz')):
        f = pd.DataFrame(rows)
        for field in ['value', 'k', 'max_k', 'replicate']:
            f[field] = pd.to_numeric(f[field], errors='raise')
        c, _ = summarize_curves(f)
        contexts.append(c)
        selected = f[(f.path == 'full_history_fixed') & (f.measure == 'distribution_tv')].copy()
        comparisons.append(selected[META + [x for x in STRATA if x not in META] + ['replicate', 'k', 'value']])
        if i % 15 == 0:
            print(f'流式统计：已处理 {i + 1} 个有窗口值的 context', flush=True)
    contexts = pd.concat(contexts, ignore_index=True)
    buildings = summarize_buildings(contexts)
    review = out / 'review'
    save(review, 'context_curves.csv.gz', contexts)
    save(review, 'building_curves.csv.gz', buildings)
    comparison = pd.concat(comparisons, ignore_index=True)
    pairs, summary = matched_curve_distances(comparison)
    save(review, 'matched_image_pair_distances.csv.gz', pairs)
    save(review, 'building_relation_summary.csv', summary)
    return contexts, buildings


def recompute_relations(out):
    usecols = META + [x for x in STRATA if x not in META] + ['replicate', 'k', 'value']
    selected = []
    for chunk in pd.read_csv(out / 'core/fixed_window_values.csv.gz', usecols=usecols, chunksize=200000):
        selected.append(chunk[(chunk.path == 'full_history_fixed') & (chunk.measure == 'distribution_tv')].copy())
    pairs, summary = matched_curve_distances(pd.concat(selected, ignore_index=True))
    save(out / 'review', 'matched_image_pair_distances.csv.gz', pairs)
    save(out / 'review', 'building_relation_summary.csv', summary)


def render_figures(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'Microsoft YaHei', 'axes.unicode_minus': False, 'font.size': 9})
    review, figdir = out / 'review', out / 'figures'
    figdir.mkdir(exist_ok=True)
    coverage = pd.read_csv(review / 'building_coverage.csv')
    counts = pd.read_csv(review / 'context_split_coverage.csv')
    curves = pd.read_csv(review / 'context_curves.csv.gz')
    buildings = pd.read_csv(review / 'building_curves.csv.gz')
    relation = pd.read_csv(review / 'building_relation_summary.csv')
    manifest = []
    def finish(fig, name, kind, building=''):
        fig.savefig(figdir / name, dpi=150)
        plt.close(fig)
        manifest.append(dict(figure='figures/' + name, kind=kind, building_id=building))
    f = coverage.sort_values('canonical_responses')
    fig, axes = plt.subplots(1, 2, figsize=(15, 10), sharey=True)
    bottom = np.zeros(len(f))
    for field, name, color in [('manual_responses', 'Manual', '#4878b0'), ('semi_responses', 'Semi', '#46a08b'), ('oos_responses', '历史 oos', '#bd9a46')]:
        axes[0].barh(f.building_id, f[field], left=bottom, color=color, label=name)
        bottom += f[field].to_numpy()
    for y, n in enumerate(bottom):
        axes[0].text(n + 3, y, str(int(n)), va='center', fontsize=8)
    for i, (field, label, color) in enumerate([('available_contexts', '可作至少一个前缀', '#b4b4b4'),
            ('window_8_support_contexts', '支持 3→8 窗口', '#4878b0'), ('window_15_support_contexts', '支持 3→15 窗口', '#46a08b')]):
        axes[1].barh(np.arange(len(f)) + (i - 1) * .24, f[field], height=.23, label=label, color=color)
    axes[0].set_xlim(0, max(bottom) * 1.12)
    axes[0].set_xlabel('canonical 响应份数'); axes[1].set_xlabel('完整 context 数（至少一次划分满足人数支持）')
    axes[0].legend(); axes[1].legend()
    fig.suptitle('22 栋楼：全部旧数据覆盖与可验证范围')
    fig.text(.5, .012, '每楼累计响应不等于每图人数；主方案为楼内人员 2/3 留作历史，剩余人员验证。', ha='center')
    fig.tight_layout(rect=[0, .03, 1, .97]); finish(fig, 'building_coverage.png', 'coverage')
    primary = curves[(curves.scheme == 'two_thirds') & (curves.config == 'ospa30_t6')]
    bc = buildings[(buildings.scheme == 'two_thirds') & (buildings.config == 'ospa30_t6')]
    strata = ['stage', 'block_index', 'raw_condition', 'initialization_kind']
    labels = {'manual': 'Manual', 'semi': 'Semi', 'oos': '历史 oos', 'not_applicable': '',
              'control_natural': '自然 control', 'trap_natural': '自然 trap',
              'trap_synthetic_disjoint_source': '合成 trap', 'c1_reference_derived_reconstruction': '参考派生初始化'}
    panels = [('full_history_fixed', 'distribution_tv', '固定历史分类 TV（回顾性）'),
              ('prefix_validation', 'distribution_tv', '仅前 k 人定簇：验证 TV'),
              ('prefix_structure', 'singleton_response_fraction', '历史单例响应占比'),
              ('adjacent_prefix', 'coassignment_disagreement', '相邻前缀成员关系变化')]
    for building in coverage.building_id:
        scope = counts[(counts.building_id == building) & (counts.scheme == 'two_thirds')]
        source_groups = list(scope.groupby(strata, dropna=False, sort=True))
        fig, axes = plt.subplots(len(source_groups), 4, figsize=(17, 2.65 * len(source_groups) + .9), squeeze=False)
        images = sorted(scope.image_id.unique())
        colors = {image: plt.get_cmap('tab20')(i % 20) for i, image in enumerate(images)}
        for row, (key, sg) in enumerate(source_groups):
            window = next((n for n in [15, 8, 5] if sg[f'window_{n}_support_splits'].gt(0).any()), None)
            title = f'{key[0]} / {labels.get(key[2], key[2])}'
            if key[1]:
                title += f' / block {key[1]}'
            if labels.get(key[3], key[3]):
                title += '\n' + labels.get(key[3], key[3])
            image_ids = set(sg.image_id)
            selection = primary[(primary.building_id == building) & primary.context_key.isin(sg.context_key)]
            means = bc[bc.building_id == building]
            for col, (path, measure, panel_title) in enumerate(panels):
                ax = axes[row, col]
                ax.set_title(panel_title, fontsize=9)
                if col == 0:
                    ax.set_ylabel(title, fontsize=9)
                if window is None:
                    ax.text(.5, .5, f'{len(image_ids)} 图 / {len(sg)} context\n无完整 3→5 人数窗口', transform=ax.transAxes, ha='center', va='center')
                    ax.set_xticks([]); ax.set_yticks([])
                    continue
                g = selection[(selection.max_k == window) & (selection.path == path) & (selection.measure == measure)]
                for image, cg in g.groupby('image_id'):
                    cg = cg.sort_values('k')
                    ax.plot(cg.k, cg['mean'], 'o-', color=colors[image], alpha=.55, lw=1, markersize=2.5, label=image[-8:])
                if len(g):
                    mean = g.groupby('k')['mean'].mean()
                    ax.plot(mean.index, mean.values, 'o-', color='#202630', lw=2.2, markersize=3)
                    minimum, maximum = int(g.valid_splits.min()), int(g.valid_splits.max())
                    note = f'{g.image_id.nunique()}/{len(image_ids)} 图；每图 {minimum}–{maximum}/200 划分'
                    if col == 0:
                        ax.legend(fontsize=6, ncol=2, loc='best', title='图ID末8位', title_fontsize=6)
                else:
                    note = '人数支持存在；本指标无全窗口有效值'
                ax.text(.02, .98, note, transform=ax.transAxes, va='top', fontsize=6.8)
                ax.set_ylim(-.03, 1.08); ax.set_xlim(2.7, window + .3)
                ax.set_xticks([k for k in [3, 5, 8, 10, 12, 15] if k <= window]); ax.grid(alpha=.16)
                ax.set_xlabel('历史可算前缀人数' if path != 'adjacent_prefix' else '相邻比较的终点人数', fontsize=8)
        total = coverage[coverage.building_id == building].iloc[0]
        fig.suptitle(f'{building}：{total.canonical_responses} 份响应 / {total.images} 图 / {total.contexts} context', fontsize=13)
        fig.text(.5, .012, 'cap=30° / 簇阈值6° / 2/3划分。每层按人数支持选最长窗口；细线为逐图，深线为图像等权均值。各指标有效集合分别固定。', ha='center', fontsize=8)
        fig.tight_layout(rect=[0, .035, 1, .97]); finish(fig, f'building_{building}.png', 'building_curves', building)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharey=True)
    order = ['ospa30_t3', 'ospa30_t6', 'ospa30_t12', 'ospa60_t6']
    for row, scheme in enumerate(['two_thirds', 'sixty_percent']):
        for col, window in enumerate([8, 15]):
            ax = axes[row, col]
            g = relation[(relation.stage == 'P1') & (relation.raw_condition == 'manual') &
                         (relation.scheme == scheme) & (relation.max_k == window)].set_index('config').reindex(order)
            ax.plot(range(4), g.pair_matched_within_distance, 'o-', label='同楼图像对（楼对端点匹配权重）')
            ax.plot(range(4), g.between_building_distance, 's-', label='异楼图像对（先楼对等权）')
            ax.set_xticks(range(4), ['30° / 3°', '30° / 6°', '30° / 12°', '60° / 6°'])
            ax.set_title(f'历史比例 {"2/3" if scheme == "two_thirds" else "60%"}；3→{window} 窗口')
            ax.set_xlabel('距离截断 / 分簇阈值'); ax.grid(alpha=.2); ax.set_ylim(bottom=0)
    axes[0, 0].legend(fontsize=8); axes[0, 0].set_ylabel('匹配排列后的 TV 曲线平均绝对差'); axes[1, 0].set_ylabel('匹配排列后的 TV 曲线平均绝对差')
    fig.suptitle('P1 Manual：同楼曲线是否比异楼曲线更相似？')
    fig.text(.5, .013, '相同楼集合；图对匹配共同排列，比较两侧匹配楼对端点权重。仅作描述性比较，不是独立检验或新图预测。', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .035, 1, .96]); finish(fig, 'within_between_building.png', 'building_relation')
    selected_panels = panels[:2] + [('prefix_validation', 'validation_outside_fraction', '仅前缀分类：验证 outside'),
                     ('prefix_validation', 'validation_ambiguous_fraction', '仅前缀分类：验证 ambiguous'),
                     ('prefix_structure', 'supported_historical_cluster_count', '至少2人支持的簇数'),
                     ('prefix_structure', 'singleton_response_fraction', '单例响应占比'),
                     ('prefix_structure', 'non_unique_indicator', '前缀分区不唯一率'), panels[3]]
    fig, axes = plt.subplots(4, 2, figsize=(14, 14))
    for ax, (path, measure, title) in zip(axes.flat, selected_panels):
        g = bc[(bc.stage == 'P1') & (bc.raw_condition == 'manual') & (bc.max_k == 15) & (bc.path == path) & (bc.measure == measure)]
        for i, (building, bg) in enumerate(g.groupby('building_id', sort=True)):
            bg = bg.sort_values('k')
            ax.plot(bg.k, bg['mean'], 'o-', markersize=3, color=plt.get_cmap('tab20')(i), label=building)
        ax.set_title(title); ax.set_xlabel('历史可算前缀人数'); ax.grid(alpha=.18)
        ax.set_xticks([3, 5, 8, 10, 12, 15]); ax.set_ylim(bottom=0)
        if measure != 'supported_historical_cluster_count':
            ax.set_ylim(-.025, 1.05)
    axes[0, 0].legend(fontsize=7, ncol=2)
    fig.suptitle('P1 Manual：逐楼的多维证据（cap30° / 阈值6° / 2/3 / 3→15固定窗口）')
    fig.text(.5, .012, '每条楼级曲线先图内平均，再对图等权；不同指标支持集合不同。平坦、正熵、多簇或低TV均不单独构成收敛判定。', ha='center', fontsize=8)
    fig.tight_layout(rect=[0, .03, 1, .97]); finish(fig, 'p1_manual_building_overview.png', 'multidimensional_overview')
    save(review, 'figure_index.csv', pd.DataFrame(manifest))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--coverage-only', action='store_true')
    parser.add_argument('--audit-only', action='store_true')
    parser.add_argument('--figures-only', action='store_true')
    parser.add_argument('--relations-only', action='store_true')
    args = parser.parse_args()
    out = args.out or args.root / OUTPUT
    review = out / 'review'
    review.mkdir(parents=True, exist_ok=True)
    if args.relations_only:
        recompute_relations(out)
        return
    if args.figures_only:
        render_figures(out)
        return
    prepare_coverage(args.root, review)
    if args.audit_only:
        audit_core(args.root, out)
        return
    if not args.coverage_only:
        summarize_files(out)
    print('逐楼覆盖及请求的统计已写入', review, flush=True)


if __name__ == '__main__':
    main()
