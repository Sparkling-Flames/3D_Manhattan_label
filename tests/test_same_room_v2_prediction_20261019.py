import pandas as pd
import numpy as np
from tools.thesis_main.analysis.same_room_v2_prediction_20261019 import scene_layer, worker_baseline, fit_transfer, balanced_weights
from tools.thesis_main.analysis.same_room_v2_prediction_20261019 import features


def test_oos_overrides_doorway_and_doorway_stays_separate():
    d=pd.DataFrame({'is_oos':[True,False,False],'is_doorway':[True,True,False]})
    assert scene_layer(d).tolist()==['excluded_oos','doorway','ordinary']


def test_baseline_cannot_read_held_out_building_and_keeps_cold_start():
    d=pd.DataFrame({'building':['A','B','C'],'worker_id':['w','w','x'],'value':[999.,10.,20.]})
    means,counts,pop=worker_baseline(d,{'A'})
    assert means['w']==10 and counts['w']==1 and pop==15
    assert 'new_worker' not in means


def test_transfer_fit_accepts_actual_series_and_recovers_linear_relation():
    x=np.array([0.,1.,2.]);y=2+3*x
    coefficient=fit_transfer(pd.Series(x),pd.Series(y),pd.Series(np.ones(3)))
    assert np.allclose(coefficient,[2.,3.])


def test_more_people_or_direct_pairs_do_not_increase_building_weight():
    d=pd.DataFrame(dict(building=['a','a','a','b'],source_image=['1','1','2','3'],target_image=['2','2','1','4'],worker_id=['x','y','x','z']))
    assert np.allclose(balanced_weights(d).groupby(d.building).sum(),[1.,1.])


def test_source_features_ignore_target_outcomes_and_peer_feature_excludes_predicted_worker():
    workers=['a','b','c','d','e']
    records=pd.DataFrame(dict(building=['train']*5,worker_id=workers,value=[10.]*5))
    edges=pd.DataFrame(dict(building=['held']*5,source_image=['s']*5,target_image=['t']*5,
        worker_id=workers,pair_id=[0]*5,calibration_training_allowed=[True]*5,
        source_value=[99.,20.,30.,40.,50.],actual=[1.,2.,3.,4.,5.]))
    first=features(edges,records,'held',[4])
    edges['actual']=999.
    second=features(edges,records,'held',[4])
    pd.testing.assert_series_equal(first.feature,second.feature)
    peer=first[first.worker_id.eq('a')&first['mode'].eq('other_source_people')]
    assert len(peer)==3 and np.allclose(peer.feature,25.)
