import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.worker_reference_feasibility_20260909 import reference_metrics, choose_reference, cross_validate, pool_responses, ordinal_groups


def test_reference_priority_and_order_free_measurement():
    gt = {'reference_id': 'gt', 'points_1024x512': [[20, 100], [20, 410], [400, 100], [400, 410]]}
    corrected = dict(gt, reference_id='human')
    assert choose_reference(gt, corrected, None)['reference_id'] == 'human'
    assert choose_reference(gt, None, None)['basis'] == 'gt_assumed_correct'
    assert not choose_reference(gt, corrected, 'review_unresolved')['score_allowed']
    assert not choose_reference(gt, corrected, 'historical_review_reference_not_geometry_ready')['score_allowed']
    assert not choose_reference(None, None, None)['score_allowed']
    p = gt['points_1024x512']
    assert reference_metrics(p[::-1], p)['ospa30'] == pytest.approx(0, abs=1e-9)
    assert reference_metrics(p[:-1], p)['ospa30'] == pytest.approx(7.5)
    assert reference_metrics(p + [p[0]], p)['extra_count_rate'] == .25
    seam = [[0, 100], [0, 400]]
    assert reference_metrics([[1024, 400], [1024, 100]], seam)['ospa30'] == pytest.approx(0, abs=1e-9)
    with pytest.raises(ValueError):
        reference_metrics([], p)
    with pytest.raises(ValueError):
        reference_metrics([[-1, 100]], p)


def test_heldout_building_does_not_enter_worker_fit():
    rows = [dict(building_id=b, context_key=b, worker_id=w, value=10*i+j)
            for i,b in enumerate(['a','b','c']) for j,w in enumerate(['1','2','3'])]
    d = pd.DataFrame(rows)
    p, _ = cross_validate(d)
    assert np.max(p.continuous_sqerr) < 1e-20
    changed = d.copy()
    changed.loc[(changed.building_id=='a') & (changed.worker_id=='1'), 'value'] += 100
    q, _ = cross_validate(changed)
    assert np.allclose(p[p.building_id=='a'].continuous_prediction,
                       q[q.building_id=='a'].continuous_prediction)


def test_pooling_ignores_stage_condition_and_does_not_duplicate_person():
    d = pd.DataFrame([
        dict(image_id='a',building_id='b',worker_id='1',canonical_annotation_id='x',stage='P1',raw_condition='manual',current20_member='true',value=2),
        dict(image_id='a',building_id='b',worker_id='1',canonical_annotation_id='y',stage='C1',raw_condition='semi',current20_member='true',value=4),
        dict(image_id='a',building_id='b',worker_id='2',canonical_annotation_id='z',stage='other',raw_condition='oos',current20_member='false',value=1)])
    pooled = pool_responses(d,['value'])
    assert len(pooled)==2
    assert pooled.loc[pooled.worker_id=='1','value'].item()==3
    assert pooled.loc[pooled.worker_id=='1','response_count'].item()==2
    changed = d.assign(stage='anything',raw_condition='anything')
    pd.testing.assert_frame_equal(pooled,pool_responses(changed,['value']))


def test_ordinal_groups_preserve_ties_and_use_only_training_effects():
    p=pd.DataFrame(dict(worker_id=list('abcdef'),effect=[0.,0.,0.,2.,3.,4.],component='0'))
    g=ordinal_groups(p,3)
    assert g.iloc[:3].label.nunique()==1
    assert np.allclose(g.layer_value,g.groupby('label').effect.transform('mean'))
    flat=ordinal_groups(p.assign(effect=1.),5)
    assert flat.label.nunique()==1
    ward=ordinal_groups(p,3,'ward')
    assert ward.iloc[:3].label.nunique()==1
    assert ward.label.nunique()==3
    assert ordinal_groups(p.assign(effect=1.),5,'ward').label.nunique()==1
