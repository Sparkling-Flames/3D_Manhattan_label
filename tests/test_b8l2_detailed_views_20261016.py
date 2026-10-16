import pandas as pd
import pytest

from tools.thesis_main.analysis.b8l2_detail_summary_20261016 import summarize_group


def test_view_weighting_and_quality_time_intersections_are_not_pooled_or_filled():
    data=pd.DataFrame([
        dict(object_id='a',image_id='i1',worker_id='w1',condition='manual',pool_analysis_eligible=True,
             B8L2=20.,active_time_seconds=10.,target_matched_time_seconds=None),
        dict(object_id='b',image_id='i1',worker_id='w2',condition='manual',pool_analysis_eligible=True,
             B8L2=40.,active_time_seconds=None,target_matched_time_seconds=None),
        dict(object_id='c',image_id='i2',worker_id='w1',condition='manual',pool_analysis_eligible=True,
             B8L2=90.,active_time_seconds=40.,target_matched_time_seconds=40.),
        dict(object_id='d',image_id='i2',worker_id='w3',condition='manual',pool_analysis_eligible=False,
             B8L2=None,active_time_seconds=None,target_matched_time_seconds=None)])
    out=summarize_group(data)
    assert out['B8L2_mean']==50
    assert out['B8L2_image_equal_mean']==60
    assert out['B8L2_sd']==pytest.approx(pd.Series([20.,40.,90.]).std())
    assert out['quality_source_time_n']==2 and out['quality_target_time_n']==1
    assert out['quality_source_time_B8L2_mean']==55
    assert out['target_matched_time_seconds_mean']==40
    assert out['target_matched_time_seconds_sd'] is None
    assert out['n_inventory_workers']==3 and out['n_source_workers']==2
    assert out['n_excluded_records']==1


def test_empty_cells_remain_missing_and_conditions_cannot_be_mixed():
    empty=pd.DataFrame(columns=['object_id','image_id','worker_id','condition','pool_analysis_eligible',
        'B8L2','active_time_seconds','target_matched_time_seconds'])
    empty['pool_analysis_eligible']=empty.pool_analysis_eligible.astype(bool)
    out=summarize_group(empty)
    assert out['B8L2_n']==0 and out['B8L2_mean'] is None
    assert out['quality_target_time_n']==0
    data=pd.concat([empty,pd.DataFrame([dict(condition='manual'),dict(condition='semi')])])
    with pytest.raises(AssertionError,match='conditions'):
        summarize_group(data)


def test_inventory_overview_keeps_nonanalyzed_people_without_restoring_their_time():
    from tools.thesis_main.analysis.b8l2_detailed_views_20261016 import inventory_overview
    rows=pd.DataFrame([dict(worker_id='accepted',image_id='i',condition='manual',
        pool_analysis_eligible=True,pool_analysis_exclusion_reasons=[],quality_exclusion_reasons=[],
        B8L2=80.,source_active_time_seconds=10.,active_time_seconds=10.,target_matched_time_seconds=10.),
        dict(worker_id='held',image_id='i',condition='manual',pool_analysis_eligible=False,
        pool_analysis_exclusion_reasons=['historical_not_accepted'],quality_exclusion_reasons=['held'],
        B8L2=None,source_active_time_seconds=100.,active_time_seconds=None,target_matched_time_seconds=None)])
    out=inventory_overview(rows,'worker_id').set_index('worker_id')
    assert set(out.index)=={'accepted','held'}
    assert out.loc['held','n_inventory_usable_time']==1
    assert out.loc['held','n_source_time']==0 and out.loc['held','n_source_records']==0
    assert out.loc['held','quality_manual']==0
    assert out.loc['held','source_exclusion_reasons']==['historical_not_accepted']
    assert 'B8L2_mean' not in out
