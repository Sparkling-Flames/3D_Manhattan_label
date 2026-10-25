#!/usr/bin/env python3
"""Readable original24 precision summaries with explicit scoreable denominators."""
from pathlib import Path
import argparse, math
import numpy as np
import pandas as pd


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);a=ap.parse_args()
    d=pd.read_csv(a.root/'OLD_PAIRED_INTERVAL_PRECISION.csv');rows=[]
    for th,ka,kb in [(20,3,6),(20,6,10),(20,10,20),(30,20,30),(35,30,35)]:
        for diff in ['全部','简单','中等','困难']:
            h=d[d.layer.eq('ordinary_manual')&d.pool_n.ge(th)&d.from_k.eq(ka)&d.to_k.eq(kb)]
            if diff!='全部':h=h[h.difficulty.eq(diff)]
            good=h.Q_mean_marginal_delta.notna();n=int(good.sum());z=h.loc[good,'Q_mean_marginal_delta']
            rows.append(dict(N_panel=th,difficulty=diff,interval=f'{ka}_to_{kb}',available_pools=len(h),
                             available_buildings=h.building.nunique(),quality_observed_images=n,
                             mean_delta=h.Q_mean_marginal_delta.mean(),
                             marginal_delta_MCSE=np.sqrt(np.nansum(h.Q_mean_delta_bootse**2))/n,
                             paired_Q_delta=h.paired_Q_delta.mean(),P10_delta=h.Q_p10_marginal_delta.mean(),
                             SD_delta=h.Q_sd_ddof1_marginal_delta.mean(),positive_images=int((z>0).sum()),
                             negative_images=int((z<0).sum()),zero_images=int((z==0).sum()),
                             positive_among_quality_images=float((z>0).mean()),negative_among_quality_images=float((z<0).mean())))
    pd.DataFrame(rows).to_csv(a.root/'OLD_FIXED_SUPPORT_INTERVAL_QUICK_PRECISION.csv',index=False)
    k=pd.read_csv(a.root/'OLD_PATH_POOL_K_PRECISION.csv.gz')
    k=k[k.layer.isin(['ordinary_manual','doorway_manual'])]
    budget=[]
    for (pool,n),g in k.groupby(['pool_id','pool_n']):
        for _,r in g.iterrows():
            kk=int(r['k']);M=math.comb(int(n),kk)
            z={c:r[c] for c in ['pool_id','image','building','layer','difficulty','pool_n','k','unique_teams']}
            z['finite_team_space']=str(M)
            for R in [24,48,96]:
                z[f'expected_distinct_teams_at_{R}_IID_orders']=1.0 if M==1 else -M*math.expm1(R*math.log1p(-1/M))
            z['estimated_new_distinct_24_after_old24']=z['expected_distinct_teams_at_48_IID_orders']-z['expected_distinct_teams_at_24_IID_orders']
            z['exact_boundary_available']=kk in [1,int(n)-1,int(n)] or int(n)<=10
            z['geometry_fusion_required']=kk>=3
            z['note']='Expected cache occupancy under IID uniform permutations; actual reuse also includes saved policy/historical teams.'
            budget.append(z)
    pd.DataFrame(budget).to_csv(a.root/'FINITE_SUBSET_SAMPLING_BUDGET_DIAGNOSTIC.csv.gz',index=False,compression='gzip')


if __name__=='__main__':main()
