import numpy as np
import pytest
from tools.thesis_main.analysis.analyze_v21_new_geometry_20261028 import core


def test_ratio_u_keeps_repeated_teams_and_invalid_attempts():
    method=core()
    # Two sampled paths coincide; a third differs; the fourth is invalid.
    d=np.array([[0,0,1,np.nan],[0,0,1,np.nan],[1,1,0,np.nan],[np.nan]*4])
    result,_=method.ustat(d)
    assert result['mean']==pytest.approx(2/3)
    assert result['valid_paths']==3 and result['attempted_paths']==4
    assert result['valid_pairs']==3
