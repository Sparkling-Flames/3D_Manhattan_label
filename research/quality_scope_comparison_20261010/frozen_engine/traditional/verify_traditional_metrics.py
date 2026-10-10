#!/usr/bin/env python3
"""Independent official-function and arithmetic audit; not the RMSE pipeline.

No score tuning, human-label use, geometry repair, source changes or network.
Requires NumPy/SciPy and the bundled frozen polygon intersection audit.
"""
import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def official_functions(vendor):
    text = (vendor/'post_proc.py').read_text()
    tree = ast.parse(text)
    names = {'np_coorx2u', 'np_coory2v', 'np_coor2xy', 'get_z1'}
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    if {f.name for f in functions} != names:
        raise RuntimeError('Official function set changed; inspect new source rather than silently adapting.')
    namespace = {'np': np, 'PI': float(np.pi)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(vendor/'post_proc.py'), 'exec'), namespace)
    post = SimpleNamespace(**{k: namespace[k] for k in names})

    eval_tree = ast.parse((vendor/'eval_layout.py').read_text())
    general = next(n for n in eval_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'test_general')
    # Keep original first four pair-array assignments and the official ch=-1.6
    # assignment. Preserve the complete official 3D-IoU try/except statement.
    body = general.body[:4]
    for n in general.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ch' for t in n.targets):
            body.append(n)
    volume_block = next(n for n in general.body if isinstance(n, ast.Try) and any(
        isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'cch_dt' for t in a.targets)
        for a in n.body))
    body.append(volume_block)
    body.append(ast.Return(value=ast.Tuple(elts=[ast.Name(id=n, ctx=ast.Load()) for n in ['iou3d','h_dt','h_gt']], ctx=ast.Load())))
    args = ast.arguments(posonlyargs=[], args=[ast.arg(arg=n) for n in
        ['dt_cor_id','gt_cor_id','area_dt','area_gt','area_inter']], kwonlyargs=[], kw_defaults=[], defaults=[])
    wrapper = ast.FunctionDef(name='_official_volume_fragment', args=args, body=body, decorator_list=[])
    compiled = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
    ns = {'np':np, 'post_proc':post}
    exec(compile(compiled, str(vendor/'eval_layout.py'), 'exec'), ns)
    return post, ns['_official_volume_fragment']


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def make_subdivision_controls():
    xz = np.array([[-2.,-1.],[2.,-1.],[2.,1.],[-2.,1.]])
    bottom = np.c_[xz[:,0], np.full(4,-1.), xz[:,1]]
    top = bottom.copy(); top[:,1] = np.array([1.01,1.01,2.99,2.99])-1.
    reference = {'top3d':np.c_[xz[:,0],np.ones(4),xz[:,1]].tolist(),'bottom3d':bottom.tolist()}
    annotation = {'top3d':top.tolist(),'bottom3d':bottom.tolist()}
    out = [{'case':'vertex_height_base4','annotation':annotation,'reference':reference}]
    for edge, name in [(0,'low_edge'),(2,'high_edge')]:
        tt, bb = [], []
        for i in range(4):
            tt.append(top[i]); bb.append(bottom[i])
            if i == edge:
                for f in np.arange(1,41)/41:
                    tt.append((1-f)*top[i]+f*top[(i+1)%4])
                    bb.append((1-f)*bottom[i]+f*bottom[(i+1)%4])
        out.append({'case':'vertex_height_'+name+'_40_collinear_insertions',
                    'annotation':{'top3d':np.asarray(tt).tolist(),'bottom3d':np.asarray(bb).tolist()},
                    'reference':reference})
    return out


def main():
    p = argparse.ArgumentParser()
    root = HERE.parents[2]
    p.add_argument('--source', type=Path, default=root/'source/oct8-pro-quality-handoff')
    p.add_argument('--polygon-audit', type=Path, default=root/'work/research_v1/geometry/audit_geometry.py')
    p.add_argument('--control-geometries', type=Path, default=root/'work/research_v1/geometry/results_v3/control_geometries.json')
    p.add_argument('--height-controls', type=Path, default=root/'work/research_v1/height_guard/final_results/large_room_uniform_height9_geometries.json')
    p.add_argument('--audit-controls', type=Path, default=root/'work/research_v1_1/new_independent_audit/layout_quality_v1_independent_audit/numeric/independent_counterexample_geometries.json')
    p.add_argument('--quality-module', type=Path, default=None,
                   help='Optional frozen quality_v11.py path: verify identical geometry despite nonuniform collinear subdivision.')
    p.add_argument('--output', type=Path, default=HERE/'results')
    args = p.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    audit = load_module(args.polygon_audit, '_old_polygon_audit_for_traditional')
    tr = load_module(HERE/'traditional_metrics.py', '_traditional_metrics_audit_target')
    post, volume = official_functions(HERE/'vendor')
    frozen = json.loads((args.source/'inputs/frozen_geometry.json').read_text())
    with (args.source/'data/all48_reference_specific_metrics.csv').open(encoding='utf-8-sig') as f:
        previous = {(r['review_id'],r['reference_id']):r for r in csv.DictReader(f)}
    cases = []
    for im in frozen['images']:
        for a in im['annotations']:
            for g in im['groundtruths']:
                cases.append(dict(case=a['reviewId']+'__'+g['id'], kind='real_reference48',
                                  review_id=a['reviewId'], reference_id=g['id'], image_code=im['code'],
                                  annotation=a,reference=g))
    for entry in json.loads(args.control_geometries.read_text()):
        cases.append(dict(case=entry['case_id'],kind='existing_control251',annotation=entry['annotation'],reference=entry['reference']))
    height_entries = json.loads(args.height_controls.read_text())
    for i, entry in enumerate(height_entries):
        cases.append(dict(case=entry.get('case_id',entry.get('case','height'+str(i))),kind='height_control9',annotation=entry['annotation'],reference=entry['reference']))
    for entry in json.loads(args.audit_controls.read_text()):
        cases.append(dict(case=entry['case'],kind='new_audit_control8',annotation=entry['annotation'],reference=entry['reference']))
    subdivisions = make_subdivision_controls()
    (args.output/'nonuniform_collinear_subdivision_geometries.json').write_text(json.dumps(subdivisions,indent=2)+'\n')
    for c in subdivisions:
        cases.append(dict(c,kind='same_geometry_nonuniform_subdivision3'))

    rows, roundtrip = [], []
    for case in cases:
        a,g=case['annotation'],case['reference']
        r=tr.traditional_metrics_detailed(a,g,intersection_area_fn=audit.intersection_area)
        row = {k:case.get(k,'') for k in ['case','kind','review_id','reference_id','image_code']}
        row.update({k:v for k,v in r.items() if not isinstance(v,(dict,list))})
        row['reason_codes'] = ';'.join(r['traditional_reason_codes'])
        if r['traditional_status'] == 'available':
            pixel_a,pixel_g=tr.frozen_to_hohonet_pixels(a),tr.frozen_to_hohonet_pixels(g)
            off_xy_a=post.np_coor2xy(pixel_a[1::2],-1.6,1024,512,floorW=1,floorH=1)
            off_xy_g=post.np_coor2xy(pixel_g[1::2],-1.6,1024,512,floorW=1,floorH=1)
            # Polygon intersection of the ORIGINAL frozen floor, uniformly
            # scaled by 1.6, supplies the official fragment. No Shapely call is
            # being asserted; comparison to frozen previous IoU is separate.
            off_iou,h_a,h_g=volume(pixel_a,pixel_g,r['area_pred_h2']*1.6**2,
                                 r['area_ref_h2']*1.6**2,r['intersection_area_h2']*1.6**2)
            row.update(official_fragment_iou3d=float(off_iou),
                       official_fragment_height_pred=float(h_a),official_fragment_height_ref=float(h_g),
                       official_iou_abs_diff=abs(float(off_iou)-r['hohonet_iou3d_vertex_mean']),
                       official_height_pred_abs_diff=abs(float(h_a)-r['hohonet_height_pred_at_camera1p6']),
                       official_height_ref_abs_diff=abs(float(h_g)-r['hohonet_height_ref_at_camera1p6']))
            for label,record,pixels,xy in [('annotation',a,pixel_a,off_xy_a),('reference',g,pixel_g,off_xy_g)]:
                expected_xy=1.6*np.asarray(record['bottom3d'])[:,[0,2]]
                projected_top=post.get_z1(pixels[1::2,1],pixels[0::2,1],-1.6,512)
                expected_top=1.6*np.asarray(record['top3d'])[:,1]
                ri=dict(case=case['case'],kind=case['kind'],role=label,
                    xy_roundtrip_max_abs_h1p6=float(np.max(np.abs(xy-expected_xy))),
                    top_roundtrip_max_abs_h1p6=float(np.max(np.abs(projected_top-expected_top))),
                    paired_x_exactly_equal=bool(np.array_equal(pixels[0::2,0],pixels[1::2,0])))
                if record.get('points') is not None:
                    old=np.asarray(record['points'],float)
                    if old.shape==pixels.shape:
                        dx=(pixels[:,0]-(old[:,0]-.5)+512)%1024-512
                        dy=pixels[:,1]-(old[:,1]-.5)
                        ri['max_original_canvas_minus_half_pixel_diff']=float(max(np.abs(dx).max(),np.abs(dy).max()))
                roundtrip.append(ri)
            if case['kind']=='real_reference48':
                old=previous[(case['review_id'],case['reference_id'])]
                row['frozen_iou2d_abs_diff']=abs(r['iou2d_bev']-float(old['iou']))
                row['frozen_perimeter_volume_abs_diff']=abs(r['conditional_iou3d_perimeter_mean']-float(old['conditional_volume_iou']))
                # Deliberately naïve coordinate-feed experiment, stored only
                # as a convention diagnostic, never replacing the main score.
                pa_old,pg_old=np.asarray(a['points']),np.asarray(g['points'])
                xy_a_old=post.np_coor2xy(pa_old[1::2],-1.6,1024,512,floorW=1,floorH=1)
                xy_g_old=post.np_coor2xy(pg_old[1::2],-1.6,1024,512,floorW=1,floorH=1)
                aa_old,ag_old=abs(audit.signed_area(xy_a_old)),abs(audit.signed_area(xy_g_old))
                ai_old=audit.intersection_area(xy_a_old,xy_g_old)
                naive,_,_=volume(pa_old,pg_old,aa_old,ag_old,ai_old)
                row['naive_original_canvas_direct_iou3d']=float(naive)
                row['naive_coordinate_convention_iou3d_change']=float(naive)-r['hohonet_iou3d_vertex_mean']
        rows.append(row)

    write_csv(args.output/'traditional_all319_cases.csv',rows)
    write_csv(args.output/'official_geometry_roundtrip.csv',roundtrip)
    write_csv(args.output/'traditional_real48.csv',[r for r in rows if r['kind']=='real_reference48'])
    write_csv(args.output/'nonuniform_collinear_subdivision3.csv',[r for r in rows if r['kind']=='same_geometry_nonuniform_subdivision3'])
    maxima={k:max((float(r[k]) for r in rows if r.get(k) is not None),default=0.) for k in [
        'official_iou_abs_diff','official_height_pred_abs_diff','official_height_ref_abs_diff',
        'frozen_iou2d_abs_diff','frozen_perimeter_volume_abs_diff']}
    maxima.update({k:max(float(r[k]) for r in roundtrip if r.get(k) is not None) for k in [
        'xy_roundtrip_max_abs_h1p6','top_roundtrip_max_abs_h1p6','max_original_canvas_minus_half_pixel_diff']})
    all_small=all(v<1e-9 for v in maxima.values())
    unavailable=[{'case':r['case'],'kind':r['kind'],'reasons':r['reason_codes'],'status':r['traditional_status']} for r in rows if r['traditional_status']!='available']
    summary=dict(status='passed' if all_small else 'failed',case_count=len(rows),
        kind_counts={k:sum(r['kind']==k for r in rows) for k in sorted({r['kind'] for r in rows})},
        available_count=len(rows)-len(unavailable),not_fully_available=unavailable,
        maximum_numeric_differences=maxima,
        every_paired_pixel_x_exact=all(r['paired_x_exactly_equal'] for r in roundtrip),
        independent_official_functions=['np_coorx2u','np_coory2v','np_coor2xy','get_z1'],
        official_eval_fragment='unchanged AST of test_general 3D-IoU try block, provided independently verified footprint areas',
        shapely_available=False,full_eval_layout_pipeline_run=False,
        validation_limit='No Shapely polygon engine, depth/RMSE/delta1 or complete official CLI run claimed. IoU areas independently triangulated/clipped and matched against frozen 48-row results.',
        geometry_convention='frozen y=-1 camera-height units; official pixel inverse has -0.5 offsets; common scale=1.6; corners not Manhattanized or flat-fitted',
        vendor_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((HERE/'vendor').iterdir()) if p.is_file()},
        supplied_intersection_engine_sha256=hashlib.sha256(args.polygon_audit.read_bytes()).hexdigest())
    if args.quality_module is not None:
        from dataclasses import asdict
        quality = load_module(args.quality_module, '_quality_for_traditional_subdivision_check')
        quality_rows=[]
        for c in subdivisions:
            q=quality.score_geometry(c['annotation'],c['reference'])
            quality_rows.append(dict(case=c['case'],version=quality.VERSION,result=q))
        scores=[r['result']['quality_score'] for r in quality_rows]
        delta=max(scores)-min(scores) if all(x is not None for x in scores) else None
        check=dict(formula_code_sha256=hashlib.sha256(args.quality_module.read_bytes()).hexdigest(),
                   parameters=asdict(quality.Parameters()),quality_score_range=delta,rows=quality_rows)
        (args.output/'nonuniform_subdivision_quality_check.json').write_text(json.dumps(check,ensure_ascii=False,indent=2)+'\n')
        summary['quality_nonuniform_collinear_subdivision_score_range']=delta
        summary['quality_nonuniform_collinear_subdivision_passed']=delta is not None and delta<1e-8
        all_small = all_small and summary['quality_nonuniform_collinear_subdivision_passed']
        summary['status']='passed' if all_small else 'failed'
    (args.output/'traditional_independent_verification.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if not all_small:
        raise SystemExit(1)


if __name__=='__main__':
    main()
