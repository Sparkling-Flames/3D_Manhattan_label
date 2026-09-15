"""Focused numerical and provenance tests; no original images required."""
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import Ridge
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import OUT,GRADES,ANCHOR,classify,scope_collapse,read
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict import center_scale,grid,CONFIGS
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people import clusters,stats,dmask

@pytest.mark.parametrize('x',['oos_geometry','oos_open_boundary','oos_split_level','oos_insufficient','out_of_scope'])
def test_scope_subtypes_are_one(x):assert scope_collapse(x)=='oos'

def test_scope_normal_and_missing():
    assert scope_collapse('normal')=='in_scope'
    assert scope_collapse(None)=='unknown'

def test_invalid_not_easy_or_hard():
    grade,status=classify(24,1,1,0,1,1,0,1,False)
    assert grade=='' and status=='invalid_response_evidence'

def test_three_people_not_full_tier():assert classify(3,0,1,0,1,1,0,1,False)[0]==''

def test_eight_people_may_be_early():assert classify(8,0,1,0,.9,.9,0,.9,False,k=8)[0]=='simple'

def test_cumulative_medium_not_interval_concentration():
    args=(15,0,2,0,.45,.9,.45,.9,False)
    assert classify(*args,medium='cumulative')[0]=='medium'
    assert classify(*args,medium='interval')[0]!='medium'

def test_stable_many_not_hard():
    grade,status=classify(24,0,5,0,.1,.9,.8,.9,False)
    assert grade=='' and status=='stable_outside_three_tier_limits'

def test_singletons_alone_not_difficult():assert classify(20,0,4,.4,0,0,0,0,False)[0]!='difficult_candidate'

def test_fragmentation_and_actual_change_are_candidate():assert classify(20,0,4,.4,0,0,0,0,True)[0]=='difficult_candidate'

def test_point_counts_never_merge():
    dm=np.zeros((4,4));lab=clusters(dm,np.array([8,8,10,10]),.1)
    assert lab[0]==lab[1] and lab[2]==lab[3] and lab[0]!=lab[2]

def test_support_requires_two_people():
    dm=np.array([[0,.01,2],[.01,0,2],[2,2,0.]])
    st=stats(dm,np.array([8,8,10]),clusters(dm,np.array([8,8,10]),.1))
    assert st['n_supported_modes']==1 and st['singleton_mass']==pytest.approx(1/3)

def test_geometry_identical_zero():
    a=np.array([[0,0,0],[10,10,10]])
    assert dmask(a,a)==0

def test_kernel_ridge_equivalent_to_explicit_training_scaling():
    rng=np.random.default_rng(42);X=rng.normal(size=(10,7));X/=np.linalg.norm(X,axis=1)[:,None]
    tr=np.arange(7);te=np.arange(7,10);Y=rng.uniform(.2,.8,size=(10,1));K=center_scale(X@X.T,tr)
    mu=X[tr].mean(0);Z=X-mu;Z/=np.sqrt(np.mean(np.sum(Z[tr]**2,axis=1)))
    fitted=Ridge(alpha=10).fit(Z[tr],Y[tr]).predict(Z[te]);n=next(j for j,c in enumerate(CONFIGS) if c==dict(algorithm='ridge',pca=None,parameter=10.))
    np.testing.assert_allclose(grid(K,Y,tr,te)[n],np.clip(fitted,0,1),atol=1e-8)

def test_test_labels_do_not_change_predictions():
    rng=np.random.default_rng(6);X=rng.normal(size=(9,4));Y=rng.random((9,2));tr=np.arange(6);te=np.arange(6,9);K=center_scale(X@X.T,tr)
    a=grid(K,Y,tr,te);Y[te]=100;b=grid(K,Y,tr,te);np.testing.assert_allclose(a,b)

def test_test_features_do_not_change_training_kernel():
    rng=np.random.default_rng(7);X=rng.normal(size=(9,4));tr=np.arange(6);a=center_scale(X@X.T,tr);X[6:]*=100;b=center_scale(X@X.T,tr);np.testing.assert_allclose(a[np.ix_(tr,tr)],b[np.ix_(tr,tr)])

def test_ordinal_probabilities_ordered():
    rng=np.random.default_rng(8);X=rng.normal(size=(8,3));Y=rng.random((8,2));tr=np.arange(6);te=np.arange(6,8);p=grid(center_scale(X@X.T,tr),Y,tr,te,True)
    assert np.all(p[...,0]>=p[...,1]) and np.all((p>=0)&(p<=1))

def test_source_metadata_has_no_difficulty_or_human_outcomes():
    p=OUT/'inputs/image_metadata_whitelist.csv'
    if not p.exists():pytest.skip('input preparation not yet executed')
    cols=pd.read_csv(p,nrows=0).columns
    assert not any('difficulty' in x or x in ['n_valid','quality','grade','onset','selection_display_group'] for x in cols)

def test_205_actual_arrays_each_model():
    p=OUT/'C/model_array_read_audit.csv'
    if not p.exists():pytest.skip('model extraction not yet executed')
    d=pd.read_csv(p);assert d.groupby('model').image_id.nunique().to_dict()=={m:205 for m in ['hohonet','bilayout','ulayout','dinov3','da3']}
    assert (d.bytes_read>0).all() and d.sha256.str.len().eq(64).all()

def test_expert_tags_remain_independent():
    p=OUT/'expert/independent_tags106.csv'
    if not p.exists():pytest.skip('inputs not yet executed')
    d=pd.read_csv(p);assert d.expert_tag.value_counts().to_dict()=={'简单':49,'中等':41,'困难':16}

def test_real_people_not_duplicated():
    p=OUT/'inputs/response_metrics_sanitized.csv.gz'
    if not p.exists():pytest.skip('inputs not yet executed')
    d=pd.read_csv(p);assert not d.duplicated(['image_id','raw_condition','worker_id']).any()
    assert not d.loc[d.main_worker_included,'worker_id'].isin(['W019','W026']).any()
    assert 'W011' in set(d.loc[d.main_worker_included,'worker_id'])
