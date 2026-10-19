import sys,json,gzip,hashlib
from pathlib import Path
BASE=Path('/workspace/shared/composition_audit_20261019');PKG=BASE/'extracted/personnel_composition_study_20261019';OUT=BASE/'dot_replay_audit';sys.path.insert(0,str(PKG/'analysis/composition'))
import fusion_runner as fr
fe=fr.init_engine(BASE/'restored'); pools={p['pool_id']:p for p in fe.load_pools()};results=[];chain_results=[]
with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
 for f in sorted((PKG/'analysis/representative_cases/cases').glob('C[0-9]*.json')):
  c=json.loads(f.read_text());p=pools[c['pool_id']];by={r['worker_id']:r for r in p['records']}
  rec_checks=[dict(worker=m['worker_id'],exact=m['frozen_record']==by[m['worker_id']]) for m in c['members']]
  refs={k:c['reference'][k]==v for k,v in p['reference'].items()}
  results.append(dict(case=c['case_id'],records=rec_checks,reference_checks=refs,pool_digest_exact=fr.digest(p)==c['pool_digest']))
  if c.get('full_member_chain'):
   chain=c['full_member_chain']; runs=[]
   for point in chain['points']:
    row=fr.evaluate_one(p,point['worker_ids'],engine,models,full_state=True);state=row.pop('full_state',None)
    runs.append(dict(point=point,result=row,identity_groups=None if state is None else state['identity_groups']))
   transitions=[]
   for before,after in zip(runs,runs[1:]):
    if before['identity_groups'] is not None and after['identity_groups'] is not None:
     transitions.append(dict(before_k=before['point']['k'],after_k=after['point']['k'],transition=fe.transition(dict(n=before['point']['k'],identity_groups=before['identity_groups']),dict(n=after['point']['k'],identity_groups=after['identity_groups']))))
   chain_results.append(dict(case=c['case_id'],chain_id=chain.get('chain_id'),points=[dict(point=r['point'],result=r['result']) for r in runs],transitions=transitions))
   print(c['case_id'],len(runs),'full chain completed',flush=True)
(OUT/'case_snapshot_and_full_chains.json').write_text(json.dumps(fe.clean(dict(case_checks=results,all_snapshot_checks_pass=all(all(r['exact'] for r in x['records']) and all(x['reference_checks'].values()) and x['pool_digest_exact'] for x in results),full_chains=chain_results)),ensure_ascii=False,indent=2))
