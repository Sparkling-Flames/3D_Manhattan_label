import copy

import pytest

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle


@pytest.fixture(scope='module')
def bundle():
    return load_current_bundle('analysis_results/research_input_20260929/manifest.json')


def inputs(worker='W001', image_id='test_building_new'):
    points = [[10, 30], [10, 70], [40, 25], [40, 75], [75, 30], [75, 70]]
    source_id = 'ls98:9991:9992'
    record = dict(source_id=source_id, project_id=98, task_id=9991, annotation_id=9992,
                  source_file='export_label/test.json', completed_by=1,
                  image_id=image_id, image_code='test-01', raw_keypoints=points,
                  scope_response='in_scope', condition='manual',
                  review=dict(source_id=source_id, raw_keypoints=copy.deepcopy(points),
                              filter='keep', order_confirmed=True, order=[2, 0, 1], note='', updated_at=''))
    batch = dict(records=[record], images=[dict(image_id=image_id, image_code='test-01',
                 building_id='test_building', gt_original=dict(source='data/test.txt',
                 points_1024x512=[[x*10.24, y*5.12] for x, y in points]))])
    mapping = dict(source_project=98, identity_confirmed=True,
                   mappings=[dict(source_account_id='1', worker_id=worker, identity_confirmed=True)])
    return batch, {source_id: [[0, 1], [2, 3], [4, 5]]}, mapping


def test_increment_preserves_old_objects_and_validates(bundle):
    from tools.thesis_main.data_prep.admit_annotation_batch_20261017 import apply_bundle
    batch, pairs, mapping = inputs()
    result = apply_bundle(bundle, batch, pairs, mapping)
    n = len(bundle['data']['objects'])
    assert result['data']['objects'][:n] == bundle['data']['objects']
    assert len(result['data']['objects']) == n+2
    assert result['comments'] == bundle['comments']
    ann = next(o for o in result['data']['objects'] if o['object_id'] == 'new_98_9991_9992_W001')
    assert ann['ordered_source_point_indices'] == [4, 5, 0, 1, 2, 3]
    assert ann['independent_vote_eligible'] is True
    assert ann['order_record']['note'] == ''
    assert result['validation']['status'] == 'passed'
    assert result['research']['summary']['annotations'] == 3153
    assert result['data'] is not bundle['data']


@pytest.mark.parametrize('failure', ['missing_pairs', 'reused_point', 'raw_drift', 'unconfirmed_order'])
def test_rejects_unbound_or_incomplete_pairing(bundle, failure):
    from tools.thesis_main.data_prep.admit_annotation_batch_20261017 import apply_bundle
    batch, pairs, mapping = inputs()
    key = batch['records'][0]['source_id']
    if failure == 'missing_pairs': pairs.clear()
    if failure == 'reused_point': pairs[key] = [[0, 1], [2, 3], [4, 3]]
    if failure == 'raw_drift': batch['records'][0]['review']['raw_keypoints'][0][0] += 1
    if failure == 'unconfirmed_order': batch['records'][0]['review']['order_confirmed'] = False
    with pytest.raises(ValueError): apply_bundle(bundle, batch, pairs, mapping)


def test_existing_exclusion_and_prior_exposure_not_restored(bundle):
    from tools.thesis_main.data_prep.admit_annotation_batch_20261017 import apply_bundle
    batch, pairs, mapping = inputs(worker='W019')
    result = apply_bundle(bundle, batch, pairs, mapping)
    ann = next(o for o in result['data']['objects'] if o['object_id'] == 'new_98_9991_9992_W019')
    assert ann['worker_quality_gate'] == 'excluded'
    assert ann['independent_vote_eligible'] is False
    existing = next(o for o in bundle['data']['objects'] if o.get('worker_id') == 'W001')
    batch, pairs, mapping = inputs(image_id=existing['image_id'])
    batch['records'][0]['image_code'] = existing['image_code']
    batch['images'] = []
    result = apply_bundle(bundle, batch, pairs, mapping)
    ann = next(o for o in result['data']['objects'] if o['object_id'] == 'new_98_9991_9992_W001')
    assert 'prior_exposure_not_new_independent_vote' in ann['independent_vote_reasons']
    assert ann['cleaning_disposition'] == 'retained_pending'
