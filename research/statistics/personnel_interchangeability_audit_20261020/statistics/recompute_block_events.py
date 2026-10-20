from pathlib import Path
import pandas as pd,numpy as np,hashlib,json
R=Path(__file__).resolve().parent.parent;f=pd.read_csv(R/'audit_corner/history_block_metrics/COMMON_ENDPOINT_PAIRS.csv.gz',low_memory=False);l=pd.read_csv(R/'audit_learning/block_fit/fold_labels.csv');target=pd.read_csv(R/'audit_learning/block_fit/inner_cv_building.csv').set_index(['method_id','fold','building']);order=sorted(f.building.unique(),key=lambda b:hashlib.sha256(f'2026102003|inner|{b}'.encode()).hexdigest());folds=[order[i:i+2] for i in range(0,10,2)];f['distance']=.5*(f.bev_mean_pairscale+f.top_mean_pairscale);f.loc[~f.status.eq('unique_cyclic_candidate'),'distance']=np.nan
errs=[]
for (mid,fold),lab in l.groupby(['method_id','fold']):
 mp=lab.set_index('worker_id').class_id.to_dict();d=f[f.building.isin(folds[fold])].copy()
 for side in ['left','right']:d[side+'_vec']=d[side+'_workers'].map(lambda x:tuple(sorted(mp[w] for w in x.split('|'))) if all(w in mp for w in x.split('|')) else None)
 d=d[d.left_vec.notna()&d.right_vec.notna()];d['same']=d.left_vec==d.right_vec
 for metric in ['distance','bev_mean_h','top_mean_h','bev_max_h','top_max_h']:
  a=d.groupby(['building','pool_id','n','anchor_id','same'])[metric].mean().unstack('same').dropna();b=a.groupby(['building','pool_id','n']).mean().groupby(['building','pool_id']).mean().groupby('building').mean()
  for building,row in b.iterrows():
   for arm,flag in [('within',True),('between',False)]:
    err=abs(row[flag]-target.loc[(mid,fold,building),arm+'_'+metric]);assert err<1e-10,(mid,building,metric,err);errs.append(err)
r=dict(raw_pair_rows=len(f),independent_event_values=len(errs),max_error=max(errs),exact_heldout_hash_folds=True,description='No evaluator import; exact sorted two-person class-count vectors; conditional two-arm common anchors, then anchor/n/image/building.')
(R/'audit_statistics/block_fit/EVENT_REAGGREGATION_RECEIPT.json').write_text(json.dumps(r,indent=2));print(r)
