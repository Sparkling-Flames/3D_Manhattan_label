"""Document the sole frozen-plan object-ID rejection, using identity fields only."""
from pathlib import Path
import hashlib,json
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent;WORK=BASE.parent
KEY='uNb9QFRL6hY-82__manual__8e7ae21c8d__bf85118df1632fe78d8a'
BAD=WORK/'repo/research/workers/personnel_v21_reselection_20261029/additional_delivery/packages/07B/experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz'
COLS=['team_key','pool_id','member_workers','member_object_ids','reference_id','reference_version','condition','data_release']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(path):
 d=pd.read_csv(path,usecols=lambda c:c in COLS,low_memory=False).fillna('')
 d=d[d.team_key.eq(KEY)];assert len(d)==1
 return d.iloc[0].to_dict()

def main():
 bad=one(BAD);plan=BASE/'stage02_engine/cache_plan/REQUEST_IDENTITY_AND_REUSE.csv.gz'
 selected=[]
 for d in pd.read_csv(plan,usecols=['team_key','pool_id','member_workers','member_object_ids','endpoint_acquisition','prior_source'],chunksize=50000):
  selected.extend(d[d.team_key.eq(KEY)].fillna('').to_dict('records'))
 assert len(selected)==1;request=selected[0];good_path=Path(request['prior_source']);good=one(good_path)
 assert request['member_workers']==bad['member_workers']==good['member_workers']
 assert request['member_object_ids']==good['member_object_ids']
 assert bad['member_object_ids']=='|'.join(request['member_object_ids'])
 projected=json.loads((BASE/'stage01_capacity/SCORE_BLIND_POOL_INPUTS.json').read_text())
 pool=next(p for p in projected['pools'] if p['pool_id']==request['pool_id'])
 by={r['worker_id']:str(r['object_id']) for r in pool['members']}
 workers=request['member_workers'].split('|');expected=[by[w] for w in workers]
 assert '|'.join(expected)==request['member_object_ids']
 metadata=one(BAD)
 for f in ['pool_id','reference_id','reference_version','condition','data_release']:
  assert metadata[f]==good[f]
 manifest=json.loads((BASE/'stage02_engine/cache_plan/CACHE_PLAN.json').read_text())
 assert manifest['rejected_candidate_rows']=={'object_ids':1}
 record={'status':'sole_identity_rejection_explained','team_key':KEY,'pool_id':request['pool_id'],
  'rejected_source':str(BAD.relative_to(WORK)),'rejected_source_sha256':sha(BAD),'rejected_identity_fields':bad,
  'expected_request_identity_fields':request,'expected_worker_object_pairs':dict(zip(workers,expected)),
  'accepted_scalar_source':str(good_path.relative_to(WORK)),'accepted_scalar_source_sha256':sha(good_path),
  'accepted_identity_fields':good,'expected_and_accepted_object_ids_identical':True,
  'observed_serialization_transformation_exact':'rejected member_object_ids == "|".join(expected member_object_ids string)',
  'interpretation':'The rejected copy contains character-separated serialization metadata. It does not identify a different qualified team. The frozen plan correctly rejects that record and uses an independently valid scalar source for geometry replay.',
  'qualification_changed':False,'frozen_design_changed':False,'cache_source_modified':False,'quality_values_read':False,
  'frozen_plan_rejection_count':manifest['rejected_candidate_rows'],'request_plan_sha256':sha(plan)}
 (OUT/'CACHE_OBJECT_ID_REJECTION_DETAIL.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 pd.DataFrame([{'worker_id':w,'expected_object_id':o,'accepted_scalar_object_id':g} for w,o,g in zip(workers,expected,good['member_object_ids'].split('|'))]).to_csv(OUT/'CACHE_REJECTION_EXPECTED_WORKER_OBJECTS.csv',index=False,encoding='utf-8-sig')
 print(json.dumps({'status':record['status'],'team_key':KEY,'qualified_workers':len(workers),'exact_character_join_verified':True,'acquisition':request['endpoint_acquisition']},ensure_ascii=False))

if __name__=='__main__':main()
