import pandas as pd
import json
import pytest

from tools.thesis_main.analysis.descriptive_statistics_current_20261015 import apply_metric_gates, QUALITY_METRICS


def test_pool_and_reference_and_legacy_rules_are_all_required():
    row=dict(pool_analysis_eligible=True,reuse_full_quality=True,role='manual_development_candidate',
        same_target_quality_hold=False,latest_step_reference_pending=False,original_holdout=False,
        same_target_unconfirmed=False,new_space_target=False,target_role='selected_gt',active_time_seconds=30.)
    row.update({metric:50. for metric in QUALITY_METRICS})
    data=pd.DataFrame([row,{**row,'pool_analysis_eligible':False},
        {**row,'reuse_full_quality':False,'new_space_target':True,'target_role':'confirmed_scope'},
        {**row,'same_target_unconfirmed':True}])
    result=apply_metric_gates(data)
    assert result.current_quality_eligible.tolist()==[True,False,False,False]
    assert result.WQ.notna().tolist()==[True,False,False,False]
    assert result.historical_WQ.eq(50).all()
    assert result.active_time_seconds.notna().tolist()==[True,False,True,True]
    assert pd.isna(result.iloc[2].target_matched_time_seconds)


def test_changed_policy_cannot_overwrite_an_existing_snapshot(tmp_path):
    from tools.thesis_main.analysis.descriptive_statistics_current_20261015 import write
    (tmp_path/'FIELD_CONTRACT.json').write_text(json.dumps(dict(difficulty_version='old',pool_rule_version='old')))
    with pytest.raises(ValueError,match='new snapshot'):
        write({},dict(difficulty_version='new',source_pool_rule='new'),tmp_path)


def test_rebuild_uses_updated_scores_eligibility_and_exact_reference_cells(monkeypatch):
    from tools.thesis_main.analysis import descriptive_statistics_current_20261015 as module
    rows=[]
    for i, score in enumerate([40.,80.,100.,None]):
        row=dict(object_id=f'O{i}',image_id='I1',image_code='I-1',worker_id=f'W{i}',condition='manual',
            reference_id='new_reference' if i==0 else 'old_reference',building_id='B1',
            pool_analysis_eligible=i<3,ordinary_difficulty_eligible=i<3,current_quality_eligible=i<3,
            pool_source_workers=3,pool_analysis_exclusion_reasons=[],reference_audit_reasons=[],
            legacy_quality_restriction_clear=True,difficulty_class='easy',scene='ordinary',
            doorway_status='none',oos_subtype='not_oos',score_version='frozen',use_panel='ordinary_current',
            active_time_seconds=30. if i<3 else None,target_matched_time_seconds=30. if i<3 else None)
        row.update({key:score for key in module.QUALITY_METRICS})
        rows.append(row)
    captured=[]
    def same_room(records):
        captured.extend(records)
        return dict(same_room_relations=[],same_room_pair_metrics=[],same_room_worker_pairs=[])
    monkeypatch.setattr(module,'build_same_room_tables',same_room)
    tables=dict(record_audit=pd.DataFrame(rows),source_pools=pd.DataFrame([dict(condition='manual',
        image_id='I1',n_effective_workers=3,n_annotation_records=4,pool_analysis_eligible=True,
        ordinary_difficulty_eligible=True,pool_exclusion_reasons=[])]),
        historical_panel_changes=pd.DataFrame(dict(object_id=[f'O{i}' for i in range(4)],
            historical_target_836=[False,True,True,True],historical_worker_931=[True]*4)))
    original=tables['record_audit'].copy(deep=True)
    assert module.rebuild_metric_tables(tables) is None
    pd.testing.assert_frame_equal(tables['record_audit'],original)
    assert tables['analysis_records'].object_id.tolist()==['O0','O1','O2']
    summary=tables['overview'].set_index('metric').loc['WQ']
    assert summary['n_valid']==3
    assert summary['mean']==pytest.approx(220/3)
    peers=tables['peer_comparisons'].query("metric=='WQ'").set_index('object_id')
    assert peers.loc['O0','n_peers']==0
    assert peers.loc['O0','reference_id']=='new_reference'
    assert peers.loc['O1','difference']==-20
    assert peers.loc['O2','difference']==20
    assert captured[0]['reference_id']=='new_reference'
    assert captured[0]['WQ']==40
    assert tables['historical_panel_changes'].target_panel_change.tolist()==['added','retained','retained','removed']
    first=tables['historical_panel_changes'].copy(deep=True)
    module.rebuild_metric_tables(tables)
    pd.testing.assert_frame_equal(tables['historical_panel_changes'],first)
