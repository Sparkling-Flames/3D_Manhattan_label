import copy
import warnings

import pytest
from shapely.geometry import box, shape

from tools.thesis_main.analysis.lee_consensus_demos_20261003 import build_case


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
