from itertools import combinations

import numpy as np
import pytest
from shapely.geometry import box

from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus, region_iou
from tools.thesis_main.analysis.lee_tile_precision_20261003 import (
    integration_basis, measure_masks, exact_ks, subset_mask, mc_bound, area_expectations,
)


def records():
    return [dict(id=f'R{i}', worker=f'P{i}', footprint=list(box(i, 0, i+2, 2).exterior.coords)[:-1])
            for i in range(3)]


def test_offline_refinement_matches_every_current_subset_and_area_expectation():
    rows = records(); gt = box(0, 0, 2, 2)
    basis = integration_basis(rows, {'original': list(gt.exterior.coords)[:-1]})
    for k in range(1, 4):
        subsets = list(combinations(range(3), k))
        masks = np.array([subset_mask(s) for s in subsets], dtype=np.uint32)
        for method in ('mv50', 'mv_strict'):
            measured = measure_masks(basis, masks, k, method)
            areas = []
            for j, sub in enumerate(subsets):
                region = tile_consensus([rows[i] for i in sub])['regions'][method]
                assert measured['original'][j] == pytest.approx(region_iou(region, gt))
                areas.append(region.area)
            expected = area_expectations(basis, k, method)['original']
            assert expected['expected_area_h2'] == pytest.approx(np.mean(areas))
    # Two single regions have IoU 1 and 1/3, so ratios must be taken before averaging.
    assert measure_masks(basis, np.array([1, 2], dtype=np.uint32), 1, 'mv50')['original'].mean() == pytest.approx(2/3)


def test_gt_cannot_change_votes_and_missing_geometry_keeps_failure():
    a = integration_basis(records(), {})
    b = integration_basis(records(), {'other': list(box(8, 8, 9, 9).exterior.coords)[:-1]})
    assert np.array_equal(a['patterns'], b['patterns'])
    assert np.array_equal(a['area'], b['area'])
    bad = records(); bad[1]['footprint'] = None
    with pytest.raises(ValueError, match='unavailable_footprint'):
        integration_basis(bad, {})
    with pytest.raises(ValueError, match='duplicate_worker'):
        integration_basis([records()[0], dict(records()[1], worker='P0')], {})


def test_precision_scope_and_singleton_are_explicit():
    assert exact_ks(1) == [1]
    assert exact_ks(8) == list(range(1, 9))
    assert exact_ks(24) == [1, 2, 22, 23, 24]
    assert 0 < mc_bound(16384, 326) < .02
    assert mc_bound(16384, 0) == 0
    with pytest.raises(ValueError):
        mc_bound(0, 326)


def test_nested_tiling_warnings_are_not_lost(monkeypatch):
    from tools.thesis_main.analysis import lee_tile_precision_20261003 as module
    original = module.tile_consensus
    def warned(rows):
        out = original(rows); out['warnings'].append('test diagnostic'); return out
    monkeypatch.setattr(module, 'tile_consensus', warned)
    assert 'test diagnostic' in integration_basis(records(), {})['warnings']
