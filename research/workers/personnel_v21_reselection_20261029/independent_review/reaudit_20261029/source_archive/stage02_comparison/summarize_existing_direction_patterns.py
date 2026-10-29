"""Re-read existing image summaries using same-original-team magnitude contrasts."""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd

def pattern(a,c,eps):
    sa=np.where(a>eps,1,np.where(a< -eps,-1,0));sc=np.where(c>eps,1,np.where(c< -eps,-1,0))
    return np.select([(sa==0)&(sc==0),(sa==0)&(sc!=0),(sa!=0)&(sc==0),sa*sc>0,sa*sc<0],
                     ['both_near_zero','cross_only','same_only','same_direction','opposite_direction'],default='unclassified')

def main(repo,out):
    w=Path(repo)/'research/workers/personnel_v21_reselection_20261029';out=Path(out)
    im=pd.read_csv(w/'analysis/focused_summary/DIRECTION_IMAGE_RESULTS.csv.gz')
    im=im[im.condition.eq('manual')&im.layer.eq('ordinary_manual')&im.scope.eq('primary')].copy()
    keys=['method','n','m','role_direction'];summary=[];patterns=[]
    events=pd.read_csv(w/'analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz',usecols=['event_id','pool_id','image','building','method','n','m','condition','layer','scope','B8L2_BA','B8L2_CA','B8L2_CB','ABC_scored','A_failed','B_failed','C_failed'])
    roles=pd.read_csv(w/'analysis/focused_summary/EVENT_ROLE_LINKS.csv.gz',usecols=['event_id','role_direction'])
    events=events.merge(roles,on='event_id',validate='one_to_one')
    pl=pd.read_csv(w/'analysis/focused_compact/EVENT_PAIR_LINKS.csv.gz')
    pg=pd.read_csv(w/'analysis/focused_compact/PAIR_GEOMETRY.csv.gz')
    gm=['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
    pair=pl.merge(pg[['pair_id']+gm],on='pair_id',validate='many_to_one')
    wide=pair.pivot(index='event_id',columns='arm_pair',values=gm)
    wide.columns=['_'.join(c) for c in wide.columns];wide=wide.reset_index()
    events=events.merge(wide,on='event_id',validate='one_to_one')
    direct=[]
    for metric in gm:
        valid=events[metric+'_AB'].notna()&events[metric+'_AC'].notna()
        for suffix,col in [('same_origin_within',metric+'_AB'),('same_origin_cross',metric+'_AC')]:
            name=metric+'_'+suffix;events[name]=events[col].where(valid);direct.append(name)
        name=metric+'_same_origin_gap';events[name]=(events[metric+'_AC']-events[metric+'_AB']).where(valid);direct.append(name)
    ep=events.groupby(keys+['pool_id','image','building'])[direct].mean().reset_index()
    ei=ep.groupby(keys+['image','building'])[direct].mean().reset_index()
    im=im.merge(ei,on=keys+['image','building'],validate='one_to_one')
    joint_valid=events.B8L2_BA.notna()&events.B8L2_CA.notna()&events.B8L2_CB.notna()
    pe=events[joint_valid].copy()
    pi=pe.groupby(keys+['pool_id','image','building'])[['B8L2_BA','B8L2_CA','B8L2_CB']].mean().reset_index()
    pi=pi.groupby(keys+['image','building'])[['B8L2_BA','B8L2_CA','B8L2_CB']].mean().reset_index()
    for eps in [1e-9,0.1,1.0,2.0]:
        nm='pattern_Q_epsilon_'+str(eps)
        events[nm]='not_jointly_scored';events.loc[joint_valid,nm]=pattern(events.loc[joint_valid,'B8L2_BA'],events.loc[joint_valid,'B8L2_CA'],eps)
        pi[nm]=pattern(pi.B8L2_BA,pi.B8L2_CA,eps)
    events.to_csv(out/'EXISTING_FOCUSED_EVENT_GEOMETRY_SAME_ORIGIN.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pi.to_csv(out/'EXISTING_FOCUSED_DIRECTION_PATTERN_IMAGE.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    metrics=['B8L2_within','B8L2_AC_absolute','B8L2_AC_gap','B8L2_cross','B8L2_gap','B8L2_BA','B8L2_CA','B8L2_CB',
             'fusion_turn_n_CA','fusion_turn_n_CB','geometry_pair_angle_gap','geometry_bev_distance_gap','record_time_CA_pct_source_matched',
             'record_time_CB_pct_source_matched','A_failed','B_failed','C_failed']+direct
    for k,g in im.groupby(keys):
        row=dict(zip(keys,k));row.update(registered_images=len(g),registered_buildings=g.building.nunique())
        for m in metrics:
            z=g[m].dropna();bz=g.groupby('building')[m].mean().dropna()
            row.update({m+'_mean_image':z.mean(),m+'_median_image':z.median(),m+'_p10_image':z.quantile(.1),m+'_p90_image':z.quantile(.9),
                        m+'_valid_images':len(z),m+'_positive_images':int(z.gt(1e-9).sum()),m+'_negative_images':int(z.lt(-1e-9).sum()),
                        m+'_near_zero_images':int(z.abs().le(1e-9).sum()),m+'_mean_building':bz.mean(),m+'_valid_buildings':len(bz),m+'_positive_buildings':int(bz.gt(1e-9).sum())})
        select=np.ones(len(pi),dtype=bool)
        for name,value in zip(keys,k):select &= pi[name].eq(value)
        z=pi.loc[select,['B8L2_BA','B8L2_CA']].dropna()
        for eps in [1e-9,0.1,1.0,2.0]:
            labels=pattern(z.B8L2_BA,z.B8L2_CA,eps)
            for lab in ['both_near_zero','cross_only','same_only','same_direction','opposite_direction']:
                patterns.append({**dict(zip(keys,k)),'epsilon_Q':eps,'pattern':lab,'images':int((labels==lab).sum()),'valid_images':len(z),'fraction':float((labels==lab).mean())})
        summary.append(row)
    pd.DataFrame(summary).to_csv(out/'EXISTING_FOCUSED_SAME_ORIGIN_SUMMARY.csv',index=False)
    pd.DataFrame(patterns).to_csv(out/'EXISTING_FOCUSED_DIRECTION_PATTERNS.csv',index=False)
    im.to_csv(out/'EXISTING_FOCUSED_IMAGE_RESULTS.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    # Same n/m, image pool, same numerical contrast. The actual A/D still differ
    # across classification designs, so this remains a common-support comparison.
    methods=['DSTRUCT_K3','TARGET_DSTRUCT_K3','OPPSTRUCT_K3']
    common=[]
    for n,m in [(10,7),(18,7),(20,6)]:
        dd=im[im.method.isin(methods)&im.n.eq(n)&im.m.eq(m)]
        images=set.intersection(*(set(dd[dd.method.eq(mm)].image) for mm in methods))
        for mm in methods:
            gg=dd[dd.method.eq(mm)&dd.image.isin(images)]
            rr=dict(method=mm,n=n,m=m,common_images=len(images),buildings=gg.building.nunique(),comparison='same image,n,m,metric; not identical A/D across methods')
            for metric in metrics:
                zz=gg[metric].dropna();rr[metric]=zz.mean();rr[metric+'_valid_images']=len(zz);rr[metric+'_positive_images']=int(zz.gt(1e-9).sum())
            common.append(rr)
    pd.DataFrame(common).to_csv(out/'STRUCTURE_THREE_METHOD_COMMON_IMAGE_N_M.csv',index=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',required=True);p.add_argument('--out',required=True);a=p.parse_args();main(a.repo,a.out)
