"""独立核验与可复用诊断；不修改原始点、时间资格或正式协议。"""
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching

from . import local_points as lp


def _none_probability(population, neighbours, k):
    if not 0 <= k <= population:
        raise ValueError('k must be within the available pool')
    available = population - np.asarray(neighbours, dtype=int)
    if np.any(available < 0) or np.any(available > population):
        raise ValueError('invalid neighbour count')
    denominator = math.comb(population, k)
    return np.array([math.comb(int(n), k) / denominator if n >= k else 0. for n in available])


def finite_pool_events(ospa_neighbours, local_neighbours, k):
    """均匀选目标及其余k人；局部相容指一份完整既有作答，不是点并集。"""
    o, h = np.asarray(ospa_neighbours, bool).copy(), np.asarray(local_neighbours, bool).copy()
    if o.ndim != 2 or o.shape[0] != o.shape[1] or h.shape != o.shape or len(o) < 2:
        raise ValueError('expected equally sized square neighbourhood matrices')
    np.fill_diagonal(o, False); np.fill_diagonal(h, False)
    po = _none_probability(len(o)-1, o.sum(1), k).mean()
    ph = _none_probability(len(o)-1, h.sum(1), k).mean()
    neither = _none_probability(len(o)-1, (o | h).sum(1), k).mean()
    return dict(ospa_uncovered=float(po), local_uncovered=float(ph),
                ospa_covered_but_local_uncovered=float(ph-neither),
                local_covered_but_ospa_uncovered=float(po-neither))


def union_point_expectation(point_by_previous_worker, k):
    """目标各点未被k人点并集覆盖的期望比例；不是至少一点新出现的概率。"""
    a = np.asarray(point_by_previous_worker, bool)
    if a.ndim != 2 or not a.shape[0]:
        raise ValueError('nonempty point by worker matrix required')
    return float(_none_probability(a.shape[1], a.sum(1), k).mean())


def stable_angular(a, b):
    """同一半像素约定，用atan2独立验证arccos及弦长实现。"""
    a, b = lp.vectors(a), lp.vectors(b)
    return np.degrees(np.arctan2(np.linalg.norm(np.cross(a[:, None], b[None, :]), axis=2),
                               np.clip(a @ b.T, -1, 1)))


def time_baselines(records):
    """复用上轮来源审计：已知人员的目标作答留出，不是新人/在线预测。"""
    required = ['id','worker','context','building','image_id','seconds','status',
                'strict_eligible','source_seconds_match']
    if not set(required) <= set(records.columns) or records.id.duplicated().any():
        raise ValueError('time schema or identity mismatch')
    for column in ['strict_eligible','source_seconds_match']:
        if records[column].isna().any() or not records[column].isin([True,False]).all():
            raise ValueError('time qualification must be explicit boolean: '+column)
    d = records[records.strict_eligible & records.source_seconds_match].copy()
    if not (d.status.eq('owner_valid_complete').all() and np.isfinite(d.seconds).all() and (d.seconds>0).all()):
        raise ValueError('invalid qualified active time')
    if d.duplicated(['image_id','context','worker']).any():
        raise ValueError('repeated worker in time comparison unit')
    d['log_seconds'] = np.log(d.seconds); d['speed_baseline'] = np.nan
    for _, g in d.groupby(['worker','context']):
        for building, group in g.groupby('building'):
            train = g[g.building != building]
            if len(train) >= 5: d.loc[group.index,'speed_baseline'] = train.log_seconds.median()
    d['speed_adjusted_log_time'] = d.log_seconds-d.speed_baseline
    predictions = []
    for _, g in d[np.isfinite(d.speed_baseline)].groupby(['image_id','context']):
        if len(g) < 5: continue
        for i, target in g.iterrows():
            predicted = target.speed_baseline + g.drop(index=i).speed_adjusted_log_time.median()
            predictions.append(dict(id=target.id,image_id=target.image_id,context=target.context,
                                    baseline_abs_log_error=abs(target.log_seconds-target.speed_baseline),
                                    peer_abs_log_error=abs(target.log_seconds-predicted),
                                    information='known_person_other_buildings_and_other_workers_same_image'))
    return d, pd.DataFrame(predictions)


def run(root=lp.ROOT, output_dir=None):
    root = Path(root); out = Path(output_dir) if output_dir is not None else root/'local_recheck'
    rows, audit = lp.load(root); by = {r['canonical_annotation_id']: r for r in rows}
    p = pd.read_csv(out/'pairwise.csv')
    errors = {key: 0. for key in ['ospa1', 'ospa2', 'hausdorff']}
    matches_checked = 0
    for pair in p.itertuples():
        c = stable_angular(by[pair.id_a]['effective_points_1024x512'], by[pair.id_b]['effective_points_1024x512'])
        m, n = c.shape; cap = np.minimum(c, 30)
        i, j = linear_sum_assignment(cap); i2, j2 = linear_sum_assignment(cap**2)
        independent = dict(ospa1=(cap[i, j].sum()+30*abs(m-n))/max(m,n),
                           ospa2=np.sqrt(((cap[i2,j2]**2).sum()+900*abs(m-n))/max(m,n)),
                           hausdorff=max(c.min(0).max(), c.min(1).max()))
        for key, value in independent.items(): errors[key] = max(errors[key], abs(value-getattr(pair,key)))
        # Independent graph matching, using original angles so threshold roundoff
        # is not mistaken for an algorithm disagreement.
        original = lp.angular(by[pair.id_a]['effective_points_1024x512'], by[pair.id_b]['effective_points_1024x512'])
        for radius in lp.RADII:
            matched = maximum_bipartite_matching(csr_matrix(original <= radius), perm_type='column')
            assert int((matched >= 0).sum()) == getattr(pair, f'matched_{int(radius)}')
            matches_checked += 1
    assert max(errors.values()) < 3e-6, errors

    cache = json.loads((out/'cache_no_borrowed.json').read_text(encoding='utf-8'))
    prior = pd.read_csv(out/'no_borrowed_next_person.csv')
    for record in prior.itertuples():
        g = cache[record.image_id+'|'+record.condition]
        event = finite_pool_events(np.array(g['Ds']['ospa1']) <= 6,
                                   np.array(g['Ds']['hausdorff']) <= record.local_radius, record.k)
        for key, value in event.items(): assert abs(value-getattr(record,key)) < 1e-12

    # Distinguish target-point novelty from lack of a symmetric full-response
    # neighbour. Restore only explicitly imputed records in a separate view.
    unions, witnesses = [], []
    for key, g in cache.items():
        if not key.endswith('|manual') or len(g['ids']) < 19: continue
        pts = [by[cid]['raw_points_1024x512'] if by[cid]['imputed_point'] else by[cid]['effective_points_1024x512'] for cid in g['ids']]
        image_values = []
        for target, target_points in enumerate(pts):
            others = [i for i in range(len(pts)) if i != target]
            near = np.column_stack([stable_angular(target_points, pts[i]).min(1) for i in others])
            covers = near <= 9
            image_values.append(union_point_expectation(covers, 8))
            h = np.array(g['Ds']['hausdorff'])[target, others]
            # One concrete counterexample per image is enough for interpretation.
            if not any(w['key'] == key for w in witnesses):
                for a, b in itertools.combinations(range(len(others)), 2):
                    if h[a] > 9 and h[b] > 9 and covers[:, [a,b]].any(1).all():
                        witnesses.append(dict(key=key,code=g['code'],target=g['workers'][target],
                                              previous_a=g['workers'][others[a]],previous_b=g['workers'][others[b]],
                                              h_a=float(h[a]),h_b=float(h[b]),all_target_points_covered_by_union=True))
                        break
        unions.append(dict(key=key,code=g['code'],N=len(pts),k=8,radius=9,
                           expected_fraction_target_points_unseen=float(np.mean(image_values)),
                           meaning='directed_point_union_expectation_not_probability_any_new_point'))
    pd.DataFrame(unions).to_csv(out/'independent_union_point_expectation.csv',index=False)
    pd.DataFrame(witnesses).to_csv(out/'independent_union_counterexamples.csv',index=False)

    # Reuse the existing frozen parser without importing optional HDBSCAN.
    repo = Path(__file__).resolve().parents[4]
    path = repo/'analysis_results/full_corpus_research_received_20260918/full_study_20260918/code/legacy_reproduction.py'
    spec = importlib.util.spec_from_file_location('frozen_pairing_helpers', path)
    legacy = importlib.util.module_from_spec(spec)
    previous_bytecode = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(legacy)
    finally:
        sys.dont_write_bytecode = previous_bytecode
    ns = legacy.legacy_functions(json.loads((root/'inputs/key39.json').read_text(encoding='utf-8')))
    flags = []
    for r in rows:
        if r['worker_id'] in {'W019','W026'} or not r['calculation_included']: continue
        norm = ns['normalize_geometry'](r['effective_points_1024x512'])
        if not norm['valid']: continue
        a = legacy.pairs3(norm)
        same = ((a[:,1]<255.5)&(a[:,2]<255.5)) | ((a[:,1]>255.5)&(a[:,2]>255.5))
        if same.any(): flags.append(dict(id=r['canonical_annotation_id'],image_id=r['image_id'],worker=r['worker_id'],
                                         condition=r['raw_condition'],same_side_pairs=int(same.sum()),status='alert_not_confirmed_error'))
    pd.DataFrame(flags).to_csv(out/'independent_pairing_flags.csv',index=False)
    timing = pd.read_csv(root/'previous_pairing_time/results/time_record_audit.csv')
    qualified, predictions = time_baselines(timing)
    frozen_time = pd.read_csv(root/'inputs/time_rows.csv').set_index('id')
    if set(qualified.id) != set(frozen_time.index): raise ValueError('time eligibility changed')
    matched_time = frozen_time.loc[qualified.id]
    assert np.allclose(qualified.speed_baseline,matched_time.speed_baseline,equal_nan=True)
    predictions.to_csv(out/'independent_same_image_time_predictions.csv',index=False)
    summary = dict(pairs=len(p),independent_max_abs_error=errors,graph_matching_checks=matches_checked,
                   finite_pool_rows_checked=len(prior),pairing_flags=len(flags),
                   pairing_flag_images=len({r['image_id'] for r in flags}),
                   union_counterexample_images=len(witnesses),
                   mean_expected_unseen_point_fraction=float(np.mean([r['expected_fraction_target_points_unseen'] for r in unions])),
                   source_verified_time_records=len(qualified),time_prediction_records=len(predictions))
    (out/'INDEPENDENT_CHECK.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
