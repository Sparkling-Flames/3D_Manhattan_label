"""Inventory completed exchange stages without counting reused teams twice."""
from pathlib import Path
import json
import pandas as pd

W=Path(__file__).resolve().parents[1]
def main():
 stages=['global_screen','focused','fixed_A_m','direct_AC','refinement','member_sensitivity'];rows=[];teams={};native=set()
 for name in stages:
  ep=W/'experiment'/(name+'_endpoints');de=W/'experiment'/(name+'_design')
  receipt=json.loads((ep/'CUMULATIVE_COMPLETION.json').read_text());assert receipt['all_requests_completed']
  r=pd.read_csv(de/'REQUESTS.csv.gz');s=pd.read_csv(ep/'ENDPOINT_SCALARS.csv.gz',usecols=['team_key','B8L2','endpoint_reused'])
  assert len(r)==len(s) and set(r.team_key)==set(s.team_key)
  for row in r.to_dict('records'):
   identity=(row['pool_id'],row['n'],row['member_workers'],row['input_pool_sha256'])
   if row['team_key'] in teams:assert teams[row['team_key']]==identity
   else:teams[row['team_key']]=identity
  nk=set(s.loc[~s.endpoint_reused.astype(bool),'team_key']);assert not nk&native;native.update(nk)
  rows.append(dict(stage=name,requests=len(r),pools=r.pool_id.nunique(),new_native=receipt['cumulative_native_endpoints'],reused=receipt['cumulative_reused_endpoints'],
   Q_available=receipt['Q_available'],Q_missing=receipt['Q_missing'],requests_file=str((de/'REQUESTS.csv.gz').relative_to(W)),scalars_file=str((ep/'ENDPOINT_SCALARS.csv.gz').relative_to(W)),complete=True))
 eventstages=['global_screen','focused','fixed_A_m','direct_AC','refinement_baseline','refinement_m','refinement_AC','member_sensitivity']
 eventrows=[];ids=set();abc=set();abc_unordered=set();ac=set()
 for name in eventstages:
  fn=W/'experiment'/(name+'_design')/'EVENTS_EXACT.csv.gz';cols=pd.read_csv(fn,nrows=0).columns
  use=[c for c in ['event_id','pool_id','A_team_key','B_team_key','C_team_key','n','m'] if c in cols];d=pd.read_csv(fn,usecols=use)
  ids.update(d.event_id)
  if 'B_team_key' in d:
   for r in d.to_dict('records'):
    abc.add((r['A_team_key'],r['B_team_key'],r['C_team_key']))
    abc_unordered.add((tuple(sorted([r['A_team_key'],r['B_team_key']])),r['C_team_key']))
   design='strict_ABC'
  else:
   ac.update(zip(d.A_team_key,d.C_team_key));design='direct_AC_no_B'
  eventrows.append(dict(stage=name,events=len(d),pools=d.pool_id.nunique(),design=design,events_file=str(fn.relative_to(W))))
 out=W/'experiment';pd.DataFrame(rows).to_csv(out/'COMPLETED_ENDPOINT_STAGES.csv',index=False);pd.DataFrame(eventrows).to_csv(out/'COMPLETED_EVENT_STAGES.csv',index=False)
 ledger=dict(source_commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',all_listed_stages_complete=True,
  endpoint_stage_rows=sum(r['requests'] for r in rows),distinct_actual_team_endpoints=len(teams),distinct_native_fusions=len(native),
  new_native_duplicate_across_stages=0,event_stage_rows=sum(r['events'] for r in eventrows),distinct_method_event_ids=len(ids),
  distinct_ordered_ABC_team_triples=len(abc),distinct_ABC_triples_with_A_B_order_ignored=len(abc_unordered),distinct_ordered_direct_AC_pairs=len(ac),
  endpoint_stages=rows,event_stages=eventrows,interpretation='Events sharing endpoint teams are correlated; these totals are coverage, not independent statistical evidence. Separate methods/phase comparisons remain separate.',
  scope='This ledger covers exchange experiments managed by this round; composition panels, raw-answer pairs, prefix experiments and case-state replays have their own ledgers.')
 (out/'ALL_EXCHANGE_EXECUTION_LEDGER.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in ledger.items() if k not in ['endpoint_stages','event_stages']},ensure_ascii=False))
if __name__=='__main__':main()
