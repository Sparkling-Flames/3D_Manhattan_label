"""Reaggregate original-answer pair distances under independently checked LOBO labels."""
from pathlib import Path
import pandas as pd
import numpy as np
OUT=Path(__file__).resolve().parent
ROOT=OUT.parent/'unpacked/06A/research/workers/personnel_exchange_discrimination_20261025'
pairs=pd.read_csv(ROOT/'features/RAW_ORIGINAL_PAIR_DISTANCES.csv.gz')
labels=pd.read_csv(ROOT/'classifications/CANDIDATE_LABELS_COMPLETE_ALL_LOBO.csv.gz')
saved=pd.read_csv(ROOT/'classifications/HELDOUT_RAW_DISTANCE_SUMMARY.csv')
results=[]
for method in ['DSTRUCT_K2','DSTRUCT_K3','MSDGEOM_SCOPE_K4']:
    lab=labels[labels.method.eq(method)&labels.known&labels.heldout_building.ne('ALL')][['heldout_building','worker_id','class_id']]
    d=pairs[pairs.pool_layer.eq('ordinary_manual')&pairs.difficulty.eq('困难')].copy()
    for suffix in ['a','b']:
        d=d.merge(lab.rename(columns={'heldout_building':'building','worker_id':f'worker_{suffix}','class_id':f'class_{suffix}'}),on=['building',f'worker_{suffix}'],how='inner',validate='many_to_one')
    for subset,metric in [('all_pairs','turn_difference'),('same_corner_count','top_difference_deg'),('same_corner_count','bottom_difference_deg')]:
        rows=d[d.same_corner_count] if subset=='same_corner_count' else d
        counts=rows.assign(type=np.where(rows.class_a.eq(rows.class_b),'within','cross')).groupby(['pool_id','type']).size().unstack(fill_value=0)
        eligible=counts.index[counts.within.ge(4)&counts.cross.ge(4)]
        rows=rows[rows.pool_id.isin(eligible)&rows[metric].notna()].copy()
        rows['classpair']=rows.apply(lambda r:'|'.join(sorted([r.class_a,r.class_b])),axis=1)
        rows['type']=np.where(rows.class_a.eq(rows.class_b),'within','cross')
        byclass=rows.groupby(['pool_id','image_id','building','type','classpair'])[metric].mean()
        byimage=byclass.groupby(['pool_id','image_id','building','type']).mean().unstack('type').dropna()
        bybuilding=byimage.groupby('building')[['within','cross']].mean()
        old=saved[saved.method.eq(method)&saved.condition.eq('manual')&saved.pool_layer.eq('ordinary_manual')&saved.difficulty.eq('困难')&saved.subset.eq(subset)&saved.metric.eq(metric)].iloc[0]
        new=dict(method=method,subset=subset,metric=metric,images=len(byimage),buildings=len(bybuilding),image_within=byimage.within.mean(),image_cross=byimage.cross.mean(),images_cross_larger=int(byimage.cross.gt(byimage.within+1e-12).sum()),building_within=bybuilding.within.mean(),building_cross=bybuilding.cross.mean(),buildings_cross_larger=int(bybuilding.cross.gt(bybuilding.within+1e-12).sum()))
        for key,value in new.items():
            if key in ['method','subset','metric']:continue
            assert np.isclose(value,old[key],atol=1e-9,rtol=1e-9),(key,value,old[key])
        results.append(new)
pd.DataFrame(results).to_csv(OUT/'CHECKS_RAW_SEPARATION.csv',index=False)
print(pd.DataFrame(results).to_string(index=False))
