"""Independent checks of two retrospective reports; never edit their inputs or assign people types."""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OTHER = ROOT / 'analysis_results/annotation_reanalysis_20260905'
V2 = ROOT / 'analysis_results/annotation_research_prework_20260905_v2'
OUT = ROOT / 'analysis_results/annotation_reanalysis_independent_audit_20260905_v1'


def fit_effects(data, field):
    """Eliminate task intercepts and solve worker contrasts with an explicit rank check."""
    d = data.dropna(subset=[field]).copy()
    workers = sorted(d.worker_id.unique())
    x = pd.get_dummies(pd.Categorical(d.worker_id, categories=workers), dtype=float).to_numpy(copy=True)
    y = d[field].to_numpy(float).copy()
    codes = pd.factorize(d.base_task_id)[0]
    for code in np.unique(codes):
        mask = codes == code
        x[mask] -= x[mask].mean(axis=0)
        y[mask] -= y[mask].mean()
    if len(workers) < 2 or np.linalg.matrix_rank(x) != len(workers) - 1:
        raise ValueError('Worker/task graph does not identify one global worker contrast.')
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return pd.Series(beta - beta.mean(), index=workers)


def lobo(data, field, test_data=None):
    """Known-worker, within-held-out-task contrasts; no test outcomes in fitting."""
    target = data if test_data is None else test_data
    parts = []
    for building in sorted(target.building_id.unique()):
        beta = fit_effects(data[data.building_id != building], field)
        test = target[target.building_id == building].dropna(subset=[field]).copy()
        test = test[test.worker_id.isin(beta.index)]
        test['prediction'] = test.worker_id.map(beta)
        test['prediction'] -= test.groupby('base_task_id').prediction.transform('mean')
        test['target'] = test[field] - test.groupby('base_task_id')[field].transform('mean')
        test['sse'] = (test.target - test.prediction) ** 2
        test['baseline_sse'] = test.target ** 2
        parts.append(test)
    joined = pd.concat(parts, ignore_index=True)
    baseline = joined.baseline_sse.sum()
    return {'rows': len(joined), 'images': joined.base_task_id.nunique(),
            'workers': joined.worker_id.nunique(), 'buildings': joined.building_id.nunique(),
            'sse': float(joined.sse.sum()), 'baseline_sse': float(baseline),
            'r2': float(1 - joined.sse.sum() / baseline) if baseline else None,
            'building_equal_r2': float(1 - joined.groupby('building_id').sse.mean().mean()
                                      / joined.groupby('building_id').baseline_sse.mean().mean()) if baseline else None,
            'heldout': joined}


def sign_diagnostic(label, local_prediction, local_outcome):
    legacy = (label.startswith('H_') and local_outcome < 0) or (label.startswith('L_') and local_outcome > 0)
    return {'legacy_label_disagrees_with_local_outcome': legacy,
            'same_center_prediction_sign_error': local_prediction * local_outcome < -1e-12,
            'same_center_prediction_agrees_despite_legacy_flag': legacy and local_prediction * local_outcome > 1e-12}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    keys = ['project_id', 'runtime_task_id', 'worker_id', 'annotation_id', 'base_task_id', 'dataset_group']
    raw = pd.read_csv(OTHER / 'inputs/legacy_rq1/formal_time_worker_task_rows.csv')
    repair = pd.read_csv(OTHER / 'inputs/legacy_rq1/c1_geometry_repair_audit.csv')
    d = raw.merge(repair[keys + ['raw_point_count', 'raw_valid', 'repair_applied']], on=keys, validate='one_to_one')
    n = d.strict_valid_support
    d['peer_distance_mean'] = (n*d.task_mask_dispersion - (n-2)*d.leave_one_worker_out_mask_dispersion)/2
    d['corner_pair_count'] = (d.raw_point_count - d.repair_applied.astype(int))/2
    d['log_active_time'] = np.log1p(d.active_time_seconds)
    assert ((d.corner_pair_count % 1) == 0).all()
    assert (d.groupby('base_task_id').size() == d.groupby('base_task_id').strict_valid_support.first()).all()
    saved = pd.read_csv(OTHER / 'c1_targeted_rows.csv')
    paired = d.merge(saved, on=keys, validate='one_to_one', suffixes=('_new', '_old'))
    for field in ['peer_distance_mean', 'corner_pair_count', 'log_active_time']:
        assert np.allclose(paired[field+'_new'], paired[field+'_old'], equal_nan=True, atol=1e-12)
    evidence = pd.read_csv(V2 / 'evidence/record_evidence.csv')
    evidence['annotation_id'] = evidence.raw_annotation_id
    bridge = d.merge(evidence[['project_id', 'runtime_task_id', 'worker_id', 'annotation_id',
                               'active_time_owner_valid_status', 'active_time_seconds']],
                     on=keys[:4], how='left', validate='one_to_one', suffixes=('', '_v2'))
    assert len(bridge) == len(d)
    bridge['active_time_owner_valid_status'] = bridge.active_time_owner_valid_status.fillna('no_exact_canonical_version_match')
    bridge.to_csv(OUT / 'c1_time_source_bridge.csv', index=False, encoding='utf-8-sig')
    metrics = ['peer_distance_mean', 'corner_pair_count', 'log_active_time']
    variants = {'all_calculation_valid': d,
                'strict_clean_tasks': d[~d.base_task_id.isin(d.loc[d.repair_applied, 'base_task_id'])]}
    checks, heldout = [], []
    for variant, data in variants.items():
        for field in metrics:
            result = lobo(data, field)
            detail = result.pop('heldout'); detail['variant'] = variant; detail['metric'] = field
            heldout.append(detail)
            checks.append({'variant': variant, 'metric': field, **result})
    time_sets = {
        'time_eligible_only': bridge[bridge.active_time_status == 'eligible'],
        'time_without_fastest_worker_W6': bridge[bridge.worker_id != 6],
        'time_10_to_1800_seconds': bridge[bridge.active_time_seconds.between(10, 1800)],
        'latest_owner_valid_complete': bridge[bridge.active_time_owner_valid_status.str.startswith('owner_valid_complete')],
    }
    for variant, data in time_sets.items():
        result = lobo(data, 'log_active_time'); result.pop('heldout')
        checks.append({'variant': variant, 'metric': 'log_active_time', **result})
    expected = pd.read_csv(OTHER / 'profile_lobo_cv.csv')
    for row in checks[:6]:
        old = expected[(expected.variant == row['variant']) & (expected.metric == row['metric'])].iloc[0]
        assert abs(row['r2'] - old.lobo_within_task_r2) < 1e-10
    expected_time = pd.read_csv(OTHER / 'time_sensitivity.csv')
    for row in checks[6:9]:
        old = expected_time[expected_time.sensitivity == row['variant']].iloc[0]
        assert abs(row['r2'] - old.lobo_within_task_r2) < 1e-10
    pd.DataFrame(checks).to_csv(OUT / 'independent_profile_validation.csv', index=False, encoding='utf-8-sig')
    pd.concat(heldout).to_csv(OUT / 'independent_heldout_predictions.csv', index=False, encoding='utf-8-sig')
    split = []
    for variant, data in variants.items():
        rng = np.random.default_rng(20260905); buildings = sorted(data.building_id.unique())
        for replicate in range(300):
            left = set(rng.permutation(buildings)[:len(buildings)//2])
            for field in metrics:
                a = fit_effects(data[data.building_id.isin(left)], field)
                b = fit_effects(data[~data.building_id.isin(left)], field)
                ids = a.index.intersection(b.index)
                split.append({'variant': variant, 'replicate': replicate, 'metric': field,
                              'n_workers': len(ids), 'rho': float(a[ids].rank().corr(b[ids].rank()))})
    sp = pd.DataFrame(split)
    summary = sp.groupby(['variant', 'metric']).rho.agg(median='median', q25=lambda x: x.quantile(.25), q75=lambda x: x.quantile(.75)).reset_index()
    expected_split = pd.read_csv(OTHER / 'profile_stability_summary.csv')
    split_differences = []
    for r in summary.to_dict('records'):
        old = expected_split[(expected_split.variant == r['variant']) & (expected_split.metric == r['metric'])].iloc[0]
        split_differences.append({'variant': r['variant'], 'metric': r['metric'], 'new_median': r['median'],
                                  'old_median': float(old.median_rho), 'absolute_difference': abs(r['median'] - old.median_rho)})
    summary.to_csv(OUT / 'independent_split_summary.csv', index=False, encoding='utf-8-sig')
    # Counterpart transport is kept descriptive: known workers, held-out buildings, final corner count.
    semi = repair[repair.condition == 'semi'].copy()
    semi['corner_pair_count'] = (semi.raw_point_count - semi.repair_applied.astype(int))/2
    semi['building_id'] = semi.base_task_id.str.split('_').str[0]
    manual_seen = set(map(tuple, repair.loc[repair.condition == 'manual', ['base_task_id', 'worker_id']].to_numpy()))
    cross = semi[['base_task_id', 'worker_id']].apply(tuple, axis=1).isin(manual_seen)
    transports = []
    for variant, data in [('calculation_valid_104', semi[semi.calculation_valid]),
                          ('raw_valid_103', semi[semi.raw_valid]),
                          ('no_same_image_cross_condition_record', semi[semi.calculation_valid & ~cross])]:
        result = lobo(d, 'corner_pair_count', data); detail = result.pop('heldout')
        detail.groupby('building_id').agg(rows=('worker_id', 'size'), sse=('sse', 'sum'), baseline_sse=('baseline_sse', 'sum')).to_csv(OUT / f'transport_building_{variant}.csv', encoding='utf-8-sig')
        transports.append({'variant': variant, **result})
    expected_transport = pd.read_csv(OTHER / 'manual_to_semi_corner_transport.csv')
    for r in transports:
        old = expected_transport[expected_transport.variant == r['variant']].iloc[0]
        assert abs(r['r2'] - old.transport_within_task_R2) < 1e-10
    pd.DataFrame(transports).to_csv(OUT / 'independent_transport_validation.csv', index=False, encoding='utf-8-sig')
    geometry = pd.read_csv(ROOT / 'analysis_results/uncertainty_substrate_20260823_v1/geometry_variants.csv')
    current = geometry[(geometry.stage == 'C1') & (geometry.variant == 'strict_normalized') & geometry.strict_valid].copy()
    current['corner_pair_count'] = current.point_count / 2
    current['building_id'] = current.base_task_id.str.split('_').str[0]
    manual_current = current[current.raw_condition == 'manual']
    canonical_checks = []
    for variant, target in [('latest_canonical_manual', manual_current),
                            ('latest_canonical_manual_to_semi', current[current.raw_condition == 'semi'])]:
        result = lobo(manual_current, 'corner_pair_count', target); result.pop('heldout')
        canonical_checks.append({'variant': variant, **result})
    pd.DataFrame(canonical_checks).to_csv(OUT / 'canonical_corner_sensitivity.csv', index=False, encoding='utf-8-sig')
    hold = pd.read_csv(V2 / 'statistics/holdout_evaluation.csv')
    hold = hold[(hold.status == 'evaluated') & (hold.threshold == .8)].copy()
    diagnostics = pd.DataFrame([sign_diagnostic(r.directional_class, r.train_prediction_same_heldout_peer_center, r.heldout_task_centered_mean) for r in hold.itertuples()], index=hold.index)
    hold = pd.concat([hold, diagnostics], axis=1)
    assert (hold.legacy_label_disagrees_with_local_outcome == hold.classification_counterexample).all()
    flags = hold[hold.same_center_prediction_agrees_despite_legacy_flag]
    flags.to_csv(OUT / 'v2_changed_peer_center_flags.csv', index=False, encoding='utf-8-sig')
    hold.groupby(['stage', 'condition', 'feature_name', 'evaluation_kind']).agg(rows=('worker_id', 'size'), legacy_flags=('classification_counterexample', 'sum'), peer_center_confounding_flags=('same_center_prediction_agrees_despite_legacy_flag', 'sum')).to_csv(OUT / 'v2_counterexample_interpretation_summary.csv', encoding='utf-8-sig')
    time_diff = bridge.dropna(subset=['active_time_seconds', 'active_time_seconds_v2'])
    qa = {'schema_version': 'independent_reanalysis_claim_audit_v1', 'status': 'pass_with_interpretation_findings',
          'source_scope': 'bundled C1 rows and v2 evidence; not a rerun of all raw geometry',
          'c1_rows': len(d), 'c1_images': d.base_task_id.nunique(), 'c1_workers': d.worker_id.nunique(),
          'c1_time_source_counts': bridge.active_time_owner_valid_status.value_counts().to_dict(),
          'unmatched_canonical_versions': bridge.loc[bridge.active_time_owner_valid_status == 'no_exact_canonical_version_match', keys].to_dict('records'),
          'time_value_mismatch_count': int((abs(time_diff.active_time_seconds-time_diff.active_time_seconds_v2) > 1e-10).sum()),
          'six_original_lobo_values_reproduced': True, 'three_original_time_sensitivities_reproduced': True,
          'building_split_fits_recomputed': len(split)*2, 'split_median_comparisons': split_differences,
          'three_cross_condition_values_reproduced': True,
          'v2_evaluable_rows_at_threshold_080': len(hold), 'v2_legacy_counterexample_flags': int(hold.classification_counterexample.sum()),
          'v2_legacy_flags_with_same_center_prediction_agreement': len(flags),
          'new_time_complete_only_result': checks[-1], 'clustering_scope': 'source reviewed; stored split summaries checked separately; Ward/GMM not rerun',
          'canonical_corner_sensitivity': canonical_checks,
          'human_decisions_written': 0, 'old_packages_modified': False}
    # Check the supplied clustering summaries without claiming to rerun their algorithms.
    cluster_checks = []
    for name, source, group_keys in [
        ('cluster', 'cluster_split_stability.csv', ['variant', 'features', 'k']),
        ('grouping_method', 'grouping_method_split_results.csv', ['method', 'features', 'k']),
    ]:
        split_rows = pd.read_csv(OTHER / source)
        expected = pd.read_csv(OTHER / (name + '_stability_summary.csv' if name == 'cluster' else name + '_summary.csv'))
        actual = split_rows.groupby(group_keys).ari.agg(median_ari='median', q25=lambda x: x.quantile(.25), q75=lambda x: x.quantile(.75)).reset_index()
        joined = actual.merge(expected, on=group_keys, validate='one_to_one', suffixes=('_new', '_old'))
        assert len(joined) == len(actual) == len(expected)
        delta = max(abs(joined[f + '_new'] - joined[f + '_old']).max() for f in ['median_ari', 'q25', 'q75'])
        assert delta < 1e-10
        cluster_checks.append({'summary': name, 'split_rows': len(split_rows), 'groups': len(joined), 'max_difference': float(delta)})
    matched = pd.read_csv(V2 / 'evidence/matched25_image_summary.csv')
    assert len(matched) == matched.base_task_id.nunique() == 25
    qa['stored_clustering_summary_checks'] = cluster_checks
    qa['matched25_summary_checks'] = {
        'images': len(matched), 'buildings': matched.building_id.nunique(),
        'manual_rows': int(matched.manual_record_count.sum()), 'semi_rows': int(matched.semi_record_count.sum()),
        'initial_reference_d_mask_zero_images': int((matched.initial_reference_d_mask == 0).sum()),
        'exact_retention_rows': int(matched.exact_retention_count.sum()),
        'scope': 'independent aggregation of v2 evidence; source generator also inspected; no new rasterization',
    }
    (OUT / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2, default=int)+'\n', encoding='utf-8')
    print(json.dumps(qa, ensure_ascii=True, default=int))


if __name__ == '__main__':
    main()
