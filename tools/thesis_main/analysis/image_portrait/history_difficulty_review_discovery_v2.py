"""Separate rare-mode discovery probability from conditional mode stability.

The final clusters are RETROSPECTIVE evaluation objects, never known beforehand.
An exact hypergeometric support ceiling is not a future population guarantee.
"""
import collections,math,json
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import OUT,PREV,cluster,sd,csv,js
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_summary_v2 import few_limit

def support_ceiling(sizes,k):
 n=sum(sizes);dp=[1]+[0]*k
 for z in sizes:
  allowed=range(2,min(z,k)+1)if z>=2 else range(min(z,k)+1)
  nd=[0]*(k+1)
  for s in range(k+1):
   if dp[s]:
    for j in allowed:
     if s+j<=k:nd[s+j]+=dp[s]*math.comb(z,j)
  dp=nd
 return dp[k]/math.comb(n,k)if k<=n else np.nan

def main():
 index=json.loads((OUT/'cache/group_index.json').read_text());idx={(r['image_id'],r['condition']):r for r in index};z=np.load(OUT/'cache/pairwise_geometry.npz',allow_pickle=False);rr=pd.read_csv(OUT/'process/per_order_onsets.csv.gz');out=[]
 for key,g in rr.groupby(['image_id','condition','cut'],sort=False):
  i,c,cut=key;t=idx[i,c];kk=t['key'];n=int(t['n_valid']);dm=z[kk+'_dm'];pcs=z[kk+'_pcs'];labs=cluster(dm,pcs,cut);counts=collections.Counter(labs);supported=[l for l,q in counts.items()if q>=2]
  rng=np.random.default_rng(sd(i,c,'review_v2',cut));orders=[rng.permutation(n)for _ in range(len(g))];g=g.sort_values('replay')
  for h in[2,3,4,5,6,7,8,10,12,15,18,19]:
   k=min(h,n-1);seen=np.array([all(np.sum(labs[order[:k]]==l)>=2 for l in supported)and bool(supported)for order in orders])
   row=dict(image_id=i,condition=c,cut=cut,n_valid=n,requested_h=h,observed_k=k,horizon_shorter_than_requested=h>n-1,orders=len(g),n_orders_supported_at_k=int(seen.sum()),p_all_modes_seen_twice_exact=support_ceiling(list(counts.values()),k)if supported else 0.,p_all_modes_seen_twice_replay=float(seen.mean()))
   for tol in[10,15,20]:
    passed=g[f'core_onset_{tol}'].to_numpy()<=k
    assert not np.any(passed&~seen),'Core stability cannot precede actual duplicate support'
    row[f'p_stable_core{tol}_unconditional']=passed.mean();row[f'p_stable_core{tol}_given_support']=float(passed[seen].mean())if seen.any()else np.nan
   out.append(row)
 result=csv('process/support_discovery_vs_conditional_stability.csv',out)
 p=pd.read_csv(OUT/'proposal/per_image_draft_for_user.csv');a=result[(result.cut==.1)&(result.requested_h==19)]
 q=p.merge(a,on=['image_id','condition','cut','n_valid'],how='left');q['rare_mode_adjusted_medium']=False
 for j,r in q.iterrows():
  # Not a new complete-convergence criterion: decision only for already-repeated
  # modes, with explicit uncertain sample-count and semantic flags still retained.
  q.loc[j,'rare_mode_adjusted_medium']=bool(r.draft_grade=='medium_candidate'and r.n_orders_supported_at_k>=20 and r.p_stable_core15_given_support>=.8)
 csv('proposal/conditional_supported_mode_adjudication.csv',q)
 csv('expert/anchor_support_ceiling.csv',q[q.expert_tag.isin(['中等','困难'])&(q.n_valid>=10)])
 js('process/discovery_interpretation.json',dict(ceiling='exact probability of observing >=2 members of EACH terminal supported mode in k distinct sampled people; terminal singleton labels unconstrained',conditional='among the SAME sampled orders in which each final supported mode is already represented twice at k, fraction with sustained recovered core and conditional TV/geometry checks from k through n',retrospective_only=True,unconditional_retained=True,do_not_call_conditional_score_whole_distribution_convergence=True,finite_draw_minimum_for_conditional_review=20,new_people=0))
 print(q.groupby('condition').rare_mode_adjusted_medium.sum());print(q[q.expert_tag.isin(['中等','困难'])&(q.n_valid>=10)][['image_id','expert_tag','n_valid','sizes_descending','p_all_modes_seen_twice_exact','core15_p_by_19','p_stable_core15_given_support','rare_mode_adjusted_medium']].to_string(index=False))
if __name__=='__main__':main()
