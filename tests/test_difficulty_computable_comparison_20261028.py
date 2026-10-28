import numpy as np
import pandas as pd
from tools.thesis_main.analysis.difficulty_computable_comparison_20261028 import matrix, fit_predict, aggregate, losses


def sample():
    return pd.DataFrame(dict(worker_id=['a','a','b','b'],source=['old']*4,
        difficulty=['简单','中等','简单','困难'],image_id=['i1','i2','i1','i2'],
        ref_turn5=[4.,6.,4.,6.],y=[0.,1.,0.,1.]))


def test_training_scaling_and_unknown_worker():
    train=sample(); test=train.iloc[:1].copy();test['worker_id']='unseen';test['ref_turn5']=100.
    x,z,names=matrix(train,test,'turn_only',np.ones(4))
    assert z[0,names.index('ref_turn5')]==95.
    assert z[0,names.index('worker_id:a')]==0
    assert z[0,names.index('worker_id:b')]==0
    np.testing.assert_allclose(x[:,-1],[-1,1,-1,1])


def test_test_response_never_used_and_identical_image_duplication():
    train=sample(); test=train.iloc[:1].copy()
    p,_,_=fit_predict(train,test,'y','three')
    test['y']=999
    q,_,_=fit_predict(train,test,'y','three')
    np.testing.assert_allclose(p,q)
    doubled=pd.concat([train,train[train.image_id.eq('i1')]],ignore_index=True)
    q,_,_=fit_predict(doubled,test,'y','three')
    np.testing.assert_allclose(p,q)


def test_image_then_building_equal_loss():
    p=pd.DataFrame(dict(outcome=['y']*4,model=['m']*4,building=['A','A','A','B'],
        image_id=['a','a','b','c'],prediction=[0,0,2,4],observed=[0]*4))
    _,b,s=aggregate(losses(p))
    assert b.set_index('building').loc['A','mae']==1
    assert s.mae.iloc[0]==2.5
