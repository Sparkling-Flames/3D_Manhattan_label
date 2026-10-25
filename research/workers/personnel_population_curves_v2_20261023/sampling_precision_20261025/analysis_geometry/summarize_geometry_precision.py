"""Summarize within-pool Monte Carlo error separately from image/building spread."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from safe_io import install_safe_csv_writer
install_safe_csv_writer()


def aggregate(d,value='mean'):
    valid=d[np.isfinite(d[value])].copy()
    n=len(valid);v=valid[value]
    se=valid.mcse
    b=valid.groupby('building')[value].mean()
    return dict(candidate_images=len(d),valid_images=n,buildings=valid.building.nunique(),
        estimate=v.mean(),median=v.median(),image_sd=v.std(ddof=1),
        image_mcse_median=se.median(),image_mcse_p90=se.quantile(.9),
        aggregate_mcse=float(np.sqrt(np.sum(se**2))/n) if n and se.notna().all() else np.nan,
        aggregate_mcse_images=int(se.notna().sum()),
        building_equal_estimate=b.mean(),building_mean_sd=b.std(ddof=1),
        positive_images=int((v>1e-9).sum()),negative_images=int((v<-1e-9).sum()),nearzero_images=int((v.abs()<=1e-9).sum()))


def selections(d):
    for layer in d.layer.unique():
        own=d[d.layer.eq(layer)]
        lows=[0,20,30,35] if layer=='ordinary_manual' else [0]
        for minimum in lows:
            base=own[own.pool_n.ge(minimum)]
            if base.empty:continue
            for difficulty in ['ALL', *sorted(base.difficulty.dropna().unique())]:
                dd=base if difficulty=='ALL' else base[base.difficulty.eq(difficulty)]
                yield dict(layer=layer,minimum_pool_n=minimum,difficulty=difficulty),dd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True);ap.add_argument('--source-base');args=ap.parse_args()
    p=Path(args.results)
    d=pd.read_csv(p/'GEOMETRY_PATH_PRECISION.csv.gz')
    changes=pd.read_csv(p/'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz')
    # Two valid paths can supply one distance but cannot support a leave-one
    # variance estimate, even if those two observed node counts happen to agree.
    small=(d.valid_paths<3) & d.mcse.notna()
    if small.any():
        d.loc[small,'mcse']=np.nan
        temp=p/'GEOMETRY_PATH_PRECISION.csv.gz.tmp'
        d.to_csv(temp,index=False,compression='gzip');temp.replace(p/'GEOMETRY_PATH_PRECISION.csv.gz')
    summary=[]
    for key,g in d.groupby(['cohort','k','metric']):
        for stratum,dd in selections(g):
            if stratum['minimum_pool_n'] and key[1]>stratum['minimum_pool_n']:continue
            summary.append(dict(cohort=key[0],k=key[1],metric=key[2],**stratum,**aggregate(dd)))
    s=pd.DataFrame(summary);s['half_width_95_mc']=1.96*s.aggregate_mcse
    s.to_csv(p/'GEOMETRY_CURVE_MC_SUMMARY.csv',index=False)
    summary=[]
    for key,g in changes.groupby(['cohort','k_from','k_to','metric']):
        for stratum,dd in selections(g):
            if stratum['minimum_pool_n'] and key[2]>stratum['minimum_pool_n']:continue
            summary.append(dict(cohort=key[0],k_from=key[1],k_to=key[2],metric=key[3],**stratum,**aggregate(dd,'delta')))
    ss=pd.DataFrame(summary);ss['half_width_95_mc']=1.96*ss.aggregate_mcse
    ss.to_csv(p/'GEOMETRY_INTERVAL_MC_SUMMARY.csv',index=False)
    old=d[d.cohort.eq('old24')].drop(columns='cohort')
    comparisons=[]
    for label in ['new24','combined48','focus48','combined96']:
        own=d[d.cohort.eq(label)].drop(columns='cohort')
        if own.empty:continue
        key=['pool_id','k','metric']
        j=old.merge(own,on=key,suffixes=('_old','_new'),validate='one_to_one')
        j['comparison']=label
        j['new_minus_old']=j['mean_new']-j['mean_old']
        j['independent_new_old_mcse']=np.sqrt(j.mcse_old**2+j.mcse_new**2) if label in ['new24','focus48'] else np.nan
        j['mcse_ratio']=j.mcse_new/j.mcse_old.replace(0,np.nan)
        comparisons.append(j)
    if comparisons:
        j=pd.concat(comparisons,ignore_index=True)
        j.to_csv(p/'GEOMETRY_OLD_ADDED_IMAGE_COMPARISONS.csv.gz',index=False)
        reports=[]
        for key,g in j.groupby(['comparison','k','metric']):
            m=g.rename(columns={'layer_old':'layer','difficulty_old':'difficulty','pool_n_old':'pool_n','building_old':'building'})
            for stratum,gg in selections(m):
                if stratum['minimum_pool_n'] and key[1]>stratum['minimum_pool_n']:continue
                ok=gg['mean_old'].notna() & gg['mean_new'].notna();v=gg[ok]
                reports.append(dict(comparison=key[0],k=key[1],metric=key[2],**stratum,
                    images=len(gg),common_images=len(v),buildings=v.building.nunique(),old_mean=v['mean_old'].mean(),new_mean=v['mean_new'].mean(),
                    change=v.new_minus_old.mean(),abs_difference_median=v.new_minus_old.abs().median(),abs_difference_p90=v.new_minus_old.abs().quantile(.9),
                    image_mcse_old_median=v.mcse_old.median(),image_mcse_new_median=v.mcse_new.median(),mcse_ratio_median=v.mcse_ratio.median(),
                    positive_changes=int((v.new_minus_old>1e-9).sum()),negative_changes=int((v.new_minus_old<-1e-9).sum())))
        pd.DataFrame(reports).to_csv(p/'GEOMETRY_OLD_ADDED_COMMON_SUPPORT.csv',index=False)
    if args.source_base:
        prior=pd.read_csv(Path(args.source_base)/'results/PREFIX_GEOMETRY_VARIATION.csv.gz')
        prior=prior[prior.policy.eq('natural_random')]
        long=prior.melt(id_vars=['pool_id','k'],value_vars=[x+'_mean' for x in d.metric.unique()],var_name='metric',value_name='prior')
        long['metric']=long.metric.str.removesuffix('_mean')
        check=old.merge(long,on=['pool_id','k','metric'],validate='one_to_one')
        both=check['mean'].notna() & check.prior.notna()
        diff=(check.loc[both,'mean']-check.loc[both,'prior']).abs()
        receipt=dict(joined_rows=len(check),common_values=int(both.sum()),missing_state_disagreements=int((check['mean'].isna()!=check.prior.isna()).sum()),max_abs_difference=float(diff.max()),different_over_1e_10=int((diff>1e-10).sum()))
        (p/'OLD_GEOMETRY_METRIC_REUSE_CHECK.json').write_text(json.dumps(receipt,indent=2))
        print(receipt,flush=True)
    print('Geometry summaries saved',flush=True)


if __name__=='__main__':main()
