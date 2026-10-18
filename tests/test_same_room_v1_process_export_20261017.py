import numpy as np
import pandas as pd

from tools.thesis_main.analysis.same_room_v1_process_export_20261017 import consumer_masks


def test_diagnostic_design_cannot_be_promoted_by_an_eligible_prefix():
    trace=pd.DataFrame(dict(request_id=['diagnostic','primary','primary'],execution_status=['observed']*3,
        main_comparison_allowed=[True]*3,complete_evaluable=[True,False,True],
        order_status=['source_suggestion','two_person_sorting_deferred','source_suggestion'],
        comparison_B8L2=[np.nan,np.nan,0.],comparison_D10=[np.nan,np.nan,0.]))
    reasons={'diagnostic':'diagnostic_mixed_bound_targets','primary':'primary_design'}
    out=consumer_masks(trace,reasons)
    assert out.primary_quality_available.tolist()==[False,False,True]
    assert out.primary_quality_eligible.tolist()==[False,True,True]
    assert out.primary_mask_reason.tolist()==['diagnostic_mixed_bound_targets','two_person_sorting_deferred','primary_quality_available']
    assert out.loc[2,'comparison_B8L2']==0.


def test_missing_execution_is_distinct_from_geometric_failure():
    trace=pd.DataFrame(dict(request_id=['p'],execution_status=['not_run'],
        main_comparison_allowed=[np.nan],complete_evaluable=[np.nan],order_status=[np.nan],
        comparison_B8L2=[np.nan],comparison_D10=[np.nan]))
    out=consumer_masks(trace,{'p':'primary_design'})
    assert out.primary_mask_reason.tolist()==['not_received']
    assert not out.primary_quality_available.any()
