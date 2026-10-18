import pandas as pd
from tools.thesis_main.analysis.difficulty_doorway_v1_20261017 import panel_summary


def test_fixed_opportunity_denominator_keeps_failed_and_diagnostic_nodes():
    nodes=pd.DataFrame([
        dict(pool_id='a',k=3,path_id='random_0',complete_evaluable=True,main_comparison_allowed=True,
             B8L2=60.,D10=62.,R_union_normalized=.2,source_time_available=True,source_active_seconds=100.,subset='x'),
        dict(pool_id='a',k=3,path_id='random_1',complete_evaluable=False,main_comparison_allowed=True,
             B8L2=None,D10=None,R_union_normalized=.4,source_time_available=False,source_active_seconds=None,subset='y'),
        dict(pool_id='b',k=3,path_id='random_0',complete_evaluable=True,main_comparison_allowed=False,
             B8L2=99.,D10=99.,R_union_normalized=.1,source_time_available=False,source_active_seconds=None,subset='z'),
    ])
    stability=pd.DataFrame([dict(pool_id='a',k=3,path_a='random_0',path_b='random_1',
        same_subset=False,both_complete_floor=False,floor_jaccard_difference=None)])
    result=panel_summary(nodes,stability)
    assert result['opportunities']==3 and result['complete']==2 and result['quality']==1
    assert result['B8L2_image_equal_mean']==60 and result['time_n']==1
    assert result['V_pairs']==0 and pd.isna(result['V_image_equal_mean'])
