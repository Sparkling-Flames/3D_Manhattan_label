import numpy as np
import pandas as pd
from tools.thesis_main.analysis.same_room_structure_v21_20261108 import paired_identity,peer_center
from tools.thesis_main.analysis.same_room_local_features_20261021 import history_prediction

def test_identity_control_excludes_same_person_and_keeps_zero_variance():
    r=paired_identity([0,1],[0,1])
    assert r['same_person_abs_gap']==0 and r['other_person_abs_gap']==1
    assert r['same_person_exact']==1 and r['other_person_exact']==0
    assert np.isnan(paired_identity([4,4],[4,4])['spearman'])

def test_peer_mean_does_not_include_self_or_missing():
    d=pd.DataFrame({'image_id':['a','a','a','b'],'x':[1.,3.,np.nan,9.]})
    r=peer_center(d,'x')
    assert r.iloc[0]==-2 and r.iloc[1]==2 and r.iloc[2:].isna().all()

def test_local_history_uses_same_sources_and_excludes_target_and_self():
    d=pd.DataFrame({'worker_id':['a','b','a','b','b'],'image_code':['x','x','y','y','z'],'hit':[1,0,0,1,0]})
    assert history_prediction(d,'a','x')==(0.,1.,1)
    d.loc[d.image_code=='x','hit']=0
    assert history_prediction(d,'a','x')==(0.,1.,1)
