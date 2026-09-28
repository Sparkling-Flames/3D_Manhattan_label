"""Simple decomposition and inference safeguards; no new clustering algorithm."""
from pathlib import Path
import collections,hashlib,itertools,json
import numpy as np,pandas as pd
from release import cluster,frame,writejson
from history_analysis import next_uncovered

def run(root,out):
 cache=json.loads((out/'cache.json').read_text());elig=pd.read_csv(out/'eligibility.csv').set_index('id');rr=[]
 for key,g in cache.items():
  if len(g['ids'])<2:continue
  n=len(g['ids']);D=np.array(g['matrices']['split_cyclic']);counts=np.array(g['counts']);total=(counts[:,None]!=counts[None,:])*181.;roles=elig.loc[g['ids'],['n_top','n_bottom']].to_numpy();same=(counts[:,None]==counts[None,:])&np.all(roles[:,None,:]==roles[None,:,:],axis=2);role=(~same)*181.
  for k in [3,5,8,12,16]:
   if k>=n:continue
   for t in [6,9,12]:
    ut=next_uncovered(total,k);ur=next_uncovered(role,k);ug=next_uncovered(D,k,t)
    assert -1e-10<=ur-ut and -1e-10<=ug-ur
    rr.append(dict(key=key,code=g['code'],image_id=key.split('|')[0],condition=key.split('|')[1],building=g['building'],N=n,k=k,cut=t,uncovered_total=ug,new_total_count=ut,new_role_count_given_known_total=ur-ut,new_geometry_or_order_given_known_role_counts=ug-ur))
 d=frame(out,'novelty_decomposition.csv',rr)
 frame(out,'novelty_decomposition_highN.csv',d[d.N>=19].groupby(['condition','cut','k']).agg(images=('image_id','nunique'),uncovered_total=('uncovered_total','mean'),new_total_count=('new_total_count','mean'),new_role_count_given_known_total=('new_role_count_given_known_total','mean'),new_geometry_or_order_given_known_role_counts=('new_geometry_or_order_given_known_role_counts','mean')).reset_index())
 # Numerical scene/category association from supplied labels only; no new visual labeling.
 reg=json.loads((root/'input/supplement/same_room_selection_registry_20260912.json').read_text());labels={r['image_id']:r for r in reg['images']};items=[]
 for r in d[(d.k==5)&(d.cut==9)].to_dict('records'):
  v=labels.get(r['image_id'],{});cl=v.get('spatial_classification',{});items.append(r|dict(coarse_type=cl.get('coarse_type','missing'),main_visual_space=v.get('main_visual_space','missing'),label_provenance=v.get('spatial_review_provenance','missing')))
 z=frame(out,'scene_label_association_rows.csv',items)
 frame(out,'scene_label_association_summary.csv',z.groupby(['condition','coarse_type']).agg(images=('image_id','nunique'),mean_uncovered=('uncovered_total','mean'),median_uncovered=('uncovered_total','median')).reset_index())
 # Identity-specific future-effect claims not supported by quartiles: report label instability explicitly.
 p=pd.read_csv(out/'out_of_building_profiles.csv');st=[]
 for w,g in p.groupby('worker'):
  c=g.label.value_counts();st.append(dict(worker=w,target_building_folds=g.target_building.nunique(),modal_quartile=c.index[0],modal_fraction=c.iloc[0]/len(g),minimum_score=g.propensity.min(),maximum_score=g.propensity.max(),interpretation='overlapping_training_folds_not_independent_type_validation'))
 frame(out,'profile_quartile_sensitivity.csv',st)
 # Building-block bootstrap of composition differences; not independent-team significance.
 c=pd.read_csv(out/'composition_paired_contrasts.csv');rng=np.random.default_rng(20260920);bres=[]
 for cut,g in c.groupby('cut'):
  for field in ['delta_uncovered_AABC_minus_ABCD','delta_within_AABC_minus_ABCD']:
   by=g.groupby('building')[field].mean();boot=rng.choice(by.values,(4000,len(by)),replace=True).mean(1)
   bres.append(dict(cut=cut,endpoint=field,images=len(g),buildings=len(by),image_equal_mean=g[field].mean(),building_equal_mean=by.mean(),block_bootstrap_low=np.quantile(boot,.025),block_bootstrap_high=np.quantile(boot,.975),negative_images=int((g[field]<-1e-10).sum()),positive_images=int((g[field]>1e-10).sum()),zero_images=int((g[field].abs()<=1e-10).sum())))
 frame(out,'composition_building_intervals.csv',bres)
 # Full-group context explains why one confirmed local relation does not imply automatic group merge.
 a=json.loads((out/'uNb21_partial_anchor.json').read_text())['original'];g=cache[a['image_id']+'|manual'];D=np.array(g['matrices']['split_cyclic']);i=g['ids'].index(a['id_a']);j=g['ids'].index(a['id_b']);cand=float(pd.read_csv(out/'uNb21_hypothetical_partition.csv').hypothetical_distance.iloc[0]);D1=D.copy();D1[i,j]=D1[j,i]=cand;rows=[]
 for cut in [6,9,12]:
  l=cluster(D1,cut);x=np.where(l==l[i])[0];y=np.where(l==l[j])[0];v=D1[np.ix_(x,y)];u,w=np.unravel_index(v.argmax(),v.shape);u=x[u];w=y[w]
  rows.append(dict(cut=cut,group_a_workers=';'.join(g['workers'][k] for k in x),group_b_workers=';'.join(g['workers'][k] for k in y),maximum_cross_distance=v.max(),witness_worker_a=g['workers'][u],witness_worker_b=g['workers'][w],witness_id_a=g['ids'][u],witness_id_b=g['ids'][w]))
 frame(out,'uNb21_group_context.csv',rows)
 # Marginal coverage saturation cannot by itself be interpreted as a correct answer.
 claims=[
  ('measurement','supported','All raw coordinates unchanged; endpoint metric and strict count gate are explicit.'),
  ('semantic_cluster_accuracy','unverified','Development judgments and AI observations do not provide a representative blind benchmark.'),
  ('uNb21_anchor','partially_supported','Only group3->group4 is user confirmed; reciprocal mapping is a scenario, not an applied correction.'),
  ('future_stopping_count','not_frozen','Finite-pool curves do not certify a population stopping rule.'),
  ('composition','exploratory_supported','Same-size actual teams and common actual validation participants were compared using out-of-building profiles.'),
  ('psychological_types','not_established','A-D are quantitative history quartiles, not personality or diligence categories.'),
  ('model_prediction','historical_validation','Nested held-building model evaluation concerns finite-pool geometric noncoverage, not quality or pool-external future participants.'),
  ('new_data_intake','software_ready','Append-only canonical schema with duplicate and coordinate checks; upstream time/role/exposure audit remains required.')]
 frame(out,'claim_status.csv',[dict(topic=a,status=b,basis=c) for a,b,c in claims])
if __name__=='__main__':
 r=Path(__file__).resolve().parents[1];run(r,r/'results/release')
