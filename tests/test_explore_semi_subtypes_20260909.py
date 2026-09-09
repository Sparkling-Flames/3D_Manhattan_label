import numpy as np
import pandas as pd
from tools.thesis_main.analysis.explore_semi_subtypes_20260909 import semi_features, make_hierarchy


def test_semi_change_and_reference_gain_are_separate():
    a=[[20,100],[20,410],[400,100],[400,410]]
    b=[[25,100],[25,410],[400,100],[400,410]]
    unchanged=semi_features(a,a,a)
    assert unchanged['edit_ospa30']==0 and unchanged['gain_ospa30']==0
    improved=semi_features(b,a,a)
    assert improved['edit_ospa30']>0 and improved['gain_ospa30']>0
    assert semi_features(b,a,None)['gain_ospa30'] is None


def test_no_subgroup_with_only_one_member():
    ids=[str(i) for i in range(8)]
    manual=pd.DataFrame(dict(worker_id=ids,effect=np.arange(8),component='0',fit_status='usable'))
    semi=manual.copy();semi['effect']=[0,0,0,12,0,0,0,0]
    result=make_hierarchy(manual,semi)
    assert all(len(g)>=2 for _,g in result.groupby('fine_label'))
    assert result.manual_prediction.notna().all()
