from __future__ import annotations

import numpy as np
import pytest

from tools.thesis_main.analysis import materialize_annotation_research_prework_statistics_20260905 as mod
from tools.thesis_main.data_prep import materialize_annotation_research_prework_evidence_20260905 as evidence


def _rows():
    return [
        {"worker_id": "1", "base_task_id": "A_1", "building_id": "A", "analysis_value": 1.0},
        {"worker_id": "2", "base_task_id": "A_1", "building_id": "A", "analysis_value": 2.0},
        {"worker_id": "1", "base_task_id": "B_1", "building_id": "B", "analysis_value": 2.0},
        {"worker_id": "2", "base_task_id": "B_1", "building_id": "B", "analysis_value": 3.0},
    ]


def test_components_and_centered_effects():
    assert len(mod.worker_task_components(_rows())) == 1
    effects = mod.fit_worker_task_effects(_rows())
    assert set(effects) == {"1", "2"}
    assert abs(sum(effects.values())) < 1e-12
    assert effects[2 if 2 in effects else "2"] > effects[1 if 1 in effects else "1"]


def test_bootstrap_keeps_exact_draw_count_without_rejection():
    _, diagnostics = mod.bootstrap_component(_rows(), replicates=25, seed=1)
    assert len(diagnostics) == 25
    assert {row["status"] for row in diagnostics} <= {
        "usable", "missing_workers", "disconnected_graph", "insufficient_task_support", "estimator_not_evaluable"
    }


def test_resample_uses_duplicate_instance_task_ids():
    sampled = mod.resample_building_then_task(_rows(), np.random.default_rng(2))
    assert sampled
    assert all(str(row["base_task_id"]).startswith("b") for row in sampled)


def test_field_contract_prohibits_zero_imputation_and_full_target_medoid():
    assert "never zero" in mod.FIELD_CONTRACT["missing_rule"].replace("_", " ")
    assert "selected_only_medoid" in mod.FIELD_CONTRACT["replay_rule"]


def test_medoid_selection_cannot_see_remaining_worker():
    dense = lambda top: (np.asarray([top, top]), np.asarray([top + 2, top + 2]))
    selected = [
        {"canonical_annotation_id": "a", "dense": dense(0)},
        {"canonical_annotation_id": "b", "dense": dense(1)},
        {"canonical_annotation_id": "c", "dense": dense(8)},
    ]
    before = mod.medoid_selected_only(selected)["canonical_annotation_id"]
    # An arbitrarily close remaining record cannot change a medoid selected from the selected set.
    remaining = {"canonical_annotation_id": "z", "dense": dense(8)}
    after = mod.medoid_selected_only(selected)["canonical_annotation_id"]
    assert before == after
    assert remaining["canonical_annotation_id"] != before


def test_real_medoid_pipeline_and_matrix_match_without_heldout_leakage():
    def record(name, top):
        return {'canonical_annotation_id':name,'worker_id':name,'dense':(np.array([top]*4), np.array([top+10]*4))}
    records = [record('a',0),record('b',1),record('c',7),record('d',8)]
    first = mod.evaluate_indices(records, mod.distance_matrix(records), [0,1,2])
    direct = mod._evaluate_medoid(records[:3], records)
    assert first['selected_medoid_id'] == direct['selected_medoid_id']
    assert first['remaining_d_mask_mean'] == pytest.approx(direct['remaining_d_mask_mean'])
    records[3] = record('d',300)
    second = mod.evaluate_indices(records,mod.distance_matrix(records),[0,1,2])
    assert first['selected_medoid_id'] == second['selected_medoid_id']
    assert first['remaining_d_mask_mean'] != second['remaining_d_mask_mean']
    with pytest.raises(ValueError,match='duplicate worker'):
        mod.distance_matrix([records[0],records[0]])
    with pytest.raises(ValueError,match='repeated'):
        mod.evaluate_indices(records,mod.distance_matrix(records),[0,0])
    assert mod.strict_medoid_replay({('P1','manual','A_x'):records}) == ([],[])


def test_task_elimination_equals_full_design_and_disconnected_is_not_ranked():
    rows = _rows() + [{'worker_id':'3','base_task_id':'B_1','building_id':'B','analysis_value':5.}]
    workers,tasks = ['1','2','3'],['A_1','B_1']
    design = np.zeros((len(rows),5))
    for i,r in enumerate(rows):
        design[i,workers.index(r['worker_id'])]=1
        design[i,3+tasks.index(r['base_task_id'])]=1
    direct = np.linalg.lstsq(design,np.array([r['analysis_value'] for r in rows]),rcond=None)[0][:3]
    direct -= direct.mean()
    assert list(mod.fit_worker_task_effects(rows).values()) == pytest.approx(direct)
    disconnected = rows + [{'worker_id':'4','base_task_id':'C_1','building_id':'C','analysis_value':0.}]
    assert len(mod.worker_task_components(disconnected)) == 2
    assert mod.fit_worker_task_effects(disconnected) == {}


def test_time_sources_partial_coverage_and_duplicate_identity():
    row = {'active_time_seconds':'30','active_time_source':'log','timing_status':'eligible_partial_session_coverage',
           'historical_active_time_eligibility_status':'eligible','active_time_formal_available':'True'}
    assert not mod.eligible_active_time_row(row)
    assert evidence.time_status(row).startswith('partial')
    row.update(timing_status='project+task+annotator',active_time_source='lead_time_fallback')
    assert evidence.time_status(row) == 'lead_time_only_not_active'
    row.update(active_time_source='log',active_time_seconds='0')
    assert not mod.eligible_active_time_row(row)
    with pytest.raises(ValueError,match='duplicate'):
        evidence.unique_index([{'canonical_annotation_id':'x'},{'canonical_annotation_id':'x'}])


def test_no_stable_label_from_missing_draws_ties_or_single_building():
    assert mod.classify_from_counts(1,1,1000,.8)[0].startswith('U_')
    assert mod.classify_from_counts(mod.positive_mass([0.]*1000),1000,1000,.8)[0].startswith('U_')
    assert mod.classify_from_counts(1000,1000,1000,.8,single_building=True)[0].startswith('U_')
    assert evidence.split_overlap({'A','B'},{'B','C'})['overlap_ids'] == ['B']
    assert evidence.parse_layout_split(['A pano1','B_pano2.jpg']) == {'A_pano1','B_pano2'}


def test_geometry_incompatibility_and_training_leakage_fail_closed():
    a = mod.audit_v1.normalize_geometry([[0,100],[0,400],[500,100],[500,400]])
    b = mod.audit_v1.normalize_geometry([[0,100],[0,400],[300,100],[300,400],[700,100],[700,400]])
    assert not mod.pairwise_similarity(a,b)['pointwise_correspondence_compatible']
    assert mod.cyclic_rmse([[0,100],[0,400]],[[0,100],[0,400],[500,100],[500,400]]) is None
    row = dict(status='evaluated',feature_name='d_mask_to_reference',threshold=.8,evaluation_kind='heldout_task_fold',
               training_task_ids_json='["A"]',evaluation_task_ids_json='["A"]')
    with pytest.raises(ValueError,match='leakage'):
        mod.group_replay({},[row])


def test_singleton_heldout_peer_is_not_zero_quality_and_peer_center_matches():
    import json
    common = dict(stage='P1',condition='manual',reference_source_version='ref',feature_name='quality')
    train = [dict(common, worker_id=w,train_continuous_effect=value,train_component_id='0',evaluation_kind='task',fold_id='1',
                  evaluation_task_ids_json=json.dumps(['A','B']),directional_class='H_positive_direction',status='evaluated')
             for w,value in [('1',1.),('2',3.),('3',2.)]]
    feature = [dict(common,worker_id='1',base_task_id='A',analysis_value=10.),dict(common,worker_id='2',base_task_id='A',analysis_value=12.),
               dict(common,worker_id='3',base_task_id='B',analysis_value=99.)]
    result=mod.refine_holdout_peer_support(train,feature)
    assert result[0]['train_prediction_same_heldout_peer_center']==-1
    assert result[0]['continuous_absolute_error']==0
    assert result[2]['status']=='not_evaluable_no_same_component_peer'
    assert result[2]['heldout_task_centered_mean']==''
