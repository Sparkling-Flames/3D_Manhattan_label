#!/usr/bin/env python3
"""Difficulty/opportunity strata for the exact adopted/comparison roles, phase separated."""
from pathlib import Path
import pandas as pd
from summarize_exchange import aggregate,separation_table,effect_long,BASE,POOL,write_csv

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis'
STEMS=['B8L2','D10','IoU3D100','geometry_bev_distance','geometry_pair_angle','geometry_top_angle',
       'geometry_bottom_angle','nodes','floor_turn5_n','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg']
RISKS=['A_failed','B_failed','C_failed','C_loss10_CA','C_loss10_CB','C_failure_or_loss10_CA',
       'C_failure_or_loss10_CB','record_time_CA_pct','record_time_CB_pct']

def main():
    selected=pd.read_csv(OUT/'FINAL_CONDITIONS_COMPACT.csv')[BASE+['role']].drop_duplicates()
    keep=set(POOL+['role','fair_role','branch','semantic_role','n_events','n_metric_records','n_pending']+RISKS)
    for s in STEMS:
        for x in ['within','cross','gap','BA','CA','CB']:
            keep.add(s+'_'+x);keep.add(s+'_'+x+'__event_n')
    for r in RISKS:keep.add(r+'__event_n')
    pools=[]
    for stage in selected.stage.unique():
        fn='REVERSE_BRANCH_POOL_SUMMARY.csv.gz' if stage.startswith('reverse') else 'FAIR_ROLE_POOL_SUMMARY.csv.gz'
        p=pd.read_csv(OUT/stage/fn,usecols=lambda c:c in keep)
        p=p.rename(columns={'fair_role':'role','branch':'role'})
        if not stage.startswith('reverse'):
            sp=pd.read_csv(OUT/stage/'POOL_ROLE_SUMMARY.csv.gz',usecols=lambda c:c in keep).rename(columns={'semantic_role':'role'})
            p=pd.concat([p,sp],ignore_index=True)
        p=p.merge(selected[selected.stage.eq(stage)],on=BASE+['role'],how='inner',validate='many_to_one')
        pools.append(p)
    pool=pd.concat(pools,ignore_index=True)
    opportunity=pd.read_csv(OUT/'screen/POOL_STRUCTURE_OPPORTUNITY_LINK.csv')
    pool=pool.merge(opportunity[['pool_id','structure_opportunity','reference_turn_group']],on='pool_id',how='left',validate='many_to_one')
    write_csv(OUT/'FINAL_CONDITIONS_POOL_SUMMARIES.csv.gz',pool)
    fields=[c for c in pool if c in RISKS or any(c==s+'_'+x for s in STEMS for x in ['within','cross','gap','BA','CA','CB'])]
    for strata in ['difficulty','structure_opportunity','reference_turn_group']:
        keys=BASE+['role',strata]
        b=aggregate(pool,keys+['building'],fields)
        empty=pd.DataFrame(columns=keys+['background_id','block_id','A_team_key','B_team_key','C_team_key']+fields)
        write_csv(OUT/('FINAL_CONDITIONS_'+strata.upper()+'.csv'),separation_table(pool,b,empty,keys,STEMS))
        write_csv(OUT/('FINAL_CONDITIONS_'+strata.upper()+'_RISK_TIME.csv'),effect_long(pool,b,empty,keys,RISKS))
    print({'conditions':len(selected),'pool_condition_rows':len(pool),'output':str(OUT)})

if __name__=='__main__':main()
