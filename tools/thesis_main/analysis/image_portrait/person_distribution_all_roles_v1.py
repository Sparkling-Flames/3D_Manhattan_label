"""All feasible type-role assignments, avoiding a privileged singleton 'A'.

A/B/C/D are roles in a composition, not globally ordered psychological types.
Every feasible repeated role is retained and actual type IDs/person IDs are saved.
Same external seeds and nested comparison people are used within each contrast.
"""
from pathlib import Path
import argparse,itertools,collections
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_profile_v1 import ProfileLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_growth_v1 import matrix
from tools.thesis_main.analysis.image_portrait.person_distribution_diagnostics_v1 import paired_fast


def run(out):
 dest=out/'all_role_compositions';dest.mkdir(exist_ok=True);s,pools,bank,raw,meta,workers=c.prepare(out);learn={};rows=[];effects=[];coverage=[]
 for g in pools:
  if len(g['ids'])<8:continue
  D,valid,_=matrix(g)
  for family,cls,temp in [('coannotation',CachedLearner,.25),('profile',ProfileLearner,.5)]:
   key=(family,g['condition'],g['building'])
   if key not in learn:
    tr=[h for h in pools if h['condition']==g['condition']and h['building']!=g['building']and len(h['ids'])>=2]
    if not tr:continue
    learn[key]=cls(tr,meta,workers,[g['building']])
   L=learn[key];labs=L.types[4][g['wi']]
   for rep in range(4):
    order=c.seed('fixed_external_seed_compositions',g['key'],rep).permutation(len(g['ids']));si=order[:4];rem=order[4:];lis={t:rem[labs[rem]==t]for t in range(4)};store={}
    def evaluate(pattern,types,indices):
     hi=np.array(indices,int);assert len(set(hi))==len(hi)and set(hi).isdisjoint(si)
     roles='|'.join(map(str,types));ip=np.triu_indices(len(hi),1);dd=D[np.ix_(hi,hi)];real=float(np.mean((g['count'][hi[ip[0]]]!=g['count'][hi[ip[1]]])|(dd[ip]>.1)));stamp=dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],family=family,repeat=rep,pattern=pattern,type_roles=roles,n_people=len(hi),seed_workers='|'.join(g['workers'][j]for j in si),worker_ids='|'.join(g['workers'][j]for j in hi),canonical_ids='|'.join(g['ids'][j]for j in hi),subset_id='|'.join(sorted(g['workers'][j]for j in hi)),actual=real)
     outp={}
     for method,sp in [('equal',dict(temp=0.)),('continuous',dict(temp=temp)),('context',dict(temp=temp,context=True)),('type4',dict(types=4))]:
      ai,w=c.distribution(g,si,hi,L,sp);pc=g['all_count'][ai];mat=(pc[:,None]!=pc[None,:])|(D[np.ix_(ai,ai)]>.1);pred=float(np.mean([w[a]@mat@w[b]for a,b in zip(*ip)]));rr=dict(stamp,method=method,predicted=pred,abs_error=abs(pred-real));rows.append(rr);outp[method]=rr
     store[(pattern,tuple(types))]=outp
    for a in range(4):
     if len(lis[a])>=2:evaluate('AA',(a,),lis[a][:2])
    for a,b in itertools.permutations(range(4),2):
     if len(lis[a]) and len(lis[b]):evaluate('AB',(a,b),[lis[a][0],lis[b][0]])
     if len(lis[a])>=2 and len(lis[b]):evaluate('AAB',(a,b),[lis[a][0],lis[a][1],lis[b][0]])
    for abc in itertools.combinations(range(4),3):
     if all(len(lis[t])for t in abc):evaluate('ACD',abc,[lis[t][0]for t in abc])
    if all(len(lis[t])for t in range(4)):evaluate('ABCD',(0,1,2,3),[lis[t][0]for t in range(4)])
    for a in range(4):
     for b,d in itertools.combinations([t for t in range(4)if t!=a],2):
      if len(lis[a])>=2 and len(lis[b])and len(lis[d]):evaluate('AABC',(a,b,d),[lis[a][0],lis[a][1],lis[b][0],lis[d][0]])
    for name in ('AA','AB','AAB','ACD','AABC','ABCD'):coverage.append(dict(image_id=g['image_id'],condition=g['condition'],family=family,repeat=rep,pattern=name,feasible_role_assignments=sum(k[0]==name for k in store),remaining_type_counts=str({t:len(v)for t,v in lis.items()})))
    comparisons=[]
    for key2 in store:
     name,role=key2
     if name=='AB'and('AA',(role[0],))in store:comparisons.append((key2,('AA',(role[0],)),'AB minus AA'))
     if name=='AAB'and('AA',(role[0],))in store:comparisons.append((key2,('AA',(role[0],)),'AAB minus AA'))
     if name=='AABC':
      if ('AAB',role[:2])in store:comparisons.append((key2,('AAB',role[:2]),'AABC minus AAB'))
      if ('ABCD',(0,1,2,3))in store:comparisons.append((('ABCD',(0,1,2,3)),key2,'ABCD minus AABC'))
    for ka,kb,name in comparisons:
     for method in ('equal','continuous','context','type4'):
      a=store[ka][method];b=store[kb][method];effects.append(dict(image_id=g['image_id'],building=g['building'],condition=g['condition'],family=family,repeat=rep,contrast=name,method=method,role_a=str(ka[1]),role_b=str(kb[1]),n_a=a['n_people'],n_b=b['n_people'],actual_delta=a['actual']-b['actual'],predicted_delta=a['predicted']-b['predicted'],abs_delta_error=abs((a['actual']-b['actual'])-(a['predicted']-b['predicted'])),seed_workers=a['seed_workers'],workers_a=a['worker_ids'],workers_b=b['worker_ids']))
  print('ALL_ROLES',g['condition'],g['image_id'],flush=True)
 df=pd.DataFrame(rows);df.to_csv(dest/'real_compositions.csv.gz',index=False);pd.DataFrame(coverage).to_csv(dest/'coverage.csv',index=False);ed=pd.DataFrame(effects);ed.to_csv(dest/'matched_effects.csv.gz',index=False)
 # Average repetitions/feasible roles within image BEFORE comparing conditions.
 ag=ed.groupby(['condition','family','contrast','method','image_id','building'],as_index=False)[['actual_delta','predicted_delta','abs_delta_error']].mean();ag.to_csv(dest/'matched_effect_per_image.csv',index=False);ag.groupby(['condition','family','contrast','method']).agg(images=('image_id','nunique'),real_delta=('actual_delta','mean'),predicted_delta=('predicted_delta','mean'),mae=('abs_delta_error','mean')).reset_index().to_csv(dest/'summary.csv',index=False)
 paired=[]
 for (arm,fam,contrast),gg in ag.groupby(['condition','family','contrast']):
  for method in ('continuous','context','type4'):
   z=paired_fast(gg,method,'equal','abs_delta_error')
   if z:paired.append(dict(condition=arm,family=fam,contrast=contrast,**z))
 pd.DataFrame(paired).to_csv(dest/'paired_increment.csv',index=False)
 c.js(dest/'COMPLETE.json',dict(status='complete',distinct_real_subsets=df[['image_id','condition','subset_id']].drop_duplicates().shape[0],images=df.image_id.nunique(),role_assignment_rule='all feasible type roles; no target-geometry selection',small_group_complete_convergence_claim=False,novel_independent_people=0))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();run(a.output)
