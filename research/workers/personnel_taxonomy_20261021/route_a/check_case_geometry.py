#!/usr/bin/env python3
"""Narrow receipt for already selected A2 illustrations; never modifies geometry."""
import gzip
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append('/tmp/hohonet_deps')
from shapely.geometry import Polygon
from shapely.validation import explain_validity

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(path):
    with gzip.open(path, 'rt', encoding='utf8') as f:
        return json.load(f)


def main():
    cluster = ROOT / 'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/clusters/CLUSTER_API.json.gz'
    audit = ROOT / 'research/statistics/v2_evidence_audit_20261019/records.json.gz'
    api = {g['object_id']: g for p in read(cluster)['pools'] for g in p['geometries']}
    cases = pd.read_csv(HERE / 'A2_case_candidates.csv')
    wanted = set('|'.join(cases.object_ids_a.tolist() + cases.object_ids_b.tolist()).split('|'))
    records = {r['object_id']: r for r in read(audit)['records'] if r['object_id'] in wanted}
    spec = importlib.util.spec_from_file_location('case_visuals_for_receipt', ROOT / 'research/workers/personnel_interchangeability_20261020/analysis/composition/case_visuals.py')
    viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(viewer)
    diagnostics = {}
    for oid in sorted(wanted):
        r, g = records[oid], api[oid]
        v = viewer.viewer_geometry(r['points_1024x512'])
        poly = Polygon(g['floor'])
        supplied = r['received_processed_points']
        preprocessed = np.asarray(r['preprocessed_points'], dtype=float)
        rebuilt_diff = None
        if supplied is not None:
            q = np.asarray(supplied, dtype=float).copy()
            shared = (q[::2, 0] + ((q[1::2, 0] - q[::2, 0] + 512) % 1024 - 512) / 2) % 1024
            q[::2, 0] = q[1::2, 0] = shared
            if q.shape == preprocessed.shape:
                rebuilt_diff = float(np.max(np.abs(q - preprocessed)))
        diagnostics[oid] = {
            'worker_id': r['worker_id'], 'image_code': r['image_code'],
            'image_id': r['image_id'], 'pair_n': len(g['points']) // 2,
            'api_points_equal_audit_preprocessed': bool(np.array_equal(g['points'], r['preprocessed_points'])),
            'api_points_equal_audit_1024x512': bool(np.array_equal(g['points'], r['points_1024x512'])),
            'api_floor_vs_viewer_max_abs_difference': float(np.max(np.abs(np.asarray(g['floor']) - v['floor']))),
            'floor_is_valid': bool(poly.is_valid), 'floor_ring_is_simple': bool(poly.exterior.is_simple),
            'floor_validity': explain_validity(poly),
            'api_geometry_status': g['geometry_status'], 'audit_geometry_status': r['geometry_status'],
            'audit_order_status': r['order_status'], 'ring_confirmed': r['ring_confirmed'],
            'quality_usable_unchanged': r['quality_usable'],
            'original_points_available': r['original_points'] is not None,
            'audit_received_processed_available': supplied is not None,
            'received_shared_x_vs_preprocessed_max_abs_difference': rebuilt_diff,
            'source_path': r['source_evidence'].get('path'),
            'source_path_present_in_checkout': bool((ROOT / str(r['source_evidence'].get('path'))).is_file()),
            'ordered_source_pair_indices': r['coordinate_evidence'].get('ordered_source_pair_indices'),
        }
    selected = cases.iloc[0]
    selected_ids = (selected.object_ids_a + '|' + selected.object_ids_b).split('|')
    pair_w132_w133 = Polygon(api['v2:new:100460']['floor']).boundary.intersection(Polygon(api['v2:new:100461']['floor']).boundary)
    output = {
        'scope': 'Previously selected A2 cases only; read-only receipt, no new classification or case search.',
        'inputs': [str(cluster.relative_to(ROOT)), str(audit.relative_to(ROOT)), str((HERE / 'A2_case_candidates.csv').relative_to(ROOT))],
        'case': selected.image_code,
        'records': {o: diagnostics[o] for o in selected_ids},
        'w132_w133_two_distinct_boundaries_intersection': pair_w132_w133.wkt,
        'interpretation_zh': '四份各自的底面均有效且无自交；W132与W133两人的边界相交是不同作答叠加后的交点，不是单份底面自交。四份均default_unreviewed、ring_confirmed=false。只能核到审计包所保存的用户processed输入，不能声称已取得新批original export。A02两人含约x=282/286的角对且不含约x=584/586角对；A03两人相反，均为六角对，显示选中的角点位置集合不同。此处不新增目标范围或正确性裁定。',
        'geometry_modified': False,
    }
    (HERE / 'A2_7y21_geometry_receipt.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    table = []
    for r in cases.itertuples(index=False):
        ids = (r.object_ids_a + '|' + r.object_ids_b).split('|')
        ds = [diagnostics[o] for o in ids]
        row = r._asdict()
        row.update(all_selected_floors_valid=all(x['floor_is_valid'] for x in ds),
                   all_selected_floor_rings_simple=all(x['floor_ring_is_simple'] for x in ds),
                   all_selected_api_points_match_audit=all(x['api_points_equal_audit_preprocessed'] and x['api_points_equal_audit_1024x512'] for x in ds),
                   selected_ring_confirmed_n=sum(bool(x['ring_confirmed']) for x in ds),
                   max_api_floor_viewer_difference=max(x['api_floor_vs_viewer_max_abs_difference'] for x in ds))
        table.append(row)
    pd.DataFrame(table).to_csv(HERE / 'A2_existing_case_geometry_status.csv', index=False)
    print(json.dumps({'selected_case': selected.image_code, 'selected_all_valid_simple': all(diagnostics[o]['floor_is_valid'] and diagnostics[o]['floor_ring_is_simple'] for o in selected_ids), 'candidates_checked': len(cases), 'max_selected_shared_x_error': max(diagnostics[o]['received_shared_x_vs_preprocessed_max_abs_difference'] for o in selected_ids), 'max_selected_floor_viewer_error': max(diagnostics[o]['api_floor_vs_viewer_max_abs_difference'] for o in selected_ids)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
