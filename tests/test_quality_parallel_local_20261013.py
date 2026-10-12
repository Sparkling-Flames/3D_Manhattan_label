import pytest

from tools.thesis_main.analysis.quality_parallel_local_20261013 import NAMES, independent_score, personnel_reasons, raw_residual, worker_conditions


def test_missing_metric_is_not_zero_and_mixed_tail_is_distinct():
    m = dict(iou_2d=1., dir=0., S_bottom_deg=0., Hmean=.2, Hcenter=0.)
    assert independent_score(m, 'P_tied_quad08')['score'] == pytest.approx(100/1.0625)
    assert independent_score(m, 'P_tied_mix08')['score'] == pytest.approx(100/(1+.2*.4**2+.8*.4**4))
    m['Hcenter'] = None
    with pytest.raises(ValueError):
        independent_score(m, 'P_tied_quad08')


def test_worker_and_reference_gate_cannot_be_overridden_by_score():
    o = dict(worker_id='W019', worker_quality_gate='candidate_pending_geometry',
             cleaning_disposition='retained', independent_vote_eligible=True)
    r = dict(applicability_confirmed=True, pool='development907', gate={'new_descriptive_development_allowed': True, 'explicit_exposure_barriers': []})
    assert 'W019_calibration_only' in personnel_reasons(o, r, [], [], True)
    o['worker_id'] = 'W001'
    assert not personnel_reasons(o, r, [], [], True)
    assert 'current_input_or_reference_drift' in personnel_reasons(o, r, [], [], False)
    assert 'reference_excluded' in personnel_reasons(o, r, ['reference_excluded'], [], True)


def test_raw_diagnostic_uses_current_pairs_and_periodic_seam():
    o = dict(before_preprocessing_points=[[1022,100],[2,400]], links_zero_based=[[0,1]])
    assert raw_residual(o)['X_max_deg'] == pytest.approx(4*360/1024)
    o['links_zero_based'] = []
    assert raw_residual(o)['X_max_deg'] is None


def test_conditional_workers_do_not_mix_conditions_or_single_person_images():
    def row(w, image, condition, score):
        return dict(worker_id=w,image_id=image,reference_id='ref',condition=condition,
                    building_id='building',record_id=w+image+condition,
                    conditional_personnel_eligible=True,scores={n:score for n in NAMES},
                    raw_input={'X_rms_deg':0.})
    result=worker_conditions([row('A','one','manual',20),row('B','one','manual',40),
                              row('A','one','semi',100),row('A','two','manual',100)])
    assert len(result['cells'])==2
    assert result['workers'][0]['results'][NAMES[0]]['mean_within_cell_difference']==-10
    assert result['workers'][0]['results'][NAMES[0]]['leave_one_building_range'] is None
