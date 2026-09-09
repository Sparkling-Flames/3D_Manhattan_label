"""高人数手工图的 q 阈值审计；历史配对假设与无序点集对照分开保存。"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import point_distances, unit_points

INPUT = 'analysis_results/confirmed_point_calculation_view_20260909_v1/calculation_view.jsonl.gz'
OUTPUT = 'analysis_results/multibuilding_threshold_stability_20260909_v1/geometry'
THRESHOLDS = (.975, .95, .925, .90, .85, .80)


def gated_pairwise(left, right):
    """保留两项原 q；有效点数不等只改变兼容，不把未知 q 改成零。"""
    item = pairwise_similarity(left, right)
    same_count = left['n_points'] == right['n_points']
    return {**item, 'count_compatible': same_count,
            'pointwise_correspondence_compatible': same_count and item['pointwise_correspondence_compatible']}


def q_partition(records, threshold, pairwise_fn=None):
    if not 0 <= threshold <= 1:
        raise ValueError('q threshold outside [0,1]')
    return cluster_geometry_records(records, min_q_boundary=threshold, min_q_wallwall=threshold,
                                    minimum_valid_k=1, pairwise_fn=pairwise_fn or gated_pairwise)


def select_responses(source, excluded_workers=(), use_imputed=True):
    excluded_workers = set(map(str, excluded_workers))
    selected = []
    for original in source:
        if not original['calculation_included'] or original['assistance_exposure'] != 'none':
            continue
        if str(original['worker_id']) in excluded_workers:
            continue
        row = dict(original, imputation_withheld=False)
        if row.get('imputed_point') and not use_imputed:
            row.update(effective_points_1024x512=[p[:] for p in row['raw_points_1024x512']],
                       effective_point_count=len(row['raw_points_1024x512']),
                       processing_status='confirmed_addition_withheld', imputation_withheld=True)
        selected.append(row)
    return selected


def run(root=ROOT, output=None, input_path=None, excluded_workers=(), use_imputed=True, min_workers=16):
    output = Path(output) if output else root / OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    custom_input = input_path is not None
    input_path = Path(input_path) if input_path else root / INPUT
    if min_workers < 1:
        raise ValueError('min_workers must be positive')
    with gzip.open(input_path, 'rt', encoding='utf8') as stream:
        source = [json.loads(line) for line in stream]
    assert len({r['canonical_annotation_id'] for r in source}) == len(source)
    manual = select_responses(source, excluded_workers, use_imputed)
    assert all(r['unassisted_manual_included'] for r in manual)
    repeats = Counter((r['image_id'], str(r['worker_id'])) for r in manual)
    if any(n != 1 for n in repeats.values()):
        raise ValueError('same image/worker repeated; do not count responses as independent people')
    grouped = defaultdict(list)
    for row in manual:
        grouped[row['image_id']].append(row)
    images = {}
    for row in source:
        iid = row['image_id']
        if iid in images and images[iid]['building_id'] != row['building_id']:
            raise ValueError('Image/building identity drift')
        images[iid] = dict(image_id=iid, building_id=row['building_id'], usable_n=len(grouped[iid]),
                           dense_ge16=len(grouped[iid]) >= 16)
    inventory_path = output.parent / 'image_inventory.csv'
    if custom_input or not inventory_path.exists():
        pd.DataFrame(images.values()).sort_values('image_id').to_csv(inventory_path, index=False)
    grouped = {i: sorted(rows, key=lambda r: r['canonical_annotation_id'])
               for i, rows in sorted(grouped.items()) if len(rows) >= min_workers}
    responses, pairs, partitions = [], [], []
    for image_index, (image_id, rows) in enumerate(grouped.items(), 1):
        building_id = rows[0]['building_id']
        geometries, units = {}, {}
        for row in rows:
            canonical = row['canonical_annotation_id']
            points = row['effective_points_1024x512']
            assert points is not None and len(points) == row['effective_point_count']
            # No automatic orphan repair: only the already-confirmed effective view is consumed.
            geom = normalize_geometry(points)
            assert geom['n_points'] == row['effective_point_count']
            geom['_canonical_id'] = canonical
            geometries[canonical] = geom
            units[canonical] = unit_points(points)
            responses.append({k: row[k] for k in ('canonical_annotation_id', 'image_id', 'building_id',
                'worker_id', 'stage', 'block_index', 'raw_condition', 'assistance_exposure',
                'raw_point_count', 'effective_point_count', 'processing_status', 'distance_recompute_required')} | {
                    'q_geometry_valid': geom['valid'], 'q_geometry_reason': geom['reason'],
                    'pairing_method': geom['pairing_method'], 'n_pairs': geom['n_pairs'],
                    'q_geometry_scope': 'historical_pairing_assumption_not_confirmed_final_wall_order'})
        cache = {}
        for left, right in combinations(rows, 2):
            a, b = left['canonical_annotation_id'], right['canonical_annotation_id']
            metrics = gated_pairwise(geometries[a], geometries[b])
            cache[a, b] = metrics
            pairs.append({'image_id': image_id, 'building_id': building_id,
                          'left_canonical': a, 'right_canonical': b,
                          'left_worker': left['worker_id'], 'right_worker': right['worker_id'],
                          'left_effective_point_count': left['effective_point_count'],
                          'right_effective_point_count': right['effective_point_count'],
                          'left_q_geometry_valid': geometries[a]['valid'],
                          'right_q_geometry_valid': geometries[b]['valid'],
                          'count_compatible': metrics['count_compatible'],
                          'metric_compatible': metrics['metric_compatible'],
                          'pointwise_correspondence_compatible': metrics['pointwise_correspondence_compatible'],
                          'order_reason': metrics['order_reason'],
                          'q_boundary': metrics['q_boundary'], 'q_wallwall': metrics['q_wallwall'],
                          **point_distances(units[a], units[b])})
        records = [{'canonical_annotation_id': row['canonical_annotation_id'], 'worker_id': row['worker_id'],
                    '_geometry': geometries[row['canonical_annotation_id']]} for row in rows]

        def cached(left, right):
            return cache[tuple(sorted((left['_canonical_id'], right['_canonical_id'])))]

        for threshold in THRESHOLDS:
            result = q_partition(records, threshold, cached)
            memberships = json.loads(result['cluster_membership_json'])
            for group in memberships:
                assert len({geometries[c]['n_points'] for c in group}) == 1
            all_valid = result['valid_k'] == len(rows)
            partitions.append({'image_id': image_id, 'building_id': building_id, 'threshold': threshold,
                               'pointset_n': len(rows), 'q_valid_n': result['valid_k'],
                               'q_invalid_n': len(rows) - result['valid_k'], 'complete_q_coverage': all_valid,
                               'partition_scope': 'all_pointset_responses' if all_valid else 'q_valid_subset_only',
                               'full_image_status': ('unknown_invalid_geometry' if not all_valid else
                                   'truncated' if result['enumeration_truncated'] else
                                   'unique' if result['partition_status'] == 'unique' else 'non_unique'),
                               **{k: result[k] for k in ('partition_status', 'cluster_count',
                                   'cluster_membership_json', 'candidate_partitions_json',
                                   'enumeration_truncated', 'partition_search_nodes', 'clique_search_nodes',
                                   'task_crowd_structure_status', 'structure_reason')},
                               'candidate_partition_count': len(json.loads(result['candidate_partitions_json'])),
                               'singleton_clusters': sum(len(g) == 1 for g in memberships) if memberships else None,
                               'supported_m2_clusters': sum(len(g) >= 2 for g in memberships) if memberships else None,
                               'supported_m3_clusters': sum(len(g) >= 3 for g in memberships) if memberships else None})
        print(f'{image_index}/{len(grouped)} {image_id} N={len(rows)} q_valid={sum(g["valid"] for g in geometries.values())}', flush=True)
    pd.DataFrame(responses).to_csv(output / 'response_geometry.csv', index=False)
    pd.DataFrame(pairs).to_csv(output / 'pairwise_q.csv.gz', index=False, float_format='%.15g')
    pd.DataFrame(partitions).to_csv(output / 'full_q_partitions.csv', index=False)
    valid_n = sum(r['q_geometry_valid'] for r in responses)
    qa = {'source': str(input_path), 'selection': f'all stages, calculation_included, assistance_exposure=none; >={min_workers} unique workers per image',
          'excluded_workers': list(excluded_workers), 'use_confirmed_imputed_points': use_imputed,
          'imputed_selected_responses': sum(r.get('imputed_point', False) and not r['imputation_withheld'] for r in manual),
          'thresholds': THRESHOLDS, 'source_canonical_n': len(source), 'manual_pointset_n': len(manual),
          'image_n': len(grouped), 'building_n': len({r['building_id'] for r in responses}),
          'building_image_counts': dict(Counter(rows[0]['building_id'] for rows in grouped.values())),
          'response_n': len(responses), 'pair_n': len(pairs), 'full_partition_n': len(partitions),
          'duplicate_image_workers': 0, 'q_valid_n': valid_n, 'q_invalid_n': len(responses) - valid_n,
          'q_invalid_reasons': dict(Counter(r['q_geometry_reason'] for r in responses if not r['q_geometry_valid'])),
          'pair_q_metric_compatible_n': sum(r['metric_compatible'] for r in pairs),
          'pair_count_compatible_n': sum(r['count_compatible'] for r in pairs),
          'pair_pointwise_compatible_n': sum(r['pointwise_correspondence_compatible'] for r in pairs),
          'hard_point_count_violation_n': 0, 'all_ospa_distances_recomputed': True,
          'geometry_limit': 'q assumes historical ceiling/floor pairing and inferred boundary connections; final edited wall order was not saved',
          'missing_q_policy': 'blank/None is not comparable; do not replace with low similarity',
          'partition_scope_policy': 'q-invalid responses remain in pointset_n; subset clusters never imply full-image stability',
          'q_boundary_definition': '1 - mean(|top_left-top_right|+|floor_left-floor_right|)/(2*512), evaluated on 256 periodic x positions',
          'q_wallwall_definition': '1 - symmetric nearest-event circular horizontal distance/(1024/2)',
          'threshold_interpretation': 'both q channels must pass plus unique forward cyclic correspondence and equal effective count; no confidence interpretation',
          'protocol_guard': 'historical exploration only; shared pairing search implementation corrected; pairing objective, ambiguity rule, formal protocol and raw exports unchanged'}
    (output / 'QA.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding='utf8')
    print(json.dumps(qa, ensure_ascii=False, indent=2))
    return qa


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--exclude-workers', nargs='*', default=[])
    parser.add_argument('--no-imputation', action='store_true')
    parser.add_argument('--min-workers', type=int, default=16)
    args = parser.parse_args()
    run(args.root, args.out, args.input, args.exclude_workers, not args.no_imputation, args.min_workers)
