"""Fixed external seeds and nested genuine-worker composition comparisons.

The same four observed people inform every composition in one image/repetition.
AA is nested inside AAB and AABC. ABCD replaces one A by a distinct D. Unknown
people are not a fifth type. Longer type-restricted rosters use actual available
people and are allowed to be too small for a stability diagnostic.
"""
from __future__ import annotations
import argparse,collections
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_growth_v1 import matrix,fit_signature,trajectory
from tools.thesis_main.analysis.image_portrait.person_distribution_diagnostics_v1 import paired_fast

PATTERNS={'AA':(0,0),'AB':(0,1),'AAB':(0,0,1),'ACD':(0,2,3),'AABC':(0,0,1,2),'ABCD':(0,1,2,3)}

def take_pattern(lists,pattern):
 used=collections.Counter();result=[]
 for t in pattern:
  if used[t]>=len(lists[t]):return None
  result.append(int(lists[t][used[t]]));used[t]+=1
 return np.array(result,int)

def run(out):
 dest=out/'composition_control';dest.mkdir(exist_ok=True);s,pools,bank,raw,meta,workers=c.prepare(out);learn={};pairs=[];coverage=[];growth=[];curves=[]
 for g in pools:
  if len(g['ids'])<8:continue
  key=(g['condition'],g['building'])
  if key not in learn:
   tr=[h for h in pools if h['condition']==g['condition']and h['building']!=g['building']and len(h['ids'])>=2]
   if not tr:continue
   learn[key]=CachedLearner(tr,meta,workers,[g['building']])
  L=learn[key];labels=fit_signature(L)[g['wi']];D,valid,err=matrix(g);n=len(g['ids'])
  for rep in range(4):
   order=c.seed('fixed_external_seed_compositions',g['key'],rep).permutation(n);si=order[:4];rem=order[4:];lists={q:rem[labels[rem]==q]for q in range(4)}
   for name,pattern in PATTERNS.items():
    hi=take_pattern(lists,pattern);coverage.append(dict(image_id=g['image_id'],condition=g['condition'],repeat=rep,pattern=name,possible=hi is not None,external_seed_workers='|'.join(g['workers'][j]for j in si),available_counts=str({q:len(v)for q,v in lists.items()}),unknown_not_a_type=int(np.sum(labels[rem]<0))))
    if hi is None:continue
    assert len(set(hi))==len(hi) and set(si).isdisjoint(hi)
    ip=np.triu_indices(len(hi),1);d=D[np.ix_(hi,hi)];real=float(np.mean((g['count'][hi[ip[0]]]!=g['count'][hi[ip[1]]])|(d[ip]>.1)))
    for method in ('seed_equal','seed_person_t025','seed_context_t025','seed_type4'):
     ai,w=c.distribution(g,si,hi,L,c.SPECS[method]);pc=g['all_count'][ai];mat=(pc[:,None]!=pc[None,:])|(D[np.ix_(ai,ai)]>.1);pred=float(np.mean([w[a]@mat@w[b]for a,b in zip(*ip)]));sc=c.scores(g,hi,ai,w)
     pairs.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],repeat=rep,pattern=name,method=method,n_people=len(hi),seed_workers='|'.join(g['workers'][j]for j in si),target_workers='|'.join(g['workers'][j]for j in hi),target_ids='|'.join(g['ids'][j]for j in hi),actual=real,predicted=pred,abs_error=abs(real-pred),kernel_score=sc['kernel_score']))
   if rep>=2:continue
   chains={'all_remaining_real_people':rem}
   for q in range(4):chains[f'type_{q}_only']=lists[q]
   for name,pat in [('AABC_cycles',(0,0,1,2)),('ABCD_cycles',(0,1,2,3)),('AB_cycles',(0,1))]:
    need=collections.Counter(pat);cycles=min(len(lists[q])//cnt for q,cnt in need.items());hi=take_pattern(lists,pat*cycles)if cycles else np.array([],int);chains[name]=hi
   for name,hi in chains.items():
    if hi is None or len(hi)<2:continue
    tr,ts=trajectory(hi,g,D,valid,.1)
    for method in ('seed_equal','seed_person_t025','seed_context_t025','seed_type4'):
     ai,w=c.distribution(g,si,hi,L,c.SPECS[method]);r=c.seed('composition_worlds',g['key'],rep,name);uu=r.random((16,len(hi)));draw=ai[np.sum(uu[:,:,None]>np.cumsum(w,axis=1)[None,:,:],axis=2).clip(max=len(ai)-1)];sim=[trajectory(dd,g,D,valid,.1)for dd in draw]
     for metric,value in ts.items():
      vv=np.array([ss[1][metric]for ss in sim]);eligible=not metric.startswith('diagnostic_')or len(hi)>=8
      growth.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],repeat=rep,chain=name,method=method,metric=metric,n_distinct_people=len(hi),status='evaluated'if eligible else 'not_enough_for_this_diagnostic_only',real=value if eligible else np.nan,predicted=float(vv.mean())if eligible else np.nan,abs_error=abs(value-float(vv.mean()))if eligible else np.nan,seed_workers='|'.join(g['workers'][j]for j in si),target_workers='|'.join(g['workers'][j]for j in hi),target_ids='|'.join(g['ids'][j]for j in hi)))
     for step,rr in enumerate(tr):
      for metric in ('mode_count','supported_modes','singleton_fraction','new_geometry','within_mode_distance'):
       curves.append(dict(image_id=g['image_id'],condition=g['condition'],repeat=rep,chain=name,method=method,n_distinct_people=len(hi),prefix=step+1,metric=metric,real=rr[metric],predicted=float(np.mean([ss[0][step][metric]for ss in sim]))))
  print('CONTROLLED_COMPOSITIONS',g['condition'],g['image_id'],flush=True)
 df=pd.DataFrame(pairs);df.to_csv(dest/'fixed_seed_real_compositions.csv.gz',index=False);pd.DataFrame(coverage).to_csv(dest/'coverage.csv',index=False);pd.DataFrame(growth).to_csv(dest/'type_restricted_growth.csv.gz',index=False);pd.DataFrame(curves).to_csv(dest/'type_restricted_curves.csv.gz',index=False)
 df.groupby(['condition','pattern','method']).agg(images=('image_id','nunique'),mae=('abs_error','mean'),real=('actual','mean'),predicted=('predicted','mean'),kernel=('kernel_score','mean')).reset_index().to_csv(dest/'summary.csv',index=False)
 effects=[]
 for a,b in [('ABCD','AABC'),('AB','AA'),('AAB','AA'),('AABC','AAB')]:
  aa=df[df.pattern==a];bb=df[df.pattern==b];zz=aa.merge(bb,on=['image_id','building','condition','repeat','method','seed_workers'],suffixes=('_a','_b'))
  for _,r in zz.iterrows():effects.append(dict(image_id=r.image_id,building=r.building,condition=r.condition,repeat=r['repeat'],method=r.method,contrast=a+' minus '+b,size_a=r.n_people_a,size_b=r.n_people_b,effect_kind='composition_at_fixed_n'if r.n_people_a==r.n_people_b else 'nested_addition_of_distinct_people',actual_delta=r.actual_a-r.actual_b,predicted_delta=r.predicted_a-r.predicted_b,abs_delta_error=abs((r.predicted_a-r.predicted_b)-(r.actual_a-r.actual_b)),seed_workers=r.seed_workers,workers_a=r.target_workers_a,workers_b=r.target_workers_b))
 ed=pd.DataFrame(effects);ed.to_csv(dest/'matched_composition_effects.csv.gz',index=False)
 if len(ed):ed.groupby(['condition','contrast','method']).agg(images=('image_id','nunique'),actual=('actual_delta','mean'),predicted=('predicted_delta','mean'),mae=('abs_delta_error','mean')).reset_index().to_csv(dest/'matched_effect_summary.csv',index=False)
 gg=pd.DataFrame(growth);gg.groupby(['condition','chain','method','metric','status']).agg(images=('image_id','nunique'),median_real_n=('n_distinct_people','median'),real=('real','mean'),predicted=('predicted','mean'),mae=('abs_error','mean')).reset_index().to_csv(dest/'growth_summary.csv',index=False)
 c.js(dest/'COMPLETE.json',dict(status='complete',images=df.image_id.nunique(),external_seed_people=4,real_composition_repeats=4,growth_repeats=2,worlds_per_growth=16,types='training building-excluded four-cluster sensitivity; not frozen taxonomy',unknown_type_is_not_real_class=True,review39_unchanged=True))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();run(a.output)
