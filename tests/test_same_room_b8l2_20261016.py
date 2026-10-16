import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_b8l2_20261016 import (
    paired_values, confirmed_relation,
    verify_original_scores,
)


def test_pair_mean_and_person_difference_use_identical_workers():
    a=pd.DataFrame({'worker_id':['a','b','only_a'],'B8L2':[90.,50.,0.]})
    b=pd.DataFrame({'worker_id':['a','b','only_b'],'B8L2':[50.,90.,100.]})
    result,people=paired_values(a,b,'B8L2')
    assert result['n_common_workers']==2 and result['n_paired']==2
    assert result['absolute_mean_gap']==0
    assert result['mean_absolute_person_delta']==40
    assert list(people.index)==['a','b']
    missing,_=paired_values(a,b.assign(worker_id=['x','y','z']),'B8L2')
    assert missing['n_common_workers']==0 and missing['n_paired']==0 and missing['mean_a'] is None


def test_missing_time_is_not_zero_and_units_stay_seconds():
    a=pd.DataFrame({'worker_id':['a','b'],'source_time_seconds':[10.,np.nan]})
    b=pd.DataFrame({'worker_id':['a','b'],'source_time_seconds':[20.,100.]})
    result,people=paired_values(a,b,'source_time_seconds')
    assert result['n_common_workers']==2 and result['n_paired']==1
    assert result['mean_a']==10 and result['mean_b']==20
    assert result['geometric_time_ratio_b_over_a']==pytest.approx(2)
    assert result['mean_absolute_log_time_ratio']==pytest.approx(np.log(2))
    a.loc[0,'source_time_seconds']=0
    with pytest.raises(ValueError,match='positive'):
        paired_values(a,b,'source_time_seconds')


def test_physical_confirmation_and_scope_comparability_stay_separate():
    comparable=dict(tier='confirmed_comparable',evidence=[dict(physical_same_supported=True,review_state='explicit_confirmed')])
    other=dict(tier='supported_other',evidence=[dict(physical_same_supported=True,review_state='explicit_confirmed')])
    pending=dict(tier='supported_other',evidence=[dict(physical_same_supported=True,review_state='explicit_discussion')])
    assert confirmed_relation(comparable)=='confirmed_comparable'
    assert confirmed_relation(other)=='confirmed_other_scope'
    assert confirmed_relation(pending)=='not_explicitly_confirmed'


def test_duplicate_worker_cannot_become_two_votes_or_time_samples():
    a=pd.DataFrame({'worker_id':['a','a'],'B8L2':[80.,90.]})
    b=pd.DataFrame({'worker_id':['a'],'B8L2':[70.]})
    with pytest.raises(ValueError,match='duplicate'):
        paired_values(a,b,'B8L2')


def test_score_rounding_interval_accepts_export_precision_but_rejects_real_change():
    from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
    values=[.85963074253,2.60191081783,3.03892155123,.07849889707,.07178600329]
    fields=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
    with scoring_engine() as (engine,models):
        score=float(models.score(*values,params=models.B))
        row=pd.DataFrame([dict(object_id='x',B8L2=round(score,10),**dict(zip(fields,[round(v,10) for v in values])))])
        assert verify_original_scores(row,models).within_rounding_interval.all()
        row['B8L2']+=.001
        with pytest.raises(ValueError,match='outside'):
            verify_original_scores(row,models)
