"""v2.1输入与原答评分闭合；后续阶段完成前不推进全局CURRENT。"""
import copy
import gzip
import json
from collections import Counter
from .rescore_adopted_references_20261028 import OUT as PRIOR, ADOPT, ROOT
from .scope_quality_scoring_20261016 import scoring_engine, score_task, METRICS
from .quality_b8l2_d10_20261017 import dual_scores
from .b8l2_usage_coverage_20261016 import scene_flags

OUT=ROOT/'research/data/releases/v2.1'
Q=ROOT/'research/quality/quality_workers_v2_20261019'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def write(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    refs=read(ADOPT/'REFERENCE_CATALOG.json'); rm={r['target_id']:r for r in refs}
    old=read(Q/'quality_inventory.json'); bindings=read(Q/'reference_bindings.json')
    bm={r['object_id']:copy.deepcopy(r) for r in bindings}
    reroute={r['object_id']:r['new_target'] for r in read(ADOPT.parent/'E9Z_BINDING_RECHECK.json')}
    diff=read(ROOT/'research/difficulty/difficulty_user_revision_20261028/current_261.json')
    dm={r['image_id']:r for r in diff['records']}
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:
        objects={r['object_id']:r for r in json.load(f)['objects']}
    OUT.mkdir(exist_ok=True)
    cache={}
    for path in [Q/'measurements.jsonl',PRIOR/'ORIGINAL_MEASUREMENTS.jsonl',OUT/'new_original_measurements.jsonl']:
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                r=json.loads(line);cache[r['task']['object_id']]=r
    results=[];counts=Counter();changes=[]
    release=read(OUT/'RELEASE.json') if (OUT/'RELEASE.json').exists() else dict(data_release='v2.1',base_release='v2',status='building',
        authorization='用户要求完整重算整个流程，版本号v2.1',
        raw_annotations='research/data/releases/v2/analysis_input/data.json.gz',
        reference_catalog='reference_catalog.json',difficulty='difficulty_records.json',
        stages=dict(originals='running',teams='pending',new_space_natural256='pending',
                    classification_and_selection='pending',derived_comparisons='pending',independent_validation='pending'))
    release['recompute_policy']='仅重算受影响依赖；不因版本更新而重复融合或重算相同输入。'
    release['stages']['originals']='running';write('RELEASE.json',release)
    with scoring_engine() as (engine,models), (OUT/'new_original_measurements.jsonl').open('a',encoding='utf-8') as log:
        for previous in old:
            oid=previous['object_id'];obj=objects[oid];b=bm[oid]
            tid=reroute.get(oid,b['chosen_target_id']);b['chosen_target_id']=tid
            ref=rm.get(tid);points=ref['points_1024x512'] if ref else None
            task=dict(object_id=oid,image_id=obj['image_id'],worker_id=obj['worker_id'],condition=obj['condition'],
                current_target_id=tid,reference_version=ref['reference_version'] if ref else None,
                annotation_points=obj['points_1024x512'],reference_points=points,
                reference_full_available=bool(ref and ref['full_reference_available']))
            hit=cache.get(oid)
            if hit and all(hit['task'].get(k, True if k=='reference_full_available' else None)==v for k,v in task.items()):
                m=copy.deepcopy(hit['result']);counts['exact_geometry_cache_reused']+=1
            else:
                m=score_task(task,engine,models)
                if m['score_status']=='complete':m.update(dual_scores(m,models))
                log.write(json.dumps(dict(task=task,result=m),ensure_ascii=False,allow_nan=False)+'\n');log.flush()
                counts['new_measurements']+=1
            complete=m['score_status']=='complete'
            blockers=list(previous['quality_exclusion_reasons'])
            if complete and ref and ref['full_reference_available']:
                blockers=[x for x in blockers if x not in ('full_reference_unavailable','reference_not_full','score_unavailable')]
            if not complete and 'score_unavailable' not in blockers:blockers.append('score_unavailable')
            if ref and ref['image_analysis_blocked']:
                blockers=list(dict.fromkeys(blockers+ref['image_analysis_hold_reasons']))
            usable=complete and not blockers
            r=copy.deepcopy(previous)
            r.update(data_release='v2.1',chosen_target_id=tid,reference_id=tid,rescore_target_id=tid,
                reference_version=task['reference_version'],current_class=dm[obj['image_id']]['current_class'],
                quality_exclusion_reasons=blockers,quality_usable=usable,current_quality_eligible=usable,
                score_status=m['score_status'],measurement_reasons=m['reasons'],
                full_score_state='computed' if complete else 'unavailable',
                quality_use=previous['quality_use'] if previous['quality_usable'] else
                    ('doorway_quality' if usable and scene_flags(dm[obj['image_id']])['is_doorway'] else
                     'ordinary_primary' if usable and b['ordinary_difficulty_eligible'] else 'special_conditional_only' if usable else 'not_qualified'))
            for key in ('B8L2','D10'):
                r[key]=m.get(key) if usable else None;r['diagnostic_'+key]=m.get(key) if complete else None
            for key in (*METRICS,'IoU3D100'):r[key]=m.get(key) if complete else None
            results.append(r);counts['complete' if complete else 'unavailable']+=1
            if usable!=previous['quality_usable'] or previous['B8L2']!=r['B8L2']:
                changes.append(dict(object_id=oid,image=r['image_code'],condition=r['condition'],
                    old_usable=previous['quality_usable'],new_usable=usable,old_Q=previous['B8L2'],new_Q=r['B8L2'],
                    old_exclusions=previous['quality_exclusion_reasons'],new_exclusions=blockers))
    assert len(results)==10439 and len({r['object_id'] for r in results})==10439
    assert all(not r['quality_usable'] for r in results if r['image_code']=='wc2JMjhGNzB-14')
    write('reference_catalog.json',refs);write('reference_bindings.json',list(bm.values()))
    write('difficulty_records.json',diff);write('quality_inventory.json',results)
    write('ORIGINAL_CHANGES.json',changes);counts['quality_usable']=sum(r['quality_usable'] for r in results)
    write('ORIGINAL_CHECKS.json',dict(counts))
    release=read(OUT/'RELEASE.json');release['stages']['originals']='complete';write('RELEASE.json',release)
    print(dict(counts))


if __name__=='__main__':main()
