"""Exploratory associations and exact probability checks; no causal tests."""
from pathlib import Path
from math import comb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr,hypergeom,binom
R=Path(__file__).parent
d=pd.read_csv(R/'c1_targeted_rows.csv')
t=d.groupby(['base_task_id','building_id','dataset_group']).agg(n=('worker_id','size'),distance=('task_mask_dispersion','first'),corners_mean=('corner_pair_count','mean'),corners_sd=('corner_pair_count','std'),occlusion_share=('difficulty_occlusion','mean'),trivial_share=('difficulty_trivial','mean'),median_active_seconds=('active_time_seconds','median'),time_n=('active_time_seconds','count')).reset_index()
t.to_csv(R/'c1_task_exploratory_features.csv',index=False)
out=[]
for subset,z in {'all84':t,'support_at_least_5':t[t.n>=5]}.items():
 for x in ['corners_mean','corners_sd','occlusion_share','trivial_share','median_active_seconds']:
  a=z[[x,'distance']].dropna()
  out.append({'subset':subset,'predictor':x,'outcome':'task_pairwise_mask_distance','n_tasks':len(a),'spearman_rho':spearmanr(a[x],a.distance).statistic,'role':'post_annotation_descriptive_not_prospective_predictor'})
pd.DataFrame(out).to_csv(R/'task_associations.csv',index=False)
prob=[]
for k in range(2,26):
 prob.append({'k':k,'scenario':'finite_N25_minority2_without_replacement','p_at_least_one':hypergeom.sf(0,25,2,k),'p_at_least_two':hypergeom.sf(1,25,2,k)})
 prob.append({'k':k,'scenario':'iid_new_workers_p0.10_assumed_not_estimated','p_at_least_one':binom.sf(0,k,.1),'p_at_least_two':binom.sf(1,k,.1)})
pd.DataFrame(prob).to_csv(R/'minority_capture_scenarios.csv',index=False)
# Toy exact check of pairwise-disagreement unbiasedness: all subsets, fixed finite roster.
y=np.array([0.,0.,.1,.2,1.,1.,1.2]);N=len(y)
from itertools import combinations
D=np.abs(y[:,None]-y[None,:]);full=D[np.triu_indices(N,1)].mean()
ex=[]
for k in range(2,N+1):
 means=[]
 for ids in combinations(range(N),k):
  M=D[np.ix_(ids,ids)];means.append(M[np.triu_indices(k,1)].mean())
 ex.append({'N':N,'k':k,'full_pairwise_distance':full,'exact_expected_sample_pairwise_distance':np.mean(means),'sample_statistic_sd':np.std(means),'subset_count':len(means),'synthetic_math_check_not_empirical_data':True})
assert max(abs(x['full_pairwise_distance']-x['exact_expected_sample_pairwise_distance']) for x in ex)<1e-12
pd.DataFrame(ex).to_csv(R/'pairwise_unbiasedness_math_check.csv',index=False)
print(pd.DataFrame(out).to_string(index=False));print(pd.DataFrame(prob).query('k in [15,20]').to_string(index=False))
