"""Numerically equivalent cached runner plus genuinely uniform unique anchors.

This runner is the executed entry point. It retains the readable reference
implementation and changes no data, learning folds or scoring definitions.
"""
from pathlib import Path
import argparse
import numpy as np
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as core

ReferenceLearner=core.Learner
class CachedLearner(ReferenceLearner):
 def affinity_weights(self,g,targets,kind):
  if kind=='uniform':
   n=len(g['model_points'])
   return np.full((len(targets),n),1/max(1,n))
  return super().affinity_weights(g,targets,kind)
 def count_prior(self,g,hi,context=False,personal=False,types=0):
  key=('count_prior',g['key'],context,personal,types)
  if key not in self._cache:
   q=self.state(g)['q'] if context else np.ones(len(self.train));ans=np.zeros((self.m,65))
   for j,h in enumerate(self.train):
    ww=np.ones((self.m,len(h['wi'])))
    if personal:ww=np.exp(-self.D[:,h['wi']]/.25)
    if types:
     labs=self.types[types];ww=np.where((labs[:,None]>=0)&(labs[:,None]==labs[h['wi']][None,:]),1.,.25)
    ww=ww/np.maximum(ww.sum(1,keepdims=True),core.EPS)
    ans+=q[j]*(ww@np.eye(65)[np.minimum(h['count'],64)])
   empty=ans.sum(1)==0;ans[empty,3:13]=1.;ans+=1e-6;ans/=ans.sum(1,keepdims=True)
   self._cache[key]=ans
  return self._cache[key][g['wi'][hi]]

def test_cache(out):
 import pandas as pd
 workers=['W001','W002','W003']
 def group(i,w,c):
  n=len(w);points=[np.array([[j*40.,100.+v],[j*40.,400.-v],[200.,110.],[200.,390.],[400.,120.],[400.,380.]])for j,v in enumerate(c)]
  return dict(key='manual|'+i,image_id=i,building=i.split('_')[0],wi=np.array(w),workers=[workers[z]for z in w],count=np.array(c),pcs=np.array(c)*2,points=points,model_points=[],model_sources=[],K=np.eye(n),dm=np.ones((n,n))*.1-np.eye(n)*.1)
 train=[group('a_1',[0,1,2],[3,4,5]),group('b_1',[0,2],[4,5])];meta=pd.DataFrame([dict(image_id=x['image_id'],scene_category='test',main_function_primary='test',floor_boundary='partial',ceiling_boundary='present')for x in train]).set_index('image_id')
 a=ReferenceLearner(train,meta,workers);b=CachedLearner(train,meta,workers);g=train[0];checks=0
 for ctx in (False,True):
  for personal in (False,True):
   for typ in (0,2,3,4):
    p=a.count_prior(g,np.array([0,2]),ctx,personal,typ);q=b.count_prior(g,np.array([0,2]),ctx,personal,typ);assert np.allclose(p,q,atol=1e-12);checks+=1
 assert b.affinity_weights(dict(model_points=[1,2]),[0,1],'uniform').tolist()==[[.5,.5],[.5,.5]]
 core.js(out/'cache_equivalence_tests.json',dict(status='passed',count=checks+1,tests='16 reference-versus-cached prior checks plus unique-anchor uniformity'))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(core.OUT_DEFAULT));ap.add_argument('--test-only',action='store_true');args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 core.self_test(args.output);test_cache(args.output);core.Learner=CachedLearner
 if not args.test_only:core.fit_all(args.output)
