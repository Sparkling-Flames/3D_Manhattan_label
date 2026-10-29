import numpy as np
from tools.thesis_main.analysis.audit_v21_half_replacement_20261029 import flags

def test_gap_is_not_quality_loss():
    f=flags({'B8L2_gap':-2,'B8L2_CB':5,'geometry_bev_distance_gap':.1})
    assert f['amplitude_nonpositive'] and not f['quality_nonpositive']
    assert f['geometry_larger_despite_Q_gap']

def test_missing_is_not_negative():
    f=flags({'B8L2_gap':np.nan,'B8L2_CB':np.nan})
    assert f['missing_common_quality']
    assert not f['amplitude_nonpositive'] and not f['quality_nonpositive']
