"""Summarize actual fixed-XYZ / nested-D size paths without new fusion.

An added member changes both the background and possibly the support threshold;
the exact ledger retains both facts rather than claiming a threshold-only cause.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from measure_registered_events import save, jsave


def aggregate(d, keys, metrics):
    p=d.groupby(keys+['pool_id','image','building'],dropna=False)[metrics].mean().reset_index()
    im=p.groupby(keys+['image','building'],dropna=False)[metrics].mean().reset_index()
    b=im.groupby(keys+['building'],dropna=False)[metrics].mean().reset_index()
    g=im.groupby(keys,dropna=False); bg=b.groupby(keys,dropna=False)
    r=g[metrics].mean().add_suffix('_mean_image').join(g[metrics].count().add_suffix('_valid_images'))
    r=r.join(bg[metrics].mean().add_suffix('_mean_building')).join(bg[metrics].count().add_suffix('_valid_buildings'))
    for col in metrics:
        z=im[keys].copy();z[col]=(im[col]>0).where(im[col].notna()).astype(float)
        r=r.join(z.groupby(keys,dropna=False)[col].sum(min_count=1).rename(col+'_positive_images'))
    r=r.join(d.groupby(keys,dropna=False).agg(path_pairs=('lower_event_id','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique')))
    return r.reset_index(),im,b


def main():
    a=argparse.ArgumentParser();a.add_argument('--metrics',required=True);a.add_argument('--links',required=True);a.add_argument('--roles',required=True);a.add_argument('--out',required=True);args=a.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    wanted=['event_id','scope','official_difficulty','geometric_challenge','background_id','block_id']
    comps=['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges','geometry_area_h2','height_mean_h','minimum_support','selected_support_min','unselected_groups_n','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','direction_loss','height_loss']
    for arm in 'ABC':wanted.extend(arm+'_'+c for c in comps);wanted.append(arm+'_failed')
    wanted+=['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','geometry_bev_distance_gap','geometry_pair_angle_gap','record_time_CB_pct_source_matched']
    ev=pd.read_csv(args.metrics,usecols=lambda c:c in wanted,low_memory=False)
    links=pd.read_csv(args.links); d=links.copy()
    for end in ['lower','higher']:
        ee=ev.rename(columns={c:end+'_'+c for c in ev if c!='event_id'}).rename(columns={'event_id':end+'_event_id'})
        d=d.merge(ee,on=end+'_event_id',how='left',validate='many_to_one')
    assert len(d)==len(links) and d.lower_A_failed.notna().all() and d.higher_A_failed.notna().all()
    roles=pd.read_csv(args.roles,usecols=['event_id','role_direction','role_axis','role_source_rank','role_target_rank'])
    d=d.merge(roles.rename(columns={'event_id':'lower_event_id'}),on='lower_event_id',validate='many_to_one')
    for c in ['scope','official_difficulty','geometric_challenge']:d[c]=d['lower_'+c]
    metrics=[]
    for arm in 'ABC':
        for c in comps:
            col='delta_'+arm+'_'+c;d[col]=d['higher_'+arm+'_'+c]-d['lower_'+arm+'_'+c];metrics.append(col)
        d[arm+'_new_failure']=(d['higher_'+arm+'_failed'] & ~d['lower_'+arm+'_failed']).astype(float).where(~d['lower_'+arm+'_failed'])
        d[arm+'_recovered']=(~d['higher_'+arm+'_failed'] & d['lower_'+arm+'_failed']).astype(float).where(d['lower_'+arm+'_failed'])
        metrics.extend([arm+'_new_failure',arm+'_recovered'])
    for c in ['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','geometry_bev_distance_gap','geometry_pair_angle_gap','record_time_CB_pct_source_matched']:
        d['delta_'+c]=d['higher_'+c]-d['lower_'+c];metrics.append('delta_'+c)
    common_bc=d[['lower_B_B8L2','higher_B_B8L2','lower_C_B8L2','higher_C_B8L2']].notna().all(axis=1)
    common_abc=common_bc & d[['lower_A_B8L2','higher_A_B8L2']].notna().all(axis=1)
    for mask_name,mask in [('paired_CB',common_bc),('paired_ABC',common_abc)]:
        for arm in ('BC' if mask_name=='paired_CB' else 'ABC'):
            col=mask_name+'_delta_'+arm+'_Q';d[col]=d['delta_'+arm+'_B8L2'].where(mask);metrics.append(col)
        col=mask_name+'_delta_net_CB_Q';d[col]=d.delta_B8L2_CB.where(mask);metrics.append(col)
        assert np.allclose(d.loc[mask,mask_name+'_delta_C_Q']-d.loc[mask,mask_name+'_delta_B_Q'],d.loc[mask,col],atol=1e-9)
    d['paired_ABC_delta_amplitude_gap']=d.delta_B8L2_gap.where(common_abc);metrics.append('paired_ABC_delta_amplitude_gap')
    for measure in ['CA','CB']:
        lo=d['lower_B8L2_'+measure];hi=d['higher_B8L2_'+measure];ok=lo.notna()&hi.notna()
        d[measure+'_positive_to_nonpositive']=((lo>0)&(hi<=0)).astype(float).where(ok)
        d[measure+'_negative_to_nonnegative']=((lo<0)&(hi>=0)).astype(float).where(ok)
        metrics.extend([measure+'_positive_to_nonpositive',measure+'_negative_to_nonnegative'])
    d['C_turn_loss']=(d.delta_C_fusion_turn_n<0).astype(float).where(d.delta_C_fusion_turn_n.notna());metrics.append('C_turn_loss')
    d['C_Q_loss10']=(d.delta_C_B8L2<-10).astype(float).where(d.delta_C_B8L2.notna());metrics.append('C_Q_loss10')
    save(out/'EXACT_SIZE_PATH_EFFECTS.csv.gz',d)
    keys=['method','condition','scope','role_direction','m','n_lower','n_higher']
    s,im,b=aggregate(d,keys,metrics);save(out/'SIZE_PATH_RESULTS.csv.gz',s);save(out/'SIZE_PATH_BY_IMAGE.csv.gz',im);save(out/'SIZE_PATH_BY_BUILDING.csv.gz',b)
    for layer in ['official_difficulty','geometric_challenge']:
        s,_,_=aggregate(d,keys+[layer],metrics);save(out/(layer.upper()+'_RESULTS.csv.gz'),s)
    jsave(out/'COMPLETE.json',dict(exact_path_pairs=len(d),methods=d.method.nunique(),pools=d.pool_id.nunique(),images=d.image.nunique(),buildings=d.building.nunique(),new_fusions=0,
        interpretation='XYZ fixed and D actually nested. Added members and changed support threshold jointly determine the result; threshold-only attribution needs the linked mechanism case.',
        weighting='within target/path condition -> equal targets within image -> equal images; building means separately',all_signed_changes_saved=True))
    print('completed',len(d),flush=True)

if __name__=='__main__':main()
