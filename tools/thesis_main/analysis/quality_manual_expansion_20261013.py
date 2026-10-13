"""冻结引擎扩展manual条件重评分；保持处理后点序及每个既有参考版本。"""
import argparse
from collections import Counter, defaultdict
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT/'research/quality_pro_joint_archive_20261013/source'
PACKAGE=ROOT/'research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012'
OUT=ROOT/'research/quality_manual_expansion_20261013'
NAMES=('baseline_quad08','J_main_hill_tail12_g1_l025','J_simple_power8_g1_l025')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def engine():
    root=PACKAGE/'source_snapshot/research/quality_scope_comparison_20261010/frozen_engine'
    for sub in ('legacy_geometry','validity','height_revision','traditional'):
        sys.path.insert(0,str(root/sub))
    sys.path.insert(0,str(PACKAGE/'scripts'))
    import audit_geometry, geometric_components, strict_geometry, height_revision, centered_height, traditional_metrics
    score=module(ARCHIVE/'calibration/score.py','expansion_score')
    geometry=module(ARCHIVE/'routing/prepare_inputs.py','expansion_geometry').geometry
    configs=read(ARCHIVE/'calibration/recommended_parameters.json')['candidates']
    configs={'baseline_quad08':score.BASELINE,**{n:configs[n] for n in NAMES[1:]}}
    return dict(au=audit_geometry,sp=geometric_components,valid=strict_geometry,hm=height_revision,
                center=centered_height,trad=traditional_metrics,score=score,geometry=geometry,configs=configs)


def evaluate_geometry(a,g,e):
    va=e['valid'].validate_record(a,role='annotation')
    vg=e['valid'].validate_record(g,role='reference')
    reasons=[role+':'+x['code'] for role,v in [('annotation',va),('reference',vg)] for x in v['errors']]
    out=dict(status='unavailable',reason_codes=reasons,metrics=None,candidate_components=None)
    if not va['available'] or not vg['available']:
        return out
    try:
        areas=e['au'].area_metrics(a,g)
        am=e['hm'].height_moments(a);gm=e['hm'].height_moments(g)
        center=e['center'].centered_height_components(a,g,samples=4096,height_module=e['hm'])
        traditional=e['trad'].traditional_metrics_detailed(a,g,areas=areas,annotation_validation=va,reference_validation=vg)
        metrics=dict(iou_2d=areas['iou'],S_bottom_deg=float(e['sp'].spherical_sym_distance(a['bottom3d'],g['bottom3d'],2048)),
            dir=float(e['au'].direction_residual(a,e['au'].direction_axis(a))),
            Hmean=abs(am['height_mean_h']/gm['height_mean_h']-1),Hcenter=center['Hcenter'],
            height_mean_ratio=am['height_mean_h']/gm['height_mean_h'],
            iou_3d_corner_mean=traditional['hohonet_iou3d_vertex_mean'])
        components={n:e['score'].score_metrics(metrics,c) for n,c in e['configs'].items()}
        out.update(status='complete' if all(c['status']=='complete' for c in components.values()) else 'formula_unavailable',
            metrics=metrics,candidate_components=components,height_diagnostics=center,
            traditional_reason_codes=traditional['traditional_reason_codes'])
    except (ValueError,ArithmeticError) as exc:
        out['reason_codes'].append(type(exc).__name__+':'+str(exc))
    return out


def main(parity_only=False):
    started=time.perf_counter();e=engine()
    objects={o['object_id']:o for o in load_current_bundle()['data']['objects']}
    current={r['record_id']:r for r in read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']}
    geometries={}
    def geometry(oid):
        if oid not in geometries:
            obj=objects[oid]
            if obj['geometry']['status']!='surface_valid' or not obj['links_zero_based']:
                raise ValueError('current_processed_geometry_unavailable:'+oid)
            geometries[oid]=e['geometry'](obj['points_1024x512'])
        return geometries[oid]
    frozen=read(PACKAGE/'inputs/calibration_records.json')
    rows=frozen['rows'];parity=[]
    for r in [rows[i] for i in (0,150,300,450,600,750)]:
        a,g=geometry(r['object_id']),geometry(r['reference_object_id'])
        delta=max(float(np.max(np.abs(np.asarray(x[k])-np.asarray(frozen['geometries'][oid][k]))))
                  for oid,x in [(r['object_id'],a),(r['reference_object_id'],g)] for k in ('bottom3d','top3d'))
        result=evaluate_geometry(a,g,e)
        errors={k:abs(result['metrics'][k]-r['metrics'][k]) for k in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')}
        expected_iou=r['legacy_metrics'].get('iou_3d_corner_mean')
        if expected_iou is not None:errors['iou_3d_corner_mean']=abs(result['metrics']['iou_3d_corner_mean']-expected_iou)
        assert delta<1e-10 and max(errors.values())<1e-8,(r['id'],delta,errors)
        parity.append(dict(record_id=r['id'],geometry_max_abs_difference=delta,metric_abs_differences=errors))
    OUT.mkdir(exist_ok=True,parents=True)
    parity_info=dict(records=parity,seconds=time.perf_counter()-started,passed=True)
    (OUT/'PARITY.json').write_text(json.dumps(parity_info,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(parity_seconds=parity_info['seconds'],passed=True)),flush=True)
    if parity_only:return
    coverage=read(ROOT/'research/quality_reference_coverage_20261013/COVERAGE.json')['records']
    routes={r['record_id']:r for r in read(ARCHIVE/'routing/results/routes.json')['rows']}
    targets=[r for r in coverage if r['action'] in ('compute_single_existing_reference_conditionally','compute_each_existing_reference_separately')]
    assert len(targets)==749 and sum(len(r['reusable_reference_ids']) for r in targets)==899
    output=[]
    for r in targets:
        live=current[r['record_id']]
        scene_only=bool(live['context_barriers']) and all(x.startswith('special_scene_separate_from_calibration:') for x in live['context_barriers'])
        assert not live['personnel_barriers'] and not live['original_holdout'] and (
            live['role']=='manual_development_candidate' and not live['context_barriers'] or scene_only),r['record_id']
        for ref in r['existing_references']:
            if ref['object_id'] not in r['reusable_reference_ids']:continue
            assert not ref['restrictions']
            try:result=evaluate_geometry(geometry(r['object_id']),geometry(ref['object_id']),e)
            except ValueError as exc:result=dict(status='unavailable',reason_codes=[str(exc)],metrics=None,candidate_components=None)
            output.append(dict(record_id=r['record_id'],object_id=r['object_id'],image_id=r['image_id'],image_code=r['image_code'],
                building_id=r['building_id'],worker_id=live['worker_id'],condition='manual',reference_object_id=ref['object_id'],reference_version=ref['version'],
                current_role=live['role'],current_context_barriers=live['context_barriers'],
                scope_record=r['scope_record'],original_holdout=live['original_holdout'],exposure=live['exposure'],
                processed_input='current_loader.points_1024x512; fixed_existing_order; no new pairing or point edits',
                reference_semantics='existing_original_or_revision_full_geometry_conditional; not confirmed_multispace_floor',
                reference_role='existing_reference_sensitivity_not_main_assignment',
                existing_route={k:routes[r['record_id']].get(k) for k in ('selected_candidate_id','selected_full_status','route_reason','manual_directive_applied','manual_family_applied')} if r['record_id'] in routes else None,
                candidate_reference_selected=False,formal_eligibility_newly_granted=False,new_independent_calibration_authorization=False,
                **result))
        if len(output)%100<2:print('processed pairs: '+str(len(output)),flush=True)
    grouped=defaultdict(list)
    for r in output:grouped[r['record_id']].append(r)
    summary=dict(records=len(grouped),pairs=len(output),images=len({r['image_id'] for r in output}),
        buildings=len({r['building_id'] for r in output}),statuses=dict(Counter(r['status'] for r in output)),
        null_iou3d=sum(r['metrics'] is None or r['metrics']['iou_3d_corner_mean'] is None for r in output),
        seconds=time.perf_counter()-started,geometry_objects_cached=len(geometries),
        dual_reference_records=sum(len(v)==2 for v in grouped.values()),no_reference_selected=True)
    summary['current_scene_separated_records']=len({r['record_id'] for r in output if r['current_role']=='held_or_diagnostic'})
    summary['current_ordinary_extension_records']=len({r['record_id'] for r in output if r['current_role']=='manual_development_candidate'})
    complete=[r for r in output if r['status']=='complete']
    deltas={name:np.asarray([r['candidate_components'][name]['score']-r['candidate_components'][NAMES[0]]['score'] for r in complete]) for name in NAMES[1:]}
    summary['pair_level_candidate_deltas_vs_baseline']={name:dict(min=float(v.min()),median=float(np.median(v)),max=float(v.max()),
        increase_ge5=int(sum(v>=5)),decrease_ge5=int(sum(v<=-5)),unit='annotation_reference_pair_not_independent_record') for name,v in deltas.items()}
    summary['scope_status_pair_counts']=dict(Counter(r['scope_record']['oos_status'] for r in output))
    result=dict(schema='quality_manual_conditional_expansion_20261013_v1',summary=summary,parity=parity_info,
        metric_samples=dict(spherical=2048,height=4096),candidate_names=list(NAMES),records=output,
        geometries=geometries,processed_points={oid:objects[oid]['points_1024x512'] for oid in geometries},
        source_pairing_and_order={oid:{k:objects[oid][k] for k in ('links_zero_based','ordered_source_point_indices')} for oid in geometries})
    (OUT/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parity-only',action='store_true')
    main(parser.parse_args().parity_only)
