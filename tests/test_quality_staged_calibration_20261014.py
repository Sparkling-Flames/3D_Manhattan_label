from tools.thesis_main.analysis import quality_staged_calibration_20261014 as q


def test_comparison_keeps_height_fixed_until_separate_global_step():
    configs=q.candidates(q.engine())
    assert configs['hill_same_height']['global_scale']==configs['current_tail']['global_scale']==1.
    assert configs['hill_global08']['global_scale']==.8
    assert all(c['local_scale']==.25 for c in configs.values())
    assert configs['no_direction_diagnostic']['direction_disabled'] is True


def test_missing_height_stays_unavailable_in_all_candidates():
    e=q.engine()
    for c in q.candidates(e).values():
        result=e['score'].score_metrics(dict(I=.8,Sb=1,D=2),c)
        assert result['score'] is None and result['floor_score'] is not None


def test_doorway_permission_never_overrides_worker_holdout_or_reference_holds():
    row=dict(condition='manual',original_holdout=False,personnel_barriers=['formal_gate:out_of_primary_scene'],
             context_barriers=['special_scene_separate_from_calibration:doorway_difficult'],
             available_reference_versions={'original':dict(object_id='gt',restrictions=[])})
    assert q.doorway_reference(row)[0]['object_id']=='gt'
    for change in (dict(original_holdout=True),dict(personnel_barriers=['formal_gate:hold_scene_or_reference']),
                   dict(context_barriers=['severe_screen:doorway_junction_deferred_by_user']),
                   dict(available_reference_versions={'a':dict(object_id='a',restrictions=[]),'b':dict(object_id='b',restrictions=[])}),
                   dict(available_reference_versions={'a':dict(object_id='a',restrictions=['scope_unresolved'])})):
        ref,reasons=q.doorway_reference(dict(row,**change))
        assert ref is None and reasons
