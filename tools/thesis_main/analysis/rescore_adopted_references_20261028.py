"""新版参考依赖清单与原答全分项重算；不覆盖冻结库存。"""
import gzip
import json
from collections import Counter
from .adopt_ceiling_review_20261028 import ROOT, OUT as ADOPT
from .scope_quality_scoring_20261016 import scoring_engine, score_task
from .quality_b8l2_d10_20261017 import dual_scores

OUT = ADOPT / 'dependent_recompute'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    OUT.mkdir(exist_ok=True)
    old = {r['target_id']: r for r in read(ROOT/'research/quality/quality_workers_v2_20261019/reference_catalog.json')}
    new = {r['target_id']: r for r in read(ADOPT/'REFERENCE_CATALOG.json')}
    changed = {tid for tid, r in new.items() if tid not in old or r['points_1024x512'] != old[tid]['points_1024x512']}
    inventory = read(ROOT/'research/quality/quality_workers_v2_20261019/quality_inventory.json')
    routing = {r['object_id']:r['new_target'] for r in read(ADOPT.parent/'E9Z_BINDING_RECHECK.json')}
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:
        objects = {r['object_id']:r for r in json.load(f)['objects']}
    def write(name, value):
        (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    dependencies = []
    for r in inventory:
        tid = routing.get(r['object_id'], r['chosen_target_id'])
        if tid in changed:
            dependencies.append(dict(object_id=r['object_id'], image=r['image_code'], condition=r['condition'],
                old_target=r['chosen_target_id'], new_target=tid, old_exclusions=r['quality_exclusion_reasons']))
    write('DEPENDENCIES.json', dict(changed_targets=sorted(changed), objects=dependencies,
        unaffected_objects=len(inventory)-len(dependencies),
        team_dependencies_status='pending_saved_endpoint_inventory', training_dependencies_status='pending_recomputed_inputs'))
    cachepath = OUT/'ORIGINAL_MEASUREMENTS.jsonl'
    cache = {}
    if cachepath.exists():
        for line in cachepath.read_text(encoding='utf-8').splitlines():
            row=json.loads(line); cache[row['task']['object_id']]=row
    computed=reused=0; ledger=[]
    with scoring_engine() as (engine, models), cachepath.open('a',encoding='utf-8') as log:
        for dep in dependencies:
            obj=objects[dep['object_id']]; ref=new[dep['new_target']]
            task=dict(object_id=obj['object_id'],image_id=obj['image_id'],worker_id=obj['worker_id'],condition=obj['condition'],
                current_target_id=ref['target_id'],reference_version=ref['reference_version'],
                annotation_points=obj['points_1024x512'],reference_points=ref['points_1024x512'],
                reference_full_available=ref['full_reference_available'])
            hit=cache.get(obj['object_id'])
            if hit and hit['task']==task:
                result=hit['result'];reused+=1
            else:
                result=score_task(task,engine,models)
                if result['score_status']=='complete':result.update(dual_scores(result,models))
                log.write(json.dumps(dict(task=task,result=result),ensure_ascii=False,allow_nan=False)+'\n');log.flush();computed+=1
            ledger.append(dict(**dep,result=result,eligibility_status='pending_full_inventory_reconciliation'))
            if (computed+reused)%100==0:print('original rescored',computed+reused,'/',len(dependencies),flush=True)
    write('ORIGINAL_SCORE_LEDGER.json',ledger)
    checks=dict(changed_targets=len(changed),affected_originals=len(dependencies),computed=computed,reused=reused,
        by_condition=dict(Counter(r['condition'] for r in dependencies)),score_states=dict(Counter(r['result']['score_status'] for r in ledger)),
        new_fusion=0, eligibility_promoted=0, full_dependency_recompute_complete=False)
    write('ORIGINAL_SCORE_CHECKS.json',checks)
    assert computed+reused==len(dependencies)
    print(checks)


if __name__=='__main__':main()
