import os,sys,json,gzip,hashlib
from pathlib import Path
for x in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[x]='1'
import pandas as pd,numpy as np
from scipy.optimize import linear_sum_assignment
BASE=Path('/workspace/shared/composition_audit_20261019'); PKG=BASE/'extracted/personnel_composition_study_20261019'; OUT=BASE/'dot_replay_audit'
sys.path.insert(0,str(PKG/'analysis/composition'))
import fusion_runner as fr
fe=fr.init_engine(BASE/'restored')
def read(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(n,d):(OUT/n).write_text(json.dumps(fe.clean(d),ensure_ascii=False,indent=2,allow_nan=False))
# Actual-case comparison of old angular minimum-sum filtering to cardinality-first.
rows=[]
for f in sorted((PKG/'analysis/representative_cases/cases').glob('C[0-9]*.json')):
 c=json.loads(f.read_text()); ref=np.asarray(c['reference']['points_1024x512'])
 for team in c['teams']:
  pts=(team.get('geometry') or {}).get('points')
  if pts is None:continue
  a=np.asarray(pts); cost=np.maximum(fe.angular(a[::2],ref[::2]),fe.angular(a[1::2],ref[1::2])); ii,jj=linear_sum_assignment(cost)
  for threshold in [5,9]:
   n,m=cost.shape; penalty=2*(n+1); aug=np.full((n,m+n),penalty);aug[:,:m]=np.where(cost<=threshold,cost/threshold,penalty*(n+m+1));ci,cj=linear_sum_assignment(aug)
   old=[(int(i),int(j)) for i,j in zip(ii,jj) if cost[i,j]<=threshold];new=[(int(i),int(j)) for i,j in zip(ci,cj) if j<m and cost[i,j]<=threshold]
   rows.append(dict(case_id=c['case_id'],team_key=team['team_key'],threshold=threshold,old_matched=len(old),max_cardinality_matched=len(new),recall_delta=(len(new)-len(old))/m,old_pairs=old,new_pairs=new))
save('actual_case_matching_comparison.json',dict(comparisons=rows,improved_count=sum(r['max_cardinality_matched']>r['old_matched'] for r in rows),note='Only raw angular node diagnostic; B8L2 untouched. Edge recall cannot be inferred from count alone.'))
# Deterministic sample from all compact highlight arm rows, stratified phase,difficulty,status.
df=pd.read_csv(PKG/'analysis/composition/compact_block_evidence/01_highlight_events.csv.gz',keep_default_na=False); candidates={}
excluded={t['team_key'] for f in (PKG/'analysis/representative_cases/cases').glob('C[0-9]*.json') for t in json.loads(f.read_text())['teams']}
for row in df.to_dict('records'):
 for arm in ['A','B','C']:
  key=row[arm+'_team_key']
  if key in excluded:continue
  candidates[key]=dict(team_key=key,pool_id=row['pool_id'],phase=row['phase'],difficulty=row['difficulty'],score_status=row[arm+'_score_status'],B8L2=row[arm+'_B8L2'],D10=row[arm+'_D10'],nodes=row[arm+'_nodes'],complete=row[arm+'_complete'],rank=hashlib.sha256(key.encode()).hexdigest())
ordered=sorted(candidates.values(),key=lambda r:r['rank']);chosen=[];counts={}
for r in ordered:
 s=(r['phase'],r['difficulty'],r['score_status'])
 if counts.get(s,0)<2: chosen.append(r);counts[s]=counts.get(s,0)+1
for r in ordered:
 if len(chosen)>=36:break
 if r not in chosen:chosen.append(r)
requests={}
for phase in ['DISCOVERY','VALIDATION']:
 for r in read(OUT/'requests'/f'{phase}_BLOCK_REQUESTS.json.gz')['requests']:
  if r['team_key'] in {x['team_key'] for x in chosen}:requests[r['team_key']]=r
pools={p['pool_id']:p for p in fe.load_pools()}; result=[]
with fe.cached_matching(),fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
 for e in chosen:
  req=requests[e['team_key']];actual=fr.evaluate_one(pools[e['pool_id']],req['worker_ids'],engine,models)
  checks={}
  for field in ['B8L2','D10','nodes']:
   old=e[field];new=actual.get(field);old=None if old=='' else float(old)
   checks[field]=dict(expected=old,actual=new,delta=None if old is None or new is None else new-old,passed=(old is None and new is None) or (old is not None and new is not None and abs(new-old)<1e-9))
  checks['score_status']=dict(expected=e['score_status'],actual=actual['score_status'],passed=e['score_status']==actual['score_status'])
  checks['complete']=dict(expected=e['complete'],actual=actual['complete_evaluable'],passed=bool(e['complete'])==actual['complete_evaluable'])
  result.append(dict(selection=e,checks=checks,all_passed=all(v['passed'] for v in checks.values()),actual=actual));print(e['team_key'],result[-1]['all_passed'],flush=True)
  save('extra_team_replay.json',dict(selection_method='SHA256(team_key) ascending, first2 each phase/difficulty/score_status stratum then fill to36, excluding21 showcase teams',candidate_unique_n=len(candidates),sample_n=len(chosen),results=result,all_passed=all(r['all_passed'] for r in result),complete=len(result)==len(chosen),scope='Compact highlight evidence arms only; not random sample of entire583261 teams.'))
