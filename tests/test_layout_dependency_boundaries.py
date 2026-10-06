"""Geometry and display consumers do not import research workflow entrypoints."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from tools.thesis_main.analysis.region_mesh import region_mesh


def test_region_mesh_preserves_holes_components_and_duplicate_observers():
    holed = Polygon(box(0, 0, 4, 4).exterior.coords,
                     [box(1, 1, 3, 3).exterior.coords])
    crossing = box(2, -1, 5, 2)
    island = box(10, 0, 11, 1)
    polygons = [holed, crossing, holed, island]
    mesh = region_mesh(polygons)

    assert unary_union(mesh['tiles']).equals(unary_union(polygons))
    np.testing.assert_array_equal(mesh['votes'][0], mesh['votes'][2])
    for i, polygon in enumerate(polygons):
        selected = mesh['votes'][i]
        assert unary_union([tile for tile, keep in zip(mesh['tiles'], selected)
                            if keep]).equals(polygon)
        assert mesh['area'][selected].sum() == pytest.approx(polygon.area)
        np.testing.assert_allclose(mesh['moment'][selected].sum(axis=0),
                                   polygon.area * np.array(polygon.centroid.coords)[0])


def test_historical_imports_reexport_the_same_geometry_helpers():
    from tools.thesis_main.analysis import audit_supervisor_gt_sensitivity_20260922 as audit
    from tools.thesis_main.analysis import layout_display_projection as projection
    from tools.thesis_main.analysis import lee_consensus_demos_20261003 as demo

    assert audit.region_mesh is region_mesh
    for name in ('projected_edge', 'region_projection', 'annotation_projection',
                 'compact_paths', 'project_display_record'):
        assert getattr(demo, name) is getattr(projection, name)


@pytest.mark.parametrize('module,forbidden', [
    ('region_mesh', ('audit_supervisor_gt_sensitivity_20260922',)),
    ('lee_tile_stage1_20261002', ('audit_supervisor_gt_sensitivity_20260922',)),
    ('layout_display_projection', ('lee_consensus_demos_20261003', 'lee_tile_stage1_20261002',
                                   'lee_tile_precision_20261003')),
    ('point_route_panel_view_20261005', ('lee_consensus_demos_20261003', 'lee_tile_stage1_20261002',
                                       'lee_tile_precision_20261003')),
    ('point_route_review_view_20261006', ('lee_consensus_demos_20261003', 'lee_tile_stage1_20261002',
                                        'lee_tile_precision_20261003')),
    ('consensus_result_studio_20261004', ('lee_consensus_demos_20261003', 'lee_tile_stage1_20261002',
                                        'lee_tile_precision_20261003')),
])
def test_geometry_entrypoints_do_not_load_analysis_workflows(module, forbidden):
    # A clean interpreter catches accidental transitive imports even when another
    # test has already imported the historical compatibility entrypoints.
    prefix = 'tools.thesis_main.analysis.'
    script = (
        'import importlib, sys\n'
        f'importlib.import_module({prefix + module!r})\n'
        f'forbidden = {tuple(prefix + name for name in forbidden)!r}\n'
        'loaded = [name for name in sys.modules if name in forbidden or name == "pandas"]\n'
        'assert not loaded, loaded\n'
    )
    result = subprocess.run([sys.executable, '-B', '-c', script],
                            cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
