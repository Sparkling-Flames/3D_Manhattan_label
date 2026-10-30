import json
import math
from pathlib import Path
from shapely.geometry import Polygon

BASE=Path(__file__).resolve().parents[1]/'research/data/doorway_review_20261030'
PREP=BASE/'curve_preparation_v21'
OUT=PREP/'full_review_20261031'
def read(path):return json.loads(path.read_text(encoding='utf8'))

def test_full_inventory_and_gt_containment():
    cases=json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']
    gt={c['image']:Polygon(c['floor']) for c in cases}
    rows=read(OUT/'ALIGNMENT_DECISIONS.json')
    assert len(rows)==len({r['image'] for r in rows})==20
    assert len(read(OUT/'ISSUE_LEDGER.json'))==20
    count=0
    for r in rows:
        if r['status']=='excluded':continue
        polygons=[Polygon(p) for p in r['space_polygons']]
        assert all(p.is_valid and p.area>0 and p.difference(gt[r['image']]).area<1e-9 for p in polygons)
        assert polygons[0].intersection(polygons[1]).area<1e-9
        count+=2
    assert count==36

def test_corrected_rectangles_follow_reference_axis():
    rows=read(OUT/'ALIGNMENT_DECISIONS.json')
    for name in ['uNb9QFRL6hY-47','uNb9QFRL6hY-83']:
        r=next(r for r in rows if r['image']==name);angle=r.get('display_yaw',0)
        for vertices in r['space_polygons']:
            local=[[x*math.cos(angle)+z*math.sin(angle),-x*math.sin(angle)+z*math.cos(angle)] for x,z in vertices]
            p=Polygon(local)
            assert abs(p.area-p.envelope.area)<1e-9
    r=next(r for r in rows if r['image']=='uNb9QFRL6hY-47')
    assert r['display_yaw']==r['adopted_axis_radians']==-.004509708399080105

def test_user_band_and_existing_decisions_preserved():
    rows=read(OUT/'ALIGNMENT_DECISIONS.json');by={r['image']:r for r in rows}
    band=by['7y3sRwLe3Va-18']['doorway_band']
    assert band['near']==.02116 and band['far']==.14475211237448768
    assert len(by['7y3sRwLe3Va-18']['diagnostic_regions'])==1
    b6=by['B6ByNegPMKs-42'];original=read(PREP/'USER_REVIEW_FINAL_RECEIVED.json')['cases'][b6['image_id']]
    assert b6['cuts']==original['cuts']
    q24=by['q9vSo1VnCiC-24']
    assert q24['scope_pending'] and q24['cuts'] is None
    p=Polygon(q24['space_polygons'][0]);assert p.convex_hull.area-p.area>.01

def test_closeout_lines_match_space_regions():
    rows={r['image']:r for r in read(OUT/'ALIGNMENT_DECISIONS.json')}
    r=rows['7y3sRwLe3Va-06']
    assert r['cuts'][0]['line'][0][0]==max(p[0] for p in r['space_polygons'][0])
    r=rows['7y3sRwLe3Va-18']
    assert abs(max(p[1] for p in r['space_polygons'][0])-.02116)<1e-12
    assert abs(min(p[1] for p in r['space_polygons'][1])-.14475211237448768)<1e-12
    assert rows['jtcxE69GiFV-12']['doorway_adjudication']=='用户确认可标的门洞交界'
