"""Additional geometric-mode share check; original diagnostic files unchanged.

The old flag balanced point-count proportions. This version additionally checks
numerical geometry-cluster proportions. Near a hard threshold, retain the exact
reference implementation if floating summation changes the accelerator's flag.
"""
from pathlib import Path
import argparse,collections,json,math
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_growth_v1 import matrix,clusters,trajectory

def endstats(indices,g,D,valid,cut=.1):
 ix=np.array(indices,int);n=len(ix);pcs=g['all_count'][ix];dm=D[np.ix_(ix,ix)];start=max(1,n-max(3,math.ceil(n/4)));old=None;prev=None;tail=True;last_lab=None
 for k in range(start,n+1):
  lab=clusters(dm[:k,:k],pcs[:k],cut);pair=np.triu_indices(k,1);same=lab[pair[0]]==lab[pair[1]];dis=float(dm[:k,:k][pair][same].mean())if same.any()else 0.
  if old is not None:
   pair0=np.triu_indices(k-1,1);repart=float(np.mean((old[pair0[0]]==old[pair0[1]])!=(lab[pair0[0]]==lab[pair0[1]])))if len(pair0[0])else 0.
   novel=not np.any((pcs[:k-1]==pcs[k-1])&(dm[k-1,:k-1]<=cut));tail=tail and not novel and repart<=.05 and abs(dis-prev)<=.03
  old=lab;prev=dis;last_lab=lab
 h=n//2;a=pcs[:h];b=pcs[h:];labels=set(a)|set(b)
 tv_count=.5*sum(abs(np.mean(a==v)-np.mean(b==v))for v in labels)
 tv_geo=.5*sum(abs(np.mean(last_lab[:h]==v)-np.mean(last_lab[h:]==v))for v in set(last_lab))
 counts=np.array(list(collections.Counter(last_lab).values()));single=np.sum(counts==1)/n;common=n>=8 and valid[ix].all()and tail and tv_count<=.25
 stable80=common and single<=.2;stable100=common and single==0
 return dict(original_stable80=float(stable80),original_stable100=float(stable100),geometry_half_tv=tv_geo,count_half_tv=tv_count,geometry_balanced_stable80=float(stable80 and tv_geo<=.25),geometry_balanced_stable100=float(stable100 and tv_geo<=.25),geometry_balanced_multimode80=float(stable80 and tv_geo<=.25 and np.sum(counts>=2)>=2))

def run(out):
 dest=out/'mode_share_sensitivity';dest.mkdir(exist_ok=True);s,pools,bank,raw,meta,workers=c.prepare(out);pool={g['key']:g for g in pools};snaps=json.loads((out/'growth_prediction_snapshots.json').read_text());orig=pd.read_csv(out/'growth_per_replay.csv.gz');orig=orig[(orig.cut==.1)&orig.metric.isin(['diagnostic_stable80','diagnostic_stable100'])].set_index(['image_id','condition','k','repeat','method','metric']);rows=[];cache={};checks=0;fallback=[]
 for num,sp in enumerate(snaps):
  g=pool[sp['condition']+'|'+sp['image_id']]
  if g['key']not in cache:cache[g['key']]=matrix(g)[:2]
  D,valid=cache[g['key']];si=np.array(sp['seed_index']);hi=np.array(sp['future_index']);ai=np.array(sp['indices']);w=np.array(sp['weights']);real=endstats(np.r_[si,hi],g,D,valid);U=c.seed('worlds',g['key'],sp['k'],sp['repeat']).random((32,len(hi)));draw=ai[np.sum(U[:,:,None]>np.cumsum(w,axis=1)[None,:,:],axis=2).clip(max=len(ai)-1)];worlds=[endstats(np.r_[si,dd],g,D,valid)for dd in draw]
  for suffix in ('80','100'):
   rr=orig.loc[(g['image_id'],g['condition'],sp['k'],sp['repeat'],sp['method'],'diagnostic_stable'+suffix)];assert abs(rr.real-real['original_stable'+suffix])<1e-12
   got=np.mean([v['original_stable'+suffix]for v in worlds])
   if abs(rr.prediction-got)>1e-10:
    fallback.append(dict(image_id=g['image_id'],condition=g['condition'],k=sp['k'],repeat=sp['repeat'],method=sp['method'],suffix=suffix,saved=rr.prediction,accelerator=got))
    for idx,dd in enumerate(draw):
     _,ref=trajectory(np.r_[si,dd],g,D,valid,.1);v=worlds[idx]
     for su in ('80','100'):
      flag=ref['diagnostic_stable'+su];v['original_stable'+su]=flag;v['geometry_balanced_stable'+su]=float(flag and v['geometry_half_tv']<=.25)
     v['geometry_balanced_multimode80']=float(ref['diagnostic_stable_multimode80']and v['geometry_half_tv']<=.25)
    got=np.mean([v['original_stable'+suffix]for v in worlds])
   assert abs(rr.prediction-got)<1e-10,('reference reproduction mismatch',num,g['image_id'],suffix,rr.prediction,got)
   checks+=2
  for metric,val in real.items():
   pred=np.mean([v[metric]for v in worlds]);rows.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],k=sp['k'],repeat=sp['repeat'],method=sp['method'],metric=metric,real=val,predicted=pred,abs_error=abs(pred-val),squared_error=(pred-val)**2,n_real=len(g['ids'])))
  if num%200==0:print('MODE_SHARE_CHECK',num+1,'/',len(snaps),'reference_fallbacks',len(fallback),flush=True)
 df=pd.DataFrame(rows);df.to_csv(dest/'per_replay.csv.gz',index=False);ag=df.groupby(['condition','k','method','metric','image_id','building'],as_index=False)[['real','predicted','abs_error','squared_error']].mean();ag.to_csv(dest/'per_image.csv',index=False);ag.groupby(['condition','k','method','metric']).agg(images=('image_id','nunique'),real=('real','mean'),predicted=('predicted','mean'),mae=('abs_error','mean'),brier_or_mse=('squared_error','mean')).reset_index().to_csv(dest/'summary.csv',index=False)
 pd.DataFrame(fallback,columns=['image_id','condition','k','repeat','method','suffix','saved','accelerator']).to_csv(dest/'accelerator_reference_audit.csv',index=False)
 c.js(dest/'COMPLETE.json',dict(status='complete',original_flag_exact_equivalence_checks=checks,reference_fallback_sets=len(fallback),additional_requirement='full numerical geometry-cluster proportions, disjoint halves TV <= .25',full_partition_used_for_scoring_only=True,formal_criterion_frozen=False))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();run(a.output)
