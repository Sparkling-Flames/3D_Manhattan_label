"""One near-group-mean explanatory addition case; frozen full-state replay."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import json,gzip,sys,pandas as pd
P=BUDGET;OUT=BUDGET_CASES;OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ENGINE))
from new_team_engine import Engine,save,gs

x=pd.read_csv(OUT/'G117_LOW_HIGH_SELECTED.csv')
x=x[(x.panel_before=='SRCC23P_299c424d1beabe2b529a')&x.selected_mask.eq(45)]
assert len(x)==1
x.to_csv(OUT/'G117_LOW_HIGH_SELECTED.csv',index=False)
r=x.iloc[0].to_dict();pools=gs.pool_lookup();records=[];receipt=[]
for side in 'ab':
 pid=r['pool_id_'+side];pool=pools[pid]
 existing={t['team_key']:t for t in gs.read(NATIVE/'pools'/(pid+'.json.gz'))['teams']}
 with Engine(full_state=True) as eng:
  for phase in ['before','after']:
   key=r['team_'+phase+'_'+side];orig=existing[key];result=eng.evaluate(pool,orig['member_workers'])
   diff={m:abs(result[m]-orig[m]) for m in ['B8L2','D10','S_bottom_deg','dir','Hmean']};assert max(diff.values())<1e-8
   records.append(dict(case_id='G117_LOW_HIGH',side=side,phase=phase,
     event_explanation_key=r['series_id']+':mask45:low_to_high',pool_meta=pool['meta'],reference=pool['reference'],
     records=[o for o in pool['records'] if o['worker_id'] in orig['member_workers']],team=result))
   receipt.append(dict(case_id='G117_LOW_HIGH',side=side,phase=phase,team_key=key,n=orig['k'],
     source_endpoint='work/native/pools/'+pid+'.json.gz',max_metric_difference=max(diff.values()),
     selection='both views Q lower and turn loss; nearest to G117 group mean Q addition effect; explanatory only'))
save(OUT/'G117_LOW_HIGH_REPLAY.json.gz',records)
pd.DataFrame(receipt).to_csv(OUT/'G117_LOW_HIGH_REPLAY_RECEIPT.csv',index=False)
sys.path.insert(0,str(CODE_ROOT/'mechanisms'))
import analyze_case_states as ac
ac.P=OUT;ac.analyze('G117_LOW_HIGH')
print(pd.DataFrame(receipt).to_string(index=False))
