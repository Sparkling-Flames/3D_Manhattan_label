"""Small preregistered history-only conditional-corner-risk learner.
Labels are new fits. No target building is read while fitting.
"""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,hashlib,time
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];BASE=Path(__file__).resolve().parent;P=ROOT/'unpacked';S=P/'interchangeability_20261020'
sys.path.insert(0,str(S/'reverse'))
from learn_swap_types import spectral_init,optimize_partition,partition_loss,canonical,make_inner_folds
from audit_inner_baselines import factor
SEED=2026102011
METRICS=['distance','distance9','distance12','distance_valid','different_count','count_not_verified_equal','missing_geometry','incomplete','high_angle','old_main','old_badwide']
def sanitize(x):
 if isinstance(x,dict):return {str(k):sanitize(v) for k,v in x.items()}
 if isinstance(x,(tuple,list,np.ndarray)):return [sanitize(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 if isinstance(x,(np.bool_,)):return bool(x)
 return x
def write(p,x):p.write_text(json.dumps(sanitize(x),indent=2,allow_nan=False))
def prepare(frame):
 f=frame.copy(); f=f[f.entrant_origin_a.eq('new')&f.entrant_origin_b.eq('new')].copy()
 f['distance']=.5*(f.bev_mean_pairscale+f.top_mean_pairscale)
 f.loc[~f.status.eq('unique_cyclic_candidate'),'distance']=np.nan
 f['distance9']=f.distance.where(f.angle_deg<=9);f['distance12']=f.distance.where(f.angle_deg<=12)
 f['distance_valid']=f.distance.notna().astype(float)
 f['different_count']=f.status.eq('different_corner_count').astype(float);f['count_not_verified_equal']=(~f.same_count).astype(float);f['missing_geometry']=f.status.eq('missing_connected_geometry').astype(float);f['incomplete']=(~f.complete).astype(float)
 f['high_angle']=(f.angle_deg>12).astype(float);f['old_main']=f.joint_stable_main.astype(float);f['old_badwide']=1-f.joint_stable_wide.astype(float)
 return f

def graph(frame,rep):
 names=['worker_a','worker_b'];keys=names+['building','pool_id','k']
 # Opportunity is about observed real replacements; valid-distance relation support is stricter.
 w=pd.concat([frame[['worker_a','building','pool_id']].rename(columns={'worker_a':'worker_id'}),frame[['worker_b','building','pool_id']].rename(columns={'worker_b':'worker_id'})]).groupby('worker_id').agg(images=('pool_id','nunique'),buildings=('building','nunique'))
 workers=sorted(w.index[(w.images>=4)&(w.buildings>=3)])
 valid=frame[frame.distance.notna()]
 pn=valid.groupby(keys).distance.agg(mean='mean',tail=lambda x:np.quantile(x.to_numpy(),.9)).reset_index()
 pi=pn.groupby(names+['building','pool_id'])[['mean','tail']].mean().reset_index()
 pb=pi.groupby(names+['building'])[['mean','tail']].mean().reset_index()
 pairs=pb.groupby(names)[['mean','tail']].mean().join(valid.groupby(names).agg(images=('pool_id','nunique'),buildings=('building','nunique'),events=('event_id','size'))).reset_index()
 pairs['known']=(pairs.images>=3)&(pairs.buildings>=2)&pairs.worker_a.isin(workers)&pairs.worker_b.isin(workers)
 p=pairs[pairs.known];scale=max(float(p['mean'].median()),1e-8) if len(p) else 1.
 risk=p['mean']/(p['mean']+scale)
 if rep=='mean_plus_tail':risk=.5*(risk+p['tail']/(p['tail']+scale))
 center=float(risk.mean()) if len(p) else .5
 idx={w:i for i,w in enumerate(workers)};n=len(workers);D=np.ones((n,n));W=np.zeros((n,n))
 for r,v in zip(p.itertuples(),risk):
  a,b=idx[r.worker_a],idx[r.worker_b];D[a,b]=D[b,a]=(r.buildings*v+center)/(r.buildings+1);W[a,b]=W[b,a]=min(r.buildings/3,1)
 np.fill_diagonal(D,0)
 return dict(workers=workers,D=D,W=W,pairs=pairs,scale=scale,center=center)

def fit(g,k,seed):
 n=len(g['workers']);D,W=g['D'],g['W']
 if n<4*k:return None,'fewer_than_four_per_class'
 first=spectral_init(D,W,k,seed)
 if first is None:return None,'spectral_repair_failed'
 second=np.arange(n)%k;np.random.default_rng(seed).shuffle(second)
 choices=[optimize_partition(x,D,W,k) for x in [first,second]]
 labels=min(choices,key=lambda x:partition_loss(x,D,W,k));labels=canonical(labels)
 for c in range(k):
  ids=np.flatnonzero(labels==c)
  if len(ids)<4:return None,'class_size_failed'
  if (W[np.ix_(ids,ids)]>0).sum()/(len(ids)*(len(ids)-1))<.75:return None,'class_pair_coverage_below_0.75'
 return labels,'ok'

class Anchors:
 def __init__(self,frame,workers):
  lookup={w:i for i,w in enumerate(workers)};a,b=frame.worker_a.map(lookup),frame.worker_b.map(lookup);ok=a.notna()&b.notna();f=frame[ok]
  self.a=a[ok].to_numpy(int);self.b=b[ok].to_numpy(int);self.x=f[METRICS].to_numpy(float)
  self.bg,bg=factor(f[['building','pool_id','k','background_id']]);self.pn,pn=factor(bg[['building','pool_id','k']]);self.pi,pi=factor(pn[['building','pool_id']]);self.pb,pb=factor(pi[['building']]);self.nbg=len(bg);self.npn=len(pn);self.npi=len(pi);self.npb=len(pb);self.buildings=pb.building.tolist();self.bg_buildings=bg.building.to_numpy()
 def common(self,labels,metric=0):
  same=labels[self.a]==labels[self.b];code=2*self.bg+same;valid=np.ones(len(code),bool) if metric is None else np.isfinite(self.x[:,metric]);counts=np.bincount(code[valid],minlength=2*self.nbg).reshape(self.nbg,2);return (counts>0).all(axis=1)
 @staticmethod
 def reduce(x,code,n):
  shape=x.shape[1:];a=x.reshape(len(x),-1);out=np.full((n,a.shape[1]),np.nan)
  for j in range(a.shape[1]):
   valid=np.isfinite(a[:,j]);den=np.bincount(code[valid],minlength=n);num=np.bincount(code[valid],weights=a[valid,j],minlength=n);np.divide(num,den,out=out[:,j],where=den>0)
  return out.reshape((n,)+shape)
 def evaluate(self,labels,masks=None):
  same=labels[self.a]==labels[self.b];code=2*self.bg+same
  common={j:self.common(labels,j if j<3 else 0) for j in range(len(METRICS))};observed=self.common(labels,None)
  if masks is not None:
   for j in common:common[j] &= masks[j]
   observed &= masks['observed']
  raw=self.reduce(self.x,code,2*self.nbg).reshape(self.nbg,2,len(METRICS));value=raw.copy()
  for j in common:value[~common[j],:,j]=np.nan
  pb=self.reduce(self.reduce(self.reduce(value,self.pn,self.npn),self.pi,self.npi),self.pb,self.npb)
  allvalue=raw.copy();allvalue[~observed]=np.nan
  allpb=self.reduce(self.reduce(self.reduce(allvalue,self.pn,self.npn),self.pi,self.npi),self.pb,self.npb)
  rows=[]
  for i,b in enumerate(self.buildings):
   if not (observed&(self.bg_buildings==b)).any():continue
   r={'building':b,'matched_anchors':int((common[0]&(self.bg_buildings==b)).sum()),'all_observed_common_anchors':int((observed&(self.bg_buildings==b)).sum()),'distance9_common_anchors':int((common[1]&(self.bg_buildings==b)).sum()),'distance12_common_anchors':int((common[2]&(self.bg_buildings==b)).sum())}
   for j,m in enumerate(MR for MR in METRICS):
    r['within_'+m]=pb[i,1,j];r['between_'+m]=pb[i,0,j]
    if j>=3:r['within_allanchors_'+m]=allpb[i,1,j];r['between_allanchors_'+m]=allpb[i,0,j]
   r['distance_gap']=r['between_distance']-r['within_distance'];r['distance9_gap']=r['between_distance9']-r['within_distance9'];r['distance12_gap']=r['between_distance12']-r['within_distance12'];rows.append(r)
  return rows
 def paired(self,a,b):
  masks={j:self.common(a,j if j<3 else 0)&self.common(b,j if j<3 else 0) for j in range(len(METRICS))};masks['observed']=self.common(a,None)&self.common(b,None)
  ar={r['building']:r for r in self.evaluate(a,masks)};br={r['building']:r for r in self.evaluate(b,masks)};rows=[]
  assert set(ar)==set(br)
  for building in ar:
   row={'building':building,'matched_anchors':ar[building]['matched_anchors'],'all_observed_common_anchors':ar[building]['all_observed_common_anchors'],'distance9_common_anchors':ar[building]['distance9_common_anchors'],'distance12_common_anchors':ar[building]['distance12_common_anchors']}
   for m,v in ar[building].items():
    if m in ['building','matched_anchors','all_observed_common_anchors','distance9_common_anchors','distance12_common_anchors']:continue
    row['candidate_'+m]=v;row['baseline_'+m]=br[building][m];row['delta_'+m]=v-br[building][m]
   rows.append(row)
  return rows

def run(tier="legacy"):
 t=time.perf_counter();out=BASE/('corner_fit_'+tier);out.mkdir(exist_ok=True)
 split=json.load(open(P/'analysis/composition/SPLIT.json'));hist=set(split['history_buildings'])
 files=sorted((BASE/'corner_history').glob('*.csv.gz'))
 if tier=='mixed':
  assert (BASE/'H20_EXTRACTION_RECEIPT.json').exists()
  files+=sorted((BASE/'corner_h20').glob('*.csv.gz'))
 frame=prepare(pd.concat([pd.read_csv(p) for p in files],ignore_index=True));assert set(frame.building)==hist;assert frame.event_id.is_unique
 folds=make_inner_folds(sorted(hist));write(out/'INPUT_RECEIPT.json',{'input_tier':'legacy_only_reduced_support' if tier=='legacy' else 'mixed_legacy_plus_H20_history','events':len(frame),'buildings':sorted(frame.building.unique()),'images':frame.pool_id.nunique(),'valid_distance':frame.distance.notna().sum(),'registration_sha256':hashlib.sha256((BASE/'CORNER_LEARNING_REGISTRATION.json').read_bytes()).hexdigest(),'extraction_files':len(files),'metric_sha256':hashlib.sha256((ROOT/'audit_corner/corner_distance.py').read_bytes()).hexdigest()})
 features=pd.read_csv(S/'forward/features_train.csv.gz').set_index('worker_id');roster=features.index.tolist();ledgers=[];cv=[];paired=[];labelrows=[];man={};classrows=[];foldlabels=[];qt=pd.read_csv(BASE/'eight_building_QT_features.csv')
 for rep in ['mean','mean_plus_tail']:
  full=graph(frame,rep)
  cache=[]
  for fi,held in enumerate(folds):
   train=frame[~frame.building.isin(held)];test=frame[frame.building.isin(held)];g=graph(train,rep);cache.append((fi,g,Anchors(test,g['workers'])))
  for k in [2,3,4]:
   mid=f'C_corner_{rep}_K{k}__new__{tier}';labels,status=fit(full,k,SEED+k)
   spec={'method_id':mid,'representation':rep,'K':k,'status':status,'risk_scale':full['scale'],'classes':{},'unknown':{}}
   if labels is not None:
    spec['classes']={f'C{c+1:02d}':[w for w,l in zip(full['workers'],labels) if l==c] for c in range(k)}
    lookup={w:c for c,ws in spec['classes'].items() for w in ws}
    for c,ws in spec['classes'].items():
     pr=full['pairs'];pr=pr[pr.worker_a.isin(ws)&pr.worker_b.isin(ws)];kp=pr[pr.known];ff=features.loc[ws]
     row={'method_id':mid,'class_id':c,'members':'|'.join(ws),'workers':len(ws),'possible_pairs':len(ws)*(len(ws)-1)//2,'known_pairs':len(kp),'pair_mean_distance':kp['mean'].mean(),'pair_mean_p90':kp['mean'].quantile(.9),'pair_tail_mean':kp['tail'].mean()}
     for col in ['q_beta','q_abs_mean','t_source_origin_effect','pair_count_effect','bottom_y_effect','height_log_effect','hard_minus_easy']:row[col+'_mean']=ff[col].mean()
     classrows.append(row)
   else:lookup={}
   for w in roster:
    reason='supported_history_corner_risk' if w in lookup else 'outside_new_source_domain' if features.loc[w,'person_origin']!='new' else 'insufficient_history_support_or_failed_partition'
    labelrows.append({'method_id':mid,'worker_id':w,'class_id':lookup.get(w,'unknown'),'known':w in lookup,'reason':reason})
    if w not in lookup:spec['unknown'][w]=reason
   man[mid]=spec
   for fi,g,fast in cache:
    lab,st=fit(g,k,SEED+fi*1000+k);ledgers.append({'method_id':mid,'fold':fi,'status':st,'workers':len(g['workers']),'risk_scale':g['scale']})
    if lab is None:continue
    for w,l in zip(g['workers'],lab):foldlabels.append({'method_id':mid,'fold':fi,'worker_id':w,'class_id':int(l)})
    for r in fast.evaluate(lab):cv.append({'method_id':mid,'fold':fi,**r})
    ff=qt[qt.fold.eq(fi)].set_index('worker_id')
    for bname,col,support in [('Q_only_same_K','q_beta','core_supported'),('T_only_same_K','t_source_origin_effect','t_supported')]:
     ids=[i for i,w in enumerate(g['workers']) if bool(ff.loc[w,support]) and np.isfinite(ff.loc[w,col])]
     if len(ids)<4*k:
      ledgers.append({'method_id':mid,'fold':fi,'status':bname+'_insufficient_support','workers':len(ids)});continue
     ws=[g['workers'][i] for i in ids];order=sorted(range(len(ws)),key=lambda i:(ff.loc[ws[i],col],ws[i]));bl=np.zeros(len(ws),int)
     for c,part in enumerate(np.array_split(order,k)):bl[part]=c
     fa=Anchors(frame[frame.building.isin(folds[fi])],ws)
     for r in fa.paired(lab[ids],bl):paired.append({'method_id':mid,'fold':fi,'baseline':bname,'draw':0,**r})
    rng=np.random.default_rng(SEED+fi*100000+k)
    for draw in range(40):
     rnd=rng.permutation(lab)
     for r in fast.paired(lab,rnd):paired.append({'method_id':mid,'fold':fi,'baseline':'same_capacity_random','draw':draw,**r})
   pd.DataFrame(foldlabels).to_csv(out/'fold_labels.csv',index=False)
   write(out/'METHOD_MANIFEST.json',man);pd.DataFrame(labelrows).to_csv(out/'worker_labels.csv',index=False)
   print(json.dumps({'finished_method':mid,'elapsed_seconds':time.perf_counter()-t}),flush=True)
 write(out/'METHOD_MANIFEST.json',man);pd.DataFrame(labelrows).to_csv(out/'worker_labels.csv',index=False);pd.DataFrame(classrows).to_csv(out/'class_profiles.csv',index=False);pd.DataFrame(ledgers).to_csv(out/'fold_ledger.csv',index=False)
 cvs=pd.DataFrame(cv);cvs.to_csv(out/'inner_cv_building.csv',index=False);cvs.groupby('method_id').mean(numeric_only=True).to_csv(out/'inner_cv_summary.csv')
 prs=pd.DataFrame(paired);prs.to_csv(out/'paired_random_building.csv.gz',index=False);num=[c for c in prs if c.startswith(('candidate_','baseline_','delta_'))];draws=prs.groupby(['method_id','baseline','draw'])[num].mean().reset_index();draws.to_csv(out/'paired_random_draws.csv',index=False)
 summary=[]
 for (mid,baseline),g in draws.groupby(['method_id','baseline']):
  r={'method_id':mid,'baseline':baseline,'draws':len(g)}
  for m in num:r[m+'_mean']=g[m].mean();r[m+'_p05']=g[m].quantile(.05);r[m+'_p95']=g[m].quantile(.95)
  summary.append(r)
 pd.DataFrame(summary).to_csv(out/'paired_random_summary.csv',index=False);write(out/'RUN_RECEIPT.json',{'seconds':time.perf_counter()-t,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'candidate_count':6,'fitting_targets':'history_only','assessment_not_loaded':True})
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--tier',choices=['legacy','mixed'],default='legacy');args=ap.parse_args();run(args.tier)
