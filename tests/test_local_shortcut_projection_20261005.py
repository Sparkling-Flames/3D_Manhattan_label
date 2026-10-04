import copy
import json

import numpy as np
import pytest

from tools.thesis_main.analysis.local_shortcut_projection_20261005 import (
    ARCHIVE, diagnose_shortcut, segment_at_longitude,
)


def record(image, rid):
    return next(r for r in json.loads((ARCHIVE/'inputs'/f'{image}.json').read_text())['records'] if r['id']==rid)


@pytest.mark.parametrize('image,rid,index,expected', [
    ('rPc6DW4iMge-06', 'R01557', 6, [5.114690188599752, -8.829622144546931]),
    ('uNb9QFRL6hY-67', 'R02928', 3, [-120.4654071420037, 126.07936863765866]),
])
def test_real_deleted_longitude_values_and_source_immutability(image, rid, index, expected):
    source = record(image, rid); before = copy.deepcopy(source)
    result = diagnose_shortcut(source, index)
    assert source == before
    assert result['measurement'] == 'new_chord_minus_removed_point_at_removed_longitude_only'
    assert [result[s]['signed_dy_px'] for s in ('top', 'bottom')] == pytest.approx(expected, abs=1e-9)
    assert all(result[s]['status']=='ok' for s in ('top', 'bottom'))
    assert all(result[s]['abs_dy_px']==abs(result[s]['signed_dy_px']) for s in ('top', 'bottom'))


def test_seam_and_phase_preserve_same_local_projection_differences():
    source = record('rPc6DW4iMge-06', 'R01557')
    expected = diagnose_shortcut(source, 6)
    for shift in (0., 723.5, 1024.):
        shifted = copy.deepcopy(source)
        shifted['points'] = [[(x+shift)%1024., y] for x,y in source['points']]
        result = diagnose_shortcut(shifted, 6)
        for side in ('top', 'bottom'):
            assert result[side]['status']=='ok'
            assert result[side]['signed_dy_px']==pytest.approx(expected[side]['signed_dy_px'], abs=1e-9)


def test_segment_statuses_do_not_invent_unique_projected_points():
    # x=512 faces -Z; all intervals below use explicit 3D segment geometry.
    assert segment_at_longitude([0., 1., -1.], [0., 2., -2.], 512.)['status']=='non_unique'
    assert segment_at_longitude([1., 1., -1.], [1., 1., -2.], 512.)['status']=='not_covered'
    assert segment_at_longitude([0., 1., 1.], [0., 2., 2.], 512.)['status']=='not_covered'
    assert segment_at_longitude([0., 1., -1.], [0., 1., -1.], 512.)['status']=='degenerate'
    assert segment_at_longitude([0., 1., -1.], [0., 2., -1.], 512.)['status']=='non_unique'
    assert segment_at_longitude([0., 1., 0.], [0., 2., 0.], 512.)['status']=='degenerate'
    hit = segment_at_longitude([-1., -1., -2.], [1., -1., -2.], 512.)
    assert hit['status']=='ok'
    assert hit['segment_parameter']==pytest.approx(.5)
    assert np.asarray(hit['point_3d_h'])==pytest.approx([0., -1., -2.])
