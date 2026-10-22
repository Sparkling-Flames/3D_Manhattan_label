"""Copy four already computed endpoints and their frozen input observations.

This is saved-result extraction, not an extra fusion run or full-state replay.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import pandas as pd,sys
P=MECHANISMS;sys.path.insert(0,str(ENGINE))
from new_team_engine import gs,save
from local_study_paths import choose

input_path=choose(WORK/'taxonomy_response/cases/CASE_G015_SAME_CLASS_W104_W120.csv',WORK/'cases/taxonomy/CASE_G015_SAME_CLASS_W104_W120.csv',WORK/'cases/taxonomy_response/CASE_G015_SAME_CLASS_W104_W120.csv')
df=pd.read_csv(input_path);panels=pd.read_csv(WORK/'design/PANELS.csv').set_index('panel_id')
panel=panels.loc[df.panel_id.iloc[0]];pools=gs.pool_lookup();out=[];receipt=[]
for side in 'ab':
 pid=panel['pool_id_'+side];p=pools[pid]
 endpoint_path=NATIVE/'pools'/(pid+'.json.gz')
 endpoints={r['team_key']:r for r in gs.read(endpoint_path)['teams']}
 for i,phase in enumerate(['before','after']):
  key=df.iloc[i]['team_key_'+side];t=endpoints[key]
  out.append(dict(case_id='G015_current_same_class',side=side,phase=phase,
   event_explanation_key='G015_n7_W104_to_W120',retrieval_kind='saved_endpoint_copy_not_replay',
   pool_meta=p['meta'],reference=p['reference'],records=[r for r in p['records'] if r['worker_id'] in t['member_workers']],team=t))
  receipt.append(dict(case_id='G015_current_same_class',side=side,phase=phase,team_key=key,
   endpoint_file=str(endpoint_path),selection_file=str(input_path),new_fusion_performed=False,
   full_state_saved='full_state' in t,repository_commit=t['repository_commit']))
save(P/'G015_current_same_class_EVIDENCE.json.gz',out)
pd.DataFrame(receipt).to_csv(P/'G015_current_same_class_EXTRACTION_RECEIPT.csv',index=False)
print(pd.DataFrame(receipt).to_string(index=False))
