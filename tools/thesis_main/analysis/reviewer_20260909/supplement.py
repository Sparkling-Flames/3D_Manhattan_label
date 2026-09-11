"""No-imputation sensitivity and equal-task coarse-group composition replay.
These are finite observed-worker checks, not natural-type or causal claims.
"""
import argparse,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from worker_audit import lines,metric,fit,cv,summarize,semi_cv,semi_summary,save,CURRENT

def run(repo,out):
 ar=repo/'analysis_results';view=lines(ar/'confirmed_point_calculation_view_20260909_v1/reviewed/calculation_view.jsonl.gz');ref={r['image_id']:r for r in lines(ar/'worker_reference_feasibility_20260909_v1/reference_ledger.jsonl')};vmap={r['canonical_annotation_id']:r for r in view}
 m=pd.read_csv(out/'reviewed_reference_measurements.csv.gz',dtype={'worker_id':str});s=m[m.scored&(m.assistance_exposure=='none')].copy();s['context_key']=s.image_id
 no=s.copy();updated=[]
 for i,r in no.iterrows():
  v=vmap[r.canonical_annotation_id]
  if v['imputed_point']:
   for c in [30,60]:no.loc[i,'ospa'+str(c)]=metric(v['raw_points_1024x512'],ref[r.image_id]['points_1024x512'],c)
   updated.append(dict(canonical_annotation_id=r.canonical_annotation_id,image=r.image_id,worker_id=r.worker_id,original_count=len(v['raw_points_1024x512']),effective_count=len(v['effective_points_1024x512'])))
 save(out,'no_imputation_records.csv',updated)
 predictions=[]
 for cohort,people in [('all26',set(no.worker_id)),('current20',CURRENT)]:
  for cap in [30,60]:
   d=no[no.worker_id.isin(people)].assign(value=lambda x:x['ospa'+str(cap)]);p=cv(d);predictions.append(p.assign(cohort=cohort,cap=cap))
 a,b=summarize(pd.concat(predictions),['cohort','cap']);save(out,'no_imputation_manual_summary.csv',a)
 sem=pd.read_csv(out/'reviewed_semi_features.csv',dtype={'worker_id':str});p,mem=semi_cv(no,sem);a,b=semi_summary(p);save(out,'no_imputation_semi_summary.csv',a)
 # Disjoint half stability summary; no claim repetitions are independent studies.
 st=pd.read_csv(out/'manual_disjoint_building_stability.csv');q=st.groupby(['cohort','metric']).agg(splits=('replicate','size'),rho_median=('rank_rho','median'),rho_q25=('rank_rho',lambda x:x.quantile(.25)),rho_q75=('rank_rho',lambda x:x.quantile(.75)),ARI_median=('coarse_ARI','median'),label_agreement_median=('label_agreement','median')).reset_index();save(out,'manual_disjoint_summary.csv',q)
 # Reference-defined operational classes, fit outside the entire target building.
 # Every recipe/k uses identical images, eligible identities and repetition seeds.
 rng=np.random.default_rng(20260909);rr=[];support=[];profiles=[]
 for building in sorted(s.building_id.unique()):
  train=s[s.worker_id.isin(CURRENT)&(s.building_id!=building)];f=fit(train.assign(value=train.ospa30));cut=f.median();A=set(f[f<=cut].index);B=set(f[f>cut].index)
  for w in f.index:profiles.append(dict(heldout_building=building,worker_id=w,reference_effect=f[w],operational_coarse='A' if w in A else 'B'))
  for image,g in s[s.worker_id.isin(CURRENT)&(s.building_id==building)].groupby('image_id'):
   g=g.sort_values('worker_id');ids=g.canonical_annotation_id.tolist();people=g.worker_id.tolist();ia=np.array([j for j,w in enumerate(people) if w in A]);ib=np.array([j for j,w in enumerate(people) if w in B]);supported=min(len(ia),len(ib))>=6
   support.append(dict(image_id=image,building_id=building,n_A=len(ia),n_B=len(ib),common_recipe_k2_4_6=supported))
   if not supported:continue
   pts=[vmap[i]['raw_points_1024x512'] if vmap[i]['imputed_point'] else vmap[i]['effective_points_1024x512'] for i in ids];n=len(pts);D=np.zeros((n,n))
   for i in range(n):
    for j in range(i):D[i,j]=D[j,i]=metric(pts[i],pts[j],30)
   quality=np.array([no.set_index('canonical_annotation_id').loc[i,'ospa30'] for i in ids]);count=np.array([len(p) for p in pts])
   for rep in range(160):
    pa=rng.permutation(ia);pb=rng.permutation(ib)
    for k in [2,4,6]:
     for recipe,sel in [('A',pa[:k]),('AB_equal',np.r_[pa[:k//2],pb[:k//2]]),('B',pb[:k])]:
      T=D[np.ix_(sel,sel)];means=T.sum(1);ties=sel[np.isclose(means,means.min(),rtol=0,atol=1e-10)];med=np.mean(quality[ties])
      rr.append(dict(image_id=image,building_id=building,reference_basis=g.reference_basis.iloc[0],replicate=rep,k=k,recipe=recipe,pairwise_OSPA30=T.sum()/(k*(k-1)),medoid_reference_OSPA30=med,point_count_disagreement=np.sum(count[sel,None]!=count[sel][None,:])/(k*(k-1)),distinct_workers=len(set(np.array(people)[sel])),n_tied_medoids=len(ties)))
 save(out,'coarse_recipe_support.csv',support);save(out,'coarse_recipe_profiles.csv',profiles);save(out,'coarse_recipe_replay.csv.gz',rr)
 z=pd.DataFrame(rr);summ=[]
 if len(z):
  for (k,recipe),g in z.groupby(['k','recipe']):
   b=g.groupby('building_id')[['pairwise_OSPA30','medoid_reference_OSPA30','point_count_disagreement']].mean()
   summ.append(dict(k=k,recipe=recipe,images=g.image_id.nunique(),buildings=g.building_id.nunique(),**b.mean().to_dict()))
  # Same target images, same repetition for paired differences; building conditional uncertainty only.
  contrasts=[]
  for metric0 in ['pairwise_OSPA30','medoid_reference_OSPA30']:
   p=z.groupby(['building_id','image_id','k','recipe'])[metric0].mean().unstack('recipe')
   for k,g in p.groupby(level='k'):
    for left,right in [('A','B'),('AB_equal','B'),('A','AB_equal')]:
     delta=(g[left]-g[right]).groupby(level='building_id').mean();draw=rng.choice(delta.to_numpy(),(4000,len(delta)),replace=True).mean(1)
     contrasts.append(dict(k=k,metric=metric0,comparison=left+' minus '+right,images=len(g),buildings=len(delta),difference=delta.mean(),conditional_q025=np.quantile(draw,.025),conditional_q975=np.quantile(draw,.975)))
  save(out,'coarse_recipe_paired_contrasts.csv',contrasts)
 save(out,'coarse_recipe_summary.csv',summ)
 (out/'SUPPLEMENT_QA.json').write_text(json.dumps(dict(no_imputation_responses=len(updated),coarse_recipe_complete_images=int(pd.DataFrame(support).common_recipe_k2_4_6.sum()),coarse_recipe_rows=len(rr),labels='training-building-excluded median reference-effect strata; A is lower relative error',reference_policy='existing reference ledger; not independent truth or literal rule adherence',raw_points_modified=False,new_annotations=0),indent=2))
 print('SUPPLEMENT DONE',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.repo,a.out)
