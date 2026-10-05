"""只复算嵌入的诊断输入；不读取全量manifest、重做选样或运行共识。"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import sys

from tools.thesis_main.analysis.layout_metric_response_20261001 import PLAN, SCHEMA, measure, _flat

RESULTS = Path('analysis_results/layout_metric_response_20261001')


def _compare(expected, actual, path):
    """状态/字段/身份严格匹配；仅浮点数允许明示舍入容差。"""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() != actual.keys(): raise ValueError(path+': field drift')
        for key,value in expected.items(): _compare(value,actual[key],path+'.'+key)
    elif isinstance(expected, list):
        if not isinstance(actual,list) or len(expected) != len(actual): raise ValueError(path+': list drift')
        for i,(a,b) in enumerate(zip(expected,actual)): _compare(a,b,f'{path}[{i}]')
    elif isinstance(expected, float):
        if (type(actual) not in (int,float) or not math.isfinite(expected) or not math.isfinite(actual)
                or not math.isclose(expected,actual,rel_tol=1e-9,abs_tol=1e-10)):
            raise ValueError(path+': numeric mismatch')
    elif type(expected) is not type(actual) or expected != actual:
        raise ValueError(path+': value/type mismatch')


def verify_embedded(result):
    if result['schema'] != SCHEMA: raise ValueError('unsupported_snapshot_schema')
    _compare(PLAN,result['plan'],'plan')
    present=0; missing=0
    for kind in ('synthetic','real'):
        for i,row in enumerate(result[kind]):
            path=f'{kind}[{i}]'
            if row['b'] is None:
                if kind != 'real': raise ValueError(path+': missing synthetic baseline')
                absent=dict(status='unavailable',reason='reference_version_absent')
                expected=dict(bev=dict(absent,bev_range_iou=None),boundary=dict(absent,boundary_sampled_max=None),
                    column={f'{w}x{h}':dict(absent,iou=None) for w,h in PLAN['raster_sizes']},
                    correspondence=dict(status='unavailable',reason='real_source_correspondence_not_established'),
                    manhattan=dict(status='unavailable',reason='real_common_axis_not_established'))
                missing+=1
            else:
                expected=measure(row['a'],row['b'],synthetic=kind=='synthetic')
                present+=kind=='real'
            _compare(expected,row['metrics'],path+'.metrics')
    dense=result['boundary_dense_check']
    if dense is not None:
        case=next(c for c in result['synthetic'] if (c['case'],c['amplitude'])==(dense['case'],dense['amplitude']))
        expected=measure(case['a'],case['b'],synthetic=True,
                         boundary_samples=PLAN['boundary_dense_check']['samples_per_side'])['boundary']
        _compare(expected,dense['boundary'],'boundary_dense_check')
    return dict(verified=True,synthetic_pairs=len(result['synthetic']),
                synthetic_families=dict(Counter(r['family'] for r in result['synthetic'])),
                real_comparisons=present,missing_reference_rows=missing,dense_boundary_checks=int(dense is not None))


def verify_snapshot(root):
    root=Path(root).resolve()
    manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['schema'] != 'public_research_bundle_manifest_v1': raise ValueError('unsupported_bundle_manifest')
    expected_files={r['path'] for r in manifest['files']}
    if len(expected_files) != len(manifest['files']): raise ValueError('duplicate_inventory_path')
    actual_files={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}-{'MANIFEST.json'}
    if expected_files != actual_files: raise ValueError('bundle_inventory_mismatch')
    for entry in manifest['files']:
        path=root/entry['path']
        if not path.resolve().is_relative_to(root) or path.stat().st_size != entry['bytes']:
            raise ValueError('bundle_path_or_size_mismatch:'+entry['path'])
        if entry['path'].endswith('.py') and entry['path'].startswith(('tools/','lib/')):
            module=sys.modules.get(entry['path'][:-3].replace('/','.'))
            if module is not None and Path(module.__file__).resolve() != path.resolve():
                raise ValueError('dependency_loaded_outside_snapshot:'+entry['path'])
    if not Path(__file__).resolve().is_relative_to(root): raise ValueError('verifier_loaded_outside_snapshot')
    result=json.loads((root/RESULTS/'results.json').read_text(encoding='utf-8'))
    _compare(result['plan'],json.loads((root/RESULTS/'experiment_plan.json').read_text(encoding='utf-8')),'plan_file')
    summary=verify_embedded(result)
    _compare(manifest['expected_recheck'],{k:summary[k] for k in manifest['expected_recheck']},'recheck_counts')
    contract=json.loads((root/RESULTS/'field_contract.json').read_text(encoding='utf-8'))
    if contract['schema'] != SCHEMA: raise ValueError('field_contract_schema_drift')
    for kind in ('synthetic','real'):
        with (root/RESULTS/(kind+'_metrics.csv')).open(encoding='utf-8-sig',newline='') as stream:
            reader=csv.DictReader(stream); rows=list(reader)
            if reader.fieldnames != contract['csv_fields'][kind]: raise ValueError(kind+': csv field drift')
        if len(rows) != len(result[kind]): raise ValueError(kind+': csv row drift')
        for i,(row,saved) in enumerate(zip(result[kind],rows)):
            flat=_flat(row)
            expected={key:json.dumps(flat[key],ensure_ascii=False) if isinstance(flat.get(key),(dict,list))
                      else str(flat[key]) if flat.get(key) is not None else '' for key in reader.fieldnames}
            _compare(expected,saved,f'{kind}_csv[{i}]')
    summary.update(scope='embedded input recheck only; no source binding, selection reconstruction or new experiment',
                   float_tolerance=dict(relative=1e-9,absolute=1e-10),inventory_files=len(expected_files))
    return summary


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    args=parser.parse_args()
    print(json.dumps(verify_snapshot(args.root),ensure_ascii=False,indent=2,allow_nan=False))
