"""Added retrospective mode-mass stability, distinct from geometric coverage.

Complete-linkage full-observed clusters are a descriptive reference partition,
not GT or prospective labels. Require TV of empirical mode weights <=.10/.20
AND >=90% observed mass represented by modes seen in at least2 real people.
Singleton modes remain separate and can prevent certification. Finite random
orders do not create people. A sustained prefix must leave at least2 observations.
"""
import collections,itertools,json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait.pro_core import OUT,SEED,write_csv,write_json


def run():
    a=pd.read_csv(OUT/'stability/observed_cluster_memberships.csv.gz')
    rows=[];summaries=[];rng=np.random.default_rng(SEED)
    # Existing IDs assign every real person to exactly one within-point-count cluster.
    for (image,arm,cut),g in a.groupby(['image_id','condition','cut']):
        g=g.sort_values('worker_id');n=len(g);assert g.worker_id.nunique()==n
        labels=g.cluster.to_numpy();classes,labels=np.unique(labels,return_inverse=True);sizes=np.bincount(labels);prob=sizes/n
        supported=sizes>=2;full_supported=int(supported.sum());mass=float(prob[supported].sum());kind='single_supported_mode'if full_supported==1 else'multiple_supported_modes'if full_supported>=2 else'no_supported_mode'
        if n<4:
            for rule,tv in itertools.product(['mass90_only','every_supported_mode_seen_twice'],[.1,.2]):summaries.append(dict(image_id=image,building=image.split('_')[0],condition=arm,cut=cut,criterion=rule,tv_tolerance=tv,n_workers=n,n_full_clusters=len(sizes),n_supported_modes=full_supported,full_supported_mass=mass,observed_pattern=kind,status='fewer_than4_real_people',stability_order_fraction=np.nan,conditional_median_k=np.nan))
            continue
        curves=[];starts={(rule,tv):[]for rule in ['mass90_only','every_supported_mode_seen_twice']for tv in [.1,.2]}
        for rep in range(100):
            order=rng.permutation(n);onehot=np.eye(len(sizes),dtype=int)[labels[order]];counts=onehot.cumsum(0);hist=counts/np.arange(1,n+1)[:,None]
            tv=.5*np.abs(hist-prob).sum(1);represented=(counts>=2)@prob
            curves.append(np.column_stack([tv,represented,(counts[:,supported]>=2).sum(1)]))
            for rule,tolerance in starts:
                valid=(tv<=tolerance+1e-12)&(represented>=.9-1e-12)
                if rule=='every_supported_mode_seen_twice':valid &= (counts[:,supported]>=2).all(1)
                # Criterion must hold for EVERY remaining prefix, not cherry-pick
                # a lucky crossing. k<=n-2 keeps the requested observed future.
                sustained=np.logical_and.accumulate(valid[::-1])[::-1]
                eligible=np.flatnonzero(sustained & (np.arange(1,n+1)>=2)&(np.arange(1,n+1)<=n-2))
                starts[rule,tolerance].append(int(eligible[0]+1)if len(eligible)else np.nan)
        v=np.stack(curves)
        for k in range(2,n+1):
            rows.append(dict(image_id=image,building=image.split('_')[0],condition=arm,cut=cut,n_workers=n,prefix=k,mean_TV_to_full_observed_modes=v[:,k-1,0].mean(),mean_supported_full_mass=v[:,k-1,1].mean(),mean_supported_modes_observed=v[:,k-1,2].mean(),n_supported_modes=full_supported))
        for (rule,tolerance),values in starts.items():
            values=np.asarray(values);valid=np.isfinite(values);summaries.append(dict(image_id=image,building=image.split('_')[0],condition=arm,cut=cut,criterion=rule,tv_tolerance=tolerance,n_workers=n,n_full_clusters=len(sizes),n_supported_modes=full_supported,full_supported_mass=mass,observed_pattern=kind,status='evaluated',stability_order_fraction=valid.mean(),conditional_median_k=np.median(values[valid])if valid.any()else np.nan))
    write_csv('stability/mode_mass_curves.csv.gz',rows);write_csv('stability/mode_mass_image_results.csv',summaries)
    s=pd.DataFrame(summaries);out=[]
    for group_name,z in [('all_n',s),('at_least10_real_people',s[s.n_workers>=10])]:
        for keys,g in z.groupby(['condition','cut','tv_tolerance','criterion']):
            e=g[g.status=='evaluated'];out.append(dict(panel=group_name,condition=keys[0],cut=keys[1],tv_tolerance=keys[2],criterion=keys[3],n_target_images=len(g),n_evaluable=len(e),mean_order_stability=e.stability_order_fraction.mean(),images_stable_in_at_least90pct_orders=int((e.stability_order_fraction>=.9).sum()),single_mode_images_stable90=int(((e.stability_order_fraction>=.9)&(e.observed_pattern=='single_supported_mode')).sum()),multi_mode_images_stable90=int(((e.stability_order_fraction>=.9)&(e.observed_pattern=='multiple_supported_modes')).sum()),images_no_stable_order=int((e.stability_order_fraction==0).sum()),conditional_image_median_k=e.conditional_median_k.median()))
    write_csv('stability/mode_mass_summary.csv',out)
    write_json(OUT/'stability/mode_mass_method.json',dict(version='added_exploration_mode_mass_v2_explicit_supported_modes',criteria=['mass90_only','every_supported_mode_seen_twice'],cuts=[.05,.1,.2],TV_tolerances=[.1,.2],required_supported_observed_mass=.9,minimum_cluster_people=2,orders=100,seed=SEED,minimum_future_observed_people=2,full_partition='Full observed complete linkage within point counts; descriptive reference only',stability='TV and supported mass criteria hold at every prefix fromk through observedn, withk<=n-2',not_prospective_or_frozen=True,coverage_not_stability=True))

if __name__=='__main__':run()
