"""Candidate-coverage probability: a deliberately partial, abstaining extension.

Predict three observable events for an unseen real person: geometry compatible
with the exposed candidates; a new geometry with an already-present point count;
or a point count absent from the candidates. No missing geometry is invented.
"""
from __future__ import annotations
import argparse, collections
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_growth_v1 import matrix

KVALS=(2,4,6,8)

def row_features(g,si,hi,L,meta):
 m=meta.loc[g['image_id']]if g['image_id']in meta.index else {};pc=g['count'][si];n=len(si);dd=g['dm'][np.ix_(si,si)];eq=np.equal.outer(pc,pc);ix=np.triu_indices(n,1);same=eq[ix];vals=dd[ix][same]
 image=list(L.numeric(g))+[float(m.get('floor_boundary')=='partial'),float(m.get('ceiling_boundary')=='partial'),float(m.get('reflection_glass')=='present'),float(m.get('reflection_glass')=='unknown')]
 for name in ('sleep','bathroom','kitchen','dining','living','work','circulation','storage'):image.append(float(m.get('main_function_primary')==name))
 prefix=[1/max(1,n),np.log1p(n),len(set(pc))/max(1,n),np.log1p(np.median(pc)),np.log1p(pc.max()-pc.min()),float(np.mean(~same))if len(same)else 0.,float(np.mean(vals))if len(vals)else 0.,float(np.mean((~same)|(dd[ix]>.1)))if len(same)else 0.]
 a=g['wi'][hi];b=g['wi'][si];d=L.D[np.ix_(a,b)];dc=L.state(g)['D'][np.ix_(a,b)];personal=np.c_[L.bias[a],L.bias[a]-np.mean(L.bias[b]),d.mean(1),d.min(1),dc.mean(1),dc.min(1)]
 return np.tile(image,(len(hi),1)),np.tile(prefix,(len(hi),1)),personal

def make_rows(groups,L,meta,repeats,kind):
 records=[];images=[];prefix=[];persons=[];y=[]
 for g in groups:
  n=len(g['ids'])
  for k in KVALS:
   if n<k+2:continue
   for rep in range(repeats):
    order=c.seed(kind,g['key'],rep).permutation(n);si=order[:k];hi=order[k:];i,p,w=row_features(g,si,hi,L,meta);d=g['dm'][np.ix_(hi,si)];eq=g['count'][hi,None]==g['count'][si][None,:];covered=np.any(eq&(d<=.1),axis=1);labels=np.where(covered,0,np.where(eq.any(1),1,2))
    for j,h in enumerate(hi):records.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],k=k,repeat=rep,worker_id=g['workers'][h],canonical_id=g['ids'][h],seed_workers='|'.join(g['workers'][a]for a in si),seed_ids='|'.join(g['ids'][a]for a in si),n_hidden=len(hi)))
    images.extend(i);prefix.extend(p);persons.extend(w);y.extend(labels)
 return pd.DataFrame(records),np.array(images),np.array(prefix),np.array(persons),np.array(y,int)

def design(i,p,w,name):
 if name=='prefix':return p
 if name=='image_prefix':return np.c_[i,p]
 if name=='person_prefix':return np.c_[p,w]
 if name=='joint':return np.c_[i,p,w]
 if name=='interaction':return np.c_[i,p,w,w*i[:,3,None],w*p[:,5,None]]
 raise ValueError(name)

def train_predict(X,y,records,Xtest,C):
 mu=X.mean(0);sd=X.std(0);sd=np.where(sd>.01,sd,1.);Z=(X-mu)/sd;T=(Xtest-mu)/sd
 weights=1/records.groupby(['image_id','k']).canonical_id.transform('size').to_numpy(float);weights*=len(weights)/weights.sum()
 prior=np.bincount(y,weights=weights,minlength=3)+.5;prior/=prior.sum()
 if len(set(y))<2:return np.tile(prior,(len(T),1))
 model=LogisticRegression(C=C,max_iter=500,solver='lbfgs',tol=1e-7);model.fit(Z,y,sample_weight=weights);pred=np.zeros((len(T),3));pred[:,model.classes_]=model.predict_proba(T);return .995*pred+.005*prior

def run(out):
 dest=out/'novelty_extension';dest.mkdir(exist_ok=True);s,pools,bank,raw,meta,workers=c.prepare(out);rows=[];selections=[]
 names=('prefix','image_prefix','person_prefix','joint','interaction')
 for arm in ('manual','semi','oos_geometry'):
  pp=[g for g in pools if g['condition']==arm and len(g['ids'])>=4];bs=sorted({g['building']for g in pp})
  for b in bs:
   tr=[g for g in pp if g['building']!=b];te=[g for g in pp if g['building']==b]
   if not tr:continue
   L=CachedLearner(tr,meta,workers,[b]);R,I,P,W,Y=make_rows(tr,L,meta,2,'novelty_training')
   # Training worker relations cannot include the validation image/building.
   validation=[];tb=sorted({g['building']for g in tr});fold={v:j%3 for j,v in enumerate(tb)}
   for f in range(3):
    fit=[g for g in tr if fold[g['building']]!=f];val=[g for g in tr if fold[g['building']]==f]
    if not fit or not val:continue
    V=CachedLearner(fit,meta,workers,[b]+[v for v in tb if fold[v]==f]);r,i,p,w,y=make_rows(fit,V,meta,1,'novelty_training');vr,vi,vp,vw,vy=make_rows(val,V,meta,1,'novelty_validation')
    if not len(r)or not len(vr):continue
    for name in names:
     for C in (.1,1.):
      pr=train_predict(design(i,p,w,name),y,r,design(vi,vp,vw,name),C);loss=np.sum((pr-np.eye(3)[vy])**2,axis=1);score=float(pd.DataFrame({'image':vr.image_id,'loss':loss}).groupby('image').loss.mean().mean());validation.append(dict(method=name,C=C,fold=f,loss=score))
   vr,vi,vp,vw,vy=make_rows(te,L,meta,2,'outer');specs=[]
   for name in names:
    vv=pd.DataFrame([x for x in validation if x['method']==name]);C=float(vv.groupby('C').loss.mean().idxmin())if len(vv)else .1;specs.append((name,C));selections.append(dict(condition=arm,outer_building=b,method=name,C=C,status='training_building_cv'if len(vv)else 'default_no_inner_support'))
   if not len(vr):continue
   # Small-sample frequency baseline depends on k only, never target full n.
   bas=np.zeros((len(vr),3))
   for k in KVALS:
    mask=R.k==k;counts=np.bincount(Y[mask],weights=1/R[mask].groupby('image_id').canonical_id.transform('size').to_numpy(),minlength=3)+.5 if mask.any()else np.ones(3);bas[vr.k==k]=counts/counts.sum()
   preds=[('training_frequency',bas),('closed_seed_assumes_no_novelty',np.tile([1.,0.,0.],(len(vr),1)))]
   for name,C in specs:preds.append((name,train_predict(design(I,P,W,name),Y,R,design(vi,vp,vw,name),C)))
   for name,pr in preds:
    for j,r in enumerate(vr.to_dict('records')):rows.append(dict(r,method=name,actual_event=int(vy[j]),p_covered=pr[j,0],p_new_same_count_geometry=pr[j,1],p_new_count=pr[j,2],brier=float(np.sum((pr[j]-np.eye(3)[vy[j]])**2)),uncovered_brier=float(((1-pr[j,0])-int(vy[j]!=0))**2)))
   print('NOVELTY_FOLD',arm,b,'heldout',len(vr),flush=True)
 df=pd.DataFrame(rows);df.to_csv(dest/'heldout_novelty_predictions.csv.gz',index=False);pd.DataFrame(selections).to_csv(dest/'training_only_selection.csv',index=False)
 agg=df.groupby(['condition','k','method','image_id','building'],as_index=False)[['brier','uncovered_brier','p_new_count','p_new_same_count_geometry']].mean();agg.to_csv(dest/'per_image_scores.csv',index=False);summary=agg.groupby(['condition','k','method']).agg(images=('image_id','nunique'),brier=('brier','mean'),uncovered_brier=('uncovered_brier','mean')).reset_index();summary.to_csv(dest/'summary.csv',index=False)
 from tools.thesis_main.analysis.image_portrait.person_distribution_diagnostics_v1 import paired_fast
 paired=[]
 for (arm,k),g in agg.groupby(['condition','k']):
  for name in names:
   for base in ('training_frequency','prefix','image_prefix'):
    if name==base:continue
    z=paired_fast(g,name,base,'brier')
    if z:paired.append(dict(condition=arm,k=k,**z))
 pd.DataFrame(paired).to_csv(dest/'paired_increment.csv',index=False)
 c.js(dest/'method.json',dict(target='three-way forecast of an unseen real response relative to current seed geometry',geometry_cut=.1,outer='leave building',inner='three training-building groups',group_profiles='training source used to construct training features; target/validation buildings excluded; retrospective known workers',future_target_n_used_as_feature=False,unknown_geometry_generated=False,role='abstaining extension: it predicts unsupported mass, not new polygon coordinates or a complete future clustering',raw_difficulty_used=False,review39_used=False))
 c.js(dest/'COMPLETE.json',dict(status='complete',real_images=df.image_id.nunique(),rows=len(df)))
 print('NOVELTY_SUMMARY\n'+summary.to_string(index=False),flush=True)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();run(a.output)
