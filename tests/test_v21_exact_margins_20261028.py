import pandas as pd
import pytest
from tools.thesis_main.analysis.build_v21_exact_margins_20261028 import summarize


def test_finite_distribution_preserves_missing_and_population_sd():
    data=pd.DataFrame(dict(team_key=['a','b','c'],k=[1]*3,B8L2=[0.,10.,None],D10=[0.,10.,None],
        floor_turn5_n=[4,4,None],floor_redundant5_n=[0,0,None],nodes=[4,4,0],complete_evaluable=[True,True,False]))
    r=summarize(data,dict(pool_n=3))
    assert r['Q_mean']==5 and r['Q_sd_population']==5
    assert r['Q_p10']==1 and r['Q_p10_inverse_cdf']==0
    assert r['quality_valid_teams']==2 and r['failure_rate']==pytest.approx(1/3)
    data['status_class']=['scoreable','scoreable','output_unscoreable']
    r=summarize(data,dict(pool_n=3))
    assert r['actual_consensus_failure_rate']==0
    assert r['output_unscoreable_rate']==pytest.approx(1/3)
    with pytest.raises(AssertionError):summarize(data.iloc[:2],dict(pool_n=3))
