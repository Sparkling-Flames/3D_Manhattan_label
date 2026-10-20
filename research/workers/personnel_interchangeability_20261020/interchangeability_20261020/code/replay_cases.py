"""Portable exact native replay using only embedded selected-case member input.

The complete inventory snapshot and any old native team cache are not read.
Frozen scientific code and measurement engine are supplied through --restored.
"""
from __future__ import annotations
import argparse,collections,copy,hashlib,json,math,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'analysis/composition'))
sys.path.insert(0,str(ROOT/'interchangeability_20261020/independent'))
import fusion_runner
import pair_diagnostics
from design_history_panel import read,write,team_key,digest

SCORE_FIELDS=['B8L2','D10','IoU3D100','iou_2d','omission','extension','Hmean','Hcenter',
 'height_mean_ratio','nodes','minimum_support','node_supports','complete_evaluable',
 'complete_floor_evaluable','geometry_reason','score_status','ref_node_recall_9','ref_edge_recall_9']

def compare(expected,actual,tol=1e-9):
 if expected is None or actual is None:return expected is actual,0.0 if expected is actual else None
 if isinstance(expected,bool) or isinstance(actual,bool):return expected==actual,0.0
 if isinstance(expected,(int,float)) and isinstance(actual,(int,float)):
  if not(math.isfinite(expected) and math.isfinite(actual)):return False,None
  d=abs(expected-actual);return d<=tol,d
 if isinstance(expected,list) and isinstance(actual,list):
  if len(expected)!=len(actual):return False,None
  pairs=[compare(x,y,tol) for x,y in zip(expected,actual)]
  return all(x[0] for x in pairs),max((x[1] for x in pairs if x[1] is not None),default=0.)
 if isinstance(expected,dict) and isinstance(actual,dict):
  if set(expected)!=set(actual):return False,None
  pairs=[compare(expected[k],actual[k],tol) for k in expected]
  return all(x[0] for x in pairs),max((x[1] for x in pairs if x[1] is not None),default=0.)
 return expected==actual,0.0

def check_event(case,by_worker,event=None):
 e=event or case.get('event')
 if not e:return {'exact_event_available':False}
 sets={arm:set(e[arm+'_workers']) for arm in 'ABC'};core=set(e['core_workers']);n=e['n'];m=e['m']
 assert all(len(x)==n for x in sets.values())
 assert sets['A']&sets['B']==sets['A']&sets['C']==core and len(core)==n-m
 assert len(sets['A']-sets['B'])==len(sets['A']-sets['C'])==m
 classes=case['worker_classes'];observed={arm:dict(sorted(collections.Counter(classes[w] for w in ws).items())) for arm,ws in sets.items()}
 assert observed['A']==observed['B']==e['A_counts'] and observed['C']==e['C_counts']
 assert observed['A']!=observed['C']
 for arm in 'ABC':assert team_key(case['pool_id'],sets[arm])==e[arm+'_team_key']
 source={arm:dict(collections.Counter(by_worker[w]['origin'] for w in ws)) for arm,ws in sets.items()}
 if e['matching']=='source_matched':assert source['A']==source['B']==source['C']
 return dict(exact_event_available=True,same_core=True,n=n,actual_m_AB=m,actual_m_AC=m,
   source_counts_equal=source['A']==source['B']==source['C'],class_count_vectors=observed)

def replay(case,fe,engine,models):
 pool=case['embedded_pool'];by_worker={r['worker_id']:r for r in pool['records']}
 assert len(by_worker)==len(pool['records'])
 assert case['pool_id']==pool['pool_id'] and case['scientific_commit']==fe.COMMIT
 assert case['fusion_parameters']['gap']==fe.WORKING_GAP
 evidence=check_event(case,by_worker)
 extra_evidence=[check_event(case,by_worker,e) for e in case.get('additional_events',[])]
 teams=[];rows=[];errors=[]
 for expected in case['teams']:
  ws=expected['member_workers'];assert len(ws)==len(set(ws))==expected['k']
  assert expected['team_key']==team_key(pool['pool_id'],ws)
  actual=fusion_runner.evaluate_one(pool,ws,engine,models)
  failures=[];max_delta=0.
  for field in SCORE_FIELDS+['geometry','member_workers','member_object_ids','team_key','reference_id']:
   ok,delta=compare(expected.get(field),actual.get(field))
   if not ok:failures.append(field)
   if delta is not None:max_delta=max(max_delta,delta)
  assert sorted(actual['member_workers'])==sorted(ws)
  rows.append(dict(team_key=actual['team_key'],k=actual['k'],fields_checked=len(SCORE_FIELDS)+6,
   max_abs_difference=max_delta,geometry_byte_equivalent=digest(expected.get('geometry'))==digest(actual.get('geometry')),
   failure_fields=failures,score_status=actual['score_status']))
  teams.append(actual)
  errors.extend([actual['team_key']+':'+x for x in failures])
 bykey={t['team_key']:t for t in teams};pairs=[]
 for old in case.get('pairs',[]):
  fn=pair_diagnostics.geometry_metrics if old.get('metric_kind')=='nested_geometry' else pair_diagnostics.pair_metrics
  actual=fn(bykey[old['a_team_key']],bykey[old['b_team_key']],cache={})
  fields=old['metrics'];failures=[];max_delta=0.
  for k,v in fields.items():
   ok,delta=compare(v,actual.get(k))
   if not ok:failures.append(k)
   if delta is not None:max_delta=max(max_delta,delta)
  pairs.append(dict(pair=old.get('label'),fields_checked=len(fields),max_abs_difference=max_delta,failure_fields=failures))
  errors.extend(['pair:'+str(old.get('label'))+':'+x for x in failures])
 return dict(case_id=case['case_id'],pool_id=pool['pool_id'],image=pool['meta']['image'],building=pool['meta']['building'],
  embedded_member_n=len(by_worker),reference_sha256=digest(pool['reference']),records_sha256=digest(pool['records']),
  full_snapshot_read=False,old_team_cache_read=False,event_assertions=evidence,additional_event_assertions=extra_evidence,teams=rows,pairs=pairs,
  all_passed=not errors,failures=errors)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--restored',type=Path,required=True)
 ap.add_argument('--cases',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 fe=fusion_runner.init_engine(a.restored)
 def forbidden(*args,**kwargs):raise AssertionError('Quick replay must not load the complete input snapshot')
 fe.load_pools=forbidden
 with fe.cached_matching():
  with fe.scoring_engine(fe.ENGINE/'measurement_engine.zip',fe.ENGINE/'working_models.py') as (engine,models):
   rows=[]
   for path in sorted(a.cases.glob('S*.json')):
    row=replay(read(path),fe,engine,models);row['case_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    rows.append(row);write(a.out/(path.stem+'.replay.json'),row)
    print(json.dumps(dict(case_id=row['case_id'],teams=len(row['teams']),all_passed=row['all_passed'])),flush=True)
 assert rows
 result=dict(cases=rows,all_passed=all(r['all_passed'] for r in rows),teams=sum(len(r['teams']) for r in rows),
  unique_teams=len({t['team_key'] for r in rows for t in r['teams']}),
  images=len({r['image'] for r in rows}),buildings=len({r['building'] for r in rows}),
  entry_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scientific_commit=fe.COMMIT,
  scope='Actual independent native fusion and B8L2/D10 measurement from embedded case inputs. Not a replay of every search team; no full snapshot or cached outcomes read.')
 write(a.out/'REPLAY_RECEIPT.json',result)
 assert result['all_passed'],result

if __name__=='__main__':main()
