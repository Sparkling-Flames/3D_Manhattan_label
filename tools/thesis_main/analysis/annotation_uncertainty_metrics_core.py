from __future__ import annotations

import json, math
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.annotation_uncertainty_common import *
try:
    from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
except Exception:
    cluster_geometry_records = None

def parse_cluster_sizes(value: Any) -> list[int]:
    try:
        clusters = json.loads(str(value or '[]'))
        return [len(cluster) for cluster in clusters if isinstance(cluster, list) and cluster]
    except Exception:
        return []

def detect_pairwise_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns = {str(c).lower(): str(c) for c in frame.columns}
    def pick(candidates: Sequence[str]) -> str:
        for candidate in candidates:
            if candidate in columns:
                return columns[candidate]
        return ''
    return {'task': pick(['base_task_id', 'task_id']), 'condition': pick(['condition', 'pool']), 'left_annotation': pick(['canonical_annotation_id_left', 'annotation_id_left', 'left_annotation_id']), 'right_annotation': pick(['canonical_annotation_id_right', 'annotation_id_right', 'right_annotation_id']), 'left_worker': pick(['worker_id_left', 'left_worker_id']), 'right_worker': pick(['worker_id_right', 'right_worker_id']), 'q_boundary': pick(['q_boundary', 'boundary_similarity']), 'q_wall': pick(['q_wallwall', 'wallwall_similarity', 'q_wall_wall']), 'compatible': pick(['metric_compatible']), 'correspondence': pick(['pointwise_correspondence_compatible'])}

def load_c1_uncertainty_inputs(c1_timing: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sidecar = read_csv(C1_ROOT / 'geometry_task_crowd_structure_C1.csv')
    sidecar['condition'] = sidecar['condition'].map(clean_condition)
    sidecar['cluster_sizes'] = sidecar['cluster_membership_json'].map(parse_cluster_sizes)
    sidecar['cluster_entropy'] = sidecar['cluster_sizes'].map(entropy_from_counts)
    sidecar['cluster_entropy_mm'] = sidecar['cluster_sizes'].map(miller_madow_entropy)
    sidecar['cluster_gini'] = sidecar['cluster_sizes'].map(gini_simpson)
    sidecar['effective_cluster_count'] = np.exp(sidecar['cluster_entropy'])
    sidecar['supported_multimodal_binary'] = (sidecar['task_crowd_structure_status'] == 'supported_multimodal').astype(int)
    sidecar['not_evaluable_binary'] = (sidecar['task_crowd_structure_status'] == 'not_evaluable').astype(int)
    structural = read_csv(C1_ROOT / 'structural_validation_analysis.csv')
    structural['condition'] = structural.get('condition', '').map(clean_condition)
    structural['point_count'] = pd.to_numeric(structural.get('repaired_point_count', structural.get('raw_point_count', np.nan)), errors='coerce')
    structural['corner_pairs'] = structural['point_count'] / 2.0
    valid_status = structural.get('structural_validation_status', '').astype(str).str.lower().eq('passed')
    structural['structurally_valid'] = valid_status
    pairwise = read_csv(C1_ROOT / 'geometry_pairwise_similarity_C1.csv')
    pcols = detect_pairwise_columns(pairwise)
    pairwise['condition_normalized'] = pairwise[pcols['condition']].map(clean_condition) if pcols['condition'] else ''
    q1 = pd.to_numeric(pairwise[pcols['q_boundary']], errors='coerce') if pcols['q_boundary'] else pd.Series(np.nan, index=pairwise.index)
    q2 = pd.to_numeric(pairwise[pcols['q_wall']], errors='coerce') if pcols['q_wall'] else pd.Series(np.nan, index=pairwise.index)
    pairwise['pair_similarity'] = np.minimum(q1, q2)
    pairwise['pair_dissimilarity'] = 1.0 - pairwise['pair_similarity']
    pairwise['pair_metric_eligible'] = pairwise[pcols['compatible']].map(truth) if pcols['compatible'] else pairwise['pair_similarity'].notna()
    if pcols['correspondence']:
        pairwise['pair_metric_eligible'] &= pairwise[pcols['correspondence']].map(truth)
    quality = read_csv(C1_ROOT / 'c1_gt_quality_evidence.csv')
    quality['condition'] = quality.get('condition', '').map(clean_condition)
    candidates = ['iou_to_gt', 'c1_iou_to_gt', 'gt_iou', 'gt_iou_public_if_computable']
    quality_col = next((column for column in candidates if column in quality.columns), '')
    quality['quality'] = pd.to_numeric(quality[quality_col], errors='coerce') if quality_col else np.nan
    if 'gt_primary_analysis_eligible' in quality:
        quality['quality_primary_eligible'] = quality['gt_primary_analysis_eligible'].map(truth)
    elif 'quality_evaluable' in quality:
        quality['quality_primary_eligible'] = quality['quality_evaluable'].map(truth)
    else:
        quality['quality_primary_eligible'] = quality['quality'].notna()
    return sidecar, structural, pairwise, quality

def aggregate_uncertainty(sidecar: pd.DataFrame, structural: pd.DataFrame, pairwise: pd.DataFrame, quality: pd.DataFrame, c1_timing: pd.DataFrame) -> pd.DataFrame:
    base = sidecar.copy()
    for column in ['valid_k', 'largest_cluster_share', 'second_cluster_share', 'cluster_margin_all']:
        base[column] = pd.to_numeric(base[column], errors='coerce')
    valid_struct = structural[structural['structurally_valid'] & structural['corner_pairs'].notna()].copy()
    corner_rows = []
    for (task, condition), group in valid_struct.groupby(['base_task_id', 'condition']):
        counts = group['corner_pairs'].round().astype(int).value_counts().sort_index().tolist()
        denominator = structural[(structural['base_task_id'] == task) & (structural['condition'] == condition)]
        corner_rows.append({'base_task_id': task, 'condition': condition, 'corner_mode_count': len(counts), 'corner_entropy': entropy_from_counts(counts), 'corner_entropy_mm': miller_madow_entropy(counts), 'corner_gini': gini_simpson(counts), 'corner_pair_sd': float(group['corner_pairs'].std(ddof=1)) if len(group) > 1 else 0.0, 'invalid_geometry_rate': 1.0 - float(denominator['structurally_valid'].mean())})
    corner = pd.DataFrame(corner_rows)
    pcols = detect_pairwise_columns(pairwise)
    pair_rows = []
    eligible_pairs = pairwise[pairwise['pair_metric_eligible'] & pairwise['pair_similarity'].notna()].copy()
    for (task, condition), group in eligible_pairs.groupby([pcols['task'], 'condition_normalized']):
        values = group['pair_similarity'].astype(float)
        pair_rows.append({'base_task_id': task, 'condition': condition, 'pair_count': len(values), 'pair_similarity_mean': float(values.mean()), 'pair_similarity_median': float(values.median()), 'pair_similarity_p10': float(values.quantile(0.1)), 'pair_dissimilarity_mean': float((1.0 - values).mean()), 'compatible_edge_rate_095': float((values >= 0.95).mean()), 'compatible_edge_rate_0925': float((values >= 0.925).mean()), 'compatible_edge_rate_090': float((values >= 0.9).mean())})
    pair = pd.DataFrame(pair_rows)
    quality_eligible = quality[quality['quality'].notna() & quality['quality_primary_eligible']].copy()
    quality_rows = quality_eligible.groupby(['base_task_id', 'condition'])['quality'].agg(quality_n='size', quality_mean='mean', quality_sd='std', quality_median='median', quality_min='min').reset_index()
    timing = c1_timing.copy()
    timing['condition'] = timing.get('condition', '').map(clean_condition)
    timing['time'] = pd.to_numeric(timing.get('task_worker_active_seconds', np.nan), errors='coerce')
    timing = timing[timing.get('task_worker_time_analysis_eligible', False).map(truth) & timing['time'].notna()]
    timing_rows = timing.groupby(['base_task_id', 'condition'])['time'].agg(active_time_n='size', active_time_mean='mean', active_time_median='median', active_time_sd='std').reset_index()
    result = base.merge(corner, how='left', on=['base_task_id', 'condition'])
    result = result.merge(pair, how='left', on=['base_task_id', 'condition'])
    result = result.merge(quality_rows, how='left', on=['base_task_id', 'condition'])
    result = result.merge(timing_rows, how='left', on=['base_task_id', 'condition'])
    return result

def extract_node_pair_map(pairwise: pd.DataFrame) -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    cols = detect_pairwise_columns(pairwise)
    use_annotation = bool(cols['left_annotation'] and cols['right_annotation'])
    left_col = cols['left_annotation'] if use_annotation else cols['left_worker']
    right_col = cols['right_annotation'] if use_annotation else cols['right_worker']
    nodes: dict[tuple[str, str], set[str]] = defaultdict(set)
    pairs: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for _, row in pairwise.iterrows():
        task = str(row.get(cols['task'], ''))
        condition = clean_condition(row.get(cols['condition'], '')) if cols['condition'] else ''
        left, right = str(row.get(left_col, '')), str(row.get(right_col, ''))
        if not task or not condition or not left or not right:
            continue
        nodes[task, condition].update([left, right])
        pairs[(task, condition, *sorted((left, right)))] = {'similarity': num(row.get('pair_similarity')), 'eligible': truth(row.get('pair_metric_eligible'))}
    return {key: sorted(value) for key, value in nodes.items()}, pairs

def graph_partition_metrics(task: str, condition: str, sample: Sequence[str], pair_map: dict[tuple[str, str, str, str], dict[str, Any]], threshold: float=0.95) -> dict[str, float | str]:
    sample = tuple(sorted(sample))
    if len(sample) < 3 or cluster_geometry_records is None:
        return {'status': 'not_evaluable', 'entropy': np.nan, 'gini': np.nan, 'largest_share': np.nan, 'cluster_count': np.nan}
    records = [{'canonical_annotation_id': node, 'worker_id': node, '_geometry': {'valid': True, 'node_id': node}} for node in sample]
    def pairwise_fn(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        a, b = str(left.get('node_id', '')), str(right.get('node_id', ''))
        item = pair_map.get((task, condition, *sorted((a, b))))
        if not item or not item['eligible'] or item['similarity'] is None:
            return {'metric_compatible': False, 'pointwise_correspondence_compatible': False, 'q_boundary': None, 'q_wallwall': None}
        similarity = float(item['similarity'])
        return {'metric_compatible': True, 'pointwise_correspondence_compatible': True, 'q_boundary': similarity, 'q_wallwall': similarity}
    result = cluster_geometry_records(records, min_q_boundary=threshold, min_q_wallwall=threshold, base_task_id=task, condition=condition, minimum_valid_k=3, maximum_partition_count=256, maximum_search_nodes=10000, pairwise_fn=pairwise_fn)
    sizes = parse_cluster_sizes(result.get('cluster_membership_json', '[]'))
    return {'status': str(result.get('task_crowd_structure_status') or 'not_evaluable'), 'entropy': entropy_from_counts(sizes) if sizes else np.nan, 'gini': gini_simpson(sizes) if sizes else np.nan, 'largest_share': max(sizes) / sum(sizes) if sizes else np.nan, 'cluster_count': len(sizes) if sizes else np.nan}

def threshold_sensitivity(pairwise: pd.DataFrame, out: Path) -> pd.DataFrame:
    nodes, pair_map = extract_node_pair_map(pairwise)
    rows = []
    for (task, condition), available in sorted(nodes.items()):
        if len(available) < 3:
            continue
        for threshold in (0.9, 0.925, 0.95):
            rows.append({'base_task_id': task, 'condition': condition, 'threshold': threshold, 'valid_k': len(available), **graph_partition_metrics(task, condition, available, pair_map, threshold=threshold)})
    result = pd.DataFrame(rows)
    write_csv(out / 'geometry_cluster_threshold_sensitivity.csv', result)
    return result

def equal_k_replay(pairwise: pd.DataFrame, overlap_tasks: Sequence[str], *, replicates: int=500) -> pd.DataFrame:
    nodes, pair_map = extract_node_pair_map(pairwise)
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(SEED)
    for task in sorted(overlap_tasks):
        manual_nodes = nodes.get((task, 'manual'), [])
        semi_nodes = nodes.get((task, 'semi'), [])
        common_k = min(len(manual_nodes), len(semi_nodes))
        if common_k < 3:
            continue
        for replicate in range(replicates):
            record: dict[str, Any] = {'base_task_id': task, 'replicate': replicate, 'common_k': common_k}
            for condition, available in (('manual', manual_nodes), ('semi', semi_nodes)):
                sample = available if len(available) == common_k else sorted(rng.choice(available, size=common_k, replace=False).tolist())
                for key, value in graph_partition_metrics(task, condition, sample, pair_map, threshold=0.95).items():
                    record[f'{condition}_{key}'] = value
            rows.append(record)
    return pd.DataFrame(rows)
