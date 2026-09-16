"""Low-cost personalised distribution simulator, exploratory follow-up.

No original images, weights, visual inference, label rewrites or production writes.
Training excludes the target building. Target response conditioning uses distinct
seed people only. Synthetic draws are NEVER additional empirical respondents.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, io, itertools, json, math, os, sys, time, urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import softmax

REPO='Sparkling-Flames/3D_Manhattan_label'
INPUT_REF='739e6e4031f7e8c18c25a36394fbad2c4fc79150'
SIM_REF='a0ce62178da2686b214a8ef7b36f8d2c7514f947'
B='analysis_results/image_portrait_20260914_v1/'
V=B+'cloud/image_links_after_review_20260915_v1/run_b02a97e2/'
INPUTS={
 'raw': B+'human/responses.jsonl.gz',
 'events': B+'human/active_events_audit.jsonl.gz',
 'time_checks': B+'human/time_source_checks.jsonl',
 'identities': B+'metadata/images.jsonl',
 'groups': V+'inputs/group_index.json',
 'geometry': V+'inputs/pairwise_geometry.npz',
 'points': V+'inputs/effective_points.json',
 'audit': V+'inputs/response_audit.csv.gz',
 'meta': V+'inputs/image_metadata_whitelist.csv',
 'models':'analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl',
}
SEEDS=(20260916,70219,93107,11833,48109,60131,79531,85207,97121,107609)
KS=(0,2,4,6,8)
FAMILIES=('HoHoNet','Bi-enclosed','Bi-extended')
EXCLUDED={'W019','W026'}

def readj(p):
 data=Path(p).read_bytes();data=gzip.decompress(data) if str(p).endswith('.gz') else data
 if str(p).endswith(('.jsonl','.jsonl.gz')): return [json.loads(x) for x in data.decode('utf-8-sig').splitlines() if x.strip()]
 return json.loads(data)

def savej(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 def conv(x):
  if isinstance(x,np.ndarray):return x.tolist()
  if isinstance(x,np.generic):return x.item()
  if isinstance(x,Path):return str(x)
  raise TypeError(type(x).__name__)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=conv,allow_nan=False),encoding='utf8')

def rng_for(*keys):
 return np.random.default_rng(int.from_bytes(hashlib.sha256('|'.join(map(str,keys)).encode()).digest()[:8],'big'))

def get_inputs(dest):
 d=Path(dest)/'inputs';d.mkdir(parents=True,exist_ok=True);paths={};manifest=[]
 for name,path in INPUTS.items():
  ref=SIM_REF if name=='models' else INPUT_REF
  p=d/(name+'__'+Path(path).name)
  if not p.exists():
   url=f'https://raw.githubusercontent.com/{REPO}/{ref}/{path}'
   err=None
   for attempt in range(3):
    try:
     with urllib.request.urlopen(url,timeout=60) as r:payload=r.read()
     p.write_bytes(payload);break
    except Exception as e:err=e;time.sleep(attempt+1)
   else:raise RuntimeError(f'Unavailable numeric source {name}: {err}')
  data=p.read_bytes();paths[name]=p
  manifest.append(dict(name=name,path=path,ref=ref,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),git_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()))
 savej(Path(dest)/'input_manifest.json',manifest)
 return paths

def rays(points):
 p=np.asarray(points,float);u=(p[:,0]/1024-.5)*2*np.pi;v=(.5-p[:,1]/512)*np.pi
 return np.c_[np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)]

# Fixed, label-independent spherical RBF feature map. Its RBF kernel is PSD.
_grid=np.arange(128);_z=1-2*(_grid+.5)/128;_a=_grid*np.pi*(3-np.sqrt(5));_r=np.sqrt(1-_z*_z)
DIRECTIONS=np.c_[_r*np.cos(_a),_z,_r*np.sin(_a)]

def embed(p):
 return np.exp(30*(rays(p)@DIRECTIONS.T-1)).mean(0)

def kernel(pa,pb):
 ea=np.stack([embed(p) for p in pa]);eb=np.stack([embed(p) for p in pb])
 eq=np.equal.outer([len(p) for p in pa],[len(p) for p in pb])
 dd=np.maximum((ea*ea).sum(1)[:,None]+(eb*eb).sum(1)[None,:]-2*ea@eb.T,0)
 return eq*np.exp(-dd/.005)

def chamfer(a,b):
 aa=np.degrees(np.arccos(np.clip(rays(a)@rays(b).T,-1,1)))
 return .5*(aa.min(0).mean()+aa.min(1).mean())

def load_data(paths,out):
 raw=readj(paths['raw']);groups=readj(paths['groups']);z=np.load(paths['geometry'],allow_pickle=False);points=readj(paths['points']);audit=pd.read_csv(paths['audit'])
 assert len(raw)==2501
 assert len({r['canonical_annotation_id'] for r in raw})==len(raw)
 lookup={r['canonical_annotation_id']:r for r in raw}
 pools=[]
 for g in groups:
  k=g['key'];ids=z[k+'_ids'].astype(str).tolist();ws=z[k+'_workers'].astype(str).tolist();pcs=z[k+'_pcs'];dm=z[k+'_dm']
  assert len(ws)==len(set(ws)) and not set(ws)&EXCLUDED
  pp=[np.asarray(points[c],float) for c in ids]
  for c,w,p,n in zip(ids,ws,pp,pcs):
   rr=lookup[c];assert rr['worker_id']==w and rr['image_id']==g['image_id'] and len(p)==n
   assert np.isfinite(p).all() and len(p)%2==0
  arm=g['condition'];assert arm in ('manual','semi','oos_geometry')
  pools.append(dict(image_id=g['image_id'],building=g['image_id'].split('_')[0],condition=arm,ids=ids,workers=ws,pcs=np.asarray(pcs,int),points=pp,dm=dm,n_observed=g['n_observed'],n_invalid=g['n_observed']-len(ids)))
 models=collections.defaultdict(dict)
 for r in readj(paths['models']):
  if r.get('source_role') not in ('offline_ep300_replay','offline_dual_prediction'):continue
  family='HoHoNet' if r.get('model_family')=='HoHoNet' else 'Bi-'+r.get('head','')
  if family not in FAMILIES:continue
  p=np.asarray(r.get('points_1024x512',[]),float)
  if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():continue
  if family in models[r['image_id']]:raise ValueError('Duplicated proposal')
  models[r['image_id']][family]=p
 counter=[]
 for w in sorted({w for g in pools for w in g['workers']}):
  rr=[r for r in raw if r['worker_id']==w];record=dict(worker_id=w,canonical_rows=len(rr),all_images=len({r['image_id'] for r in rr}))
  for arm in ('manual','semi','oos_geometry'):
   gg=[g for g in pools if g['condition']==arm and w in g['workers']];record[arm+'_valid_images']=len(gg)
  counter.append(record)
 pd.DataFrame(counter).to_csv(out/'worker_coverage.csv',index=False)
 pd.DataFrame([{k:g[k] for k in ('image_id','building','condition','n_observed','n_invalid')}|dict(n_valid=len(g['ids']),model_proposals=len(models.get(g['image_id'],{}))) for g in pools]).to_csv(out/'image_coverage.csv',index=False)
 # No extraction of any old difficulty field.
 return pools,dict(models),raw

def temporal_audit(paths,raw,out):
 def walk(o,prefix='',depth=0):
  if depth>5:return []
  rr=[]
  if isinstance(o,dict):
   for k,v in o.items():
    p=prefix+'.'+k if prefix else k
    if any(t in k.lower() for t in ('created','timestamp','started','ended','session','active','updated','submitted','duration')):
     rr.append((p,type(v).__name__,str(v)[:100] if not isinstance(v,(dict,list)) else 'nested'))
    if isinstance(v,dict):rr+=walk(v,p,depth+1)
  return rr
 fields=collections.defaultdict(lambda:dict(nonempty=0,types=set(),examples=[]));events=readj(paths['events']);checks=readj(paths['time_checks'])
 for source,rows in [('canonical',raw),('active_events',events),('time_source_checks',checks)]:
  for row in rows:
   for p,typ,example in walk(row):
    a=fields[(source,p)];a['nonempty']+=example not in ('None','','[]','{}');a['types'].add(typ)
    if len(a['examples'])<2 and example not in a['examples']:a['examples'].append(example)
 rr=[dict(source=s,field=k,**{a:b for a,b in v.items() if a!='types'},types=sorted(v['types']))for (s,k),v in fields.items()]
 savej(out/'temporal_field_audit.json',dict(canonical_rows=len(raw),event_rows=len(events),time_check_rows=len(checks),canonical_top_keys=sorted(raw[0]),event_top_keys=sorted(events[0]) if events else [],time_check_keys=sorted(checks[0]) if checks else [],fields=rr))
 print('TEMPORAL_AUDIT',json.dumps(dict(event_rows=len(events),fields=rr),ensure_ascii=False)[:18000],flush=True)
 # Presence of a cumulative active duration is not an ordered work session.
 return events,checks

def pair_profile(training,workers):
 widx={w:i for i,w in enumerate(workers)};m=len(workers);s=np.zeros((m,m));n=np.zeros((m,m));bias=collections.defaultdict(list);ys=collections.defaultdict(list)
 for g in training:
  if len(g['workers'])<2:continue
  ix=np.array([widx[w] for w in g['workers']]);pc=g['pcs']/2
  dist=np.where(np.equal.outer(pc,pc),np.minimum(g['dm'],1),1.)
  s[np.ix_(ix,ix)]+=dist;n[np.ix_(ix,ix)]+=1
  for a,w in enumerate(g['workers']):
   others=np.delete(pc,a);bias[w].append(float(np.log(pc[a])-np.median(np.log(others))))
   # Paired endpoint marginal location; preserves original saved point arrays.
   v=np.asarray(g['points'][a]);y=np.sort(v[:,1].reshape(-1,2),axis=1).mean(0)/512
   ys[w].append(y)
 off=np.triu(n>0,1);glob=float(s[off].sum()/n[off].sum()) if off.any() else .5
 d=(s+8*glob)/(n+8);np.fill_diagonal(d,0)
 return dict(workers=workers,widx=widx,d=d,n=n,global_distance=glob,bias={w:float(np.sum(v)/(len(v)+8))for w,v in bias.items()},support={w:len(v)for w,v in bias.items()})

def seed_weights(prof,seed_workers,target_workers,temp):
 if not seed_workers:return np.zeros((len(target_workers),0))
 if temp==0:return np.full((len(target_workers),len(seed_workers)),1/len(seed_workers))
 si=[prof['widx'][w] for w in seed_workers];ti=[prof['widx'][w] for w in target_workers]
 dist=prof['d'][np.ix_(ti,si)]
 ww=softmax(-dist/temp,axis=1)
 return .1/len(si)+.9*ww

def prediction_scores(g,seed_idx,prof,temp,models,alpha=0.):
 n=len(g['workers']);seed_idx=np.asarray(seed_idx,int);hold=np.array([i for i in range(n) if i not in set(seed_idx)],int)
 assert set(seed_idx).isdisjoint(hold)
 anchors=[g['points'][i]for i in seed_idx];seedw=[g['workers'][i]for i in seed_idx];targetw=[g['workers'][i]for i in hold]
 candidates=[models[g['image_id']][f]for f in FAMILIES if f in models.get(g['image_id'],{})]
 if not anchors:anchors=candidates;weights=np.full((len(hold),len(anchors)),1/max(1,len(anchors)))
 else:
  weights=seed_weights(prof,seedw,targetw,temp)
  if alpha>0 and candidates:
   anchors=anchors+candidates
   weights=np.c_[weights*(1-alpha),np.full((len(hold),len(candidates)),alpha/len(candidates))]
 if not anchors:return None
 truth=[g['points'][i]for i in hold];ac=np.array([len(p)//2 for p in anchors]);hc=g['pcs'][hold]//2;labels=sorted(set(ac)|set(hc));mat=(ac[:,None]==np.array(labels)[None,:]).astype(float);pr=weights@mat;y=(hc[:,None]==labels).astype(float)
 brier=np.sum((pr-y)**2,axis=1);kc=kernel(anchors,anchors);kh=kernel(truth,anchors)
 # Proper kernel score of each target person's predictive distribution.
 ks=1-2*np.sum(weights*kh,axis=1)+np.einsum('ij,jk,ik->i',weights,kc,weights)
 meanp=pr.mean(0);freq=y.mean(0);tv=.5*np.abs(meanp-freq).sum()
 point_support=float(np.mean(~np.isin(hc,ac)))
 return dict(count_brier=float(brier.mean()),kernel_score=float(ks.mean()),count_tv=float(tv),uncovered_point_count=point_support,n_holdout=len(hold),seed_workers='|'.join(seedw),holdout_workers='|'.join(targetw),seed_canonical_ids='|'.join(g['ids'][i]for i in seed_idx),holdout_canonical_ids='|'.join(g['ids'][i]for i in hold),weights=weights,anchors=anchors,hold=hold)

TEMPS=(0.,.1,.25,.5)
ALPHAS=(0.,.1,.25)

def evaluate(pools,models,out):
 workers=sorted({w for g in pools for w in g['workers']});rows=[];selection=[];profile_rows=[];folds=[]
 # Each condition has a separate learner; OOS not silently merged with Manual.
 for arm in ('manual','semi','oos_geometry'):
  arm_pools=[g for g in pools if g['condition']==arm and len(g['workers'])>=2]
  targets=[g for g in arm_pools if len(g['workers'])>=10]
  for building in sorted({g['building']for g in targets}):
   train=[g for g in arm_pools if g['building']!=building];test=[g for g in targets if g['building']==building];prof=pair_profile(train,workers)
   assert not any(g['building']==building for g in train)
   folds.append(dict(condition=arm,heldout_building=building,training_images=[g['image_id']for g in train],target_images=[g['image_id']for g in test]))
   for w in workers:profile_rows.append(dict(condition=arm,heldout_building=building,worker_id=w,n_training_images=prof['support'].get(w,0),relative_log_point_count=prof['bias'].get(w,0)))
   # Inner leave-building: no final target data or seed outcomes are used to tune.
   vtargets=[g for g in train if len(g['workers'])>=10]
   val=[]
   for vb in sorted({g['building']for g in vtargets}):
    ip=pair_profile([g for g in train if g['building']!=vb],workers)
    for vg in [g for g in vtargets if g['building']==vb]:
     for k in (2,4,6,8):
      if k>=len(vg['workers']):continue
      for repeat in range(3):
       si=rng_for('inner',vg['image_id'],k,repeat).permutation(len(vg['workers']))[:k]
       for temp,alpha in itertools.product(TEMPS,ALPHAS):
        sc=prediction_scores(vg,si,ip,temp,models,alpha)
        if sc:val.append(dict(k=k,temp=temp,alpha=alpha,building=vb,image_id=vg['image_id'],loss=sc['kernel_score']))
   vd=pd.DataFrame(val)
   settings={}
   for k in (2,4,6,8):
    if len(vd):
     vv=vd[vd.k==k].groupby(['temp','alpha','building','image_id']).loss.mean().groupby(['temp','alpha','building']).mean().groupby(['temp','alpha']).mean();best=min(vv.index,key=lambda key:(vv.loc[key],key));settings[k]=best
     for (temp,alpha),loss in vv.items():selection.append(dict(condition=arm,outer_building=building,k=k,temp=temp,alpha=alpha,inner_kernel_score=loss,selected=(temp,alpha)==best))
    else:settings[k]=(0.,0.)
   print('FOLD',arm,building,'train',len(train),'test',len(test),'chosen',settings,flush=True)
   for g in test:
    n=len(g['workers'])
    for k in KS:
     if k>=n:continue
     for rep,seed in enumerate(SEEDS):
      si=rng_for(seed,g['image_id']).permutation(n)[:k]
      specs=[('model_uniform',0.,1.)]if k==0 else [('seed_empirical',0.,0.),('personal_fixed_t025',.25,0.),('seed_model_mix025',0.,.25),('nested_selected',*settings[k])]
      for method,temp,alpha in specs:
       sc=prediction_scores(g,si,prof,temp,models,alpha)
       if sc:
        for key in ('weights','anchors','hold'):sc.pop(key)
        rows.append(dict(image_id=g['image_id'],building=building,condition=arm,n_valid=n,n_observed=g['n_observed'],k=k,random_seed=seed,method=method,temp=temp,model_mixture=alpha,**sc))
 pd.DataFrame(rows).to_csv(out/'heldout_seed_predictions.csv.gz',index=False)
 pd.DataFrame(selection).to_csv(out/'training_only_selection.csv',index=False)
 pd.DataFrame(profile_rows).to_csv(out/'worker_profiles_oof.csv',index=False)
 savej(out/'folds.json',folds)
 scores=pd.DataFrame(rows)
 agg=scores.groupby(['condition','k','method','image_id','building'])[['kernel_score','count_brier','count_tv','uncovered_point_count']].mean().reset_index()
 agg.to_csv(out/'per_image_scores.csv',index=False)
 summary=agg.groupby(['condition','k','method']).agg(images=('image_id','nunique'),buildings=('building','nunique'),kernel_score=('kernel_score','mean'),count_brier=('count_brier','mean'),count_tv=('count_tv','mean'),uncovered_point_count=('uncovered_point_count','mean')).reset_index()
 summary.to_csv(out/'score_summary.csv',index=False);print('SCORE_SUMMARY\n'+summary.to_string(index=False),flush=True)
 diffs=[]
 for (arm,k),gg in agg.groupby(['condition','k']):
  if k==0:continue
  base=gg[gg.method=='seed_empirical'].set_index('image_id')
  for method in sorted(set(gg.method)-{'seed_empirical'}):
   alt=gg[gg.method==method].set_index('image_id');ids=base.index.intersection(alt.index)
   for metric in ('kernel_score','count_brier','count_tv'):
    delta=alt.loc[ids,metric]-base.loc[ids,metric];bs=base.loc[ids,'building'];uniq=sorted(set(bs));r=rng_for('bootstrap',arm,k,method,metric);vv=[]
    for _ in range(2000):
     draw=r.choice(uniq,len(uniq),replace=True);values=np.concatenate([delta[bs==b].to_numpy()for b in draw]);vv.append(values.mean())
    diffs.append(dict(condition=arm,k=k,method=method,baseline='seed_empirical',metric=metric,images=len(ids),buildings=len(uniq),mean_delta=delta.mean(),ci_low=np.quantile(vv,.025),ci_high=np.quantile(vv,.975)))
 pd.DataFrame(diffs).to_csv(out/'paired_increment.csv',index=False)
 return summary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--audit-only',action='store_true');args=ap.parse_args();out=args.output
 out.mkdir(parents=True,exist_ok=True);paths=get_inputs(out);pools,models,raw=load_data(paths,out);temporal_audit(paths,raw,out)
 savej(out/'method.json',dict(input_ref=INPUT_REF,simulation_baseline_ref=SIM_REF,random_seeds=SEEDS,seed_people=KS,temperature_candidates=TEMPS,proposal_mixture_candidates=ALPHAS,protocol='leave building; inner leave building; conditions separate',target='heldout real worker predictive distribution',synthetic_as_empirical=False,unknown_worker='pooled profile, not a new type',fatigue='not inferred from cumulative task counts; audit chronology first',old_difficulty_used=False,new_visual_inference=False))
 if not args.audit_only:evaluate(pools,models,out)
 print('COMPLETE',str(out),flush=True)

if __name__=='__main__':main()
