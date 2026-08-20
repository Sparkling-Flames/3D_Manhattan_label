from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.annotation_uncertainty_common import *

def paired_mode_analysis(task_metrics: pd.DataFrame, replay: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    manual = task_metrics[task_metrics['condition'] == 'manual'].copy()
    semi = task_metrics[task_metrics['condition'] == 'semi'].copy()
    overlap = sorted(set(manual['base_task_id']) & set(semi['base_task_id']))
    metrics = ['cluster_entropy', 'cluster_entropy_mm', 'cluster_gini', 'effective_cluster_count', 'largest_cluster_share', 'corner_entropy', 'corner_gini', 'pair_dissimilarity_mean', 'compatible_edge_rate_095', 'invalid_geometry_rate', 'quality_mean', 'quality_sd', 'active_time_median']
    paired = manual[manual['base_task_id'].isin(overlap)][['base_task_id', 'building_id', 'task_crowd_structure_status', *[m for m in metrics if m in manual]]].rename(columns={m: f'manual_{m}' for m in metrics if m in manual})
    semi_keep = semi[semi['base_task_id'].isin(overlap)][['base_task_id', 'task_crowd_structure_status', *[m for m in metrics if m in semi]]].rename(columns={'task_crowd_structure_status': 'semi_task_crowd_structure_status', **{m: f'semi_{m}' for m in metrics if m in semi}})
    paired = paired.merge(semi_keep, on='base_task_id', how='inner', validate='one_to_one')
    for metric in metrics:
        if f'manual_{metric}' in paired and f'semi_{metric}' in paired:
            paired[f'delta_{metric}'] = paired[f'semi_{metric}'] - paired[f'manual_{metric}']
    replay_task = replay.groupby('base_task_id', as_index=False).agg(common_k=('common_k', 'first'), manual_equal_k_entropy=('manual_entropy', 'mean'), semi_equal_k_entropy=('semi_entropy', 'mean'), manual_equal_k_gini=('manual_gini', 'mean'), semi_equal_k_gini=('semi_gini', 'mean'), manual_equal_k_largest_share=('manual_largest_share', 'mean'), semi_equal_k_largest_share=('semi_largest_share', 'mean'), manual_equal_k_multimodal_rate=('manual_status', lambda x: float((x == 'supported_multimodal').mean())), semi_equal_k_multimodal_rate=('semi_status', lambda x: float((x == 'supported_multimodal').mean())), manual_equal_k_not_evaluable_rate=('manual_status', lambda x: float((x == 'not_evaluable').mean())), semi_equal_k_not_evaluable_rate=('semi_status', lambda x: float((x == 'not_evaluable').mean())))
    replay_task['delta_equal_k_entropy'] = replay_task['semi_equal_k_entropy'] - replay_task['manual_equal_k_entropy']
    replay_task['delta_equal_k_gini'] = replay_task['semi_equal_k_gini'] - replay_task['manual_equal_k_gini']
    replay_task['delta_equal_k_largest_share'] = replay_task['semi_equal_k_largest_share'] - replay_task['manual_equal_k_largest_share']
    replay_task['delta_equal_k_multimodal_rate'] = replay_task['semi_equal_k_multimodal_rate'] - replay_task['manual_equal_k_multimodal_rate']
    paired = paired.merge(replay_task, on='base_task_id', how='left', validate='one_to_one')
    result_rows = []
    inference_metrics = [c for c in paired.columns if c.startswith('delta_') and pd.api.types.is_numeric_dtype(paired[c])]
    for metric in inference_metrics:
        values = paired[metric].dropna().astype(float).tolist()
        lo, hi = bootstrap_interval(values)
        result_rows.append({'analysis_family': 'manual_vs_semi_task_paired', 'metric': metric, 'n_tasks': len(values), 'mean_delta_semi_minus_manual': float(np.mean(values)) if values else np.nan, 'median_delta': float(np.median(values)) if values else np.nan, 'ci_lower': lo, 'ci_upper': hi, 'p_sign_flip': paired_sign_flip(values)})
    inference = pd.DataFrame(result_rows)
    inference['q_bh_within_family'] = bh_adjust(inference['p_sign_flip'].tolist())
    write_csv(out / 'manual_semi_paired_task_metrics.csv', paired)
    write_csv(out / 'manual_semi_paired_inference.csv', inference)
    write_csv(out / 'manual_semi_equal_k_replay_task_summary.csv', replay_task)
    return paired, inference

def manual_semi_design_audit(structural: pd.DataFrame, sidecar: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    eligible_col = 'peer_analysis_eligible' if 'peer_analysis_eligible' in structural.columns else 'geometry_calculation_eligible'
    eligible = structural[structural[eligible_col].map(truth)].copy()
    eligible['worker_id'] = eligible['worker_id'].map(norm_worker)
    per_task = []
    for task in sorted(set(eligible.loc[eligible['condition'] == 'manual', 'base_task_id']) & set(eligible.loc[eligible['condition'] == 'semi', 'base_task_id'])):
        manual_workers = set(eligible.loc[(eligible['base_task_id'] == task) & (eligible['condition'] == 'manual'), 'worker_id'])
        semi_workers = set(eligible.loc[(eligible['base_task_id'] == task) & (eligible['condition'] == 'semi'), 'worker_id'])
        manual_row = sidecar[(sidecar['base_task_id'] == task) & (sidecar['condition'] == 'manual')]
        semi_row = sidecar[(sidecar['base_task_id'] == task) & (sidecar['condition'] == 'semi')]
        per_task.append({'base_task_id': task, 'manual_worker_count': len(manual_workers), 'semi_worker_count': len(semi_workers), 'same_worker_cross_mode_count': len(manual_workers & semi_workers), 'same_worker_cross_mode_ids': ';'.join(sorted(manual_workers & semi_workers)), 'manual_valid_k': num(manual_row.iloc[0]['valid_k']) if len(manual_row) else None, 'semi_valid_k': num(semi_row.iloc[0]['valid_k']) if len(semi_row) else None})
    frame = pd.DataFrame(per_task)
    summary = {'overlap_task_count': len(frame), 'tasks_with_same_worker_cross_mode': int((frame['same_worker_cross_mode_count'] > 0).sum()) if len(frame) else 0, 'same_worker_cross_mode_total': int(frame['same_worker_cross_mode_count'].sum()) if len(frame) else 0, 'manual_valid_k_median': float(frame['manual_valid_k'].median()) if len(frame) else None, 'semi_valid_k_median': float(frame['semi_valid_k'].median()) if len(frame) else None, 'causal_interpretation_status': 'requires_assignment_randomization_manifest_review'}
    write_csv(out / 'manual_semi_design_audit_by_task.csv', frame)
    write_json(out / 'manual_semi_design_audit_summary.json', summary)
    return frame, summary

def fixed_effect_mode_models(c1_timing: pd.DataFrame, quality: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    try:
        import statsmodels.formula.api as smf
    except Exception as exc:
        write_json(out / 'manual_semi_fixed_effect_model_status.json', {'status': 'not_evaluable', 'reason': repr(exc)})
        return pd.DataFrame()
    timing = c1_timing.copy()
    timing['condition'] = timing['condition'].map(clean_condition)
    timing['time'] = pd.to_numeric(timing['task_worker_active_seconds'], errors='coerce')
    timing['worker_id'] = timing['worker_id'].map(norm_worker)
    timing = timing[timing['task_worker_time_analysis_eligible'].map(truth) & timing['time'].notna() & timing['condition'].isin(['manual', 'semi'])].copy()
    timing['log_time'] = np.log1p(timing['time'])
    formula = "log_time ~ C(condition, Treatment(reference='manual')) + C(base_task_id) + C(worker_id)"
    try:
        model = smf.ols(formula, data=timing).fit(cov_type='cluster', cov_kwds={'groups': timing['base_task_id']})
        term = next(key for key in model.params.index if 'condition' in key and 'semi' in key)
        ci = model.conf_int().loc[term]
        rows.append({'outcome': 'log1p_formal_active_time', 'n_rows': int(model.nobs), 'n_tasks': timing['base_task_id'].nunique(), 'n_workers': timing['worker_id'].nunique(), 'semi_coefficient': float(model.params[term]), 'cluster_se': float(model.bse[term]), 'ci_lower': float(ci.iloc[0]), 'ci_upper': float(ci.iloc[1]), 'p': float(model.pvalues[term]), 'model': formula})
    except Exception as exc:
        rows.append({'outcome': 'log1p_formal_active_time', 'n_rows': len(timing), 'error': repr(exc), 'model': formula})
    q = quality.copy()
    q['worker_id'] = q['worker_id'].map(norm_worker)
    q = q[q['quality_primary_eligible'] & q['quality'].notna() & q['condition'].isin(['manual', 'semi'])].copy()
    formula = "quality ~ C(condition, Treatment(reference='manual')) + C(base_task_id) + C(worker_id)"
    try:
        model = smf.ols(formula, data=q).fit(cov_type='cluster', cov_kwds={'groups': q['base_task_id']})
        term = next(key for key in model.params.index if 'condition' in key and 'semi' in key)
        ci = model.conf_int().loc[term]
        rows.append({'outcome': 'GT_quality', 'n_rows': int(model.nobs), 'n_tasks': q['base_task_id'].nunique(), 'n_workers': q['worker_id'].nunique(), 'semi_coefficient': float(model.params[term]), 'cluster_se': float(model.bse[term]), 'ci_lower': float(ci.iloc[0]), 'ci_upper': float(ci.iloc[1]), 'p': float(model.pvalues[term]), 'model': formula})
    except Exception as exc:
        rows.append({'outcome': 'GT_quality', 'n_rows': len(q), 'error': repr(exc), 'model': formula})
    result = pd.DataFrame(rows)
    if 'p' in result:
        result['q_bh'] = bh_adjust(result['p'].tolist())
    write_csv(out / 'manual_semi_fixed_effect_models.csv', result)
    return result

def status_transition_table(paired: pd.DataFrame, out: Path) -> pd.DataFrame:
    full = pd.crosstab(paired['manual_task_crowd_structure_status'], paired['semi_task_crowd_structure_status'], dropna=False).stack().reset_index(name='task_count')
    write_csv(out / 'manual_semi_status_transition.csv', full)
    return full

def uncertainty_quality_tradeoff(paired: pd.DataFrame, out: Path, tolerance: float=0.005) -> pd.DataFrame:
    data = paired[['base_task_id', 'delta_equal_k_entropy', 'delta_quality_mean']].dropna().copy()
    data['uncertainty_change'] = np.where(data['delta_equal_k_entropy'] < 0, 'compressed', np.where(data['delta_equal_k_entropy'] > 0, 'expanded', 'unchanged'))
    data['quality_change'] = np.where(data['delta_quality_mean'] > tolerance, 'improved', np.where(data['delta_quality_mean'] < -tolerance, 'harmed', 'within_tolerance'))
    data['tradeoff_class'] = data['uncertainty_change'] + '+' + data['quality_change']
    write_csv(out / 'uncertainty_quality_tradeoff_by_task.csv', data)
    summary = data.groupby('tradeoff_class').size().reset_index(name='task_count')
    write_csv(out / 'uncertainty_quality_tradeoff_summary.csv', summary)
    return summary

def worker_mode_preference(sidecar: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows = []
    for _, task in sidecar[sidecar['condition'] == 'manual'].iterrows():
        try:
            clusters = json.loads(str(task.get('cluster_membership_json') or '[]'))
        except Exception:
            continue
        if not clusters:
            continue
        largest = set(clusters[0])
        for annotation in [item for cluster in clusters for item in cluster]:
            rows.append({'base_task_id': task['base_task_id'], 'canonical_annotation_id': str(annotation), 'in_largest_mode': int(annotation in largest), 'task_status': task['task_crowd_structure_status']})
    assignments = pd.DataFrame(rows)
    if assignments.empty:
        return assignments
    canonical = read_csv(C1_ROOT / 'c1_canonical_annotations.csv', usecols=lambda c: c in {'canonical_annotation_id', 'worker_id'})
    canonical['canonical_annotation_id'] = canonical['canonical_annotation_id'].astype(str)
    canonical['worker_id'] = canonical['worker_id'].map(norm_worker)
    assignments = assignments.merge(canonical.drop_duplicates('canonical_annotation_id'), on='canonical_annotation_id', how='left')
    observed = assignments.groupby('worker_id')['in_largest_mode'].agg(['mean', 'count']).reset_index()
    variance_observed = float(observed.loc[observed['count'] >= 3, 'mean'].var(ddof=1))
    rng = np.random.default_rng(SEED)
    permuted = []
    for _ in range(9999):
        shuffled = assignments.copy()
        shuffled['in_largest_mode'] = shuffled.groupby('base_task_id')['in_largest_mode'].transform(lambda values: rng.permutation(values.to_numpy()))
        values = shuffled.groupby('worker_id')['in_largest_mode'].agg(['mean', 'count'])
        permuted.append(float(values.loc[values['count'] >= 3, 'mean'].var(ddof=1)))
    observed['between_worker_variance'] = variance_observed
    observed['task_centered_permutation_p'] = (sum(value >= variance_observed - 1e-15 for value in permuted) + 1) / 10000
    write_csv(out / 'worker_mode_preference.csv', observed)
    return observed
