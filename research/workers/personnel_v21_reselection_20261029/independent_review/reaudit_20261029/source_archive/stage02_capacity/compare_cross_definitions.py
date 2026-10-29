"""Keep common-A and symmetric cross amplitudes explicit and side by side."""
from pathlib import Path
import pandas as pd
import numpy as np
from audit_large_blocks import image_stats

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'completed_supplement'

def main():
    e=pd.read_csv(OUT/'COMPETITIVE_OLD_AND_NEW_EVENTS_Q.csv.gz',low_memory=False)
    valid=e[['A_Q','B_Q','C_Q']].notna().all(axis=1)
    e['within_same_A']=(e.B_Q-e.A_Q).abs().where(valid)
    e['cross_same_A']=(e.C_Q-e.A_Q).abs().where(valid)
    e['gap_same_A']=e.cross_same_A-e.within_same_A
    e['cross_symmetric']=((e.C_Q-e.A_Q).abs()+(e.C_Q-e.B_Q).abs()).div(2).where(valid)
    e['gap_symmetric']=e.cross_symmetric-e.within_same_A
    e['signed_CA']=e.C_Q-e.A_Q;e['signed_CB']=e.C_Q-e.B_Q
    metrics=['within_same_A','cross_same_A','gap_same_A','cross_symmetric','gap_symmetric','signed_CA','signed_CB']
    keys=['method','audit_role_direction','n','m']
    e[['event_id','pool_id','image','building','evidence_stage']+keys+['A_Q','B_Q','C_Q']+metrics].to_csv(OUT/'EVENTS_BOTH_CROSS_DEFINITIONS.csv.gz',index=False,encoding='utf-8-sig')
    rows=[];by_pool=[]
    for stage,frame in [('new_supplement_only',e[e.evidence_stage.eq('new_supplement')]),('combined_coverage',e)]:
        for k,g in frame.groupby(keys):
            r=dict(zip(keys,k),evidence_stage=stage,events=len(g),registered_images=g.image.nunique())
            for metric in metrics:r.update({metric+'_'+name:value for name,value in image_stats(g,metric).items()})
            rows.append(r)
        po=frame.groupby(keys+['pool_id','image','building'])[metrics].mean().reset_index()
        po['summary_stage']=stage;by_pool.append(po)
    pd.DataFrame(rows).to_csv(OUT/'RESULTS_BOTH_CROSS_DEFINITIONS.csv',index=False,encoding='utf-8-sig')
    p=pd.concat(by_pool,ignore_index=True)
    p.to_csv(OUT/'POOL_RESULTS_BOTH_CROSS_DEFINITIONS.csv.gz',index=False,encoding='utf-8-sig')
    comparisons=[]
    for stage in p.summary_stage.unique():
        a=p[p.summary_stage.eq(stage)&p.method.eq('V21_DSTRUCT_RAW3_K3')]
        for other in ['TARGET_DSTRUCT_K3','OPPSTRUCT_K3']:
            b=p[p.summary_stage.eq(stage)&p.method.eq(other)]
            z=a.merge(b,on=['audit_role_direction','n','m','pool_id','image','building'],suffixes=('_RAW3','_other'),validate='one_to_one')
            for group,g in z.groupby(['audit_role_direction','n','m']):
                for metric in metrics:
                    v=g.dropna(subset=[metric+'_RAW3',metric+'_other']).groupby(['building','image'])[[metric+'_RAW3',metric+'_other']].mean()
                    delta=v[metric+'_RAW3']-v[metric+'_other']
                    comparisons.append(dict(other_method=other,evidence_stage=stage,audit_role_direction=group[0],n=group[1],m=group[2],metric=metric,
                        common_images=len(v),common_buildings=v.index.get_level_values('building').nunique(),RAW3_mean_image=v[metric+'_RAW3'].mean(),
                        other_mean_image=v[metric+'_other'].mean(),RAW3_larger_images=int(delta.gt(1e-9).sum()),other_larger_images=int(delta.lt(-1e-9).sum()),
                        equal_images=int(delta.abs().le(1e-9).sum()),controls='same pool,n/m,structure-role ranks; actual members and background need not coincide'))
    pd.DataFrame(comparisons).to_csv(OUT/'COMMON_POOLS_BOTH_CROSS_DEFINITIONS.csv',index=False,encoding='utf-8-sig')
    print('events',len(e),'direction rows',len(rows),'common rows',len(comparisons))

if __name__=='__main__':main()
