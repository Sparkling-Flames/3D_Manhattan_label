import copy
import warnings

import pytest
from shapely.geometry import box, shape

from tools.thesis_main.analysis.lee_consensus_demos_20261003 import build_case, annotation_projection, region_projection


def test_demo_retiles_prefixes_keeps_independent_equal_shapes_and_gt_out_of_votes(monkeypatch):
    from tools.thesis_main.analysis import lee_consensus_demos_20261003 as module
    original_basis = module.integration_basis
    def warned(*args):
        result = original_basis(*args)
        warnings.warn('reference integration diagnostic', RuntimeWarning)
        return result
    monkeypatch.setattr(module, 'integration_basis', warned)
    records = [dict(id=f'R{i}', worker=f'P{i}', footprint=list(p.exterior.coords),
                    order_status='default_unreviewed', ring_confirmed=False)
               for i, p in enumerate([box(0, 0, 2, 2), box(1, 0, 3, 2), box(0, 0, 2, 2)])]
    original = copy.deepcopy(records)
    a = build_case(records, {'original': list(box(0, 0, 2, 2).exterior.coords)})
    b = build_case(records, {'original': list(box(10, 10, 12, 12).exterior.coords)})
    assert records == original
    assert len(a['steps']) == 3
    two = a['steps'][1]
    assert shape(two['regions']['mv50']).area == pytest.approx(6)
    assert shape(two['regions']['mv_strict']).area == pytest.approx(2)
    assert two['tie_area_h2'] == pytest.approx(4)
    assert shape(a['steps'][2]['regions']['mv50']).equals(box(0, 0, 2, 2))
    assert a['checks']['prefixes_rebuilt'] == 3
    assert a['checks']['max_geometry_difference_h2'] < 1e-10
    assert a['checks']['max_iou_difference'] < 1e-10
    assert any(w['message'] == 'reference integration diagnostic' for w in a['warnings'])
    assert [s['regions'] for s in a['steps']] == [s['regions'] for s in b['steps']]
    assert a['steps'][0]['metrics']['mv50']['original']['iou'] != b['steps'][0]['metrics']['mv50']['original']['iou']


def test_erp_projection_preserves_singleton_points_ring_seam_and_holes():
    import numpy as np
    from tools.label_studio.panorama_studio.geometry import project_pixel
    from shapely.geometry import Polygon, mapping
    floor = [[-2,-2],[2,-2],[2,2],[-2,2]]
    points = [p for x,z in floor for p in [project_pixel([x,1.4,z],1024,512),project_pixel([x,-1,z],1024,512)]]
    record = dict(id='R1',worker='P1',points=points,footprint=floor,source_pair_indices=[3,1,0,2],
                  source_point_indices=list(range(8)),source_point_labels=[f'p{i}' for i in range(8)])
    frozen = copy.deepcopy(record)
    actual = annotation_projection(record)
    assert record == frozen
    assert actual['points'] == points
    assert actual['source_pair_indices'] == [3,1,0,2]
    assert actual['floor_roundtrip_max_px'] < 1e-10
    assert actual['footprint_max_error_h'] < 1e-10
    single = build_case([record], {'original':floor})['steps'][0]['regions']['mv50']
    projected = region_projection(single)
    assert len(projected) == 1 and not projected[0]['hole']
    assert all(abs(b[0]-a[0])<=512 for ring in projected for path in ring['paths'] for a,b in zip(path,path[1:]))
    assert len(projected[0]['paths']) > len(floor)  # rear edge splits at ERP seam
    expected=np.asarray(points[1::2]); got=np.asarray(projected[0]['vertices'])[:-1]
    for p in got:
        assert min(np.linalg.norm(p-q) for q in expected) < 1e-10
    holed=Polygon(floor, [[[-.2,-.2],[.2,-.2],[.2,.2],[-.2,.2]]])
    holes=region_projection(mapping(holed))
    assert [r['hole'] for r in holes] == [False, True]
