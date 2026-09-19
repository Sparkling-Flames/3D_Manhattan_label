"""Simple alternative GROUP DEFINITION, not a new point distance.
Greedily choose a real remaining response covering the most remaining responses within r.
Tie: smaller within-neighbourhood mean distance, then fixed canonical order.
Groups are r-close to their exemplar, NOT necessarily r-close pairwise.
No target K, minimum group size, outlier deletion or semantic labels.
"""
import json,collections
from pathlib import Path
import numpy as np,pandas as pd
import local_points as lp
R=lp.ROOT

def cover(D,r):
 remaining=list(range(len(D)));lab=np.zeros(len(D),int);centres=[];k=0
 while remaining:
  scores=[]
  for i in remaining:
   near=[j for j in remaining if D[i,j]<=r+1e-12]
   scores.append((-len(near),float(np.mean(D[i,near])),i,near))
  _,_,i,near=min(scores,key=lambda x:x[:3]);k+=1;centres.append(i);lab[near]=k
  remaining=[j for j in remaining if j not in near]
 return lab,centres

def run():
 cache=json.loads((R/'results/cache.json').read_text());s=[];m=[];centres=[]
 for key,g in cache.items():
  iid,cond=key.split('|');h=np.array(g['Ds']['hausdorff']);o=np.array(g['Ds']['ospa1'])
  for metric,D,thresholds in [('H',h,[6,9,12]),('O',o,[6])]:
   for r in thresholds:
    name=f'Exemplar_{metric}{r}';lab,cs=cover(D,r)
    tr=np.triu_indices(len(lab),1);same=lab[:,None]==lab[None,:];near=D<=r
    within_far=int((same[tr]&~near[tr]).sum());near_apart=int((near[tr]&~same[tr]).sum())
    s.append(dict(key=key,code=g['code'],condition=cond,method=name,**lp.stats(lab),within_pairs_over_radius=within_far,near_pairs_separated=near_apart))
    for i,cid in enumerate(g['ids']):
     ci=cs[lab[i]-1];m.append(dict(key=key,code=g['code'],condition=cond,method=name,id=cid,worker=g['workers'][i],cluster=int(lab[i]),representative_id=g['ids'][ci],distance_to_representative=float(D[i,ci])))
    for j,ci in enumerate(cs,1):
     ix=np.where(lab==j)[0];diam=float(D[np.ix_(ix,ix)].max());radius=float(D[ci,ix].max())
     assert radius<=r+1e-9
     centres.append(dict(key=key,code=g['code'],condition=cond,method=name,cluster=j,N=len(ix),representative=g['workers'][ci],diameter=diam,radius=radius,all_pairwise_within_r=diam<=r))
    g['labels'][name]=lab.tolist()
 pd.DataFrame(s).to_csv(R/'results/exemplar_summary.csv',index=False);pd.DataFrame(m).to_csv(R/'results/exemplar_memberships.csv',index=False);pd.DataFrame(centres).to_csv(R/'results/exemplar_centres.csv',index=False)
 (R/'results/cache_with_exemplars.json').write_text(json.dumps(cache,separators=(',',':')))
 rv=pd.read_csv(R/'results/user24_multitarget_relations.csv');results=[]
 for name in ['Exemplar_H6','Exemplar_H9','Exemplar_H12','Exemplar_O6']:
  pred=[]
  for key in rv.key:
   iid,cond,a,b=key.split('|');g=cache[iid+'|'+cond];l=g['labels'][name];pred.append(l[g['ids'].index(a)]==l[g['ids'].index(b)])
  rv[name]=pred
  results.append(dict(method=name,explicit_near=int(rv.similarity_explicit.sum()),near_together=int(rv.loc[rv.similarity_explicit,name].sum()),coverage_difference=int(rv.different_coverage_reported.sum()),coverage_separate=int((~rv.loc[rv.different_coverage_reported,name]).sum()),old_difference=int((rv.previous_interpretation=='different_expression_or_cover').sum()),old_difference_separate=int((~rv.loc[rv.previous_interpretation=='different_expression_or_cover',name]).sum())))
 rv.to_csv(R/'results/exemplar_user24.csv',index=False)
 print(pd.DataFrame(results).to_string(index=False))
 print(pd.DataFrame(s).groupby('method')[['clusters','singletons','within_pairs_over_radius','near_pairs_separated']].sum().to_string())
if __name__=='__main__':run()
