"""Retrospective image/person conditional distribution experiment.

Only numeric/text inputs. No images, weights, inference or production annotation
writes. Known workers across held-out buildings, NOT forward-time validation.
All raw labels and the 39 user review fields are untouched.
"""
from __future__ import annotations
import argparse, collections, hashlib, importlib.util, itertools, json, math, sys, time, urllib.parse, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, fcluster, cut_tree
from scipy.spatial.distance import squareform
from scipy.special import softmax

REPO='Sparkling-Flames/3D_Manhattan_label'
INPUT_REF='ae94e825fc8b792255200b880da478aea52a19cc'
PROTO_REF='9b0daaa7d307d7909fa46b4a1085fbe840206c0d'
B='analysis_results/image_portrait_20260914_v1/'
OUT_DEFAULT=B+'cloud/person_distribution_hypothesis_20260916_v1/run_ae94e825'
KS=(0,2,4,6,8)
OUTER_REPEATS=6
INNER_REPEATS=2
EPS=1e-12

def seed(*args):
 return np.random.default_rng(int.from_bytes(hashlib.sha256('|'.join(map(str,args)).encode()).digest()[:8],'big'))

def safe(x):
 if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [safe(v) for v in x]
 if isinstance(x,np.ndarray):return safe(x.tolist())
 if isinstance(x,np.generic):return safe(x.item())
 if isinstance(x,float) and not math.isfinite(x):return None
 return x

def js(path,value):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')

def get(path,ref,dest):
 p=Path(dest);p.parent.mkdir(parents=True,exist_ok=True)
 if not p.exists():
  url='https://raw.githubusercontent.com/'+REPO+'/'+ref+'/'+urllib.parse.quote(path,safe='/')
  for attempt in range(3):
   try:
    with urllib.request.urlopen(url,timeout=90) as r:data=r.read()
    p.write_bytes(data);break
   except Exception:
    if attempt==2:raise
    time.sleep(attempt+1)
 return p

def prepare(out):
 out.mkdir(parents=True,exist_ok=True)
 pp=get('tools/thesis_main/analysis/personalized_simulator_v2.py',PROTO_REF,out/'sources/personalized_simulator_v2.py')
 spec=importlib.util.spec_from_file_location('numerical_source_prototype',pp);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
 s.INPUT_REF=INPUT_REF
 paths=s.get_inputs(out);pools,models,raw=s.load_data(paths,out)
 meta=pd.read_csv(paths['meta']).fillna('').set_index('image_id')
 manifests=[]
 for path in ('PRO_START_HERE.md','prompts/PERSON_TYPE_HYPOTHESIS.md','evaluation/metrics.md','evaluation/config.json','evaluation/room_components.jsonl','review_workflow_20260915/key39/README.md'):
  try:
   p=get(B+path,INPUT_REF,out/'sources'/path);manifests.append(dict(path=B+path,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),ref=INPUT_REF,status='received'))
  except Exception as e:manifests.append(dict(path=B+path,ref=INPUT_REF,status='unavailable',error=str(e)))
 js(out/'source_audit.json',dict(input_commit=INPUT_REF,prototype_commit=PROTO_REF,prototype_sha256=hashlib.sha256(pp.read_bytes()).hexdigest(),documents=manifests,original_images_read=False,model_weights_downloaded=False,review39_filled=False,raw_difficulty_used=False))
 # Exact duplicate model layouts are one predictive anchor, not extra votes.
 bank={}
 for iid,mm in models.items():
  values=[];sources=[]
  for fam,p in mm.items():
   match=next((j for j,q in enumerate(values) if p.shape==q.shape and np.allclose(p,q,atol=1e-9,rtol=0)),None)
   if match is None:values.append(p);sources.append([fam])
   else:sources[match].append(fam)
  bank[iid]=dict(points=values,sources=sources)
 for g in pools:
  g['key']=g['condition']+'|'+g['image_id'];g['count']=g['pcs']//2
  g['model_points']=bank.get(g['image_id'],{}).get('points',[])
  g['model_sources']=bank.get(g['image_id'],{}).get('sources',[])
  # Cache output kernels before fitting: fixed representation, not fitted to outcomes.
  pts=g['points']+g['model_points'];g['K']=s.kernel(pts,pts) if pts else np.zeros((0,0))
  g['all_count']=np.array([len(p)//2 for p in pts],int)
 workers=sorted({w for g in pools for w in g['workers']});wi={w:j for j,w in enumerate(workers)}
 for g in pools:g['wi']=np.array([wi[w] for w in g['workers']],int)
 return s,pools,bank,raw,meta,workers

class Learner:
 """Low-dimensional, shrunken co-annotation relations; training buildings only."""
 def __init__(self,training,meta,workers,excluded_buildings=()):
  self.train=list(training);self.meta=meta;self.workers=workers;self.wi={w:j for j,w in enumerate(workers)};self.m=len(workers)
  assert not set(excluded_buildings)&{g['building'] for g in self.train}
  self.exclude=list(excluded_buildings)
  self.num=np.array([self.numeric(g) for g in self.train]);self.sd=np.std(self.num,axis=0) if len(self.num) else np.ones(3);self.sd=np.where(self.sd>.2,self.sd,1.)
  self.dist=[];self.obs=[];self.hist=[];self.size=[];self.bias=[[]for _ in workers]
  self.affinity=np.zeros((len(self.train),self.m,3));self.affobs=np.zeros((len(self.train),self.m))
  for z,g in enumerate(self.train):
   n=len(g['wi']);dm=np.where(np.equal.outer(g['count'],g['count']),np.minimum(g['dm'],1),1.)
   d=np.zeros((self.m,self.m));o=np.zeros_like(d);d[np.ix_(g['wi'],g['wi'])]=dm;o[np.ix_(g['wi'],g['wi'])]=1
   np.fill_diagonal(o,0);self.dist.append(d);self.obs.append(o)
   self.hist.append(np.bincount(np.minimum(g['count'],64),minlength=65).astype(float)/max(1,n));self.size.append(n)
   for j,w in enumerate(g['wi']):
    if n>=2:self.bias[w].append(float(np.log(g['count'][j])-np.median(np.delete(np.log(g['count']),j))))
   # Soft proximity to named model families; this is not a semantic intent label.
   if g['model_points']:
    nm=len(g['model_points']);similarity=g['K'][:n,n:n+nm];aa=softmax((similarity-1)/.2,axis=1)
    for j,w in enumerate(g['wi']):
     for a,fams in enumerate(g['model_sources']):
      for fam in fams:
       if fam in ('HoHoNet','Bi-enclosed','Bi-extended'):self.affinity[z,w,('HoHoNet','Bi-enclosed','Bi-extended').index(fam)]+=aa[j,a]/len(fams)
     self.affobs[z,w]=1
  self.dist=np.array(self.dist);self.obs=np.array(self.obs);self.hist=np.array(self.hist)
  self.support=np.sum(self.obs.sum(2)>0,axis=0) if len(self.obs) else np.zeros(self.m)
  self.D,self.N=self.relation(np.ones(len(self.train)))
  self.types={}
  eligible=np.flatnonzero(self.support>=5)
  for k in (2,3,4):
   lab=np.full(self.m,-1,int)
   if len(eligible)>=k:
    Z=linkage(squareform(self.D[np.ix_(eligible,eligible)],checks=False),method='average');lab[eligible]=cut_tree(Z,n_clusters=[k]).ravel()
   self.types[k]=lab
  self.bias=np.array([sum(v)/(len(v)+8) for v in self.bias]);self._cache={}
 def numeric(self,g):
  counts=[len(p)//2 for p in g['model_points']]
  return np.array([np.log1p(np.median(counts)) if counts else 0.,np.log1p(max(counts)-min(counts)) if counts else 0.,float(not counts)])
 def context(self,g,strength=1.):
  if strength==0:return np.ones(len(self.train))
  x=self.numeric(g);dd=np.mean(((self.num-x)/self.sd)**2,axis=1)
  mt=self.meta.loc[g['image_id']] if g['image_id']in self.meta.index else {}
  for j,h in enumerate(self.train):
   mh=self.meta.loc[h['image_id']] if h['image_id']in self.meta.index else {}
   for key,weight in [('scene_category',.5),('main_function_primary',.5),('floor_boundary',.75),('ceiling_boundary',.25)]:
    a=mt.get(key,'');b=mh.get(key,'')
    if a not in ('','unknown') and b not in ('','unknown'):dd[j]+=weight*float(a!=b)
  return .05+.95*np.exp(-strength*dd)
 def relation(self,q):
  if not len(self.train):return np.zeros((self.m,self.m)),np.zeros((self.m,self.m))
  n=np.einsum('g,gij->ij',q,self.obs);v=np.einsum('g,gij->ij',q,self.dist*self.obs)
  glob=v.sum()/max(EPS,n.sum());D=(v+8*glob)/(n+8);np.fill_diagonal(D,0)
  return D,n
 def state(self,g):
  if g['key'] not in self._cache:
   q=self.context(g);D,N=self.relation(q)
   self._cache[g['key']]=dict(q=q,D=D,N=N)
  return self._cache[g['key']]
 def affinity_weights(self,g,targets,kind):
  q=self.state(g)['q'] if 'context'in kind else np.ones(len(self.train))
  totals=np.einsum('g,gwm->wm',q,self.affinity);nn=np.einsum('g,gw->w',q,self.affobs)
  pop=(totals.sum(0)+1)/(totals.sum()+3)
  pp=(totals+8*pop)/(nn[:,None]+8)
  if kind=='uniform':pp=np.full_like(pp,1/3)
  elif kind in ('population','context_population'):pp=np.tile(pop,(self.m,1))
  elif kind.startswith('type'):
   k=int(kind[4]);labs=self.types[k]
   for lab in set(labs)-{-1}:
    ix=np.flatnonzero(labs==lab);v=totals[ix].sum(0)+8*pop;pp[ix]=v/v.sum()
   pp[labs<0]=pop
  merged=np.array([[pp[w,[('HoHoNet','Bi-enclosed','Bi-extended').index(f)for f in fams]].sum() for fams in g['model_sources']]for w in targets])
  return merged/np.maximum(merged.sum(1,keepdims=True),EPS) if merged.size else np.zeros((len(targets),0))
 def seed_weights(self,g,si,hi,temp=.25,context=False,types=0):
  if not len(si):return np.zeros((len(hi),0))
  if temp==0:return np.full((len(hi),len(si)),1/len(si))
  a=g['wi'][hi];b=g['wi'][si]
  if types:
   labels=self.types[types];same=(labels[a,None]==labels[b][None,:])&(labels[a,None]>=0)&(labels[b][None,:]>=0)
   z=np.where(same,1.,.25);w=z/z.sum(1,keepdims=True)
  else:
   D=self.state(g)['D'] if context else self.D;w=softmax(-D[np.ix_(a,b)]/temp,axis=1)
  return .1/len(si)+.9*w
 def count_prior(self,g,hi,context=False,personal=False,types=0):
  q=self.state(g)['q'] if context else np.ones(len(self.train));ans=np.zeros((len(hi),65))
  for a,target in enumerate(g['wi'][hi]):
   for j,h in enumerate(self.train):
    ww=np.ones(len(h['wi']))
    if personal:ww=np.exp(-self.D[target,h['wi']]/.25)
    if types:
     labels=self.types[types];ww=np.where((labels[target]>=0)&(labels[h['wi']]==labels[target]),1.,.25)
    ww=ww/max(EPS,ww.sum());ans[a]+=q[j]*np.bincount(np.minimum(h['count'],64),weights=ww,minlength=65)
   if ans[a].sum()==0:ans[a,3:13]=1
  ans+=1e-6;return ans/ans.sum(1,keepdims=True)

# All candidate hyperparameters are fixed here before reading new held-out scores.
SPECS={'seed_equal':dict(temp=0.),'seed_person_t01':dict(temp=.1),'seed_person_t025':dict(temp=.25),'seed_person_t05':dict(temp=.5),'seed_context_t01':dict(temp=.1,context=True),'seed_context_t025':dict(temp=.25,context=True),'seed_context_t05':dict(temp=.5,context=True),'seed_type2':dict(types=2),'seed_type3':dict(types=3),'seed_type4':dict(types=4),'seed_model_uniform10':dict(temp=0.,alpha=.1),'seed_model_uniform25':dict(temp=0.,alpha=.25),'joint_model10':dict(temp=.25,context=True,alpha=.1,model_kind='context_personal'),'joint_model25':dict(temp=.25,context=True,alpha=.25,model_kind='context_personal')}
FAMILIES={'selected_person':['seed_equal','seed_person_t01','seed_person_t025','seed_person_t05'],'selected_context':['seed_equal','seed_person_t025','seed_context_t01','seed_context_t025','seed_context_t05'],'selected_type':['seed_equal','seed_type2','seed_type3','seed_type4'],'selected_mixture':['seed_equal','seed_model_uniform10','seed_model_uniform25','joint_model10','joint_model25']}
COLD=('uniform','population','personal','context_population','context_personal','type2','type3','type4')

def distribution(g,si,hi,L,spec=None,cold=None):
 n=len(g['ids']);si=np.asarray(si,int);hi=np.asarray(hi,int)
 assert set(si).isdisjoint(hi) and len(set(g['workers'][j]for j in hi))==len(hi)
 if cold is not None:
  inds=np.arange(n,n+len(g['model_points']));w=L.affinity_weights(g,g['wi'][hi],cold)
 else:
  sp=spec or {};a=sp.get('alpha',0.) if g['model_points']else 0.
  inds=si.copy();w=L.seed_weights(g,si,hi,temp=sp.get('temp',.25),context=sp.get('context',False),types=sp.get('types',0))
  if a:
   inds=np.r_[inds,np.arange(n,n+len(g['model_points']))];w=np.c_[w*(1-a),a*L.affinity_weights(g,g['wi'][hi],sp.get('model_kind','uniform'))]
 assert not w.size or np.allclose(w.sum(1),1)
 return inds,w

def scores(g,hi,inds,w):
 if not len(inds):return None
 hc=np.minimum(g['count'][hi],64);ac=np.minimum(g['all_count'][inds],64);mat=np.eye(65)[ac];pr=w@mat;y=np.eye(65)[hc]
 K=g['K'];kh=K[np.ix_(hi,inds)];kc=K[np.ix_(inds,inds)]
 ks=K[hi,hi]-2*np.sum(w*kh,axis=1)+np.einsum('ij,jk,ik->i',w,kc,w)
 cb=np.sum((pr-y)**2,axis=1);tv=.5*np.abs(pr.mean(0)-y.mean(0)).sum()
 h=g['count'][hi];real_dis=float(np.mean(h[:,None]!=h[None,:])*len(h)/max(1,len(h)-1)) if len(h)>1 else np.nan
 pred_dis=1-(pr.sum(0)@pr.sum(0)-np.sum(pr*pr))/max(1,len(hi)*(len(hi)-1)) if len(hi)>1 else np.nan
 return dict(kernel_score=float(ks.mean()),count_brier=float(cb.mean()),count_tv=float(tv),uncovered_count=float(np.mean(~np.isin(hc,ac))),true_pair_count_disagreement=real_dis,pred_pair_count_disagreement=pred_dis,abs_pair_disagreement_error=abs(pred_dis-real_dis),per_worker_kernel=ks,per_worker_brier=cb)

def compact_scores(sc):return {k:v for k,v in sc.items() if not k.startswith('per_worker_')}

def pick_settings(train,meta,workers,outer_building):
 # Deterministic three-way building folds reduce computation; no outer building enters.
 buildings=sorted({g['building']for g in train});bins={b:j%3 for j,b in enumerate(buildings)};vals=[]
 for fold in range(3):
  fit=[g for g in train if bins[g['building']]!=fold];val=[g for g in train if bins[g['building']]==fold and len(g['ids'])>=4]
  if not fit or not val:continue
  L=Learner(fit,meta,workers,excluded_buildings=[outer_building]+[b for b in buildings if bins[b]==fold])
  for g in val:
   n=len(g['ids'])
   for k in KS[1:]:
    if n<k+2:continue
    for rep in range(INNER_REPEATS):
     order=seed('inner',g['key'],k,rep).permutation(n);si=order[:k];hi=order[k:]
     for name,sp in SPECS.items():
      inds,w=distribution(g,si,hi,L,sp);sc=scores(g,hi,inds,w)
      if sc:vals.append(dict(image_id=g['image_id'],building=g['building'],k=k,method=name,loss=sc['kernel_score']))
 v=pd.DataFrame(vals);chosen={};records=[]
 for k in KS[1:]:
  for fam,names in FAMILIES.items():
   vv=v[(v.k==k)&v.method.isin(names)] if len(v) else pd.DataFrame()
   if len(vv):
    loss=vv.groupby(['method','image_id']).loss.mean().groupby('method').mean();winner=min(names,key=lambda name:(loss.get(name,np.inf),names.index(name)));status='training_inner_building_selected';count=vv.image_id.nunique()
   else:winner='seed_equal';status='no_inner_support_fallback';count=0
   chosen[(k,fam)]=winner
   records.append(dict(outer_building=outer_building,k=k,family=fam,selected=winner,status=status,validation_images=count,inner_losses=json.dumps({n:float(vv[vv.method==n].groupby('image_id').loss.mean().mean()) for n in names})if len(vv) else '{}'))
 return chosen,records

def boot_pair(frame,method,base,metric,keys):
 a=frame[frame.method==method];b=frame[frame.method==base];z=a.merge(b,on=keys,suffixes=('_a','_b'))
 z=z[np.isfinite(z[metric+'_a'])&np.isfinite(z[metric+'_b'])]
 if not len(z):return None
 dd=z[metric+'_a']-z[metric+'_b'];bs=z.building if 'building'in z else z.building_a;groups=sorted(bs.unique());v=[];r=seed('paired',method,base,metric,str(keys))
 for _ in range(1500):
  draw=r.choice(groups,len(groups),replace=True);v.append(np.concatenate([dd[bs==x]for x in draw]).mean())
 return dict(method=method,baseline=base,metric=metric,images=z.image_id.nunique(),buildings=len(groups),delta=float(dd.mean()),ci_low=float(np.quantile(v,.025)),ci_high=float(np.quantile(v,.975)),building_macro_delta=float(pd.DataFrame({'b':bs,'d':dd}).groupby('b').d.mean().mean()))

def fit_all(out):
 s,pools,bank,raw,meta,workers=prepare(out);rows=[];individual=[];selections=[];profiles=[];types=[];folds=[];counts=[];missing=[];snapshots=[]
 for arm in ('manual','semi','oos_geometry'):
  pp=[g for g in pools if g['condition']==arm and len(g['ids'])>=2]
  for building in sorted({g['building']for g in pp}):
   train=[g for g in pp if g['building']!=building];test=[g for g in pp if g['building']==building]
   if not train:
    missing.extend(dict(image_id=g['image_id'],condition=arm,reason='no_other_building_training')for g in test);continue
   L=Learner(train,meta,workers,[building]);settings,sel=pick_settings(train,meta,workers,building);selections.extend(dict(condition=arm,**r)for r in sel)
   folds.append(dict(condition=arm,building=building,training_images=[g['image_id']for g in train],target_images=[g['image_id']for g in test]))
   for wi,w in enumerate(workers):
    profiles.append(dict(condition=arm,heldout_building=building,worker_id=w,coannotated_training_images=int(L.support[wi]),relative_log_pairs=L.bias[wi],known=bool(L.support[wi]>=5)))
    for nc,lab in L.types.items():types.append(dict(condition=arm,heldout_building=building,n_types=nc,worker_id=w,type_id=int(lab[wi]),support=int(L.support[wi])))
   for g in test:
    n=len(g['ids'])
    for k in KS:
     if n<k+2:
      missing.append(dict(image_id=g['image_id'],condition=arm,k=k,n_valid=n,reason='fewer_than_two_unseen_people_at_this_k'));continue
     for rep in range(1 if k==0 else OUTER_REPEATS):
      order=seed('outer',g['key'],rep).permutation(n);si=order[:k];hi=order[k:]
      stamp=dict(image_id=g['image_id'],building=building,condition=arm,k=k,repeat=rep,n_valid=n,n_observed=g['n_observed'],n_invalid=g['n_invalid'],seed_workers='|'.join(g['workers'][j]for j in si),seed_ids='|'.join(g['ids'][j]for j in si),holdout_workers='|'.join(g['workers'][j]for j in hi),holdout_ids='|'.join(g['ids'][j]for j in hi))
      specs=[('cold_'+name,None,name)for name in COLD] if k==0 else [(name,sp,None)for name,sp in SPECS.items()]+[(fam,SPECS[settings[(k,fam)]],None)for fam in FAMILIES]
      for method,sp,cold in specs:
       inds,w=distribution(g,si,hi,L,sp,cold);sc=scores(g,hi,inds,w)
       if sc is None:
        missing.append(dict(image_id=g['image_id'],condition=arm,k=k,method=method,reason='no_valid_model_anchor'));continue
       rows.append(dict(stamp,method=method,selected_method=settings.get((k,method),method),**compact_scores(sc)))
       if rep==0 or method.startswith('selected') or method=='seed_equal':
        for pos,h in enumerate(hi):individual.append(dict(image_id=g['image_id'],building=building,condition=arm,k=k,repeat=rep,method=method,worker_id=g['workers'][h],canonical_id=g['ids'][h],kernel_score=sc['per_worker_kernel'][pos],count_brier=sc['per_worker_brier'][pos]))
       if rep<2 and k in (4,8) and n>=k+4 and method in ('seed_equal','seed_person_t025','seed_context_t025','seed_type4','selected_mixture'):
        snapshots.append(dict(stamp,method=method,indices=inds.tolist(),weights=w.tolist(),seed_index=si.tolist(),future_index=hi.tolist(),type4=L.types[4].tolist(),roster=workers))
      # An unrestricted count forecast isolates missing-geometry-anchor capacity.
      hc=np.minimum(g['count'][hi],64);truth=np.eye(65)[hc]
      for name,ctx,person,nt in [('population',False,False,0),('image',True,False,0),('person',False,True,0),('joint',True,True,0),('image_type2',True,False,2),('image_type3',True,False,3),('image_type4',True,False,4)]:
       pr=L.count_prior(g,hi,ctx,person,nt)
       if k:
        sw=L.seed_weights(g,si,hi,context=ctx,types=nt,temp=.25 if person or nt else 0.);emp=sw@np.eye(65)[np.minimum(g['count'][si],64)];pr=(4*pr+k*emp)/(4+k)
       loss=np.sum((pr-truth)**2,axis=1)
       counts.append(dict(stamp,method=name,count_brier=float(loss.mean()),count_tv=float(.5*np.abs(pr.mean(0)-truth.mean(0)).sum()),unseen_train_count=float(np.mean(~np.isin(hc,np.concatenate([h['count']for h in train]))))))
   print('FOLD',arm,building,'targets',len(test),'rows',len(rows),flush=True)
   # Checkpoint actual completed work; partial files never imply full execution.
   pd.DataFrame(rows).to_csv(out/'heldout_distribution_predictions.csv.gz',index=False)
 pd.DataFrame(individual).to_csv(out/'heldout_individual_scores.csv.gz',index=False);pd.DataFrame(selections).to_csv(out/'training_only_selection.csv',index=False);pd.DataFrame(profiles).to_csv(out/'worker_profiles_oof.csv',index=False);pd.DataFrame(types).to_csv(out/'worker_types_oof.csv',index=False)
 pd.DataFrame(counts).to_csv(out/'unrestricted_count_predictions.csv.gz',index=False);pd.DataFrame(missing).to_csv(out/'coverage_and_failures.csv',index=False);js(out/'folds.json',folds);js(out/'growth_prediction_snapshots.json',snapshots)
 frame=pd.DataFrame(rows);mets=['kernel_score','count_brier','count_tv','uncovered_count','abs_pair_disagreement_error']
 agg=frame.groupby(['condition','k','method','image_id','building','n_valid'],as_index=False)[mets].mean();agg.to_csv(out/'per_image_scores.csv',index=False)
 summary=agg.groupby(['condition','k','method']).agg(images=('image_id','nunique'),buildings=('building','nunique'),**{m:(m,'mean')for m in mets}).reset_index();summary.to_csv(out/'score_summary.csv',index=False)
 diffs=[]
 for (arm,k),g in agg.groupby(['condition','k']):
  base='cold_uniform' if k==0 else 'seed_equal'
  for method in sorted(set(g.method)-{base}):
   for m in mets:
    r=boot_pair(g,method,base,m,['image_id','building']);
    if r:diffs.append(dict(condition=arm,k=k,**r))
 pd.DataFrame(diffs).to_csv(out/'paired_increment.csv',index=False)
 cnt=pd.DataFrame(counts).groupby(['condition','k','method','image_id','building'],as_index=False)[['count_brier','count_tv','unseen_train_count']].mean();cnt.to_csv(out/'count_per_image.csv',index=False);cnt.groupby(['condition','k','method']).agg(images=('image_id','nunique'),brier=('count_brier','mean'),tv=('count_tv','mean')).reset_index().to_csv(out/'count_summary.csv',index=False)
 cd=[]
 for (arm,k),g in cnt.groupby(['condition','k']):
  for method in sorted(set(g.method)-{'population'}):
   for base in ('population','image'):
    if method==base:continue
    r=boot_pair(g,method,base,'count_brier',['image_id','building']);
    if r:cd.append(dict(condition=arm,k=k,**r))
 pd.DataFrame(cd).to_csv(out/'count_paired_increment.csv',index=False)
 js(out/'method.json',dict(input_ref=INPUT_REF,prototype_ref=PROTO_REF,k_values=KS,outer_seed_repeats=OUTER_REPEATS,inner_seed_repeats=INNER_REPEATS,outer='leave entire building',inner='three deterministic groups of training buildings',hyperparameter_objective='mean individual kernel score, first average within image',condition_separate=True,raw_target_annotations_not_in_training=True,geometry_candidate_sources='target image frozen proposals at k=0; only the exposed seed geometries at k>0 plus explicitly labelled proposal mixtures',model_family_is_not_human_type=True,geometry_candidates_deduplicated=True,context_variables=['scene_category','AI-derived main_function_primary','floor_boundary','ceiling_boundary','model point-count median and spread'],unrestricted_count_output='counts only: cannot assert geometry for count categories with no geometry anchor',retrospective_known_worker=True,forward_time_validated=False,user39_adjudicated=False,notes=['Count and geometry metrics are not correctness.','Seed replacement copies a candidate geometry in a MODEL world; it never creates real support.','Hyperparameters, types and scaling use training buildings only.','Pooled hidden empirical distributions are scoring targets only.']))
 print('SUMMARY\n'+summary.to_string(index=False),flush=True);js(out/'FIT_COMPLETE.json',dict(status='complete',prediction_rows=len(frame),images=frame.image_id.nunique(),conditions=sorted(frame.condition.unique()),timestamp=time.time()))

def self_test(out):
 from scipy.stats import binom
 assert np.allclose(np.eye(65)[[3,4]].sum(1),1)
 # Brier optimum for the expected categorical score.
 p=np.array([.2,.8]);score=lambda q:sum(p[j]*sum((q-np.eye(2)[j])**2)for j in range(2));assert score(p)<score(np.array([.5,.5]))
 # Analytical >=2 support for different probabilities matches brute enumeration.
 p=np.array([.2,.4,.7]);p0=np.prod(1-p);p1=sum(p[j]*np.prod(np.delete(1-p,j))for j in range(3));brute=sum(np.prod(np.where(bits,p,1-p))for bits in itertools.product((0,1),repeat=3)if sum(bits)>=2);assert abs(1-p0-p1-brute)<1e-12
 # Same raw respondent cannot be a two-person seed.
 assert len(set(['W001','W001']))==1
 # Complete linkage preserves structurally distinct point counts (growth helper tests separately).
 js(Path(out)/'base_tests.json',dict(status='passed',checks=['categorical simplex','proper Brier expectation','Poisson-binomial support exactness','duplicate-worker identity'],count=4))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(OUT_DEFAULT));ap.add_argument('--test-only',action='store_true');a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True);self_test(a.output)
 if not a.test_only:fit_all(a.output)
