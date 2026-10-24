"""Check synthetic 3D surfaces, not real-image eligibility or ground truth."""
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

from tools.thesis_main.analysis import build_oos_schematics_20261025 as drawing


def test_surfaces_are_non_degenerate_and_planar():
    for kind in drawing.TITLES:
        for surface in drawing.scene(kind):
            vertices = np.asarray(surface['vertices'],dtype=float)
            # Polygon rank: all surfaces are real 2D planes in 3D, never warped quads.
            assert np.linalg.matrix_rank(vertices[1:]-vertices[0],tol=1e-9)==2,(kind,surface['label'])


def test_features_match_their_labels():
    slant=next(s for s in drawing.scene('oblique_wall') if s['label']=='oblique wall')
    points=np.asarray(slant['vertices'])
    horizontal=points[1]-points[0]
    assert horizontal[0]!=0 and horizontal[1]!=0 and horizontal[2]==0
    assert np.ptp(drawing.project(points)[:,0])>.7  # Avoid an edge-on, unreadable wall.
    roof=next(s for s in drawing.scene('sloped_ceiling') if s['label']=='ceiling')
    vertices=np.asarray(roof['vertices'])
    assert np.allclose(vertices[:,2],2.05+.24*vertices[:,0])
    levels=[s for s in drawing.scene('stepped_ceiling') if s['label'] in ['high ceiling','low ceiling']]
    assert len(levels)==2
    assert all(len({p[2] for p in s['vertices']})==1 for s in levels)
    assert levels[0]['vertices'][0][2]!=levels[1]['vertices'][0][2]


def test_raised_floor_does_not_retain_a_false_lower_floor():
    scene=drawing.scene('stepped_floor')
    assert not any(s['label']=='floor' for s in scene)
    floors=[s for s in scene if s['label']=='floor level']
    assert len(floors)==5
    # Every interior x coordinate is covered by one floor elevation only.
    for x in [.6,1.35,1.65,1.95,3]:
        covering=[s for s in floors if min(p[0] for p in s['vertices'])<x<max(p[0] for p in s['vertices'])]
        assert len(covering)==1
    side=next(s for s in scene if s['label']=='side wall')
    assert min(p[2] for p in side['vertices'])==1.2


def test_doorway_is_open_below_the_lintel():
    def occupied(y,z):
        return sum(y0<y<y1 and z0<z<z1 for y0,y1,z0,z1 in drawing.DOORWAY_BLOCKS)
    assert occupied(1.45,1.15)==0
    assert occupied(1.45,2.4)==1
    assert occupied(.3,1.15)==1
    assert occupied(2.6,1.15)==1


def test_paper_exports_are_readable():
    stems=['OOS_'+key for key in drawing.TITLES]+['OOS_construction_plate','DOORWAY_spatial_boundary']
    for stem in stems:
        svg=ET.parse(drawing.OUT/f'{stem}.svg').getroot()
        assert svg.tag.endswith('svg')
        assert any('omitted-front-corner' in el.get('id','') for el in svg.iter())
        assert (drawing.OUT/f'{stem}.pdf').read_bytes().startswith(b'%PDF-')
        with Image.open(drawing.OUT/f'{stem}.png') as im:
            assert min(im.size)>=1500
            assert round(im.info['dpi'][0])==300
