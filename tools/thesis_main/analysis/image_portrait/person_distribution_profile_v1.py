"""Post-finding alternative to a large co-annotation cluster plus singletons.

Five low-dimensional, task-centered behavior features. No GT or difficulty tags.
Ward types, continuous distances and context-weighted distances are compared with
training-only selection. This is additional exploration, not a new data set.
"""
from pathlib import Path
import argparse,collections
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,cut_tree
from scipy.spatial.distance import cdist
from sklearn.metrics import adjusted_rand_score
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_diagnostics_v1 import paired_fast

class ProfileLearner(CachedLearner):
 def __init__(self,training,meta,workers,excluded_buildings=()):
  super().__init__(training,meta,workers,excluded_buildings)
  m=self.m;G=len(self.train);self.V=np.zeros((G,m,5));self.O=np.zeros((G,m))
  for a,g in enumerate(self.train):
   n=len(g['ids'])
   if n<2:continue
   count=np.log(g['count']);pos=np.array([np.sort(np.asarray(p)[:,1].reshape(-1,2),axis=1).mean(0)/512 for p in g['points']]);d=np.where(np.equal.outer(g['count'],g['count']),np.minimum(g['dm'],1),1.);glob=d[np.triu_indices(n,1)].mean()
   for j,w in enumerate(g['wi']):
    co=count[j]-np.median(np.delete(count,j));other=np.delete(pos,j,axis=0);loc=pos[j]-np.median(other,axis=0);peer=np.delete(d[j],j).mean()-glob
    self.V[a,w]=[co,loc[0],loc[1],peer,co*co];self.O[a,w]=1
  self.global_profile=self.V.sum(0)/(self.O.sum(0)[:,None]+8)
  eligible=self.support>=5
  self.profile_sd=self.global_profile[eligible].std(0)if eligible.any()else np.ones(5);self.profile_sd=np.where(self.profile_sd>1e-4,self.profile_sd,1.)
  Z=self.global_profile/self.profile_sd;self.D=cdist(Z,Z)/np.sqrt(5);np.fill_diagonal(self.D,0)
  self.types={};ix=np.flatnonzero(eligible)
  for k in (2,3,4):
   lab=np.full(m,-1,int)
   if len(ix)>=k:lab[ix]=cut_tree(linkage(Z[ix],method='ward'),n_clusters=[k]).ravel()
   self.types[k]=lab
 def state(self,g):
  key=g['key']
  if key not in self._cache:
   q=self.context(g);n=np.einsum('g,gw->w',q,self.O);v=np.einsum('g,gwf->wf',q,self.V);profile=(v+8*self.global_profile)/(n[:,None]+8);Z=profile/self.profile_sd;D=cdist(Z,Z)/np.sqrt(5);np.fill_diagonal(D,0);self._cache[key]=dict(q=q,D=D,N=np.minimum.outer(n,n))
  return self._cache[key]

SPECS={'equal':dict(temp=0.),'profile_continuous':dict(temp=.5),'profile_context':dict(temp=.5,context=True),'profile_type2':dict(types=2),'profile_type3':dict(types=3),'profile_type4':dict(types=4)}

def choose(train,meta,workers,outer):
 bs=sorted({g['building']for g in train});fold={b:j%3 for j,b in enumerate(bs)};vals=[]
 for f in range(3):
  tr=[g for g in train if fold[g['building']]!=f];va=[g for g in train if fold[g['building']]==f]
  if not tr or not va:continue
  L=ProfileLearner(tr,meta,workers,[outer]+[b for b in bs if fold[b]==f])
  for g in va:
   n=len(g['ids'])
   for k in (2,4,6,8):
    if n<k+2:continue
    for rep in range(2):
     order=c.seed('inner',g['key'],k,rep).permutation(n);si=order[:k];hi=order[k:]
     for name,sp in SPECS.items():
      ai,w=c.distribution(g,si,hi,L,sp);loss=c.scores(g,hi,ai,w)['kernel_score'];vals.append(dict(image_id=g['image_id'],k=k,name=name,loss=loss))
 df=pd.DataFrame(vals);settings={};audit=[]
 for k in (2,4,6,8):
  dd=df[df.k==k]if len(df)else pd.DataFrame()
  loss=dd.groupby(['name','image_id']).loss.mean().groupby('name').mean().to_dict()if len(dd)else {};win=min(SPECS,key=lambda name:(loss.get(name,np.inf),list(SPECS).index(name)))
  settings[k]=win;audit.append(dict(outer_building=outer,k=k,selected=win,inner_images=dd.image_id.nunique()if len(dd)else 0,losses=str(loss)))
 return settings,audit

def run(out):
 dest=out/'profile_alternative';dest.mkdir(exist_ok=True);s,pools,bank,raw,meta,workers=c.prepare(out);rows=[];audits=[];members=[];profiles=[]
 for arm in ('manual','semi','oos_geometry'):
  pp=[g for g in pools if g['condition']==arm and len(g['ids'])>=2]
  for b in sorted({g['building']for g in pp}):
   tr=[g for g in pp if g['building']!=b];te=[g for g in pp if g['building']==b]
   if not tr:continue
   L=ProfileLearner(tr,meta,workers,[b]);settings,aa=choose(tr,meta,workers,b);audits.extend(dict(condition=arm,**r)for r in aa)
   for j,w in enumerate(workers):
    profiles.append(dict(condition=arm,outer_building=b,worker_id=w,support=int(L.support[j]),log_count_relative=L.global_profile[j,0],top_relative=L.global_profile[j,1],bottom_relative=L.global_profile[j,2],peer_distance_relative=L.global_profile[j,3],squared_count_relative=L.global_profile[j,4]))
    for k,lab in L.types.items():members.append(dict(condition=arm,outer_building=b,worker_id=w,n_types=k,type_id=int(lab[j]),support=int(L.support[j])))
   for g in te:
    n=len(g['ids'])
    for k in (2,4,6,8):
     if n<k+2:continue
     for rep in range(6):
      order=c.seed('outer',g['key'],rep).permutation(n);si=order[:k];hi=order[k:]
      for name,sp in list(SPECS.items())+[('selected_profile',SPECS[settings[k]])]:
       ai,w=c.distribution(g,si,hi,L,sp);sc=c.scores(g,hi,ai,w);rows.append(dict(image_id=g['image_id'],building=b,condition=arm,k=k,repeat=rep,method=name,selected=settings[k]if name=='selected_profile'else name,n_valid=n,seed_workers='|'.join(g['workers'][j]for j in si),holdout_workers='|'.join(g['workers'][j]for j in hi),**c.compact_scores(sc)))
   print('PROFILE_FOLD',arm,b,flush=True)
 df=pd.DataFrame(rows);df.to_csv(dest/'heldout_predictions.csv.gz',index=False);pd.DataFrame(audits).to_csv(dest/'training_selection.csv',index=False);pd.DataFrame(profiles).to_csv(dest/'worker_profiles.csv',index=False);pd.DataFrame(members).to_csv(dest/'worker_types.csv',index=False)
 metrics=['kernel_score','count_brier','count_tv','uncovered_count','abs_pair_disagreement_error'];agg=df.groupby(['condition','k','method','image_id','building'],as_index=False)[metrics].mean();agg.to_csv(dest/'per_image.csv',index=False);agg.groupby(['condition','k','method']).agg(images=('image_id','nunique'),kernel=('kernel_score','mean'),brier=('count_brier','mean'),tv=('count_tv','mean')).reset_index().to_csv(dest/'summary.csv',index=False)
 orig=pd.read_csv(out/'per_image_scores.csv');allv=pd.concat([agg,orig[orig.method.isin(['selected_person','seed_person_t025'])][list(agg.columns)]],ignore_index=True);paired=[]
 for (arm,k),g in allv.groupby(['condition','k']):
  for name in SPECS.keys()|{'selected_profile'}:
   for base in ('equal','selected_person'):
    if name==base:continue
    rr=paired_fast(g,name,base,'kernel_score')
    if rr:paired.append(dict(condition=arm,k=k,**rr))
 pd.DataFrame(paired).to_csv(dest/'paired_increment.csv',index=False)
 repro=[]
 for arm in ('manual','semi','oos_geometry'):
  pp=[g for g in pools if g['condition']==arm and len(g['ids'])>=2];bs=sorted({g['building']for g in pp})
  if len(bs)<4:continue
  for rep in range(10):
   order=c.seed('profile_disjoint_halves',arm,rep).permutation(bs);left=set(order[:len(bs)//2]);A=ProfileLearner([g for g in pp if g['building']in left],meta,workers);B=ProfileLearner([g for g in pp if g['building']not in left],meta,workers)
   for k in (2,3,4):
    a=A.types[k];b=B.types[k];mask=(a>=0)&(b>=0)
    if mask.sum()>=4:repro.append(dict(condition=arm,repeat=rep,n_types=k,workers=int(mask.sum()),ari=adjusted_rand_score(a[mask],b[mask])))
 pd.DataFrame(repro).to_csv(dest/'disjoint_type_reproducibility.csv',index=False)
 c.js(dest/'method.json',dict(status='complete',additional_exploration_trigger='co-annotation average-link types often collapse to a large group plus singleton profiles',five_features=['within-image relative log count','relative ceiling endpoint mean','relative floor endpoint mean','within-image relative peer distance','mean squared relative log count'],worker_scaling='training workers only',shrinkage=8,grouping='Ward on shrunken standardized training-only behavioral profile',image_condition='training-image kernel weights; no target human outcome beyond exposed seeds',no_quality_truth_axis=True,no_time_or_fatigue_model=True))
 print('PROFILE_SUMMARY\n'+pd.read_csv(dest/'summary.csv').to_string(index=False),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();run(a.output)
