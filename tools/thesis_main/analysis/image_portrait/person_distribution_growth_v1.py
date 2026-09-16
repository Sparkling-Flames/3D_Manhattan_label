"""Growth and composition validation of the fitted finite-support simulator.

Synthetic worlds are predictive worlds, never new empirical people. Numerical
clusters and stability flags are exploratory measurements, not semantic truth.
"""
from __future__ import annotations
import argparse, collections, itertools, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from sklearn.metrics import adjusted_rand_score
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.quality_core.geometry_metrics import _interp_periodic

DRAWS=32
CUTS=(.05,.1,.2)

def dense(points):
 g=normalize_geometry(points)
 if not g['valid']:return None
 pairs=g['pairs'];xs=np.array([p['x']for p in pairs],np.float32)
 top=np.clip(np.rint(_interp_periodic(xs,np.array([p['y_ceiling']for p in pairs],np.float32),1024)),0,511).astype(np.int32)
 bottom=np.clip(np.rint(_interp_periodic(xs,np.array([p['y_floor']for p in pairs],np.float32),1024)),0,511).astype(np.int32)
 return np.minimum(top,bottom),np.maximum(top,bottom)

def distance(a,b):
 if a is None or b is None:return 1.
 it=np.maximum(0,np.minimum(a[1],b[1])-np.maximum(a[0],b[0])+1);un=(a[1]-a[0]+1)+(b[1]-b[0]+1)-it
 return 1.-float(it.sum()/un.sum())

def matrix(g):
 pts=g['points']+g['model_points'];bounds=[dense(p)for p in pts];n=len(pts);D=np.zeros((n,n))
 for a in range(n):
  for b in range(a):D[a,b]=D[b,a]=distance(bounds[a],bounds[b])
 nv=len(g['ids']);eq=np.equal.outer(g['count'],g['count']);delta=np.abs(D[:nv,:nv]-np.nan_to_num(g['dm'],nan=1,posinf=1))
 assert all(b is not None for b in bounds[:nv]),'A previously accepted human geometry failed the same normalizer'
 if eq.any():assert delta[eq].max()<1e-6,('saved-distance mismatch',g['image_id'],delta[eq].max())
 return D,np.array([b is not None for b in bounds]),float(delta[eq].max())if eq.any()else 0.

def clusters(D,pc,cut):
 out=np.zeros(len(pc),int);nxt=0
 for v in sorted(set(pc)):
  ix=np.flatnonzero(pc==v)
  lab=np.ones(len(ix),int)if len(ix)==1 else fcluster(linkage(squareform(D[np.ix_(ix,ix)],checks=False),method='complete'),cut,criterion='distance')
  out[ix]=lab+nxt;nxt=int(out.max())
 return out

def matched_tv(old,new):
 a=np.unique(old);b=np.unique(new);mat=np.array([[np.sum((old==u)&(new[:-1]==v))for v in b]for u in a]);r,s=linear_sum_assignment(-mat)
 total=0.;useda=set();usedb=set()
 for i,j in zip(r,s):
  total+=abs(np.mean(old==a[i])-np.mean(new==b[j]));useda.add(i);usedb.add(j)
 total+=sum(np.mean(old==a[i])for i in range(len(a))if i not in useda)+sum(np.mean(new==b[j])for j in range(len(b))if j not in usedb)
 return .5*total

def trajectory(indices,g,D,valid,cut):
 indices=np.array(indices,int);pc=g['all_count'][indices];K=g['K'][np.ix_(indices,indices)];dm=D[np.ix_(indices,indices)];rows=[];old=None;disp_prev=0.
 for k in range(1,len(indices)+1):
  lab=clusters(dm[:k,:k],pc[:k],cut);values,sizes=np.unique(lab,return_counts=True);pairs=np.triu_indices(k,1);within=(lab[pairs[0]]==lab[pairs[1]])
  dsp=float(dm[:k,:k][pairs][within].mean())if within.any()else 0.
  new=bool(k>1 and not np.any((pc[:k-1]==pc[k-1])&(dm[k-1,:k-1]<=cut)))
  change=float(np.mean((old[pairs2[0]]==old[pairs2[1]])!=(lab[pairs2[0]]==lab[pairs2[1]])))if old is not None and len(old)>1 and (pairs2:=np.triu_indices(k-1,1))[0].size else 0.
  promotions=sum(np.sum(old==u)==1 and np.sum(lab==lab[np.flatnonzero(old==u)[0]])>=2 for u in np.unique(old))if old is not None else 0
  rows.append(dict(k=k,mode_count=len(values),supported_modes=int(np.sum(sizes>=2)),singleton_fraction=float(np.sum(sizes==1)/k),new_geometry=float(new),support_promotions=int(promotions),repartition=change,matched_share_step=matched_tv(old,lab)if old is not None else 0.,within_mode_distance=dsp,within_mode_step=abs(dsp-disp_prev),point_disagreement=float(np.mean(pc[pairs[0]]!=pc[pairs[1]]))if len(pairs[0])else 0.,invalid_count=int(np.sum(~valid[indices[:k]]))))
  old=lab;disp_prev=dsp
 n=len(indices);tail=rows[max(1,n//2):];last=rows[max(1,n-max(3,math.ceil(n/4))):];a=pc[:n//2];b=pc[n//2:];labels=set(a)|set(b)
 htv=.5*sum(abs(np.mean(a==v)-np.mean(b==v))for v in labels)if len(a)else np.nan
 ha=K[:n//2,:n//2];hb=K[n//2:,n//2:];hab=K[:n//2,n//2:]
 hmmd=float(ha.mean()+hb.mean()-2*hab.mean())if ha.size else np.nan
 # Two transparent diagnostic flags. Neither is a frozen human stopping rule.
 common=n>=8 and rows[-1]['invalid_count']==0 and all(r['new_geometry']==0 and r['repartition']<=.05 and r['within_mode_step']<=.03 for r in last) and htv<=.25
 loose=common and rows[-1]['singleton_fraction']<=.2;strict=common and rows[-1]['singleton_fraction']==0
 summary=dict(terminal_modes=rows[-1]['mode_count'],terminal_supported=rows[-1]['supported_modes'],terminal_singleton_fraction=rows[-1]['singleton_fraction'],terminal_within=rows[-1]['within_mode_distance'],terminal_point_disagreement=rows[-1]['point_disagreement'],late_half_new=np.mean([r['new_geometry']for r in tail])if tail else np.nan,late_quarter_new=np.mean([r['new_geometry']for r in last])if last else np.nan,late_repartition=np.mean([r['repartition']for r in tail])if tail else np.nan,half_count_tv=htv,half_output_mmd=hmmd,diagnostic_stable80=float(loose),diagnostic_stable100=float(strict),diagnostic_stable_multimode80=float(loose and rows[-1]['supported_modes']>=2),invalid_generated=rows[-1]['invalid_count'])
 return rows,summary

def fit_signature(L):
 # Type letters have a reproducible descriptive order, not an ability ranking.
 lab=L.types[4].copy();groups=sorted(set(lab)-{-1},key=lambda x:(float(L.bias[lab==x].mean()),min(np.flatnonzero(lab==x))))
 return np.array([groups.index(x)if x>=0 else -1 for x in lab])

def run(out):
 s,pools,bank,raw,meta,workers=c.prepare(out);pool={g['key']:g for g in pools};snaps=c.safe(json.loads((out/'growth_prediction_snapshots.json').read_text()));rows=[];curves=[];fail=[];draws_examples=[];dm_cache={};audit=[]
 for number,sp in enumerate(snaps):
  g=pool[sp['condition']+'|'+sp['image_id']]
  if g['key']not in dm_cache:
   D,valid,err=matrix(g);dm_cache[g['key']]=(D,valid);audit.append(dict(image_id=g['image_id'],condition=g['condition'],max_same_count_distance_error=err,models_invalid_for_band_metric=int(np.sum(~valid[len(g['ids']):]))))
  D,valid=dm_cache[g['key']];si=np.array(sp['seed_index']);hi=np.array(sp['future_index']);inds=np.array(sp['indices']);w=np.array(sp['weights']);order=np.r_[si,hi]
  assert len(set(order))==len(order) and len(set(g['workers'][j]for j in order))==len(order)
  # Same hidden personnel and seed assignments for all competing methods.
  U=c.seed('worlds',g['key'],sp['k'],sp['repeat']).random((DRAWS,len(hi)))
  draws=inds[np.sum(U[:,:,None]>np.cumsum(w,axis=1)[None,:,:],axis=2).clip(max=len(inds)-1)]
  for cut in CUTS:
   tr,ts=trajectory(order,g,D,valid,cut);sums=[];array=[]
   for draw in range(DRAWS):
    sr,ss=trajectory(np.r_[si,draws[draw]],g,D,valid,cut);sums.append(ss);array.append(sr)
   stamp={key:sp[key]for key in ('image_id','building','condition','k','repeat','method','n_valid','n_observed','n_invalid','seed_workers','holdout_workers','seed_ids','holdout_ids')};stamp['cut']=cut;stamp['model_worlds']=DRAWS
   for metric,value in ts.items():
    vals=np.array([x[metric]for x in sums],float);finite=vals[np.isfinite(vals)]
    pred=float(finite.mean())if len(finite)else np.nan;lo=float(np.quantile(finite,.05))if len(finite)else np.nan;up=float(np.quantile(finite,.95))if len(finite)else np.nan
    rows.append(dict(stamp,metric=metric,real=value,prediction=pred,abs_error=abs(value-pred),lo90=lo,hi90=up,in_predictive_interval=float(lo<=value<=up),mc_se=float(finite.std(ddof=1)/np.sqrt(len(finite)))if len(finite)>1 else np.nan))
   if cut==.1:
    for step,realstep in enumerate(tr):
     for metric in ('mode_count','supported_modes','singleton_fraction','new_geometry','support_promotions','repartition','within_mode_distance','point_disagreement'):
      vv=[a[step][metric]for a in array];curves.append(dict(stamp,observed_prefix=step+1,metric=metric,real=realstep[metric],prediction=float(np.mean(vv)),lo90=float(np.quantile(vv,.05)),hi90=float(np.quantile(vv,.95))))
    if sp['repeat']==0 and sp['method']=='selected_mixture' and len(draws_examples)<24:
     for j,h in enumerate(hi):
      a=int(draws[0,j]);draws_examples.append(dict(image_id=g['image_id'],condition=g['condition'],simulated_for_worker=g['workers'][h],real_count_inference=sp['k'],synthetic=True,source='seed_geometry'if a<len(g['ids'])else 'model_proposal',source_canonical_id=g['ids'][a]if a<len(g['ids'])else None,points=(g['points']+g['model_points'])[a].tolist(),review_required=True))
  if number%30==0:print('GROWTH',number+1,'/',len(snaps),flush=True)
 pd.DataFrame(rows).to_csv(out/'growth_per_replay.csv.gz',index=False);pd.DataFrame(curves).to_csv(out/'growth_curves.csv.gz',index=False);pd.DataFrame(audit).to_csv(out/'geometry_equivalence_audit.csv',index=False);c.js(out/'synthetic_examples_NOT_HUMAN.json',draws_examples)
 df=pd.DataFrame(rows);agg=df.groupby(['condition','k','cut','method','image_id','building','metric'],as_index=False)[['real','prediction','abs_error','in_predictive_interval','mc_se']].mean();agg.to_csv(out/'growth_per_image.csv',index=False)
 summ=agg.groupby(['condition','k','cut','method','metric']).agg(images=('image_id','nunique'),real=('real','mean'),predicted=('prediction','mean'),mae=('abs_error','mean'),interval_coverage=('in_predictive_interval','mean'),mc_se=('mc_se','mean')).reset_index();summ.to_csv(out/'growth_summary.csv',index=False)
 paired=[]
 for (arm,k,cut,met),gg in agg.groupby(['condition','k','cut','metric']):
  for name in sorted(set(gg.method)-{'seed_equal'}):
   r=c.boot_pair(gg,name,'seed_equal','abs_error',['image_id','building']);
   if r:paired.append(dict(condition=arm,k=k,cut=cut,endpoint=met,**r))
 pd.DataFrame(paired).to_csv(out/'growth_paired_increment.csv',index=False)
 # Mechanistic capacity diagnostic: no weighting can predict omitted geometry anchors.
 cap=[]
 for sp in snaps:
  if sp['method'] not in ('seed_equal','selected_mixture'):continue
  g=pool[sp['condition']+'|'+sp['image_id']];D,valid=dm_cache[g['key']];hi=np.array(sp['future_index']);ai=np.array(sp['indices']);eq=g['all_count'][hi,None]==g['all_count'][ai][None,:]
  near=np.where(eq,D[np.ix_(hi,ai)],1.).min(1)
  for cut in CUTS:cap.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],k=sp['k'],repeat=sp['repeat'],method=sp['method'],cut=cut,hidden_geometry_outside_candidate_support=float(np.mean(near>cut)),hidden_counts_outside_support=float(np.mean(~eq.any(1))),n_hidden=len(hi)))
 pd.DataFrame(cap).to_csv(out/'candidate_support_ceiling.csv',index=False)
 compositions(pools,meta,workers,out,dm_cache)
 type_repro(pools,meta,workers,out)
 c.js(out/'GROWTH_COMPLETE.json',dict(status='complete',prediction_sets=len(snaps),real_images=df.image_id.nunique(),synthetic_worlds_per_set=DRAWS,stability_definitions='last-quarter geometry/pair-partition + disjoint-half count proportions + supported mass .8 or 1; exploratory, not formal stopping',credible_intervals='conditional simulation intervals only; not parameter uncertainty',raw_images_read=False))
 print('GROWTH_SUMMARY\n'+summ[(summ.cut==.1)&summ.metric.isin(['terminal_supported','late_quarter_new','diagnostic_stable80'])].to_string(index=False),flush=True)

def compositions(pools,meta,workers,out,cache):
 results=[];coverage=[];fold_profiles={};patterns={'AA':(0,0),'AB':(0,1),'AAB':(0,0,1),'ACD':(0,2,3),'AABC':(0,0,1,2),'ABCD':(0,1,2,3)}
 for g in pools:
  if len(g['ids'])<8:continue
  key=(g['condition'],g['building'])
  if key not in fold_profiles:
   tr=[h for h in pools if h['condition']==g['condition'] and h['building']!=g['building'] and len(h['ids'])>=2]
   if not tr:continue
   fold_profiles[key]=CachedLearner(tr,meta,workers,[g['building']])
  L=fold_profiles[key];labs=fit_signature(L)[g['wi']]
  if g['key'] not in cache:cache[g['key']]=matrix(g)[:2]
  D,valid=cache[g['key']]
  for name,pat in patterns.items():
   need=collections.Counter(pat);avail={a:np.flatnonzero(labs==a)for a in need};possible=all(len(avail[a])>=nn for a,nn in need.items())
   coverage.append(dict(image_id=g['image_id'],condition=g['condition'],pattern=name,possible=possible,type_counts=json.dumps(dict(collections.Counter(map(int,labs)))),unknown_people=int(np.sum(labs<0))))
   if not possible:continue
   for rep in range(8):
    r=c.seed('combination',g['key'],name,rep);hi=np.array(sorted(np.concatenate([r.choice(avail[a],nn,replace=False)for a,nn in need.items()])),int)
    rest=np.array([j for j in range(len(g['ids']))if j not in hi]);si=r.choice(rest,min(4,len(rest)),replace=False)
    assert len(set(hi))==len(hi) and set(hi).isdisjoint(si)
    ix=np.triu_indices(len(hi),1);rd=float(np.mean((g['count'][hi[ix[0]]]!=g['count'][hi[ix[1]]])|(D[np.ix_(hi,hi)][ix]>.1)))
    for method in ('seed_equal','seed_person_t025','seed_context_t025','seed_type4'):
     ai,w=c.distribution(g,si,hi,L,c.SPECS[method]);pc=g['all_count'][ai];ad=(pc[:,None]!=pc[None,:])|(D[np.ix_(ai,ai)]>.1);pred=float(np.mean([w[a]@ad@w[b]for a,b in zip(*ix)]))
     sc=c.scores(g,hi,ai,w)
     results.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],pattern=name,repeat=rep,n_people=len(hi),seed_people=len(si),target_workers='|'.join(g['workers'][j]for j in hi),target_ids='|'.join(g['ids'][j]for j in hi),seed_workers='|'.join(g['workers'][j]for j in si),seed_ids='|'.join(g['ids'][j]for j in si),method=method,true_incompatible_pair_fraction=rd,pred_incompatible_pair_fraction=pred,abs_error=abs(rd-pred),kernel_score=sc['kernel_score'],complete_convergence_claim=False))
 pd.DataFrame(results).to_csv(out/'real_composition_predictions.csv.gz',index=False);pd.DataFrame(coverage).to_csv(out/'composition_coverage.csv',index=False)
 if results:
  df=pd.DataFrame(results);df.groupby(['condition','pattern','method']).agg(images=('image_id','nunique'),rows=('repeat','size'),mae=('abs_error','mean'),kernel=('kernel_score','mean')).reset_index().to_csv(out/'composition_summary.csv',index=False)

def type_repro(pools,meta,workers,out):
 rows=[];sub=[]
 for arm in ('manual','semi','oos_geometry'):
  pp=[g for g in pools if g['condition']==arm and len(g['ids'])>=2];bs=sorted({g['building']for g in pp})
  if len(bs)<4:continue
  for rep in range(20):
   order=c.seed('disjoint_person_types',arm,rep).permutation(bs);left=set(order[:len(order)//2]);A=CachedLearner([g for g in pp if g['building']in left],meta,workers);B=CachedLearner([g for g in pp if g['building']not in left],meta,workers)
   for nc in (2,3,4):
    a=A.types[nc];b=B.types[nc];mask=(a>=0)&(b>=0)
    if mask.sum()<4:continue
    rows.append(dict(condition=arm,repeat=rep,n_types=nc,workers=int(mask.sum()),ari=adjusted_rand_score(a[mask],b[mask]),left_buildings='|'.join(sorted(left)),right_buildings='|'.join(sorted(set(bs)-left))))
    for lab in sorted(set(a[mask])):
     ix=set(np.flatnonzero((a==lab)&mask));best=max((len(ix&set(np.flatnonzero((b==q)&mask)))/len(ix|set(np.flatnonzero((b==q)&mask))),q)for q in set(b[mask]))
     sub.append(dict(condition=arm,repeat=rep,n_types=nc,left_workers='|'.join(workers[j]for j in sorted(ix)),size=len(ix),best_disjoint_jaccard=best[0]))
 pd.DataFrame(rows).to_csv(out/'types_disjoint_building_reproducibility.csv',index=False);pd.DataFrame(sub).to_csv(out/'local_type_reproducibility.csv',index=False)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();run(a.output)
