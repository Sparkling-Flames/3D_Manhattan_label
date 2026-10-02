import numpy as np
import pytest
from shapely.geometry import box

from tools.thesis_main.analysis.worker_profiles_20261003 import (
    area_metrics, calibrate, composition_stats, panel_records,
)
from tools.thesis_main.analysis.lee_tile_precision_20261003 import integration_basis, subset_mask
from tools.thesis_main.analysis.lee_tile_stage1_20261002 import tile_consensus, region_iou


def test_area_centroid_and_lobo_do_not_use_target_building():
    ref = list(box(0, 0, 2, 2).exterior.coords)[:-1]
    moved = list(box(1, 0, 3, 2).exterior.coords)[:-1]
    m = area_metrics(moved, ref)
    assert m['iou'] == pytest.approx(1/3)
    assert m['centroid_distance_h'] == pytest.approx(1)
    assert m['centroid_normalized'] == pytest.approx(.5)
    same_center = area_metrics(list(box(-1, -1, 3, 3).exterior.coords)[:-1], ref)
    assert same_center['centroid_distance_h'] == 0
    assert same_center['iou'] == pytest.approx(.25)
    scores = np.array([[.9, .8, .4, .2], [.1, .3, .7, .9], [.8, .7, .3, .1], [.2, .6, .9, .4]])
    buildings = ['train', 'target', 'train2', 'target']
    first = calibrate(scores, buildings, 'target')
    scores[1] = [1, 0, .9, .5]
    scores[3] = [0, 1, .8, .9]
    second = calibrate(scores, buildings, 'target')
    assert np.array_equal(first['higher'], [True, True, False, False])
    np.testing.assert_array_equal(first['mean'], second['mean'])
    with pytest.raises(ValueError, match='cutoff_tie'):
        calibrate(np.ones((4, 4)), buildings, 'target')


@pytest.mark.parametrize('method', ['mv50', 'mv_strict'])
def test_exact_composition_and_member_area_against_independent_geometry(method):
    records = [dict(id=str(j), worker=str(j), footprint=list(box(j/3, 0, j/3+1, 1).exterior.coords)[:-1]) for j in range(4)]
    reference = list(box(0, 0, 1, 1).exterior.coords)[:-1]
    basis = integration_basis(records, {'original': reference})
    members = np.array([[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]])
    masks = np.array([subset_mask(s) for s in members], dtype=np.uint32)
    rows, values = composition_stats(basis, masks, members, np.array([True, True, False, False]), method)
    assert [r['subset_n'] for r in rows] == [1, 4, 1]
    middle = rows[1]
    geometries = [tile_consensus([records[j] for j in s])['regions'][method] for s in members[1:5]]
    direct = [region_iou(g, box(0, 0, 1, 1)) for g in geometries]
    assert middle['iou_mean'] == pytest.approx(np.mean(direct))
    assert middle['iou_sd'] == pytest.approx(np.std(direct))
    pair_area = np.mean([a.symmetric_difference(b).area for a in geometries for b in geometries])
    assert middle['member_symdiff_h2'] == pytest.approx(pair_area)
    assert sum(r['subset_n']*r['iou_mean'] for r in rows)/6 == pytest.approx(values['original'].mean())


def test_panel_does_not_silently_drop_failed_or_duplicate_people():
    p = list(box(0, 0, 1, 1).exterior.coords)[:-1]
    record = dict(id='a', worker='a', condition='manual', independent=True, consensus_eligible=True,
                  main_consensus_gate={'status':'main_candidate'}, quality_candidate=True,
                  main_quality_gate={'status':'candidate_pending_geometry'}, footprint=p)
    image = dict(code='image', annotations=[record, dict(record, id='b', worker='b')],
                 references=[dict(version='original', footprint=p)])
    data = dict(schema='lee_tile_stage1_input_v1', images=[image])
    block = dict(images=['image'], workers='a|b')
    assert panel_records(data, block)[0] == ['a', 'b']
    image['annotations'][1]['footprint'] = None
    with pytest.raises(ValueError, match='quality_or_geometry_unavailable'):
        panel_records(data, block)
    image['annotations'][1].update(footprint=p, worker='a')
    with pytest.raises(ValueError, match='nonrectangular_or_duplicate_worker_panel'):
        panel_records(data, block)
