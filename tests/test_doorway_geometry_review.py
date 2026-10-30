import json
import math
from pathlib import Path
from shapely.geometry import Polygon

ROOT=Path(__file__).resolve().parents[1]
PREP=ROOT/'research/data/doorway_review_20261030/curve_preparation_v21'
OUT=PREP/'new_geometry_review_20261031'

def read(path):return json.loads(path.read_text(encoding='utf8'))

def test_q9_uses_adopted_axis_and_preserves_reference():
    binding=read(OUT/'Q9_13_ADOPTION_BINDING.json')
    source=ROOT/binding['source']
    adopted=next(r for r in read(source/'ADOPTED_REFERENCES.json') if r['target_id']==binding['target_id'])
    ceiling=next(r for r in read(source/'ceiling_adopted_20261028/ADOPTED_REFERENCES.json') if r['target_id']==binding['target_id'])
    assert binding['axis_radians']==adopted['axis_radians']
    assert binding['geometry']==ceiling['geometry']
    r=next(r for r in read(OUT/'ALIGNMENT_DECISIONS.json') if r['image']=='q9vSo1VnCiC-13')
    theta=r['display_yaw']
    for cut in r['cuts']:
        a,b=cut['line']
        assert abs((a[0]-b[0])*math.cos(theta)+(a[1]-b[1])*math.sin(theta))<1e-10

def test_derived_spaces_and_pending_status():
    rows=read(OUT/'ALIGNMENT_DECISIONS.json')
    assert len(rows)==20
    for row in rows:
        if 'space_polygons' not in row:continue
        a,b=map(Polygon,row['space_polygons'])
        assert a.is_valid and b.is_valid and min(a.area,b.area)>0
        assert a.intersection(b).area<1e-8
    q24=next(r for r in rows if r['image']=='q9vSo1VnCiC-24')
    assert q24['status']=='uncertain' and q24['cuts'] is None
    for name in ['q9vSo1VnCiC-04','q9vSo1VnCiC-24']:
        poly=Polygon(next(r for r in rows if r['image']==name)['space_polygons'][1])
        assert abs(poly.area-poly.envelope.area)/poly.area<1e-4
