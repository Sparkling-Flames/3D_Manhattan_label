import copy

import pytest
from shapely.geometry import Polygon, box

from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus, replay_group


def record(i, polygon):
    return dict(id=f'R{i}', worker=f'P{i}', footprint=list(polygon.exterior.coords)[:-1])


def test_tiles_partition_real_regions_and_obey_inclusive_ties():
    a, b = box(0, 0, 2, 2), box(1, 0, 3, 2)
    result = tile_consensus([record(1, a), record(2, b)])
    assert len(result['mesh']['tiles']) == 3
    assert result['regions']['mv50'].equals(a.union(b))
    assert result['regions']['mv_strict'].equals(a.intersection(b))
    assert result['mesh']['votes'].shape == (2, 3)
    for i, p in enumerate((a, b)):
        assert result['mesh']['area'][result['mesh']['votes'][i]].sum() == pytest.approx(p.area)


def test_consensus_ignores_order_and_vertex_density_and_preserves_holes():
    a = Polygon([(0, 0), (1, 0), (2, 0), (2, 2), (0, 2)])
    b = box(1, 0, 3, 2)
    rows = [record(1, a), record(2, b), record(3, a)]
    original = copy.deepcopy(rows)
    assert tile_consensus(rows)['regions']['mv50'].equals(a)
    rows[0]['footprint'].reverse()
    assert tile_consensus(rows[::-1])['regions']['mv50'].equals(a)
    # Four independent strips enclose an uncovered centre; no closing/repair is allowed.
    strips = [box(0, 0, 3, 1), box(0, 2, 3, 3), box(0, 1, 1, 2), box(2, 1, 3, 2)]
    out = tile_consensus([record(i, p) for i, p in enumerate(strips)])
    assert out['regions']['mv50'].is_empty
    assert sum(out['mesh']['area']) == pytest.approx(8)
    assert original[0]['footprint'] != rows[0]['footprint']


def test_duplicates_invalid_geometry_and_missing_votes_are_not_silently_repaired():
    a = record(1, box(0, 0, 2, 2))
    with pytest.raises(ValueError, match='duplicate'):
        tile_consensus([a, a])
    with pytest.raises(ValueError, match='invalid_footprint'):
        tile_consensus([record(2, Polygon([(0, 0), (2, 2), (0, 2), (2, 0)]))])
    missing = dict(id='R2', worker='P2', footprint=None)
    group = dict(code='test', condition='manual', gate='main_candidate', records=[a, missing], references={})
    result = replay_group(group, permutations=3, seed=42)
    last = [r for r in result['rows'] if r['k'] == 2]
    assert last and all(r['status'] == 'unavailable' and r['k'] == 2 for r in last)
    assert all(r['original_iou'] is None for r in result['rows'])


def test_replay_is_gt_blind_and_full_set_is_mechanically_order_invariant():
    rows = [record(i, box(i / 5, 0, 2 + i / 5, 2)) for i in range(3)]
    group = dict(code='test', condition='manual', gate='main_candidate', records=rows,
                 references={'original': list(box(0, 0, 2, 2).exterior.coords)[:-1]})
    a = replay_group(group, permutations=4, seed=7)
    group['references']['original'] = list(box(10, 10, 12, 12).exterior.coords)[:-1]
    b = replay_group(group, permutations=4, seed=7)
    assert [r['members'] for r in a['rows']] == [r['members'] for r in b['rows']]
    assert [r['area_h2'] for r in a['rows']] == [r['area_h2'] for r in b['rows']]
    assert any(r['original_iou'] != s['original_iou'] for r, s in zip(a['rows'], b['rows']))
    assert all(r['member_distance_mean'] == 0 for r in a['summary'] if r['k'] == 3)
    assert all(r['unique_subsets'] == 1 for r in a['summary'] if r['k'] == 3)


def test_floating_geometry_warnings_are_exposed(monkeypatch):
    import warnings
    from tools.thesis_main.analysis import lee_tile_stage1_20261002 as module
    original = module.region_mesh
    def with_warning(polygons):
        warnings.warn('numeric diagnostic', RuntimeWarning)
        return original(polygons)
    monkeypatch.setattr(module, 'region_mesh', with_warning)
    result = tile_consensus([record(1, box(0, 0, 1, 1))])
    assert result['warnings'] == ['numeric diagnostic']
