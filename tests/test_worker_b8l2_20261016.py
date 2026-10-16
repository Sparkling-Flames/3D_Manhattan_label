import pandas as pd
import pytest
import json
from pathlib import Path

from tools.thesis_main.analysis.worker_b8l2_20261016 import (
    bind_admission, prediction_rows, primary_attempt, validate_ordinary_bridge, doorway_training_rows,
)


def test_admission_does_not_turn_missing_shared_holdout_into_training():
    scores = pd.DataFrame([dict(object_id='x', image_id='i', worker_id='W1', condition='manual',
                                original_holdout=None, role=None, quality_use='ordinary_primary')])
    gates = [dict(object_id='x', image_id='i', worker_id='W1', condition='manual',
                  original_holdout=True, role='held_or_diagnostic', personnel_barriers=[], context_barriers=['original_holdout'])]
    assert not bind_admission(scores, gates).iloc[0].profile_allowed
    gates[0]['worker_id'] = 'W2'
    with pytest.raises(ValueError, match='identity'):
        bind_admission(scores, gates)


def test_prediction_uses_only_training_effects_and_preserves_same_task_centering():
    fit = pd.DataFrame(dict(worker_id=['a','b','c','d'], effect=[-3.,-1.,1.,3.],
                            supported=[True]*4, label=['below_pool']*2+['above_pool']*2))
    test = pd.DataFrame(dict(object_id=list('abcd'), worker_id=list('abcd'),
                             building_id=['held']*4, context_key=['same']*4, Q=[100.,102.,104.,106.]))
    result = prediction_rows(test, fit, 'Q')
    assert result.continuous_sqerr.sum() == 0
    assert result['class_sqerr'].sum() == 4
    shifted = prediction_rows(test.assign(Q=test.Q+1000), fit, 'Q')
    assert result.target.tolist() == shifted.target.tolist()
    assert result.continuous_prediction.tolist() == shifted.continuous_prediction.tolist()


def test_team_attempt_gate_keeps_geometry_failures_but_not_holdouts_or_unbound_targets():
    im=dict(use='ordinary_conditional',source_pool={'pool_analysis_eligible':True},reference={'target_id':'target'})
    person=dict(quality_gate={'status':'candidate_pending_geometry'},worker_quality_gate='candidate_pending_geometry',
                legacy_personnel_barriers=[],original_holdout=False,binding=None)
    assert primary_attempt(im,[person])
    assert not primary_attempt(im,[dict(person,original_holdout=True)])
    assert not primary_attempt(im,[dict(person,binding={'chosen_target_id':'another'})])


def test_computable_oos_cannot_enter_quality_and_doorway_stays_separate():
    row=dict(object_id='x',image_id='i',worker_id='W1',condition='manual',quality_use='ordinary_primary',B8L2=99.)
    gate=dict(object_id='x',image_id='i',worker_id='W1',condition='manual',original_holdout=False,
              role='manual_development_candidate',personnel_barriers=[],context_barriers=[])
    assert bind_admission(pd.DataFrame([dict(row,scene='clear')]),[gate]).iloc[0].profile_allowed
    for scene in ['oos','doorway_annotatable','oos_and_doorway']:
        assert not bind_admission(pd.DataFrame([dict(row,scene=scene)]),[gate]).iloc[0].profile_allowed


def test_frozen_delivery_preserves_holdout_isolation_and_failed_team_denominators():
    root=Path(__file__).resolve().parents[1]/'research/workers/worker_b8l2_20261016'
    panel=pd.read_csv(root/'current_quality_panel.csv')
    assert len(panel)==949 and not panel.admission_original_holdout.any()
    audit=pd.read_csv(root/'score_admission_audit.csv')
    assert len(audit[audit.condition.eq('manual') & audit.quality_use.eq('ordinary_primary') & audit.admission_original_holdout])==188
    folds=pd.read_csv(root/'fold_profiles.csv')
    for r in folds[folds.fold.ne('full_descriptive')].itertuples():
        assert r.fold not in json.loads(r.training_buildings)
    teams=pd.read_csv(root/'team_scores.csv')
    assert teams.primary_attempt_eligible.sum()==399
    assert teams.primary_comparison_eligible.sum()==374
    failed=teams[teams.primary_attempt_eligible & teams.B8L2.isna()]
    assert len(failed)==25 and not failed.primary_comparison_eligible.any()
    pairs=pd.read_csv(root/'replacement_pairs.csv')
    assert len(pairs)==4076 and pairs.B8L2_change.notna().sum()<len(pairs)


def test_usage_bridge_rejects_changed_score_or_membership():
    row=dict(object_id='x',worker_id='w',image_id='i',condition='manual',reference_id='r',reference_version='v',
        input_version='input',B8L2_version='score',building_id='b',B8L2=70.,WQ=60.,IoU3D100=80.,
        iou_2d=.8,S_bottom_deg=1.,dir=2.,Hmean=.1,Hcenter=.2,
        source_active_time_seconds=10.,target_matched_time_seconds=None)
    old=pd.DataFrame([row]);new=old.copy()
    new.loc[0,'B8L2']+=1e-11
    assert validate_ordinary_bridge(old,new).B8L2_delta.abs().max()<1e-8
    new.loc[0,'B8L2']=71.
    with pytest.raises(ValueError,match='values changed'):validate_ordinary_bridge(old,new)
    with pytest.raises(ValueError,match='membership'):validate_ordinary_bridge(old,new.iloc[:0])


def test_doorway_quality_permission_does_not_release_holdout_or_oos():
    base=dict(quality_use='doorway_quality',quality_usable=True,is_doorway=True,is_oos=False,
        condition='manual',admission_original_holdout=False)
    rows=pd.DataFrame([dict(base,object_id='allowed'),dict(base,object_id='held',admission_original_holdout=True),
        dict(base,object_id='oos',is_oos=True),dict(base,object_id='unusable',quality_usable=False)])
    assert doorway_training_rows(rows).object_id.tolist()==['allowed']


def test_usage_v2_delivery_separates_doorway_holdouts_and_preserves_all_workers():
    root=Path(__file__).resolve().parents[1]/'research/workers/worker_b8l2_20261016'
    usage=root/'usage_v2'
    ledger=pd.read_csv(usage/'personnel_usage_ledger.csv')
    assert len(ledger)==3152 and ledger.worker_id.nunique()==27 and ledger.object_id.is_unique
    assert ledger.quality_usable.sum()==1787
    assert len(ledger[ledger.is_oos])==412
    assert not ledger.loc[ledger.is_oos,['ordinary_Q_profile','doorway_profile_training','quality_usable']].any().any()
    assert ledger.loc[ledger.is_oos,'B8L2'].isna().all()
    door=ledger[ledger.doorway_quality_evidence]
    ordinary_hold=ledger[ledger.quality_use.eq('ordinary_primary') & ledger.condition.eq('manual') & ledger.admission_original_holdout]
    assert len(door)==len(ordinary_hold)==188 and set(door.object_id).isdisjoint(ordinary_hold.object_id)
    assert door.admission_original_holdout.sum()==8 and ledger.doorway_profile_training.sum()==180
    assert not ledger.loc[ledger.doorway_profile_training,'admission_original_holdout'].any()
    ordinary=pd.read_csv(root/'current_quality_panel.csv')
    assert set(ordinary.object_id)==set(ledger.loc[ledger.ordinary_Q_profile,'object_id'])
    time=pd.read_csv(usage/'time_profile_bridge.csv')
    assert time.groupby('panel').size().to_dict()=={'T_source':682,'T_target':418}
    assert time.seconds_delta.abs().max()==0
    primary=pd.read_csv(usage/'worker_primary_reasons.csv')
    assert primary.n_records.sum()==3152
    folds=pd.read_csv(usage/'doorway_fold_profiles.csv')
    for r in folds[folds.fold.ne('full_descriptive')].itertuples():
        assert r.fold not in json.loads(r.training_buildings)
