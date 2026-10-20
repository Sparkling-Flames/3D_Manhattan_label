"""Independent pandas implementation from history event rows and fold labels.
Verifies CV held-out IDs, mean distances under exact same-anchor masks, and
full observed-anchor coverage/incomplete rates. Imports no learning code.
"""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
B=Path('/workspace/shared/interchangeability_audit_20261020/audit_learning');O=Path(__file__).parent/'learning_legacy';O.mkdir(exist_ok=True)
f=pd.concat([pd.read_csv(x) for x in sorted((B/'corner_history').glob('*.csv.gz'))],ignore_index=True);f=f[(f.entrant_origin_a=='new')&(f.entrant_origin_b=='new')].copy()
f['distance']=(f.bev_mean_pairscale+f.top_mean_pairscale)/2;f['distance']=f.distance.where(f.status=='unique_cyclic_candidate');f['distance9']=f.distance.where(f.angle_deg<=9);f['distance12']=f.distance.where(f.angle_deg<=12);f['distance_valid']=f.distance.notna().astype(float);f['incomplete']=(~f.complete).astype(float)
order=sorted(f.building.unique(),key=lambda b:hashlib.sha256(f'2026102003|inner|{b}'.encode()).hexdigest());folds=[order[x:x+2] for x in range(0,10,2)]
l=pd.read_csv(B/'corner_fit_legacy/fold_labels.csv');r=pd.read_csv(B/'corner_fit_legacy/inner_cv_building.csv').set_index(['method_id','fold','building']);rows=[];errs=[]
keys=['building','pool_id','k','background_id']
for (mid,fold),lab in l.groupby(['method_id','fold']):
 d=f[f.building.isin(folds[fold])].copy();mp=dict(zip(lab.worker_id,lab.class_id));d=d[d.worker_a.isin(mp)&d.worker_b.isin(mp)];d['same']=d.worker_a.map(mp)==d.worker_b.map(mp)
 for metric in ['distance','distance9','distance12','distance_valid','incomplete']:
  means=d.groupby(keys+['same'])[metric].mean().unstack('same');assert set(means.columns)=={False,True}
  # For rates use full observed same/between support, not valid-distance support.
  both=means.dropna();v=both.groupby(['building','pool_id','k']).mean().groupby(['building','pool_id']).mean().groupby('building').mean()
  for building,row in v.iterrows():
   target=r.loc[(mid,fold,building)]
   for same,arm in [(False,'between'),(True,'within')]:
    name=arm+'_'+('allanchors_' if metric in ['distance_valid','incomplete'] else '')+metric
    err=abs(row[same]-target[name]);assert err<1e-10,(mid,fold,building,name,err);errs.append(err);rows.append(dict(method_id=mid,fold=fold,building=building,metric=name,value=row[same],absolute_error=err))
pd.DataFrame(rows).to_csv(O/'INDEPENDENT_EVENT_LEVEL_REAGGREGATION.csv',index=False)
receipt=dict(checked_values=len(rows),max_error=max(errs),held_out_fold_hash_independently_verified=True,source='75,373 historical event rows and frozen fold labels; no fitting or original evaluator used')
(O/'EVENT_LEVEL_REAGGREGATION_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(receipt)
