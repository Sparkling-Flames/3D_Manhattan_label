import pandas as pd
import pytest
import json
from pathlib import Path

from tools.thesis_main.analysis.worker_b8l2_d10_20261017 import review_new_record, source_time_value


def test_new_scores_do_not_release_existing_image_holdout():
    history=pd.DataFrame([dict(image_id='i',building_id='b',original_holdout=True)])
    row=dict(image_id='i',building_id='b',quality_usable=True)
    held,reason=review_new_record(row,history)
    assert held is True and reason=='inherited_same_image_holdout'
    held,reason=review_new_record(dict(row,image_id='new'),history)
    assert held is None and reason=='new_image_in_mixed_or_held_building_pending'


def test_new_image_development_requires_absence_of_historical_building_holdout():
    history=pd.DataFrame([dict(image_id='i',building_id='b',original_holdout=False)])
    held,reason=review_new_record(dict(image_id='new',building_id='b'),history)
    assert held is False and reason=='new_image_in_nonheld_building_development'


def test_task_worker_time_never_becomes_target_time():
    row=dict(task_worker_active_seconds=103.,source_active_time_seconds=103.,target_matched_time_seconds=None,
        time_source='active_log_v10_admitted',time_rule_version='session_max_then_sum_v10_task_worker')
    assert source_time_value(row)==pytest.approx(4.644390899)
    with pytest.raises(ValueError,match='target'):
        source_time_value(dict(row,target_matched_time_seconds=103.))
    with pytest.raises(ValueError,match='source'):
        source_time_value(dict(row,source_active_time_seconds=104.))


def test_frozen_v2_panel_is_paired_and_preserves_holdouts_and_time_scope():
    root=Path(__file__).resolve().parents[1]/'research/workers/worker_b8l2_d10_20261017'
    d=pd.read_csv(root/'personnel_ledger.csv');q=d[d.in_Q_training]
    assert len(d)==3222 and len(q)==1048 and q.new_batch.sum()==41
    assert not q.admission_original_holdout.any() and not q.is_oos.any()
    assert len(d[d.new_batch & d.quality_usable & d.admission_original_holdout])==22
    assert d.loc[d.new_batch,'target_matched_time_seconds'].isna().all()
    assert d.loc[d.new_batch,'task_worker_active_seconds'].sum()==5205
    preds=pd.read_csv(root/'predictions.csv')
    for _,g in preds[preds.axis.isin(['B8L2','D10'])].groupby(['panel','comparison']):
        assert set(g.loc[g.axis.eq('B8L2'),'object_id'])==set(g.loc[g.axis.eq('D10'),'object_id'])
    folds=pd.read_csv(root/'fold_profiles.csv')
    for r in folds[folds.fold.ne('full_descriptive')].itertuples():
        assert r.fold not in json.loads(r.training_buildings)
    counts=pd.read_csv(root/'worker_usage_summary.csv')
    assert len(counts)==27 and counts.n_submissions.sum()==3222
