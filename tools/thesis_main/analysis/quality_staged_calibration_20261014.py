"""普通粗调 -> 明确冻结 -> 门洞细调 -> 普通回归；只复用冻结研究评分接口。"""
from collections import Counter, defaultdict
import json
import numpy as np

from tools.thesis_main.analysis.quality_manual_expansion_20261013 import ROOT, ARCHIVE, PACKAGE, engine, read, evaluate_geometry
from tools.thesis_main.analysis.quality_height_calibration_ready_20261013 import evidence

OUT=ROOT/'research/quality/quality_staged_calibration_20261014'
PREP=ROOT/'research/quality_calibration_preparation_20261013'


def dump(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def candidates(e):
    main=e['configs']['J_main_hill_tail12_g1_l025']
    configs=dict(current_tail=main, hill_same_height=dict(main,family='hill'),
                hill_global08=dict(main,family='hill',global_scale=.8),
                simple_power8=e['configs']['J_simple_power8_g1_l025'],
                no_direction_diagnostic=dict(main,direction_disabled=True))
    return {name:dict(config,name=name) for name,config in configs.items()}


def score(rows,configs,e):
    return {r['record_id']:{n:e['score'].score_metrics(r['metrics'],c) for n,c in configs.items()} for r in rows}


def descriptive(values,rows,base):
    delta=np.array(values)-np.array(base)
    out=dict(min_delta=float(delta.min()),median_delta=float(np.median(delta)),max_delta=float(delta.max()))
    for field in ('image_id','building_id'):
        bins=defaultdict(list)
        for r,d in zip(rows,delta): bins[r[field]].append(float(d))
        means={k:float(np.mean(v)) for k,v in bins.items()}
        out[field]=dict(equal_group_mean=float(np.mean(list(means.values()))),per_group_mean=means)
    return out


def coarse():
    design=read(OUT/'DESIGN.json'); e=engine();configs=candidates(e)
    assert set(configs)==set(design['coarse_candidates'])
    baseline=read(PREP/'BASELINE.json')['rows']; ordinary=[r for r in baseline if r['use']=='ordinary_development']
    severe=[r for r in baseline if r['use']=='separate_severe_constraint']
    assert len(ordinary)==574 and len(severe)==9
    primary=read(ROOT/'research/quality_data_admission_audit_20261013/MANUAL_PRIMARY_SEARCH_INPUTS.json')
    values=score(baseline,configs,e); byid={r['record_id']:r for r in baseline}
    legacy={r['id']:r for r in read(PACKAGE/'inputs/calibration_records.json')['rows']}
    iou={}
    for r in baseline:
        old=legacy[r['record_id']]
        assert old['reference_object_id']==r['reference_object_id']
        iou[r['record_id']]=old['legacy_metrics'].get('iou_3d_corner_mean')
    controls=[]
    for source in ('quality_calibration_preparation_20261013/BOTTOM_CONTROLS.json','quality_height_calibration_ready_20261013/CONTROLS.json'):
        d=read(ROOT/'research'/source)
        for r in d.get('rows',d.get('records',[])):
            if r.get('metrics') is not None:
                controls.append(dict(record_id=source.split('/')[0]+':'+r['case_id'], source=source,metrics=r['metrics']))
    for angle in design['rhombus_angles']:
        u=np.array([1.,0]);v=np.array([np.cos(np.radians(angle)),np.sin(np.radians(angle))])
        p=np.array([(-u-v)/2,(u-v)/2,(u+v)/2,(-u+v)/2])
        ref=np.array([[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]])
        def geo(p):return dict(bottom3d=np.c_[p[:,0],-np.ones(4),p[:,1]].tolist(),top3d=np.c_[p[:,0],np.full(4,1.6),p[:,1]].tolist())
        result=evaluate_geometry(geo(p),geo(ref),dict(e,configs={'current':configs['current_tail']}))
        assert result['status']=='complete'
        controls.append(dict(record_id=f'rhombus:{angle}',source='new_complete_rhombus_RMS',angle=angle,metrics=result['metrics']))
    control_scores=score(controls,configs,e)
    historical_ids={'R00397','R00418','R01609','R02297','R01810','R01385','R01033','R01022','R02447','R01973'}
    frozen=read(ARCHIVE/'calibration/inputs/search_inputs.json')['rows']
    history=[dict(record_id=r['id'],metrics=r['metrics']) for r in frozen if r['id'] in historical_ids]
    assert len(history)==len(historical_ids)
    hs=score(history,configs,e)
    summary={}
    for n in configs:
        q=np.array([values[r['id']][n]['score'] for r in primary['rows']])
        b=[values[r['id']]['current_tail']['score'] for r in primary['rows']]
        sr=[values[r['record_id']][n]['score'] for r in severe]
        sequence=[control_scores['rhombus:'+str(a)][n]['score'] for a in design['rhombus_angles']]
        bottom_pair=[[control_scores[f'quality_calibration_preparation_20261013:1x4:distributed_bottom:{sign}:{amp}'][n]['score'] for amp in (8,16)] for sign in (-1,1)]
        summary[n]=dict(evidence=evidence(primary,q),ordinary=descriptive(q,primary['rows'],b),
            severe_scores=sr,severe_min=min(sr),severe_max=max(sr),
            J04=values['R03274'][n],J01=[values[x][n]['score'] for x in ('R03346','R03347')],
            rhombus_scores=sequence,rhombus_reversals=int(sum(np.diff(sequence)>1e-8)),
            bottom_counterexample_scores=bottom_pair,
            T20=hs['R00397'][n],P04_height_losses=[hs[x][n]['height_loss'] for x in ('R00397','R00418')],
            L01_gap=hs['R02297'][n]['score']-hs['R01609'][n]['score'])
    assert max(abs(values[r['record_id']]['current_tail']['score']-r['components']['score']) for r in baseline)<1e-10
    dump('COARSE.json',dict(schema='quality_coarse_comparison_v1',configs=configs,summary=summary,records=values,
                           current_iou3d=iou,iou3d_source='existing_frozen_same_reference_metrics_not_new_full_geometry',
                           controls=controls,control_scores=control_scores,historical_scores=hs,
                           ordinary_ids=[r['record_id'] for r in ordinary],severe_ids=[r['record_id'] for r in severe],
                           working_version_selected=False))
    print(json.dumps({n:{k:v for k,v in s.items() if k!='ordinary' and k!='evidence'}|{'weak_inversions':s['evidence']['weak_grade_inversions'],'P01':s['evidence']['explicit_overall']} for n,s in summary.items()},ensure_ascii=False))


def doorway_reference(r):
    """第二阶段只解除场景隔离，不解除人员、留出或参考暂缓。"""
    reasons=[]
    if r['condition']!='manual':reasons.append('not_manual')
    if r['original_holdout']:reasons.append('original_holdout')
    reasons += [x for x in r['personnel_barriers'] if x!='formal_gate:out_of_primary_scene']
    reasons += [x for x in r['context_barriers'] if not x.startswith('special_scene_separate_from_calibration:doorway_')]
    versions=r['available_reference_versions']
    if len(versions)!=1:reasons.append('reference_binding_unresolved')
    else:
        version,ref=next(iter(versions.items()))
        reasons += ['reference:'+x for x in ref['restrictions']]
    return (None if reasons else dict(version=version,**ref)),list(dict.fromkeys(reasons))


def doorway():
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    freeze=read(OUT/'WORKING_COARSE.json');e=engine();c=freeze['config']
    configs=dict(center=c,global_minus=dict(c,global_scale=c['global_scale']-.05),
                 global_plus=dict(c,global_scale=c['global_scale']+.05),
                 local_minus=dict(c,local_scale=c['local_scale']-.025),
                 local_plus=dict(c,local_scale=c['local_scale']+.025))
    configs={name:dict(config,name=name) for name,config in configs.items()}
    stages=read(ROOT/'research/quality_scope_resolution_20261013/STAGE_LEDGER.json')['records']
    ids={r['record_id'] for r in stages if r['stage']=='doorway_second_stage_review_before_small_adjustment'}
    admissions=read(ROOT/'research/quality_data_admission_audit_20261013/FULL_ADMISSION.json')['records']
    objects={o['object_id']:o for o in load_current_bundle()['data']['objects']};cache={}
    def geometry(oid):
        if oid not in cache:
            obj=objects[oid]
            if obj['geometry']['status']!='surface_valid' or not obj['links_zero_based']:
                raise ValueError('current_processed_geometry_unavailable:'+oid)
            cache[oid]=e['geometry'](obj['points_1024x512'])
        return cache[oid]
    rows=[]
    for r in admissions:
        if r['record_id'] not in ids:continue
        ref,reasons=doorway_reference(r)
        out=dict(record_id=r['record_id'],image_code=r['image_code'],image_id=r['image_id'],
                 object_id=r['object_id'],worker_id=r['worker_id'],scene=r['current_scene_review'],
                 original_holdout=r['original_holdout'],exposure=r['exposure'],
                 personnel_barriers=r['personnel_barriers'],context_barriers=r['context_barriers'],
                 available_reference_versions=r['available_reference_versions'],reference=ref,
                 status='held',reason_codes=reasons,metrics=None,candidate_components=None,
                 formal_eligibility_newly_granted=False)
        if ref is not None:
            try:
                result=evaluate_geometry(geometry(r['object_id']),geometry(ref['object_id']),dict(e,configs=configs))
            except ValueError as exc:
                result=dict(status='unavailable',reason_codes=[str(exc)],metrics=None,candidate_components=None)
            out.update(result)
        rows.append(out)
    assert len(rows)==len(ids)==217
    grouped=defaultdict(list)
    for r in rows:grouped[r['image_code']].append(r)
    images=[]
    for code,rs in sorted(grouped.items()):
        valid=[r for r in rs if r['status']=='complete']
        summary={}
        for name in configs:
            qs=[r['candidate_components'][name]['score'] for r in valid]
            ds=[r['candidate_components'][name]['score']-r['candidate_components']['center']['score'] for r in valid]
            summary[name]=dict(n=len(qs),median=float(np.median(qs)) if qs else None,
                min=min(qs) if qs else None,max=max(qs) if qs else None,
                mean_delta=float(np.mean(ds)) if ds else None)
        images.append(dict(image_code=code,n=len(rs),statuses=dict(Counter(r['status'] for r in rs)),
            hold_reasons=dict(Counter(x for r in rs for x in r['reason_codes'])),scores=summary))
    coarse_result=read(OUT/'COARSE.json')
    baseline=read(PREP/'BASELINE.json')['rows']
    regression=score(baseline,configs,e)
    assert max(abs(regression[r['record_id']]['center']['score']-coarse_result['records'][r['record_id']][freeze['candidate']]['score']) for r in baseline)<1e-10
    controls=score(coarse_result['controls'],configs,e)
    primary=read(ROOT/'research/quality_data_admission_audit_20261013/MANUAL_PRIMARY_SEARCH_INPUTS.json')
    history_metrics=[dict(record_id=r['id'],metrics=r['metrics']) for r in read(ARCHIVE/'calibration/inputs/search_inputs.json')['rows'] if r['id'] in coarse_result['historical_scores']]
    history=score(history_metrics,configs,e)
    checks={}
    for name in configs:
        checks[name]=dict(evidence=evidence(primary,np.array([regression[r['id']][name]['score'] for r in primary['rows']])),
            severe_scores={rid:regression[rid][name]['score'] for rid in coarse_result['severe_ids']},
            P04_height_losses=[history[rid][name]['height_loss'] for rid in ('R00397','R00418')],
            T20=history['R00397'][name],
            L01_gap=history['R02297'][name]['score']-history['R01609'][name]['score'])
    dump('DOORWAY.json',dict(schema='quality_doorway_fine_v1',configs=configs,rows=rows,images=images,
        statuses=dict(Counter(r['status'] for r in rows)),selected='center',
        decision='保留粗调中心：本批没有足以识别微调收益的门洞质量比较标签；分布较低不作为优化目标。多参考未绑定及额外暂缓维持held。'))
    dump('REGRESSION.json',dict(schema='quality_staged_regression_v1',records=regression,controls=controls,
        historical_scores=history,checks=checks,center_equals_frozen_coarse=True,
        ordinary_n=574,severe_separate_n=9,control_n=len(controls),selected='center'))
    dump('WORKING_FINAL.json',dict(schema='quality_staged_working_v1',candidate=freeze['candidate'],config=c,
        fine_selected='center',doorway_fine_parameter_change=False,formal_algorithm_changed=False,
        status='research_working_only',limitations=['门洞比较未提供独立人工标签，微调保持中心','J01绝对分数意见未解决','去尾项未修复方向指标对墙族坍缩的语义盲区']))
    print(json.dumps(dict(statuses=dict(Counter(r['status'] for r in rows)),images=len(images),regression_n=len(regression),control_n=len(controls)),ensure_ascii=False))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=('coarse','doorway'),default='coarse')
    (coarse if parser.parse_args().stage=='coarse' else doorway)()
