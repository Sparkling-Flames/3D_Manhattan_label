from copy import deepcopy

import pandas as pd

from tools.thesis_main.analysis.scope_quality_rescore_20261016 import integrate_scores, QUALITY_METRICS


def test_complete_reference_never_overrides_person_pool_or_target_gates():
    rows = [dict(object_id=str(i), pool_analysis_eligible=i != 1,
        current_quality_eligible=False, target_matched_time_seconds=None,
        **{m: None for m in QUALITY_METRICS}) for i in range(4)]
    affected = [dict(object_id=str(i), chosen_target_id='old' if i == 3 else 'new',
        person_quality_restriction_clear=i != 2, pool_analysis_eligible=i != 1,
        binding_status='sole_admitted_space') for i in range(4)]
    scores = [dict(object_id=str(i), score_status='complete', score_versions={'WQ':'frozen'},
        **{m: 70. for m in QUALITY_METRICS}) for i in range(4)]
    refs = [dict(target_id='new', current_target=True, reference_version='v2'),
        dict(target_id='old', current_target=False, reference_version='v1')]
    before = deepcopy(scores)
    result = integrate_scores(pd.DataFrame(rows), affected, scores, refs)
    assert result.current_quality_eligible.tolist() == [True, False, False, False]
    assert result.WQ.notna().tolist() == [True, False, False, False]
    assert result.target_matched_time_seconds.isna().all()
    assert scores == before


def test_missing_binding_and_missing_score_stay_missing():
    audit = pd.DataFrame([dict(object_id='a', pool_analysis_eligible=True,
        current_quality_eligible=False, **{m: None for m in QUALITY_METRICS})])
    affected = [dict(object_id='a', chosen_target_id='', binding_status='pending_multiple_admitted_spaces',
        person_quality_restriction_clear=True, pool_analysis_eligible=True)]
    result = integrate_scores(audit, affected, [], [])
    assert not result.current_quality_eligible.any()
    assert result.WQ.isna().all()
    assert result.rescore_status.iloc[0] == 'pending_multiple_admitted_spaces'
