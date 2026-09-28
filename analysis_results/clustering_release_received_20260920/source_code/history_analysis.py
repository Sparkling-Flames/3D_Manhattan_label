"""Finite real-person replay, composition demonstration, and available scene/model analyses.
All resampled entities are distinct existing people. Replicates are NOT additional samples.
"""
from __future__ import annotations
import argparse,collections,copy,hashlib,itertools,json,math
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import spearmanr
from release import CONFIG,cluster,frame,writejson,prepare

def miss(N,m,k):
 return math.comb(N-1-m,k)/math.comb(N-1,k) if 0<=k<=N-1-m else 0.
def next_uncovered(D,k,t=9):
 N=len(D)
 if not 0<=k<N:return np.nan
 nei=(np.round(D,8)<=t).sum(axis=1)-1
 return float(np.mean([miss(N,int(m),k) for m in nei]))
def fixed_mode_stats(l,k):
 N=len(l);sizes=list(collections.Counter(l).values());den=math.comb(N,k)
 K=0.;K2=0.;ones=0.;missingmass=0.;minoritymiss=0.;minoritytot=0.
 for s in sizes:
  p0=math.comb(N-s,k)/den if k<=N-s else 0.
  p1=s*math.comb(N-s,k-1)/den if k>=1 and k-1<=N-s else 0.
  K+=1-p0;K2+=1-p0-p1;ones+=p1;missingmass+=s/N*p0
  if s>=2 and s/N<=.2:minoritymiss+=s/N*p0;minoritytot+=s/N
 return dict(retrospective_expected_modes=K,retrospective_expected_supported_modes=K2,retrospective_singleton_response_fraction=ones/k,
             retrospective_unseen_fullpool_mode_mass=missingmass,retrospective_unseen_repeated_minority_mass=minoritymiss,retrospective_repeated_minority_total_mass=minoritytot)

def run_history(root,out,permutations=128,new_path=None):
 cache=json.loads((out/'cache.json').read_text());curves=[];replays=[];groupstates=[];rng=np.random.default_rng(20260920)
 for key,g in cache.items():
  D=np.array(g['matrices']['split_cyclic']);N=len(D);base=dict(key=key,code=g['code'],image_id=key.split('|')[0],condition=key.split('|')[1],building=g['building'],N=N,N_record=g['N_record'])
  for t in [6,9,12]:
   lab=cluster(D,t)
   for k in range(1,N+1):curves.append(dict(**base,cut=t,k=k,next_real_person_uncovered=next_uncovered(D,k,t) if k<N else np.nan,**fixed_mode_stats(lab,k)))
   if t==9:
    co=collections.Counter(lab);iso=int(((np.round(D,8)<=t).sum(1)==1).sum());K=len(co);single=sum(x==1 for x in co.values())
    state='insufficient_for_growth_demo' if N<8 or N<g['N_record'] else 'observed_pool_single_compatible' if K==1 else 'observed_pool_repeated_modes_no_singletons' if single==0 else 'observed_pool_has_singleton_expressions'
    groupstates.append(dict(**base,clusters=K,singletons=single,isolated_no_compatible_peer=iso,state=state,stopping_n=None,interpretation='descriptive_state_not_population_convergence',next_uncovered_k5=next_uncovered(D,5,t) if N>5 else np.nan,next_uncovered_k8=next_uncovered(D,8,t) if N>8 else np.nan,next_uncovered_Nminus1=iso/N))
  if N<8:continue
  group_rng=np.random.default_rng(int(hashlib.sha256((key+'20260920').encode()).hexdigest()[:16],16))
  for rep in range(permutations):
   order=group_rng.permutation(N);prev=None
   for k in range(2,N+1):
    ix=order[:k];d=D[np.ix_(ix,ix)];l=cluster(d,9);co=collections.Counter(l)
    oldrel_changed=np.nan if prev is None else float(np.mean((prev[:,None]==prev[None,:])[np.triu_indices(k-1,1)]!=(l[:-1,None]==l[None,:-1])[np.triu_indices(k-1,1)])) if k>2 else 0.
    nextbad=bool(np.min(D[order[k],ix])>9+1e-8) if k<N else np.nan
    replays.append(dict(key=key,code=g['code'],condition=base['condition'],N=N,replicate=rep,k=k,clusters=len(co),singletons=sum(s==1 for s in co.values()),supported=sum(s>=2 for s in co.values()),largest_share=max(co.values())/k,next_uncovered=nextbad,previous_pair_relation_changed=oldrel_changed))
    prev=l
 c=frame(out,'historical_exact_curves.csv',curves);frame(out,'observed_pool_states.csv',groupstates)
 r=frame(out,'prefix_reclustering_replays.csv.gz',replays)
 agg=r.groupby(['key','code','condition','N','k']).agg(cluster_mean=('clusters','mean'),cluster_p10=('clusters',lambda x:x.quantile(.1)),cluster_p90=('clusters',lambda x:x.quantile(.9)),singleton_mean=('singletons','mean'),largest_share_mean=('largest_share','mean'),mean_relation_churn=('previous_pair_relation_changed','mean'),mc_next_uncovered=('next_uncovered','mean')).reset_index()
 frame(out,'prefix_reclustering_summary.csv',agg)
 # Freeze the same >=19-person images at every k<=18: no changing image mix in aggregate plots.
 selected=c[(c.N>=19)&(c.k<=18)]
 frame(out,'high_support_curve_summary.csv',selected.groupby(['condition','cut','k']).agg(images=('image_id','nunique'),next_uncovered=('next_real_person_uncovered','mean'),unseen_mode_mass=('retrospective_unseen_fullpool_mode_mass','mean'),single_response_mass=('retrospective_singleton_response_fraction','mean'),expected_modes=('retrospective_expected_modes','mean'),minority_unseen_mass=('retrospective_unseen_repeated_minority_mass','mean')).reset_index())
 # No borrowed imputation: restore only the two existing borrowed-point records in a numerical copy.
 st,rows,rec,elig,sroot=prepare(root,new_path);changed=[];alternative=[];rawrows=copy.deepcopy(rows)
 for r in rawrows:
  if r.get('imputed_point'):
   oldn=r['effective_point_count'];r['effective_points_1024x512']=r['raw_points_1024x512'];r['effective_point_count']=r['raw_point_count'];changed.append(dict(id=r['canonical_annotation_id'],image_id=r['image_id'],condition=r['raw_condition'],worker=r['worker_id'],old_count=oldn,raw_count=r['raw_point_count']))
 _,_,rec2,el2,_=prepare(root,new_path,restore_borrowed=True)
 affected={x['image_id']+'|'+x['condition'] for x in changed}
 for key,g in cache.items():
  if key in affected:
   rr=[rec2[i] for i in g['ids'] if i in rec2];ids=[x['id'] for x in rr];D=np.full((len(rr),len(rr)),181.);np.fill_diagonal(D,0)
   for i,j in itertools.combinations(range(len(rr)),2):
    s,_=st.compare(rr[i],rr[j]);D[i,j]=D[j,i]=s.get('split_cyclic',181.)
  else:D=np.array(g['matrices']['split_cyclic'])
  if len(D)<19:continue
  for k in [3,5,8,12,16]:
   for t in [6,9,12]:alternative.append(dict(key=key,code=g['code'],condition=key.split('|')[1],N=len(D),k=k,cut=t,next_uncovered=next_uncovered(D,k,t),borrowed_point_changed=key in affected))
 frame(out,'no_borrowed_imputation_records.csv',changed);frame(out,'no_borrowed_exact_curves.csv',alternative)
 return cache

def profiles(cache):
 obs=[]
 for key,g in cache.items():
  if key.split('|')[1]!='manual' or len(g['ids'])<3:continue
  D=np.array(g['matrices']['split_cyclic']);q=(np.round(D,8)>9).sum(axis=1)/(len(D)-1)
  for w,val in zip(g['workers'],q):obs.append(dict(key=key,image_id=key.split('|')[0],building=g['building'],worker=w,strict_disagreement=float(val)))
 return pd.DataFrame(obs)

def run_composition(root,out,cache):
 obs=profiles(cache);frame(out,'profile_observations.csv',obs);prows=[];teamrows=[];sumrows=[];coverage=[]
 for key,g in cache.items():
  if key.split('|')[1]!='manual' or len(g['ids'])<12:continue
  train=obs[obs.building!=g['building']];p=train.groupby('worker').agg(propensity=('strict_disagreement','mean'),history_images=('image_id','nunique'),history_buildings=('building','nunique'));p=p[p.history_images>=5]
  if len(p)<8:continue
  edges=np.quantile(p.propensity,[.25,.5,.75]);p['bin']=np.searchsorted(edges,p.propensity,side='right');p['label']=p.bin.map(dict(enumerate('ABCD')))
  for w,r in p.iterrows():prows.append(dict(target_building=g['building'],worker=w,**r.to_dict(),basis='other_buildings_manual_strict_disagreement_not_psychology'))
  eligible=[i for i,w in enumerate(g['workers']) if w in p.index]
  if len(eligible)<12:continue
  rank=sorted(eligible,key=lambda i:hashlib.sha256((g['ids'][i]+'validation20260920').encode()).hexdigest());held=rank[:4];pool=rank[4:]
  bins={s:[i for i in pool if p.loc[g['workers'][i],'label']==s] for s in 'ABCD'}
  good=len(bins['A'])>=2 and all(bins[x] for x in 'BCD')
  coverage.append(dict(key=key,code=g['code'],N=len(g['ids']),available_profile_workers=len(eligible),common_validation_workers=';'.join(g['workers'][i] for i in held),**{'n_'+s:len(v) for s,v in bins.items()},both_compositions_feasible=good))
  if not good:continue
  abcd=list(itertools.product(*[bins[s] for s in 'ABCD']))
  aabc=[(a,b,c,d) for a,b in itertools.combinations(bins['A'],2) for c in bins['B'] for d in bins['C']]
  D=np.array(g['matrices']['split_cyclic']);slices=[]
  for label,teams in [('ABCD',abcd),('AABC',aabc)]:
   ar=np.array(teams,int);assert all(len(set(x))==4 for x in ar)
   for cut in [6,9,12]:
    cov=np.round(D,8)<=cut
    uncovered=(~np.any(cov[np.array(held)[None,:,None],ar[:,None,:]],axis=2)).mean(1)
    within=np.mean([~cov[ar[:,i],ar[:,j]] for i,j in itertools.combinations(range(4),2)],axis=0)
    slopes=np.mean([[p.loc[g['workers'][i],'propensity'] for i in team] for team in teams],axis=1)
    sumrows.append(dict(key=key,code=g['code'],image_id=key.split('|')[0],building=g['building'],composition=label,cut=cut,n_teams=len(teams),n_validation=4,mean_uncovered=float(uncovered.mean()),mean_within_disagreement=float(within.mean()),mean_profile=float(slopes.mean()),evaluation='same_fixed_4_heldout_people_finite_pool_association'))
    if cut==9:
     for team,u,v,sc in zip(teams,uncovered,within,slopes):teamrows.append(dict(key=key,code=g['code'],composition=label,worker_ids=';'.join(g['workers'][i] for i in team),canonical_ids=';'.join(g['ids'][i] for i in team),validation_ids=';'.join(g['ids'][i] for i in held),uncovered=u,within_disagreement=v,mean_profile=sc))
 frame(out,'composition_feasibility.csv',coverage);frame(out,'out_of_building_profiles.csv',pd.DataFrame(prows).drop_duplicates(['target_building','worker']));frame(out,'composition_teams.csv',teamrows);s=frame(out,'composition_summary.csv',sumrows)
 if not s.empty:
  p=s.pivot(index=['key','code','building','cut'],columns='composition',values=['mean_uncovered','mean_within_disagreement']).reset_index();p.columns=['_'.join(x).strip('_') if isinstance(x,tuple) else x for x in p.columns]
  p['delta_uncovered_AABC_minus_ABCD']=p.mean_uncovered_AABC-p.mean_uncovered_ABCD;p['delta_within_AABC_minus_ABCD']=p.mean_within_disagreement_AABC-p.mean_within_disagreement_ABCD;frame(out,'composition_paired_contrasts.csv',p)


def run_rooms(root,out,cache):
 reg=json.loads((root/'input/supplement/same_room_selection_registry_20260912.json').read_text());pairs=collections.defaultdict(set)
 for r in reg['candidates']:
  if not r['physical_same_supported']:continue
  for a,b in itertools.combinations(sorted(r['image_ids']),2):pairs[a,b].add(r['candidate_id'])
 results=[]
 for (a,b),groups in pairs.items():
  for cond in ['manual','semi','oos']:
   ka=a+'|'+cond;kb=b+'|'+cond
   if ka not in cache or kb not in cache:continue
   A,B=cache[ka],cache[kb];workers=sorted(set(A['workers'])&set(B['workers']))
   if len(workers)<3:continue
   ix=[A['workers'].index(w) for w in workers];jx=[B['workers'].index(w) for w in workers]
   da=np.array(A['matrices']['split_cyclic'])[np.ix_(ix,ix)];db=np.array(B['matrices']['split_cyclic'])[np.ix_(jx,jx)]
   tri=np.triu_indices(len(ix),1)
   results.append(dict(image_a=a,image_b=b,code_a=A['code'],code_b=B['code'],building=A['building'],condition=cond,support_groups=';'.join(sorted(groups)),N_common=len(workers),workers=';'.join(workers),disagreement_a=float((da[tri]>9).mean()),disagreement_b=float((db[tri]>9).mean()),clusters_a=len(set(cluster(da,9))),clusters_b=len(set(cluster(db,9))),next_uncovered_k3_a=next_uncovered(da,3) if len(ix)>3 else np.nan,next_uncovered_k3_b=next_uncovered(db,3) if len(ix)>3 else np.nan))
 frame(out,'same_room_common_people.csv',results)
 meta=[json.loads(l) for l in (root/'input/supplement/images.jsonl').read_text().splitlines()];writejson(out/'IMAGE_METADATA_SCHEMA.json',{'first_record':meta[0],'metadata_use':'descriptive_mapping_only_not_same_room_inference'})
 # Same person time ratios, reuse vetted timing rows, never insert lead_time.
 p=root/'input/source/analysis_results/local_point_research_received_20260919/inputs/time_same_room_person_pairs.csv';d=pd.read_csv(p);d=d[(d.seconds_a>0)&(d.seconds_b>0)].copy();d['long_short_ratio']=np.maximum(d.seconds_a,d.seconds_b)/np.minimum(d.seconds_a,d.seconds_b)
 t=d.groupby(['code_a','code_b','building','context']).agg(common_people=('worker','nunique'),median_long_short_ratio=('long_short_ratio','median')).reset_index();frame(out,'same_person_time_context.csv',t)


def run_prediction(root,out,cache):
 # Existing model output descriptors only. No target-person or target-image human geometry is an input.
 from sklearn.linear_model import Ridge
 from sklearn.preprocessing import StandardScaler
 from sklearn.impute import SimpleImputer
 from sklearn.pipeline import make_pipeline
 F=pd.read_csv(root/'input/supplement/model_image_features.csv').set_index('image_id');data=[]
 for key,g in cache.items():
  if key.split('|')[1]!='manual' or len(g['ids'])<8 or key.split('|')[0] not in F.index:continue
  D=np.array(g['matrices']['split_cyclic']);r=F.loc[key.split('|')[0]].to_dict();r.update(key=key,image_id=key.split('|')[0],code=g['code'],N=len(D),target=next_uncovered(D,5));data.append(r)
 d=pd.DataFrame(data);frame(out,'prediction_input_targets.csv',d)
 sets={'N_only':['N'],'N_plus_corners':['N']+[c for c in F.columns if c.endswith('_corners')],'N_plus_Bi':['N','gap_bi_enclosed__bi_extended'],'N_plus_model_feedback':['N']+[c for c in F.columns if c.endswith('_corners') or c.startswith('gap_')]}
 preds=[];choices=[]
 def fit(X,y,alpha):return make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),Ridge(alpha=alpha)).fit(X,y)
 for b in sorted(d.building.unique()):
  train=d[d.building!=b];test=d[d.building==b]
  for name,cols in sets.items():
   errors=[]
   for alpha in [.1,1.,10.,100.]:
    per=[]
    for v in train.building.unique():
     tr=train[train.building!=v];va=train[train.building==v]
     if len(tr)<5:continue
     y=np.clip(fit(tr[cols],tr.target,alpha).predict(va[cols]),0,1);per.append(np.mean(abs(y-va.target)))
    errors.append((np.mean(per),alpha))
   err,alpha=min(errors);model=fit(train[cols],train.target,alpha);y=np.clip(model.predict(test[cols]),0,1)
   choices.append(dict(heldout_building=b,model=name,alpha=alpha,inner_building_mean_MAE=err))
   for (_,r),yp in zip(test.iterrows(),y):preds.append(dict(image_id=r.image_id,code=r.code,building=b,model=name,observed=r.target,predicted=yp,absolute_error=abs(r.target-yp),target='finite_pool_next_uncovered_after_k5_not_stopping_n'))
  for _,r in test.iterrows():
   yp=train.target.mean();preds.append(dict(image_id=r.image_id,code=r.code,building=b,model='train_mean',observed=r.target,predicted=yp,absolute_error=abs(r.target-yp),target='finite_pool_next_uncovered_after_k5_not_stopping_n'))
 pr=frame(out,'model_LOBO_predictions.csv',preds);frame(out,'model_inner_selection.csv',choices)
 frame(out,'model_LOBO_summary.csv',pr.groupby('model').agg(images=('image_id','nunique'),buildings=('building','nunique'),MAE=('absolute_error','mean')).reset_index())
 # Building-bootstrap interval for paired differences. Small number of buildings, exploratory only.
 w=pr.pivot(index=['image_id','building'],columns='model',values='absolute_error').reset_index();rng=np.random.default_rng(20260920);rr=[]
 for name in sets:
  if name=='N_only':continue
  z=w.assign(delta=w[name]-w.N_only).groupby('building').delta.mean();boots=np.mean(rng.choice(z.values,size=(4000,len(z)),replace=True),axis=1)
  rr.append(dict(model=name,reference='N_only',buildings=len(z),building_equal_delta_MAE=z.mean(),bootstrap_low=np.quantile(boots,.025),bootstrap_high=np.quantile(boots,.975),claim='exploratory_historical_not_new_person_validation'))
 for name,reference in [('N_plus_model_feedback','N_plus_corners')]:
  z=w.assign(delta=w[name]-w[reference]).groupby('building').delta.mean();boots=np.mean(rng.choice(z.values,size=(4000,len(z)),replace=True),axis=1)
  rr.append(dict(model=name,reference=reference,buildings=len(z),building_equal_delta_MAE=z.mean(),bootstrap_low=np.quantile(boots,.025),bootstrap_high=np.quantile(boots,.975),claim='exploratory_incremental_comparison'))
 frame(out,'model_paired_building_intervals.csv',rr)

if __name__=='__main__':
 r=Path(__file__).resolve().parents[1];o=r/'results/release';c=run_history(r,o);run_composition(r,o,c);run_rooms(r,o,c);run_prediction(r,o,c)
