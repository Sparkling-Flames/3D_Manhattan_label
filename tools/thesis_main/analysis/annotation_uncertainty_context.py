from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.annotation_uncertainty_common import *

def parse_task_data_features(out: Path) -> pd.DataFrame:
    path = PACKAGE / 'curated' / 'raw_annotation_fact.csv'
    usecols = ['stage', 'base_task_id', 'condition', 'task_data_json']
    frame = read_csv(path, usecols=lambda c: c in usecols).drop_duplicates()
    long_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for (stage, task, condition), group in frame.groupby(['stage', 'base_task_id', 'condition'], dropna=False):
        flattened: dict[str, list[Any]] = defaultdict(list)
        for text in group['task_data_json'].dropna().astype(str):
            try:
                value = json.loads(text)
            except Exception:
                continue
            for key, item in flatten_json(value):
                flattened[key].append(item)
        pre_risk = None
        pre_stratum = ''
        pre_difficulty = ''
        for key, values in flattened.items():
            low = key.lower()
            unique = list(dict.fromkeys(str(v) for v in values if v not in (None, '')))
            for value in unique:
                long_rows.append({'stage': stage, 'base_task_id': task, 'condition': clean_condition(condition), 'field_path': key, 'value': value})
            if pre_risk is None and 'risk' in low and not any(token in low for token in ('outcome', 'quality', 'worker')):
                candidates = [num(v) for v in values]
                candidates = [v for v in candidates if v is not None]
                if candidates:
                    pre_risk = float(candidates[0])
            if not pre_stratum and 'stratum' in low and unique:
                pre_stratum = unique[0]
            if not pre_difficulty and 'difficulty' in low and unique:
                pre_difficulty = unique[0]
        summary_rows.append({'stage': stage, 'base_task_id': task, 'condition': clean_condition(condition), 'preassignment_risk_from_task_data': pre_risk, 'preassignment_stratum_from_task_data': pre_stratum, 'preassignment_difficulty_from_task_data': pre_difficulty, 'task_data_field_count': len(flattened)})
    long = pd.DataFrame(long_rows)
    summary = pd.DataFrame(summary_rows)
    write_csv(out / 'task_data_fields_long.csv', long)
    write_csv(out / 'task_pretask_feature_summary.csv', summary)
    return summary

def parse_raw_choices() -> pd.DataFrame:
    path = PACKAGE / 'curated' / 'raw_annotation_fact.csv'
    usecols = ['stage', 'project_id', 'ls_runtime_task_id', 'base_task_id', 'condition', 'annotation_id', 'worker_id', 'canonical_join_status', 'task_data_json', 'result_json']
    frame = read_csv(path, usecols=lambda c: c in usecols)
    rows: list[dict[str, Any]] = []
    for _, item in frame.iterrows():
        try:
            results = json.loads(str(item.get('result_json') or '[]'))
        except Exception:
            continue
        for result in results if isinstance(results, list) else []:
            value = result.get('value') or {}
            choices = value.get('choices') or []
            if isinstance(choices, str):
                choices = [choices]
            for choice in choices:
                rows.append({'stage': item.get('stage', ''), 'base_task_id': item.get('base_task_id', ''), 'condition': clean_condition(item.get('condition', '')), 'worker_id': norm_worker(item.get('worker_id', '')), 'annotation_id': item.get('annotation_id', ''), 'canonical_join_status': item.get('canonical_join_status', ''), 'from_name': str(result.get('from_name') or ''), 'choice': str(choice)})
    return pd.DataFrame(rows)

def meta_difficulty_summary(choices: pd.DataFrame, paired: pd.DataFrame, pretask: pd.DataFrame, out: Path) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
    c1 = choices[(choices['stage'] == 'C1') & (choices['condition'] == 'manual')].copy()
    c1['token'] = (c1['from_name'] + ' ' + c1['choice']).str.lower()
    difficult_terms = 'difficult|hard|occlusion|occluded|遮挡|困难|难|low.?texture|reflection|reflective|seam|topology|open|ambiguous'
    c1['difficulty_related'] = c1['token'].str.contains(difficult_terms, regex=True)
    summary = c1.groupby('base_task_id').agg(manual_meta_choice_count=('choice', 'size'), manual_difficulty_related_choice_count=('difficulty_related', 'sum'), manual_difficulty_related_rate=('difficulty_related', 'mean'), manual_unique_meta_choices=('choice', 'nunique')).reset_index()
    result = paired.merge(summary, on='base_task_id', how='left')
    if not pretask.empty:
        pre = pretask[pretask['stage'] == 'C1'].copy().sort_values('condition').drop_duplicates('base_task_id')
        result = result.merge(pre[['base_task_id', 'preassignment_risk_from_task_data', 'preassignment_stratum_from_task_data', 'preassignment_difficulty_from_task_data']], on='base_task_id', how='left')
    if 'manual_active_time_median' in result:
        result['high_manual_time'] = result['manual_active_time_median'] >= result['manual_active_time_median'].median(skipna=True)
    result['high_manual_ambiguity'] = result['manual_equal_k_entropy'] >= result['manual_equal_k_entropy'].median(skipna=True)
    if 'preassignment_risk_from_task_data' in result and result['preassignment_risk_from_task_data'].notna().sum() >= 6:
        result['high_pretask_risk'] = result['preassignment_risk_from_task_data'] >= result['preassignment_risk_from_task_data'].median(skipna=True)
    if 'manual_difficulty_related_rate' in result:
        result['high_manual_meta_difficulty'] = result['manual_difficulty_related_rate'] >= result['manual_difficulty_related_rate'].median(skipna=True)
    write_csv(out / 'manual_task_difficulty_and_ambiguity_strata.csv', result)
    return result

def stratified_mode_inference(frame: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows = []
    outcomes = ['delta_equal_k_entropy', 'delta_equal_k_gini', 'delta_pair_dissimilarity_mean', 'delta_quality_mean', 'delta_active_time_median']
    strata = [c for c in ['high_manual_ambiguity', 'high_manual_time', 'high_manual_meta_difficulty', 'high_pretask_risk'] if c in frame]
    for stratum in strata:
        for outcome in outcomes:
            if outcome not in frame:
                continue
            for value in (False, True):
                data = frame[frame[stratum].fillna(False) == value][outcome].dropna().astype(float).tolist()
                lo, hi = bootstrap_interval(data, seed=SEED + int(value))
                rows.append({'analysis_family': 'mode_effect_by_manual_defined_stratum', 'stratum': stratum, 'stratum_value': value, 'outcome': outcome, 'n_tasks': len(data), 'mean_delta': float(np.mean(data)) if data else np.nan, 'ci_lower': lo, 'ci_upper': hi, 'p_sign_flip': paired_sign_flip(data, seed=SEED + int(value))})
            low = frame[~frame[stratum].fillna(False)][outcome].dropna().astype(float).to_numpy()
            high = frame[frame[stratum].fillna(False)][outcome].dropna().astype(float).to_numpy()
            if len(low) >= 3 and len(high) >= 3:
                observed = float(high.mean() - low.mean())
                combined = np.concatenate([high, low])
                rng = np.random.default_rng(SEED + len(combined))
                extreme = 0
                for _ in range(19999):
                    rng.shuffle(combined)
                    value = float(combined[:len(high)].mean() - combined[len(high):].mean())
                    extreme += abs(value) >= abs(observed) - 1e-15
                rows.append({'analysis_family': 'mode_by_stratum_interaction', 'stratum': stratum, 'stratum_value': 'high_minus_low', 'outcome': outcome, 'n_tasks': len(low) + len(high), 'mean_delta': observed, 'ci_lower': np.nan, 'ci_upper': np.nan, 'p_sign_flip': (extreme + 1) / 20000})
    result = pd.DataFrame(rows)
    if not result.empty:
        result['q_bh_within_family'] = result.groupby('analysis_family')['p_sign_flip'].transform(lambda values: pd.Series(bh_adjust(values.tolist()), index=values.index))
    write_csv(out / 'manual_semi_stratified_inference.csv', result)
    return result
