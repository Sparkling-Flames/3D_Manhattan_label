import copy

import pytest


def source(admitted=True):
    bundle = dict(data=dict(objects=[dict(object_kind='annotation', object_id='old', image_id='a', worker_id='W1', condition='manual')]))
    if admitted:
        new = dict(object_kind='annotation', object_id='new', image_id='b', worker_id='W2', condition='manual')
        bundle['data']['objects'].append(new)
        bundle['batch_admission'] = dict(version='batch1', records=[dict(new, source_id='ls98:1:2')],
            difficulty_records=[dict(image_id='b', current_class='中等')],
            reference_catalog=[dict(image_id='b', target_id='refb', current_target=True)])
    quality = [dict(object_id='old', image_id='a', worker_id='W1', condition='manual', quality_usable=True, B8L2=73)]
    binding = [dict(quality[0], chosen_target_id='refa', target_binding_unique=True)]
    return bundle, [dict(image_id='a')], [dict(image_id='a', target_id='refa', current_target=True)], quality, binding


def test_only_registered_increment_is_unscored_and_old_values_unchanged():
    from tools.thesis_main.analysis.current_annotation_context_20261017 import build_current_context
    args = source(); before = copy.deepcopy(args)
    result = build_current_context(*args)
    assert result['quality_records'][0] == args[3][0]
    new = result['quality_records'][1]
    assert new['quality_usable'] is False and new['B8L2'] is None
    assert new['full_score_state'] == 'pending_target' and new['calculation_status'] == 'pending_target'
    assert result['binding_records'][1]['target_binding_unique'] is False
    assert len(result['difficulty_records']) == len(result['reference_catalog']) == 2
    assert args == before


@pytest.mark.parametrize('change', ['unregistered', 'old_missing', 'identity_drift'])
def test_unknown_or_drifted_ids_are_rejected(change):
    from tools.thesis_main.analysis.current_annotation_context_20261017 import build_current_context
    args = list(source())
    if change == 'unregistered': args[0]['batch_admission']['records'] = []
    if change == 'old_missing': args[0]['data']['objects'].pop(0)
    if change == 'identity_drift': args[0]['batch_admission']['records'][0]['worker_id'] = 'other'
    with pytest.raises(ValueError): build_current_context(*args)


def test_no_batch_entrypoint_preserves_legacy_context():
    from tools.thesis_main.analysis.current_annotation_context_20261017 import build_current_context
    args = source(False)
    result = build_current_context(*args)
    assert result['quality_records'] == args[3]
    assert result['admitted_source_ids'] == []


def scored_source():
    bundle, difficulty, references, quality, bindings = source(False)
    quality[0].update(D10='75', B8L2='73', quality_usable='True', pool_analysis_eligible='True',
        is_oos='False', current_quality_eligible='True', rescore_target_id='refa')
    bindings[0].update(target_binding_unique='True')
    metadata=dict(version='quality_b8l2_d10_20261017_v2', primary_metric='B8L2', parallel_metric='D10',
                  counts=dict(inventory=1, quality_rows=1))
    return bundle, difficulty, references, quality, bindings, copy.deepcopy(quality), metadata


@pytest.mark.parametrize('version',['quality_b8l2_d10_20261017_v2','quality_workers_v2_20261019','quality_workers_v21_20261028'])
def test_shared_scores_use_complete_population_and_typed_binding_booleans(version):
    from tools.thesis_main.analysis.current_annotation_context_20261017 import build_scored_context
    args=scored_source();args[-1]['version']=version; before=copy.deepcopy(args)
    result=build_scored_context(*args)
    assert result['quality_records'][0]['B8L2']==73
    assert result['quality_records'][0]['D10']==75
    assert result['binding_records'][0]['target_binding_unique'] is True
    assert result['quality_records'][0]['is_oos'] is False
    assert args==before


@pytest.mark.parametrize('release,version',[('v2.1','quality_workers_v2_20261019'),('v2','quality_workers_v21_20261028'),('v1','quality_workers_v21_20261028')])
def test_explicit_score_context_cannot_cross_data_releases(tmp_path,release,version):
    import json
    from tools.thesis_main.analysis.current_annotation_context_20261017 import load_scored_context
    source=tmp_path/'context.json';source.write_text(json.dumps(dict(version=version)),encoding='utf8')
    with pytest.raises(ValueError,match='quality_data_release_mismatch'):
        load_scored_context(dict(manifest=dict(data_release=release)),source)


@pytest.mark.parametrize('change',['missing_id','identity','mask','oos','bool','binding','qualified','reference_image'])
def test_shared_score_drift_cannot_be_silently_displayed(change):
    from tools.thesis_main.analysis.current_annotation_context_20261017 import build_scored_context
    args=list(scored_source())
    if change=='missing_id':args[4]=[]
    if change=='identity':args[3][0]['worker_id']='other'
    if change=='mask':args[3][0]['D10']=''
    if change=='oos':args[3][0]['is_oos']='True'
    if change=='bool':args[4][0]['target_binding_unique']='false'
    if change=='binding':args[4][0]['target_binding_unique']='False'
    if change=='qualified':args[5]=[]
    if change=='reference_image':args[2][0]['image_id']='other'
    with pytest.raises(ValueError):build_scored_context(*args)
