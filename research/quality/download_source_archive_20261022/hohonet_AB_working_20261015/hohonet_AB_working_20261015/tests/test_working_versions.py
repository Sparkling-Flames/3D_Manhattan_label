from pathlib import Path
import sys,json
import numpy as np,pandas as pd,pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from working_models import score,attribution,floor_upper_bound,MODELS,WQ,A,B,Parameters
from native_geometry import project,erp_triples,direction,iou,bottom_distance
RESULTS=Path(__import__('os').environ.get('AB_TEST_RESULTS',str(ROOT/'results')))

@pytest.mark.parametrize('p',list(MODELS.values()))
def test_perfect_zero_and_height(p):
 assert float(score(1,0,0,0,0,p))==100
 assert float(score(0,9,10,.2,.2,p))==0
 assert np.isclose(score(1,0,0,3,0,p),100/(1+(3/.8)**2))
 assert float(score(0,1e300,1,1e300,1e300,p))==0

@pytest.mark.parametrize('p',list(MODELS.values()))
def test_bounds_and_monotonic_raw_components(p):
 rng=np.random.default_rng(234);x=np.c_[rng.uniform(.001,1,500),rng.uniform(0,30,500),rng.uniform(0,25,500),rng.uniform(0,3,500),rng.uniform(0,1,500)]
 y=score(*x.T,p);assert np.all(y>=0) and np.all(y<=100*x[:,0]+1e-10)
 for k in range(5):
  z=x.copy();z[:,k] *= .9 if k==0 else 1.1
  assert np.all(score(*z.T,p)<=y+1e-10)

@pytest.mark.parametrize('p',list(MODELS.values()))
def test_missing_never_zero(p):
 for k in range(5):
  x=[.8,1,2,.02,.03];x[k]=None
  with pytest.raises(ValueError):score(*x,p)
 with pytest.raises(ValueError):score(1.2,0,0,0,0,p)
 with pytest.raises(ValueError):score(.8,-1,0,0,0,p)

@pytest.mark.parametrize('p',list(MODELS.values()))
def test_shapley_additivity_not_ablations(p):
 r=attribution(.8,2,6,.1,.08,p)
 assert abs(sum(v for k,v in r.items() if k.startswith('shapley_loss_'))-r['total_loss_points'])<1e-10
 assert all(v>=-1e-10 for k,v in r.items() if k.startswith(('delete_','shapley_')))
 assert not np.isclose(sum(v for k,v in r.items() if k.startswith('delete_')),r['total_loss_points'])

@pytest.mark.parametrize('p',list(MODELS.values()))
def test_floor_upper_is_only_upper(p):
 f=float(floor_upper_bound(.7,2,4,p));q=float(score(.7,2,4,.12,.04,p));assert q<f

def test_no_D_same_all_versions():
 rng=np.random.default_rng(3);I=rng.uniform(.01,1,100);s=rng.uniform(0,10,100);g=rng.uniform(0,1,100);l=rng.uniform(0,.5,100)
 assert np.allclose(score(I,s,0,g,l,A),score(I,s,0,g,l,WQ),rtol=0,atol=1e-12)
 assert np.allclose(score(I,s,0,g,l,B),score(I,s,0,g,l,WQ),rtol=0,atol=1e-12)

def test_B_balanced_and_not_max():
 # F=1 and d8=1 (D^2=128), geometric loss sqrt(2), not 1 nor 2.
 D=np.sqrt(128);q=float(score(.5,0,D,0,0,B));assert np.isclose(q,100/(1+np.sqrt(2)))
 assert q<50 and q>100/3

def test_B_response_and_pool_separable():
 r=attribution(.8,1,5,.03,.01,B);F=r['floor_fidelity_loss'];d=r['direction_loss']
 assert np.isclose(r['effective_extra_direction_loss'],d*d/(np.hypot(F,d)+F))
 assert 0<r['effective_extra_direction_loss']<d

def test_versions_not_uniform_shift_or_equivalence():
 d=pd.read_csv(RESULTS/'SCORES_1145.csv');delta=d.Q_A10-d.Q_B8L2
 assert (delta>1e-6).any() and (delta< -1e-6).any()
 assert (d.Q_A10>=d.Q_WQ-1e-10).all() and (d.Q_B8L2>=d.Q_WQ-1e-10).all()

def test_1145_input_columns_preserved_and_parity():
 raw=pd.read_csv(ROOT/'inputs/JOINT_COMPARISON_1145.csv');d=pd.read_csv(RESULTS/'SCORES_1145.csv')
 assert len(d)==1145 and d.record_id.nunique()==1145
 for c in raw.columns:pd.testing.assert_series_equal(raw[c],d[c],check_names=False)
 assert max(abs(raw.WQ-d.Q_WQ))<1e-10
 assert not d.formal_eligibility_newly_granted.any()

def test_qualification_counts():
 d=pd.read_csv(RESULTS/'SCORES_1145.csv')
 assert d.comparison_layer.value_counts().to_dict()=={'ordinary_manual_conditional':931,'doorway_conditional':115,'semi_secondary':39,'two_image_scope_diagnostic':28,'doorway_target_hold':10,'historical_diagnostic':10,'severe_exception':9,'ordinary_target_hold':3}

def test_nonorthogonal_self_and_family_blind_spot_retained():
 d=pd.read_csv(RESULTS/'geometric_controls.csv').set_index('case')
 r=d.loc['nonorthogonal_self_0.1'];assert np.isclose(r.iou_2d,1)
 assert 0<r.Q_WQ<r.Q_A10<100 and r.Q_B8L2<100
 assert d.loc['rhombus_1','dir']<d.loc['rhombus_45','dir']
 assert d.loc['rhombus_1','Q_B8L2']<d.loc['rhombus_45','Q_B8L2']

def test_omission_not_fixed_or_rewarded():
 d=pd.read_csv(RESULTS/'geometric_controls.csv').set_index('case');r=d.loc['branch_omission_0.1']
 assert r.Q_WQ>98 and np.isclose(r.Q_A10,r.Q_WQ) and np.isclose(r.Q_B8L2,r.Q_WQ)

def test_two_image_full_NA_and_exclusions():
 d=pd.read_csv(RESULTS/'TWO_IMAGE_CHANGELOG_36.csv');p=pd.read_csv(RESULTS/'TWO_IMAGE_FLOOR_COMPARISONS_68.csv')
 assert len(d)==36 and len(p)==68 and d.record_id.nunique()==36
 assert sum(d.execution_status.eq('unavailable_pairing'))==2
 for c in ['new_full_WQ','new_full_A10','new_full_B8L2','new_full_IoU3D','adopted_reference_id']:assert d[c].isna().all()
 assert not d.formal_eligibility_newly_granted.any() and not d.photo_visual_adjudication_completed.any()
 raw=json.loads((ROOT/'inputs/CURRENT_TWO_IMAGE_MINIMAL_38.json').read_text(encoding='utf-8'))['objects']
 for o in raw:
  if o['object_kind']!='annotation':continue
  z=d[d.object_id.eq(o['object_id'])].iloc[0];assert z.condition==o['condition'] and z.cleaning_disposition==o['cleaning_disposition']

def test_new_floor_ERP_round_trip_not_top_imputation():
 req=pd.read_csv(RESULTS/'TOP_BOUNDARY_REQUEST_8.csv');ds=json.loads((ROOT/'inputs/TWO_IMAGE_SCOPE_DELTA.json').read_text(encoding='utf-8'))['records']
 assert req.top_y_erp.isna().all()
 for r in ds:
  z=req[req.image_code.eq(r['image_code'])].sort_values('corner_index')
  # Arbitrary synthetic top used only for inverse-projection UNIT TEST, never a reference.
  triples=np.c_[z.bottom_x_erp.to_numpy(),np.full(len(z),100.),z.bottom_y_erp.to_numpy()]
  x,_=project(triples);assert np.max(abs(x-np.array(r['new_floor_polygon_xz_h'])))<1e-10

def test_stage_lock_same_ordinary_door():
 s=json.loads((RESULTS/'ORDINARY_FROZEN_WORKING.json').read_text(encoding='utf-8'));t=json.loads((RESULTS/'DOORWAY_FINAL_WORKING.json').read_text(encoding='utf-8'))
 assert s['ordinary_complete_before_doorway'] and not t['changed']
 assert s['A']==t['A'] and s['B']==t['B']
 assert len(pd.read_csv(RESULTS/'ordinary_coarse_grid_28.csv'))==28

def test_difficulty_no_target_substitution():
 d=pd.read_csv(RESULTS/'DIFFICULTY_JOIN_1145.csv');assert d.same_reference_id.sum()==1050
 z=d[d.difficulty_comparison_allowed];assert len(z)==836 and z.image_id.nunique()==95
 assert z.same_reference_id.all() and (z.comparison_layer=='ordinary_manual_conditional').all()
 assert not z.current_class.eq('单列').any()

def test_worker_fusion_targets_not_used_for_tuning():
 d=pd.read_csv(RESULTS/'leave_building_selection_diagnostic.csv');assert d.target_building_excluded.all()
 f=pd.read_csv(RESULTS/'fusion_220_rescored.csv');assert len(f)==220 and f.analysis_allowed.sum()==89
 assert f.operation.eq('fixed_endpoint_rescoring_no_reselection_or_refusion').all()
 assert f[f.status.ne('complete')][['Q_WQ','Q_A10','Q_B8L2']].isna().all().all()

def test_invariances_native():
 x=np.array([[-2,-2],[2,-2],[2,0],[0,0],[0,2],[-2,2]],float)
 for z in [np.roll(x,2,axis=0),x[::-1],np.insert(x,1,(x[0]+x[1])/2,axis=0)]:
  assert abs(direction(z)-direction(x))<1e-10 and abs(iou(x,z)-1)<1e-12
  assert bottom_distance(x,z)<1e-10

def test_concave_control_camera_is_strictly_inside():
 d=pd.read_csv(RESULTS/'geometric_controls.csv').set_index('case');r=d.loc['concave_L_self']
 assert r.camera_strictly_inside_candidate and r.camera_strictly_inside_reference and r.physical_camera_below_all_top
 assert abs(r.Q_A10-100)<1e-10 and abs(r.Q_B8L2-100)<1e-10

def test_next20_not_used_for_ordinary_tuning():
 s=pd.read_csv(ROOT/'inputs/next_review_bindings.csv');h=pd.read_csv(RESULTS/'HUMAN44_AB_COMPARISON.csv')
 assert len(s)==20 and s.blind_id.nunique()==20 and not s.used_for_current_calibration.any()
 assert not set(s.image_id).intersection(h.image_id)
