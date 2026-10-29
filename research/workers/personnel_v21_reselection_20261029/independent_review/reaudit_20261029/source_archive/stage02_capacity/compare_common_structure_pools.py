"""Pair same-picture, n/m and historical structure-rank conditions.

This controls pool and condition support, not identical people/backgrounds or
historical Q. These limitations are explicit in every comparison row.
"""
from pathlib import Path
import itertools
import pandas as pd
import numpy as np

OUT=Path(__file__).resolve().parent/'completed_supplement'

def main():
    p=pd.read_csv(OUT/'INDEPENDENT_Q_BY_DIRECTED_POOL.csv.gz')
    rows=[]
    for stage in ['new_supplement_only','combined_coverage']:
        for other in ['TARGET_DSTRUCT_K3','OPPSTRUCT_K3']:
            a=p[p.evidence_stage.eq(stage)&p.method.eq('V21_DSTRUCT_RAW3_K3')]
            b=p[p.evidence_stage.eq(stage)&p.method.eq(other)]
            k=['audit_role_direction','n','m','pool_id','image','building']
            z=a.merge(b,on=k,suffixes=('_RAW3','_other'),validate='one_to_one')
            for group,g in z.groupby(['audit_role_direction','n','m']):
                for metric in ['Q_CA','Q_CB','Q_within','Q_cross','Q_gap']:
                    valid=g.dropna(subset=[metric+'_RAW3',metric+'_other']).copy()
                    v=valid.groupby(['building','image'])[[metric+'_RAW3',metric+'_other']].mean()
                    delta=v[metric+'_RAW3']-v[metric+'_other']
                    rows.append(dict(other_method=other,evidence_stage=stage,audit_role_direction=group[0],n=group[1],m=group[2],metric=metric,
                                     common_images=len(v),common_buildings=v.index.get_level_values('building').nunique(),
                                     RAW3_mean_image=v[metric+'_RAW3'].mean(),other_mean_image=v[metric+'_other'].mean(),
                                     RAW3_mean_building=v[metric+'_RAW3'].groupby(level='building').mean().mean(),
                                     other_mean_building=v[metric+'_other'].groupby(level='building').mean().mean(),
                                     paired_RAW3_minus_other_mean=delta.mean(),RAW3_larger_images=int(delta.gt(1e-9).sum()),
                                     other_larger_images=int(delta.lt(-1e-9).sum()),
                                     comparison_controls='same ordinary Manual target pool, same n/m, same historical challenge-turn rank direction; pool/image/building equal aggregation',
                                     not_controlled='exact D/X/Y/Z and individual historical Q; this is not an identical-person or Q-adjusted causal comparison'))
    pd.DataFrame(rows).to_csv(OUT/'RAW3_STRUCT_COMMON_POOL_Q_COMPARISON.csv',index=False,encoding='utf-8-sig')
    print('rows',len(rows))

if __name__=='__main__':main()
