import numpy as np
import pandas as pd
from tools.thesis_main.analysis.audit_population_precision_natural_20261025 import measures

def frame(q,failed,deferred,teams):
    return pd.DataFrame(dict(B8L2=q,D10=q,floor_turn5_n=4.,floor_redundant5_n=0.,nodes=4.,
      score_failure_nonpolicy=failed,incomplete_nonpolicy=failed,policy_deferred=deferred,team_key=teams))

def test_failure_denominator_excludes_deferred_but_preserves_failed():
    r=measures(frame([80.,np.nan,np.nan],[False,True,False],[False,False,True],['a','b','c']))
    assert r['Q_mean']==80 and r['failure_rate']==.5 and r['quality_valid_paths']==1
    assert np.isnan(r['Q_sd_ddof1']) and r['nondeferred_attempts']==2

def test_repeated_team_keeps_random_path_frequency():
    r=measures(frame([10.,10.,90.],[False]*3,[False]*3,['a','a','b']))
    assert np.isclose(r['Q_mean'],110/3) and r['unique_teams']==2 and r['paths_attempted']==3

def test_all_failed_has_missing_quality_not_zero():
    r=measures(frame([np.nan,np.nan],[True,True],[False,False],['a','b']))
    assert np.isnan(r['Q_mean']) and np.isnan(r['Q_p10']) and r['failure_rate']==1
