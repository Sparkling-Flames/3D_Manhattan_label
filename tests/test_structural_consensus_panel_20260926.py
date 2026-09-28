import json

import numpy as np

from tools.thesis_main.analysis.structural_consensus_panel_20260926 import annotation_record, run


def test_adapter_preserves_given_ring_and_coordinate_views(tmp_path):
    points = [[800, 150], [802, 360], [200, 140], [204, 370],
              [650, 130], [650, 380], [400, 140], [400, 370]]
    raw = {'id': 1, 'annotations': [{'id': 2, 'result': [
        {'type': 'keypointlabels', 'value': {'x': x / 1024 * 100, 'y': y / 512 * 100}}
        for x, y in points]}]}
    (tmp_path / 'one.json').write_text(json.dumps([raw]), encoding='utf8')
    row = dict(canonical_annotation_id='one', worker_id='W1', raw_condition='manual',
               raw_export_path='one.json', runtime_task_id=1, raw_annotation_id=2,
               raw_points_1024x512=points, effective_points_1024x512=points,
               links_zero_based=[[0, 1], [2, 3], [4, 5], [6, 7]],
               pairing_status='existing_accepted_pairing', processing_status='unchanged',
               imputed_point=False, accepted_before_new_review=True, known_wrong=False,
               stage='test', assistance_exposure='none')
    result = annotation_record(tmp_path, row, {}, None)
    assert result['status'] == 'conditional_existing_ring'
    assert np.allclose(result['raw_pairs'], np.array(points).reshape(4, 2, 2))
    assert np.allclose(np.array(result['shared_x_pairs'])[:, 0, 0], [801, 202, 650, 400])
    assert result['core_record']['order_status'] == 'existing_ring_unreviewed'
    assert result['core_record']['id'] == 'one'
    assert result['links_zero_based'] == row['links_zero_based']
    assert row['raw_points_1024x512'] == points


def test_panel_freezes_all_hold_images_and_preserves_unavailable_denominators(tmp_path):
    result = run(tmp_path)
    assert result['schema'] == 'structural_consensus_input_panel_20260926_v1'
    assert result['counts']['selected_images'] == 40
    assert result['counts']['accepted_annotations'] == 605
    assert result['counts']['strata_images']['doorway_hold'] == 18
    assert result['counts']['strata_images']['oos_hold'] == 18
    assert result['counts']['strata_images']['low_corner_count_control'] == 4
    assert all(r['source']['status'] == 'verified_against_raw_export'
               for image in result['images'] for r in image['annotations'])
    assert any(r['core_record'] is None for image in result['images'] for r in image['annotations'])
    assert all(not image['formal_geometry_confirmation'] for image in result['images'])
    assert {x['code'] for x in result['images']} >= {'B6ByNegPMKs-11', 'e9zR4mvMWw7-19', 'wc2JMjhGNzB-30'}
    assert len(result['references_for_evaluation_only']) == 40
    assert result['selection']['uses_gt_scores'] is False
    assert result['selection']['uses_new_algorithm_outputs'] is False
