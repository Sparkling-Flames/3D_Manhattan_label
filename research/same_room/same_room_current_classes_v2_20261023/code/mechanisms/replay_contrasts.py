"""Replay selected explanatory cases with frozen native state; zero new selection."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import json,pandas as pd,sys,gzip,argparse
P=MECHANISMS;sys.path.insert(0,str(ENGINE))
from new_team_engine import Engine,save,gs
p=argparse.ArgumentParser();p.add_argument('selected_csv');p.add_argument('--prefix',required=True);a=p.parse_args()
sel=pd.read_csv(a.selected_csv);pools=gs.pool_lookup();records=[];expected=[]
for r in sel.to_dict('records'):
 for side in ['a','b']:
  pid=r['pool_id_'+side];pool=pools[pid];old={x['team_key']:x for x in gs.read(NATIVE/'pools'/(pid+'.json.gz'))['teams']}
  with Engine(full_state=True) as engine:
   for phase in ['before','after']:
    key=r[f'team_{side}_{phase}'];base=old[key];result=engine.evaluate(pool,base['member_workers'])
    checks={m:abs(result[m]-base[m]) for m in ['B8L2','D10','S_bottom_deg','dir','Hmean'] if result.get(m) is not None and base.get(m) is not None}
    assert all(v<1e-8 for v in checks.values()),checks
    records.append(dict(case_id=a.prefix,side=side,phase=phase,event_explanation_key=r['event_explanation_key'],pool_meta=pool['meta'],reference=pool['reference'],records=[q for q in pool['records'] if q['worker_id'] in base['member_workers']],team=result))
    expected.append(dict(case_id=a.prefix,image=pool['meta']['image'],side=side,phase=phase,team_key=key,original_endpoint_file=str(NATIVE/'pools'/(pid+'.json.gz')),max_metric_difference=max(checks.values()),full_state_keys='|'.join(result.get('full_state',{}))))
save(P/(a.prefix+'_REPLAY.json.gz'),records);pd.DataFrame(expected).to_csv(P/(a.prefix+'_REPLAY_RECEIPT.csv'),index=False)
print(pd.DataFrame(expected).to_string(index=False));print('state header',str(records[0]['team'].get('full_state'))[:7000])
