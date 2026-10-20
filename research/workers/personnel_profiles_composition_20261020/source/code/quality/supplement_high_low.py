"""Small post-computation Q-mixture analyses; no fusion is run here.

Separates source restriction from image-capacity changes and measures observed
new-cohort labor time without mixing inherited v1 timing semantics.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

import high_low_study as hs
from analyze_high_low import bmean, delta_summary, add_phase_all


def common_source(out):
    p = pd.read_csv(out/'composition_pair_events.csv.gz')
    p = add_phase_all(p[(p.n==7)&p.baseline.isin(['pure_H','pure_L'])])
    rows=[]
    for key,g in p.groupby(['layer','phase','H','L','baseline']):
        cols=['d_B8L2','d_D10','d_score_rate','d_ref_edge_recall_9','loss_over_5','within_2_of_H']
        pool = g.groupby(['source_policy','building','pool_id','image_id'])[cols].mean().reset_index()
        a=pool[pool.source_policy=='all_supported'].drop(columns='source_policy')
        n=pool[pool.source_policy=='new_only'].drop(columns='source_policy')
        m=a.merge(n,on=['building','pool_id','image_id'],suffixes=('_all','_new'),validate='one_to_one')
        if m.empty:continue
        row=dict(zip(['layer','phase','H','L','baseline'],key),common_images=m.image_id.nunique(),common_buildings=m.building.nunique())
        for side in ['all','new']:
            for c in cols:row[side+'_'+c]=bmean(m,c+'_'+side)
            row[side+'_finite_Q_images']=int(m['d_B8L2_'+side].notna().sum())
        complete=m.dropna(subset=['d_B8L2_all','d_B8L2_new']).copy()
        complete['d_B8L2']=complete.d_B8L2_new-complete.d_B8L2_all
        row.update({('source_difference_'+k):v for k,v in delta_summary(complete).items()})
        row['all_d_B8L2_on_both_finite_images']=bmean(complete,'d_B8L2_all') if len(complete) else np.nan
        row['new_d_B8L2_on_both_finite_images']=bmean(complete,'d_B8L2_new') if len(complete) else np.nan
        rows.append(row)
    hs.write_csv(out/'source_common_image_comparison.csv',pd.DataFrame(rows))


def time_cost(out):
    e=pd.DataFrame(hs.read(out/'requests.json.gz')['events'])
    e=e[(e.family=='grid')&(e.n==7)&(e.source_policy=='new_only')&(e.pure_comparison_available==True)]
    wanted=set(e.team_key);rows=[]
    for pid in e.pool_id.unique():
        for x in hs.read(out/'native_final'/f'{pid}.json.gz')['teams']:
            if x['team_key'] in wanted:
                rows.append({k:x.get(k) for k in ['team_key','B8L2','D10','source_time_known_n','source_time_total_seconds']})
    f=e.merge(pd.DataFrame(rows),on='team_key',validate='many_to_one')
    f['time_complete']=(f.source_time_known_n==f.n)&(f.source_time_total_seconds>0)
    keys=['pool_id','n','replicate','source_policy'];pairs=[]
    for base,mask in [('pure_H',f.H==7),('pure_L',f.H==0)]:
        b=f[mask][keys+['team_key','B8L2','D10','time_complete','source_time_total_seconds']]
        p=f.merge(b,on=keys,suffixes=('','_baseline'),validate='many_to_one')
        p['baseline']=base
        p['time_pair_complete']=p.time_complete&p.time_complete_baseline
        p['ratio_labor_time']=np.where(p.time_pair_complete,p.source_time_total_seconds/p.source_time_total_seconds_baseline,np.nan)
        p['d_labor_seconds']=np.where(p.time_pair_complete,p.source_time_total_seconds-p.source_time_total_seconds_baseline,np.nan)
        p['d_B8L2']=np.where(p.time_pair_complete,p.B8L2-p.B8L2_baseline,np.nan)
        p['d_D10']=np.where(p.time_pair_complete,p.D10-p.D10_baseline,np.nan)
        p['joint_quality_within_2_and_time_saving']=np.where(p.d_B8L2.notna(),((p.d_B8L2>=-2)&(p.ratio_labor_time<1)).astype(float),np.nan)
        pairs.append(p)
    p=pd.concat(pairs,ignore_index=True)
    keep=['event_id','pool_id','image','image_id','building','layer','condition','phase','H','L','replicate','team_key','team_key_baseline','baseline','time_pair_complete','source_time_total_seconds','source_time_total_seconds_baseline','ratio_labor_time','d_labor_seconds','d_B8L2','d_D10','joint_quality_within_2_and_time_saving']
    hs.write_csv(out/'new_only_n7_labor_pairs.csv.gz',p[keep])
    rows=[]
    for key,g in add_phase_all(p).groupby(['layer','phase','H','L','baseline']):
        row=dict(zip(['layer','phase','H','L','baseline'],key),requested_images=g.image_id.nunique(),requested_events=len(g))
        row['time_pair_complete_rate']=bmean(g,'time_pair_complete')
        good=g[g.time_pair_complete].copy()
        row.update(time_pair_events=len(good),time_pair_images=good.image_id.nunique(),time_pair_buildings=good.building.nunique())
        for c in ['ratio_labor_time','d_labor_seconds','d_B8L2','d_D10','joint_quality_within_2_and_time_saving']:
            row[c]=bmean(good,c) if len(good) else np.nan
        row['labor_seconds_mixed']=bmean(good,'source_time_total_seconds') if len(good) else np.nan
        row['labor_seconds_baseline']=bmean(good,'source_time_total_seconds_baseline') if len(good) else np.nan
        row.update({'quality_'+k:v for k,v in delta_summary(good).items()})
        rows.append(row)
    hs.write_csv(out/'new_only_n7_labor_summary.csv',pd.DataFrame(rows))


def common_n(out):
    p=pd.read_csv(out/'composition_pair_events.csv.gz')
    p=p[(p.source_policy=='all_supported')&(p.n.between(3,9))]
    # A common pool set supports every pure H/L endpoint at n=9 and contains
    # the identifier-selected broad grid. n7-only pools therefore cannot enter.
    eligible=set(p[p.n==9].pool_id)
    p=p[p.pool_id.isin(eligible)].copy()
    p['policy']=np.select([p.H==0,p.H==1,p.H==p.n//2,p.H==p.n-1,p.H==p.n],['all_L','one_H','floor_half_H','one_L','all_H'],default='other')
    p=p[p.policy!='other']
    rows=[]
    for key,g in p.groupby(['layer','n','policy','baseline']):
        row=dict(zip(['layer','n','policy','baseline'],key))
        row.update(delta_summary(g))
        for c in ['d_D10','d_score_rate','d_ref_edge_recall_9','within_2_of_H','loss_over_5']:
            row[c]=bmean(g,c)
        row.update(requested_images=g.image_id.nunique(),requested_buildings=g.building.nunique())
        rows.append(row)
    hs.write_csv(out/'n3_to_n9_common_pool_effects.csv',pd.DataFrame(rows))


def replicate_consistency(out):
    p=pd.read_csv(out/'composition_pair_events.csv.gz')
    p=p[(p.n==7)&(p.baseline=='pure_H')&(p.H.between(1,6))]
    # All scheduled member permutations must have finite Q before calling an
    # image consistent over repeats; all others keep a separate incomplete flag.
    rows=[]
    keys=['layer','phase','source_policy','H','L','building','pool_id','image_id']
    for key,g in p.groupby(keys):
        q=g.d_B8L2
        complete=q.notna().all()
        rows.append(dict(zip(keys,key),replicates=len(g),finite_pairs=int(q.notna().sum()),all_pairs_finite=float(complete),
            all_members_within_2=float((q>=-2).all()) if complete else np.nan,
            any_member_loss_over_5=float((q<-5).any()) if complete else np.nan,
            member_delta_sd=q.std(),member_delta_range=q.max()-q.min(),
            image_mean_delta=q.mean()))
    f=pd.DataFrame(rows);hs.write_csv(out/'n7_member_consistency_per_image.csv.gz',f)
    summaries=[]
    for key,g in add_phase_all(f).groupby(['layer','phase','source_policy','H','L']):
        row=dict(zip(['layer','phase','source_policy','H','L'],key),images=g.image_id.nunique(),buildings=g.building.nunique())
        for c in ['all_pairs_finite','all_members_within_2','any_member_loss_over_5','member_delta_sd','member_delta_range','image_mean_delta']:
            row[c]=bmean(g,c)
        row['complete_images']=int(g.all_pairs_finite.sum())
        summaries.append(row)
    hs.write_csv(out/'n7_member_consistency_summary.csv',pd.DataFrame(summaries))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args()
    common_source(a.out);time_cost(a.out);common_n(a.out);replicate_consistency(a.out)
    print('Source-common images, complete new-cohort labor costs, common-n pools, and member consistency tables written.')
