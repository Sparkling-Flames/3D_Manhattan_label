"""接续已处理v1与新增真人作答，继承图级暂停；不生成质量分数。"""
import copy
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from .consolidate_research_input import load_current_bundle, validate_bundle
from .admit_annotation_batch_20261017 import _research_row, _summaries, _layout
from .intake_workers_v2_20261019 import OUT as INTAKE, read, write, table
from ..analysis.current_annotation_context_20261017 import load_scored_context
from ..analysis.descriptive_pool_gate_20261015 import load_image_review_decisions
from ..analysis.scope_quality_binding_20261016 import build_affected_records
from ..analysis.b8l2_usage_snapshot_20261016 import usage_policy
from ..analysis.b8l2_usage_coverage_20261016 import scene_flags

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/data/releases/v2/analysis_input'
BASE=ROOT/'research/data/processed_input_review_20261018/manifest.json'
REVISION='human_annotation_v2_20261019'
RECONFIRMED={
    'jtcxE69GiFV-05':'hold_reference_quality', 'jtcxE69GiFV-17':'hold_reference_quality',
    'wc2JMjhGNzB-14':'hold_reference_quality', 'zsNo4HB9uLZ-05':'hold_reference_quality',
    'pRbA3pwrgk9-12':'hold_reference_quality', 'uNb9QFRL6hY-32':'hold_main_analysis',
    'x8F5xyUWy9e-01':'hold_reference_quality', 'uNb9QFRL6hY-36':'hold_main_analysis',
    'pRbA3pwrgk9-16':'hold_all_analysis', 'uNb9QFRL6hY-51':'hold_reference_quality',
    'jtcxE69GiFV-11':'hold_all_analysis',
}
HOLDS=('hold_all_analysis','hold_main_analysis','hold_reference_quality')


def csv_table(path,rows):
    table(path,[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows])


def publish_release_pointer():
    # 仅在完整包已通过loader验证后发布；v1历史消费者固定读取自己的release。
    manifest=(OUT/'manifest.json').relative_to(ROOT).as_posix()
    release_path=OUT.parent/'RELEASE.json';release=read(release_path)
    release.update(status='analysis_input_admitted_scores_not_run',executable_analysis_manifest=manifest,
        analysis_status='v2 processed input, reference bindings and image holds admitted; scores/personnel/fusion not rerun.')
    write(release_path,release)
    write(OUT.parent.parent/'CURRENT.json',dict(data_release='v2',manifest=release_path.relative_to(ROOT).as_posix(),
        analysis_manifest=manifest,legacy_v1_analysis_manifest=BASE.relative_to(ROOT).as_posix(),
        policy='research/data/releases/VERSION_POLICY.md',analysis_status='input_admitted_scores_not_run',
        rule='Explicit release manifest required for analysis; historical v1 outputs and payload remain frozen.'))


def image_policy(im,d,objects,review):
    holds={o['main_quality_gate']['status'] for o in objects}&set(HOLDS)
    reasons=sorted('inherited:'+h for h in holds)
    code=im['image_code']
    if code in RECONFIRMED:
        holds.add(RECONFIRMED[code]);reasons.append('user_reconfirmed_20261019:'+RECONFIRMED[code])
    if d['gt_error_excluded'] or im.get('gt_substantive_error_mark'):
        holds.add('hold_reference_quality');reasons.append('existing_gt_error')
    if review.get('status')=='pending' or d['difficulty_analysis_exclusion']=='user_reported_issue_pending':
        holds.add('hold_main_analysis');reasons.append('existing_image_pending')
    scene=set(d['scene'].split(';'))
    oos=('confirmed' if 'oos' in scene or im.get('oos_status')=='confirmed' else
         'pending' if any('suspected' in s or 'pending' in s for s in scene) or im.get('oos_status')=='pending' else
         'not_oos' if d['oos_subtype']=='not_oos' else 'not_recorded')
    gate=next((h for h in HOLDS if h in holds),'out_of_primary_scene' if oos=='confirmed' else 'candidate_pending_geometry')
    consensus=gate if gate in HOLDS[:2] else 'main_candidate'
    if any(o['main_consensus_gate']['status']=='inner_space_only_reference_hold' for o in objects) and consensus=='main_candidate':
        consensus='inner_space_only_reference_hold'
    return dict(image_id=im['image_id'],image_code=code,quality_gate=gate,consensus_gate=consensus,
        oos_status=oos,oos_subtype=d['oos_subtype'],scene=d['scene'],reasons=reasons,
        user_list_11=code in RECONFIRMED,prior_image_review=review,
        inherited_hold_object_ids=[o['object_id'] for o in objects if o['main_quality_gate']['status'] in HOLDS],
        image_comment=im.get('image_comment',''))


def make_object(r,im,policy):
    excluded=r['disposition']=='excluded_by_user';oid=r['object_id']
    gate='excluded' if excluded else policy['quality_gate']
    consensus='excluded' if excluded else policy['consensus_gate']
    reasons=['user_excluded_record'] if excluded else policy['reasons'] or ['oos_diagnostic_only' if policy['oos_status']=='confirmed' else 'candidate_pending_geometry']
    source=dict(path='research/data/intake_W100_W134_20261019/received/'+
        ('excluded_label_studio_W100-W134.min.json' if excluded else 'annotations_label_studio_W100-W134.min.json'),
        project=None,task=None,annotation=r['annotation_id'],worker=r['worker_id'],source_account_id=None,source_id=oid)
    evidence=dict(verdict='user_excluded' if excluded else 'user_retained',current_comment='',current_decision_comment='',
        image_comment=policy['image_comment'],points_without_imputation=True,coverage_review={},annotation_traits={},
        source_confirmation='user_confirmed_new_human_processed_data_20261019')
    o=dict(object_id=oid,object_kind='annotation',image_id=r['image_id'],image_code=r['image_code'],worker_id=r['worker_id'],
        condition=r['condition'],source=source,original_export_points=None,
        before_preprocessing_points=r['before_preprocessing_points'],preprocessed_points=r['preprocessed_points'],
        links_zero_based=r['matterport_links_zero_based'],point_labels=[f'p{i+1}' for i in range(len(r['before_preprocessing_points']))],
        preprocessing=r['preprocessing'],preprocessing_status=r['preprocessing_status'],preprocessing_blockers=r['preprocessing_blockers'],
        pairing_basis='user_supplied_processed_pair_indices',building_id=im['building_id'],room_id=im.get('room_id',''),
        cleaning_disposition='excluded_by_review' if excluded else 'retained',worker_quality_gate=gate,consensus_group=consensus,
        independent_vote_eligible=not excluded,independent_vote_reasons=['user_excluded_record'] if excluded else [],
        canonical_unit=[r['worker_id'],r['image_id'],r['condition']],person_image_unit=[r['worker_id'],r['image_id']],
        borrowed_point_provenance=[],scene_category=policy['scene'],scene_oos_status=policy['oos_status'],
        scene_doorway_status=im.get('doorway_status','not_recorded'),trap_status='unknown',model_edit_status='reported_flags_only' if r['condition']=='semi' else 'not_checked_non_semi',
        repair_evidence=[],main_quality_gate=dict(status=gate,reasons=reasons),
        main_consensus_gate=dict(status=consensus,reasons=policy['reasons'] if not excluded else reasons,scope_policy='retain_scope_variation'),
        review_evidence=evidence,batch_review=dict(source='user_processed_file',individual_ring_confirmation=False),
        worker_scope_response=r['scope'],batch_revision=REVISION,reported_geometry_status=r['geometry_status'],
        reported_active_time_seconds=r['active_time_seconds'],time_provenance='user_processed_reported_not_raw_log_replayed',
        semi_reported={k:r.get(k) for k in ('initialization_kind','initialization_unchanged','known_error_unchanged','error_specific_outcome')},
        exclusion_reason=r.get('exclusion_reason',''),provided_boundary_next_pair_indices=r['boundary_next_pair_indices'])
    if o['preprocessing_status']=='ready':
        order=[];i=0
        for _ in o['links_zero_based']:order.append(i);i=r['boundary_next_pair_indices'][i]
        assert sorted(order)==list(range(len(o['links_zero_based']))) and i==0
        _layout(o,order)
    else:
        o.update(points_1024x512=None,matterport_links_zero_based=None,ordered_source_pair_indices=None,
            ordered_source_point_indices=None,ordered_source_point_labels=None,geometry=dict(status='pairing_unavailable',issues=r['preprocessing_blockers'],unusable_pair_ids=[]),
            ring_confirmed=False,order_record=None,order_status='default_unreviewed',order_origins=[],method_evaluability='not_assessed_per_method')
    o['final_review']=dict(object_id=oid,cleaning_disposition=o['cleaning_disposition'],worker_quality_gate=gate,
        order_state='not_confirmed',geometry_status=o['geometry']['status'],geometry_issues=o['geometry']['issues'],
        scope_difference_annotation=False,detail_difference_annotation=False)
    return o


def build():
    base=load_current_bundle(BASE);context=load_scored_context(base);bundle=copy.deepcopy(base)
    with gzip.open(INTAKE/'preprocessed_annotations.json.gz','rt',encoding='utf-8') as f:received=json.load(f)['objects']
    images={i['image_id']:i for i in bundle['research']['images']}
    difficulty={d['image_id']:d for d in context['difficulty_records']};reviews=load_image_review_decisions()
    old=[o for o in base['data']['objects'] if o['object_kind']=='annotation'];grouped=defaultdict(list)
    for o in old:grouped[o['image_id']].append(o)
    policies={iid:image_policy(im,difficulty[iid],grouped[iid],reviews.get(iid,{})) for iid,im in images.items()}
    new=[make_object(r,images[r['image_id']],policies[r['image_id']]) for r in received]
    print('new geometry checked',dict(Counter(o['geometry']['status'] for o in new)),flush=True)
    assert not {o['object_id'] for o in new}&{o['object_id'] for o in base['data']['objects']}
    bundle['data']['objects'].extend(new)
    for o in new:
        row=_research_row(o,images[o['image_id']])
        row.update(order_state='not_confirmed',order_change='provided_boundary_unreviewed',
            worker_scope_response=o['worker_scope_response'],reported_active_time_seconds=o['reported_active_time_seconds'],
            time_provenance=o['time_provenance'],semi_reported=o['semi_reported'],exclusion_reason_detail=o['exclusion_reason'])
        bundle['research']['annotations'].append(row)
    _summaries(bundle,new,set(),revision=REVISION,order_change='provided_boundary_unreviewed')
    bundle['data'].update(data_release='v2',input_revision=REVISION)
    bundle['research']['data_release']='v2'
    bundle['final_summary'].update(data_release='v2',formal_analysis_connected=False,order_queue_complete=False)
    bundle['batch_admission']['version']=REVISION
    bundle['batch_admission']['records'].extend(dict(object_id=o['object_id'],source_id=o['object_id'],
        image_id=o['image_id'],worker_id=o['worker_id'],condition=o['condition'],
        reported_active_time_seconds=o['reported_active_time_seconds'],worker_scope_response=o['worker_scope_response']) for o in new)
    validation=validate_bundle(bundle['data'],bundle['research'],bundle['comments'],bundle['final_summary'])
    assert bundle['data']['objects'][:len(base['data']['objects'])]==base['data']['objects']
    assert bundle['comments']==base['comments'] and bundle['final_orders']==base['final_orders']
    print('bundle validated; binding references',flush=True)
    routing=build_affected_records(bundle,context['difficulty_records'],context['reference_catalog'],include_all_images=True,resolve_multiple_spaces=True)
    gates={r['object_id']:r for r in routing['affected_records']}
    refs={r['target_id']:r for r in context['reference_catalog']}
    prior={r['object_id']:r for r in context['binding_records']}
    prior_quality={r['object_id']:r for r in context['quality_records']}
    # 旧作答继承已审核绑定，不能被本次自动路由覆盖；不继承旧分数或旧人数资格。
    for oid,p in prior.items():
        for k in ('chosen_target_id','binding_status'):
            gates[oid][k]=p[k] or ''
        gates[oid]['chosen_target_is_current']=gates[oid]['chosen_target_id']==gates[oid]['current_target_id']
        gates[oid]['analysis_binding_eligible']=bool(gates[oid]['chosen_target_id']) and gates[oid]['pool_analysis_eligible']
    rows=[]
    for o in bundle['data']['objects']:
        if o['object_kind']!='annotation':continue
        g=gates[o['object_id']];p=policies[o['image_id']];ref=refs.get(g['chosen_target_id'])
        usage_row=dict(prior_quality.get(o['object_id'],{}),**g)
        usage_row['difficulty_analysis_exclusion']=difficulty[o['image_id']]['difficulty_analysis_exclusion']
        usage=usage_policy(usage_row,o,g,ref,dict(full_input_available=o['geometry']['status']=='surface_valid'),
            scene_flags(difficulty[o['image_id']]),full_score_state='computed')
        # computed仅用于先验输入门评估；没有产生分数，结果字段明确为candidate/not_scored。
        reasons=list(usage['quality_exclusion_reasons'])
        if p['quality_gate'] in HOLDS:reasons+=p['reasons']
        if p['oos_status']=='confirmed':reasons.append('oos_diagnostic_only')
        if p['oos_status']=='pending':reasons.append('scope_applicability_pending')
        if o['preprocessing_status']!='ready' or o['geometry']['status']!='surface_valid':reasons.append('input_geometry_unavailable')
        if not ref:reasons.append('reference_binding_pending')
        elif not ref['full_reference_available']:reasons.append('full_reference_unavailable')
        # 与v1用途一致，绑定其它已准入空间不自动升级成主参考质量。
        if ref and not ref['current_target']:reasons.append('bound_other_admitted_space')
        rows.append(dict(object_id=o['object_id'],image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],condition=o['condition'],
            origin='v1' if o['object_id'] in prior else 'new',cleaning_disposition=o['cleaning_disposition'],
            preprocessing_status=o['preprocessing_status'],geometry_status=o['geometry']['status'],
            source_pool_eligible=g['pool_vote_eligible'],pool_source_workers=g['pool_source_workers'],pool_analysis_eligible=g['pool_analysis_eligible'],
            image_quality_gate=p['quality_gate'],image_oos_status=p['oos_status'],image_oos_subtype=p['oos_subtype'],
            chosen_target_id=g['chosen_target_id'],binding_status=g['binding_status'],quality_input_candidate=not reasons,
            quality_input_blockers='|'.join(sorted(set(reasons))),score_status='not_scored_v2',
            reported_active_time_seconds=o.get('reported_active_time_seconds'),time_provenance=o.get('time_provenance','inherited_v1_time_source'),
            worker_scope_response=o.get('worker_scope_response')))
    assert len(rows)==10439 and len({r['object_id'] for r in rows})==len(rows)
    assert all(not r['quality_input_candidate'] and not r['pool_analysis_eligible'] for r in rows if r['image_code'] in RECONFIRMED)
    OUT.mkdir(parents=True,exist_ok=True)
    bundle['field_contract']['v2_addendum']=dict(data_release='v2',annotations=10439,
        original_export_points='New rows null: user-processed source is before_preprocessing_points, not raw export.',
        provided_order='Source boundary retained; ring_confirmed remains false without a separate human order receipt.',
        runtime_identity='New source project/task/account null; source_id is the v2 object namespace.',
        reported_active_time_seconds='User-processed time; not silently certified as v1 raw-log-equivalent.',
        worker_scope_response='Worker response, distinct from image_oos_status and image-level analysis holds.')
    bundle['research_field_contract']['cross_table_denominators']={k:dict(unit='image_id' if k in ('gt_marks','scene_images') else 'object_id',
        n=sum(r['n'] for r in v)) for k,v in bundle['research']['cross_tables'].items()}
    entrypoints={}
    for key in ('data','research','comments','final_summary','final_orders','batch_admission','field_contract','research_field_contract','quality_review_metadata'):
        name=key+'.json.gz';entrypoints[key]=name
        with gzip.open(OUT/name,'wt',encoding='utf-8') as f:json.dump(bundle[key],f,ensure_ascii=False,allow_nan=False)
    validation.update(v1_objects_unchanged=True,v1_comments_and_confirmed_orders_unchanged=True,
        v2_records=len(rows),new_records=len(new),new_geometry=dict(Counter(o['geometry']['status'] for o in new)),
        user_list_11_main_analysis_blocked=True,quality_input_candidates=sum(r['quality_input_candidate'] for r in rows),
        quality_input_candidate_images=len({r['image_id'] for r in rows if r['quality_input_candidate']}),
        not_performed=['v2 scoring','personnel refit','fusion rerun','raw active log replay'])
    write(OUT/'validation.json',validation);entrypoints['validation']='validation.json'
    write(OUT/'manifest.json',dict(schema='research_analysis_bundle_v1',contract_version=bundle['data']['contract_version'],
        data_release='v2',effective_input_revision=REVISION,entrypoints=entrypoints,validation=validation,
        base_manifest=BASE.relative_to(ROOT).as_posix(),image_policy='image_policy.json',record_eligibility='record_eligibility.csv',
        reference_bindings='reference_bindings.json.gz',difficulty_records='difficulty_records.json.gz',reference_catalog='reference_catalog.json.gz',
        status='analysis_input_admitted_scores_not_run'))
    write(OUT/'image_policy.json',list(policies.values()));csv_table(OUT/'record_eligibility.csv',rows)
    csv_table(OUT/'source_pools.csv',routing['source_pools'])
    for name,payload in [('reference_bindings',list(gates.values())),('difficulty_records',context['difficulty_records']),('reference_catalog',context['reference_catalog'])]:
        with gzip.open(OUT/(name+'.json.gz'),'wt',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,allow_nan=False)
    csv_table(OUT/'image_hold_audit.csv',[dict(p,new_manual=sum(o['image_id']==p['image_id'] and o['condition']=='manual' and o['cleaning_disposition']=='retained' for o in new),
        combined_manual_source_workers=next(x['n_effective_workers'] for x in routing['source_pools'] if x['image_id']==p['image_id'] and x['condition']=='manual'))
        for p in policies.values() if p['quality_gate'] in HOLDS])
    assert load_current_bundle(OUT/'manifest.json')['validation']['annotations']==10439
    publish_release_pointer()
    print(json.dumps(validation,ensure_ascii=True,indent=2))


if __name__=='__main__':build()
