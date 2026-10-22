import numpy as np
import pandas as pd
from tools.thesis_main.analysis.audit_personnel_mixture_20261022 import macro, variance_parts


def test_variance_parts_uses_member_weight_and_excludes_missing():
    total, within, between = variance_parts([0,2,10,np.nan], ['a','a','b','b'])
    np.testing.assert_allclose([total,within,between],[56/3,2/3,18])


def test_building_weight_is_not_event_weight():
    f=pd.DataFrame({'building':['a','a','a','b'],'image':['x','x','y','z'],'q':[0,0,6,12]})
    assert macro(f,['q']).q.mean()==7.5
