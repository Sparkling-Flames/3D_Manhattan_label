import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_update_20261017 import prepare_panel, metric_sensitivity


def panel():
    return pd.DataFrame(dict(object_id=['old','new','oos'], image_id=['i','i','o'],
        worker_id=['a','b','c'], condition=['manual']*3, pool_analysis_eligible=[True]*3,
        quality_usable=[True,True,False], is_oos=[False,False,True],
        B8L2=[70.,80.,np.nan], D10=[72.,81.,np.nan], diagnostic_B8L2=[70.,80.,99.],
        active_time_seconds=[10.,20.,30.], source_active_time_seconds=[10.,20.,30.],
        target_matched_time_seconds=[10.,np.nan,np.nan], time_status=['usable']*3,
        time_source=['active_log','active_log_v10_admitted','active_log'], time_source_file=['audit']*3,
        target_time_interpretation=['audited_target','task_worker_total_not_target_specific','unknown']))


def test_new_source_time_survives_without_fabricating_target_time_or_oos_quality():
    result=prepare_panel(panel())
    assert result.source_time_seconds.tolist()==[10.,20.,30.]
    assert pd.isna(result.loc[1,'target_matched_time_seconds'])
    assert pd.isna(result.loc[2,'B8L2']) and result.loc[2,'diagnostic_B8L2']==99.
    wrong=panel();wrong.loc[1,'target_matched_time_seconds']=20.
    with pytest.raises(ValueError,match='target time'):
        prepare_panel(wrong)


def test_b8l2_and_d10_must_share_quality_eligibility():
    wrong=panel();wrong.loc[1,'D10']=np.nan
    with pytest.raises(ValueError,match='same qualified'):
        prepare_panel(wrong)
    wrong=panel();wrong.loc[2,['B8L2','D10']]=[99.,99.]
    with pytest.raises(ValueError,match='excluded'):
        prepare_panel(wrong)


def test_metric_gap_change_is_only_compared_on_identical_workers():
    pairs=pd.DataFrame(dict(image_a=['a','a'],image_b=['b','b'],condition=['manual']*2,
        metric=['B8L2','D10'],paired_workers=['x|y','x|y'],n_paired=[2,2],
        absolute_mean_gap=[4.,5.],mean_absolute_person_delta=[9.,10.]))
    result=metric_sensitivity(pairs)
    assert result.gap_change_D10_minus_B8L2.iloc[0]==1.
    pairs.loc[1,'paired_workers']='x|z'
    with pytest.raises(ValueError,match='workers'):
        metric_sensitivity(pairs)
