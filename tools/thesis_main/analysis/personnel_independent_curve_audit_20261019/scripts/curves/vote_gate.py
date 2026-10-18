from pathlib import Path
import pandas as pd,numpy as np
P=Path(__file__).parent;M=pd.read_csv(P/'VOTE_BOUNDARY_DIAGNOSTIC.csv');C=pd.read_csv(P/'curves.csv')
G=M.groupby('experiment_id').agg(available=('base_vote_boundary_available','all'),any_near=('base_near_boundary','any'))
G['gate']=np.where(~G.available,'unknown',np.where(G.any_near,'at_least_one_k_within_one_vote','all_four_k_clear_of_one_vote'))
C=C.merge(G[['gate']],left_on='experiment_id',right_index=True);C.to_csv(P/'VOTE_GATE_CURVES.csv',index=False);out=[]
for (method,gate),g in C.groupby(['method','gate']):
 im=g.groupby(['building','pool_id','arm']).curve_stable.mean().unstack('arm');b=im.groupby('building').mean();rng=np.random.default_rng(20261018);ix=rng.integers(len(b),size=(10000,len(b)));near=b.same_or_near.to_numpy()[ix].mean(axis=1);far=b.cross_or_far.to_numpy()[ix].mean(axis=1)
 out.append(dict(method=method,gate=gate,experiments=g.experiment_id.nunique(),images=g.pool_id.nunique(),buildings=len(b),same_stable_chains=int(g[g.arm.eq('same_or_near')].curve_stable.sum()),cross_stable_chains=int(g[g.arm.eq('cross_or_far')].curve_stable.sum()),same_building_weighted=b.same_or_near.mean(),same_low=np.quantile(near,.025),same_high=np.quantile(near,.975),cross_building_weighted=b.cross_or_far.mean(),cross_minus_same=(b.cross_or_far-b.same_or_near).mean(),delta_low=np.quantile(far-near,.025),delta_high=np.quantile(far-near,.975)))
pd.DataFrame(out).to_csv(P/'VOTE_GATE_SUMMARY.csv',index=False);print(pd.DataFrame(out).to_string(index=False))
