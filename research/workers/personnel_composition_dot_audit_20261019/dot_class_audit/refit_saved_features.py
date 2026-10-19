import os
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
import sys,json,time
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import adjusted_rand_score
root=Path('/workspace/shared/composition_audit_20261019/extracted/personnel_composition_study_20261019/analysis')
out=Path('/workspace/shared/composition_audit_20261019/dot_class_audit')
sys.path[:0]=[str(root/'forward'),str(root/'reverse')]
import build_forward as fwd
import discover_reverse_composition as rev
f=pd.read_csv(root/'forward/results/features_train.csv.gz'); labels=pd.read_csv(root/'forward/results/worker_labels.csv.gz')
cat=fwd.candidates(f,f.train_key.iloc[0]); new=pd.DataFrame(cat.rows)
keys=['method_id','domain','worker_id']; join=labels.merge(new,on=keys,suffixes=('_old','_new'),validate='one_to_one')
rows=[]
for key,g in join.groupby(['method_id','domain']):
 rows.append(dict(method_id=key[0],domain=key[1],changed_labels=int(g.class_id_old.ne(g.class_id_new).sum()),ari=adjusted_rand_score(g.class_id_old,g.class_id_new)))
pd.DataFrame(rows).to_csv(out/'forward_saved_features_refit.csv',index=False)
roles=pd.read_csv(root/'reverse/historical_roles.csv.gz');labs=pd.read_csv(root/'reverse/worker_labels.csv.gz');rows=[]
for spec in rev.specifications():
 if spec['family']!='historical_role':continue
 for dom in rev.DIFFICULTIES if spec['conditional'] else ['global']:
  rf=roles[roles.domain.eq(dom)].set_index('worker_id'); eligible=rf[rf.supported].index.tolist()
  new,_=rev.fit_roles(rf,eligible,spec['k'],spec['algorithm']);old=labs[(labs.method_id==spec['method_id'])&(labs.domain==dom)&labs.known].set_index('worker_id').class_id.to_dict()
  rows.append(dict(method_id=spec['method_id'],domain=dom,known=len(old),changed_labels=sum(old.get(w)!=new.get(w) for w in set(old)|set(new)),ari=adjusted_rand_score(list(old.values()),[new.get(w,'unknown') for w in old])))
pd.DataFrame(rows).to_csv(out/'reverse_saved_roles_refit.csv',index=False)
sel=pd.read_csv(root/'SELECTED_WORKER_CLASSES.csv'); rh=sel[(sel.R_role.eq('C05'))|sel.H_hard_role.eq('C02')].merge(f.drop(columns=['train_key']),on='worker_id',suffixes=('','_full'))
cols=['worker_id','person_origin','R_role','H_hard_role','q_beta','q_abs_mean','theta_easy','theta_medium','theta_hard','hard_minus_easy','hard_minus_medium','pair_count_effect']
rh[cols].to_csv(out/'R5_H2_members_traits.csv',index=False)
summary={'forward_methods':len(cat.methods),'forward_labels':len(join),'forward_changed_labels':int(join.class_id_old.ne(join.class_id_new).sum()),'reverse_role_method_domains':len(rows),'reverse_role_changed_labels':sum(r['changed_labels'] for r in rows),'R5_members':sorted(sel.loc[sel.R_role.eq('C05'),'worker_id']),'H2_members':sorted(sel.loc[sel.H_hard_role.eq('C02'),'worker_id']),'R5_traits_mean':rh[rh.R_role.eq('C05')][cols[4:]].mean().to_dict(),'H2_traits_mean':rh[rh.H_hard_role.eq('C02')][cols[4:]].mean().to_dict()}
(out/'SAVED_FEATURE_REFIT.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
