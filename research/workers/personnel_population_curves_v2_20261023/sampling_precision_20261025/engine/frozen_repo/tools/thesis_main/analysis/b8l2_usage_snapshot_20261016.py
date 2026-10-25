"""固定v6输入的新用途快照：门洞实测，OOS指数仅诊断，全库存计算状态分轴。"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

from .b8l2_calculation_status_20261016 import inspect_geometry
from .b8l2_shared_descriptive_20261016 import add_b8l2_descriptive_tables
from .b8l2_shared_snapshot_20261016 import member_changes,read_json
from .b8l2_usage_coverage_20261016 import scene_flags,build_usage_coverage
from .descriptive_statistics_current_20261015 import ROOT,QUALITY_METRICS,rebuild_metric_tables,write
from .scope_quality_scoring_20261016 import scoring_engine,score_task

SOURCE=ROOT/'research/statistics/b8l2_shared_v6_20261016'
OUT=ROOT/'research/statistics/b8l2_usage_v6_20261016'
VERSION='b8l2_scene_usage_v6_20261016_v2'
INPUT_VERSION='b8l2_shared_v6_20261016_v1'
HOLD_FIELDS=('same_target_quality_hold','latest_step_reference_pending','original_holdout','same_target_unconfirmed')


def usage_policy(row,obj,binding,reference,geometry,scene,*,full_score_state):
    """用途门不当作计算失败；仅明确的门洞场景blanket可解除。"""
    reasons=[]; bypass=[]
    gate=obj['main_quality_gate'];gate_reasons=gate['reasons']
    unconfirmed_door=scene['is_doorway'] and gate['status']=='hold_scene_or_reference' and gate_reasons==['unconfirmed']
    full_ref=bool(reference and reference['full_reference_available'])
    scene_only=(scene['is_doorway'] and ((gate['status']=='out_of_primary_scene' and gate_reasons==['doorway_difficult']) or
        (gate['status']=='hold_scene_or_reference' and gate_reasons==['doorway_annotatable'])))
    blanket_uncertified=(scene_only and bool(binding['chosen_target_id']) and full_ref and row.get('stage')=='doorway'
        and row.get('same_target_quality_hold') not in (True,'True'))
    target_holds=[key for key in HOLD_FIELDS if row.get(key) in (True,'True')
                  and not (key=='same_target_unconfirmed' and blanket_uncertified)]
    unique=bool(binding['chosen_target_id']) and not unconfirmed_door and not target_holds
    if scene_only:bypass.append('old_doorway_scene_blanket')
    if obj['cleaning_disposition']!='retained':reasons.append('cleaning:'+obj['cleaning_disposition'])
    if not obj['independent_vote_eligible']:reasons.append('independent_response_ineligible')
    if not row['pool_analysis_eligible']:reasons.extend(row['pool_analysis_exclusion_reasons'])
    if gate['status']!='candidate_pending_geometry' and not scene_only:
        reasons.append('main_quality_gate:'+gate['status'])
    if obj['worker_quality_gate'] not in ('candidate_pending_geometry',gate['status']):
        reasons.append('worker_quality_gate:'+obj['worker_quality_gate'])
    if not unique:reasons.append('space_binding_not_unique')
    if not full_ref:reasons.append('reference_not_full')
    if not geometry['full_input_available']:reasons.append('full_input_unavailable')
    if reference and not reference['current_target']:reasons.append('bound_other_admitted_space')
    if row.get('difficulty_analysis_exclusion')=='user_reported_issue_pending':reasons.append('current_image_issue_pending')
    for key in HOLD_FIELDS:
        if row.get(key) not in (True,'True'):continue
        if key=='same_target_unconfirmed' and blanket_uncertified:
            bypass.append('old_doorway_same_target_not_certified_blanket')
        else:reasons.append('legacy:'+key)
    if scene['is_oos']:reasons.append('oos_diagnostic_only')
    if full_score_state!='computed':reasons.append('full_score:'+full_score_state)
    return dict(quality_usable=not reasons,quality_exclusion_reasons=sorted(set(reasons)),
                purpose_bypass=bypass,target_binding_unique=unique)


def run(out=OUT,source=SOURCE):
    out,source=Path(out),Path(source)
    if out.resolve()==source.resolve():raise ValueError('usage output must not overwrite historical shared snapshot')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'CHECKS.json').exists() and read_json(out/'CHECKS.json').get('snapshot_version')!=VERSION:
        raise ValueError('existing output has different version')
    fixed=read_json(source/'FROZEN_INPUTS.json');assert fixed['version']==INPUT_VERSION
    tables={name:pd.DataFrame(rows) for name,rows in read_json(source/'tables.json').items()}
    previous=tables['quality_records'].copy(); audit=tables['shared_records'].copy()
    objects={o['object_id']:o for o in fixed['bundle']['data']['objects'] if o['object_kind']=='annotation'}
    refs={r['target_id']:r for r in read_json(source/'inputs/reference_catalog.json')}
    binding=read_json(source/'inputs/binding_all.json');bindings={r['object_id']:r for r in binding['affected_records']}
    assert set(audit.object_id)==set(objects)==set(bindings)
    audit['previous_usage_quality_eligible']=audit.current_quality_eligible
    audit['previous_usage_B8L2']=audit.B8L2
    audit[QUALITY_METRICS]=np.nan
    audit['current_quality_eligible']=False
    for metric in QUALITY_METRICS:audit['diagnostic_'+metric]=np.nan
    audit['diagnostic_floor_iou']=np.nan
    for name in ['input_geometry_status','full_score_state','calculation_status','quality_use','purpose_bypass']:
        audit[name]=''
    for name in ['input_geometry_reasons','measurement_reasons','quality_exclusion_reasons']:
        audit[name]=[[] for _ in range(len(audit))]
    for name in ['full_input_available','floor_input_available','reference_full_available','target_binding_unique',
                 'is_doorway','is_oos','quality_usable']:audit[name]=False
    audit['input_version']=INPUT_VERSION;audit['snapshot_version']=VERSION;audit['usage_version']=VERSION
    audit=audit.set_index('object_id',drop=False)
    scores=[]; geometry_rows=[]
    with scoring_engine(source/'inputs/measurement_engine.zip',source/'inputs/working_models.py') as (engine,models):
        parameters=vars(models.MODELS['B8L2']);assert parameters['version']=='WQ-B8L2-20261015'
        (out/'MODEL_PARAMETERS.json').write_text(json.dumps(parameters,ensure_ascii=False,indent=2),encoding='utf-8')
        for index,(oid,row) in enumerate(audit.iterrows()):
            obj=objects[oid];choice=bindings[oid];ref=refs.get(choice['chosen_target_id'])
            scene=scene_flags(row);geometry=inspect_geometry(obj,engine);geometry_rows.append(geometry)
            initial=usage_policy(row,obj,choice,ref,geometry,scene,full_score_state='not_run')
            unique=initial['target_binding_unique']; full_ref=bool(ref and ref['full_reference_available'])
            state=('pending_target' if not unique else 'input_uncomputable' if not geometry['full_input_available'] else
                   'pending_reference' if not full_ref else 'not_run')
            score=None; measurement_reasons=[]
            if state=='not_run':
                score=score_task(dict(object_id=oid,image_id=row.image_id,worker_id=row.worker_id,condition=row.condition,
                    current_target_id=ref['target_id'],reference_version=ref['reference_version'],
                    annotation_points=obj['points_1024x512'],reference_points=ref['points_1024x512']),engine,models)
                state='computed' if score['score_status']=='complete' else 'measurement_failed'
                measurement_reasons=score['reasons']
                scores.append(dict(score,input_version=INPUT_VERSION,usage_version=VERSION,
                                   values_are_diagnostic_until_quality_policy_passes=True))
            calculation='full_computed' if state=='computed' else state
            floor_iou=None
            if state=='computed':floor_iou=score['iou_2d']
            elif unique and geometry['floor_input_available'] and ref:
                reference_floor=engine.valid.validate_footprint(ref['floor_xz_h'],role='reference')
                if reference_floor['available']:
                    a,b=Polygon(geometry['floor_xz_h']),Polygon(ref['floor_xz_h'])
                    floor_iou=a.intersection(b).area/a.union(b).area
                    calculation='floor_only_computed'
            policy=usage_policy(row,obj,choice,ref,geometry,scene,full_score_state=state)
            for key,value in dict(scene,**policy,input_geometry_status=geometry['input_geometry_status'],
                full_input_available=geometry['full_input_available'],floor_input_available=geometry['floor_input_available'],
                reference_full_available=full_ref,full_score_state=state,calculation_status=calculation,
                input_geometry_reasons=geometry['reasons'],measurement_reasons=measurement_reasons).items():
                if key not in audit:audit[key]=None
                audit.at[oid,key]=value
            audit.at[oid,'purpose_bypass']=policy['purpose_bypass']
            audit.at[oid,'diagnostic_floor_iou']=floor_iou
            audit.at[oid,'rescore_target_id']=choice['chosen_target_id']
            audit.at[oid,'rescore_status']='complete' if state=='computed' else state
            if ref:
                audit.at[oid,'reference_id']=ref['target_id'];audit.at[oid,'reference_version']=ref['reference_version']
                audit.at[oid,'rescore_reference_version']=ref['reference_version']
            if state=='computed':
                for metric in QUALITY_METRICS:
                    audit.at[oid,'diagnostic_'+metric]=score[metric]
                    if policy['quality_usable']:audit.at[oid,metric]=score[metric]
                audit.at[oid,'score_version']=json.dumps(score['score_versions'],ensure_ascii=False)
            audit.at[oid,'current_quality_eligible']=policy['quality_usable']
            audit.at[oid,'quality_use']=('oos_diagnostic_only' if scene['is_oos'] else 'doorway_quality' if policy['quality_usable'] and scene['is_doorway'] else
                'ordinary_primary' if policy['quality_usable'] and row.ordinary_difficulty_eligible else
                'special_conditional_only' if policy['quality_usable'] else 'not_qualified')
            if (index+1)%200==0:print(f'usage geometry/measurement {index+1}/{len(audit)}',flush=True)
    audit=audit.reset_index(drop=True)
    assert not (audit.is_oos & audit.quality_usable).any()
    assert audit.loc[~audit.quality_usable,QUALITY_METRICS].isna().all().all()
    coverage=build_usage_coverage(audit)
    audit=coverage['record_reason_audit'];tables.update(coverage)
    newbindings=pd.DataFrame(binding['affected_records'])
    newbindings['nominal_chosen_target_id']=newbindings.chosen_target_id
    newbindings['target_binding_unique']=newbindings.object_id.map(audit.set_index('object_id').target_binding_unique)
    newbindings.loc[~newbindings.target_binding_unique,'chosen_target_id']=''
    newbindings=newbindings.rename(columns={'person_quality_restriction_clear':'historical_person_quality_restriction_clear'})
    tables['shared_bindings']=newbindings
    tables.update(record_audit=audit,shared_records=audit.copy(),previous_quality_records=previous,
        member_changes=member_changes(audit,previous),calculation_ledger=audit.copy(),
        input_geometry_audit=pd.DataFrame(geometry_rows),rescore_comparisons=pd.DataFrame(scores))
    rebuild_metric_tables(tables,bundle=fixed['bundle']);add_b8l2_descriptive_tables(tables)
    historical_checks=read_json(source/'CHECKS.json')
    checks={key:historical_checks[key] for key in ['difficulty_version','source_pool_rule','inventory_rows','inventory_images']}
    checks['historical_snapshot_checks']=historical_checks
    checks.update(snapshot_version=VERSION,usage_version=VERSION,input_version=INPUT_VERSION,
        previous_quality_rows=len(previous),quality_rows=len(tables['quality_records']),
        new_scores_computed=True,score_tasks=len(scores),complete_scores=int(audit.full_score_state.eq('computed').sum()),
        calculation_counts=audit.calculation_status.value_counts().to_dict(),
        input_geometry_counts=audit.input_geometry_status.value_counts().to_dict(),
        quality_use_counts=audit.quality_use.value_counts().to_dict(),membership_changes=tables['member_changes'].membership_change.value_counts().to_dict(),
        analysis_rows=len(tables['analysis_records']),pending_rescore_rows=int(audit.full_score_state.isin(['pending_target','pending_reference']).sum()),
        source_time_rows=int(audit.active_time_seconds.notna().sum()),target_matched_time_rows=int(audit.target_matched_time_seconds.notna().sum()),
        old_snapshot_unchanged=True,OOS_quality_rows=0,source_snapshot=source.relative_to(ROOT).as_posix())
    tables['member_changes']['membership_change']=tables['member_changes'].membership_change.replace('added_new_score_coverage','new_usage_admission')
    checks['membership_changes']=tables['member_changes'].membership_change.value_counts().to_dict()
    tables['affected_records']=tables['affected_records'].drop(columns=['current_quality_eligible'],errors='ignore').merge(
        audit[['object_id','current_quality_eligible','quality_usable','calculation_status','full_score_state']],on='object_id',validate='one_to_one')
    tables['affected_records']=tables['affected_records'].rename(columns={
        'person_quality_restriction_clear':'historical_person_quality_restriction_clear','score_status':'historical_score_status'})
    tables['pending_rescore']=audit[audit.full_score_state.isin(['pending_target','pending_reference'])]
    tables['remaining_gaps']=audit[~audit.quality_usable][['object_id','image_id','image_code','worker_id','condition',
        'quality_exclusion_reasons','calculation_status','full_score_state']].copy()
    write(tables,checks,out)
    contract=read_json(out/'FIELD_CONTRACT.json')
    contract.pop('difficulty_pointer',None)
    contract.update(version=VERSION,input_version=INPUT_VERSION,usage_version=VERSION,
        input_freeze=(source/'FROZEN_INPUTS.json').relative_to(ROOT).as_posix(),
        difficulty_source=(source/'FROZEN_INPUTS.json').relative_to(ROOT).as_posix()+'#/difficulty',
        historical_pointer_at_freeze=fixed['difficulty_pointer'],
        quality_eligibility='current unique full reference + unchanged computable input + cleaning/independent/pool/GT/specific holds clear; OOS never quality',
        quality_metrics='normal Q/WQ/A10/B8L2/IoU fields are masked unless quality_usable; diagnostic_* never quality summaries',
        calculation_axes='input_geometry_status, full_score_state and calculation_status independent; floor diagnostic does not complete full score',
        purpose_bypass='only declared doorway scene blanket and audited old conditional_full source flag (records.stage=doorway); specific holds retained',
        history='old shared1622 frozen, including OOS23; this usage snapshot removes diagnostic OOS from quality',
        raw_measurements='rescore_comparisons includes computed diagnostic values for excluded/OOS objects; never use it as qualified_scores',
        time='source and preexisting audited target time retained independently of quality use; scoring never creates target time')
    (out/'FIELD_CONTRACT.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    cross=read_json(source/'CROSS_MODULE_INPUTS.json')
    cross['historical_shared_delivery']=dict(path=(source/'CROSS_MODULE_INPUTS.json').relative_to(ROOT).as_posix(),
                                           version=INPUT_VERSION,quality_rows=len(previous))
    for key in ['measured_values','changes','all_pre_score_bindings','source_pools','image_status','direct_room_relations']:
        filename={'measured_values':'rescore_comparisons.csv','changes':'member_changes.csv',
                  'all_pre_score_bindings':'shared_bindings.csv','source_pools':'source_pools.csv',
                  'image_status':'current_images.csv','direct_room_relations':'same_room_relations.csv'}[key]
        cross[key]=(out/filename).relative_to(ROOT).as_posix()
    cross['rules']['applicability']='OOS all GT-based indices diagnostic only, never quality; doorway explicit full-reference and real geometry required'
    cross['rules']['image_holds']='cleaning/independent/source-pool/GT/specific holds remain; declared doorway scene blanket is purpose-bypassed only'
    cross['rules']['time']='source and audited target times independent of quality use; no new target times by scoring'
    cross.update(version=VERSION,usage_version=VERSION,input_version=INPUT_VERSION,input_freeze=(source/'FROZEN_INPUTS.json').relative_to(ROOT).as_posix(),
        recommended_qualified_scores=(out/'quality_records.csv').relative_to(ROOT).as_posix(),
        full_inventory_with_metric_eligibility=(out/'shared_records.csv').relative_to(ROOT).as_posix(),
        fields=(out/'FIELD_CONTRACT.json').relative_to(ROOT).as_posix(),counts=checks,
        usage_rule='OOS all GT-based indices diagnostic only; doorway full reference and real geometry measured; normal columns gated by quality_usable',
        calculation_ledger=(out/'calculation_ledger.csv').relative_to(ROOT).as_posix())
    (out/'CROSS_MODULE_INPUTS.json').write_text(json.dumps(cross,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2),flush=True)
    return tables,checks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,default=OUT)
    args=parser.parse_args();run(args.out)
