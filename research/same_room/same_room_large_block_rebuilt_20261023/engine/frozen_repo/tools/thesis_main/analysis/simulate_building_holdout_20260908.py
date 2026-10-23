"""同building真实历史人员回放：训练/验证身份隔离，不生成虚拟标注。"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import sys
import warnings
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.preflight_statistics_20260906 import moments, iid_var

OUTPUT = 'analysis_results/building_holdout_exploration_20260908_v1'
BASE = 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
META = ['context_key', 'image_id', 'building_id', 'stage', 'block_index', 'raw_condition', 'initialization_source']
VALUES = ['absolute_disagreement_gap', 'signed_disagreement_gap', 'medoid_validation_distance',
          'medoid_gain_to_full_history', 'train_plugin_sd', 'count_distribution_tv']


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def save(out, name, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if len(frame.columns) == 0:
        raise ValueError('Missing output schema: ' + name)
    frame.to_csv(out / name, index=False, float_format='%.12g')
    return frame


def history_precision(history_matrix, ks):
    """经验iid方差插件；只消费训练块，不使用有限人群归零修正。"""
    matrix = np.asarray(history_matrix, float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or len(matrix) < 2:
        raise ValueError('At least two historical responses are required')
    if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T) or not np.allclose(np.diag(matrix), 0):
        raise ValueError('Invalid distance matrix')
    m = moments(matrix)
    return {int(k): math.sqrt(iid_var(m, int(k))) for k in ks if k >= 2}


def distribution_tv(left, right):
    if len(left) == 0 or len(right) == 0:
        raise ValueError('Empty distribution is not agreement')
    a, b = Counter(left), Counter(right)
    return .5 * sum(abs(a[x]/len(left) - b[x]/len(right)) for x in a.keys() | b.keys())


def prefix_results(matrix, history, validation, ks):
    """历史全组只拟合精度诊断；每个代表仅使用其历史前缀，验证组始终固定。"""
    if set(history) & set(validation):
        raise ValueError('history/validation overlap')
    if len(set(history)) != len(history) or len(set(validation)) != len(validation):
        raise ValueError('Duplicate worker within a group')
    if min(len(history), len(validation)) < 2:
        raise ValueError('Insufficient independent pair support')
    matrix = np.asarray(matrix, float)
    hh = matrix[np.ix_(history, history)]
    sd = history_precision(hh, ks)
    full_pick = history[int(hh.sum(axis=1).argmin())]
    full_risk = float(matrix[full_pick, validation].mean())
    v = len(validation)
    target = float(matrix[np.ix_(validation, validation)].sum()/(v*(v-1)))
    full_d = float(hh.sum()/(len(history)*(len(history)-1)))
    rows = []
    for k in sorted(set(ks)):
        if not 2 <= k <= len(history):
            continue
        ids = history[:k]
        sub = matrix[np.ix_(ids, ids)]
        pick = ids[int(sub.sum(axis=1).argmin())]
        estimate = float(sub.sum()/(k*(k-1)))
        risk = float(matrix[pick, validation].mean())
        rows.append(dict(k=k, history_full_d=full_d, history_prefix_d=estimate, validation_d=target,
                         signed_disagreement_gap=estimate-target, absolute_disagreement_gap=abs(estimate-target),
                         medoid_index=pick, medoid_validation_distance=risk,
                         full_history_medoid_validation_distance=full_risk,
                         medoid_gain_to_full_history=risk-full_risk,
                         train_plugin_sd=sd[k], is_full_history=k == len(history)))
    return rows


def load_measurements(root, out):
    from tools.thesis_main.analysis.prepare_uncertainty_visual_review import helpers
    from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
    from tools.thesis_main.analysis.audit_annotation_research_data_20260905 import _dense_boundaries
    from tools.thesis_main.analysis.preflight_data_20260906 import distance_matrix
    audit, _ = helpers()
    annotations = read(root / BASE / 'annotations.csv.gz')
    assert annotations.canonical_annotation_id.is_unique
    assert not annotations.duplicated(['context_key', 'worker_id']).any()
    versions = [json.loads(x) for x in (root / BASE / 'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()]
    raw = {v['canonical_annotation_id']: v['points_1024x512'] for v in versions if str(v['selected_canonical_version']).lower() == 'true'}
    assert set(raw) == set(annotations.canonical_annotation_id)
    traces = read(root / 'analysis_results/uncertainty_decision_ready_20260908_v1/response_index.csv.gz')
    init = {key: json.dumps(sorted(set(g.initialization_reconstructed_source)-{''}), ensure_ascii=False)
            for key, g in traces.groupby('context_key')}
    polygons, bands, point_counts, status = {}, {}, {}, []
    for a in annotations.to_dict('records'):
        aid = a['canonical_annotation_id']; points = raw[aid]
        point_counts[aid] = len(points)
        floor_status = 'computable'
        try:
            polygons[aid] = audit.footprint(points)
        except (ValueError, IndexError, TypeError) as exc:
            floor_status = str(exc)
        first = normalize_geometry(np.asarray(points).reshape(-1, 2))
        strict = normalize_geometry(first['canonical_points']) if first['valid'] else first
        if strict['valid']:
            bands[aid] = _dense_boundaries(strict['pairs'])
        for metric, state in [('original_floor', floor_status), ('legacy_linear', 'computable' if strict['valid'] else strict['reason']),
                              ('raw_endpoint_count', 'computable_descriptor_not_geometry')]:
            status.append({k: a[k] for k in META if k != 'initialization_source'} | dict(
                canonical_annotation_id=aid, worker_id=a['worker_id'], metric=metric, status=state,
                raw_point_count=len(points), raw_coordinates_changed=False,
                raw_adjacency_changed=False, legacy_normalization_used=metric == 'legacy_linear'))
    status_frame = save(out, 'response_metric_status.csv.gz', status)
    expected = read(root / 'analysis_results/uncertainty_decision_ready_20260908_v1/geometry/human_bi_comparisons.csv.gz')
    expected = expected[(expected.reading == 'serialized_adjacency') & (expected.representation == 'native_uv')].set_index('canonical_annotation_id')
    actual = status_frame[status_frame.metric == 'original_floor'].set_index('canonical_annotation_id')
    assert actual.status.sort_index().equals(expected.human_status.sort_index())
    legacy = read(root / 'analysis_results/preflight_20260906_v2/record_inventory.csv').set_index('canonical_annotation_id')
    assert {k for k in legacy.index if legacy.loc[k, 'valid'].lower() == 'true'} == set(bands)
    tasks = read(root / 'analysis_results/preflight_20260906_v2/task_inventory.csv').set_index('context')
    groups, pair_rows = [], []
    for context, frame in annotations.groupby('context_key', sort=True):
        frame = frame.sort_values('worker_id', key=lambda s: s.astype(int))
        rows = frame.to_dict('records'); ids = list(frame.canonical_annotation_id)
        common = set(ids) & set(polygons) & set(bands)
        for metric in ('original_floor', 'legacy_linear', 'raw_endpoint_count'):
            good = [x for x in ids if x in (polygons if metric == 'original_floor' else bands if metric == 'legacy_linear' else raw)]
            n = len(good); matrix = np.zeros((n, n))
            if metric == 'legacy_linear' and n:
                matrix = distance_matrix([bands[x] for x in good])
            elif metric == 'raw_endpoint_count':
                counts = np.array([point_counts[x] for x in good]); matrix = (counts[:, None] != counts[None, :]).astype(float)
            else:
                for i in range(n):
                    for j in range(i):
                        matrix[i, j] = matrix[j, i] = audit.dp(polygons[good[i]], polygons[good[j]])
            assert np.isfinite(matrix).all() and (matrix >= -1e-12).all() and (matrix <= 1+1e-12).all()
            if metric == 'legacy_linear' and n >= 2:
                key = '|'.join(str(rows[0][k]) for k in ('stage', 'block_index', 'raw_condition', 'image_id'))
                assert abs(matrix.sum()/(n*(n-1)) - float(tasks.loc[key, 'D_mean'])) < 1e-10
            for i in range(n):
                for j in range(i):
                    pair_rows.append(dict(context_key=context, metric=metric, left_canonical=good[i], right_canonical=good[j], distance=float(matrix[i,j])))
            for cohort in (['all_responses'] if metric == 'raw_endpoint_count' else ['method_available', 'common_geometry']):
                subset = good if cohort != 'common_geometry' else [x for x in good if x in common]
                ii = [good.index(x) for x in subset]
                lookup = frame.set_index('canonical_annotation_id')
                meta = {k: rows[0][k] for k in META if k != 'initialization_source'}
                meta['initialization_source'] = init[context]
                groups.append(dict(**meta, metric=metric, cohort=cohort, ids=subset,
                                   workers=[str(lookup.loc[x, 'worker_id']) for x in subset],
                                   matrix=matrix[np.ix_(ii, ii)], counts=[point_counts[x] for x in subset],
                                   raw_workers=set(frame.worker_id)))
    save(out, 'pairwise_distances.csv.gz', pair_rows)
    qa = dict(canonical=len(annotations), versions=len(versions), metrics=status_frame.groupby(['metric','status']).size().to_dict(),
              original_floor_computable=len(polygons), legacy_linear_computable=len(bands), common_geometry=len(set(polygons)&set(bands)),
              raw_endpoint_descriptors=len(point_counts), pair_rows=len(pair_rows), raw_order_unchanged=True,
              same_as_previously_audited_status=True)
    qa['metrics'] = [{'metric': k[0], 'status': k[1], 'count': int(v)} for k,v in qa['metrics'].items()]
    (out / 'MEASUREMENT_QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf-8')
    return annotations, groups


def summarize_local(rows, key_fields, values):
    if not rows:
        return []
    frame = pd.DataFrame(rows); summaries = []
    for key, data in frame.groupby(key_fields, dropna=False, sort=True):
        keys = key if isinstance(key, tuple) else (key,)
        row = dict(zip(key_fields, keys)); row['split_count'] = len(data)
        for value in values:
            x = pd.to_numeric(data[value], errors='coerce').dropna()
            row[value+'_count'] = len(x)
            row[value+'_mean'] = float(x.mean()) if len(x) else np.nan
            row[value+'_q10'] = float(x.quantile(.1)) if len(x) else np.nan
            row[value+'_q90'] = float(x.quantile(.9)) if len(x) else np.nan
        summaries.append(row)
    return summaries


def run(root, out):
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((out / 'EXPLORATION_PLAN.json').read_text(encoding='utf-8'))
    print('建立两种几何度量及全部原始端点数描述...', flush=True)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always', RuntimeWarning)
        annotations, groups = load_measurements(root, out)
    warning_rows = [dict(message=str(w.message), source=w.filename, line=w.lineno) for w in captured]
    (out / 'NUMERIC_WARNINGS.json').write_text(json.dumps(warning_rows, ensure_ascii=False, indent=2), encoding='utf-8')
    people = read(out / 'census/worker_splits.csv.gz')
    schedules = defaultdict(list)
    for row in people.to_dict('records'):
        row['history'] = json.loads(row['history_worker_ids_json']); row['validation'] = json.loads(row['validation_worker_ids_json'])
        assert not set(row['history']) & set(row['validation'])
        schedules[row['building_id']].append(row)
    context_summaries, contrast_summaries, candidate_summaries = [], [], []
    stream_counts, support_counts = Counter(), Counter()
    with ExitStack() as stack:
        writers = {}
        def emit(name, row):
            if name not in writers:
                stream = stack.enter_context(gzip.open(out / name, 'wt', encoding='utf-8', newline=''))
                writers[name] = csv.DictWriter(stream, fieldnames=list(row))
                writers[name].writeheader()
            writers[name].writerow(row); stream_counts[name] += 1
        for ordinal, group in enumerate(groups):
            if ordinal % 150 == 0:
                print(f'回放输入视图 {ordinal}/{len(groups)}', flush=True)
            position = {w:i for i,w in enumerate(group['workers'])}
            metadata = {k:group[k] for k in META+['metric','cohort']}
            local_rows, local_contrasts, local_candidates = [], [], []
            for split in schedules[group['building_id']]:
                h = [position[w] for w in split['history'] if w in position]
                v = [position[w] for w in split['validation'] if w in position]
                nh, nv = len(h), len(v)
                support = 'available' if min(nh,nv)>=2 else 'history_lt2' if nh<2 else 'validation_lt2'
                raw_h = len(set(split['history']) & group['raw_workers']); raw_v = len(set(split['validation']) & group['raw_workers'])
                base = metadata | dict(split_id=split['split_id'], replicate=int(split['replicate']), scheme=split['scheme'],
                                       history_n=nh, validation_n=nv, raw_history_n=raw_h, raw_validation_n=raw_v)
                emit('context_split_support.csv.gz', base | dict(status=support))
                support_counts[(group['metric'],group['cohort'],split['scheme'],support)] += 1
                if support != 'available':
                    continue
                hh = group['matrix'][np.ix_(h,h)]
                precision = history_precision(hh, range(2,21)) if nh>=4 else {}
                candidates = {e: next((k for k,sd in precision.items() if sd<=e), None) for e in plan['training_only_precision_diagnostic']['numeric_sd_tolerances']}
                ks = set(plan['historical_prefix_k']) | {nh} | {k for k in candidates.values() if k is not None}
                results = prefix_results(group['matrix'], h, v, ks)
                by_k = {r['k']:r for r in results}
                for r in results:
                    r['count_distribution_tv'] = distribution_tv([group['counts'][i] for i in h[:r['k']]], [group['counts'][i] for i in v]) if group['metric']=='raw_endpoint_count' else np.nan
                    r['medoid_canonical_id'] = group['ids'][r.pop('medoid_index')] if group['metric']!='raw_endpoint_count' else ''
                    if group['metric']=='raw_endpoint_count':
                        r.pop('medoid_index', None)
                        for f in ('medoid_validation_distance','full_history_medoid_validation_distance','medoid_gain_to_full_history'):
                            r[f] = np.nan
                    emit('heldout_prefix_draws.csv.gz', base | r)
                    local_rows.append(dict(scheme=split['scheme'], k_label=str(r['k']), **{k:r[k] for k in VALUES}, history_n=nh, validation_n=nv))
                    if r['is_full_history']:
                        local_rows.append(dict(scheme=split['scheme'], k_label='full_history', **{k:r[k] for k in VALUES}, history_n=nh, validation_n=nv))
                full = by_k[nh]
                for start in [3,5,8,10,12,15]:
                    if nh < start+2 or start not in by_k:
                        continue
                    r = by_k[start]
                    contrast = dict(start_k=start, end_history_n=nh,
                                    disagreement_gap_improvement=r['absolute_disagreement_gap']-full['absolute_disagreement_gap'],
                                    medoid_validation_improvement=r['medoid_validation_distance']-full['medoid_validation_distance'],
                                    count_tv_improvement=r['count_distribution_tv']-full['count_distribution_tv'])
                    emit('paired_gain_draws.csv.gz', base | contrast)
                    local_contrasts.append(dict(scheme=split['scheme'], **contrast))
                for eps, k in candidates.items():
                    result = by_k.get(k)
                    candidate = dict(tolerance=eps, predicted_k=k, status='history_lt4' if nh<4 else 'not_reached_by20' if k is None else 'candidate',
                                     candidate_within_history=k is not None and k<=nh,
                                     candidate_within_validation=k is not None and k<=nv,
                                     candidate_observed_absolute_gap=result['absolute_disagreement_gap'] if result else np.nan,
                                     candidate_observed_medoid_distance=result['medoid_validation_distance'] if result else np.nan,
                                     candidate_gap_within_same_numeric_tolerance=(result['absolute_disagreement_gap']<=eps) if result else None,
                                     historical_endpoint_abs_gap=full['absolute_disagreement_gap'],
                                     precision_source='historical_only_empirical_iid_plugin_not_confidence_or_stopping_rule')
                    emit('precision_candidates.csv.gz', base | candidate)
                    local_candidates.append(dict(scheme=split['scheme'], history_n=nh, validation_n=nv, **candidate))
            for r in summarize_local(local_rows, ['scheme','k_label'], VALUES+['history_n','validation_n']):
                context_summaries.append(metadata | r)
            for r in summarize_local(local_contrasts, ['scheme','start_k'], ['end_history_n','disagreement_gap_improvement','medoid_validation_improvement','count_tv_improvement']):
                contrast_summaries.append(metadata | r)
            if local_candidates:
                frame = pd.DataFrame(local_candidates)
                for (scheme, eps), g in frame.groupby(['scheme','tolerance']):
                    observed_k = g.predicted_k.dropna()
                    candidate_summaries.append(metadata | dict(scheme=scheme,tolerance=eps,available_splits=len(g),
                        precision_fit_splits=int((g.status!='history_lt4').sum()),candidate_splits=int((g.status=='candidate').sum()),
                        predicted_k_median=observed_k.median() if len(observed_k) else np.nan,
                        predicted_k_q10=observed_k.quantile(.1) if len(observed_k) else np.nan,
                        predicted_k_q90=observed_k.quantile(.9) if len(observed_k) else np.nan,
                        predicted_k_within_history_splits=int(g.candidate_within_history.sum()),
                        predicted_k_within_validation_splits=int(g.candidate_within_validation.sum()),
                        candidate_gap_observed_splits=int(g.candidate_observed_absolute_gap.notna().sum()),
                        candidate_gap_within_tolerance_splits=int(g.candidate_gap_within_same_numeric_tolerance.eq(True).sum())))
    context = save(out, 'context_curve_summary.csv', context_summaries)
    contrasts = save(out, 'context_paired_gain_summary.csv', contrast_summaries)
    save(out, 'context_precision_candidate_summary.csv', candidate_summaries)
    save(out, 'support_summary.csv', [dict(metric=k[0],cohort=k[1],scheme=k[2],status=k[3],split_context_records=v) for k,v in support_counts.items()])
    summary_keys = ['building_id','stage','raw_condition','initialization_source','metric','cohort','scheme']
    def building_summary(frame, axis, value_columns):
        rows = []
        for key, g in frame.groupby(summary_keys+[axis], sort=True):
            r = dict(zip(summary_keys+[axis],key))
            r.update(contexts=g.context_key.nunique(), images=g.image_id.nunique(), minimum_context_splits=int(g.split_count.min()), maximum_context_splits=int(g.split_count.max()))
            for col in value_columns:
                r[col] = g[col].mean()
            rows.append(r)
        return rows
    save(out,'building_curve_summary.csv',building_summary(context,'k_label',[v+'_mean' for v in VALUES]+['history_n_mean','validation_n_mean']))
    save(out,'building_paired_gain_summary.csv',building_summary(contrasts,'start_k',[v+'_mean' for v in ['end_history_n','disagreement_gap_improvement','medoid_validation_improvement','count_tv_improvement']]))
    qa = dict(status='completed',canonical=len(annotations), workers=annotations.worker_id.nunique(), buildings=annotations.building_id.nunique(),
              context_metric_views=len(groups), repetitions=plan['replicates'], scheme_count=len(plan['schemes']),
              streams=dict(stream_counts), context_curve_summary_rows=len(context), context_paired_gain_rows=len(contrasts),
              training_and_validation_worker_overlap=0, new_people=False, old_eligibility_filter=False,
              original_geometry_modified=False, old_clusters_used_for_training=False, reference_used_for_model_selection=False,
              inference='固定历史数据反复划分；均值与分位数描述分组敏感性，不是独立新人试验或总体置信区间')
    (out/'SIMULATION_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    run(args.root.resolve(),args.out or args.root/OUTPUT)
