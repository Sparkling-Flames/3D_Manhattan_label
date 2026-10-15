import copy

from tools.thesis_main.analysis import descriptive_reference_audit_20261015 as audit


def fixture(monkeypatch):
    points = [[128, 150], [128, 350], [384, 150], [384, 350],
              [640, 150], [640, 350], [896, 150], [896, 350]]
    worker = dict(object_id='o', image_id='i', worker_id='w', condition='manual', points_1024x512=points)
    reference = dict(object_id='ref', image_id='i', points_1024x512=points)
    data = dict(objects=[worker, reference])
    bundle = dict(data=copy.deepcopy(data))
    monkeypatch.setattr(audit, 'load_scoring_snapshot', lambda: data)
    monkeypatch.setattr(audit, 'scope_sources', lambda b: {})
    difficulty = dict(image='code', image_id='i', target_version='ref', current_class='简单',
                      selected=dict(target_id='ref', role='selected_gt', floor=audit.floor(points).tolist()),
                      top_boundary_pending=False, gt_error_excluded=False, difficulty_analysis_eligible=True)
    old = dict(object_id='o', image_id='i', worker_id='w', condition='manual', reference_id='ref',
               WQ='20', A10='21', B8L2='22', IoU3D100='23')
    return bundle, [difficulty], [old]


def test_full_unchanged_reference_reuses_and_same_id_floor_change_does_not(monkeypatch):
    bundle, difficulty, old = fixture(monkeypatch)
    images, bindings = audit.audit_references(bundle, difficulty, old)
    assert bindings[0]['reuse_full_quality']
    difficulty[0]['selected']['floor'][0][0] += 1
    assert not audit.audit_references(bundle, difficulty, old)[1][0]['reuse_full_quality']


def test_same_floor_without_top_is_not_complete(monkeypatch):
    bundle, difficulty, old = fixture(monkeypatch)
    difficulty[0]['selected']['role'] = 'confirmed_scope'
    difficulty[0]['top_boundary_pending'] = True
    binding = audit.audit_references(bundle, difficulty, old)[1][0]
    assert binding['target_floor_relation'] == 'same_vertices'
    assert not binding['full_reference_compatible']
    assert not binding['reuse_full_quality']
    assert 'top_geometry_pending' in binding['reasons']


def test_input_coordinate_drift_requires_rescore(monkeypatch):
    bundle, difficulty, old = fixture(monkeypatch)
    bundle['data']['objects'][0]['points_1024x512'][0][0] += 1
    row = audit.audit_references(bundle, difficulty, old)[1][0]
    assert not row['input_geometry_unchanged'] and not row['reuse_full_quality']
    assert 'annotation_geometry_changed_or_missing' in row['reasons']


def test_known_gt_error_has_priority_and_revision_is_not_old_reference(monkeypatch):
    bundle, difficulty, old = fixture(monkeypatch)
    difficulty[0]['gt_error_excluded'] = True
    assert audit.audit_references(bundle, difficulty, old)[1][0]['quality_audit_status'] == 'excluded_gt_error'
    difficulty[0]['gt_error_excluded'] = False
    difficulty[0]['selected']['role'] = 'user_revised_gt'
    difficulty[0]['target_version'] = 'revised'
    difficulty[0]['selected']['target_id'] = 'revised'
    assert not audit.audit_references(bundle, difficulty, old)[1][0]['reuse_full_quality']
