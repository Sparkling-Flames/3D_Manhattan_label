"""质量数据核查收尾：闭合全量分母、来源、几何复算及用途，不改原始资格。"""
from collections import Counter
import json

import numpy as np

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ROOT, ARCHIVE, read, engine, evaluate_geometry
from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle

OUT=ROOT/'research/quality_data_closeout_20261013'


def permitted_use(role,holdout,numeric_exists):
    if holdout or role=='held_or_diagnostic':
        return 'historical_diagnostic_only'
    if not numeric_exists:
        return 'explicitly_unavailable_no_score_imputed'
    return {'manual_development_candidate':'manual_conditional_comparison',
            'semi_secondary_candidate':'separate_semi_conditional_diagnostic',
            'severe_exception_candidate':'separate_reviewed_severe_diagnostic'}[role]


def audit_routes(objects,e):
    prepared=read(ARCHIVE/'routing/inputs/prepared_input.json')
    routes=read(ARCHIVE/'routing/results/routes.json')['rows']
    view={r['record_id']:r for r in read(ROOT/'research/quality_current_candidate_view_20261013/ROUTED_EXISTING_VIEW.json')['rows']}
    sources={r['record_id']:r for r in prepared['records']}
    candidates={c['candidate_id']:c for im in prepared['candidate_images'] for c in im['candidates']}
    fields=('before_preprocessing_points','preprocessed_points','points_1024x512','links_zero_based','ordered_source_point_indices')
    external=[];known_refs=0
    for im in prepared['candidate_images']:
        for c in im['candidates']:
            if not c['full_reference_available']:continue
            oid=c['reference_object_id']
            if oid in objects:
                assert c['points_1024x512']==objects[oid]['points_1024x512'],c['candidate_id']
                known_refs+=1
            else:
                assert not im['in_formal_corpus'] and not any(r['image_code']==im['image_code'] for r in routes)
                external.append(dict(candidate_id=c['candidate_id'],reason=im['reference_only_reason'],used_by_current_annotations=False))
    output=[];max_score_error=0.;max_geometry_error=0.;max_iou3d_error=0.;max_raw_error=0.
    for route in routes:
        rid=route['record_id'];source=sources[rid];obj=objects[route['object_id']]
        for k in fields:assert obj[k]==source['source_object'][k],(rid,k)
        if route['raw_input_diagnostics']['status']=='available':
            p=np.asarray(obj['before_preprocessing_points']);links=np.asarray(obj['links_zero_based'])
            delta=(p[links[:,0],0]-p[links[:,1],0]+512)%1024-512
            x=float(np.sqrt(np.mean(delta**2))*360/1024)
            error=abs(x-route['raw_input_diagnostics']['X_rms_deg'])
            assert error<1e-9,(rid,error)
            max_raw_error=max(max_raw_error,error)
        row=dict(record_id=rid,object_id=route['object_id'],source_fields_match=True,status=route['status'],
                 selected_candidate_id=route['selected_candidate_id'])
        if route['status']!='available':
            assert all(v is None for c in view[rid]['scores_under_selected_reference'].values() for v in c.values())
            row['unavailable_reason']=route['route_reason'];output.append(row);continue
        c=candidates[route['selected_candidate_id']]
        assert c['admitted_for_routing'] and not route['quality_or_height_used_for_route']
        a=e['geometry'](obj['points_1024x512'])
        delta=max(float(np.max(np.abs(np.asarray(a[k])-source['geometry'][k]))) for k in ('bottom3d','top3d'))
        assert delta<1e-10,(rid,delta)
        max_geometry_error=max(max_geometry_error,delta)
        floor=np.asarray(c['floor_xz_h']);ref_floor=np.column_stack((floor[:,0],-np.ones(len(floor)),floor[:,1]))
        gm=dict(bottom3d=ref_floor.tolist())
        if c['full_reference_available']:
            assert route['selected_full_status']=='available'
            gm=c['full_geometry'];result=evaluate_geometry(a,gm,e)
            assert result['status']=='complete',(rid,result)
            metrics=result['metrics']
            actual,previous=metrics['iou_3d_corner_mean'],route['IoU3D_selected']
            if actual is None or previous is None:assert actual is previous,rid
            else:
                error=abs(actual-previous);assert error<1e-8,(rid,error)
                max_iou3d_error=max(max_iou3d_error,error)
        else:
            assert route['selected_full_status']!='available'
            metrics=dict(iou_2d=e['au'].area_metrics(a,gm)['iou'],
                         S_bottom_deg=float(e['sp'].spherical_sym_distance(a['bottom3d'],ref_floor,2048)),
                         dir=float(e['au'].direction_residual(a,e['au'].direction_axis(a))),Hmean=None,Hcenter=None)
        scores={n:e['score'].score_metrics(metrics,cfg) for n,cfg in e['configs'].items()}
        errors=[]
        for n in e['configs']:
            for actual,expected in [('floor_score','floor'),('score','full')]:
                value=scores[n][actual]
                if n=='baseline_quad08':
                    previous=route['Q_floor_selected' if expected=='floor' else 'Q_full_selected']
                else:previous=view[rid]['scores_under_selected_reference'][n][expected]
                if value is None or previous is None:assert value is previous,(rid,n,expected)
                else:errors.append(abs(value-previous))
        assert max(errors)<1e-8,(rid,max(errors))
        max_score_error=max(max_score_error,max(errors))
        row.update(full_geometry_recomputed=c['full_reference_available'],floor_geometry_recomputed=True,
                   score_max_absolute_error=max(errors),metrics=metrics)
        output.append(row)
    for rid,rule in prepared['manual_overrides'].items():
        assert view[rid]['route']['selected_candidate_id']==rule['selected_candidate_id']
    for rid,rule in prepared['manual_family_directives'].items():
        assert view[rid]['route']['selected_candidate_id'] in rule['allowed_candidate_ids']
    return dict(records=output,summary=dict(source_records_checked=len(output),
        floor_geometry_recomputed=sum(r.get('floor_geometry_recomputed',False) for r in output),
        full_geometry_recomputed=sum(r.get('full_geometry_recomputed',False) for r in output),
        unavailable_retained=sum(r['status']!='available' for r in output),
        max_score_error=max_score_error,max_geometry_error=max_geometry_error,
        max_iou3d_error=max_iou3d_error,max_raw_X_error=max_raw_error,
        full_reference_snapshots_matched_current=known_refs,external_reference_only_snapshots=external,
        explicit_human_assignments_checked=len(prepared['manual_overrides']),family_restrictions_checked=len(prepared['manual_family_directives'])))


def main():
    bundle=load_current_bundle();objects={o['object_id']:o for o in bundle['data']['objects']}
    gate=read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')
    frozen={r['record_id']:r for r in read(ROOT/'research/quality_current_candidate_view_20261013/CANDIDATE_VIEW.json')['rows']}
    expanded=read(ROOT/'research/quality_manual_expansion_20261013/RESULTS.json')['records']
    expanded_ids={r['record_id'] for r in expanded}
    final=read(ROOT/'research/quality_candidate_disagreement_20261013/RESULTS.json')
    current={r['record_id']:r for r in final['records']}
    historical={r['record_id']:r for r in final['historical_fixed_reference_replay']}
    routed=read(ROOT/'research/quality_current_candidate_view_20261013/ROUTED_EXISTING_VIEW.json')['rows']
    routes={r['record_id']:r for r in routed}
    gaps=read(ROOT/'research/quality_downstream_audit_20261013/REFERENCE_GAP_AUDIT.json')['records']
    fusion_materialized_members={rid for r in gaps if r['scores'] is not None for rid in r['current_member_ids']}
    assert len(gate['records'])==3152 and len({r['object_id'] for r in gate['records']})==3152
    assert {r['object_id'] for r in gate['records']}=={o['object_id'] for o in objects.values() if o['object_kind']=='annotation'}
    ledger=[]
    for r in gate['records']:
        rid=r['record_id'];obj=objects[r['object_id']]
        for k,ok in [('image_id','image_id'),('worker_id','worker_id'),('condition','condition'),('current_personnel_gate','worker_quality_gate')]:
            assert r[k]==obj[ok],(rid,k)
        exists=rid in frozen or rid in expanded_ids or (rid in routes and routes[rid]['route']['status']=='available')
        if rid in current:
            materialized='current_'+current[rid]['score_kind']
        elif rid in historical:materialized='historical_fixed_reference_scope_confounded'
        elif rid in frozen:materialized='frozen_score_outside_current_manual_panel'
        elif exists:materialized='other_reference_conditioned_diagnostic'
        else:materialized='no_computable_score_in_authorized_views'
        raw=dict(status='unavailable_trusted_pairing_missing',X_rms_deg=None,Eperp_deg=None)
        if obj['preprocessing_status']=='ready':
            points=np.asarray(obj['before_preprocessing_points']);links=np.asarray(obj['links_zero_based'])
            delta=(points[links[:,0],0]-points[links[:,1],0]+512)%1024-512
            x=float(np.sqrt(np.mean(delta**2))*360/1024)
            raw=dict(status='available',X_rms_deg=x,Eperp_deg=x/2)
        ledger.append(dict(record_id=rid,object_id=r['object_id'],image_code=r['image_code'],worker_id=r['worker_id'],
            condition=r['condition'],source_cohort=r['source_cohort'],current_personnel_gate=r['current_personnel_gate'],
            role=r['role'],original_holdout=r['original_holdout'],exposure=r['exposure'],
            source_of_new_frozen_fusion_diagnostic=rid in fusion_materialized_members,
            unexposed_validation_certified=False,
            materialized_numeric_status=materialized,numeric_evidence_exists=exists,
            permitted_use=permitted_use(r['role'],r['original_holdout'],exists),
            personnel_barriers=r['personnel_barriers'],context_barriers=r['context_barriers'],
            historical_admission_numeric_barriers=r['numeric_barriers'],
            source_geometry_status=r['source_geometry_status'],raw_diagnostic=raw,
            raw_diagnostic_changes_score=False,formal_eligibility_newly_granted=False))
    assert sum(r['original_holdout'] for r in ledger)==282
    assert all(not r['original_holdout'] and r['condition']=='manual' and r['role']=='manual_development_candidate'
               for r in ledger if r['record_id'] in current or r['record_id'] in historical)
    for r in expanded:
        assert r['reference_role']=='existing_reference_sensitivity_not_main_assignment'
    search=read(ROOT/'research/quality_data_admission_audit_20261013/MANUAL_PRIMARY_SEARCH_INPUTS.json')
    assert len(search['rows'])==574 and len(search['grades'])==11 and len(search['constraints'])==5
    allowed=set(gate['primary_calibration_ids'])
    assert {r['id'] for r in search['rows']}==allowed
    assert all(set(c['record_ids'])<=allowed for c in search['constraints'])
    assert all(g['case_id'] not in ('T13','T22') for g in search['grades'])
    unbound=[r for r in bundle['comments']['occurrences'] if r['binding_status']=='unresolved']
    # 无对象的全局政策备注保留；不能伪造作答ID来消掉未绑定计数。
    assert len(unbound)==1 and unbound[0]['field']=='gt_blank_policy'
    route_checks=audit_routes(objects,engine())
    downstream=read(ROOT/'research/quality_downstream_audit_20261013/SUMMARY.json')
    height=read(ROOT/'research/quality_height_correspondence_20261013/SUMMARY.json')
    summary=dict(status='computable_data_checks_complete_with_explicit_semantic_and_source_limits',
        loader_validation=bundle['validation'],conditions=dict(Counter(r['condition'] for r in ledger)),
        source_cohorts=dict(Counter(r['source_cohort'] for r in ledger)),roles=dict(Counter(r['role'] for r in ledger)),
        materialized_numeric_status=dict(Counter(r['materialized_numeric_status'] for r in ledger)),
        permitted_use_counts=dict(Counter(r['permitted_use'] for r in ledger)),
        raw_diagnostic_status=dict(Counter(r['raw_diagnostic']['status'] for r in ledger)),
        original_holdout=282,filtered_old_grade_count=11,filtered_constraint_entries=5,
        original_holdout_members_in_new_frozen_fusion_diagnostics=sum(r['original_holdout'] and r['source_of_new_frozen_fusion_diagnostic'] for r in ledger),
        constraint_question_groups=dict(Counter(c['source_question_group'] for c in search['constraints'])),
        routing=route_checks['summary'],height=height,downstream=downstream,
        unresolved_global_comment=unbound[0],remaining_computable_checks=[],
        remaining_noncomputational_limits=['未确认顶面不制造完整分','范围或语义墙对应未决保留条件结果',
            '缺可信配对不自动修复排除人员作答','来源未核实semi不入manual校准',
            '缺真实融合逐人数序列不插值','未以弱开发标签宣称唯一参数或独立验证'])
    OUT.mkdir(parents=True,exist_ok=True)
    for filename,value in [('FINAL_LEDGER.json',dict(schema='quality_data_closeout_20261013_v1',records=ledger,
            policy='最新数值覆盖叠加在旧用途账本上；历史numeric_barriers不是当前缺算结论，数值存在不授予资格。')),
            ('ROUTE_REPLAY.json',route_checks),('SUMMARY.json',summary)]:
        (OUT/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('downstream','unresolved_global_comment')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
