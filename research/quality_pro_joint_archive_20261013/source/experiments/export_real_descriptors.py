#!/usr/bin/env python3
"""Export all 922 source rows without introducing a quality or eligibility label."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from structural_features import direction_descriptors, raw_vertical_alignment

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--out', type=Path, default=Path(__file__).parent/'results')
    args = p.parse_args()
    source = args.source.resolve(); out = args.out.resolve()
    data = read(source/'inputs/calibration_records.json')
    layers_path = source/'input_quality/results/source_layers_922.json'
    layers = {r['object_id']: r for r in read(layers_path)}
    engine = source/'source_snapshot/research/quality_scope_comparison_20261010/frozen_engine'
    sys.path.insert(0, str(engine/'validity'))
    sys.path.insert(0, str(engine/'legacy_geometry'))
    from strict_geometry import validate_record
    from audit_geometry import direction_axis, direction_residual
    rows = []
    independent_errors = []
    frozen_errors = []
    invariance = []
    for r in data['rows']:
        g = data['geometries'].get(r['object_id'])
        row = {k: r.get(k) for k in ('object_id', 'image_id', 'image_code', 'building_id',
                'room_group', 'worker_id', 'current_points_sha256', 'reference_points_sha256',
                'reference_object_id', 'coordinate_hash', 'pool', 'applicability_confirmed')}
        row.update(record_id=r['id'], input_version='calibration_records_20261012_frozen_mean_x_geometry',
                   annotation_geometry_sha256=digest(g),
                   legacy_metric_D_rms_deg=r['metrics']['dir'], eligibility=r['gate'])
        try:
            validity = validate_record(g, role='annotation')
            row['validity'] = validity
            if not validity['valid_2d']:
                row['status'] = 'unavailable_floor_geometry'
                row['reason_codes'] = [x['code'] for x in validity['errors']]
            else:
                descriptor = direction_descriptors(g['bottom3d'])
                row.update(descriptor)
                frozen_d = direction_residual(g, direction_axis(g))
                row['independent_vs_engine_D_abs_difference_deg'] = abs(descriptor['D_rms_deg']-frozen_d)
                row['independent_vs_frozen_metric_D_abs_difference_deg'] = abs(descriptor['D_rms_deg']-r['metrics']['dir'])
                independent_errors.append(row['independent_vs_engine_D_abs_difference_deg'])
                frozen_errors.append(row['independent_vs_frozen_metric_D_abs_difference_deg'])
                points = np.asarray(g['bottom3d'], float)
                split = np.vstack([points[:1], .7*points[0]+.3*points[1], points[1:]])
                transformed = [direction_descriptors(q) for q in (points[::-1], np.roll(points, 1, axis=0), split)]
                for name, t in zip(('reverse', 'cyclic', 'collinear_split'), transformed):
                    invariance.append({'record_id':r['id'], 'transform':name,
                        'D_abs_diff_deg': abs(t['D_rms_deg']-descriptor['D_rms_deg']),
                        'moment4_rel_difference': abs(t['weighted_abs_moments_deg_power']['p4']-
                         descriptor['weighted_abs_moments_deg_power']['p4']) / max(1., descriptor['weighted_abs_moments_deg_power']['p4']),
                        'tail10_p2_abs_diff':abs(t['excess_by_threshold_deg']['10']['normalized_excess_p2']-
                                              descriptor['excess_by_threshold_deg']['10']['normalized_excess_p2'])})
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            row.update(status='unavailable_descriptor', reason_codes=[str(exc)])
        layer = layers.get(r['object_id'])
        if layer is None:
            row['raw_alignment'] = {'status': 'unavailable_raw_source'}
        else:
            row['raw_before_preprocessing_points_sha256_canonical'] = digest(layer['before_preprocessing_points'])
            row['mean_x_preprocessed_points_sha256_canonical'] = digest(layer['preprocessed_points'])
            row['raw_source_provenance'] = layer['source']
            try:
                row['raw_alignment'] = raw_vertical_alignment(layer)
            except (ValueError, KeyError, ArithmeticError) as exc:
                row['raw_alignment'] = {'status':'unavailable', 'reason':str(exc)}
        rows.append(row)
    references = []
    for oid in sorted(set(r['reference_object_id'] for r in data['rows'])):
        g = data['geometries'].get(oid)
        try:
            descriptor = direction_descriptors(g['bottom3d'])
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            descriptor = {'status':'unavailable', 'reason':str(exc)}
        references.append({'reference_object_id':oid, 'geometry_sha256':digest(g), **descriptor})
    provenance = {
        'schema':'length_supported_direction_descriptors_v1',
        'source_calibration_sha256':sha(source/'inputs/calibration_records.json'),
        'source_raw_layers_sha256':sha(layers_path),
        'source_declared_main_sha':data['main_sha'],
        'latest_audit_sha':'fdfc8a51ad668c83172ca4a9cf0105f417dac61c',
        'input_version_is_distinct_from_latest_audit_version':True,
        'structural_features_sha256':sha(Path(__file__).parent/'structural_features.py'),
        'frozen_engine_audit_geometry_sha256':sha(engine/'legacy_geometry/audit_geometry.py'),
        'point_hashes':{'current_points_sha256':'source-supplied identifier retained unchanged',
                        '*_canonical':'independent canonical JSON SHA256; not substituted for source hashes'},
        'all_computable_rows_not_newly_qualified':True,
        'n_rows':len(rows), 'n_available':sum(r['status']=='available' for r in rows),
        'n_references':len(references),
        'max_independent_vs_engine_D_abs_diff_deg':max(independent_errors, default=None),
        'max_independent_vs_frozen_metric_D_abs_diff_deg':max(frozen_errors, default=None),
        'n_invariance_checks':len(invariance),
        'max_invariance_D_diff_deg':max((r['D_abs_diff_deg'] for r in invariance), default=None),
        'max_invariance_moment4_relative_diff':max((r['moment4_rel_difference'] for r in invariance), default=None),
        'max_invariance_tail10_p2_abs_diff':max((r['tail10_p2_abs_diff'] for r in invariance), default=None),
        'max_raw_X_minus_2E_abs_diff_deg':max((abs(r['raw_alignment']['X_rms_deg']-2*r['raw_alignment']['Eperp_deg'])
                                           for r in rows if r['raw_alignment']['status']=='available'), default=None),
    }
    write(out/'real_direction_descriptors.json', {'provenance':provenance, 'rows':rows, 'references':references})
    write(out/'descriptor_invariance.json', invariance)
    write(out/'descriptor_summary.json', provenance)
    csv_rows=[]
    for r in rows:
        t={k:r.get(k) for k in ('record_id','object_id','image_code','building_id','status','D_rms_deg','Dmax_deg','axis_deg','axis_tie_count')}
        if r['status']=='available':
            for th,v in r['excess_by_threshold_deg'].items():
                for k in ('fraction_above','normalized_excess_p2','normalized_excess_p4'):
                    t[f'threshold{th}_{k}']=v[k]
        t.update({k:r['raw_alignment'].get(k) for k in ('X_rms_deg','Eperp_deg')})
        csv_rows.append(t)
    out.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for r in csv_rows for k in r))
    with (out/'real_direction_descriptors.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(csv_rows)
    print(json.dumps(provenance,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
