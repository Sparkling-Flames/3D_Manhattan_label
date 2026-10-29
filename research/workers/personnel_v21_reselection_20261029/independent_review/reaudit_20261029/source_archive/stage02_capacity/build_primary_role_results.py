"""Use each family's declared main historical axis; retain all role changes.

TARGET/RAW3: formal-hard turn rank. OPPSTRUCT: computable-challenge turn rank.
OPPJOINT: historical-Q rank. The former challenge summaries remain untouched.
"""
from pathlib import Path
import pandas as pd
from audit_large_blocks import image_stats

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'audit_capacity/completed_supplement'

def main():
    ranks=pd.read_csv(ROOT/'audit_comparison/abc_integrated/HISTORY_ROLE_RANKS_USED.csv')
    ranks.to_csv(OUT/'PRIMARY_ROLE_AXES_USED.csv',index=False,encoding='utf-8-sig')
    r=ranks.set_index(['method','heldout_building','class_id'])
    e=pd.read_csv(OUT/'COMPETITIVE_OLD_AND_NEW_EVENTS_Q.csv.gz',low_memory=False)
    values=pd.read_csv(OUT/'EVENTS_BOTH_CROSS_DEFINITIONS.csv.gz')
    metrics=['within_same_A','cross_same_A','gap_same_A','cross_symmetric','gap_symmetric','signed_CA','signed_CB']
    e=e.merge(values[['event_id']+metrics],on='event_id',validate='one_to_one')
    role=[]
    for row in e.itertuples():
        axis='hard_turn_rank_asc' if row.method in ['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'] else 'challenge_turn_rank_asc' if row.method=='OPPSTRUCT_K3' else 'q_rank_asc'
        s=r.loc[(row.method,row.building,row.source_class)];t=r.loc[(row.method,row.building,row.target_class)]
        role.append(dict(role_axis=axis,source_role_rank=int(s[axis]),target_role_rank=int(t[axis]),
                         primary_role_direction=f'{axis}:{int(s[axis])}/{int(s.k)}->{int(t[axis])}/{int(t.k)}'))
    e=pd.concat([e.reset_index(drop=True),pd.DataFrame(role)],axis=1)
    changed=ranks[ranks.method.isin(['TARGET_DSTRUCT_K3','V21_DSTRUCT_RAW3_K3'])&ranks.hard_turn_rank_asc.ne(ranks.challenge_turn_rank_asc)]
    changed.to_csv(OUT/'HARD_VS_CHALLENGE_CHANGED_FOLDS.csv',index=False,encoding='utf-8-sig')
    e['role_numeric_changed']=e.audit_role_direction.str.split(':').str[-1].ne(e.primary_role_direction.str.split(':').str[-1])
    ec=e[e.role_numeric_changed].copy()
    ec.to_csv(OUT/'HARD_VS_CHALLENGE_CHANGED_EVENTS.csv.gz',index=False,encoding='utf-8-sig')
    ec.groupby(['method','pool_id','image','building','source_class','target_class','n','m','audit_role_direction','primary_role_direction']).agg(events=('event_id','size')).to_csv(OUT/'HARD_VS_CHALLENGE_CHANGED_POOL_N_M.csv',encoding='utf-8-sig')
    keep=['event_id','pool_id','image','building','method','n','m','source_class','target_class','evidence_stage','role_axis','source_role_rank','target_role_rank','primary_role_direction','audit_role_direction','role_numeric_changed']+metrics
    e[keep].to_csv(OUT/'PRIMARY_ROLE_EVENTS_BOTH_CROSS_DEFINITIONS.csv.gz',index=False,encoding='utf-8-sig')
    rows=[];by_pool=[];keys=['method','role_axis','source_role_rank','target_role_rank','primary_role_direction','n','m']
    for stage,frame in [('new_supplement_only',e[e.evidence_stage.eq('new_supplement')]),('combined_coverage',e)]:
        for k,g in frame.groupby(keys):
            row=dict(zip(keys,k),summary_stage=stage,events=len(g),registered_images=g.image.nunique(),registered_buildings=g.building.nunique())
            for metric in metrics:row.update({metric+'_'+name:value for name,value in image_stats(g,metric).items()})
            rows.append(row)
        po=frame.groupby(keys+['pool_id','image','building'])[metrics].mean().reset_index();po['summary_stage']=stage;by_pool.append(po)
    pd.DataFrame(rows).to_csv(OUT/'PRIMARY_ROLE_DIRECTION_RESULTS.csv',index=False,encoding='utf-8-sig')
    p=pd.concat(by_pool,ignore_index=True)
    p.to_csv(OUT/'PRIMARY_ROLE_POOL_RESULTS.csv.gz',index=False,encoding='utf-8-sig')
    common=[]
    for stage in p.summary_stage.unique():
        a=p[p.summary_stage.eq(stage)&p.method.eq('V21_DSTRUCT_RAW3_K3')]
        b=p[p.summary_stage.eq(stage)&p.method.eq('TARGET_DSTRUCT_K3')]
        z=a.merge(b,on=['role_axis','source_role_rank','target_role_rank','n','m','pool_id','image','building'],suffixes=('_RAW3','_TARGET'),validate='one_to_one')
        for k,g in z.groupby(['source_role_rank','target_role_rank','n','m']):
            for metric in metrics:
                v=g.dropna(subset=[metric+'_RAW3',metric+'_TARGET']).groupby(['building','image'])[[metric+'_RAW3',metric+'_TARGET']].mean();diff=v[metric+'_RAW3']-v[metric+'_TARGET']
                common.append(dict(summary_stage=stage,source_role_rank=k[0],target_role_rank=k[1],n=k[2],m=k[3],metric=metric,
                    common_images=len(v),common_buildings=v.index.get_level_values('building').nunique(),RAW3_mean=v[metric+'_RAW3'].mean(),TARGET_mean=v[metric+'_TARGET'].mean(),
                    RAW3_larger_images=int(diff.gt(1e-9).sum()),TARGET_larger_images=int(diff.lt(-1e-9).sum()),equal_images=int(diff.abs().le(1e-9).sum()),
                    controls='same ordinary Manual pool,n/m,formal-hard turn rank; not all exact members/backgrounds or historical Q'))
    pd.DataFrame(common).to_csv(OUT/'PRIMARY_HARD_ROLE_COMMON_POOL_COMPARISON.csv',index=False,encoding='utf-8-sig')
    print('changed folded classes',len(changed),'changed events',len(ec),'changed images',ec.image.nunique(),'summary rows',len(rows))

if __name__=='__main__':main()
