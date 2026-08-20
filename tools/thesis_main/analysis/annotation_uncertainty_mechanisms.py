from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.annotation_uncertainty_common import *

def semi_mechanism_analysis(paired: pd.DataFrame, out: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    semi = read_csv(PACKAGE / 'curated' / 'semi_review_fact.csv')
    for col in ['geometry_edit_rmse_panorama_diagonal_normalized', 'geometry_edit_rmse_px', 'U_initial', 'U_final', 'delta_U']:
        semi[col] = pd.to_numeric(semi.get(col, np.nan), errors='coerce')
    for col in ['analysis_eligible', 'exact_geometry_equal', 'edited_binary', 'improved_binary', 'harmed_binary', 'initial_structurally_valid', 'final_structurally_valid']:
        if col in semi:
            semi[col] = semi[col].map(truth)
    eligible = semi[semi.get('analysis_eligible', False) & semi['delta_U'].notna()].copy()
    eligible['structural_zero_zero'] = (eligible['geometry_edit_rmse_panorama_diagonal_normalized'].fillna(0) == 0) & (eligible['delta_U'] == 0)
    eligible['meaningful_edit'] = eligible['geometry_edit_rmse_panorama_diagonal_normalized'].fillna(0) > 0
    assoc_rows = []
    populations = {'all_eligible': eligible, 'exclude_zero_zero': eligible[~eligible['structural_zero_zero']], 'edited_only': eligible[eligible['meaningful_edit']], 'c1_only': eligible[eligible['stage'] == 'C1']}
    for name, data in populations.items():
        worker_result = spearman_with_group_permutation(data, 'geometry_edit_rmse_panorama_diagonal_normalized', 'delta_U', 'worker_id', seed=SEED + 1)
        task_result = spearman_with_group_permutation(data, 'geometry_edit_rmse_panorama_diagonal_normalized', 'delta_U', 'base_task_id', seed=SEED + 2)
        p_candidates = [p for p in [worker_result['p'], task_result['p']] if p is not None]
        assoc_rows.append({'population': name, 'row_n': len(data), 'worker_groups': worker_result['groups'], 'task_groups': task_result['groups'], 'worker_axis_rho': worker_result['rho'], 'worker_axis_p': worker_result['p'], 'task_axis_rho': task_result['rho'], 'task_axis_p': task_result['p'], 'conservative_p': max(p_candidates) if p_candidates else np.nan})
    associations = pd.DataFrame(assoc_rows)
    associations['q_bh'] = bh_adjust(associations['conservative_p'].tolist())
    task_mechanism = eligible.groupby('base_task_id').agg(semi_review_n=('canonical_annotation_id', 'size'), initial_quality_mean=('U_initial', 'mean'), final_quality_mean=('U_final', 'mean'), delta_quality_mean=('delta_U', 'mean'), unchanged_rate=('exact_geometry_equal', 'mean'), meaningful_edit_rate=('meaningful_edit', 'mean'), structural_zero_zero_rate=('structural_zero_zero', 'mean'), harm_rate=('harmed_binary', 'mean'), improvement_rate=('improved_binary', 'mean'), edit_magnitude_mean=('geometry_edit_rmse_panorama_diagonal_normalized', 'mean')).reset_index()
    task_mechanism = paired.merge(task_mechanism, on='base_task_id', how='left')
    mechanism_associations = []
    for predictor in ['initial_quality_mean', 'unchanged_rate', 'meaningful_edit_rate', 'harm_rate', 'edit_magnitude_mean']:
        for outcome in ['delta_equal_k_entropy', 'delta_equal_k_gini', 'delta_quality_mean']:
            if predictor not in task_mechanism or outcome not in task_mechanism:
                continue
            data = task_mechanism[[predictor, outcome]].dropna()
            if len(data) >= 6 and data[predictor].nunique() > 1 and data[outcome].nunique() > 1:
                rho, p = stats.spearmanr(data[predictor], data[outcome])
                mechanism_associations.append({'predictor': predictor, 'outcome': outcome, 'n_tasks': len(data), 'rho': float(rho), 'p': float(p)})
    mechanism_assoc = pd.DataFrame(mechanism_associations)
    if not mechanism_assoc.empty:
        mechanism_assoc['q_bh'] = bh_adjust(mechanism_assoc['p'].tolist())
    write_csv(out / 'semi_edit_zero_sensitivity.csv', associations)
    write_csv(out / 'semi_task_mechanism_vs_uncertainty.csv', task_mechanism)
    write_csv(out / 'semi_mechanism_associations.csv', mechanism_assoc)
    return associations, task_mechanism

def event_sequence_analysis(unified: pd.DataFrame, task_metrics: pd.DataFrame, out: Path) -> pd.DataFrame:
    path = PACKAGE / 'curated' / 'raw_active_event_fact.csv'
    use = ['source_collection', 'event_stage', 'in_formal_stage_scope', 'project_id', 'task_id', 'annotator_id', 'annotation_id', 'session_id', 'timestamp', 'server_received_at', 'page_type', 'page_gate_eligible', 'page_gate_reason', 'store_mismatch_present', 'active_seconds_fragment']
    events = read_csv(path, usecols=lambda c: c in use)
    events = events[events['in_formal_stage_scope'].map(truth)].copy()
    events['project_id'] = events['project_id'].astype(str)
    events['task_id'] = events['task_id'].astype(str)
    events['worker_id'] = events['annotator_id'].map(norm_worker)
    mapping = unified[['stage', 'project_id', 'runtime_task_id', 'worker_id', 'base_task_id', 'condition_normalized']].drop_duplicates()
    mapping['project_id'] = mapping['project_id'].astype(str)
    mapping['runtime_task_id'] = mapping['runtime_task_id'].astype(str)
    joined = events.merge(mapping, left_on=['event_stage', 'project_id', 'task_id', 'worker_id'], right_on=['stage', 'project_id', 'runtime_task_id', 'worker_id'], how='left')
    joined['page_gate_fail'] = joined['page_gate_eligible'].notna() & ~joined['page_gate_eligible'].map(truth)
    joined['store_mismatch'] = joined['store_mismatch_present'].map(truth)
    joined['timestamp_parsed'] = pd.to_datetime(joined['timestamp'], errors='coerce', utc=True)
    joined['server_parsed'] = pd.to_datetime(joined['server_received_at'], errors='coerce', utc=True)
    joined['server_lag_seconds'] = (joined['server_parsed'] - joined['timestamp_parsed']).dt.total_seconds()
    context = joined.groupby(['event_stage', 'project_id', 'task_id', 'worker_id', 'base_task_id', 'condition_normalized'], dropna=False).agg(raw_event_count=('annotation_id', 'size'), session_count=('session_id', 'nunique'), page_type_count=('page_type', 'nunique'), page_gate_fail_rate=('page_gate_fail', 'mean'), store_mismatch_rate=('store_mismatch', 'mean'), server_lag_median=('server_lag_seconds', 'median')).reset_index()
    c1 = context[(context['event_stage'] == 'C1') & context['base_task_id'].notna()].copy()
    task_process = c1.groupby(['base_task_id', 'condition_normalized']).agg(event_context_n=('worker_id', 'size'), event_count_median=('raw_event_count', 'median'), session_count_mean=('session_count', 'mean'), page_gate_fail_rate=('page_gate_fail_rate', 'mean'), store_mismatch_rate=('store_mismatch_rate', 'mean'), server_lag_median=('server_lag_median', 'median')).reset_index().rename(columns={'condition_normalized': 'condition'})
    linked = task_metrics.merge(task_process, on=['base_task_id', 'condition'], how='left')
    rows = []
    for predictor in ['event_count_median', 'session_count_mean', 'page_gate_fail_rate', 'store_mismatch_rate', 'server_lag_median']:
        for outcome in ['cluster_entropy', 'pair_dissimilarity_mean', 'invalid_geometry_rate', 'quality_mean']:
            data = linked[[predictor, outcome, 'base_task_id']].dropna()
            if len(data) >= 8 and data[predictor].nunique() > 1 and data[outcome].nunique() > 1:
                rho, p = stats.spearmanr(data[predictor], data[outcome])
                rows.append({'predictor': predictor, 'outcome': outcome, 'n_task_conditions': len(data), 'rho': float(rho), 'p': float(p)})
    result = pd.DataFrame(rows)
    if not result.empty:
        result['q_bh'] = bh_adjust(result['p'].tolist())
    write_csv(out / 'event_context_features.csv', context)
    write_csv(out / 'event_task_uncertainty_links.csv', linked)
    write_csv(out / 'event_uncertainty_associations.csv', result)
    return result

def make_plots(paired: pd.DataFrame, out: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    plot_dir = out / 'plots'
    plot_dir.mkdir(parents=True, exist_ok=True)
    if {'manual_equal_k_entropy', 'semi_equal_k_entropy'}.issubset(paired.columns):
        data = paired[['manual_equal_k_entropy', 'semi_equal_k_entropy']].dropna()
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(data['manual_equal_k_entropy'], data['semi_equal_k_entropy'])
        limits = [min(data.min()), max(data.max())] if len(data) else [0, 1]
        ax.plot(limits, limits, linestyle='--')
        ax.set_xlabel('Manual equal-k cluster entropy')
        ax.set_ylabel('Semi equal-k cluster entropy')
        ax.set_title('Task-paired annotation uncertainty')
        fig.tight_layout(); fig.savefig(plot_dir / 'manual_vs_semi_entropy.png', dpi=180); plt.close(fig)
    columns = [c for c in ['delta_equal_k_entropy', 'delta_pair_dissimilarity_mean', 'delta_quality_mean', 'delta_active_time_median'] if c in paired]
    if columns:
        means, lows, highs = [], [], []
        for col in columns:
            values = paired[col].dropna().astype(float).tolist()
            lo, hi = bootstrap_interval(values)
            means.append(float(np.mean(values)) if values else np.nan); lows.append(lo); highs.append(hi)
        fig, ax = plt.subplots(figsize=(8, 4.5))
        y = np.arange(len(columns))
        xerr = np.array([[means[i] - lows[i] if lows[i] is not None else 0 for i in range(len(columns))], [highs[i] - means[i] if highs[i] is not None else 0 for i in range(len(columns))]])
        ax.errorbar(means, y, xerr=xerr, fmt='o')
        ax.axvline(0, linestyle='--')
        ax.set_yticks(y, columns)
        ax.set_xlabel('Semi − Manual paired mean (95% task bootstrap CI)')
        fig.tight_layout(); fig.savefig(plot_dir / 'paired_effects.png', dpi=180); plt.close(fig)

def fmt(value: Any, digits: int=4) -> str:
    number = num(value)
    return 'NA' if number is None else f'{number:.{digits}f}'

def generate_report(out: Path, inventory: pd.DataFrame, timing_summary: dict[str, Any], timing_coverage: pd.DataFrame, task_metrics: pd.DataFrame, paired: pd.DataFrame, inference: pd.DataFrame, stratified: pd.DataFrame, semi_assoc: pd.DataFrame, worker_modes: pd.DataFrame, event_assoc: pd.DataFrame, provenance: dict[str, Any]) -> None:
    def row(metric: str) -> pd.Series | None:
        subset = inference[inference['metric'] == metric]
        return subset.iloc[0] if len(subset) else None
    entropy, gini = row('delta_equal_k_entropy'), row('delta_equal_k_gini')
    quality, time = row('delta_quality_mean'), row('delta_active_time_median')
    overlap_n = int(paired['base_task_id'].nunique()) if len(paired) else 0
    structural_zero = semi_assoc.loc[semi_assoc['population'] == 'all_eligible', 'row_n']
    excluded_zero = semi_assoc.loc[semi_assoc['population'] == 'exclude_zero_zero', 'row_n']
    lines = ['# 标注不确定性与 Manual/Semi 关联：原始证据重建报告', '', '## 1. 证据边界', '', f'- Git HEAD：`{git_head()}`。', f'- 完整 raw 包文件数：{len(inventory)}；逐文件建立 inventory 和字段账本。', f"- C1 timing 从冻结日志重建：context={timing_summary.get('task_worker_active_time', {}).get('context_count', 'NA')}，eligible={timing_summary.get('task_worker_active_time', {}).get('eligible_context_count', 'NA')}。", f"- 当前与冻结 C1 日志共享文件 {provenance.get('shared_file_count', 'NA')}，字节 SHA 不同 {provenance.get('byte_sha_different_count', 'NA')}；规范化事件 multiset 相同：{provenance.get('normalized_event_multiset_equal', 'NA')}。", '- `new_server` 未作为独立阶段。lead_time 未作为 formal active-time fallback。', '', '## 2. 不确定性定义', '', '分别估计 topology/cluster entropy、corner-count entropy、pairwise geometry dispersion、结构无效率与最大模式占比；不同 topology 不做坐标平均。', '', '## 3. Manual 与 Semi 同图配对', '', f'同时具有 Manual/Semi 证据的 base task：{overlap_n}。equal-k replay 控制有效支持量。']
    for label, item in [('equal-k cluster entropy', entropy), ('equal-k Gini-Simpson disagreement', gini), ('task mean quality', quality), ('formal active-time median', time)]:
        if item is not None:
            lines.append(f"- {label}：Semi−Manual={fmt(item['mean_delta_semi_minus_manual'])}，95% CI [{fmt(item['ci_lower'])}, {fmt(item['ci_upper'])}]，p={fmt(item['p_sign_flip'])}，BH q={fmt(item['q_bh_within_family'])}。")
    lines += ['', '这些是任务级配对关联；若 assignment 随机化未被完整验证，不升级为因果效应。', '', '## 4. 高歧义/高难度', '', '高歧义由 Manual 证据定义；高难度分别使用 pre-task 字段、Manual formal time 与 Manual meta choices。结果见 `manual_semi_stratified_inference.csv`。', '', '## 5. Proposal 机制', '', f"Semi all-eligible 行数：{int(structural_zero.iloc[0]) if len(structural_zero) else 'NA'}；排除 `(edit=0, delta_U=0)` 后：{int(excluded_zero.iloc[0]) if len(excluded_zero) else 'NA'}。"]
    for _, item in semi_assoc.iterrows():
        lines.append(f"- {item['population']}：worker-axis ρ={fmt(item['worker_axis_rho'])}, p={fmt(item['worker_axis_p'])}; task-axis ρ={fmt(item['task_axis_rho'])}, p={fmt(item['task_axis_p'])}; 保守 p={fmt(item['conservative_p'])}。")
    lines += ['', '编辑幅度不被解释为纠错能力；另行分析是否编辑、收益/伤害与原样接受。', '', '## 6. 工人模式与过程日志', '', f"工人进入最大模式的 task-centered permutation p={fmt(worker_modes['task_centered_permutation_p'].iloc[0]) if len(worker_modes) else 'NA'}。", f'event-sequence 扫描项：{len(event_assoc)}；详见 CSV 与 FDR。', '', '## 7. 主要输出', '', '- `unified_submission_timing_fact.csv`：含 `ls_runtime_task_id` 和全阶段 formal timing。', '- `c1_task_condition_uncertainty.csv`：任务×模式不确定性。', '- `manual_semi_paired_task_metrics.csv`：同图比较。', '- `semi_edit_zero_sensitivity.csv`：结构零敏感性。', '- `event_context_features.csv`：过程特征。', '', '所有结论以 effect、CI、support 与 provenance 为准。']
    (out / 'REPORT_ZH.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
