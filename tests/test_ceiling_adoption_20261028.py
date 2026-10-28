import json
import numpy as np
import pytest
from tools.thesis_main.analysis.adopt_ceiling_review_20261028 import BASE, OUT, adjust
from tools.thesis_main.analysis.orthogonal_scope_references_20261028 import geometry, points_for


def test_representative_group_mean_uses_both_rays_and_ignores_distant_heights():
    p = points_for(np.array([[-1,-2],[3,-2],[3,4],[-1,4]]), [1,1.0001,1.00005,1.1])
    result, info = adjust(p, 'adopt_majority_height_plane', '1')
    assert info['averaged_pairs_1based'] == [1,2,3]
    assert info['adopted_height_h'] == pytest.approx(1.00005)
    np.testing.assert_array_equal(np.array(result)[1::2], np.array(p)[1::2])
    np.testing.assert_array_equal(np.array(result)[:,0], np.array(p)[:,0])
    # 同一个top y而改变bottom y，推算顶高必须改变。
    altered = np.array(p); altered[1,1] += 1
    assert geometry(altered)['top3d'][0][1] != geometry(p)['top3d'][0][1]


def test_reject_bad_anchor_or_ambiguous_tolerance():
    p = points_for(np.array([[-1,-1],[1,-1],[1,1],[-1,1]]), [1,1.0003,1,1.1])
    for note in ['0', '5', '不确定']:
        with pytest.raises(ValueError): adjust(p, 'adopt_majority_height_plane', note)
    with pytest.raises(ValueError, match='容差敏感'): adjust(p, 'adopt_majority_height_plane', '1')


def test_delivered_catalog_preserves_exclusions_and_unreviewed_geometry():
    old = {r['target_id']:r for r in json.loads((BASE/'REFERENCE_CATALOG.json').read_text(encoding='utf-8'))}
    new = {r['target_id']:r for r in json.loads((OUT/'REFERENCE_CATALOG.json').read_text(encoding='utf-8'))}
    changed = json.loads((OUT/'ADOPTED_REFERENCES.json').read_text(encoding='utf-8'))
    ids = {r['target_id'] for r in changed}
    assert len(ids) == 30 and new.keys() == old.keys()
    for tid, r in new.items():
        if tid not in ids:
            assert r == old[tid]
            continue
        for key in ('current_target','image_analysis_blocked','image_analysis_hold_reasons','floor_xz_h'):
            assert r[key] == old[tid][key]
        assert r['current_target'] and not r['image_analysis_blocked'] and not r['image_analysis_hold_reasons']
        np.testing.assert_array_equal(np.array(r['points_1024x512'])[1::2], np.array(old[tid]['points_1024x512'])[1::2])
        assert np.ptp(np.array(r['geometry']['top3d'])[:,1]) < 1e-10
        assert r['score_status_for_reference_version'] == 'not_recomputed'
