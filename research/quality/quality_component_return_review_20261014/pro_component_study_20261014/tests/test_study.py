import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from models import losses,aggregate
from geometry import interior_angles,matched_angle_error,simplify_collinear,direction_rms
W=np.array([.35,.30,.10,.20,.05])
SQUARE=np.array([[-1.,-1.],[1.,-1.],[1.,1.],[-1.,1.]])

def test_harmonic_equivalence():
    p=np.random.default_rng(4).lognormal(0,2,(10000,5));s,_=aggregate(p,W)
    np.testing.assert_allclose(s['WQ_LS08'],s['harmonic_exact_rewrite'],atol=5e-14,rtol=1e-14)

def test_mean_inequality():
    p=np.random.default_rng(8).lognormal(0,2,(10000,5));s,_=aggregate(p,W)
    assert np.all(s['WQ_LS08']<=s['geometric_control']+1e-12)
    assert np.all(s['geometric_control']<=s['arithmetic_candidate']+1e-12)

@pytest.mark.parametrize('column',range(5))
def test_component_monotonicity(column):
    p=np.ones((100,5))*.02;p[:,column]=np.linspace(0,20,100);s,_=aggregate(p,W)
    for values in s.values():assert np.max(np.diff(values))<1e-10

@pytest.mark.parametrize('j',range(5))
def test_nan_not_zero(j):
    a=[.9,1.,2.,.1,.1];a[j]=np.nan;p=losses(*a);s,_=aggregate(p,W)
    assert all(np.isnan(v) for v in s.values())

def test_zero_measured_overlap():
    s,_=aggregate(losses(0,0,0,0,0),W)
    assert s['WQ_LS08']==0 and s['range_anchored_A']==0 and s['geometric_control']==0
    assert abs(s['arithmetic_candidate']-70)<1e-12

def test_invalid_not_repaired():
    for a in [(-.1,0,0,0,0),(1.1,0,0,0,0),(.9,-1,0,0,0)]:
        s,_=aggregate(losses(*a),W);assert all(np.isnan(v) for v in s.values())

def test_fixed_weights_validate():
    with pytest.raises(ValueError):aggregate(np.zeros(5),np.ones(5))

def test_range_bound():
    p=np.random.default_rng(1).lognormal(0,3,(10000,5));s,_=aggregate(p,W)
    assert np.all(s['range_anchored_A']<=100/(1+p[:,1])+1e-12)

def test_asymptotic_global_height_cap():
    p=np.zeros(5);p[4]=1e12;s,_=aggregate(p,W)
    assert abs(s['arithmetic_candidate']-95)<1e-8
    assert abs(s['range_anchored_A']-100*(1-1/14))<1e-8

def test_same_total_loss_different_ranking():
    p=np.array([[.8,0,0,0,0],[.4,.4,0,0,0]])
    s,_=aggregate(p,W);assert s['WQ_LS08'][0]==s['WQ_LS08'][1]
    assert s['arithmetic_candidate'][0]>s['arithmetic_candidate'][1]+10

def test_angles_square_and_winding():
    np.testing.assert_allclose(interior_angles(SQUARE),90)
    np.testing.assert_allclose(interior_angles(SQUARE[::-1]),90)

def test_concavity_preserved():
    a=np.array([[-1.5,-1.5],[1.5,-1.5],[1.5,.3],[.3,.3],[.3,1.5],[-1.5,1.5]])
    ang=interior_angles(a);assert np.sum(ang==270)==1 and np.sum(ang==90)==5

def test_collinear_subdivision_only():
    a=np.array([[-1.,-1.],[0.,-1.],[1.,-1.],[1.,1.],[-1.,1.]])
    np.testing.assert_allclose(simplify_collinear(a),SQUARE)
    a[1,1]-=.001;assert len(simplify_collinear(a))==5

def test_missing_correspondence_not_zero():
    assert matched_angle_error(SQUARE,SQUARE,None)['available'] is False

def test_partial_matching_reports_coverage():
    r=matched_angle_error(SQUARE,SQUARE,[(0,0),(1,1)])
    assert r['candidate_corner_coverage']==.5 and not r['complete_correspondence']

def test_duplicate_matching_rejected():
    with pytest.raises(ValueError):matched_angle_error(SQUARE,SQUARE,[(0,0),(1,0)])

def test_legal_nonorthogonal_reference_self():
    a=np.array([[-1.,-1.],[1.,-1.],[.5,1.],[-.5,1.]])
    assert direction_rms(a)>10
    r=matched_angle_error(a,a,list(zip(range(4),range(4))))
    assert r['matched_angle_rms_deg']==0

def test_rhombus_direction_aliasing_is_exposed_not_called_correct():
    def shape(theta):
        v=np.array([2*np.cos(np.deg2rad(theta)),2*np.sin(np.deg2rad(theta))]);u=np.array([2.,0.])
        a=np.array([[0.,0.],u,u+v,v]);return a-a.mean(axis=0)
    np.testing.assert_allclose(direction_rms(shape(45)),22.5,atol=1e-6)
    np.testing.assert_allclose(direction_rms(shape(1)),.5,atol=1e-6)
    r=matched_angle_error(shape(1),SQUARE,list(zip(range(4),range(4))))
    np.testing.assert_allclose(r['matched_angle_rms_deg'],89,atol=1e-6)

def test_real_replay_and_holds():
    d=pd.read_csv(ROOT/'results/per_case.csv');audit=json.loads((ROOT/'results/execution_audit.json').read_text())
    assert audit['execution_status_counts']=={'scored':331,'held_unchanged':92,'incomplete_quarantined':1}
    assert d.loc[d.execution_status!='scored','arithmetic_candidate'].isna().all()
    assert d.loc[d.execution_status=='scored','formula_replay_error'].abs().max()<1e-10
    assert not d.loc[d.execution_status=='scored','bound_key'].duplicated().any()

def test_no_unsupported_worker_ranks():
    d=pd.read_csv(ROOT/'results/worker_support_and_available_means.csv')
    assert d['WQ_LS08_rank'].isna().all()
