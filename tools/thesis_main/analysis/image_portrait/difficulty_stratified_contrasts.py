"""Within-source-stratum contrasts and literal local-image review evidence.
Pair counts are not independent samples. All supervised scores are outer held-out.
"""
import itertools,collections
import numpy as np,pandas as pd
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import *

def entropy(v):
 q=pd.Series(v).value_counts(normalize=True).to_numpy();return float(-np.sum(q*np.log2(q)))
def describe():
 d=pd.read_csv(O/'images/labels106.csv');rows=[]
 for fields in [['scene_category'],['main_function_primary'],['fine_ai'],['building'],['selection_display_group'],['scene_category','building'],['main_function_primary','building'],['scene_category','main_function_primary']]:
  for key,g in d.groupby(fields,dropna=False):
   rows.append(dict(stratification='+'.join(fields),stratum=str(key),n_images=len(g),n_buildings=g.building.nunique(),n_labels=g.y.nunique(),label_entropy=entropy(g.y),simple=int((g.y==0).sum()),medium=int((g.y==1).sum()),hard=int((g.y==2).sum()),labelled_images=';'.join(g.image_id)))
 csv('stratification/source_strata.csv',rows)
 sums=[]
 for key,g in pd.DataFrame(rows).groupby('stratification'):
  sums.append(dict(stratification=key,n_strata=len(g),mixed_label_strata=int((g.n_labels>1).sum()),images_in_mixed_strata=int(g.loc[g.n_labels>1,'n_images'].sum()),conditional_label_entropy=float(np.average(g.label_entropy,weights=g.n_images)),overall_label_entropy=entropy(d.y),caution='descriptive only: sparse partitions can trivially lower empirical entropy'))
 csv('stratification/descriptive_entropy.csv',sums)
 v=[]
 for field in TRAITS+['doorway']+['position_'+x for x in POSITIONS]:
  for cat,g in d.groupby('scene_category'):
   for val,z in g.groupby(field,dropna=False):v.append(dict(field=field,scene=cat,value=val,n=len(z),n_buildings=z.building.nunique(),simple=int((z.y==0).sum()),medium=int((z.y==1).sum()),hard=int((z.y==2).sum())))
 csv('stratification/trait_and_main_positions_counts.csv',v)
 # Explicit sample-selection coverage: no extrapolation from the 106 to the 648.
 allx=pd.read_csv(O/'images/metadata_all648.csv');cov=[]
 for field in ['scene_category','main_function_primary']:
  for val,g in allx.groupby(field):cov.append(dict(field=field,value=val,pool=len(g),labelled=int((g.difficulty_status=='labelled').sum()),selected_fraction=float((g.difficulty_status=='labelled').mean())))
 csv('stratification/selection_coverage.csv',cov)
 # All mixed display groups, but physical eligibility comes from independent relationship ledger.
 mixed=[]
 for group,g in d.groupby('selection_display_group'):
  if g.y.nunique()>1:
   for _,z in g.iterrows():mixed.append(dict(display_group=group,image_id=z.image_id,scene=z.scene_category,main_space=z.main_space_raw,label=z.difficulty_tag,room_id=z.room_id,room_status=z.room_status))
 csv('stratification/mixed_display_group_members.csv',mixed)

def pair_evaluation():
 d=pd.read_csv(O/'images/labels106.csv');allp=pd.read_csv(O/'results/all_oof_predictions.csv.gz');records=[];summaries=[];physical=[]
 selected=allp[(allp.feature.str.startswith('selected__')&(allp.baseline.isin(['global','main']))&(allp.algorithm=='ridge'))|allp.feature.isin(['baseline__global','baseline__coarse','baseline__main'])]
 panels={'coarse_within_building':['building','scene_category'],'main_within_building':['building','main_function_primary'],'supported_room_same_coarse':['room_id','scene_category']}
 for design,fields in panels.items():
  panel=d[d.room_status=='supported_component']if design.startswith('supported')else d
  pairs=[]
  for key,g in panel.groupby(fields):
   for a,b in itertools.combinations(g.index,2):
    if d.y.iloc[a]==d.y.iloc[b]:continue
    a,b=(a,b)if d.y.iloc[a]<d.y.iloc[b]else(b,a)
    pairs.append((a,b));physical.append(dict(comparison_stratum=design,image_low=d.image_id.iloc[a],image_high=d.image_id.iloc[b],label_low=d.difficulty_tag.iloc[a],label_high=d.difficulty_tag.iloc[b],building=d.building.iloc[a],main_low=d.main_space_raw.iloc[a],main_high=d.main_space_raw.iloc[b],room_status=d.room_status.iloc[a],same_room_id=d.room_id.iloc[a]==d.room_id.iloc[b]))
  for (scheme,feature,baseline,alg),p in selected.groupby(['design','feature','baseline','algorithm']):
   pp=p.set_index('image_id').loc[d.image_id][['p0','p1','p2']].to_numpy();trial=[]
   for a,b in pairs:
    lo,hi=int(d.y.iloc[a]),int(d.y.iloc[b]);gap=(np.cumsum(pp[a])[:2]-np.cumsum(pp[b])[:2])[lo:hi];scores=np.where(np.abs(gap)<1e-6,.5,(gap>0).astype(float));trial.append(dict(comparison_stratum=design,design=scheme,feature=feature,baseline=baseline,algorithm=alg,image_low=d.image_id.iloc[a],image_high=d.image_id.iloc[b],building=d.building.iloc[a],scene=d.scene_category.iloc[a],concordance=float(scores.mean()),gap=float(gap.mean())))
   records.extend(trial)
   if trial:
    z=pd.DataFrame(trial);group=z.groupby('building').concordance.agg(['sum','count','mean']);rng=np.random.default_rng(SEED);ix=rng.integers(len(group),size=(5000,len(group)));v=group.to_numpy();boot=v[ix,0].sum(1)/v[ix,1].sum(1)
    summaries.append(dict(comparison_stratum=design,design=scheme,feature=feature,baseline=baseline,algorithm=alg,n_pairs=len(z),n_buildings=len(group),n_images=len(set(z.image_low)|set(z.image_high)),pair_concordance=z.concordance.mean(),building_macro_concordance=group['mean'].mean(),lo=np.quantile(boot,.025),hi=np.quantile(boot,.975)))
 csv('contrasts/heldout_label_pair_scores.csv.gz',records);csv('contrasts/heldout_label_pair_summary.csv',summaries);csv('contrasts/mixed_label_pairs.csv',physical)

def similarity():
 d=pd.read_csv(O/'images/labels106.csv');n=len(d);names=[f'dinov3__block{k}__panorama_mean'for k in [3,6,9,11,12]]+['dinov3__cls__panorama','dinov3__block12__faces_global'];nn=[];summ=[];queues=[]
 expectations={field:sum(c*(c-1)for c in d[field].value_counts())/(n*(n-1))for field in ['building','scene_category','main_function_primary','difficulty_tag']}
 for name in names:
  X=np.load(O/'cache'/f'{name}.npy').astype(float);X/=np.maximum(np.linalg.norm(X,axis=1,keepdims=True),1e-12);C=X@X.T;np.fill_diagonal(C,-np.inf)
  for rule in ['all_labelled106','outside_building','outside_building_same_coarse','outside_building_same_main']:
   local=[]
   for i in range(n):
    ok=np.arange(n)!=i
    if rule!='all_labelled106':ok&=d.building.to_numpy()!=d.building.iloc[i]
    if rule.endswith('_coarse'):ok&=d.scene_category.to_numpy()==d.scene_category.iloc[i]
    if rule.endswith('_main'):ok&=d.main_function_primary.to_numpy()==d.main_function_primary.iloc[i]
    candidates=np.flatnonzero(ok);ix=candidates[np.argsort(-C[i,candidates],kind='stable')[:5]]
    if not len(ix):local.append(dict(image_id=d.image_id.iloc[i],feature=name,rule=rule,n_neighbors=0,status='no_eligible_labeled_neighbor'));continue
    local.append(dict(image_id=d.image_id.iloc[i],feature=name,rule=rule,n_neighbors=len(ix),same_building=float(np.mean(d.building.to_numpy()[ix]==d.building.iloc[i])),same_coarse=float(np.mean(d.scene_category.to_numpy()[ix]==d.scene_category.iloc[i])),same_main=float(np.mean(d.main_function_primary.to_numpy()[ix]==d.main_function_primary.iloc[i])),same_tag=float(np.mean(d.y.to_numpy()[ix]==d.y.iloc[i])),status='ok'))
    for rank,j in enumerate(ix):
     nn.append(dict(image_id=d.image_id.iloc[i],neighbor_id=d.image_id.iloc[j],feature=name,rule=rule,rank=rank+1,cosine=float(C[i,j]),target_tag=d.difficulty_tag.iloc[i],neighbor_tag=d.difficulty_tag.iloc[j],target_main=d.main_space_raw.iloc[i],neighbor_main=d.main_space_raw.iloc[j],target_coarse=d.scene_category.iloc[i],neighbor_coarse=d.scene_category.iloc[j],same_room=d.room_id.iloc[i]==d.room_id.iloc[j],room_relation_usable=bool(d.room_id.iloc[i]==d.room_id.iloc[j]and d.room_status.iloc[i]=='supported_component')))
   z=pd.DataFrame(local);sums=z[z.status=='ok'].select_dtypes('number').mean().to_dict();summ.append(dict(feature=name,rule=rule,n_targets=n,n_with_neighbors=int((z.status=='ok').sum()),**sums));
 csv('similarity/neighbor_pairs.csv.gz',nn);csv('similarity/neighbor_summary.csv',summ);savej('similarity/random_neighbor_expectations.json',dict(on_pool='106 labelled only; not 648',expected_same=expectations,note='descriptive cosine neighborhoods, not independent validation, physical relation or convergence'))

if __name__=='__main__':
 describe();pair_evaluation();similarity();print('CONTRASTS DONE',flush=True)
