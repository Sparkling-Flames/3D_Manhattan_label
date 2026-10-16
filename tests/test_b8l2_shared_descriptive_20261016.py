import pandas as pd

from tools.thesis_main.analysis.b8l2_shared_descriptive_20261016 import add_b8l2_descriptive_tables
from tools.thesis_main.analysis.descriptive_statistics_current_20261015 import QUALITY_METRICS


def test_shared_descriptions_preserve_missing_time_and_do_not_invent_member_change_reasons():
    rows=[]
    for i in [1,2]:
        row=dict(object_id=f'O{i}',image_id='I1',image_code='I-1',worker_id=f'W{i}',condition='manual',
            analysis_layer='ordinary_current',difficulty_class='medium',reference_id='new',
            time_status='usable' if i==1 else 'unfrozen',target_time_interpretation='not_established',
            active_time_seconds=20. if i==1 else None,target_matched_time_seconds=None)
        row.update({metric:float(i*20) for metric in QUALITY_METRICS})
        rows.append(row)
    analysis=pd.DataFrame(rows)
    changes=pd.DataFrame(dict(object_id=['O1'],reason=['explicit_source_reason']))
    tables=dict(analysis_records=analysis,quality_records=analysis.copy(),member_changes=changes)
    add_b8l2_descriptive_tables(tables)
    assert tables['b8l2_image_overview'].iloc[0].B8L2_mean==30
    assert tables['time_coverage'].n_source_time.sum()==1
    assert tables['time_coverage'].n_target_time.sum()==0
    assert tables['time_coverage'].n_quality_target_time.sum()==0
    pd.testing.assert_frame_equal(tables['member_changes'],changes)
    assert analysis.reference_id.eq('new').all()
