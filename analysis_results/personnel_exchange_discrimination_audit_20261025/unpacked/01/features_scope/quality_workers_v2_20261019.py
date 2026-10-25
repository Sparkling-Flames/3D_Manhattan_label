"""v2参考身份复核、冻结B8L2/D10复算；不解除历史用途限制。"""
import csv
import gzip
import json
from pathlib import Path

from ..data_prep.consolidate_research_input import load_current_bundle
from ..data_prep.admit_workers_v2_20261019 import BASE, OUT as INPUT, csv_table
from .current_annotation_context_20261017 import load_scored_context
from .scope_quality_scoring_20261016 import scoring_engine, score_task
from .quality_b8l2_d10_20261017 import dual_scores
from .b8l2_usage_coverage_20261016 import scene_flags
from .scope_local_routing_20261017 import historical_router
from .difficulty_coarse_closeout_20261014 import floor

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/quality/quality_workers_v2_20261019'
ENGINE=ROOT/'research/statistics/b8l2_shared_v6_20261016/inputs'

def read(path):
    if str(path).endswith('.gz'):
        with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
    return json.loads(path.read_text(encoding='utf-8-sig'))

def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def resolve_binding(binding,oid):
    b=dict(binding)
    if b['chosen_target_id']:return b,None
    if len(b['allowed_target_ids'])==1:
        b.update(chosen_target_id=b['allowed_target_ids'][0],binding_status='sole_reference_identity_only')
        b['chosen_target_is_current']=b['chosen_target_id']==b['current_target_id']
        return b,'sole_reference_identity_only'
    return b,'needs_geometry_or_target_review' if oid.startswith('v2:new:') else 'historical_unusable_or_excluded'

def quality_gate(blockers,computed):
    return sorted(set(blockers+([] if computed else ['score_unavailable'])))

def apply_review(binding,obj,refs,review):
    assert obj['points_1024x512']==review['reviewed_points'],'reviewed_geometry_changed'
    b=dict(binding);target=review['chosen_target_id'];evidence=dict(review)
    if target is None:
        router,config=historical_router()
        prepared=router.prepare_reference_set([dict(candidate_id=t,floor_xz_h=refs[t]['floor_xz_h'])
            for t in b['allowed_target_ids']],config)
        route=router.route_floor(floor(obj['points_1024x512']),prepared)
        target=route['global_iou_best']
        evidence.update(fallback_rule=config['fallback'],candidate_floor_metrics=route['candidate_floor_metrics'],
            uncertainty='camera_outside_user_authorized_provisional',quality_used_for_binding=False)
    assert target in b['allowed_target_ids']
    evidence['chosen_target_id']=target
    b.update(chosen_target_id=target,chosen_target_is_current=target==b['current_target_id'],
        binding_status=review['method'],user_reference_review=evidence)
    return b

def run():
    OUT.mkdir(parents=True,exist_ok=True)
    bundle=load_current_bundle(INPUT/'manifest.json')
    old=load_scored_context(load_current_bundle(BASE))
    oldq={r['object_id']:r for r in old['quality_records']}
    binding_map={b['object_id']:b for b in read(INPUT/'reference_bindings.json.gz')}
    objects={o['object_id']:o for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    refs=read(INPUT/'reference_catalog.json.gz'); refmap={r['target_id']:r for r in refs}
    reviewpath=OUT/'USER_REFERENCE_REVIEW.json'
    reviews={r['object_id']:r for r in read(reviewpath)['records']} if reviewpath.exists() else {}
    difficulty=read(INPUT/'difficulty_records.json.gz'); dm={d['image_id']:d for d in difficulty}
    with (INPUT/'record_eligibility.csv').open(encoding='utf-8-sig',newline='') as f:elig={r['object_id']:r for r in csv.DictReader(f)}
    bindings=[];audits=[];scores=[]
    # Cache stores exact geometry and reference, never just an annotation identifier.
    cachepath=OUT/'measurements.jsonl';cache={}
    if cachepath.exists():
        for line in cachepath.read_text(encoding='utf-8').splitlines():
            r=json.loads(line);cache[r['task']['object_id']]=r
    with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (engine,models), cachepath.open('a',encoding='utf-8') as log:
        for i,(oid,o) in enumerate(objects.items()):
            b,a=resolve_binding(binding_map[oid],oid)
            if oid in reviews:b=apply_review(b,o,refmap,reviews[oid])
            e=elig[oid];ref=refmap.get(b['chosen_target_id']); d=dm[o['image_id']]
            if a:audits.append(dict(object_id=oid,image_code=o['image_code'],worker_id=o['worker_id'],resolution=a,
                previous_target='',chosen_target_id=b['chosen_target_id'],routing=b.get('local_routing_evidence'),
                retained_quality_blockers=e['quality_input_blockers'],adopted_review=None))
            if oid in reviews:audits[-1]['adopted_review']=b['user_reference_review']
            result=None
            if ref and ref['full_reference_available'] and o['geometry']['status']=='surface_valid':
                task=dict(object_id=oid,image_id=o['image_id'],worker_id=o['worker_id'],condition=o['condition'],
                    current_target_id=ref['target_id'],reference_version=ref['reference_version'],
                    annotation_points=o['points_1024x512'],reference_points=ref['points_1024x512'])
                cached=cache.get(oid)
                if cached and cached['task']==task:result=cached['result']
                else:
                    result=score_task(task,engine,models)
                    if result['score_status']=='complete':result.update(dual_scores(result,models))
                    log.write(json.dumps(dict(task=task,result=result),ensure_ascii=False,allow_nan=False)+'\n');log.flush()
            complete=bool(result and result['score_status']=='complete')
            inherited=[x for x in e['quality_input_blockers'].split('|') if x]
            if oid in reviews:
                inherited=[x for x in inherited if x not in ('reference_binding_pending','reference_not_full','space_binding_not_unique')]
                if not ref['full_reference_available']:inherited.append('reference_not_full')
                if not ref['current_target']:inherited.append('bound_other_admitted_space')
            blockers=quality_gate(inherited,complete)
            # Sole identity repair is diagnostic only: historical holds stay in force.
            usable=not blockers
            b['target_binding_unique']=bool(b['chosen_target_id']) and 'space_binding_not_unique' not in blockers
            b.setdefault('user_reference_review',None)
            bindings.append(b)
            r=dict(e,building_id=o['building_id'],current_class=d['current_class'],scene=d['scene'],
                chosen_target_id=b['chosen_target_id'],binding_status=b['binding_status'],
                is_oos=e['image_oos_status'] in ('confirmed','pending'),pool_analysis_eligible=e['pool_analysis_eligible']=='True',
                quality_usable=usable,current_quality_eligible=usable,quality_exclusion_reasons=blockers,
                full_score_state='computed' if complete else 'unavailable',score_status='complete' if complete else 'unavailable',
                measurement_reasons=result['reasons'] if result else ['input_or_reference_unavailable'],
                rescore_target_id=b['chosen_target_id'],reference_id=b['chosen_target_id'],
                reference_version=ref['reference_version'] if ref else None,
                source_active_time_seconds=o.get('reported_active_time_seconds') if oid.startswith('v2:new:') else oldq[oid].get('source_active_time_seconds'),
                semi_reported=o.get('semi_reported'),worker_scope_response=o.get('worker_scope_response'),
                quality_use='not_qualified' if not usable else 'doorway_quality' if scene_flags(d)['is_doorway'] else
                    'ordinary_primary' if b['ordinary_difficulty_eligible'] else 'special_conditional_only')
            for m in ('B8L2','D10'):
                r[m]=result[m] if usable else None
                r['diagnostic_'+m]=result[m] if complete else None
            if complete:
                for m in ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter'):r[m]=result[m]
            scores.append(r)
            if i%200==0:print('measured',i,'/',len(objects),flush=True)
    assert len(scores)==10439 and len(audits)==34
    assert sum(a['resolution']=='sole_reference_identity_only' for a in audits)==19
    assert all(not r['quality_usable'] for r in scores if r['image_quality_gate'].startswith('hold_'))
    write(OUT/'binding_audit.json',audits);csv_table(OUT/'binding_audit.csv',audits)
    write(OUT/'reference_bindings.json',bindings);write(OUT/'reference_catalog.json',refs);write(OUT/'difficulty_records.json',difficulty)
    write(OUT/'quality_inventory.json',scores);csv_table(OUT/'quality_inventory.csv',scores)
    qualified=[r for r in scores if r['quality_usable']];csv_table(OUT/'quality_records.csv',qualified)
    write(OUT/'old_membership_expansion.json',[dict(object_id=r['object_id'],image_code=r['image_code'],
        old_reasons=oldq[r['object_id']]['quality_exclusion_reasons'],new_pool_workers=r['pool_source_workers'])
        for r in qualified if r['origin']=='v1' and not oldq[r['object_id']]['quality_usable']])
    metadata=dict(version='quality_workers_v2_20261019',data_release='v2',primary_metric='B8L2',parallel_metric='D10',
        n1_applied=False,counts=dict(inventory=len(scores),quality_rows=len(qualified),quality_images=len({r['image_id'] for r in qualified}),
        computed=sum(r['score_status']=='complete' for r in scores),binding_identity_resolved=19,
        user_reviewed_bindings=len(reviews),binding_remaining=sum(not b['chosen_target_id'] for b in bindings)),
        full_inventory_with_metric_eligibility=str((OUT/'quality_inventory.csv').relative_to(ROOT)),
        all_pre_score_bindings=str((OUT/'reference_bindings.csv').relative_to(ROOT)),
        recommended_qualified_scores=str((OUT/'quality_records.csv').relative_to(ROOT)),
        reference_catalog=str((OUT/'reference_catalog.json').relative_to(ROOT)),difficulty_records=str((OUT/'difficulty_records.json').relative_to(ROOT)))
    csv_table(OUT/'reference_bindings.csv',bindings);write(OUT/'CROSS_MODULE_INPUTS.json',metadata)
    print(json.dumps(metadata['counts']),flush=True)

if __name__=='__main__':
    run()
