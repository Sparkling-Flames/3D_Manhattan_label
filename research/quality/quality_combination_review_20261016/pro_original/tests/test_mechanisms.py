import sys,json,math
from pathlib import Path
import numpy as np,pandas as pd,pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from mechanisms import *

@pytest.mark.parametrize('model',[m.name for m in MODELS])
def test_anchors_and_monotone(model):
    assert float(score(1,0,0,0,0,model))==100
    assert float(score(0,3,2,.1,.2,model))==0
    x=np.linspace(.001,1,1000)
    np.testing.assert_allclose(score(x,0,0,0,0,model),100*x,rtol=1e-13)
    q=score(.85,1,4,.1,.05,model)
    assert score(.84,1,4,.1,.05,model)<=q
    for i in range(1,5):
        v=[.85,1,4,.1,.05];v[i]+=.1
        assert score(*v,model)<=q+1e-12
    assert 0<=q<=85

@pytest.mark.parametrize('model',[m.name for m in MODELS])
def test_missing_height_is_not_zero(model):
    with pytest.raises(ValueError):score(.9,1,1,float('nan'),0,model)
    with pytest.raises(ValueError):score(.9,1,1,.1,float('nan'),model)
    with pytest.raises(ValueError):score(1.01,0,0,0,0,model)

@pytest.mark.parametrize('kind,p',[('sum',0),('l2',0),('ordered',LAMBDA),('max',0),('lp',1.5),('lp',3),('mixed',.25)])
def test_pool_axioms(kind,p):
    rng=np.random.default_rng(123);a=rng.uniform(0,8,10000);b=rng.uniform(0,2,10000)
    m=pool(a,b,kind,p)
    assert np.all(m>=np.maximum(a,b)-1e-12)
    assert np.all(m<=a+b+1e-12)
    np.testing.assert_allclose(pool(a,np.zeros_like(a),kind,p),a,rtol=1e-13)
    np.testing.assert_allclose(pool(3*a,3*b,kind,p),3*m,rtol=1e-13)
    np.testing.assert_allclose(pool(a,b,kind,p),pool(b,a,kind,p),rtol=1e-13)

def test_matched_diagonal_and_non_equivalence():
    t=np.linspace(0,10,101)
    np.testing.assert_allclose(pool(t,t,'ordered',LAMBDA),pool(t,t,'l2'))
    assert pool(1,.1,'ordered',LAMBDA)>pool(1,.1,'l2')

def test_loss_and_score_bounds():
    f,d=np.meshgrid(np.logspace(-4,2,511),np.linspace(0,1.5,511))
    b=np.hypot(f,d);c=np.maximum(f,d)+LAMBDA*np.minimum(f,d)
    assert np.all(c>=b-1e-12)
    assert np.max(c/b)<=math.sqrt(1+LAMBDA**2)+1e-12
    assert np.max(100/(1+b)-100/(1+c))<=1.97908135060
    assert np.max(100/(1+b)-100/(1+f+d))<=8.64272337260

def test_aggregation_changes_height_cost():
    f,d,h=.5,.5,.5
    db=100/(1+math.hypot(f,d))-100/(1+math.hypot(f,d)+h)
    ds=100/(1+f+d)-100/(1+f+d+h)
    assert db>ds

def test_finite_ablation_and_local_derivative_are_different():
    f,d,h=.1,1.,0.
    qb=100/(1+math.hypot(f,d));qs=100/(1+f+d)
    assert 100/(1+f)-qb<100/(1+f)-qs
    assert 100*d/math.hypot(f,d)/(1+math.hypot(f,d))**2>100/(1+f+d)**2

def test_remeasured_data_and_inherited_keys():
    e=json.load(open(ROOT/'results/EXECUTION.json'))
    assert e['baseline_scores_rows']==1145 and e['physical_controls']==72
    assert e['geometry_remeasured_answers']==30 and e['fusion_full_rows']==144
    p=pd.read_csv(ROOT/'results/GEOMETRY_PARITY_30.csv').filter(like='abs_error_')
    assert p.max().max()<1e-8
    s=pd.read_csv(ROOT/'results/SCORES_1145.csv')
    old=pd.read_csv(ROOT/'inputs/handoff/prior_AB/results/SCORES_1145.csv')
    for k in ['record_id','object_id','reference_id','comparison_layer','original_holdout','same_target_quality_hold','personnel_barriers','context_barriers']:
        pd.testing.assert_series_equal(s[k],old[k])
    np.testing.assert_allclose(s.B8L2,old.Q_B8L2,atol=1e-11)
    np.testing.assert_allclose(s.Q_gain_scale_shapley+s.Q_gain_pool_shapley,s.B8L2-s.WQ,atol=1e-11)

def test_exposure_and_verbatim_preservation():
    h=ROOT/'inputs/handoff';raw=json.load(open(h/'quality_ab_human_review_20261015_v1.json'))
    f=pd.read_csv(ROOT/'results/FEEDBACK_30_ALL_RECORDS_AND_RAW_COMMENTS.csv').fillna('')
    assert len(f)==30 and sum(f.pre_grade_available)==23 and sum(f.changed_after_first_reveal)==6
    for row in f.to_dict('records'):
        r=raw['decisions'][row['case_id']]
        assert row['comment']==r.get('comment','')
        assert row['final_grade']==r['grade']
        assert row['first_reveal_grade']==(r.get('grade_at_first_score_reveal') or '')
        assert row['reference_id']==r['bindings'][0]['reference_object_id']

def test_fourfold_height_and_structural_limit_retained():
    c=pd.read_csv(ROOT/'results/PHYSICAL_CONTROLS.csv').set_index('case')
    assert abs(c.loc['height_4','B8L2']-6.6390041493776)<1e-9
    assert c.loc['branch_omission_0.1','B8L2']>98
    assert c.loc['nonorthogonal_self_0.05','B8L2']<100
    b=c.loc[[f'subdivision_{i}' for i in [0,1,3,10,100]],'B8L2']
    assert max(b)-min(b)<1e-8

def test_fusion_no_new_records():
    e=json.load(open(ROOT/'results/EXECUTION.json'))
    assert e['fusion_total_status_rows']==220 and e['fusion_paired_units']==12
    assert not e['new_model_fit_to_current_ratings'] and not e['production_default_changed']
