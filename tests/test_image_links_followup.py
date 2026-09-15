"""Numerical and provenance regression tests for the b02 continuation."""
import json,hashlib,itertools
import numpy as np
import pandas as pd
import pytest
from tools.thesis_main.analysis.image_portrait.image_links_followup_common import *
from tools.thesis_main.analysis.image_portrait.image_links_followup_predict import Provider,probabilities,load_tasks,loss
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict import center_scale,grid,CONFIGS
from tools.thesis_main.analysis.image_portrait.history_difficulty_review_v2 import cluster

@pytest.fixture(scope='module')
def groups_data():return groups()
@pytest.fixture(scope='module')
def targets():return pd.read_csv(OUT/'targets/per_image_versions_and_process.csv')
@pytest.fixture(scope='module')
def combinations_data():return pd.read_csv(OUT/'E/real_combinations_fixed_future2.csv.gz')

def test_latest_raw_git_blob():
 p=B/'human/responses.jsonl.gz';v=p.read_bytes();sha=hashlib.sha1(b'blob '+str(len(v)).encode()+b'\0'+v).hexdigest();assert sha=='6261c30d1abf2d7ad0e71702348fc81819e783ad'
def test_raw_canonical_count_and_uniqueness():
 r=readj(B/'human/responses.jsonl.gz');assert len(r)==2501;assert len({x['canonical_annotation_id']for x in r})==2501

def test_union_expansion(targets):
 assert targets.image_id.nunique()==214;assert len(targets)==239
 m=readj(OUT/'audit/manifest.json');assert m['union']==285 and m['intersection']==35

def test_conditions(targets):assert targets.groupby('condition').size().to_dict()=={'manual':187,'oos_geometry':9,'semi':43}

def test_excluded_workers_never_votes(groups_data):
 for _,_,_,workers,_ in groups_data.values():assert not set(workers)&EXCLUDE

def test_no_duplicate_people(groups_data):
 for _,_,_,w,c in groups_data.values():assert len(w)==len(set(w))==len(c)

def test_w011_retained(groups_data):assert any('W011'in w for _,_,_,w,_ in groups_data.values())

def test_all_distance_properties(groups_data):
 for _,dm,pc,w,ci in groups_data.values():
  assert dm.shape==(len(w),len(w));np.testing.assert_allclose(dm,dm.T);assert np.isfinite(dm).all();assert np.all(np.diag(dm)==0)
  if len(w):assert np.all(dm[pc[:,None]!=pc[None,:]]==2)

def test_point_counts_never_merged(groups_data):
 for _,dm,pc,w,ci in groups_data.values():
  if not len(w):continue
  lab=cluster(dm,pc,.1)
  for k in np.unique(lab):assert len(set(pc[lab==k]))==1

def test_corrected_odd_retained():
 raw=readj(B/'human/responses.jsonl.gz');valid=readj(OUT/'inputs/effective_points.json');n=0
 for r in raw:
  if r['worker_id']in EXCLUDE or r['raw_condition']not in ['manual','semi']:continue
  if r['raw_point_count']%2:
   verified=r['processing_status']in ['confirmed_point_removed','confirmed_point_added']and bool(r.get('confirmation_source'))
   assert (r['canonical_annotation_id']in valid)==bool(verified)
   if verified:n+=1;assert len(valid[r['canonical_annotation_id']])%2==0
 assert n==5

def test_oos_geometry_and_exposure():
 raw=[r for r in readj(B/'human/responses.jsonl.gz')if r['worker_id']not in EXCLUDE and r['raw_condition']=='oos'];assert len(raw)==216
 assert all(r.get('assistance_exposure')=='none'and r.get('unassisted_manual_included')for r in raw)
 a=pd.read_csv(OUT/'audit/coverage.csv').set_index('condition');assert a.loc['oos_geometry','valid_responses']==212

def test_old_pairwise_parity():
 a=pd.read_csv(OUT/'audit/old_pairwise_parity.csv');assert len(a)==230
 numeric=a.select_dtypes('number');assert np.nanmax(numeric.filter(regex='delta').to_numpy())<1e-8

def test_candidates_unchanged(targets):
 src=pd.read_csv(V2/'proposal/final_review_draft_per_image.csv');x=targets[targets.condition.ne('oos_geometry')].merge(src,on=['image_id','condition'],suffixes=('_new','_old'))
 assert x.review_draft_grade_new.fillna('').equals(x.review_draft_grade_old.fillna(''))

def test_candidate_counts(targets):
 a=targets[targets.condition=='manual'].review_draft_grade.value_counts();assert a['simple_candidate']==22 and a['medium_candidate']==27 and a['difficult_candidate']==12

def test_no_review_is_approval(targets):assert targets.review_status.eq('not_provided').all()and targets.reviewed_grade.isna().all()

def test_oos_no_in_scope_candidate(targets):assert targets[targets.condition=='oos_geometry'].review_draft_grade.eq('not_assigned_scope_separate').all()

def test_cold_features_exclude_outcomes():
 p=Provider([next(iter(groups()))[0]])
 for name in ['scene','main_space','traits','positions','fine_human','fine_ai','scene_traits','main_traits']:
  cols=p.fields(name);assert not any(x in ['n_valid','n_observed','quality','difficulty','review_draft_grade']for x in cols)
 assert 'corner_occlusion'not in p.fields('traits')

def test_train_only_centering():
 X=np.arange(20).reshape(5,4).astype(float);X[1]*=.75;X[4]+=20;tr=np.array([0,1,2]);A=center_scale(X@X.T,tr)
 Z=X.copy();Z[4]+=999;C=center_scale(Z@Z.T,tr);np.testing.assert_allclose(A[np.ix_(tr,tr)],C[np.ix_(tr,tr)],atol=1e-10)

def test_grid_does_not_read_target_labels():
 rng=np.random.default_rng(42);X=rng.normal(size=(8,4));y=rng.uniform(size=(8,1));tr=np.arange(5);te=np.arange(5,8);K=center_scale(X@X.T,tr);p=grid(K,y,tr,te,False);y2=y.copy();y2[te]=999;np.testing.assert_allclose(grid(K,y2,tr,te,False),p)

def test_kernel_ridge_against_explicit_solution():
 rng=np.random.default_rng(71);X=rng.normal(size=(9,5));Y=rng.uniform(size=(9,2));tr=np.arange(6);te=np.arange(6,9);K=center_scale(X@X.T,tr);out=grid(K,Y,tr,te,False);j=next(j for j,c in enumerate(CONFIGS)if c['algorithm']=='ridge'and c['pca']is None and c['parameter']==10);mu=Y[tr].mean(0);pred=K[np.ix_(te,tr)]@np.linalg.solve(K[np.ix_(tr,tr)]+10*np.eye(6),Y[tr]-mu)+mu;np.testing.assert_allclose(out[j],np.clip(pred,0,1),atol=1e-9)

def test_probabilities_valid():
 p=probabilities(np.array([[-1.,-1.,-1.],[.2,.3,.6]]),np.array([.2,.7,.1]));np.testing.assert_allclose(p.sum(1),1);assert (p>=0).all();np.testing.assert_allclose(p[0],[.2,.7,.1])

def test_all_fixed_candidates_completed():
 s=readj(OUT/'prediction/execution_progress.json');assert len(s)==155;assert not [r for r in s if r['status']=='failed']

def test_actual_folds_disjoint_buildings():
 for fold in readj(B/'evaluation/folds.jsonl.gz'):
  tr=set(fold['train']);te=set(fold['test']);assert not tr&te
  if fold['design']!='same_room_leave_view':assert not {i.split('_')[0]for i in tr}&{i.split('_')[0]for i in te}

def test_70_model_kernels205():
 reg=readj(V1/'kernels/registry.json');assert len(reg)==70
 for r in reg:
  z=np.load(V1/'kernels'/r['file']);assert len(z['image_ids'])==205;assert z['K'].shape==(205,205)

def test_oos_real4model9():
 a=pd.read_csv(OUT/'audit/oos_inherited_model_sources.csv');assert len(a)==63;assert a.sha256.notna().all()
 r=pd.read_csv(OUT/'C/oos_inherited_candidate_inventory.csv');assert len(r)==33 and r.images.eq(9).all()

def test_family_inventory():
 a=pd.read_csv(OUT/'E/information_family_group_capacity.csv');assert a.family.nunique()==16;assert not a.family.isna().any()

def test_verified_semi_axes_not_missing():
 a=pd.read_csv(OUT/'E/person_axis_input_coverage.csv').set_index('raw_condition');assert a.loc['semi','benefit']==532 and a.loc['semi','edit']==532

def test_future_people_separated(combinations_data):
 pairs=combinations_data[['workers','future_workers']].drop_duplicates()
 for r in pairs.itertuples():
  w=r.workers.split(';');f=r.future_workers.split(';');assert len(w)==len(set(w));assert len(f)==2;assert not set(w)&set(f)

def test_real_combinations_not_new_samples(combinations_data):
 assert len(combinations_data)==585554;assert combinations_data.image_id.nunique()==151
 assert {'AA','AB','AAB','AABC','ABCD'}<=set(combinations_data.signature);assert 'ACD'in set(combinations_data.actual_types)

def test_type_qualification_outside_building():
 a=pd.read_csv(OUT/'E/outside_building_axis_profiles.csv');q=a[a.qualified];assert (q.training_responses>=6).all()and(q.training_buildings>=3).all();raw=pd.read_csv(V1/'inputs/response_metrics_sanitized.csv.gz')
 # Scores are recomputed from excluded-building data in an isolated fitting call.
 from tools.thesis_main.analysis.image_portrait.image_links_followup_people import raw_axes,fits
 rows=raw_axes();b=a.target_building.iloc[0];p=pd.DataFrame(fits(rows,'manual',b));rows.loc[rows.building==b,'quality']=999;z=pd.DataFrame(fits(rows,'manual',b));np.testing.assert_allclose(p.score,z.score,equal_nan=True)

def test_neighbors_are_not_targets():
 a=pd.read_csv(OUT/'D/conditional_predictions_with_neighbors.csv.gz',low_memory=False);z=a[a.actual_neighbor_id.notna()];assert (z.image_id!=z.actual_neighbor_id).all()
 q=z[z.design.isin(['all_other_building','same_scene_other_building','same_mainspace_other_building'])];assert all(i.split('_')[0]!=j.split('_')[0]for i,j in zip(q.image_id,q.actual_neighbor_id))

def test_common_person_crossview_identity():
 a=pd.read_csv(OUT/'D/exact_common_people_across_views.csv');assert a.common_n.max()>4
 for r in a.itertuples():assert len(r.common_workers.split(';'))==r.common_n and len(r.canonical_ids_a.split(';'))==r.common_n and len(r.canonical_ids_b.split(';'))==r.common_n

def test_review_queue_no_invented_decisions():
 a=pd.read_csv(OUT/'local_image_review_queue.csv');assert a.user_decision.isna().all()and a.user_reason.isna().all();assert a.canonical_ids.notna().all()
