"""Evidence inventory must not silently become a GT-error or admission list."""
from tools.thesis_main.analysis.collect_gt_revision_cases_20261031 import build


def test_collection_identity_and_evidence_boundaries():
    rows, images, checks = build()
    assert checks['unique_images'] == 89
    assert checks['entries'] == 125
    assert checks['manual_and_ceiling_image_overlap'] == 23
    assert checks['ceiling_30_match_release_geometry_and_version']
    assert len({r['entry_id'] for r in rows}) == 125
    assert all(not r['original_gt_error_established_by_this_collection'] for r in rows)
    assert all(not r['human_review_required_now'] for r in rows)
    manual = [r for r in rows if r['group'] == 'saved_manual_gt']
    assert all(len(r['detail']['saved_manual_points_1024x512']) >= 8 for r in manual)
    doors = {r['image']: r for r in rows if r['group'] == 'doorway'}
    assert doors['q9vSo1VnCiC-24']['status'] == 'user_kept_pending'
    assert doors['pRbA3pwrgk9-01']['detail']['space_polygons'] is None
    assert doors['q9vSo1VnCiC-13']['status'] == 'adopted_axis_binding_fixed'
    assert doors['2t7WUuJeko7-07']['status'] == 'user_reported_missing_corners'
    assert '旧保守矩形和紫色未分配连接段不再采用' in doors['7y3sRwLe3Va-18']['detail']['user_closeout']
    assert all('_no_occ' not in r['original_mp3d_points'] for r in images)
