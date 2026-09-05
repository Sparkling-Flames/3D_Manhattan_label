"""Compare stable operational stratification with multivariate clustering.
Median/tertile bins are imposed rank strata, NOT discovered natural worker types.
GMM is a small-sample exploratory benchmark, not an endorsed production model.
"""
from pathlib import Path
import warnings
import numpy as np,pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_rand_score
R=Path(__file__).parent
src=(R/'fit_exploratory_profiles.py').read_text().split('summary=[];profile=[];cv=[];stability=[];cluster=[]')[0]
ns={'__file__':str(R/'fit_exploratory_profiles.py')};exec(src,ns)
d=ns['D'];fit=ns['fit'];metrics=ns['metrics'];bs=np.array(sorted(d.building_id.unique()));rng=np.random.default_rng(20260905)
rows=[]
for rep in range(200):
 a=set(rng.permutation(bs)[:len(bs)//2]);pa={};pb={}
 for m in metrics:
  pa[m]=fit(d[d.building_id.isin(a)],m)[0];pb[m]=fit(d[~d.building_id.isin(a)],m)[0]
 for m in ['corner_pair_count','log_active_time']:
  ca,cb=pa[m],pb[m];ix=ca.index.intersection(cb.index)
  for k in [2,3]:
   la=pd.qcut(ca.loc[ix].rank(method='first'),k,labels=False).to_numpy();lb=pd.qcut(cb.loc[ix].rank(method='first'),k,labels=False).to_numpy()
   rows.append({'replicate':rep,'method':'imposed_rank_strata','features':m,'k':k,'ari':adjusted_rand_score(la,lb),'n_workers':len(ix)})
 A=pd.DataFrame(pa).dropna();B=pd.DataFrame(pb).dropna();ix=A.index.intersection(B.index)
 X=A.loc[ix].to_numpy();Y=B.loc[ix].to_numpy();X=(X-X.mean(0))/X.std(0);Y=(Y-Y.mean(0))/Y.std(0)
 for k in [2,3]:
  with warnings.catch_warnings():
   warnings.simplefilter('ignore')
   ma=GaussianMixture(k,covariance_type='diag',reg_covar=.05,n_init=5,random_state=rep).fit(X)
   mb=GaussianMixture(k,covariance_type='diag',reg_covar=.05,n_init=5,random_state=rep).fit(Y)
  rows.append({'replicate':rep,'method':'diagonal_Gaussian_mixture','features':'peer_corner_time','k':k,'ari':adjusted_rand_score(ma.predict(X),mb.predict(Y)),'n_workers':len(ix)})
r=pd.DataFrame(rows);r.to_csv(R/'grouping_method_split_results.csv',index=False)
s=r.groupby(['method','features','k']).ari.agg(['median',lambda x:x.quantile(.25),lambda x:x.quantile(.75)]);s.columns=['median_ari','q25','q75'];s.reset_index().to_csv(R/'grouping_method_summary.csv',index=False)
print(s)
