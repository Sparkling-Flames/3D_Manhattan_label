"""Diagnostic cached-reference rescore only; no binding choice or eligibility promotion."""
import gzip
import json
from .extend_scope_references_20261028 import ROOT,OUT,PENDING_COLLINEAR
from .scope_quality_scoring_20261016 import scoring_engine,score_task
from .quality_b8l2_d10_20261017 import dual_scores


def main():
    refs={r['target_id']:r for r in json.loads((OUT/'REFERENCES.json').read_text(encoding='utf-8'))}
    inventory=json.loads((OUT/'FROZEN_BINDING_INVENTORY.json').read_text(encoding='utf-8'))
    with gzip.open(ROOT/'research/data/releases/v2/analysis_input/data.json.gz','rt',encoding='utf-8') as f:data=json.load(f)
    objects={r['object_id']:r for r in data['objects']}
    cachepath=OUT/'DIAGNOSTIC_MEASUREMENTS.jsonl'
    cache={}
    if cachepath.exists():
        for line in cachepath.read_text(encoding='utf-8').splitlines():
            r=json.loads(line);cache[r['task']['object_id']]=r
    ledger=[];computed=reused=0
    with scoring_engine() as (engine,models),cachepath.open('a',encoding='utf-8') as log:
        for r in inventory:
            if r['condition']!='manual' or r['chosen_target_id'] not in refs:continue
            oid=r['object_id'];o=objects[oid];ref=refs[r['chosen_target_id']]
            if r['image_code'] in PENDING_COLLINEAR or r['image_code']=='e9zR4mvMWw7-09':
                ledger.append(dict(object_id=oid,image=r['image_code'],state='pending_collinear_or_changed_floor_binding_review'));continue
            task=dict(object_id=oid,image_id=o['image_id'],worker_id=o['worker_id'],condition=o['condition'],current_target_id=ref['target_id'],reference_version=ref['reference_version'],annotation_points=o['points_1024x512'],reference_points=ref['points_1024x512'])
            cached=cache.get(oid)
            if cached and cached['task']==task:result=cached['result'];reused+=1
            else:
                result=score_task(task,engine,models)
                if result['score_status']=='complete':result.update(dual_scores(result,models))
                log.write(json.dumps(dict(task=task,result=result),ensure_ascii=False,allow_nan=False)+'\n');log.flush();computed+=1
            ledger.append(dict(object_id=oid,image=r['image_code'],target_id=ref['target_id'],state=result['score_status'],diagnostic_B8L2=result['B8L2'],diagnostic_D10=result.get('D10'),original_exclusions=r['quality_exclusion_reasons'],eligibility_promoted=False))
            if (computed+reused)%100==0:print('diagnostic measured',computed+reused,flush=True)
    (OUT/'DIAGNOSTIC_SCORE_LEDGER.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    receipt=dict(new_measurements=computed,reused_measurements=reused,complete=sum(r['state']=='complete' for r in ledger),pending=sum(r['state'].startswith('pending') for r in ledger),formal_eligibility_promoted=0,new_fusion=0)
    (OUT/'DIAGNOSTIC_SCORE_CHECKS.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(receipt)


if __name__=='__main__':main()
