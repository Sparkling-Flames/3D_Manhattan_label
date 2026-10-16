import pandas as pd
import pytest

from tools.thesis_main.analysis.b8l2_d10_statistics_20261017 import validate_scores, dual_detail_tables, coverage_summaries


def scores():
    return pd.DataFrame(dict(object_id=['a','b'], pool_analysis_eligible=[True,False],
        quality_usable=[True,False], is_oos=[False,True], B8L2=[80.,None], D10=[81.,None]))


def test_denominators_and_oos_cannot_drift():
    frame=scores();validate_scores(frame,{'a','b'})
    with pytest.raises(AssertionError,match='inventory'):
        validate_scores(frame,{'a'})
    frame.loc[1,'D10']=70
    with pytest.raises(AssertionError,match='same score mask'):
        validate_scores(frame,{'a','b'})
    frame.loc[1,['B8L2','quality_usable']]=[69,True]
    with pytest.raises(AssertionError,match='OOS'):
        validate_scores(frame,{'a','b'})


def test_dual_tables_reuse_same_denominators_and_keep_target_time_missing():
    frame=scores().iloc[:1].copy()
    frame['B8L2_version']='B8';frame['D10_version']='D10';frame['diagnostic_B8L2']=80.
    frame['diagnostic_D10']=81.;frame['target_matched_time_seconds']=None
    def build(records,bundle,adoption=None):
        return {'sample':pd.DataFrame([dict(n=1,B8L2_mean=records.B8L2.mean(),
            quality_source_time_B8L2_mean=records.B8L2.mean(),
            target_matched_time_seconds_n=records.target_matched_time_seconds.notna().sum())])}
    out=dual_detail_tables(frame,{}, {}, builder=build)['sample'].iloc[0]
    assert out.B8L2_mean==80 and out.D10_mean==81
    assert out.quality_source_time_D10_mean==81
    assert out.target_matched_time_seconds_n==0 and out.n==1


def test_metric_view_cannot_change_a_nonmetric_denominator():
    frame=scores().iloc[:1].copy()
    frame['B8L2_version']='B8';frame['D10_version']='D10'
    frame['diagnostic_B8L2']=80.;frame['diagnostic_D10']=81.
    def build(records,bundle,adoption=None):
        return {'sample':pd.DataFrame([dict(n=int(records.B8L2.iloc[0]),B8L2_mean=1.)])}
    with pytest.raises(AssertionError):dual_detail_tables(frame,{}, {},builder=build)


def test_diagnostic_and_task_time_coverage_do_not_restore_quality_or_target_time():
    frame=scores()
    for column,value in dict(condition='manual',analysis_layer='ordinary_current',quality_use='not_qualified',
        worker_id='w',image_id='i',scene_bucket='neither_flagged',new_batch=True,
        cleaning_disposition='retained',calculation_status='full_computed',time_status='usable',
        time_rule_version='task-worker',time_binding='matched',target_time_interpretation='task_worker_total').items():
        frame[column]=value
    frame['diagnostic_B8L2']=[80.,60.];frame['diagnostic_D10']=[81.,61.]
    frame['source_active_time_seconds']=[10.,20.];frame['active_time_seconds']=[10.,None]
    frame['target_matched_time_seconds']=None
    frame['pool_analysis_exclusion_reasons']=[[],['OOS']]
    frame['quality_exclusion_reasons']=[[],['OOS']]
    out=coverage_summaries(frame)
    summary=out['exclusion_time_summary'].iloc[0]
    assert summary.n_inventory==2 and summary.n_quality==1 and summary.n_inventory_time==2
    assert summary.n_source_time==1 and summary.n_target_time==0
    assert summary.n_source_target_time_missing==1
    assert out['diagnostic_quality_stats'].iloc[0].B8L2_n==2
    assert out['diagnostic_quality_stats'].iloc[0].D10_n==2
    assert frame.B8L2.notna().sum()==1
