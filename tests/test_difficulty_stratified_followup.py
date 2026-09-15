"""Tests for the 106-tag follow-up; no images, model weights or visual inference."""
import json,gzip,shutil
from pathlib import Path
import numpy as np,pandas as pd,pytest
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor
from tools.thesis_main.analysis.image_portrait import difficulty_stratified_cv as cv
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import B,O,load,first_clause,keyword_vector,FUNCTIONS
from tools.thesis_main.analysis.image_portrait.difficulty_history_bridge import label_profile

def fixture_frame(n=26):
 return pd.DataFrame(dict(image_id=[f'B{i//6}_image{i}'for i in range(n)],building=[f'B{i//6}'for i in range(n)],scene_category=['bed'if i%2 else'bath'for i in range(n)],main_function_primary=['sleep'if i%2 else'bath'for i in range(n)],y=np.arange(n)%3,main_space_safe=['room']*n))

@pytest.mark.parametrize('pc',[0,16,32])
def test_ridge_matches_primal_and_train_pca(pc):
 rng=np.random.default_rng(13);X=rng.normal(size=(26,45));d=fixture_frame();tr=np.arange(20);ev=np.arange(20,26);p=cv.grids(X,d,tr,ev)
 ss=StandardScaler();A=ss.fit_transform(X[tr]);V=ss.transform(X[ev])
 if pc:
  pca=PCA(n_components=min(pc,len(tr)-1),svd_solver='full');A=pca.fit_transform(A);V=pca.transform(V)
 for mi,mode in enumerate(cv.MODES):
  bt=cv.cat_probs(d,tr,tr,mode);bv=cv.cat_probs(d,tr,ev,mode);model=Ridge(alpha=10).fit(A,np.eye(3)[d.y.to_numpy()[tr]]-bt);expected=cv.prob(bv+model.predict(V));j=next(j for j,g in enumerate(cv.GRID)if g['algorithm']=='ridge'and g['pca']==pc and g['alpha']==10)
  np.testing.assert_allclose(p[mi,j],expected,atol=2e-6)

@pytest.mark.parametrize('pc',[0,16,32])
def test_knn_matches_primal(pc):
 rng=np.random.default_rng(19);X=rng.normal(size=(26,35));d=fixture_frame();tr=np.arange(20);ev=np.arange(20,26);p=cv.grids(X,d,tr,ev)
 ss=StandardScaler();A=ss.fit_transform(X[tr]);V=ss.transform(X[ev])
 if pc:
  pca=PCA(n_components=min(pc,len(tr)-1),svd_solver='full');A=pca.fit_transform(A);V=pca.transform(V)
 for mi,mode in enumerate(cv.MODES):
  bt=cv.cat_probs(d,tr,tr,mode);bv=cv.cat_probs(d,tr,ev,mode);model=KNeighborsRegressor(n_neighbors=3).fit(A,np.eye(3)[d.y.to_numpy()[tr]]-bt);expected=cv.prob(bv+model.predict(V));j=next(j for j,g in enumerate(cv.GRID)if g['algorithm']=='knn'and g['pca']==pc and g['k']==3)
  np.testing.assert_allclose(p[mi,j],expected,atol=2e-6)

def test_current_target_labels_never_enter_fit():
 X=np.random.default_rng(3).normal(size=(26,8));d=fixture_frame();tr=np.arange(20);ev=np.arange(20,26);a=cv.grids(X,d,tr,ev);d.loc[ev,'y']=2;bb=cv.grids(X,d,tr,ev);np.testing.assert_array_equal(a,bb)

def test_full_nested_selection_ignores_outer_labels(tmp_path,monkeypatch):
 d=fixture_frame(24);X=np.random.default_rng(7).normal(size=(24,8));monkeypatch.setattr(cv,'O',tmp_path);(tmp_path/'images').mkdir();(tmp_path/'cache').mkdir();d.to_csv(tmp_path/'images/labels106.csv',index=False);np.save(tmp_path/'cache/toy.npy',X)
 cv.run_feature('toy');a=pd.read_csv(tmp_path/'cv/pooled/toy.csv.gz');a=a[a.building=='B0'].reset_index(drop=True)
 shutil.rmtree(tmp_path/'cv');d.loc[d.building=='B0','y']=2;d.to_csv(tmp_path/'images/labels106.csv',index=False);cv.run_feature('toy');b=pd.read_csv(tmp_path/'cv/pooled/toy.csv.gz');b=b[b.building=='B0'].reset_index(drop=True)
 np.testing.assert_array_equal(a[['p0','p1','p2','grid']],b[['p0','p1','p2','grid']])

def test_unknown_stratum_does_not_read_test_labels():
 d=fixture_frame();tr=np.arange(20);ev=np.arange(20,26);d.loc[ev,'scene_category']='not_seen';a=cv.cat_probs(d,tr,ev,'coarse');d.loc[ev,'y']=2;b=cv.cat_probs(d,tr,ev,'coarse');np.testing.assert_array_equal(a,b)

def test_rps_is_cumulative_probability_score():
 assert cv.rps(np.array([1.,0,0]),0)==0;assert cv.rps(np.array([0.,1,0]),0)==.5;assert cv.rps(np.array([0.,0,1]),0)==1

def test_declared_subjective_labels_and_sources():
 d=pd.read_csv(O/'images/labels106.csv');assert len(d)==106 and d.image_id.nunique()==106;assert d.difficulty_tag.value_counts().to_dict()=={'简单':49,'中等':41,'困难':16};raw={r['image_id']:r for r in load(B/'metadata/spatial_history.jsonl.gz')}
 assert all(raw[r.image_id]['latest_selection_record']['difficulty']==r.difficulty_tag for r in d.itertuples())
 assert d.main_space_human.notna().sum()==11;assert(d.main_space_source=='AI_new_spatial_review').all()

def test_first_clause_does_not_promote_adjacent_room():
 x='淋浴内部为主，玻璃外主浴室可见';assert first_clause(x)=='淋浴内部为主';v=keyword_vector(first_clause('卧室床区为主；厨房次要'),FUNCTIONS);assert v['sleep']==1 and v['kitchen']==0

def test_frozen_leave_building_membership():
 d=pd.read_csv(O/'images/labels106.csv');ids=set(d.image_id)
 folds=load(B/'evaluation/folds.jsonl.gz')
 for f in folds:
  if f['design']!='leave_building':continue
  te=ids&set(f['test']);tr=ids&set(f['train']);assert not te&tr and te|tr==ids
  if te:
   b=d[d.image_id.isin(te)].building.unique();assert len(b)==1;assert tr==set(d[d.building!=b[0]].image_id)

def test_all_methods_keep_106_targets():
 p=pd.read_csv(O/'results/all_oof_predictions.csv.gz');g=p.groupby(['design','feature','baseline','algorithm']);assert(g.image_id.nunique()==106).all();assert(g.size()==106).all();assert np.isfinite(p[['p0','p1','p2','rps']]).all().all();np.testing.assert_allclose(p[['p0','p1','p2']].sum(1),1,atol=1e-6)

def test_exact_dino_106_payload_identity():
 q=pd.read_csv(O/'audit/loaded_model_files.csv');assert q[q.model=='dinov3'].image_id.nunique()==106
 d=json.loads((O/'cache/image_ids.json').read_text());assert len(d)==106

@pytest.mark.parametrize('design,field',[('within_coarse','scene_category'),('within_main','main_function_primary')])
def test_training_empty_status_is_not_silent(design,field):
 d=pd.read_csv(O/'images/labels106.csv');p=pd.read_csv(O/'results/all_oof_predictions.csv.gz');p=p[(p.design==design)&(p.feature=='selected__existing')&(p.algorithm=='ridge')&(p.baseline=='main')]
 for _,x in p.iterrows():
  row=d[d.image_id==x.image_id].iloc[0];n=((d[field]==row[field])&(d.building!=row.building)).sum()
  if not n:assert 'fallback'in x.status

def test_room_history_excludes_target_and_pending_relations():
 d=pd.read_csv(O/'images/labels106.csv').set_index('image_id');p=pd.read_csv(O/'rooms/same_room_tag_predictions.csv');assert p.image_id.nunique()==54 and p.room_id.nunique()==9
 for r in p.itertuples():
  members=r.training_image_ids.split(';');assert r.image_id not in members;assert d.loc[r.image_id,'room_status']=='supported_component';assert all(d.loc[x,'room_id']==d.loc[r.image_id,'room_id']for x in members)

def test_worker_exclusions_and_oos_separation():
 p=B/'cloud/pro_exploration/v2_convergence_e086b2b9/foundation/human/response_metrics.csv.gz';d=pd.read_csv(p);q=d[d.main_worker_included];assert len(q)==2388;assert 'W011'in set(q.worker_id);assert not({'W019','W026'}&set(q.worker_id));s=pd.read_csv(O/'historical_bridge/inputs/image_uncertainty_structure.csv');assert set(s.condition)=={'manual','semi'}

def test_early_limits_and_unknown_are_separate():
 e=pd.read_csv(O/'historical_bridge/early_onset_probabilities.csv');assert set(e.early_k)=={2,3,4,5,6,7};assert label_profile(2,0,1,0,1,0,1,0,7,15,3,.1,.8)=='insufficient_observed_people';assert label_profile(24,0,5,0,0,1,1,0,7,15,3,.1,.8)=='stable_many_supported_modes'

def test_invalid_and_singletons_not_relabelled_as_never_converges():
 a=label_profile(12,1,4,.2,0,0,0,.2,7,15,3,.1,.8);assert a=='invalid_records_preclude_process_tier';b=label_profile(24,0,6,.4,0,0,0,.2,7,15,3,.1,.8);assert b=='observed_fragmented_late_changes';assert 'never'not in b and 'cannot_converge'not in b

def test_suffix_confirmation_difference_is_preserved():
 d=pd.read_csv(O/'historical_bridge/confirmation_disagreement.csv');q=d[(d.image_id=='uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97')&(d.cut==.1)&(d.rule=='G10_geometry')];assert len(q)==1;assert q.p_any_suffix.iloc[0]==.84 and q.p_tail_stable.iloc[0]==.54

def test_native_historical_mean_matched_coverage():
 d=pd.read_csv(O/'legacy/native_labels.csv');assert len(d)==35 and d.image_id.nunique()==35;p=pd.read_csv(O/'legacy/native_predictions.csv');assert(p.groupby(['feature','baseline','algorithm']).image_id.nunique()==35).all()
