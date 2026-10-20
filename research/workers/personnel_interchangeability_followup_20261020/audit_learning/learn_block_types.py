"""Finite registered history-only m2 class-count-vector partition learner."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,time,hashlib
from pathlib import Path
import numpy as np,pandas as pd
import learn_corner_types as lc
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;SEED=2026102037
METRICS=['distance','distance9','distance12','bev_mean_h','top_mean_h','bev_max_h','top_max_h','valid_distance','different_count','count_not_verified_equal','missing_geometry','incomplete','high_angle']
# Base evaluator uses first3 conditional-distance masks; later risk is also exposed on all observed anchors.
lc.METRICS=METRICS

def prepare(f):
 f=f.copy();f['distance']=.5*(f.bev_mean_pairscale+f.top_mean_pairscale);f.loc[~f.status.eq('unique_cyclic_candidate'),'distance']=np.nan
 for a in [9,12]:f['distance'+str(a)]=f.distance.where(f.angle_deg<=a)
 f['incomplete']=f.noncomplete;f['k']=f.n;f['background_id']=f.anchor_id
 for side in ['left','right']:f[side+'_tuple']=f[side+'_workers'].map(lambda x:tuple(x.split('|')))
 return f

def supported(f):
 rows=[(w,r.pool_id,r.building) for r in f[['left_tuple','right_tuple','pool_id','building']].drop_duplicates().itertuples() for w in r.left_tuple+r.right_tuple]
 q=pd.DataFrame(rows,columns=['w','pool','b']).groupby('w').agg(images=('pool','nunique'),buildings=('b','nunique'))
 return sorted(q.index[(q.images>=4)&(q.buildings>=3)])

class BlockAnchors:
 def __init__(self,f,workers):
  self.workers=workers;ix={w:i for i,w in enumerate(workers)}
  f=f[f.left_tuple.map(lambda x:all(w in ix for w in x))&f.right_tuple.map(lambda x:all(w in ix for w in x))].copy()
  blocks=sorted(set(f.left_tuple)|set(f.right_tuple));lookup={b:'B'+str(i) for i,b in enumerate(blocks)}
  self.block=np.array([[ix[w] for w in b] for b in blocks],int)
  f['worker_a']=f.left_tuple.map(lookup);f['worker_b']=f.right_tuple.map(lookup)
  self.base=lc.Anchors(f,[lookup[b] for b in blocks])
 def expand(self,l):
  x=l[self.block];return x.min(axis=1)*(int(l.max())+1)+x.max(axis=1)
 def evaluate(self,l):return self.base.evaluate(self.expand(l))
 def paired(self,a,b):return self.base.paired(self.expand(a),self.expand(b))

class Objective:
 def __init__(self,f,workers):
  ix={w:i for i,w in enumerate(workers)};f=f[f.distance.notna()&f.left_tuple.map(lambda x:all(w in ix for w in x))&f.right_tuple.map(lambda x:all(w in ix for w in x))].copy()
  self.scale=max(float(f.distance.median()),1e-8);f['risk']=f.distance/(f.distance+self.scale)
  keys=['building','pool_id','n','anchor_id'];a=f[keys].drop_duplicates();p=a.groupby(['building','pool_id','n']).anchor_id.nunique();n=a.groupby(['building','pool_id']).n.nunique();i=a.groupby('building').pool_id.nunique();nb=a.building.nunique();cnt=f.groupby('anchor_id').size()
  f['weight']=[1/(nb*i[r.building]*n[r.building,r.pool_id]*p[r.building,r.pool_id,r.n]*cnt[r.anchor_id]) for r in f[keys].itertuples()]
  f['quad']=[tuple(ix[w] for w in x+y) for x,y in zip(f.left_tuple,f.right_tuple)];f['wr']=f.weight*f.risk
  g=f.groupby('quad')[['weight','wr']].sum();self.q=np.array(g.index.tolist(),int);self.w=g.weight.to_numpy();self.r=g.wr.to_numpy();self.tw=self.w.sum();self.tr=self.r.sum();self.n=len(workers)
  self.related=[np.flatnonzero((self.q==j).any(axis=1)) for j in range(self.n)]
 def same(self,l,ids=None):
  z=l[self.q if ids is None else self.q[ids]]
  return (np.minimum(z[:,0],z[:,1])==np.minimum(z[:,2],z[:,3]))&(np.maximum(z[:,0],z[:,1])==np.maximum(z[:,2],z[:,3]))
 def score(self,sw,sr,counts):
  if sw<.05*self.tw or self.tw-sw<.05*self.tw or min(counts)<4:return np.inf
  return sr/sw-.5*(self.tr-sr)/(self.tw-sw)+.03*np.square(counts/self.n).sum()
 def optimize(self,start,K):
  l=start.copy();same=self.same(l);sw=self.w[same].sum();sr=self.r[same].sum();cnt=np.bincount(l,minlength=K);loss=self.score(sw,sr,cnt);trace=[]
  for step in range(30):
   best=(loss,None)
   for j in range(self.n):
    old=l[j]
    if cnt[old]<=4:continue
    ids=self.related[j];oldw=self.w[ids][same[ids]].sum();oldr=self.r[ids][same[ids]].sum()
    for c in range(K):
     if c==old:continue
     l[j]=c;ss=self.same(l,ids);nw=sw-oldw+self.w[ids][ss].sum();nr=sr-oldr+self.r[ids][ss].sum();cc=cnt.copy();cc[old]-=1;cc[c]+=1;v=self.score(nw,nr,cc)
     if v<best[0]-1e-12:best=(v,(j,c,nw,nr,cc))
    l[j]=old
   if best[1] is None:break
   j,c,sw,sr,cnt=best[1];l[j]=c;same=self.same(l);loss=best[0];trace.append({'step':step,'worker_index':j,'class':c,'objective':loss})
  return l,loss,trace

def rank_labels(workers,values,capacities):
 order=sorted(range(len(workers)),key=lambda i:(values[workers[i]],workers[i]));l=np.zeros(len(workers),int);start=0
 for c,n in enumerate(capacities):l[order[start:start+n]]=c;start+=n
 return l

def run():
 t=time.perf_counter();out=BASE/'block_fit';out.mkdir(exist_ok=True)
 inp=ROOT/'audit_corner/history_block_metrics/COMMON_ENDPOINT_PAIRS.csv.gz';f=prepare(pd.read_csv(inp));split=json.load(open(ROOT/'unpacked/analysis/composition/SPLIT.json'));assert set(f.building)<=set(split['history_buildings']);folds=lc.make_inner_folds(split['history_buildings'])
 features=pd.read_csv(ROOT/'unpacked/interchangeability_20261020/forward/features_train.csv.gz').set_index('worker_id')
 qt=pd.read_csv(BASE/'eight_building_QT_features.csv');rn=pd.read_csv(BASE/'original_Rnew2_inner_fold_labels.csv');labels=[];foldlabels=[];ledger=[];cv=[];paired=[];manifest={}
 for fold in [-1,0,1,2,3,4]:
  train=f if fold==-1 else f[~f.building.isin(folds[fold])];test=None if fold==-1 else f[f.building.isin(folds[fold])];workers=supported(train)
  qframe=features if fold==-1 else qt[qt.fold.eq(fold)].set_index('worker_id');qvalues=qframe.q_beta.to_dict()
  known=set(workers);eligible_valid=train.distance.notna() & train.left_tuple.map(lambda x:all(w in known for w in x)) & train.right_tuple.map(lambda x:all(w in known for w in x));enough=len(workers)>=8 and eligible_valid.any()
  q_ok=all(w in qframe.index and bool(qframe.loc[w,'core_supported']) and np.isfinite(qvalues[w]) for w in workers)
  if not enough or not q_ok:
   for K in [2,3]:
    mid='B_direct_m2_composition_K'+str(K);status='insufficient_worker_or_valid_distance_support' if not enough else 'Q_start_or_control_unsupported'
    ledger.append({'method_id':mid,'fold':fold,'status':status,'workers':len(workers)})
    if fold==-1:manifest[mid]={'method_id':mid,'K':K,'status':status,'classes':{},'unknown':{w:status for w in features.index}}
   continue
  obj=Objective(train,workers);fast=None if fold==-1 else BlockAnchors(test,workers)
  for K in [2,3]:
   mid='B_direct_m2_composition_K'+str(K);starts=[rank_labels(workers,qvalues,[len(x) for x in np.array_split(workers,K)])];r=np.arange(len(workers))%K;np.random.default_rng(SEED+1000*(fold+1)+K).shuffle(r);starts.append(r);options=[]
   for si,start in enumerate(starts):
    l,loss,trace=obj.optimize(start,K);options.append((l,loss));ledger.append({'method_id':mid,'fold':fold,'start':si,'workers':len(workers),'risk_scale':obj.scale,'objective':loss,'accepted_moves':len(trace),'trace':trace})
   l,loss=min(options,key=lambda z:z[1]);l=lc.canonical(l)
   if not np.isfinite(loss):
    ledger.append({'method_id':mid,'fold':fold,'status':'no_supported_finite_partition'})
    if fold==-1:manifest[mid]={'method_id':mid,'K':K,'status':'no_supported_finite_partition','classes':{},'unknown':{w:'failed_partition' for w in features.index}}
    continue
   if fold==-1:
    classes={f'C{c+1:02d}':[w for w,z in zip(workers,l) if z==c] for c in range(K)};manifest[mid]={'method_id':mid,'K':K,'classes':classes,'objective':loss,'unknown':{w:'outside_new_or_insufficient_history_panel_support' for w in features.index if w not in workers}}
    for w in features.index:labels.append({'method_id':mid,'worker_id':w,'class_id':next((c for c,ws in classes.items() if w in ws),'unknown'),'known':w in workers})
   else:
    foldlabels.extend({'method_id':mid,'fold':fold,'worker_id':w,'class_id':int(c)} for w,c in zip(workers,l));cv.extend({'method_id':mid,'fold':fold,**v} for v in fast.evaluate(l));caps=np.bincount(l,minlength=K);controls=[('Q_same_capacity',0,rank_labels(workers,qvalues,caps))]
    rmap=rn[rn.fold.eq(fold)].set_index('worker_id').class_id.to_dict()
    if all(w in rmap for w in workers):controls.append(('original_Rnew2_mixed_refit',0,np.array([rmap[w] for w in workers],int)))
    rng=np.random.default_rng(SEED+fold*10000+K)
    controls.extend(('random_same_capacity',draw,rng.permutation(l)) for draw in range(40))
    for name,draw,bl in controls:paired.extend({'method_id':mid,'fold':fold,'baseline':name,'draw':draw,**v} for v in fast.paired(l,bl))
   lc.write(out/'METHOD_MANIFEST.json',manifest);pd.DataFrame(labels).to_csv(out/'worker_labels.csv',index=False);pd.DataFrame(foldlabels).to_csv(out/'fold_labels.csv',index=False);print(json.dumps({'fold':fold,'K':K,'objective':loss,'elapsed':time.perf_counter()-t}),flush=True)
 lc.write(out/'METHOD_MANIFEST.json',manifest);pd.DataFrame(cv).to_csv(out/'inner_cv_building.csv',index=False);pd.DataFrame(paired).to_csv(out/'paired_building.csv.gz',index=False);lc.write(out/'FIT_LEDGER.json',ledger)
 if cv:pd.DataFrame(cv).groupby('method_id').mean(numeric_only=True).to_csv(out/'inner_cv_summary.csv')
 if paired:pd.DataFrame(paired).groupby(['method_id','baseline']).mean(numeric_only=True).to_csv(out/'paired_summary.csv')
 lc.write(out/'RUN_RECEIPT.json',{'input_sha256':hashlib.sha256(inp.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'registration_sha256':hashlib.sha256((BASE/'BLOCK_LEARNING_REGISTRATION.json').read_bytes()).hexdigest(),'seconds':time.perf_counter()-t,'history_only':True,'candidate_count':2,'folds':5,'starts':2,'max_accepted_moves':30})
if __name__=='__main__':run()
