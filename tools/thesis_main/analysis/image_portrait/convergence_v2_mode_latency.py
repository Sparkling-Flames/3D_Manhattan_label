"""Exact finite-pool discovery/support delay; no additional observations assumed.
Separates occupancy effects from geometric re-clustering. Formula comparisons
are identities conditional on the observed mode-size multiset, not population
estimates or proof that a two-person mode is semantically valid.
"""
import math,itertools,json
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.convergence_v2_common import *


def no_seen(N,m,k):
 return math.comb(N-m,k)/math.comb(N,k)if k<=N-m else 0.

def exactly_one(N,m,k):
 return m*math.comb(N-m,k-1)/math.comb(N,k)if 0<=k-1<=N-m and k>=1 else 0.


def run():
 members=pd.read_csv(OUT/'process/mode_memberships.csv.gz');summ=[];curves=[];signatures=[]
 for (im,arm,cut),g in members.groupby(['image_id','condition','cut']):
  N=len(g);sizes=g.groupby('cluster').size();pc=g.groupby('cluster').point_count.first();signature=','.join(map(str,sorted(sizes.tolist(),reverse=True)));signatures.append(dict(image_id=im,condition=arm,cut=cut,n=N,signature=signature,n_topologies=g.point_count.nunique(),n_modes=len(sizes)))
  for cl,m in sizes.items():
   summ.append(dict(image_id=im,condition=arm,cut=cut,n=N,mode=cl,point_count=pc.loc[cl],mode_people=m,workers=';'.join(g[g.cluster==cl].worker_id),canonical_ids=';'.join(g[g.cluster==cl].canonical_annotation_id),expected_first_seen_k=(N+1)/(m+1),expected_second_support_k=2*(N+1)/(m+1)if m>=2 else np.nan,has_other_same_point_mode=bool(((pc==pc.loc[cl])&(pc.index!=cl)).any()),singleton=m==1))
   for k in range(1,N+1):
    p0=no_seen(N,m,k);p1=exactly_one(N,m,k);curves.append(dict(image_id=im,condition=arm,cut=cut,n=N,mode=cl,mode_people=m,k=k,P_seen=1-p0,P_supported=1-p0-p1,finite_observed_pool_only=True))
 csv('process/exact_mode_discovery_support_delay.csv',summ);a=csv('process/exact_mode_discovery_curves.csv.gz',curves);sg=pd.DataFrame(signatures);examples=[]
 for (arm,cut,N,signature),g in sg.groupby(['condition','cut','n','signature']):
  if len(g)<2 or N<10:continue
  for r,s in itertools.combinations(g.to_dict('records'),2):
   if r['n_topologies']!=s['n_topologies']:
    examples.append(dict(condition=arm,cut=cut,n=N,mode_size_signature=signature,image_a=r['image_id'],image_b=s['image_id'],topologies_a=r['n_topologies'],topologies_b=s['n_topologies'],fixed_partition_discovery_curves_identical_by_construction=True))
 csv('structure/same_mode_sizes_different_topology_examples.csv',examples)
 js('process/exact_mode_latency_method.json',dict(first_order_statistic='E[K_first]=(N+1)/(m+1)',second_order_statistic='E[K_support2]=2(N+1)/(m+1) for m>=2',absent_probability='choose(N-m,k)/choose(N,k)',one_probability='m*choose(N-m,k-1)/choose(N,k)',conditioning='Full observed partition, retained as retrospective descriptive sensitivity. These formulas never assert a mode is reasonable or estimate unseen population mass.',implication='Fixed-partition discovery depends on counts, not on whether modes have the same point count. Geometric re-clustering differences are a distinct process.',counts='Repeated orders are not independent observations'))
 print('LATENCY',len(summ),'modes',len(examples),'identical-occupancy examples')

if __name__=='__main__':run()
