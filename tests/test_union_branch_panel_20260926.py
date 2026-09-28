import numpy as np

from tools.thesis_main.analysis.union_branch_panel_20260926 import PANEL, run


def test_user_selected_panel_keeps_unavailable_and_borrowed_votes_separate(tmp_path):
    result = run(tmp_path)
    assert {image['code'] for image in result['images']} == set(PANEL)
    assert result['counts']['accepted_annotations'] == 160
    assert result['counts']['primary_computable_annotations'] == 153
    assert result['counts']['primary_unavailable_annotations'] == 7
    records = [r for image in result['images'] for r in image['annotations']]
    assert all(r['source']['status'] == 'verified_against_raw_export' for r in records)
    for image in result['images']:
        assert image['default_order_user_confirmed'] is True
        assert image['formal_geometry_confirmation'] is False
        for record in image['annotations']:
            if record['core_record'] is not None:
                core = record['core_record']
                assert core['order_status'] == 'user_confirmed_default_order'
                assert np.allclose(core['pairs'], record['shared_x_pairs'])
                assert len(core['pairs']) == len(core['floor']) == len(core['heights'])
                assert core['independent_raw_vote'] is True
    borrowed = [r for r in records if r.get('revised_core_record') is not None]
    assert len(borrowed) == 1
    record = borrowed[0]
    assert record['worker_id'] == 'W031' and record['core_record'] is None
    assert record['reason'] == 'borrowed_point_not_independent_geometric_vote'
    assert record['revision_verification']['donor_worker'] == 'W033'
    assert record['revision_verification']['coordinates_verified'] is True
    assert record['revised_core_record']['independent_raw_vote'] is False
    assert record['revised_core_record']['use'] == 'full_sample_descriptive_sensitivity_only'
    refs = result['references_for_evaluation_only']
    assert sum(r['pairs'] is not None for image in refs for r in image['references']) == 15
    q9 = next(image for image in refs if image['code'] == 'q9vSo1VnCiC-04')
    revised = next(r for r in q9['references'] if r['name'] == 'gt_revised')
    assert revised['status'] == 'raw_verified_pairing_unconfirmed'
    assert revised['pairs'] is None
    assert result['selection']['uses_gt_scores'] is False
