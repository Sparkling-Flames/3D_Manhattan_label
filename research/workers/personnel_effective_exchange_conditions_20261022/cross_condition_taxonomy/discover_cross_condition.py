#!/usr/bin/env python3
"""Cross-condition personnel taxonomies on the frozen underlying v2 inventory.

Three prespecified families, open K subject to actual capacity. No fusion score
or target-building record in either condition enters any class fit or selection.
The previous v3 study is imported read-only for its opportunity-aware features.
"""
from __future__ import annotations
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[v]='1'
import argparse, gzip, hashlib, importlib.util, json, sys, time
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from sklearn.metrics import adjusted_rand_score, adjusted_mutual_info_score

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
PREVIOUS=REPO/'research/workers/personnel_useful_taxonomy_v3_20261021/taxonomy'
sys.path.insert(0,str(PREVIOUS))
import discover_behavior_classes as previous_behavior
import discover_joint_qt as previous_joint
HIST=previous_behavior.HIST
RAW=previous_behavior.RAW
CONDITIONS=['manual','semi']
PREFIX={'manual':'m','semi':'s'}
OUTCOME_COLS=HIST+['B8L2_peer_delta','log_time_peer_delta']
PRED_COLS=HIST+['q_history','t_history']
DOMAIN_FIELDS={
 'E':[c+'_'+v for c in ['m','s'] for v in ['turn_history','short_history']],
 'R':[c+'_redundancy_history' for c in ['m','s']],
 'G':[c+'_'+v for c in ['m','s'] for v in ['area_history','height_history']],
 'Q':[c+'_'+v for c in ['m','s'] for v in ['q_history','q_downside']],
 'T':[c+'_t_history' for c in ['m','s']],
 'PE':['pair_common_turn_history','pair_delta_turn_history','pair_common_short_history','pair_delta_short_history'],
 'PR':['pair_common_redundancy_history','pair_delta_redundancy_history'],
 'PG':['pair_common_area_history','pair_delta_area_history','pair_common_height_history','pair_delta_height_history'],
}
FAMILIES={
 'XCOND_GEOM':{'domains':['E','R','G'],'support':'both_geometry_supported','objective':'geometry'},
 'XCOND_GEOM_QT':{'domains':['E','R','G','Q','T'],'support':'both_qt_supported','objective':'geometry_QT'},
 'XCOND_PAIRED':{'domains':['PE','PR','PG'],'support':'paired_supported','objective':'paired_geometry'},
}
GEOM_WEIGHTS=np.array([1/6,1/6,1/3,1/6,1/6,0.,0.])
JOINT_WEIGHTS=np.array([.1,.1,.2,.1,.1,.2,.2])
MIN_CLASS=3
STABILITY_GATE=.50

def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [clean(x) for x in v]
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,float) and not np.isfinite(v):return None
 return v
def atomic(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.partial')
 with tmp.open('wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def save(d,name):
 p=HERE/name;data=d.to_csv(index=False).encode('utf-8-sig')
 if p.suffix=='.gz':data=gzip.compress(data,compresslevel=5,mtime=0)
 atomic(p,data)
 check=pd.read_csv(p);assert check.shape==d.shape,(name,check.shape,d.shape)
def js(name,value):atomic(HERE/name,(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def equal_image_mean(values,d):
 z=d[['image_id','reference_id']].copy();z['v']=values
 return z.groupby(['image_id','reference_id'],dropna=False).v.mean().groupby('image_id').mean().mean()

class CrossStudy:
 def __init__(self):
  self.records=pd.read_csv(PREVIOUS/'BEHAVIOR_RECORDS.csv.gz')
  self.old=previous_joint.Joint(self.records)
  self.fit=self.old.fit;self.roster=self.old.roster;self.buildings=self.old.buildings
  keys=['worker_id','image_id','reference_id','building_id','origin']
  self.pairs=self.fit[self.fit.condition.eq('manual')].merge(self.fit[self.fit.condition.eq('semi')],on=keys,suffixes=('_m','_s'),validate='one_to_one')
  p=self.pairs;group=['image_id','reference_id','origin']
  for raw,hist in zip(RAW,HIST):
   for suffix in ['m','s']:
    p['paired_'+suffix+'_'+hist]=p[raw+'_'+suffix]-p.groupby(group,dropna=False)[raw+'_'+suffix].transform('median')
   p['pair_common_'+hist]=(p['paired_m_'+hist]+p['paired_s_'+hist])/2
   p['pair_delta_'+hist]=p['paired_s_'+hist]-p['paired_m_'+hist]
   p['pair_delta_raw_'+hist]=p[raw+'_s']-p[raw+'_m']
  self.pair_buildings=sorted(p.building_id.unique())
  self.pair_features=[c for c in p if c.startswith(('pair_common_','pair_delta_','paired_m_','paired_s_'))]
  self.pair_by={b:g.copy() for b,g in p.groupby('building_id')}

 @lru_cache(maxsize=None)
 def features(self,excluded):
  parts=[]
  for c in CONDITIONS:
   f=self.old.features(c,excluded).drop(columns='condition')
   f=f.rename(columns={col:PREFIX[c]+'_'+col for col in f if col!='worker_id'})
   parts.append(f)
  f=parts[0].merge(parts[1],on='worker_id',validate='one_to_one')
  f['origin']=f.m_origin.combine_first(f.s_origin)
  f['both_geometry_supported']=f.m_base_supported & f.s_base_supported
  f['both_qt_supported']=f.m_qt_supported & f.s_qt_supported
  pp=self.pairs[~self.pairs.building_id.isin(excluded)]
  means=pp.groupby(['worker_id','building_id'])[self.pair_features].mean().groupby('worker_id').mean()
  ss=pp.groupby('worker_id').agg(pair_images=('image_id','nunique'),pair_buildings=('building_id','nunique'),pair_records=('image_id','size'))
  f=f.merge(means,on='worker_id',how='left',validate='one_to_one').merge(ss,on='worker_id',how='left',validate='one_to_one')
  for c in ['pair_images','pair_buildings','pair_records']:f[c]=f[c].fillna(0).astype(int)
  f['paired_supported']=f.pair_images.ge(6)&f.pair_buildings.ge(3)&f[self.pair_features].notna().all(axis=1)
  return f

 @lru_cache(maxsize=None)
 def fitted(self,excluded,method):
  meta=FAMILIES[method];f=self.features(excluded);g=f[f[meta['support']]].copy().reset_index(drop=True)
  if len(g)<2*MIN_CLASS:return {}
  xs=[];scales={}
  for domain in meta['domains']:
   cols=DOMAIN_FIELDS[domain];a=g[cols].to_numpy(float)
   med=np.median(a,axis=0);scale=np.quantile(a,.75,axis=0)-np.quantile(a,.25,axis=0)
   scale=np.where(scale>1e-8,scale,np.std(a,axis=0));scale=np.where(scale>1e-8,scale,1.)
   xs.append(np.clip((a-med)/scale,-3,3)/np.sqrt(len(cols)*len(meta['domains'])))
   scales[domain]={'columns':cols,'median':med.tolist(),'scale':scale.tolist(),'clip':3}
  x=np.column_stack(xs);tree=linkage(x,method='ward');out={}
  k_max=len(g)//MIN_CLASS
  for k in range(2,k_max+1):
   raw=cut_tree(tree,n_clusters=k).ravel()
   sortcols=['m_turn_history','s_turn_history','s_redundancy_history','s_height_history']
   if method=='XCOND_GEOM_QT':sortcols=['m_q_history','s_q_history','m_t_history','s_t_history']
   if method=='XCOND_PAIRED':sortcols=['pair_delta_turn_history','pair_common_turn_history','pair_delta_height_history']
   order=sorted(set(raw),key=lambda j:tuple(g.loc[raw==j,sortcols].mean()))
   lab=np.array([order.index(j) for j in raw]);sizes=np.bincount(lab,minlength=k)
   centers={}
   for c in CONDITIONS:
    cols=[PREFIX[c]+'_'+v for v in PRED_COLS]
    if method=='XCOND_PAIRED':cols=['paired_'+PREFIX[c]+'_'+v for v in HIST]+cols[5:]
    centers[c]=g[cols].groupby(pd.Series(lab,name='cluster')).mean().to_numpy()
   out[k]={'workers':g.worker_id.to_numpy(),'labels':lab,'sizes':sizes,'eligible':bool(sizes.min()>=MIN_CLASS),
    'centers':centers,'features':g,'scales':scales,'k_max_capacity':k_max}
  return out

 def evaluate_all_k(self,excluded,target,method):
  fits=self.fitted(excluded,method)
  if not fits:return []
  workers=fits[min(fits)]['workers'];rows=[]
  paired=method=='XCOND_PAIRED';objective_weights=JOINT_WEIGHTS if method=='XCOND_GEOM_QT' else GEOM_WEIGHTS
  for cond in CONDITIONS:
   if paired:
    base=self.pair_by.get(target)
    if base is None:continue
    d=base[base.worker_id.isin(workers)].copy()
    targetcols=['paired_'+PREFIX[cond]+'_'+v for v in HIST]
    train=self.pairs[~self.pairs.building_id.isin(excluded)]
   else:
    base=self.old.by_image.get((cond,target))
    if base is None:continue
    d=base[base.worker_id.isin(workers)].copy();targetcols=OUTCOME_COLS
    train=self.old.fit_by[cond];train=train[~train.building_id.isin(excluded)]
   if len(d)<6:continue
   scales=train[targetcols].std().to_numpy();scales=np.where(scales>1e-8,scales,1.)
   # Image/reference-balanced target moments suffice for every K; no repeated
   # individual-record model fitting and no use of target values for labels.
   moments=[]
   for col in targetcols:
    z=d[d[col].notna()].copy()
    if not len(z):moments.append(None);continue
    n=z.groupby(['image_id','reference_id'],dropna=False).worker_id.transform('size').to_numpy(float)
    refs=z[['image_id','reference_id']].drop_duplicates().groupby('image_id').size()
    w=1/n/z.image_id.map(refs).to_numpy()/z.image_id.nunique()
    y=z[col].to_numpy();t=pd.DataFrame({'worker_id':z.worker_id.to_numpy(),'s0':w,'s1':w*y,'s2':w*y*y}).groupby('worker_id').sum().reindex(workers).fillna(0)
    moments.append(t.to_numpy())
   for k,model in fits.items():
    values=[]
    for i,moment in enumerate(moments):
     if moment is None:values.append(np.nan);continue
     pred=model['centers'][cond][model['labels'],i]
     values.append(float(np.sum(moment[:,2]-2*pred*moment[:,1]+pred*pred*moment[:,0])/scales[i]**2))
    v=np.array(values);ww=objective_weights[:len(values)];good=np.isfinite(v)&(ww>0)
    if not good.any():continue
    rows.append(dict(method=method,target_building=target,condition=cond,k=k,eligible=model['eligible'],min_class=int(model['sizes'].min()),
     workers=len(workers),records=len(d),images=d.image_id.nunique(),loss=float(np.sum(v[good]*ww[good])/sum(ww[good])),
     **{OUTCOME_COLS[i]+'_nmse':values[i] for i in range(len(values))}))
  return rows

 def select(self,outer,method):
  exc=() if outer=='ALL' else (outer,)
  outerfits=self.fitted(exc,method);inners=[b for b in (self.pair_buildings if method=='XCOND_PAIRED' else self.buildings) if b!=outer]
  rows=[];stab=[]
  for inner in inners:
   excluded=tuple(sorted(set(exc+(inner,))))
   rows.extend(self.evaluate_all_k(excluded,inner,method))
   fits=self.fitted(excluded,method)
   for k,fit in outerfits.items():
    inn=fits.get(k)
    if inn is None:continue
    a=pd.Series(fit['labels'],index=fit['workers']);bb=pd.Series(inn['labels'],index=inn['workers']);common=a.index.intersection(bb.index)
    stab.append(dict(method=method,heldout_building=outer,inner_building=inner,k=k,workers_common=len(common),
     ari=adjusted_rand_score(a.loc[common],bb.loc[common]) if len(common)>=6 else np.nan,eligible=inn['eligible']))
  d=pd.DataFrame(rows);st=pd.DataFrame(stab);cand=[]
  for k,fit in outerfits.items():
   dd=d[d.k.eq(k)];ss=st[st.k.eq(k)]
   good=dd[dd.eligible].target_building.nunique();score=dd.groupby('condition').loss.mean().mean()
   ari=ss.ari.mean();capacity=fit['eligible'] and good>=max(5,int(np.ceil(.8*len(inners))))
   eligible=capacity and np.isfinite(ari) and ari>=STABILITY_GATE
   cand.append(dict(method=method,heldout_building=outer,k=k,workers=len(fit['workers']),minimum_class=int(fit['sizes'].min()),
    outer_capacity_eligible=fit['eligible'],inner_buildings=len(inners),capacity_valid_inner_buildings=good,
    inner_ari_mean=ari,capacity_gate=capacity,stability_gate=bool(np.isfinite(ari) and ari>=STABILITY_GATE),eligible_selection=eligible,
    score=score,manual_score=dd[dd.condition.eq('manual')].loss.mean(),semi_score=dd[dd.condition.eq('semi')].loss.mean(),
    size_vector='|'.join(map(str,fit['sizes'])),k_max_mathematical=fit['k_max_capacity']))
  cs=pd.DataFrame(cand);valid=cs[cs.eligible_selection]
  status='selected'
  if not len(valid):
   # Preserve a labelled exploratory candidate if it has capacity but lacks
   # stable members. It cannot silently pass the registered stability gate.
   valid=cs[cs.capacity_gate];status='exploratory_failed_stability_gate'
  if not len(valid):
   # A sparse outer fold must not abort other deliverables. Keep an explicitly
   # exploratory cut with real outer member capacity, without changing the
   # registered 80% inner-capacity requirement or calling it selected.
   valid=cs[cs.outer_capacity_eligible];status='exploratory_failed_nested_capacity_gate'
  if not len(valid):
   return dict(method=method,heldout_building=outer,selected_family=method,coarse_k=0,fine_k=0,
    status='unassigned_no_multi_member_cut',selected_inner_score=None,selected_inner_ari=None,coarse_rule=[],
    family_domains=FAMILIES[method]['domains'],input_conditions=CONDITIONS),cs,d.assign(heldout_building=outer),st
  best=valid.sort_values(['score','k']).iloc[0];fine=int(best.k);coarse=fine;comparisons=[]
  bestrows=d[d.k.eq(fine)].set_index(['condition','target_building']).loss
  # Paired building bootstrap/SE respects the two conditions in the same
  # building. An absent Semi target contributes no artificial zero outcome.
  for k in sorted(valid[valid.k.le(fine)].k):
   s=d[d.k.eq(k)].set_index(['condition','target_building']).loss
   z=pd.concat([s.rename('candidate'),bestrows.rename('fine')],axis=1).dropna();z['delta']=z.candidate-z.fine
   vals=z.reset_index().groupby('target_building').delta.mean();delta=z.groupby(level='condition').delta.mean().mean()
   se=float(vals.std(ddof=1)/np.sqrt(len(vals))) if len(vals)>1 else 0.
   st_candidate=float(cs.loc[cs.k.eq(k),'inner_ari_mean'].iloc[0]);within=bool(delta<=se+1e-12 and st_candidate>=best.inner_ari_mean-.05)
   comparisons.append(dict(k=int(k),delta=delta,se=se,inner_ari=st_candidate,within_one_se_and_stability=within))
   if within:coarse=min(coarse,int(k))
  choice=dict(method=method,heldout_building=outer,selected_family=method,coarse_k=coarse,fine_k=fine,status=status,
   selected_inner_score=float(best.score),selected_inner_ari=float(best.inner_ari_mean),coarse_rule=comparisons,
   family_domains=FAMILIES[method]['domains'],input_conditions=CONDITIONS)
  return choice,cs,d.assign(heldout_building=outer),st

 def labels(self,choice):
  method=choice['method'];outer=choice['heldout_building'];exc=() if outer=='ALL' else (outer,)
  f=self.features(exc).copy();fits=self.fitted(exc,method)
  co=fits.get(choice['coarse_k']);fi=fits.get(choice['fine_k'])
  lc=dict(zip(co['workers'],co['labels'])) if co else {};lf=dict(zip(fi['workers'],fi['labels'])) if fi else {};fine_map={}
  for parent in sorted(set(lc.values())):
   children=sorted(set(lf[w] for w in lc if lc[w]==parent))
   for i,child in enumerate(children):fine_map[child]=f'X{parent+1}.{i+1}'
  f['method']=method;f['method_id']=method;f['heldout_building']=outer;f['selected_family']=method
  f['coarse_label']=f.worker_id.map({w:f'X{a+1}' for w,a in lc.items()}).fillna('unknown')
  f['fine_label']=f.worker_id.map({w:fine_map[a] for w,a in lf.items()}).fillna('unknown')
  f['known']=f.coarse_label.ne('unknown');f['missing_reason']=''
  f.loc[~f.known,'missing_reason']='insufficient_Manual_or_Semi_geometry_history'
  if method=='XCOND_GEOM_QT':f.loc[~f.known & f.both_geometry_supported,'missing_reason']='insufficient_Manual_or_Semi_qualified_Q_or_source_compatible_time_history'
  if method=='XCOND_PAIRED':f.loc[~f.known,'missing_reason']='fewer_than_6_same_image_reference_pairs_or_3_buildings'
  if co is None:f['missing_reason']='no_cut_with_three_members_per_class_in_training_population'
  f['coarse_k']=choice['coarse_k'];f['fine_k']=choice['fine_k'];f['selection_status']=choice['status']
  f['label_stage']='all_data_descriptive' if outer=='ALL' else 'both_conditions_target_building_excluded_inner_selected'
  f['input_conditions']='manual|semi';f['underlying_data_version']='v2';f['new_study_date']='20261022'
  f['evaluation_condition']='separate'
  return pd.concat([f.assign(condition=c) for c in CONDITIONS],ignore_index=True)

 def centers(self,labels):
  # Evaluation-condition-specific readable centers, plus the complete M/S
  # formation history. No use of a heldout target's raw response.
  rows=[]
  numeric=[c for c in self.features(()).select_dtypes(include=[np.number]).columns if c!='worker_id']
  for (method,outer,cond),g in labels.groupby(['method','heldout_building','condition']):
   for tier in ['coarse','fine']:
    for cl,z in g[g.known].groupby(tier+'_label'):
     r=dict(method=method,condition=cond,heldout_building=outer,tier=tier,class_id=cl,
      parent_class=z.coarse_label.iloc[0],members='|'.join(z.worker_id),n_members=len(z),
      old_members=int(z.origin.eq('v1').sum()),new_members=int(z.origin.eq('new').sum()),
      selected_family=method,coarse_k=int(z.coarse_k.iloc[0]),fine_k=int(z.fine_k.iloc[0]),
      selection_status=z.selection_status.iloc[0],input_conditions='manual|semi')
     r.update({c:float(z[c].mean()) for c in numeric})
     for col in PRED_COLS:r[col]=float(z[PREFIX[cond]+'_'+col].mean())
     rows.append(r)
  return pd.DataFrame(rows)

def contract():
 return dict(study='personnel_effective_exchange_conditions_20261022',underlying_data='v2',previous_study='v3 is a study version, not a newer data version',
  input=str(PREVIOUS/'BEHAVIOR_RECORDS.csv.gz'),input_sha256=sha(PREVIOUS/'BEHAVIOR_RECORDS.csv.gz'),
  methods=FAMILIES,domain_fields=DOMAIN_FIELDS,
  preprocessing='unchanged v3 expressions: non-collinear turns, short edges, redundant near-collinear nodes, log floor area and height; peer residuals remain frozen',
  cross_condition='same worker Manual and Semi histories jointly enter each family; target building excluded from BOTH conditions, including paired differences',
  paired='same worker/image/reference/origin; pairwise per-condition medians among paired workers; common=(M+S)/2 and contrast=S-M; raw differences retained. Not a randomized causal condition effect.',
  opportunity_gates={'geometry_each_condition':'at least 12 images and 4 buildings, all 5 geometry fields observed',
   'Q_each_condition':'Manual >=8 images, Semi >=4 images; >=3 buildings; original quality eligibility',
   'T_each_condition':'>=6 images and 3 buildings; log seconds centered within image/origin/time_source_kind',
   'paired':'>=6 same-image-reference pairs and >=3 buildings; no requirement for unpaired history; mostly new-source support'},
  standardization='within training roster median/IQR, SD fallback, clip ±3; equal total weight per domain and equal weight per field inside domain',
  clustering='Ward, every K=2..floor(n_supported/3), capacity min3; no fixed 3/8-class limit',
  selection='each family selected separately: nested leave-building-out raw reconstruction, capacity in >=80% inner buildings and mean inner label ARI>=.50; minimum reconstruction loss; coarsest paired one-SE cut with ARI no more than .05 below fine',
  objective='geometry E/R/G equally; combined E/R/G/Q/T equally; conditions equal after condition-specific building averaging. Paired family selects on paired opportunity records only.',
  exploratory_fallback='if no candidate passes stability but has nested capacity, explicitly mark failed_stability; if even nested capacity fails, keep an outer-capacity cut explicitly marked failed_nested_capacity; no cut with outer min3 gives all unknown. No gate is silently changed.',
  exclusions='doorway and special conditional not fit; original behavior-eligible historical removals/GT pauses may inform geometry but never restore Q/voting eligibility',
  scope_note='project_sources/01-scope-.md is ambiguity interpretation only; no frozen scope/reference/qualification changes',
  missing='feature absence stays NaN; support counts may be zero; no absent opportunity coded as observed behavior 0',
  team_endpoints_seen=False,external_blind_validation=False,prior_inventory_repeatedly_explored=True,
  outputs='ALL descriptive and LOBO evaluation labels separate; same joint labels listed separately for Manual/Semi evaluation; do not pool endpoints')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--all-only',action='store_true');ap.add_argument('--method',choices=list(FAMILIES));ap.add_argument('--resume',action='store_true');args=ap.parse_args()
 start=time.time();js('DESIGN_BEFORE_TARGET_EVALUATION.json',contract());study=CrossStudy()
 save(study.pairs,'PAIRED_INPUT_RECORDS.csv.gz')
 inventory=study.records.groupby(['condition','layer'],dropna=False).agg(records=('object_id','size'),workers=('worker_id','nunique'),images=('image_id','nunique'),buildings=('building_id','nunique')).reset_index();save(inventory,'INPUT_INVENTORY.csv')
 labels=[];choices=[];candidates=[];inner=[];stability=[]
 methods=[args.method] if args.method else list(FAMILIES)
 targets=['ALL'] if args.all_only else ['ALL']+study.buildings
 for target in targets:
  exc=() if target=='ALL' else (target,)
  save(study.features(exc).assign(heldout_building=target),f'checkpoints/FEATURES_{target}.csv.gz')
  for method in methods:
   prefix=f'checkpoints/{method}__{target}'
   if args.resume and (HERE/(prefix+'__INNER_STABILITY.csv.gz')).exists():
    choice=json.loads((HERE/(prefix+'__SELECTION.json')).read_text());ll=pd.read_csv(HERE/(prefix+'__LABELS.csv.gz'))
    cs=pd.read_csv(HERE/(prefix+'__CANDIDATES.csv'));dd=pd.read_csv(HERE/(prefix+'__INNER_LOSSES.csv.gz'));st=pd.read_csv(HERE/(prefix+'__INNER_STABILITY.csv.gz'))
   else:
    choice,cs,dd,st=study.select(target,method);ll=study.labels(choice)
    save(ll,prefix+'__LABELS.csv.gz');js(prefix+'__SELECTION.json',choice)
    save(cs,prefix+'__CANDIDATES.csv');save(dd,prefix+'__INNER_LOSSES.csv.gz');save(st,prefix+'__INNER_STABILITY.csv.gz')
   labels.append(ll);choices.append(choice);candidates.append(cs);inner.append(dd);stability.append(st)
   print(json.dumps({k:v for k,v in choice.items() if k not in ['coarse_rule','family_domains','input_conditions']},ensure_ascii=False),flush=True)
  current=pd.concat(labels,ignore_index=True)
  save(current,'CROSS_LABELS_CHECKPOINT.csv.gz');save(study.centers(current),'CROSS_CLASS_CENTERS_CHECKPOINT.csv.gz')
  js('PROGRESS.json',dict(completed_building_folds=target,selected_families=len(choices),seconds=time.time()-start,labels=len(current),stage='discovery_no_target_endpoints'))
 if not args.all_only and not args.method:
  labels=pd.concat(labels,ignore_index=True);all_l=labels[labels.heldout_building.eq('ALL')];lo=labels[~labels.heldout_building.eq('ALL')]
  save(all_l,'CROSS_LABELS_ALL.csv');save(lo,'CROSS_LABELS_LOBO.csv.gz')
  centers=study.centers(labels);save(centers[centers.heldout_building.eq('ALL')],'CROSS_CLASS_CENTERS_ALL.csv');save(centers[~centers.heldout_building.eq('ALL')],'CROSS_CLASS_CENTERS_LOBO.csv.gz')
  save(pd.concat(candidates,ignore_index=True),'CANDIDATE_SELECTION_ALL.csv');save(pd.concat(inner,ignore_index=True),'INNER_BUILDING_LOSSES.csv.gz');save(pd.concat(stability,ignore_index=True),'INNER_LABEL_STABILITY.csv.gz');js('SELECTED_MODELS.json',choices)
  fs=pd.concat([study.features(() if b=='ALL' else (b,)).assign(heldout_building=b) for b in ['ALL']+study.buildings],ignore_index=True)
  save(fs[fs.heldout_building.eq('ALL')],'FEATURES_ALL.csv');save(fs[fs.heldout_building.ne('ALL')],'FEATURES_LOBO.csv.gz')
  paths=['CROSS_LABELS_ALL.csv','CROSS_LABELS_LOBO.csv.gz','CROSS_CLASS_CENTERS_ALL.csv','CROSS_CLASS_CENTERS_LOBO.csv.gz','FEATURES_ALL.csv','FEATURES_LOBO.csv.gz','SELECTED_MODELS.json','DESIGN_BEFORE_TARGET_EVALUATION.json']
  js('LABEL_FREEZE.json',dict(status='frozen_before_target_endpoint_evaluation',code_sha256=sha(__file__),files={p:sha(HERE/p) for p in paths},rows=len(labels),seconds=time.time()-start,underlying_data_version='v2',team_endpoints_seen=False))
 print('FINISHED',time.time()-start,flush=True)
if __name__=='__main__':main()
