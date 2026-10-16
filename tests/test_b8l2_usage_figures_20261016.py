import pandas as pd
import pytest

from tools.thesis_main.analysis.b8l2_usage_figures_20261016 import plot_inputs


def test_worker_coverage_has_exclusive_denominator_and_rejects_oos_quality():
    frame=pd.DataFrame([
        dict(object_id='a',worker_id='w',is_oos=False,quality_usable=True,diagnostic_B8L2=80.,
             B8L2=80.,WQ=81.,A10=82.,IoU3D100=90.,calculation_status='full_computed'),
        dict(object_id='b',worker_id='w',is_oos=True,quality_usable=False,diagnostic_B8L2=99.,
             B8L2=None,WQ=None,A10=None,IoU3D100=None,calculation_status='full_computed'),
        dict(object_id='c',worker_id='held',is_oos=False,quality_usable=False,diagnostic_B8L2=None,
             B8L2=None,WQ=None,A10=None,IoU3D100=None,calculation_status='pending_target')])
    coverage=plot_inputs(frame).set_index('worker_id')
    assert coverage.loc['w','n']==2 and coverage.loc['w','quality']==1
    assert coverage.loc['w','oos_diagnostic']==1
    assert coverage.loc['held','no_full_score']==1
    frame.loc[1,'B8L2']=99.
    with pytest.raises(AssertionError):
        plot_inputs(frame)
